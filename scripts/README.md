# WiiM Integration Scripts

This directory contains utility scripts for development, testing, and releasing the WiiM integration.

## Release Script

### `release.sh` - Automated Release Process

Comprehensive release script that handles the entire release workflow:

**Features:**

- ✅ Runs linting checks (ruff + flake8)
- ✅ Runs test suite
- ✅ Updates version in `manifest.json`
- ✅ Updates `CHANGELOG.md`
- ✅ Creates git commit and tag
- ✅ Pushes to GitHub with tags

**Usage:**

```bash
# Interactive mode (will prompt for version)
./scripts/release.sh

# Specify version directly
./scripts/release.sh 0.3.1

# Run from repository root
./scripts/release.sh 1.0.0
```

**Process Flow:**

1. **Linting** - Runs ruff and flake8 checks
   - Offers auto-fix if errors found
2. **Testing** - Runs full test suite
   - Must pass before continuing
3. **Versioning** - Updates manifest.json
   - Validates semantic versioning format
4. **Changelog** - Prompts to update CHANGELOG.md
   - Adds version header with date
5. **Git Operations** - Commits, tags, and pushes
   - Interactive confirmation for each step

**Requirements:**

- Python 3.13+
- ruff, flake8, pytest installed
- Git configured and authenticated

---

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

---

## Makefile Targets

Convenience targets for common operations:

```bash
# Release workflow
bash scripts/release.sh [version]  # Full release process (use this, not make release)

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

1. **Update code**

   ```bash
   # Make your changes
   git add .
   git commit -m "Your changes"
   ```

2. **Run release script**

   ```bash
   ./scripts/release.sh 0.3.1
   ```

   The release script automatically:

   - Runs linting checks
   - Runs all tests
   - Updates version in manifest.json
   - Commits changes
   - Creates git tag
   - **Pushes to GitHub** (commit + tag)

3. **Verify release**

   - Check GitHub for tag (should already be pushed)
   - Create GitHub release from the tag
   - Verify HACS can see new version

4. **Test with HACS**
   - Install in test HA instance
   - Verify functionality

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

**Preparing release:**

```bash
# Full validation
make check-all

# Create release
./scripts/release.sh X.Y.Z
```
