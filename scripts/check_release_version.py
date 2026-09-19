#!/usr/bin/env python3
"""Refuse to publish a release whose tag disagrees with the integration's version.

HACS installs from releases, so a tag that disagrees with
custom_components/hagrid/manifest.json means HACS hands out a version number that does not match the
code in the release. That is the same class of mistake as the 1.0.0 nested-layout bug: invisible
until somebody tries to install it.

    python scripts/check_release_version.py v1.1.0        # tag on the command line
    GITHUB_REF_NAME=v1.1.0 python scripts/check_release_version.py
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys

MANIFEST = pathlib.Path("custom_components/hagrid/manifest.json")


def manifest_version(manifest: pathlib.Path = MANIFEST) -> str:
    """Version declared in the integration manifest."""
    return json.loads(manifest.read_text(encoding="utf-8"))["version"]


def check(tag: str, manifest: pathlib.Path = MANIFEST) -> str | None:
    """Return an error message if the tag is not 'v' + the manifest version, else None."""
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        return f"tag {tag!r} is not of the form vX.Y.Z"
    version = manifest_version(manifest)
    if tag != f"v{version}":
        return f"tag {tag!r} does not match manifest.json version {version!r} (expected 'v{version}')"
    return None


def main(argv: list[str]) -> int:
    """Exit non-zero when the tag and the manifest disagree."""
    tag = argv[1] if len(argv) > 1 else os.environ.get("GITHUB_REF_NAME", "")
    if not tag:
        print("usage: check_release_version.py vX.Y.Z", file=sys.stderr)
        return 2
    error = check(tag)
    if error:
        print(f"refusing to release: {error}", file=sys.stderr)
        return 1
    print(f"{tag} matches manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
