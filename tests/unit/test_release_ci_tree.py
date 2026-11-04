"""Test release CI reuse without publishing or contacting GitHub."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.name == "nt", reason="Release scripts use a POSIX shell")


@pytest.mark.parametrize(
    ("case", "pr_head", "pr_run", "artifact", "tested_tree", "main_result", "expected", "uses_main"),
    [
        ("matching tree", True, True, True, True, "completed\tfailure", 0, False),
        ("different tree and passing main", True, True, True, False, "completed\tsuccess", 0, True),
        ("different tree and failing main", True, True, True, False, "completed\tfailure", 1, True),
        ("missing PR", False, True, True, True, "completed\tfailure", 1, True),
        ("PR not successful", True, False, True, True, "completed\tfailure", 1, True),
        ("artifact missing", True, True, False, True, "completed\tfailure", 1, True),
        ("main still running", False, True, True, True, "in_progress\t", 1, True),
        ("direct commit with passing main", False, True, True, True, "completed\tsuccess", 0, True),
        ("main already failed", True, True, True, True, "completed\tfailure", 1, True),
    ],
)
def test_release_requires_ci_for_the_exact_tree(
    tmp_path: Path,
    case: str,
    pr_head: bool,
    pr_run: bool,
    artifact: bool,
    tested_tree: bool,
    main_result: str,
    expected: int,
    uses_main: bool,
) -> None:
    """A missing or mismatched PR proof must fall back to main CI."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_LOG"
case "$1:$2" in
  api:*) printf '%s\\n' "$FAKE_PR_HEAD" ;;
  run:list)
    case " $* " in
      *' --event pull_request '*) printf '%s\\n' "$FAKE_PR_RUN" ;;
      *)
        if [ -e "$FAKE_MAIN_SEEN" ]; then
          printf '%s\\n' "$FAKE_MAIN_RESULT"
        else
          : > "$FAKE_MAIN_SEEN"
          printf '%s\\n' "$FAKE_MAIN_INITIAL"
        fi ;;
    esac ;;
  run:download)
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --name) name=$2; shift ;;
        --dir) dir=$2; shift ;;
      esac
      shift
    done
    [ "$name" = "$FAKE_ARTIFACT_NAME" ] || exit 1
    printf '%s\\n' "$FAKE_TESTED_TREE" > "$dir/tested-tree" ;;
esac
""",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    git = bin_dir / "git"
    git.write_text('#!/bin/sh\nprintf "%s\\n" "$FAKE_RELEASE_TREE"\n', encoding="utf-8")
    git.chmod(0o755)

    log = tmp_path / "gh.log"
    is_wiim = (ROOT / ".github/workflows/tests.yaml").exists()
    artifact_name = "ci-tested-tree-default-2" if is_wiim else "ci-tested-tree-3.12-2"
    env = os.environ.copy()
    env.update(
        PATH=f"{bin_dir}{os.pathsep}{env['PATH']}",
        GITHUB_REPOSITORY="owner/project",
        GITHUB_SHA="a" * 40,
        CI_WAIT_ATTEMPTS="1",
        CI_WAIT_INTERVAL="0",
        FAKE_LOG=str(log),
        FAKE_MAIN_SEEN=str(tmp_path / "main-seen"),
        FAKE_MAIN_INITIAL="completed\tfailure" if case == "main already failed" else "in_progress\t",
        FAKE_PR_HEAD="b" * 40 if pr_head else "",
        FAKE_PR_RUN="123\t2" if pr_run else "",
        FAKE_ARTIFACT_NAME=artifact_name if artifact else "missing",
        FAKE_TESTED_TREE="c" * 40 if tested_tree else "d" * 40,
        FAKE_RELEASE_TREE="c" * 40,
        FAKE_MAIN_RESULT=main_result,
    )
    run = subprocess.run(
        ["bash", str(ROOT / "scripts/wait-for-ci.sh")], env=env, capture_output=True, text=True, check=False
    )
    assert run.returncode == expected, run.stdout + run.stderr
    calls = log.read_text(encoding="utf-8")
    assert "--event push" in calls
    assert ("--event pull_request" not in calls) == (case == "main already failed" or not pr_head)
    assert (calls.count("--event push") > 1) == (uses_main and case != "main already failed")
