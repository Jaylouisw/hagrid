"""Which network operator's power cuts to ask for, and reading each one's answer.

Two separate things are pinned here, both of which were wrong in the same way: the code was reading
field names that do not exist on the datasets it was calling.

  * UKPN publishes `geopoint`, `incidenttypename`, `postcodesaffected` and `nocustomeraffected`. The
    integration read `geo_point_2d`, `status`, `postcodearea` and `estimatedrestoredcustomers`, so
    every fault arrived with no coordinates, no postcode area, no affected customers and the numeric
    `incidenttype` standing in for the type text. The record below is a real one from the live
    dataset, 2026-09-19.
  * NGED is a different operator with a different portal, and which one a user belongs to has to be
    decided before anything is fetched, because the wrong operator's power cuts are worse than none.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from custom_components.hagrid.api import UKPNClient, nged_licence_area  # noqa: E402
from custom_components.hagrid.const import (  # noqa: E402
    NGED_LICENCE_AREAS,
    NGED_REGION_IDS,
)

# Verbatim from ukpn-live-faults, 2026-09-19, one incident, fields trimmed to the ones read here.
UKPN_RECORD = {
    "incidentreference": "INCD-632893-Z",
    "incidenttype": 2,
    "incidenttypename": "Restored",
    "incidentcategory": "47",
    "powercuttype": "Restored",
    "statusid": 5,
    "nocustomeraffected": 0,
    "postcodesaffected": "NR19 1;NR19 2",
    "geopoint": {"lon": 0.96436, "lat": 52.65082},
    "operatingzone": "NORWICH",
    "creationdatetime": "2026-09-19T19:09:41.237",
    "estimatedrestorationdate": "2026-09-20T00:30:00",
    "planneddate": None,
    "incidentcategorycustomerfriendlydescription": "Low voltage overhead network",
}


def test_ukpn_fault_reads_the_field_names_the_dataset_actually_publishes() -> None:
    fault = UKPNClient._parse_ukpn_fault(dict(UKPN_RECORD))

    assert fault is not None
    assert fault.id == "INCD-632893-Z"
    assert fault.latitude == pytest.approx(52.65082)
    assert fault.longitude == pytest.approx(0.96436)
    assert fault.postcode_area == "NR19 1"
    assert fault.status == "Restored"
    assert fault.incident_type == "Restored"
    assert fault.description == "Low voltage overhead network"
    assert fault.start_time is not None
    assert fault.estimated_restore_time is not None
    assert fault.planned is False


def test_ukpn_affected_customers_are_read_from_nocustomeraffected() -> None:
    record = dict(UKPN_RECORD)
    record["nocustomeraffected"] = 137

    fault = UKPNClient._parse_ukpn_fault(record)

    assert fault is not None and fault.estimated_customers == 137


def test_a_ukpn_planned_date_marks_the_cut_as_planned() -> None:
    """`planneddate` is populated for planned works, which is the signal the old code ignored."""
    record = dict(UKPN_RECORD)
    record["planneddate"] = "2026-09-21T09:00:00"
    record["incidenttypename"] = "In Progress"

    fault = UKPNClient._parse_ukpn_fault(record)

    assert fault is not None and fault.planned is True


def test_a_ukpn_record_without_an_incident_reference_is_skipped() -> None:
    record = dict(UKPN_RECORD)
    record.pop("incidentreference")

    assert UKPNClient._parse_ukpn_fault(record) is None


def test_ukpn_missing_timestamps_do_not_become_now() -> None:
    """A fabricated start time is worse than an absent one; the fields are optional to say so."""
    record = dict(UKPN_RECORD)
    record["creationdatetime"] = None
    record["estimatedrestorationdate"] = "not a timestamp"

    fault = UKPNClient._parse_ukpn_fault(record)

    assert fault is not None
    assert fault.start_time is None
    assert fault.estimated_restore_time is None


@pytest.mark.parametrize(
    ("dno", "expected"),
    [
        ("WPD West Midlands", "West Midlands"),
        ("WPD East Midlands", "East Midlands"),
        ("WPD South West", "South West"),
        ("WPD South Wales", "South Wales"),
    ],
)
def test_the_dno_string_carbon_intensity_returns_decides_the_operator(dno: str, expected: str) -> None:
    """The Carbon Intensity API still names NGED after its previous owner, which is why the mapping
    is keyed on those strings rather than on anything NGED calls itself."""
    assert nged_licence_area(dno, None) == expected


def test_a_ukpn_entry_is_not_given_nged_power_cuts() -> None:
    assert nged_licence_area("UKPN London", 13) is None
    assert nged_licence_area("SP Distribution", 2) is None


def test_the_region_id_is_the_fallback_when_there_is_no_dno_string() -> None:
    """An entry whose region was chosen by hand has no DNO, and the licence area still has to be
    worked out from the region id or a Midlands user would be shown London's faults."""
    assert nged_licence_area(None, 8) == "West Midlands"
    assert nged_licence_area("", 9) == "East Midlands"
    assert nged_licence_area(None, 7) == "South Wales"
    assert nged_licence_area(None, 11) == "South West"


def test_a_region_outside_nged_stays_with_ukpn() -> None:
    assert nged_licence_area(None, 13) is None  # London
    assert nged_licence_area(None, None) is None


def test_the_two_mappings_agree_on_the_four_areas() -> None:
    assert set(NGED_LICENCE_AREAS.values()) == set(NGED_REGION_IDS.values())
