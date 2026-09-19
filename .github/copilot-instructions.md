# Copilot instructions for HAGrid

Rules for an agent working in this repository.

## What this is

HAGrid is a Home Assistant custom integration, distributed through HACS, that brings GB electricity
grid data into Home Assistant: live carbon intensity and the 48-hour forecast, the generation mix,
live and planned DNO power cuts, and a Lovelace map card of substations, 33kV and HV overhead lines
and embedded generation.

| | |
|---|---|
| Layout | `custom_components/hagrid/` at the repository **root** |
| Domain | `hagrid`, matching the folder name and `manifest.json` |
| Data sources | Carbon Intensity API (NESO) and UKPN Open Data. Both free, both keyless |
| Tests | `python -m pytest -q tests/` |
| Lint | `ruff check .` (rule set pinned in `pyproject.toml`) |

## Rules that exist because they were broken once

1. **Never nest the integration.** `custom_components/` sits at the repository root, the folder is
   named exactly `hagrid`, and `manifest.json` declares `"domain": "hagrid"`. HAGrid was once two
   levels down inside another repository, so HACS could never see it, and a user filed a bug about it.
2. **Both shipped bugs were import-time failures.** A dataclass field-order error meant no module
   imported, and Home Assistant reported it as `Config flow could not be loaded: {"message":"Invalid
   handler specified"}`, which reads like a folder-name problem and is not one. If you meet that
   message, check the import first.
3. **Only claim what has been measured.** The GB path is verified against real APIs. The other DNOs
   (SSEN, ENWL, Northern Powergrid, SP Energy, National Grid) are stubs with no API behind them, and
   the non-GB TSO clients in `api.py` have never been runnable. Do not describe them as working, in
   code, comments, README or a pull request description.
4. **Nothing has run against a live Home Assistant.** The tests import the integration against a real
   Home Assistant installation used as a library. That is not a running instance, and that difference
   is where the remaining bugs are.
5. **Never declare a release asset that no release carries**, and never put `zip_release` back into
   `hacs.json`. The old one promised a zip that was never attached, so HACS had nothing to install.
6. **Do not add a workflow you have not seen run.** Push it, watch it, read the conclusion.

## Before you call a change finished

```bash
ruff check .                    # must be clean
python -m pytest -q tests/      # must pass
```

Both run in CI and a pull request will not merge with them red. The environment in
`.github/workflows/copilot-setup-steps.yml` has Home Assistant, pytest and ruff installed and working.

## Do not

- **Do not bump `version` in `custom_components/hagrid/manifest.json` and do not create a tag.** The
  `Release` workflow publishes from a tag after checking that the tag and the manifest agree.
  Releasing is the maintainer's decision.
- **Do not touch `.github/workflows/` unless the task is about CI.**
- **Do not reformat files as a side effect of another change.** Formatting is not enforced yet.
- **Keep one pull request to one subject.** If a task tempts you into a codebase-wide sweep
  (whitespace, import order, renaming), stop and open an issue instead.
- **Do not edit a failing test to make it pass** when the failure is unrelated to your change. Report
  it instead.

## Copilot-specific points

- **Run the checks before you open a pull request.** `ruff check .` and `python -m pytest -q tests/`.
  The environment in `.github/workflows/copilot-setup-steps.yml` has both installed and working.
- **Do not bump `version` in `custom_components/hagrid/manifest.json` and do not create a tag.** A
  release is the maintainer's decision, and the `Release` workflow publishes from a tag.
- **Do not touch `.github/workflows/` unless the task is about CI**, and never add a workflow that
  has not been observed running.
- **Keep one pull request to one subject.** If a task tempts you into a codebase-wide sweep
  (whitespace, import order, renaming), stop and open an issue instead.
- **Say what you did not verify.** Additions to the GB path can be tested; the non-GB TSO clients
  cannot, because there is nothing to run them against. A pull request that adds a client for a
  foreign grid must say so in its description.
- If a test fails for a reason unrelated to your change, report it rather than editing the test.
