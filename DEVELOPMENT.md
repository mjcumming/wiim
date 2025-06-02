# WiiM Integration Development Guide

This guide helps you set up a development environment and catch issues **before** they reach CI/CD, saving time and preventing broken builds.

## Quick Start for New Developers

```bash
# 1. Verify you have the correct Python version
make check-python

# 2. Install development dependencies with HA compatibility validation
make install-dev

# 3. Run all checks (same as CI)
make check-all

# 4. During development, run quick checks
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

## Home Assistant Version Requirements

**Critical:** This integration must stay compatible with Home Assistant Core requirements:

- **Python 3.13+** (as of HA 2024.12)
- **Python 3.12 deprecated** (will be removed in HA 2025.2)
- Dependencies must match HA Core versions to avoid conflicts

### Why This Matters

Home Assistant 2024.12+ requires Python 3.13. Using the wrong Python version or incompatible dependencies will cause:

- CI failures
- Integration not loading in newer HA versions
- Dependency conflicts in user installations

## Development Workflow

### Initial Setup (One Time)

```bash
# Check Python version (must be 3.13+)
make check-python

# Install development environment with HA compatibility validation
make install-dev

# (Optional) Set up pre-commit hooks
pre-commit install
```

### During Development

```bash
# Make your changes...

# Quick check during development (fast)
make dev-check

# Full check before commit (same as CI)
make check-all

# If everything passes, commit your changes
git add .
git commit -m "Your changes"
```

### Understanding the Commands

#### `make check-python`

- Validates you're using Python 3.13+ (required for HA 2024.12+)
- Prevents wasting time with wrong Python version

#### `make check-ha-compat`

- Verifies Home Assistant test dependencies can be installed
- Catches Python version mismatches early

#### `make install-dev`

- Installs dependencies with version constraints that match HA Core
- Uses `.github/workflows/constraints.txt` for exact version pinning
- Validates HA compatibility before installation

#### `make dev-check` (Fast, for active development)

- Python version check
- Code linting
- Quick tests without coverage
- ~30 seconds

#### `make check-all` (Complete, before git commit)

- Python version validation
- HA compatibility check
- Full linting
- Complete test suite with coverage
- Same as CI pipeline
- ~2-3 minutes

## Dependabot Management

### The Dependabot Problem

Dependabot automatically creates PRs to update packages, but it doesn't understand Home Assistant's specific requirements. This can cause:

- Updates to packages that require newer Python versions
- Breaking changes that aren't compatible with HA Core
- Version conflicts with HA's dependency constraints

### Our Solution

1. **Version Constraints**: We use `.github/workflows/constraints.txt` to pin exact versions that work with HA Core
2. **Local Validation**: Our Makefile validates compatibility before installation
3. **CI Protection**: Our GitHub Actions workflow will catch incompatible updates

### Handling Dependabot PRs

**Before merging any dependabot PR:**

```bash
# Pull the PR branch
git checkout dependabot-branch

# Run compatibility checks
make check-all

# If it passes, it's safe to merge
# If it fails, we need to investigate the dependency conflict
```

## Python Version Management

### Current Status

- **Required**: Python 3.13+
- **Reason**: Home Assistant 2024.12+ requires Python 3.13
- **Timeline**: Python 3.12 support was deprecated in HA 2024.12 and will be removed in 2025.2

### When HA Updates Python Requirements

When Home Assistant updates their Python requirements:

1. Update the Python version in:

   - `.github/workflows/tests.yaml` (`DEFAULT_PYTHON` and `matrix.python-version`)
   - `Makefile` (`check-python` function)
   - This documentation

2. Update test dependencies:

   - `requirements_test.txt`
   - `.github/workflows/constraints.txt`

3. Test the changes:
   ```bash
   make clean
   make install-dev
   make check-all
   ```

## Troubleshooting Common Issues

### "Python 3.13+ required"

**Problem**: You're using an older Python version
**Solution**: Install Python 3.13+ or use pyenv/virtualenv with the correct version

### "Cannot install HA test dependencies"

**Problem**: Dependency version conflicts
**Solution**: Check if pytest-homeassistant-custom-component version is compatible with your Python version

### "CI passes locally but fails on GitHub"

**Problem**: Environment differences
**Solution**: Our constraints file should prevent this, but if it happens:

1. Check the CI logs for specific errors
2. Update constraints.txt with the working versions
3. Test locally with `make check-all`

## Development Tools and Integration

### VS Code Integration

Add to `.vscode/tasks.json`:

```json
{
  "tasks": [
    {
      "label": "WiiM: Quick Check",
      "type": "shell",
      "command": "make dev-check",
      "group": "build"
    },
    {
      "label": "WiiM: Full Check",
      "type": "shell",
      "command": "make check-all",
      "group": "test"
    }
  ]
}
```

### Pre-commit Integration

```bash
# Install pre-commit hooks (optional but recommended)
pre-commit install

# Pre-commit will now run automatically on each commit
```

## Best Practices

1. **Always run `make check-python` first** - saves time
2. **Use `make dev-check` during active development** - faster feedback
3. **Run `make check-all` before committing** - prevents CI failures
4. **Keep dependencies aligned with HA Core** - prevents user issues
5. **Test with the exact Python version HA uses** - ensures compatibility

This workflow ensures your changes are compatible with Home Assistant's requirements before they ever reach the CI pipeline, saving time and preventing integration issues for users.
