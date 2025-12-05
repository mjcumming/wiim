# Testing Guidelines

This document provides comprehensive testing guidelines for the WiiM Home Assistant integration.

## 4-Tier Testing Strategy

The integration uses a 4-tier testing approach to catch issues at different levels:

### Tier 1: Unit Tests (Fast, Mocked)

**Location**: `tests/unit/`

**Purpose**: Catch logic errors, regressions, basic functionality

**Characteristics**:
- ✅ Fast (runs in seconds)
- ✅ Uses mocks/fixtures
- ✅ No real devices needed
- ✅ Can run in CI/CD
- ✅ Catches bugs before release
- ✅ Regression tests for fixed bugs

**When to use**:
- Before every commit
- In CI/CD pipelines
- When fixing bugs (write test first!)
- Pre-release validation

**Run with**:
```bash
make test              # All unit tests
pytest tests/unit/     # Unit tests only
make test-quick        # Fast (no coverage)
```

### Tier 2: Integration Tests (pywiim Integration Layer)

**Location**: `tests/integration/`

**Purpose**: Test pywiim → HA integration layer

**Characteristics**:
- ✅ Uses real pywiim Player objects (mocked HTTP)
- ✅ Validates integration patterns
- ✅ Tests callback flows
- ✅ Tests coordinator refresh patterns
- ✅ Fast (runs in seconds)

**When to use**:
- Before every PR
- When changing coordinator/entity patterns
- Pre-release validation

**Run with**:
```bash
make test-integration  # Integration tests
pytest tests/integration/ -v
```

### Tier 3: Real-Device Tests (Systematic)

**Location**: `scripts/test-automated.py`

**Purpose**: Catch device-specific issues, firmware quirks, real-world scenarios

**Characteristics**:
- ⚠️ Requires running Home Assistant
- ⚠️ Requires real WiiM devices
- ⚠️ Slower (5-15 minutes)
- ✅ Systematic coverage
- ✅ Result tracking
- ✅ Regression detection

**When to use**:
- Before major releases
- When testing new features
- Final validation before release

**Run with**:
```bash
# Critical path (5 min)
python scripts/test-automated.py --mode critical --version 1.0.37

# Full suite (15 min)
python scripts/test-automated.py --mode full --version 1.0.37
```

### Tier 4: Smoke Tests (Quick Validation)

**Location**: `scripts/test-smoke.py`

**Purpose**: Fast validation that nothing is broken

**Characteristics**:
- ✅ Very fast (2-3 minutes)
- ⚠️ Requires running Home Assistant
- ⚠️ Requires real WiiM devices
- ✅ Quick feedback

**When to use**:
- Before commits (optional)
- Quick validation after changes
- Pre-release smoke check

**Run with**:
```bash
make test-smoke        # Requires HA_URL and HA_TOKEN env vars
python scripts/test-smoke.py --ha-url http://localhost:8123 --token YOUR_TOKEN
```

## Test Directory Structure

### `tests/` - Automated Tests

```
tests/
├── unit/              # Tier 1: Unit tests (fast, isolated, mocked)
│   ├── test_media_player.py
│   ├── test_config_flow.py
│   ├── test_diagnostics.py
│   └── ...
├── integration/        # Tier 2: Integration tests (pywiim integration)
│   ├── test_pywiim_integration.py
│   ├── test_state_callbacks.py
│   └── test_coordinator_refresh.py
├── fixtures/          # Realistic test fixtures
│   └── realistic_player.py
├── conftest.py        # All pytest fixtures (consolidated)
└── run_tests.py       # Test runner
```

### `scripts/` - Real-Device Tests

```
scripts/
├── test-smoke.py              # Tier 4: Smoke tests (quick validation)
├── test-automated.py          # Tier 3: Automated real-device tests
├── test-complete-suite.py     # Legacy: Full feature test
├── test-real-devices.py        # Legacy: Basic device test
├── test-advanced-features.py  # Legacy: Advanced features
├── lib/
│   └── test_tracker.py        # Result tracking utilities
└── pre-release-check.py       # Pre-release validation
```

