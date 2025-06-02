# WiiM Integration Development Guide

This guide helps you set up a development environment and catch issues **before** they reach CI/CD, saving time and preventing broken builds.

## Quick Start for New Developers

```bash
# 1. Install development dependencies
make install-dev

# 2. Run all checks (same as CI)
make check-all

# 3. During development, run quick checks
make dev-check
```

## The Problem We're Solving

Previously, developers would:

1. Make changes
2. Commit to git
3. Push to CI
4. **Find out about Python version incompatibilities or test failures**
5. Fix locally and repeat

**Now, you can catch all these issues locally before any git operations.**

## Development Workflow

### Initial Setup (One Time)

```bash
# Check Python version (requires 3.12+)
python --version

# Install all development dependencies with proper constraints
make install-dev

# This installs:
# - pytest-homeassistant-custom-component==0.13.108 (Python 3.12 compatible)
# - All testing dependencies
# - Pre-commit hooks (runs checks on every commit)
```

### Daily Development Workflow

```bash
# 1. Before starting work
make check-python  # Ensure Python version compatibility

# 2. During development - quick iteration
make dev-check      # Formats code + runs fast tests

# 3. Before committing - full validation
make check-all      # Simulates complete CI pipeline
```

### Individual Commands

```bash
# Format code automatically
make format

# Run tests quickly (no coverage)
make test-quick

# Run full test suite with coverage (same as CI)
make test

# Run linting checks
make lint

# Run pre-commit hooks manually
make pre-commit

# Check Python version compatibility
make check-python

# Clean temporary files
make clean
```

## Python Version Compatibility

### Current Status

- **CI/Local Development**: Python 3.12
- **pytest-homeassistant-custom-component**: 0.13.108 (last Python 3.12 compatible version)
- **Future**: When we upgrade to Python 3.13, we'll need to update `requirements_test.txt`

### The Version Problem We Fixed

```
❌ pytest-homeassistant-custom-component==0.13.209+ requires Python 3.13
✅ pytest-homeassistant-custom-component==0.13.108 works with Python 3.12
```

This was causing CI failures that were only discovered after pushing to git.

## Pre-commit Hooks (Automatic Quality Checks)

Pre-commit hooks run automatically on every `git commit` to catch issues early:

```bash
# Install hooks (one time)
pre-commit install

# Run hooks manually on all files
pre-commit run --all-files

# Skip hooks if needed (not recommended)
git commit --no-verify -m "Skip hooks"
```

### What Pre-commit Checks

1. **Code Formatting**: Black, isort, reorder-python-imports
2. **Linting**: Flake8 for code quality
3. **Basic Issues**: Trailing whitespace, YAML syntax, merge conflicts
4. **Python Version**: Ensures Python 3.12+ compatibility
5. **Import Testing**: Verifies critical imports work

## Understanding Test Commands

### Local Testing (Fast Iteration)

```bash
# Quick tests without coverage (fastest)
make test-quick

# Tests with coverage (slower but complete)
make test
```

### CI Simulation (Before Commit)

```bash
# Runs everything the CI pipeline runs
make check-all

# Equivalent to:
# - Python version check
# - Pre-commit hooks (formatting, linting)
# - Full test suite with coverage
# - Home Assistant validation (if available)
```

## Troubleshooting

### "pytest-homeassistant-custom-component version conflict"

```bash
# Ensure you're using the Python 3.12 compatible version
grep pytest-homeassistant-custom-component requirements_test.txt
# Should show: pytest-homeassistant-custom-component==0.13.108
```

### "ModuleNotFoundError" during tests

```bash
# Reinstall development dependencies
make install-dev

# Check Python version
make check-python
```

### "Pre-commit hook failed"

```bash
# Run pre-commit manually to see details
pre-commit run --all-files

# Fix issues automatically where possible
make format

# Run checks again
make lint
```

### Tests pass locally but fail in CI

```bash
# Ensure you're running the same checks as CI
make check-all

# Check you have the same Python version as CI
python --version  # Should be 3.12.x
```

## File Structure for Development

```
wiim/
├── Makefile                     # Development commands
├── DEVELOPMENT.md               # This file
├── .pre-commit-config.yaml      # Automatic quality checks
├── requirements_test.txt        # Test dependencies (Python 3.12 compatible)
├── .github/workflows/tests.yaml # CI configuration
└── custom_components/wiim/      # Integration code
```

## Best Practices

### Before Every Commit

```bash
make check-all
```

### During Active Development

```bash
make dev-check  # Faster iteration
```

### Before Creating PRs

```bash
make check-all
git status      # Ensure no uncommitted changes from auto-formatting
```

### When Updating Dependencies

1. Update `requirements_test.txt`
2. Run `make install-dev`
3. Run `make check-all` to ensure compatibility
4. Test that CI still passes

## Integration with IDEs

### VS Code

Add to `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"],
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true
}
```

### PyCharm

1. Set interpreter to project virtual environment
2. Enable pytest as test runner
3. Configure Black as code formatter
4. Add Makefile support plugin

## Upgrading Python Version (Future)

When Home Assistant moves to Python 3.13:

1. Update `.github/workflows/tests.yaml`: Change `DEFAULT_PYTHON: "3.13"`
2. Update `requirements_test.txt`: Use newer pytest-homeassistant-custom-component
3. Update `Makefile`: Change version check to 3.13
4. Update this documentation

## Summary

**Before this setup**: Developers found Python compatibility issues in CI after pushing
**After this setup**: All issues caught locally with `make check-all` before any git operations

The key insight is that CI failures are expensive (time, context switching), but local failures are cheap and fast to fix.
