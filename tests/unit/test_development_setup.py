"""Verify setup does not overwrite an existing Home Assistant configuration."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.name == "nt", reason="The setup script runs in a POSIX shell")


@pytest.fixture
def setup_project(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    project = tmp_path / "project"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "setup.sh").write_text((ROOT / "scripts/setup.sh").read_text(encoding="utf-8"), encoding="utf-8")
    (project / "custom_components/wiim").mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, status in (("pip", 0), ("pre-commit", 1)):
        tool = bin_dir / name
        tool.write_text(f"#!/bin/sh\nexit {status}\n", encoding="utf-8")
        tool.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    return project, env


def test_setup_creates_missing_config_without_installing_hooks(setup_project: tuple[Path, dict[str, str]]) -> None:
    project, env = setup_project
    subprocess.run(["bash", "scripts/setup.sh"], cwd=project, env=env, capture_output=True, text=True, check=True)
    assert (project / "config/custom_components/wiim").resolve() == project / "custom_components/wiim"
    assert "default_config:" in (project / "config/configuration.yaml").read_text(encoding="utf-8")


def test_setup_preserves_existing_config(setup_project: tuple[Path, dict[str, str]]) -> None:
    project, env = setup_project
    integration = project / "config/custom_components/wiim"
    integration.mkdir(parents=True)
    (integration / "sentinel").write_text("keep", encoding="utf-8")
    config = project / "config/configuration.yaml"
    config.write_text("existing: true\n", encoding="utf-8")
    subprocess.run(["bash", "scripts/setup.sh"], cwd=project, env=env, capture_output=True, text=True, check=True)
    assert (integration / "sentinel").read_text(encoding="utf-8") == "keep"
    assert config.read_text(encoding="utf-8") == "existing: true\n"
