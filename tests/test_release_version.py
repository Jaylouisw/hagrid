"""The release-version gate is the thing standing between a bad tag and a HACS install."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_release_version", ROOT / "scripts" / "check_release_version.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_version_is_what_the_tag_will_carry():
    version = _load().manifest_version(ROOT / "custom_components" / "hagrid" / "manifest.json")
    assert isinstance(version, str) and version


def test_matching_tag_passes(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": "9.9.9"}), encoding="utf-8")
    assert _load().check("v9.9.9", manifest) is None


def test_mismatched_tag_is_refused(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
    error = _load().check("v1.1.1", manifest)
    assert error is not None and "does not match" in error


def test_malformed_tag_is_refused(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
    assert _load().check("1.1.0", manifest) is not None
    assert _load().check("v1.1", manifest) is not None
