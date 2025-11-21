# Test Suite Analysis - Migration to pywiim

## Overview

This integration is a **simple wrapper** around the `pywiim` library. According to `.cursorrules`, we should:

- ✅ Test integration glue code (HA-specific code)
- ❌ NOT test pywiim library functionality (that's the library's responsibility)

## Current Test Structure

### Core Integration Tests (KEEP - These test integration glue)

- ✅ `test_init_core.py` - Tests integration setup, error handling, coordinator/speaker creation
- ✅ `test_coordinator_core.py` - Tests coordinator wrapper using pywiim `Player.refresh()` (CURRENT implementation)
- ✅ `test_data_core.py` - Tests `Speaker` class and helper functions
- ✅ `test_entity_core.py` - Tests base entity class
- ✅ `test_services_core.py` - Tests HA-specific services
- ✅ `test_coordinator_multiroom.py` - Tests integration-specific multiroom source/media resolution logic
- ✅ `test_sensor_core.py` - Tests sensor platform logic and utilities
- ✅ `test_switch_core.py` - Tests switch platform logic
- ✅ `test_update_core.py` - Tests update platform logic

### Platform Entity Tests (KEEP - These test HA entity implementations)

- ✅ `test_media_player.py` - Tests media player entity
- ✅ `test_group_media_player.py` - Tests group media player entity
- ✅ `test_select.py` - Tests select entities
- ✅ `test_number.py` - Tests number entities
- ✅ `test_light.py` - Tests light entity
- ✅ `test_button.py` - Tests button entities
- ✅ `test_binary_sensor.py` - Tests binary sensor entities
- ✅ `test_sensor.py` - Tests sensor entity classes (WiiMRoleSensor, etc.)
- ✅ `test_config_flow.py` - Tests HA config flow
- ✅ `test_discovery_flows.py` - Tests discovery flows
- ✅ `test_diagnostics.py` - Tests diagnostics
- ✅ `test_system_health.py` - Tests system health
- ✅ `test_media_commands_enhanced.py` - Tests media command handling
- ✅ `test_media_image_cache.py` - Tests media image caching
- ✅ `test_elapsed_time_last_updated.py` - Tests elapsed time tracking

### Redundant/Outdated Tests (REMOVE - These test old implementation or pywiim directly)

#### ❌ `test_coordinator.py` - REMOVE

**Reason**: Tests OLD implementation that directly calls `WiiMClient.get_player_status()`, `get_device_info()`, etc.

- Current implementation uses `Player.refresh()` from pywiim
- This file tests pywiim API directly, not integration glue
- Functionality is covered by `test_coordinator_core.py`

#### ❌ `test_init.py` - REMOVE

**Reason**: Most tests are skipped, tests outdated implementation

- Functionality is covered by `test_init_core.py`
- Contains skipped tests with note "Skipped due to HA background thread issue"

#### ⚠️ `test_init_integration.py` - KEEP (but consider moving to `integration/`)

**Reason**: Tests integration-level functionality (device registry, entity registry, teardown, reload)

- `test_init_core.py` - Unit tests for setup function
- `test_init_integration.py` - Integration tests for full lifecycle (device creation, platform setup, teardown)
- They're complementary, but name suggests it belongs in `integration/` directory

#### ⚠️ `test_sensor.py` - KEEP (tests entity classes, different from `_core`)

**Reason**: Tests HA entity classes (WiiMRoleSensor, WiiMDiagnosticSensor, etc.)

- `test_sensor_core.py` tests platform setup logic and utilities
- `test_sensor.py` tests entity implementations
- Both are needed, test different aspects

#### ❌ `test_switch.py` - REMOVE (redundant with `test_switch_core.py`)

**Reason**: Only 2 test classes vs 6 in `test_switch_core.py`

- `test_switch.py`: 128 lines, 2 classes (TestSwitchConstants, TestSwitchPlatformSetup)
- `test_switch_core.py`: 307 lines, 6 classes (includes all from `test_switch.py` plus more)
- `test_switch_core.py` is more comprehensive

#### ❌ `test_update.py` - REMOVE (redundant with `test_update_core.py`)

**Reason**: Likely redundant with more comprehensive `test_update_core.py`

- `test_update.py`: 199 lines, 2 classes
- `test_update_core.py`: 384 lines, more comprehensive
- Review if `test_update.py` has unique tests, but likely covered by `_core`

## What Should Be Tested

### ✅ Integration Glue Code (Test These)

1. **Config Flow** - HA-specific configuration
2. **Coordinator Wrapper** - How it uses pywiim `Player`, not pywiim itself
3. **Entity Classes** - How they transform pywiim data to HA entities
4. **Speaker Class** - HA-specific wrapper around coordinator
5. **Multiroom Resolution** - Integration-specific logic for source/media resolution
6. **HA Services** - Custom services exposed to HA
7. **Platform Setup** - How platforms are initialized
8. **Error Handling** - How HA exceptions are raised from pywiim exceptions

### ❌ pywiim Library Functionality (Don't Test These)

1. Direct API calls (`WiiMClient.get_player_status()`)
2. Device communication (handled by pywiim)
3. Polling strategies (handled by pywiim `PollingStrategy`)
4. Track detection (handled by pywiim `TrackChangeDetector`)
5. State management (handled by pywiim `Player`)

## Recommended Actions

1. **Delete immediately:**

   - `test_coordinator.py` (tests old implementation)
   - `test_init.py` (mostly skipped, outdated)

2. **Delete redundant files:**

   - `test_switch.py` (covered by `test_switch_core.py`)
   - `test_update.py` (covered by `test_update_core.py`)

3. **Keep (but consider moving):**

   - `test_init_integration.py` - Keep, but consider moving to `integration/` directory (tests full lifecycle)

4. **Keep all `_core.py` tests** - These test integration glue code

5. **Keep all platform entity tests** - These test HA entity implementations

## Test Coverage Goals

After cleanup, we should have:

- ✅ Core integration tests (`*_core.py`)
- ✅ Platform entity tests (one per platform)
- ✅ Config flow tests
  - ✅ Integration tests (in `integration/` directory)

## Cleanup Completed ✅

The following redundant test files have been removed:

- ✅ `test_coordinator.py` - Deleted (tests old implementation)
- ✅ `test_init.py` - Deleted (mostly skipped, outdated)
- ✅ `test_switch.py` - Deleted (redundant with `test_switch_core.py`)
- ✅ `test_update.py` - Deleted (redundant with `test_update_core.py`)

The test suite now focuses on testing integration glue code rather than pywiim library functionality.
