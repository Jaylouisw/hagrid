"""Shape tests for the HAGrid integration.

These exist because of a real bug, not for coverage's sake. `CircuitFlow` in `api.py` declared
`fuel_type: str | None = None` before `timestamp: datetime`, which Python dataclasses reject, so
*every* module in this integration raised at import:

    TypeError: non-default argument 'timestamp' follows default argument 'fuel_type'

Home Assistant could not import `config_flow`, never registered the handler, and reported the
user-visible symptom `Config flow could not be loaded: {"message":"Invalid handler specified"}`.

Nothing here needs a running Home Assistant: every failure mode it covers is an import-time or
registration-time failure, which is where this integration's real bugs have been found.
"""
from __future__ import annotations

import importlib
import json
import pathlib
import py_compile
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
INTEGRATION = REPO / "custom_components" / "hagrid"
MODULES = ["const", "api", "coordinator", "sensor", "config_flow"]

sys.path.insert(0, str(REPO))


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module: str) -> None:
    """Every module of the integration must import cleanly under the installed Home Assistant."""
    importlib.import_module(f"custom_components.hagrid.{module}")


def test_every_source_file_compiles() -> None:
    """Catches a syntax error anywhere, including in files no test imports."""
    for path in sorted(INTEGRATION.rglob("*.py")):
        py_compile.compile(str(path), doraise=True)


def test_manifest_domain_matches_directory() -> None:
    """Home Assistant maps the integration by folder name; a mismatch breaks the config flow."""
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    assert manifest["domain"] == INTEGRATION.name == "hagrid"
    for key in (
        "name",
        "version",
        "documentation",
        "issue_tracker",
        "codeowners",
        "config_flow",
        "requirements",
        "iot_class",
    ):
        assert key in manifest, f"manifest.json is missing {key!r}"
    assert manifest["config_flow"] is True


def test_hacs_manifest_is_present_and_parses() -> None:
    data = json.loads((REPO / "hacs.json").read_text())
    assert data.get("name")


def test_config_flow_handler_registers_in_home_assistant() -> None:
    """The registration Home Assistant relies on — the exact thing that was missing in 1.0.0."""
    from homeassistant import config_entries

    import custom_components.hagrid.config_flow as config_flow

    assert config_entries.HANDLERS.get("hagrid") is config_flow.HAGridConfigFlow


def test_map_card_js_is_inside_integration() -> None:
    """The JS file must live inside the integration so HACS installs it automatically."""
    js = INTEGRATION / "www" / "hagrid-map.js"
    assert js.is_file(), (
        f"{js} not found — the map-card JS must live inside the integration folder "
        "so that HACS installs it without any manual file-copy step"
    )


def test_manifest_frontend_dependency() -> None:
    """frontend must be loaded before async_setup adds the extra module URL."""
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    assert "frontend" in manifest.get("dependencies", []), (
        "'frontend' must be in manifest.json dependencies so HAGrid can call "
        "add_extra_js_url during async_setup"
    )


def test_circuit_flow_constructs_the_way_call_sites_do() -> None:
    """The dataclass behind the import-failure bug, built with the keyword arguments used in api.py."""
    from datetime import UTC, datetime

    from custom_components.hagrid.api import CircuitFlow

    now = datetime.now(UTC)
    flow = CircuitFlow(
        circuit_id="gen_wind",
        circuit_type="generation",
        name="WIND Generation",
        flow_mw=1.5,
        capacity_mw=None,
        direction="in",
        fuel_type="WIND",
        timestamp=now,
    )
    assert flow.timestamp is now
    assert flow.fuel_type == "WIND"