## Testing Workflow

### Daily Development

```bash
# Fast feedback - run unit tests
make test-quick

# Before committing
make test
make lint
```

### Before PR

```bash
# Comprehensive automated tests
make test              # Unit tests
make test-integration  # Integration tests
make lint              # Code quality
```

### Pre-Release

```bash
# 1. Automated tests (MANDATORY)
make test              # Unit tests
make test-integration  # Integration tests
make lint              # Code quality
make pre-release       # Full validation checklist

# 2. Real-device validation (RECOMMENDED)
# Critical path (5 min)
python scripts/test-automated.py --mode critical --version 1.0.37

# Or full suite (15 min)
python scripts/test-automated.py --mode full --version 1.0.37
```

### When Fixing Bugs

```bash
# 1. Write failing test (TDD)
pytest tests/unit/test_media_player.py::test_new_bug -v

# 2. Verify test fails (reproduces bug)
# ... test should fail ...

# 3. Fix the bug
# ... edit code ...

# 4. Verify test passes
pytest tests/unit/test_media_player.py::test_new_bug -v

# 5. Run full suite
make test
```

## Test Requirements

### Coverage Goals

- **Current**: 56% (above 10% minimum)
- **Target**: 80%+
- **Focus**: Core functionality first, then expand to sensors, buttons, numbers

### Current Test Status

- **Total Test Cases**: 214+
- **Passing Tests**: 183+
- **Test Files**: 16 unit test files
- **Coverage**: 56% and growing

### Test Types

#### Tier 1: Unit Tests (`tests/unit/`)

**Pattern**:

```python
def test_component_behavior():
    """Test description."""
    # Arrange
    mock_player = MagicMock()
    mock_player.volume_level = 0.5

    # Act
    result = entity.volume_level

    # Assert
    assert result == 0.5
```

**Requirements**:
- Fast (< 1 second per test)
- Isolated (no side effects)
- Mocked (no real devices)
- Comprehensive (all code paths)

**Fixtures**:
- Use `realistic_player` fixture for Player mocks with callback simulation
- Use `realistic_group` fixture for multiroom testing

#### Tier 2: Integration Tests (`tests/integration/`)

**Pattern**:

```python
async def test_coordinator_uses_player_refresh(coordinator_with_real_player):
    """Coordinator should call player.refresh() in _async_update_data."""
    coordinator = coordinator_with_real_player

    with patch.object(coordinator.player, "refresh", new_callable=AsyncMock) as mock_refresh:
        await coordinator._async_update_data()
        mock_refresh.assert_called_once()
```

**Requirements**:
- Use real pywiim Player objects (mocked HTTP)
- Test integration patterns
- Validate callback flows
- Fast (runs in seconds)

#### Tier 3: Real-Device Tests (`scripts/test-automated.py`)

**Requirements**:
- Real devices
- Real Home Assistant instance
- Systematic coverage
- Result tracking
- Before major releases

#### Tier 4: Smoke Tests (`scripts/test-smoke.py`)

**Requirements**:
- Real devices
- Real Home Assistant instance
- Quick validation (2-3 min)
- Before commits (optional)

## Test Naming Convention

```python
def test_<component>_<behavior>_<condition>():
    """Test description."""
    pass
```

**Examples**:

- `test_media_player_volume_step_reads_from_config()`
- `test_media_player_volume_level_for_slave_in_group()`
- `test_config_flow_options_handles_missing_entry()`
- `test_diagnostics_upnp_client_safe_access()`

## Test Fixtures

All fixtures are defined in `tests/conftest.py` and organized into categories:

### Autouse Fixtures (applied automatically)

- `auto_enable_custom_integrations` - Enable custom integrations
- `skip_notifications` - Skip notification calls
- `allow_unwatched_threads` - Allow background threads

