# Testing Strategy - Preventing Random Release Problems

**Date:** 2025-01-15 (Updated: 2025-12-04)
**Context:** pywiim 2.1.43+ update, addressing recurring issues with each release

## Problem Statement

We're experiencing random problems with each release that aren't caught by our current testing approach. These issues typically manifest as:

- State synchronization problems
- Edge cases in real-world usage
- Integration issues between pywiim and HA
- Race conditions and timing issues
- Device-specific firmware quirks

## Implementation Status

### ✅ Completed

- [x] Update pywiim to 2.1.43
- [x] Download latest HA integration and API guides
- [x] Create realistic player fixtures (`tests/fixtures/realistic_player.py`)
- [x] Add edge case tests for None values (`tests/unit/test_media_player.py`)
- [x] Create integration test structure (`tests/integration/`)
- [x] Create smoke test script (`scripts/test-smoke.py`)
- [x] Create automated test runner (`scripts/test-automated.py`)
- [x] Create comprehensive multiroom tests (`scripts/test-multiroom-comprehensive.py`)
- [x] Create pre-release validation (`scripts/pre-release-check.py`)
- [x] Update Makefile with new targets
- [x] Update code to delegate capability checks to pywiim (no source-type checks)

### 🔄 In Progress / Future

- [ ] Increase coverage to 80%+
- [ ] Add smoke tests to pre-commit hook (optional)
- [ ] Track test results over time with JSON output

---

## 4-Tier Testing Strategy

### Tier 1: Fast Unit Tests

**Purpose:** Catch logic errors, regressions, basic functionality

**Files:**

- `tests/unit/` - All unit test files
- `tests/fixtures/realistic_player.py` - Realistic Player mock

**Commands:**

```bash
make test           # Full test suite with coverage
make test-quick     # Fast tests without coverage
```

**Coverage:** 214+ test cases, 56% coverage (target: 80%)

---

### Tier 2: Integration Tests

**Purpose:** Test pywiim → HA integration layer

**Files:**

- `tests/integration/test_pywiim_integration.py`
- `tests/integration/test_coordinator_refresh.py`
- `tests/integration/test_state_callbacks.py`

**Commands:**

```bash
make test-integration
```

---

### Tier 3: Real Device Tests

**Purpose:** Catch device-specific issues, firmware quirks, real-world scenarios

**Files:**

- `scripts/test-automated.py` - Full automated suite (15 tests, ~5 min)
- `scripts/test-multiroom-comprehensive.py` - Full multiroom testing (10 tests, ~10 min)
- `scripts/test-device-115-comprehensive.py` - Device-specific deep testing

**Commands:**

```bash
# Quick automated tests (15 tests) - uses first available device
python scripts/test-automated.py --config scripts/test.config --mode full

# Critical path only (4 tests)
python scripts/test-automated.py --config scripts/test.config --mode critical

# Comprehensive multiroom tests (10 scenarios)
make test-multiroom
```

**Automated Test Suite (`test-automated.py`):**
| Test | Description |
|------|-------------|
| device_discovery | Find WiiM devices in HA |
| playback_controls | Play/pause/stop |
| volume_control | Volume set/mute |
| state_synchronization | State updates properly |
| source_selection | Input source switching (shows available sources) |
| multiroom_basic | Basic group check |
| eq_control | EQ preset selection |
| shuffle_repeat | Shuffle/repeat (skips if source doesn't support) |
| output_mode | Audio output mode selection (Line Out/Optical/Coax) |
| play_preset | Preset playback |
| play_url | URL playback |
| announcements | Notification/TTS playback |
| queue_management | Queue info retrieval |
| sync_time | Device time synchronization |
| bluetooth_output | Bluetooth output selection |

**Multiroom Comprehensive (`test-multiroom-comprehensive.py`):**
| Test | Description |
|------|-------------|
| 2-device join | Join .115 + .68 |
| Unjoin slave | Unjoin .68 |
| 3-device join | Join .115 + .68 + .116 |
| Unjoin middle | Unjoin .68 (breaks group) |
| Rejoin 2 devices | Rejoin .115 + .116 |
| Unjoin master | Unjoin .115 (slave becomes solo) |
| Join already joined | Replace group membership |
| Unjoin solo | Unjoin when already solo |
| Join to self | Edge case - device joins itself |
| Complex join | Multi-step: A+B then add C |

---

### Tier 4: Smoke Tests

**Purpose:** Fast validation that nothing is broken

**Files:**

- `scripts/test-smoke.py` - Quick 4-test validation

**Commands:**

```bash
make test-smoke
# or
python scripts/test-smoke.py --config scripts/test.config
```

**Tests:**

1. Device discovery
2. Basic playback (play/pause)
3. Volume control
4. State synchronization

---

## Testing Workflow

### Before Every Commit

```bash
make test-quick     # Unit tests only (30 seconds)
make lint           # Code quality
```

### Before Every PR

```bash
make test           # All unit tests with coverage
make lint           # Code quality
make test-integration  # Integration tests
```

### Before Every Release

```bash
# Full automated validation
make pre-release

# Real device tests (with devices connected)
export HA_TOKEN=$(cat ~/.ha_token)
python scripts/test-automated.py --config scripts/test.config --mode full
make test-multiroom   # Comprehensive multiroom testing
```

---

## Device Requirements for Real Tests

### Minimum (Smoke/Automated Tests)

- 1 WiiM device (tests use first available device dynamically)
- Home Assistant running with WiiM integration
- Note: Some tests skip gracefully if source doesn't support feature (e.g., shuffle on Bluetooth)

### Full Multiroom Testing

- 3 WiiM devices on same network
- Active audio source on at least one device
- Note: Multiroom tests use device IPs configured in the test script

---

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

---

## Success Metrics

- **Coverage:** 56% → 80%+
- **Test Execution Time:** < 5 minutes for automated suite
- **Release Issues:** Reduce by 80%
- **Pre-Release Validation:** Automated, < 15 minutes
- **Test Reliability:** 100% pass rate on known-good code

---

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
