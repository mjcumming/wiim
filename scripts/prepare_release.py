"""Run release checks once for each clean, committed source tree."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_NAME = "wiim-release-preflight"


def git(root: Path, *args: str) -> str:
    command = ["git"]
    # Windows checkouts can report permission-only changes for every file.
    if os.name == "nt":
        command += ["-c", "core.filemode=false"]
    result = subprocess.run(
        [*command, "-C", str(root), *args],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Git command failed")
    return result.stdout.strip()


def clean_tree(root: Path) -> str:
    if git(root, "status", "--porcelain", "--untracked-files=normal"):
        raise RuntimeError(
            "The checkout has tracked or untracked changes. Commit the candidate "
            "or use a clean worktree before preparing a release."
        )
    return git(root, "rev-parse", "HEAD^{tree}")


def cache_file(tree: str) -> Path:
    cache = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    base = Path(cache) if cache else Path.home() / ".cache"
    return base / CACHE_NAME / (tree + ".ok")


def build_image(archive: Path, temp: Path, version: str | None = None) -> str:
    image_id = temp / ("image-" + (version or "default"))
    command = [
        "docker",
        "build",
        "--file",
        "scripts/release-preflight.Dockerfile",
        "--iidfile",
        str(image_id),
    ]
    if version:
        command += ["--build-arg", "PYTHON_VERSION=" + version]
    with archive.open("rb") as source:
        subprocess.run([*command, "-"], stdin=source, check=True)
    return image_id.read_text(encoding="utf-8").strip()


def run_archive(archive: Path, image: str, command: str) -> None:
    with archive.open("rb") as source:
        subprocess.run(
            ["docker", "run", "--rm", "-i", "--entrypoint", "sh", image, "-ec", command],
            stdin=source,
            check=True,
        )


def run_checks(archive: Path, temp: Path) -> None:
    # Keep these commands aligned with .github/workflows/tests.yaml.
    def tests() -> None:
        print("Building WiiM Python 3.13 test environment...", flush=True)
        image = build_image(archive, temp)
        run_archive(
            archive,
            image,
            """mkdir -p /workspace && tar -xf - -C /workspace && cd /workspace
python scripts/sync-pywiim-version.py
ruff check custom_components/wiim --line-length 120
flake8 custom_components/wiim --max-line-length=120 --extend-ignore=E203,W503
mypy --strict custom_components/wiim
pytest tests/ --cov=custom_components/wiim --cov-report=term --cov-report=xml
""",
        )

    def hassfest() -> None:
        print("Running Home Assistant hassfest...", flush=True)
        run_archive(
            archive,
            "ghcr.io/home-assistant/hassfest:latest",
            """mkdir -p /github/workspace && tar -xf - -C /github/workspace
cd /github/workspace
exec /usr/src/homeassistant/script/hassfest/docker/entrypoint.sh
""",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [executor.submit(tests), executor.submit(hassfest)]
        for result in results:
            result.result()


def prepare(root: Path, force: bool = False) -> bool:
    """Return True for a new successful run and False for a cached success."""
    tree = clean_tree(root)
    stamp = cache_file(tree)
    if not force and stamp.is_file() and stamp.read_text(encoding="utf-8") == tree + "\n":
        print(f"Release preflight already passed for tree {tree}. Use --force to rerun.")
        return False
    # A failed forced rerun must not leave an older success behind.
    stamp.unlink(missing_ok=True)
    print(f"Running release preflight for tree {tree}...", flush=True)
    with tempfile.TemporaryDirectory(prefix="wiim-release-") as directory:
        temp = Path(directory)
        archive = temp / "candidate.tar"
        # Archive the tree we checked, even if HEAD changes while tests run.
        git(root, "archive", "--format=tar", f"--output={archive}", tree)
        run_checks(archive, temp)
    if clean_tree(root) != tree:
        raise RuntimeError("The candidate changed during the checks. Run them again.")
    stamp.parent.mkdir(parents=True, exist_ok=True)
    # The complete marker must be written before it becomes visible.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=stamp.parent, delete=False) as marker:
        marker.write(tree + "\n")
        temporary_stamp = Path(marker.name)
    try:
        os.replace(temporary_stamp, stamp)
    finally:
        temporary_stamp.unlink(missing_ok=True)
    print(f"Release preflight passed for tree {tree}.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="rerun even if this tree already passed")
    args = parser.parse_args()
    try:
        prepare(ROOT, force=args.force)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Release preflight failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
