# WiiM Unit Tests

## Quick Start

```bash
# Run all tests
make test

# Run unit tests only
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/test_media_player.py -v

# Run with coverage
pytest --cov=custom_components.wiim --cov-report=term-missing
```

## Test Structure

```
tests/
├── unit/              # Unit tests (fast, isolated, mocked)
│   ├── test_media_player.py    # Media player functionality
│   ├── test_config_flow.py     # Config flow & options
│   ├── test_diagnostics.py     # Diagnostics & error handling
│   └── ...
├── conftest.py        # All pytest fixtures (consolidated)
└── run_tests.py       # Test runner script
```

## Test Categories

### Unit Tests (`tests/unit/`)

- **Fast** - Run in seconds
- **Isolated** - Use mocks/fixtures
- **Comprehensive** - Test all code paths
- **Regression** - Prevent bugs from returning

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

## Adding New Tests

### When Fixing a Bug

1. **Write failing test first (TDD)**

   ```python
   def test_bug_description():
       """Test that reproduces the bug."""
       # Arrange
       # Act
       # Assert - should fail initially
   ```

2. **Verify test fails** (confirms bug exists)

3. **Fix the bug**

4. **Verify test passes**

5. **Add edge cases**

### Test Naming

```python
def test_<component>_<behavior>_<condition>():
    """Test description."""
    pass
```

Examples:

- `test_media_player_volume_step_reads_from_config()`
- `test_config_flow_options_handles_missing_entry()`
- `test_diagnostics_upnp_client_safe_access()`

## Test Fixtures

See `conftest.py` for all available fixtures, organized into categories:

**Autouse Fixtures** (applied automatically):

- `auto_enable_custom_integrations` - Enable custom integrations
- `skip_notifications` - Skip notification calls
- `allow_unwatched_threads` - Allow background threads

**Core Mock Fixtures**:

- `mock_wiim_client` - Mock pywiim client
- `mock_coordinator` - Mock coordinator

**Error Simulation Fixtures**:

- `bypass_get_data` - Bypass API calls for testing integration setup
- `error_on_get_data` - Simulate API errors

**WiiM-Specific Fixtures**:

- `wiim_config_entry`, `wiim_client`, `wiim_coordinator`, `wiim_speaker`, `wiim_speaker_slave`

**Helper Fixtures**:

- `mock_wiim_device_registry`, `mock_wiim_dispatcher`

Note: Many test files define their own local fixtures for specific scenarios. See `conftest.py` for complete documentation.

## Coverage Goals

- **Current:** 56% (above 10% minimum)
- **Target:** 80%+
- **Focus:** Core functionality first, then expand to sensors, buttons, numbers

## Test Files

### Unit Tests

- `test_media_player.py` - Media player entity (40+ tests)
- `test_group_media_player.py` - Group coordinator entity (42 tests)
- `test_config_flow.py` - Config and options flow (12+ tests)
- `test_light.py` - LED light entity (18 tests)
- `test_select.py` - Output mode selection (18 tests)
- `test_services.py` - Custom services (9 tests)
- `test_diagnostics.py` - Diagnostics (4 tests)
- `test_data.py` - Speaker data class (6 tests)
- `test_system_health.py` - System health (1 test)
- `test_entity_core.py` - Base entity (4 tests)
- `test_coordinator_core.py` - Coordinator (9 tests)
- `test_init_integration.py` - Integration setup and teardown (10 tests)
- `test_binary_sensor.py` - Binary sensor platform (1 test)
- `test_button.py` - Button entities (11 tests)
- `test_number.py` - Number entities (4 tests)
- `test_sensor_core.py` - Sensor platform (multiple tests)

**Total: 214+ test cases, 183+ passing**

## See Also

- `docs/TESTING-CONSOLIDATED.md` - Complete testing strategy (includes test directory explanation)
- `docs/bug-fix-testing-checklist.md` - Bug fix workflow
- `docs/DEVELOPMENT-RULES.md` - Development rules (includes documentation guidelines)
