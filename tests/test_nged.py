"""NGED's open live data, and the datastore selection that reaches it.

National Grid Electricity Distribution publishes its live layer as open data (Icebreaker One
sensitivity class IB1-O), and it answers with no credential at all. Reaching it needs one awkward
thing done right: the portal's `datastore_active` flag cannot be trusted to pick a resource.

Measured 2026-09-19: thirteen of the fourteen East Midlands GSP resources are flagged
`datastore_active: false` and answer queries anyway, while the genuinely non-tabular entries (a map, a
Data Sharing Assessment PDF) answer 404. So the selection walks the CSV resources in turn rather than
trusting the flag, which is what these tests pin down.

The record shapes below are the ones the portal actually returns, taken from live responses.
"""
from __future__ import annotations

import asyncio
import pathlib
import sys
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from custom_components.hagrid.api import (  # noqa: E402
    NationalGridClient,
    RegisteredKeyRequired,
)
from custom_components.hagrid.const import (  # noqa: E402
    NGED_DATASETS,
    NGED_GSP_DATASETS,
    NGED_LICENCE_AREAS,
)

# Live Detailed Power Cuts, verbatim field names.
DETAILED = {
    "_id": 3,
    "upload_date": "2026-09-19T23:25:44.231000",
    "licence_area": "West Midlands",
    "fault_id": "FPI-1234567",
    "confirmed_off": "421",
    "predicted_off": "421",
    "restored": "0",
    "status": "In Progress",
    "planned": "false",
    "category": "HV OVERHEAD",
}

# Live Power Cuts, the summary resource, same incident in its own field names.
SUMMARY = {
    "_id": 7,
    "Upload Date": "2026-09-19T23:25:44.231000",
    "Region": "South West",
    "Incident ID": "INC-987654",
    "Confirmed Off": "88",
    "Predicted Off": "88",
    "Restored": "12",
    "Status": "In Progress",
    "Planned": "true",
    "Category": "LV UNDERGROUND",
}


class _FakeResponse:
    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self._payload = payload

    async def json(self) -> dict[str, Any]:
        return self._payload

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class _FakeSession:
    """Serves package_show and datastore_search from dicts, so the selection logic is what is tested."""

    def __init__(
        self,
        resources: list[dict[str, Any]],
        datastores: dict[str, tuple[int, dict[str, Any]]],
    ) -> None:
        self._resources = resources
        self._datastores = datastores
        self.searched: list[str] = []

    def get(self, url: str, params: dict[str, Any] | None = None, headers: dict | None = None):
        params = params or {}
        if url.endswith("package_show"):
            return _FakeResponse(200, {"success": True, "result": {"resources": self._resources}})
        resource_id = params["resource_id"]
        self.searched.append(resource_id)
        status, payload = self._datastores.get(
            resource_id,
            (
                404,
                {
                    "success": False,
                    "error": {"message": f'Not found: Resource "{resource_id}" was not found.'},
                },
            ),
        )
        return _FakeResponse(status, payload)


def _rows(records: list[dict[str, Any]]) -> tuple[int, dict[str, Any]]:
    return 200, {"success": True, "result": {"records": records, "total": len(records)}}


def _client(session: _FakeSession) -> NationalGridClient:
    return NationalGridClient(session)  # type: ignore[arg-type]


def test_both_published_shapes_normalise_to_the_same_fields() -> None:
    """Which of the two resources the portal has populated must not change what the caller sees."""
    detailed = NationalGridClient._parse_nged_fault(DETAILED)
    summary = NationalGridClient._parse_nged_fault(SUMMARY)

    assert detailed is not None and summary is not None
    assert detailed.id == "FPI-1234567"
    assert detailed.area == "West Midlands"
    assert detailed.estimated_customers == 421
    assert detailed.planned is False
    assert detailed.status == "In Progress"

    assert summary.id == "INC-987654"
    assert summary.area == "South West"
    assert summary.estimated_customers == 88
    assert summary.planned is True


def test_a_record_with_no_fault_id_is_skipped_rather_than_guessed() -> None:
    assert NationalGridClient._parse_nged_fault({"_id": 1, "Status": "In Progress"}) is None


def test_faults_can_be_filtered_to_one_licence_area() -> None:
    """A user in the West Midlands should not be shown a South West power cut."""
    session = _FakeSession(
        resources=[{"id": "detailed", "name": "Live Detailed Power Cuts", "format": "CSV"}],
        datastores={"detailed": _rows([DETAILED, SUMMARY])},
    )

    faults = asyncio.run(_client(session).get_nged_live_faults(licence_area="West Midlands"))

    assert [f.id for f in faults] == ["FPI-1234567"]


def test_selection_walks_past_a_resource_that_is_not_a_table() -> None:
    """The 404 walk, with nothing in the names to sort by: candidates stay in published order, so the
    first is tried, answers 404, and the call carries on to the next one instead of ending."""
    session = _FakeSession(
        resources=[
            {"id": "dsa-pdf", "name": "Data Sharing Assessment", "format": "CSV"},
            {"id": "the-table", "name": "Live Power Cuts", "format": "CSV"},
        ],
        datastores={"the-table": _rows([DETAILED])},
    )

    records = asyncio.run(_client(session)._datastore_search(NGED_DATASETS["live_power_cuts"]))

    assert records == [DETAILED]
    assert session.searched == ["dsa-pdf", "the-table"]


def test_a_named_resource_is_asked_first() -> None:
    session = _FakeSession(
        resources=[
            {"id": "other", "name": "Something Else", "format": "CSV"},
            {"id": "wanted", "name": "Live Detailed Power Cuts", "format": "CSV"},
        ],
        datastores={"wanted": _rows([DETAILED]), "other": _rows([SUMMARY])},
    )

    records = asyncio.run(
        _client(session)._datastore_search(NGED_DATASETS["live_power_cuts"], name="detailed")
    )

    assert records == [DETAILED]
    assert session.searched == ["wanted"]


def test_a_restricted_resource_says_so_instead_of_returning_nothing() -> None:
    """403 is the portal's "restricted to registered users", and it must not look like "no data"."""
    session = _FakeSession(
        resources=[{"id": "gated", "name": "Primary Substation Location", "format": "CSV"}],
        datastores={
            "gated": (
                403,
                {
                    "success": False,
                    "error": {"message": "Access denied: Resource access restricted to registered users"},
                },
            )
        },
    )

    try:
        asyncio.run(_client(session)._datastore_search("primary-substation-location"))
    except RegisteredKeyRequired:
        pass
    else:  # pragma: no cover
        raise AssertionError("a 403 must raise RegisteredKeyRequired")


def test_non_csv_resources_are_not_queried() -> None:
    session = _FakeSession(
        resources=[
            {"id": "pdf", "name": "Data Sharing Assessment", "format": "PDF"},
            {"id": "map", "name": "Live Power Cuts Map", "format": ""},
        ],
        datastores={},
    )

    assert asyncio.run(_client(session)._datastore_search("live-power-cuts")) == []
    assert session.searched == []


def test_every_nged_licence_area_the_carbon_api_names_has_a_gsp_package() -> None:
    """The routing is only free if the DNO string the config flow already has maps onto a package."""
    assert set(NGED_LICENCE_AREAS.values()) == set(NGED_GSP_DATASETS)


def test_a_ukpn_dno_string_is_not_an_nged_area() -> None:
    assert NGED_LICENCE_AREAS.get("UKPN London") is None
