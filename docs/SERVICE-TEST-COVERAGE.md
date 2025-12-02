# Action (Service) Test Coverage

This document lists all registered actions and their test coverage status.

> **Note**: Home Assistant now calls "services" as "actions" in the UI. Both terms refer to the same functionality.

## Action Test Coverage Summary

### ✅ Fully Tested Actions

#### Platform Entity Actions (in `services.py`)

- ✅ **`set_sleep_timer`** - Tested in `test_services.py`
- ✅ **`clear_sleep_timer`** - Tested in `test_services.py`
- ✅ **`update_alarm`** - Tested in `test_services.py`
- ✅ **`reboot_device`** - Tested in `test_services.py`
- ✅ **`sync_time`** - Tested in `test_services.py`
- ✅ **`scan_bluetooth`** - Tested in `test_services.py`
- ✅ **`set_channel_balance`** - Tested in `test_services.py`

#### Media Player Entity Actions (in `media_player.py`)

- ✅ **`play_url`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers`
- ✅ **`play_preset`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers`
- ✅ **`play_playlist`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers`
- ✅ **`set_eq`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers`:
  - `test_async_set_eq_preset` - EQ preset selection
  - `test_async_set_eq_custom_list` - Custom EQ with list values
  - `test_async_set_eq_custom_dict` - Custom EQ with dict values
  - `test_async_set_eq_requires_custom_values` - Validation when preset is custom
  - `test_async_set_eq_not_supported` - Error when EQ not supported
  - `test_async_set_eq_handles_error` - Error handling
- ✅ **`play_notification`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers`
- ✅ **`play_queue`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers`
- ✅ **`remove_from_queue`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers`
- ✅ **`get_queue`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers`

## Test Coverage Details

### Action Sync Tests

**Location**: `tests/unit/test_services.py::TestActionYAMLSync`

These tests ensure all actions are properly synchronized across Python, YAML, and strings.json:

- ✅ `test_all_yaml_actions_registered_in_python` - Ensures all YAML actions are registered
- ✅ `test_all_registered_actions_have_yaml_definition` - Ensures registered actions have YAML
- ✅ `test_all_yaml_actions_have_strings_translations` - Ensures all actions have translations
- ✅ `test_strings_json_actions_match_yaml` - Ensures no orphaned translations
- ✅ `test_services_yaml_structure` - Validates YAML structure
- ✅ `test_strings_json_services_structure` - Validates strings.json structure
- ✅ `test_yaml_fields_have_string_translations` - Ensures fields have translations

### Action Registration Tests

**Location**: `tests/unit/test_services.py::TestActionRegistration`

- ✅ `test_all_platform_actions_registered` - All platform actions are registered
- ✅ `test_set_sleep_timer_action_schema`
- ✅ `test_clear_sleep_timer_action_schema`
- ✅ `test_update_alarm_action_schema`
- ✅ `test_reboot_device_action_schema`
- ✅ `test_sync_time_action_schema`
- ✅ `test_scan_bluetooth_action_schema`
- ✅ `test_set_channel_balance_action_schema`

### Action Execution Tests

**Location**: `tests/unit/test_services.py::TestActionExecution`

- ✅ `test_set_sleep_timer_calls_entity_method`
- ✅ `test_clear_sleep_timer_calls_entity_method`
- ✅ `test_update_alarm_calls_entity_method`

### Handler Method Tests

**Location**: `tests/unit/test_services.py::TestMediaPlayerEntityActionHandlers`

- ✅ `test_entity_has_required_handler_methods` - Verifies all handler methods exist

### Action Handler Tests

**Location**: `tests/unit/test_media_player.py::TestWiiMMediaPlayerServiceHandlers`

All action handler methods are tested with:

- ✅ Happy path (successful execution)
- ✅ Error cases (when features not supported)
- ✅ Edge cases (missing parameters, invalid values)
- ✅ Error handling (WiiMError conversion to HomeAssistantError)

## Test Statistics

- **Total Actions**: 15 registered actions
- **Tested Actions**: 15 (100% coverage)
- **Test Classes**: 5
  - `TestActionRegistration` - Registration and schema tests (8 tests)
  - `TestActionExecution` - Action execution tests (3 tests)
  - `TestActionValidation` - Parameter validation tests (4 tests)
  - `TestActionYAMLSync` - Comprehensive sync checks (7 tests)
  - `TestMediaPlayerEntityActionHandlers` - Handler method tests (1 test)
  - `TestWiiMMediaPlayerServiceHandlers` - Handler method tests (16+ tests)
- **Total Test Methods**: 39+ action-specific tests
- **All Tests Passing**: ✅ Yes

## Action Categories

### Official Actions (15 total)

| Action               | Type     | Handler Method             |
| -------------------- | -------- | -------------------------- |
| `play_url`           | Entity   | `async_play_url`           |
| `play_preset`        | Entity   | `async_play_preset`        |
| `play_playlist`      | Entity   | `async_play_playlist`      |
| `set_eq`             | Entity   | `async_set_eq`             |
| `play_notification`  | Entity   | `async_play_notification`  |
| `play_queue`         | Entity   | `async_play_queue`         |
| `remove_from_queue`  | Entity   | `async_remove_from_queue`  |
| `get_queue`          | Entity   | `async_get_queue`          |
| `set_sleep_timer`    | Platform | `set_sleep_timer`          |
| `clear_sleep_timer`  | Platform | `clear_sleep_timer`        |
| `update_alarm`       | Platform | `set_alarm`                |
| `reboot_device`      | Platform | `async_reboot_device`      |
| `sync_time`          | Platform | `async_sync_time`          |
| `scan_bluetooth`     | Platform | `async_scan_bluetooth`     |
| `set_channel_balance`| Platform | `async_set_channel_balance`|

### Registration Methods

- **Entity Actions** (`media_player.py`): `platform.async_register_entity_service()`
- **Platform Actions** (`services.py`): `service.async_register_platform_entity_service()`

## Running Tests

### Run All Action Tests

```bash
pytest tests/unit/test_services.py -v
pytest tests/unit/test_media_player.py::TestWiiMMediaPlayerServiceHandlers -v
```

### Run Action Sync Tests

```bash
pytest tests/unit/test_services.py::TestActionYAMLSync -v
```

### Run Action Registration Tests

```bash
pytest tests/unit/test_services.py::TestActionRegistration -v
```

### Run Action Handler Tests

```bash
pytest tests/unit/test_media_player.py::TestWiiMMediaPlayerServiceHandlers -v
```

## Test Coverage Goals

✅ **100% Action Coverage** - All registered actions have tests
✅ **Registration Tests** - Tests ensure actions are registered
✅ **Sync Tests** - Tests ensure YAML, Python, and strings.json are in sync
✅ **Execution Tests** - Tests verify action calls work
✅ **Error Handling** - Tests cover error cases
✅ **Edge Cases** - Tests cover validation and edge cases

## Maintenance

When adding new actions:

1. **Add to `services.yaml`** - Define action schema
2. **Add to `strings.json`** - Add translations for name, description, and fields
3. **Register in Python** - Add registration code in `services.py` or `media_player.py`
4. **Add handler method** - Implement action handler in `WiiMMediaPlayer`
5. **Add tests** - Create tests in appropriate test class
6. **Update this document** - Add action to coverage list

The `TestActionYAMLSync` tests will automatically catch if you:
- Define an action in YAML but don't register it
- Register an action but don't add it to YAML
- Forget to add translations to strings.json
- Add translations without corresponding YAML definition
- Forget to add field translations
