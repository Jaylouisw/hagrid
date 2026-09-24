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


# ---------------------------------------------------------------------------------------------------
# The map card is served by the integration, not by a file the user copies. These tests call
# async_setup for real against a stub `hass.http`, because "the card is registered automatically" is
# a claim about what async_setup *does*, and a file-exists check cannot make it. The failure this
# guards against is silent: the integration loads, the sensors work, and the user's dashboard says
# the custom element does not exist.
# ---------------------------------------------------------------------------------------------------


class _RecordingHTTP:
    """Minimal stand-in for HomeAssistantHTTP, recording what async_setup asks of it."""

    def __init__(self, *, modern: bool = True) -> None:
        self.registered: list[tuple] = []
        if modern:

            async def async_register_static_paths(configs) -> None:
                self.registered.extend(("modern", cfg) for cfg in configs)

            self.async_register_static_paths = async_register_static_paths
        else:

            def register_static_path(url_path, path, cache_headers=True) -> None:
                self.registered.append(("legacy", (url_path, path, cache_headers)))

            self.register_static_path = register_static_path


class _StubHass:
    def __init__(self, http) -> None:
        self.http = http


def _run_async_setup(monkeypatch, http):
    """Call the integration's async_setup against a stub hass, returning the extra-JS URLs added."""
    import asyncio

    import custom_components.hagrid as hagrid

    extra_js: list[str] = []
    monkeypatch.setattr(hagrid, "add_extra_js_url", lambda hass, url, *a, **k: extra_js.append(url))
    ok = asyncio.run(hagrid.async_setup(_StubHass(http), {}))
    return ok, extra_js


def _home_assistant_static_path_config():
    """Home Assistant's own StaticPathConfig, or None on a version that predates it (<= 2024.6)."""
    from homeassistant.components import http as ha_http

    return getattr(ha_http, "StaticPathConfig", None)


def test_async_setup_registers_the_map_card_on_modern_home_assistant(monkeypatch) -> None:
    """HA 2024.7+ path: one StaticPathConfig pointing at the JS inside the integration."""
    ha_static_path_config = _home_assistant_static_path_config()
    if ha_static_path_config is None:
        pytest.skip(
            "this Home Assistant predates async_register_static_paths, so the modern branch is "
            "unreachable on it — the floor branch is covered by its own test"
        )

    http = _RecordingHTTP(modern=True)
    ok, extra_js = _run_async_setup(monkeypatch, http)

    assert ok is True
    assert len(http.registered) == 1, "exactly one static path should be registered"
    kind, cfg = http.registered[0]
    assert kind == "modern"
    assert isinstance(cfg, ha_static_path_config), (
        "the modern call must be handed Home Assistant's own StaticPathConfig, not a stand-in "
        "object that merely has the same attributes"
    )
    assert cfg.url_path == "/hagrid/hagrid-map.js"
    assert cfg.path == str(INTEGRATION / "www" / "hagrid-map.js")
    assert pathlib.Path(cfg.path).is_file(), "the registered path must exist on disk"
    assert cfg.cache_headers is False, "the card must not be cached across an integration update"
    assert extra_js == ["/hagrid/hagrid-map.js"], (
        "the JS URL must be added to the frontend, or the file is served but never loaded"
    )


def test_async_setup_falls_back_to_register_static_path_on_the_declared_floor(monkeypatch) -> None:
    """HA 2024.1 path: no async_register_static_paths, so the older call must be used instead."""
    http = _RecordingHTTP(modern=False)
    ok, extra_js = _run_async_setup(monkeypatch, http)

    assert ok is True
    assert http.registered == [
        ("legacy", ("/hagrid/hagrid-map.js", str(INTEGRATION / "www" / "hagrid-map.js"), False))
    ]
    assert extra_js == ["/hagrid/hagrid-map.js"]


def test_async_setup_survives_a_missing_card_file(monkeypatch) -> None:
    """A missing JS file must not stop the integration loading — the sensors are the primary feature."""
    import custom_components.hagrid as hagrid

    monkeypatch.setattr(hagrid, "_MAP_CARD_PATH", REPO / "does-not-exist.js")
    # Whichever static-path API this Home Assistant actually has, so the test runs on the floor too.
    http = _RecordingHTTP(modern=_home_assistant_static_path_config() is not None)
    ok, extra_js = _run_async_setup(monkeypatch, http)

    assert ok is True
    assert http.registered == []
    assert extra_js == []


def test_the_shipped_card_defines_the_element_the_readme_tells_users_to_use() -> None:
    """The card type in the README must exist in the JS we serve, or the docs are a dead end."""
    readme = (REPO / "README.md").read_text()
    js = (INTEGRATION / "www" / "hagrid-map.js").read_text()

    assert "type: custom:hagrid-map-card" in readme
    assert 'customElements.define("hagrid-map-card"' in js
# Home Assistant does not encrypt config entry data. `config/.storage/core.config_entries` is plain
# JSON — `homeassistant/helpers/storage.py` writes it with `json_util` and no cipher — and the setup
# screen used to tell users the opposite, that their keys were protected by encryption. A security
# claim someone could act on is a bug, so the correction is gated here: the claim is forbidden
# anywhere in the repository, and the truth (where the key is, what protects it) is required.
#
# FALSE_STORAGE_CLAIMS is assembled from fragments on purpose: written out in full, the literals would
# be found in this file by its own scan, which is exactly what happened the first time it was run.
# ---------------------------------------------------------------------------------------------------

# Split so the guard does not match its own source.
FALSE_STORAGE_CLAIMS = ("encrypted " + "storage", "stored " + "securely")
TEXT_SUFFIXES = {".py", ".json", ".md", ".js", ".txt", ".yaml", ".yml"}
SKIPPED_DIRS = {".git", ".venv-ha", ".ruff_cache", ".pytest_cache", "__pycache__", "node_modules"}


def _repository_text_files() -> list[pathlib.Path]:
    return [
        path
        for path in sorted(REPO.rglob("*"))
        if path.is_file()
        and path.suffix in TEXT_SUFFIXES
        and not SKIPPED_DIRS & set(path.relative_to(REPO).parts)
    ]


def test_no_file_claims_api_keys_are_stored_encrypted() -> None:
    """Nothing in the repository may describe config entry storage as encrypted."""
    offenders = [
        f"{path.relative_to(REPO)} ({claim})"
        for path in _repository_text_files()
        for claim in FALSE_STORAGE_CLAIMS
        if claim in path.read_text(encoding="utf-8", errors="replace").lower()
    ]
    assert offenders == [], (
        "Home Assistant writes config entry data as plain text to config/.storage/core.config_entries "
        "and never encrypts it, so these claims are false — the key is protected by nothing but the "
        "file permissions on .storage: " + "; ".join(offenders)
    )


def test_the_install_screen_says_where_a_key_is_kept() -> None:
    """Correcting the claim must not leave the screen vague: it has to name the real location."""
    for name in ("strings.json", "translations/en.json"):
        text = (INTEGRATION / name).read_text(encoding="utf-8")
        assert ".storage/core.config_entries" in text, f"{name} does not say where a key is kept"
        assert "plain text" in text, f"{name} does not say the key is stored as plain text"


def test_readme_says_where_a_key_is_kept_and_what_protects_it() -> None:
    flat = " ".join((REPO / "README.md").read_text(encoding="utf-8").split())
    assert ".storage/core.config_entries" in flat, "the README must name the file the key lands in"
    assert "does not encrypt that file" in flat, "the README must say the file is not encrypted"
    assert "file permissions" in flat, "the README must say what actually protects the key"
