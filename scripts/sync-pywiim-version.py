#!/usr/bin/env python3
"""Keep the pinned pywiim version in sync across the repo.

We intentionally keep a single source of truth in:

  custom_components/wiim/pywiim-version.txt

Home Assistant still requires the requirement pin to physically exist in
`custom_components/wiim/manifest.json`, and our dev/test environment installs
runtime deps via `requirements_dev.txt`. This script prevents drift.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from packaging.version import InvalidVersion, Version


REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_VERSION_FILE = REPO_ROOT / "custom_components" / "wiim" / "pywiim-version.txt"
MANIFEST_FILE = REPO_ROOT / "custom_components" / "wiim" / "manifest.json"
REQUIREMENTS_DEV_FILE = REPO_ROOT / "requirements_dev.txt"


def _load_canonical_version() -> str:
    raw = CANONICAL_VERSION_FILE.read_text(encoding="ascii").strip()
    try:
        Version(raw)
    except InvalidVersion as err:
        raise SystemExit(f"Invalid canonical pywiim version {raw!r} in {CANONICAL_VERSION_FILE}: {err}") from err
    return raw


def _read_manifest() -> dict:
    return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))


def _write_manifest(data: dict) -> None:
    MANIFEST_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _get_manifest_pywiim_pin(data: dict) -> str | None:
    reqs = data.get("requirements", [])
    for req in reqs:
        if isinstance(req, str) and req.startswith("pywiim=="):
            return req.split("==", 1)[1]
    return None


def _set_manifest_pywiim_pin(data: dict, version: str) -> None:
    reqs = list(data.get("requirements", []))
    updated = False
    for i, req in enumerate(reqs):
        if isinstance(req, str) and req.startswith("pywiim=="):
            reqs[i] = f"pywiim=={version}"
            updated = True
            break
    if not updated:
        reqs.append(f"pywiim=={version}")
    data["requirements"] = reqs


def _get_requirements_dev_pywiim_pin(lines: list[str]) -> str | None:
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("pywiim=="):
            return stripped.split("==", 1)[1]
    return None


def _set_requirements_dev_pywiim_pin(lines: list[str], version: str) -> list[str]:
    out: list[str] = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("pywiim==") and not replaced:
            out.append(f"pywiim=={version}\n")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        # Keep it simple: append if missing.
        if out and not out[-1].endswith("\n"):
            out[-1] += "\n"
        out.append("\n# Integration runtime dependencies (matches manifest.json)\n")
        out.append(f"pywiim=={version}\n")
    return out


def check(*, write: bool) -> int:
    canonical = _load_canonical_version()

    # manifest.json
    manifest = _read_manifest()
    manifest_pin = _get_manifest_pywiim_pin(manifest)

    # requirements_dev.txt
    req_lines = REQUIREMENTS_DEV_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    req_pin = _get_requirements_dev_pywiim_pin(req_lines)

    mismatches: list[str] = []
    if manifest_pin != canonical:
        mismatches.append(f"{MANIFEST_FILE}: pywiim=={manifest_pin} (expected {canonical})")
    if req_pin != canonical:
        mismatches.append(f"{REQUIREMENTS_DEV_FILE}: pywiim=={req_pin} (expected {canonical})")

    if mismatches and not write:
        print("pywiim version pins are out of sync:")
        for m in mismatches:
            print(f" - {m}")
        print(f"\nCanonical source of truth: {CANONICAL_VERSION_FILE}")
        print("Fix with: python scripts/sync-pywiim-version.py --write")
        return 1

    if write:
        if manifest_pin != canonical:
            _set_manifest_pywiim_pin(manifest, canonical)
            _write_manifest(manifest)

        if req_pin != canonical:
            new_lines = _set_requirements_dev_pywiim_pin(req_lines, canonical)
            REQUIREMENTS_DEV_FILE.write_text("".join(new_lines), encoding="utf-8")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync pinned pywiim version across repo")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Update manifest.json and requirements_dev.txt to match the canonical version file",
    )
    args = parser.parse_args()
    return check(write=args.write)


if __name__ == "__main__":
    raise SystemExit(main())

