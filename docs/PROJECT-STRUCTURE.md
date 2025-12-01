# Project Structure Guide

## Overview

This document defines the standard structure and organization for the WiiM Home Assistant integration.

## Directory Structure

```
wiim/
├── custom_components/wiim/    # Integration code (ONLY place to modify)
│   ├── __init__.py           # Setup entry point
│   ├── config_flow.py         # Config & options flow
│   ├── coordinator.py         # pywiim wrapper
│   ├── data.py                # Speaker wrapper
│   ├── entity.py              # Base entity
│   ├── media_player.py        # Media player entity
│   ├── group_media_player.py  # Group coordinator entity
│   ├── sensor.py              # Sensor entities
│   ├── switch.py              # Switch entities
│   ├── select.py              # Select entities
│   ├── number.py              # Number entities
│   ├── button.py              # Button entities
│   ├── light.py               # Light entity (LED)
│   ├── binary_sensor.py       # Binary sensor entities
│   ├── services.py            # Custom services
│   ├── diagnostics.py         # Diagnostics
│   ├── system_health.py       # System health
│   ├── const.py               # Constants
│   ├── models.py              # Data models
│   ├── manifest.json          # Integration manifest
│   ├── strings.json           # Translation strings
│   ├── services.yaml          # Service definitions
│   └── translations/          # Translation files
│
├── tests/                      # Automated tests (pytest)
│   ├── unit/                   # Unit tests (fast, isolated, mocked)
│   │   ├── test_media_player.py
│   │   ├── test_config_flow.py
│   │   ├── test_diagnostics.py
│   │   └── ...

│   ├── conftest.py             # All pytest fixtures (consolidated)
│   ├── const.py                # Test constants
│   ├── run_tests.py            # Test runner
│   └── README.md               # Test documentation
│
├── scripts/                    # Manual validation tests
│   ├── test-complete-suite.py  # Full E2E test suite
│   ├── test-real-devices.py    # Basic device tests
│   ├── test-advanced-features.py # Advanced features
│   ├── test-timers-*.py        # Timer-specific tests
│   ├── test.config             # Saved HA token/config
│   ├── load-test-env.sh       # Load test environment
│   ├── pre_run_check.sh        # Pre-run validation
│   ├── pre_commit_check.sh    # Pre-commit validation
│   └── README.md               # Scripts documentation
│
├── docs/                       # Documentation
│   ├── INDEX.md                # Documentation index
│   ├── ARCHITECTURE.md         # Architecture guide
│   ├── DEVELOPMENT-RULES.md   # Development rules
│   ├── TESTING-CONSOLIDATED.md # Testing strategy
│   ├── PROJECT-STRUCTURE.md    # This file
│   ├── user-guide.md           # User guide
│   ├── faq-and-troubleshooting.md # FAQ
│   └── ...
│
├── development/                # Developer guides
│   └── README.md               # Development quick start
│
├── .github/                    # GitHub configuration
│   ├── copilot-instructions.md # AI assistant rules
│   └── workflows/              # CI/CD workflows
│
├── stubs/                      # Test stubs (for unit tests)
├── images/                     # Images and logos
├── CHANGELOG.md                # Version changelog
├── CONTRIBUTING.md             # Contribution guide
├── README.md                   # Project README
├── LICENSE                     # License file
├── Makefile                    # Build and test commands
├── pytest.ini                  # Pytest configuration
└── pyproject.toml              # Project configuration
```

## Component Responsibilities

### Core Components

#### `custom_components/wiim/__init__.py`

- Integration setup
- Config entry lifecycle
- Platform registration
- Coordinator creation

#### `custom_components/wiim/coordinator.py`

- Thin wrapper around pywiim Player
- DataUpdateCoordinator implementation
- Polling interval management

#### `custom_components/wiim/data.py`

- Speaker wrapper class
- Links config entry to coordinator
- Device info management

#### `custom_components/wiim/entity.py`

- Base entity class
- Common functionality
- Device info

### Platform Components