### Core Mock Fixtures

- `mock_wiim_client` - Mock pywiim client with common methods
- `mock_coordinator` - Mock coordinator with standard data structure

### Error Simulation Fixtures

- `bypass_get_data` - Bypass API calls and return mock data
- `error_on_get_data` - Simulate API errors for error handling tests

### WiiM-Specific Fixtures

- `wiim_config_entry` - Mock config entry
- `wiim_client` - Mock WiiM client with realistic responses
- `wiim_coordinator` - Mock coordinator with full player object
- `wiim_speaker` - Test Speaker instance with HA integration
- `wiim_speaker_slave` - Test slave Speaker for group testing

### Helper Fixtures

- `mock_wiim_device_registry` - Mock device registry
- `mock_wiim_dispatcher` - Mock dispatcher

Note: Many test files define their own local fixtures for specific test scenarios. This is acceptable and encouraged when fixtures are test-specific.

## Regression Tests

### Every Bug Fix Must Include a Test

**Process**:

1. Write failing test (reproduces bug)
2. Verify test fails
3. Fix the bug
4. Verify test passes
5. Add edge cases

**Examples**:

- Issue #127: `test_volume_step_reads_from_config_*`
- Issue #126: `test_volume_level_for_slave_in_group`
- Diagnostics: `test_diagnostics_handles_missing_upnp_client`

## Running Tests

### Tier 1: Unit Tests

```bash
make test              # All unit tests
make test-quick        # Fast (no coverage)
pytest tests/unit/ -v  # Unit tests only
```

### Tier 2: Integration Tests

```bash
make test-integration           # Integration tests
pytest tests/integration/ -v     # Integration tests only
```

### Tier 3: Real-Device Tests

```bash
# Critical path (5 min)
python scripts/test-automated.py --mode critical --version 1.0.37

# Full suite (15 min)
python scripts/test-automated.py --mode full --version 1.0.37
```

### Tier 4: Smoke Tests

```bash
# Requires HA_URL and HA_TOKEN environment variables
make test-smoke

# Or directly
python scripts/test-smoke.py --ha-url http://localhost:8123 --token YOUR_TOKEN
```

### All Automated Tests

```bash
make test-all  # Unit + Integration tests
```

### Pre-Release Validation

```bash
make pre-release  # Full validation checklist
```

### Specific Test

```bash
pytest tests/unit/test_media_player.py::TestWiiMMediaPlayerVolume::test_volume_step_reads_from_config_custom -v
```

### With Coverage

```bash
pytest --cov=custom_components.wiim --cov-report=html
# Open htmlcov/index.html in browser
```

## Pre-Release Checklist

Use `make pre-release` or `python scripts/pre-release-check.py` to validate:

- ✅ All unit tests pass
- ✅ Integration tests pass
- ✅ Coverage above threshold (70%+)
- ✅ Linting passes
- ✅ Smoke tests pass (if device available)

## Test Maintenance

### Keep Tests Up to Date

- Update tests when code changes
- Remove obsolete tests
- Refactor tests when code refactors
- Document complex test scenarios
- Use realistic fixtures for better coverage

### Monthly Review

- Coverage report
- Test execution time
- Flaky tests
- Missing coverage areas
- Real-device test results comparison

## Test Fixtures

### Realistic Player Fixtures

Located in `tests/fixtures/realistic_player.py`:

- `realistic_player` - Player mock with callback simulation
- `realistic_player_solo` - Solo player
- `realistic_player_master` - Master player
- `realistic_player_slave` - Slave player
- `realistic_group` - Group mock for multiroom testing
- `player_with_state` - Parameterized fixture for different states

These fixtures simulate real pywiim Player behavior including:
- Callback firing on commands
- State transitions
- Group operations
- Property access patterns

See `tests/FIXTURES.md` for complete fixture documentation.
