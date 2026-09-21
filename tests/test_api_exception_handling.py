"""Exception-handling boundaries for GB API clients."""
from __future__ import annotations

import asyncio
import json
import pathlib
import sys
from typing import Any

import aiohttp
import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from custom_components.hagrid.api import CarbonIntensityClient  # noqa: E402


class _FakeResponse:
    def __init__(self, status: int = 200, payload: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.status = status
        self._payload = payload or {}
        self._error = error

    async def json(self) -> dict[str, Any]:
        if self._error is not None:
            raise self._error
        return self._payload

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class _FakeSession:
    def __init__(self, response: _FakeResponse | None = None, error: Exception | None = None) -> None:
        self._response = response or _FakeResponse()
        self._error = error

    def get(self, *_args: Any, **_kwargs: Any) -> _FakeResponse:
        if self._error is not None:
            raise self._error
        return self._response


def _request(session: _FakeSession):
    return asyncio.run(CarbonIntensityClient(session)._request("/intensity"))  # type: ignore[arg-type]


def test_carbon_intensity_request_handles_transport_failures() -> None:
    assert _request(_FakeSession(error=aiohttp.ClientError("connection refused"))) is None


def test_carbon_intensity_request_handles_json_decode_failures() -> None:
    decode_error = json.JSONDecodeError("invalid json", "{}", 0)
    assert _request(_FakeSession(response=_FakeResponse(error=decode_error))) is None


def test_carbon_intensity_request_does_not_hide_unexpected_errors() -> None:
    with pytest.raises(RuntimeError):
        _request(_FakeSession(error=RuntimeError("programming bug")))
