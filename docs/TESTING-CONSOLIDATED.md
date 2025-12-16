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

**Automated Test Suite** (`test-automated.py`):

| Test                  | Description                                         |
| --------------------- | --------------------------------------------------- |
| device_discovery      | Find WiiM devices in HA                             |
| playback_controls     | Play/pause/stop                                     |
| volume_control        | Volume set/mute                                     |
| state_synchronization | State updates properly                              |
| source_selection      | Input source switching (shows available sources)    |
| multiroom_basic       | Basic group check                                   |
| eq_control            | EQ preset selection                                 |
| shuffle_repeat        | Shuffle/repeat (skips if source doesn't support)    |
| output_mode           | Audio output mode selection (Line Out/Optical/Coax) |
| play_preset           | Preset playback                                     |
| play_url              | URL playback                                        |
| announcements         | Notification/TTS playback                           |
| queue_management      | Queue info retrieval                                |
| sync_time             | Device time synchronization                         |
| bluetooth_output      | Bluetooth output selection                          |

**Multiroom Comprehensive** (`test-multiroom-comprehensive.py`):

| Test                | Description                         |
| ------------------- | ----------------------------------- |
| 2-device join       | Join two devices                    |
| Unjoin slave        | Unjoin slave device                 |
| 3-device join       | Join three devices                  |
| Unjoin middle       | Unjoin middle device (breaks group) |
| Rejoin 2 devices    | Rejoin two devices                  |
| Unjoin master       | Unjoin master (slave becomes solo)  |
| Join already joined | Replace group membership            |
| Unjoin solo         | Unjoin when already solo            |
| Join to self        | Edge case - device joins itself     |
| Complex join        | Multi-step: A+B then add C          |

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

**Smoke Tests:**

1. Device discovery
2. Basic playback (play/pause)
3. Volume control
4. State synchronization

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
├── test-multiroom-comprehensive.py  # Multiroom edge cases
├── lib/
│   └── test_tracker.py        # Result tracking utilities
└── pre-release-check.py       # Pre-release validation
```

## Device Requirements for Real Tests

### Minimum (Smoke/Automated Tests)

- 1 WiiM device (tests use first available device dynamically)
- Home Assistant running with WiiM integration
- Note: Some tests skip gracefully if source doesn't support feature (e.g., shuffle on Bluetooth)

### Full Multiroom Testing

- 3 WiiM devices on same network
- Active audio source on at least one device
- Note: Multiroom tests use device IPs configured in the test script

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
export HA_TOKEN=$(cat ~/.ha_token)
python scripts/test-automated.py --config scripts/test.config --mode full
make test-multiroom    # Comprehensive multiroom testing
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

## Key Design Decisions

### 1. Capability Checks Delegated to pywiim

We do NOT check source types in our code. All capability checks use pywiim's properties:

```python
# ✅ CORRECT - use pywiim capability properties
if self._shuffle_supported():  # Uses player.shuffle_supported
    features |= MediaPlayerEntityFeature.SHUFFLE_SET

# ❌ WRONG - don't check source types
if source != "AirPlay":  # Never do this
    ...
```

### 2. No async_request_refresh() in Entity Methods

Per pywiim guide, entities should NOT call refresh after commands:

- Commands trigger callbacks automatically
- Coordinator handles refresh scheduling
- Callbacks update state immediately

### 3. Separate Comprehensive from Automated Tests

- `test-automated.py` - Fast, runs in full suite (~5 min)
- `test-multiroom-comprehensive.py` - Thorough, runs separately (~10 min)

This keeps the main test suite fast while providing thorough multiroom coverage when needed.

## Test Requirements

### Coverage Goals

- **Target**: 80%+
- **Focus**: Core functionality first, then expand to sensors, buttons, numbers

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

### Quick Reference

```bash
make test              # All unit tests with coverage
make test-quick        # Fast (no coverage)
make test-integration  # Integration tests
make test-smoke        # Smoke tests (requires devices)
make test-all          # Unit + Integration tests
make pre-release       # Full validation checklist
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

## Known Issues and Dependencies

### pytest-asyncio `event_loop` Fixture Deprecation Warning

**Status**: Known issue, monitoring for resolution

**Warning Message**:

```
Warning: The event_loop fixture provided by pytest-asyncio has been redefined in
/home/runner/work/wiim/wiim/tests/conftest.py:31
Replacing the event_loop fixture with a custom implementation is deprecated
and will lead to errors in the future.
```

**Root Cause**:

- `pytest-asyncio` v1.0.0+ (released May 2025) removed the `event_loop` fixture
- `pytest-homeassistant-custom-component==0.13.251` still depends on the legacy `event_loop` fixture via its `enable_event_loop_debug` autouse fixture
- A custom `event_loop` fixture in `tests/conftest.py` (lines 31-43) bridges this compatibility gap

**Current Workaround**:
The custom fixture in `conftest.py` provides the legacy `event_loop` fixture that the HA test plugin expects:

```python
@pytest.fixture
def event_loop() -> asyncio.AbstractEventLoop:
    """Provide legacy `event_loop` fixture for HA pytest plugin compatibility."""
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()
```

**Why This Exists**:

- Required for `pytest-homeassistant-custom-component`'s `enable_event_loop_debug` fixture to work
- Without it, tests would fail with missing fixture errors
- This is a temporary workaround until the HA plugin updates to support newer pytest-asyncio

**Future Resolution**:

1. **Short term**: Warning is informational only - tests continue to work
2. **Medium term**: Monitor `pytest-homeassistant-custom-component` releases for pytest-asyncio v1.0+ compatibility
3. **Long term**: When HA plugin updates, remove custom fixture and rely on pytest-asyncio's built-in behavior

**Options Considered**:

- **Suppress warning**: Could add `filterwarnings` to `pytest.ini`, but doesn't fix underlying issue
- **Use `event_loop_policy`**: Modern approach, but may not satisfy HA plugin's requirements
- **Disable `enable_event_loop_debug`**: Would lose useful debugging capabilities

**Action Items**:

- [ ] Monitor `pytest-homeassistant-custom-component` releases
- [ ] Test compatibility when HA plugin updates
- [ ] Remove custom fixture once upstream supports newer pytest-asyncio
- [ ] Consider suppressing warning if it becomes too noisy

**Related Files**:

- `tests/conftest.py` (lines 31-43) - Custom event_loop fixture
- `pytest.ini` - pytest-asyncio configuration
- `requirements_test.txt` - pytest-homeassistant-custom-component dependency

**Last Updated**: 2025-12-10

## File Reference

| File                                      | Purpose                  |
| ----------------------------------------- | ------------------------ |
| `tests/unit/`                             | Unit tests with mocks    |
| `tests/integration/`                      | pywiim integration tests |
| `tests/fixtures/realistic_player.py`      | Realistic Player mock    |
| `tests/conftest.py`                       | Shared fixtures          |
| `tests/FIXTURES.md`                       | Fixture documentation    |
| `scripts/test-smoke.py`                   | Quick smoke tests        |
| `scripts/test-automated.py`               | Full automated suite     |
| `scripts/test-multiroom-comprehensive.py` | Multiroom edge cases     |
| `scripts/pre-release-check.py`            | Pre-release validation   |
| `scripts/test.config`                     | Test configuration       |
| `Makefile`                                | Build/test commands      |
