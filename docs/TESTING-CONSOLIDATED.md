# Testing Guidelines

## Test Directory Structure

### `tests/` - Automated Tests (Primary)

**Location**: `/workspaces/wiim/tests/`

**Structure**:

```
tests/
├── unit/              # Unit tests (fast, isolated, mocked)
│   ├── test_media_player.py
│   ├── test_config_flow.py
│   ├── test_diagnostics.py
│   └── ...
├── integration/       # Integration tests (realistic scenarios)
│   └── test_ipv6_regression.py
├── conftest.py        # Shared pytest fixtures
├── conftest_wiim.py   # WiiM-specific fixtures
└── run_tests.py       # Test runner
```

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
make test              # All tests
pytest tests/unit/     # Unit tests only
python tests/run_tests.py
```

### `scripts/` - Manual Validation (Secondary)

**Location**: `/workspaces/wiim/scripts/`

**Structure**:

```
scripts/
├── test-complete-suite.py      # Full feature test
├── test-real-devices.py         # Basic device test
├── test-advanced-features.py    # Advanced features
├── test-timers-*.py             # Timer-specific tests
├── test.config                  # Saved HA token/config
└── load-test-env.sh             # Load test environment
```

**Characteristics**:

- ⚠️ Requires running Home Assistant
- ⚠️ Requires real WiiM devices
- ⚠️ Slower (minutes, not seconds)
- ⚠️ Can't run in CI/CD easily
- ✅ Tests real-world scenarios
- ✅ Catches integration issues
- ✅ Validates against real devices

**When to use**:

- Before major releases
- When testing new features manually
- User acceptance testing
- Final validation before release

**Run with**:

```bash
source scripts/load-test-env.sh
python scripts/test-complete-suite.py
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

### Pre-Release

```bash
# 1. Automated tests (MANDATORY)
make test
make lint
make check-all

# 2. Manual validation (OPTIONAL, but recommended)
source scripts/load-test-env.sh
python scripts/test-complete-suite.py
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

#### Unit Tests (`tests/unit/`)

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

#### Integration Tests (`tests/integration/`)

**Pattern**:

```python
async def test_workflow():
    """Test complete workflow."""
    # Setup
    # Execute workflow
    # Verify results
```

**Requirements**:

- Realistic scenarios
- May use test containers
- Test workflows, not just units

#### Manual Validation (`scripts/`)

**Requirements**:

- Real devices
- Real Home Assistant instance
- Manual execution
- Before major releases

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

### Shared Fixtures (`conftest.py`)

- `mock_wiim_client` - Mock pywiim client
- `mock_coordinator` - Mock coordinator
- `hass` - Home Assistant instance
- `enable_custom_integrations` - Enable custom integrations

### WiiM Fixtures (`conftest_wiim.py`)

- `mock_player` - Mock pywiim Player
- `mock_speaker` - Mock Speaker object
- `mock_config_entry` - Mock config entry

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

### All Tests

```bash
make test
# or
python tests/run_tests.py
```

### Unit Tests Only

```bash
pytest tests/unit/ -v
# or
python tests/run_tests.py --unit
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

### Quick Test (No Coverage)

```bash
make test-quick
```

## Test Maintenance

### Keep Tests Up to Date

- Update tests when code changes
- Remove obsolete tests
- Refactor tests when code refactors
- Document complex test scenarios

### Monthly Review

- Coverage report
- Test execution time
- Flaky tests
- Missing coverage areas
