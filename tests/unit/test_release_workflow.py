"""Exercise the release workflow with a fake GitHub CLI."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.name == "nt", reason="The release workflow runs in a POSIX shell")


@pytest.fixture
def release_env(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """Supply fake gh and sleep commands; no release can be created."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        """#!/bin/sh
if [ "$1" = release ]; then
    [ "$2" = view ] && exit 1
    printf '%s\\n' "$@" > "$FAKE_GH_ARGS"
    exit 0
fi
if [ "$2" = list ]; then
    [ "$FAKE_CI_STATUS" = missing ] || echo 123
elif [ "$2" = view ]; then
    case "$*" in
        *.status*) echo "$FAKE_CI_STATUS" ;;
        *.conclusion*) echo "${FAKE_CI_CONCLUSION:-}" ;;
    esac
fi
"""
    )
    gh.chmod(0o755)
    git = bin_dir / "git"
    git.write_text('#!/bin/sh\nprintf "%b" "${FAKE_TAG_REFS:-}"\nexit "${FAKE_TAG_STATUS:-0}"\n')
    git.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)
    record = tmp_path / "gh-args"
    env = os.environ.copy()
    env.update(
        PATH=f"{bin_dir}{os.pathsep}{env['PATH']}",
        FAKE_GH_ARGS=str(record),
        GITHUB_SHA="reviewed-commit",
        RELEASE_NOTES="Test notes",
    )
    return env, record


def workflow_step(name: str) -> str:
    """Return a runnable workflow step with Actions expressions expanded."""
    workflow = yaml.safe_load((ROOT / ".github/workflows/auto-release.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["release"]["steps"]
    script = next(step["run"] for step in steps if step.get("name") == name)
    return (
        script.replace("${{ github.sha }}", "reviewed-commit")
        .replace("${{ github.repository }}", "mjcumming/wiim")
        .replace("${{ needs.check-version.outputs.version }}", "1.2.3")
    )


@pytest.mark.parametrize(
    ("status", "conclusion", "expected"),
    [("completed", "success", 0), ("completed", "failure", 1), ("in_progress", "", 1), ("missing", "", 1)],
)
def test_release_requires_ci_to_finish_successfully(
    release_env: tuple[dict[str, str], Path], status: str, conclusion: str, expected: int
) -> None:
    env, _ = release_env
    env.update(FAKE_CI_STATUS=status, FAKE_CI_CONCLUSION=conclusion)
    run = subprocess.run(
        ["bash", "-e", "-c", workflow_step("Wait for CI tests to complete")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == expected
    if status in {"in_progress", "missing"}:
        assert "Timeout" in run.stdout


def test_release_tag_targets_the_validated_commit(release_env: tuple[dict[str, str], Path]) -> None:
    env, record = release_env
    run = subprocess.run(
        ["bash", "-e", "-c", workflow_step("Create Release with GitHub CLI")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0
    args = record.read_text().splitlines()
    assert args[args.index("--target") + 1] == "reviewed-commit"


@pytest.mark.parametrize(
    ("tag_refs", "expected"),
    [
        ("wrong-commit\\trefs/tags/v1.2.3\\n", 1),
        ("annotated-tag\\trefs/tags/v1.2.3\\nreviewed-commit\\trefs/tags/v1.2.3^{}\\n", 0),
    ],
)
def test_existing_release_tag_must_point_to_the_validated_commit(
    release_env: tuple[dict[str, str], Path], tag_refs: str, expected: int
) -> None:
    env, record = release_env
    env["FAKE_TAG_REFS"] = tag_refs
    run = subprocess.run(
        ["bash", "-e", "-c", workflow_step("Create Release with GitHub CLI")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == expected
    assert record.exists() is (expected == 0)


def test_release_stops_if_existing_tags_cannot_be_checked(release_env: tuple[dict[str, str], Path]) -> None:
    env, record = release_env
    env["FAKE_TAG_STATUS"] = "1"
    run = subprocess.run(
        ["bash", "-e", "-c", workflow_step("Create Release with GitHub CLI")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode != 0
    assert not record.exists()
