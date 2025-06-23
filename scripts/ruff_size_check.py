"""Simple file-size (LOC) enforcement for Python modules.

Usage (CI / pre-commit):
    python scripts/ruff_size_check.py custom_components/wiim 300 400

Arguments:
    path        Project directory to scan recursively for *.py files.
    warn_limit  Soft warning threshold (inclusive).
    hard_limit  Hard failure threshold (inclusive).

Exit status:
    0 – success (all files <= warn_limit)
    1 – soft warning triggered (warn_limit < LOC <= hard_limit)
    2 – hard failure (LOC > hard_limit)
"""

from __future__ import annotations

import sys
from pathlib import Path


def _scan(path: Path, warn: int, hard: int) -> int:
    max_loc = 0
    offending: list[tuple[Path, int]] = []

    for py_file in path.rglob("*.py"):
        if py_file.is_symlink():
            continue
        loc = sum(1 for _ in py_file.open("r", encoding="utf-8", errors="ignore"))
        max_loc = max(max_loc, loc)
        if loc > warn:
            offending.append((py_file, loc))

    status = 0
    for file, loc in offending:
        level = "⚠️  WARN" if loc <= hard else "❌ FAIL"
        print(f"{level}: {file} – {loc} LOC (limit {warn}/{hard})")
        if loc > hard:
            status = 2
        elif status == 0:
            status = 1  # escalate to soft warn if not already hard fail

    if status == 0:
        print(f"✅ All Python files within {warn} LOC (max {max_loc})")
    elif status == 1:
        print("⚠️  Size warnings detected – please refactor, but CI passes for now.")
    else:
        print("❌ Size check failed – refactor required.")

    return status


def main() -> None:  # pragma: no cover – simple CLI
    if len(sys.argv) < 4:
        print("Usage: python ruff_size_check.py <path> <warn_limit> <hard_limit>")
        sys.exit(1)

    target = Path(sys.argv[1]).resolve()
    warn_limit = int(sys.argv[2])
    hard_limit = int(sys.argv[3])

    if not target.exists():
        print(f"Target path does not exist: {target}")
        sys.exit(1)

    sys.exit(_scan(target, warn_limit, hard_limit))


if __name__ == "__main__":
    main()
