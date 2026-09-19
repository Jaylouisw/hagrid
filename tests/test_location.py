"""The home-location lookup, and the shape of the config flow that uses it.

HAGrid asks for no postcode any more: it takes the home location already set in Home Assistant and
turns it into a UK postcode through postcodes.io, which the Carbon Intensity API's regional endpoints
then understand. Two things can go wrong there and they read very differently to a user, so they are
tested separately:

  * the coordinate is outside Great Britain (postcodes.io answers with a null result)
  * the lookup could not be made at all (transport error, or an HTTP status that is not 200)

The response shapes below are the ones measured against the live service on 2026-09-19, including the
null result for Home Assistant's own default location, which is not in the UK.
"""
from __future__ import annotations

import asyncio
import pathlib
import sys
from typing import Any

import aiohttp
import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from custom_components.hagrid.api import (  # noqa: E402
    GeocoderUnavailable,
    PostcodesIoClient,
)
from custom_components.hagrid.const import POSTCODES_IO_API  # noqa: E402

# Abbreviated from a real response: https://api.postcodes.io/postcodes?lon=-0.1276&lat=51.5072
GB_RESULT: dict[str, Any] = {
    "status": 200,
    "result": [
        {
            "postcode": "SW1A 2DX",
            "outcode": "SW1A",
            "country": "England",
            "region": "London",
            "latitude": 51.506897,
            "longitude": -0.127763,
        }
    ],
}

# What the same call returns for 52.3731339, 4.8903147, the coordinate Home Assistant ships with.
NOT_GB_RESULT: dict[str, Any] = {"status": 200, "result": None}


class _FakeResponse:
    """Enough of an aiohttp response for the one call the client makes."""

    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self._payload = payload

    async def json(self) -> dict[str, Any]:
        """The decoded body."""
        return self._payload

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class _FakeSession:
    """Enough of an aiohttp.ClientSession for the one call the client makes."""

    def __init__(self, status: int = 200, payload: dict[str, Any] | None = None,
                 error: Exception | None = None) -> None:
        self._response = _FakeResponse(status, payload or {})
        self._error = error
        self.requested_url: str = ""
        self.requested_params: dict[str, Any] = {}

    def get(self, url: str, params: dict[str, Any] | None = None) -> _FakeResponse:
        """Record the request and hand back the canned response."""
        self.requested_url = url
        self.requested_params = params or {}
        if self._error is not None:
            raise self._error
        return self._response


def _lookup(session: _FakeSession, lat: float = 51.5072, lon: float = -0.1276):
    return asyncio.run(PostcodesIoClient(session).reverse_geocode(lat, lon))  # type: ignore[arg-type]


def test_gb_coordinate_resolves_to_an_outcode() -> None:
    """The outcode is what the Carbon Intensity API's regional endpoints take."""
    session = _FakeSession(payload=GB_RESULT)

    location = _lookup(session)

    assert location is not None
    assert location.outcode == "SW1A"
    assert location.country == "England"


def test_the_request_sends_both_coordinates_in_the_order_the_service_expects() -> None:
    """postcodes.io takes lon before lat, and a swap returns a plausible wrong answer."""
    session = _FakeSession(payload=GB_RESULT)

    _lookup(session, lat=51.5072, lon=-0.1276)

    assert session.requested_url == f"{POSTCODES_IO_API}/postcodes"
    assert session.requested_params == {"lon": -0.1276, "lat": 51.5072, "limit": 1}


def test_coordinate_outside_great_britain_returns_nothing() -> None:
    """Not an error: the grid APIs are GB-only, and this is how the flow finds that out."""
    assert _lookup(_FakeSession(payload=NOT_GB_RESULT)) is None


def test_an_http_error_is_reported_as_the_service_being_unavailable() -> None:
    """Distinct from "not in GB", because the two need different words in the form."""
    with pytest.raises(GeocoderUnavailable):
        _lookup(_FakeSession(status=503, payload={}))


def test_a_transport_error_is_reported_as_the_service_being_unavailable() -> None:
    with pytest.raises(GeocoderUnavailable):
        _lookup(_FakeSession(error=aiohttp.ClientError("connection refused")))


def test_config_flow_asks_for_no_postcode() -> None:
    """The whole point of the change: a postcode is a question Home Assistant already knows the answer to.

    A shape test rather than a runtime one, in keeping with the rest of this suite: driving the flow
    for real needs a running Home Assistant, and what broke here before was the shape of the flow.
    """
    source = (REPO / "custom_components" / "hagrid" / "config_flow.py").read_text()

    assert "vol.Optional(CONF_POSTCODE)" not in source
    assert "CONF_POSTCODE: str" not in source
    assert "self.hass.config.latitude" in source
    assert "self.hass.config.longitude" in source


def test_config_flow_records_whether_the_region_came_from_the_home_location() -> None:
    """Which is what lets a moved home location correct itself, and a chosen region stay put."""
    source = (REPO / "custom_components" / "hagrid" / "config_flow.py").read_text()

    assert "CONF_USE_HOME_LOCATION: self._use_home_location" in source
    assert "self._use_home_location = False" in source
