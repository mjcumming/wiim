# AGENTS.md

## Cursor Cloud specific instructions

This is a WiiM Home Assistant custom integration (`custom_components/wiim/`). It uses the `pywiim` library as the sole interface to WiiM audio devices.

### Environment

- **Python 3.13** is required (CI, mypy, and Makefile all enforce `>= 3.13`). Installed via `deadsnakes` PPA on Ubuntu.
- **System dependency**: `libturbojpeg` (needed by Home Assistant test harness).
- **Virtual environment**: `/workspace/.venv` (Python 3.13). Always activate before running any commands: `source /workspace/.venv/bin/activate`.
- No Docker, Node.js, or external services are required for unit testing or linting.

### Key commands

All commands require the venv to be activated first.

| Task | Command |
|---|---|
| Full CI simulation | `bash scripts/check-before-push.sh` |
| Lint (ruff) | `ruff check custom_components/wiim --line-length 120` |
| Lint (flake8) | `flake8 custom_components/wiim --max-line-length=120 --extend-ignore=E203,W503` |
| Type check (mypy) | `mypy --strict custom_components/wiim` |
| Tests with coverage | `pytest tests/ --cov=custom_components/wiim --cov-report=term-missing --cov-report=xml:build/coverage.xml -q` |
| Quick tests (no cov) | `pytest tests/unit/ -v` |
| Build | `make build` |
| Format | `make format` |

See the `Makefile` and `scripts/check-before-push.sh` for the full set of development targets.

### Gotchas

- The `build/` directory must exist before running pytest with coverage XML output. Create it with `mkdir -p build` if missing.
- The `RequestsDependencyWarning` about urllib3/chardet versions in test output is harmless and expected — it comes from pinned HA dependency versions.
- Real-world / smoke tests (`scripts/test-automated.py`, `scripts/test-smoke.py`) require a running Home Assistant instance with WiiM devices configured and are not part of standard CI.
- The `pytest.ini` `addopts` already includes `--cov` flags, so running `pytest tests/` alone will produce coverage output (ensure `build/` dir exists).
