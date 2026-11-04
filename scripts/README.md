# WiiM Integration Scripts

This directory contains utility scripts for development, testing, and releasing the WiiM integration.

## Releases

Prepare the version and changelog in a PR. GitHub Actions creates the release
after the reviewed change reaches main and CI passes; see the
[release checklist](#release-checklist). The old local release script is
retired and does not stage, commit, tag, or push files.

---

## Testing Scripts

### `test-complete-suite.py` - Comprehensive Device Testing

Complete integration test suite for real WiiM devices.

**Usage:**

```bash
export HA_TOKEN="your_long_lived_access_token"
python scripts/test-complete-suite.py http://localhost:8123
```

**Tests:**

- Volume control, mute, TTS
- Device information retrieval
- Multiroom grouping
- EQ/shuffle/repeat (requires active playback)

### `test-real-devices.py` - Basic Device Tests

Quick 5-test validation of core functionality.

**Usage:**

```bash
export HA_TOKEN="your_token"
python scripts/test-real-devices.py http://localhost:8123
```

### `test-advanced-features.py` - Advanced Feature Tests

Extended test suite for advanced features including EQ, shuffle/repeat, presets, audio output, URL playback, sleep timer, and alarms.

**Usage:**

```bash
export HA_TOKEN="your_token"
python scripts/test-advanced-features.py http://localhost:8123
```

**Tests:**

- EQ control (preset selection)
- Shuffle and repeat modes
- Preset playback
- URL/stream playback
- Audio output mode selection
- **Sleep timer** (set and clear) - WiiM devices only
- **Alarm management** (create, update, multiple slots) - WiiM devices only
- Multiroom grouping (if multiple devices available)
- TTS announcements

---

## Development Scripts

### `pre_commit_check.sh` - Pre-Commit Validation

Runs before git commits to ensure code quality.

**Checks:**

- Syntax validation
- Import verification
- Linting (ruff/flake8)
- Quick test run

**Usage:**

```bash
./scripts/pre_commit_check.sh
```

### `pre_run_check.sh` - Pre-Run Validation

Quick checks before starting Home Assistant.

**Checks:**

- Python syntax
- Import errors
- Basic linting

**Usage:**

```bash
make pre-run
# or directly:
./scripts/pre_run_check.sh
```

### `setup.sh` - Development Environment Setup

Sets up development environment with all dependencies.

**Usage:**

```bash
./scripts/setup.sh
```

### `develop` - Run Home Assistant Locally

Starts Home Assistant with `./config/` and a live symlink to `custom_components/wiim` (no HA core checkout required).

**Usage:**

```bash
./scripts/develop
```

Run `./scripts/setup.sh` first if dependencies or `config/` are missing. The dev container runs `setup.sh` on create.

---

## Makefile Targets

Convenience targets for common operations:

```bash
# Releases
# Merge a reviewed manifest version and changelog to main; Actions publishes it.

# Development
make pre-run          # Quick checks before running HA
make pre-commit       # Pre-commit validation
make dev-check        # Development checks (lint + quick test)

# Testing
make test             # Full test suite with coverage
make test-quick       # Quick test without coverage

# Code quality
make lint             # Run all linting checks
make format           # Auto-format code
make check-all        # Run all quality checks

# Build
make clean            # Clean build artifacts
make build            # Build integration package
```

---

## Release Checklist

1. Prepare a manifest version and changelog entry in the change's PR.
2. Review the PR, pass CI, and merge it to main. The auto-release workflow
   validates HACS, waits for main-commit CI, and creates the tag and release.
3. Verify the workflow and release. Test installation or device behavior when
   relevant and available, and report what was actually tested.

See [CONTRIBUTING.md](../CONTRIBUTING.md) and the
[cross-repository release rules](../docs/DEVELOPMENT-RULES.md#rule-2c-cross-repository-pywiim-work-agents--automation).

---

## Troubleshooting

**Linting fails:**

```bash
# Auto-fix most issues
python -m ruff check custom_components/wiim/ --fix
python -m ruff format custom_components/wiim/

# Check remaining issues
make lint
```

**Tests fail:**

```bash
# Run verbose to see details
pytest tests/ -v

# Run specific test
pytest tests/unit/test_config_flow.py -v
```

**Import errors:**

```bash
# Verify pywiim is installed
pip install pywiim>=1.0.57

# Check Python version
python --version  # Should be 3.13+
```

---

## Development Workflow

**Daily development:**

```bash
# Before starting work
make pre-run

# During development
make dev-check  # Quick validation

# Before committing
./scripts/pre_commit_check.sh
```

**Preparing a release:** Update the manifest version and changelog in the PR,
then review the Actions result and published release after merge.
