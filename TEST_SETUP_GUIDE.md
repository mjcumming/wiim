# WiiM Integration Local Test Environment Setup Guide

## Overview

This guide explains how to set up and run tests locally for the WiiM Home Assistant integration without needing to push to GitHub.

## Prerequisites

- Python 3.11+ (tested with Python 3.13)
- pip package manager
- Git repository cloned locally

## Installation Steps

### 1. Install Test Dependencies

```bash
# Navigate to the WiiM integration directory
cd /path/to/wiim

# Install all test dependencies
pip install -r requirements_test.txt
```

### 2. Verify Installation

```bash
# Check that pytest and key dependencies are installed
python -m pytest --version
python -c "import pytest_homeassistant_custom_component; print('HA test plugin installed')"
```

## Test Structure

The test suite is organized as follows:

```
tests/
├── conftest.py              # Global test fixtures
├── conftest_wiim.py         # WiiM-specific fixtures
├── const.py                 # Test constants and mock data
├── unit/                    # Unit tests
│   ├── test_media_player.py
│   ├── test_coordinator.py
│   └── ...
└── integration/             # Integration tests
    └── ...
```

## Running Tests

### Basic Test Commands

```bash
# Run all tests
python -m pytest

# Run only unit tests
python -m pytest tests/unit/

# Run specific test file
python -m pytest tests/unit/test_media_player.py

# Run specific test class
python -m pytest tests/unit/test_media_player.py::TestMediaPlayerControls

# Run specific test method
python -m pytest tests/unit/test_media_player.py::TestMediaPlayerControls::test_async_media_play

# Run with verbose output
python -m pytest -v

# Run with short traceback
python -m pytest --tb=short

# Stop on first failure
python -m pytest -x
```

### Test Coverage

```bash
# Run tests with coverage report
python -m pytest --cov=custom_components.wiim --cov-report=term-missing

# Generate HTML coverage report
python -m pytest --cov=custom_components.wiim --cov-report=html
```

### Linting and Code Quality

```bash
# Run ruff linter
python -m ruff check custom_components/wiim/

# Run flake8
python -m flake8 custom_components/wiim/

# Auto-fix ruff issues
python -m ruff check custom_components/wiim/ --fix
```

## Test Fixtures

The test environment uses several key fixtures:

### Core Fixtures (conftest.py)

- `hass`: Home Assistant instance
- `enable_custom_integrations`: Enables custom integrations
- `skip_notifications`: Skips notification calls

### WiiM-Specific Fixtures (conftest_wiim.py)

- `mock_wiim_client`: Mocked WiiM API client
- `mock_coordinator`: Mocked WiiM coordinator
- `wiim_speaker`: Mocked speaker entity
- `bypass_get_data`: Bypasses API calls

## Common Test Patterns

### Mocking Controller Methods

```python
@pytest.mark.asyncio
async def test_async_media_play(self, media_player):
    """Test play command."""
    # Mock the controller methods that are called
    media_player.controller = AsyncMock()
    media_player.controller.play = AsyncMock()

    # Mock required attributes
    media_player._optimistic_state = None
    media_player._optimistic_state_timestamp = None
    media_player.async_write_ha_state = MagicMock()

    await media_player.async_media_play()
    media_player.controller.play.assert_called_once()
```

### Testing with Speaker Fixtures

```python
def test_media_player_creation(self, media_player, wiim_speaker):
    """Test media player entity creation."""
    assert media_player.speaker is wiim_speaker
    assert media_player.unique_id == "test-speaker-uuid"
```

## Troubleshooting

### Import Errors

If you see import errors for `custom_components.wiim.*`, this is expected when not running in a full Home Assistant environment. The tests use stubs to mock Home Assistant components.

### Coroutine Errors

If you encounter "object of type 'coroutine' has no len()" errors:

1. Check if any async methods are being called without await
2. Ensure all AsyncMock objects are properly awaited in tests
3. Verify that media_player_browser.py handles coroutines correctly

### Test Environment Issues

```bash
# Clean up any cached files
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +

# Reinstall dependencies
pip install -r requirements_test.txt --force-reinstall
```

## Current Test Status

As of the latest update:

### ✅ Working Tests

- Basic media player entity creation
- Supported features validation
- State property delegation
- Volume level property delegation
- Group members property delegation

### ⚠️ Known Issues

- Some tests may fail due to coroutine handling in media_player_browser.py
- Import warnings for custom_components are expected in test environment
- Some integration tests require full Home Assistant environment

### 🔧 Recent Fixes

- Fixed test mocking for controller methods
- Added required attribute mocks for optimistic state updates
- Updated test assertions to match new controller-based architecture

## Advanced Testing

### Running Tests in Parallel

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (4 workers)
python -m pytest -n 4
```

### Debugging Tests

```bash
# Run with debug output
python -m pytest -v -s --tb=long

# Use pdb for debugging
python -m pytest --pdb
```

### Performance Testing

```bash
# Install pytest-benchmark
pip install pytest-benchmark

# Run performance tests
python -m pytest --benchmark-only
```

## Continuous Integration

The test suite is designed to work with GitHub Actions. Local testing should match CI behavior:

```bash
# Run the same commands as CI
python -m ruff check custom_components/wiim/
python -m pytest tests/unit/ --cov=custom_components.wiim --cov-fail-under=10
```

## Contributing

When adding new tests:

1. Follow the existing patterns for mocking and fixtures
2. Use descriptive test names and docstrings
3. Ensure tests are isolated and don't depend on external state
4. Add appropriate coverage for new functionality
5. Update this guide if adding new test patterns or requirements

## Support

For issues with the test environment:

1. Check the troubleshooting section above
2. Review the test logs for specific error messages
3. Ensure all dependencies are properly installed
4. Verify Python version compatibility
