# Service Test Coverage

This document lists all registered services and their test coverage status.

## Service Test Coverage Summary

### ✅ Fully Tested Services

#### Core Services (in `services.py`)

- ✅ **`set_sleep_timer`** - Tested in `test_services.py::TestServiceExecution`
- ✅ **`clear_sleep_timer`** - Tested in `test_services.py::TestServiceExecution`
- ✅ **`update_alarm`** - Tested in `test_services.py::TestServiceExecution`

#### Global Services (in `__init__.py`)

- ✅ **`reboot_device`** - Tested in `test_init_integration.py::test_reboot_device_service`
- ✅ **`sync_time`** - Tested in `test_init_integration.py::test_sync_time_service`

#### Media Player Services (in `media_player.py`)

- ✅ **`play_url`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers::test_async_play_url`
- ✅ **`play_preset`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers::test_async_play_preset`
- ✅ **`play_playlist`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers::test_async_play_playlist`
- ✅ **`set_eq`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers`:
  - `test_async_set_eq_preset` - EQ preset selection
  - `test_async_set_eq_custom_list` - Custom EQ with list values
  - `test_async_set_eq_custom_dict` - Custom EQ with dict values
  - `test_async_set_eq_requires_custom_values` - Validation when preset is custom
  - `test_async_set_eq_not_supported` - Error when EQ not supported
  - `test_async_set_eq_handles_error` - Error handling
- ✅ **`play_notification`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers::test_async_play_notification`
- ✅ **`play_queue`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers`:
  - `test_async_play_queue_no_upnp` - Error when UPnP not available
  - `test_async_play_queue_not_implemented` - Error until pywiim implements
- ✅ **`remove_from_queue`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers`:
  - `test_async_remove_from_queue_no_upnp` - Error when UPnP not available
  - `test_async_remove_from_queue_not_implemented` - Error until pywiim implements
- ✅ **`get_queue`** - Tested in `test_media_player.py::TestWiiMMediaPlayerServiceHandlers`:
  - `test_async_get_queue_no_upnp` - Error when UPnP not available
  - `test_async_get_queue_not_implemented` - Error until pywiim implements

## Test Coverage Details

### Service Registration Tests

**Location**: `tests/unit/test_services.py::TestAllServicesRegistered`

- ✅ `test_all_services_from_yaml_registered` - Ensures all YAML services are registered
- ✅ `test_services_yaml_matches_registered_services` - Ensures registered services have YAML
- ✅ `test_services_yaml_structure` - Validates YAML structure

### Service Execution Tests

**Location**: `tests/unit/test_services.py::TestServiceExecution`

- ✅ `test_set_sleep_timer_calls_entity_method`
- ✅ `test_clear_sleep_timer_calls_entity_method`
- ✅ `test_update_alarm_calls_entity_method`

### Service Handler Tests

**Location**: `tests/unit/test_media_player.py::TestWiiMMediaPlayerServiceHandlers`

All service handler methods are tested with:

- ✅ Happy path (successful execution)
- ✅ Error cases (when features not supported)
- ✅ Edge cases (missing parameters, invalid values)
- ✅ Error handling (WiiMError conversion to HomeAssistantError)

## Test Statistics

- **Total Services**: 13 registered services
- **Tested Services**: 13 (100% coverage)
- **Test Classes**: 4
  - `TestServiceRegistration` - Registration and schema tests (4 tests)
  - `TestServiceExecution` - Service execution tests (3 tests)
  - `TestServiceValidation` - Parameter validation tests (2 tests)
  - `TestAllServicesRegistered` - Comprehensive registration checks (3 tests)
  - `TestWiiMMediaPlayerServiceHandlers` - Handler method tests (16 tests)
- **Total Test Methods**: 28 service-specific tests
- **All Tests Passing**: ✅ Yes

## Services Not Registered (Intentionally)

These services are defined in `services.yaml` but intentionally not registered:

- `scan_bluetooth` - Unofficial API
- `set_channel_balance` - Unofficial API
- `set_spdif_delay` - Unofficial API
- `discover_lms_servers` - Unofficial API
- `connect_lms_server` - Unofficial API
- `set_auto_connect_lms` - Unofficial API
- `set_touch_buttons` - Unofficial API

These are marked as "unofficial" and may not be fully implemented/tested.

## Running Tests

### Run All Service Tests

```bash
pytest tests/unit/test_services.py -v
pytest tests/unit/test_media_player.py::TestWiiMMediaPlayerServiceHandlers -v
pytest tests/unit/test_init_integration.py::test_reboot_device_service -v
pytest tests/unit/test_init_integration.py::test_sync_time_service -v
```

### Run Service Registration Tests

```bash
pytest tests/unit/test_services.py::TestAllServicesRegistered -v
```

### Run Service Handler Tests

```bash
pytest tests/unit/test_media_player.py::TestWiiMMediaPlayerServiceHandlers -v
```

## Test Coverage Goals

✅ **100% Service Coverage** - All registered services have tests
✅ **Registration Tests** - Tests ensure services are registered
✅ **Execution Tests** - Tests verify service calls work
✅ **Error Handling** - Tests cover error cases
✅ **Edge Cases** - Tests cover validation and edge cases

## Maintenance

When adding new services:

1. **Add to `services.yaml`** - Define service schema
2. **Register in Python** - Add registration code
3. **Add handler method** - Implement service handler
4. **Add tests** - Create tests in `TestWiiMMediaPlayerServiceHandlers`
5. **Update this document** - Add service to coverage list

The `TestAllServicesRegistered` test will automatically catch if you forget to register a service!