Each platform file follows the same pattern:

1. **Read from pywiim**: `coordinator.data["player"]`
2. **Call pywiim**: `coordinator.player.method()`
3. **Handle errors**: Catch WiiMError, raise HomeAssistantError

### Test Components

#### `tests/unit/`

- Fast, isolated unit tests
- Use mocks and fixtures
- Test individual components
- Run on every commit

#### `scripts/`

- Manual validation tests
- Real devices required
- Real Home Assistant instance
- Run before major releases

## File Naming Rules

### Code Files

- ✅ **DO**: Use lowercase with underscores: `media_player.py`
- ✅ **DO**: Match class name: `WiiMMediaPlayer` → `media_player.py`
- ❌ **DON'T**: Use hyphens: `media-player.py` (Python doesn't allow)
- ❌ **DON'T**: Use camelCase: `MediaPlayer.py`

### Test Files

- ✅ **DO**: Match source file: `test_media_player.py` for `media_player.py`
- ✅ **DO**: Use `test_` prefix: `test_config_flow.py`
- ✅ **DO**: Group by component: `test_media_player.py`, `test_sensor.py`

### Documentation Files

- ✅ **DO**: Use hyphens: `testing-strategy.md`
- ✅ **DO**: Use YYYY.MM.DD format for dated docs: `2025.11.28-architecture.md`
- ❌ **DON'T**: Use underscores: `testing_strategy.md`

### Script Files

- ✅ **DO**: Use hyphens: `test-complete-suite.py`
- ✅ **DO**: Use descriptive names: `pre-commit-check.sh`
- ❌ **DON'T**: Use underscores: `test_complete_suite.py`

## Code Organization

### Import Order

1. **Standard library**
2. **Third-party** (homeassistant, pywiim)
3. **Local** (custom_components.wiim)

### Class Organization

1. **Imports**
2. **Constants**
3. **Helper functions**
4. **Main class**
   - `__init__`
   - Properties
   - Methods (grouped by functionality)

### Method Organization

Within a class, organize methods by:

1. **Initialization** (`__init__`)
2. **Properties** (read-only)
3. **State methods** (read state)
4. **Control methods** (change state)
5. **Helper methods** (private)

## Testing Structure

### Unit Tests

```
tests/unit/
├── test_media_player.py      # Media player tests
├── test_config_flow.py       # Config flow tests
├── test_diagnostics.py       # Diagnostics tests
└── ...
```

**Pattern**: One test file per scenario/workflow

### Test Fixtures

- **`conftest.py`**: Shared fixtures (HA, mocks)
- **`conftest_wiim.py`**: WiiM-specific fixtures (player, speaker)

## Documentation Structure

### Developer Docs

- **`ARCHITECTURE.md`**: Complete architecture
- **`DEVELOPMENT-RULES.md`**: Development rules
- **`TESTING-CONSOLIDATED.md`**: Testing strategy
- **`PROJECT-STRUCTURE.md`**: This file

### User Docs

- **`user-guide.md`**: User guide
- **`faq-and-troubleshooting.md`**: FAQ
- **`automation-cookbook.md`**: Automation examples

## Rules Summary

### DO

- ✅ Keep code in `custom_components/wiim/`
- ✅ Follow file naming conventions
- ✅ Organize code logically
- ✅ Write tests for bug fixes
- ✅ Document architecture decisions

### DON'T

- ❌ Modify `homeassistant/` core
- ❌ Import private HA internals
- ❌ Create files outside allowed directories
- ❌ Skip tests for bug fixes
- ❌ Work around pywiim issues

## Maintenance

### When Adding New Files

1. Check if similar file exists
2. Follow naming conventions
3. Add to appropriate directory
4. Update this document if structure changes

### When Refactoring

1. Update file structure
2. Update this document
3. Update tests
4. Update documentation

## References

- [Architecture Guide](ARCHITECTURE.md)
- [Development Rules](DEVELOPMENT-RULES.md)
- [Testing Strategy](TESTING-CONSOLIDATED.md)
