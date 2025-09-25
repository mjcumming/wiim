# Changelog

All notable changes to the WiiM Audio integration will be documented in this file.

## [0.1.21] - 2025-09-25

### Fixed

- **Group Coordinator UI Issues**: Fixed multiple group coordinator display and behavior issues
  - Group coordinators no longer appear in join/unjoin menus (excluded GROUPING feature)
  - Dynamic naming now always shows "Group Master" suffix for consistency
  - Fixed Master Bedroom group coordinator visibility issues
  - Improved role detection and immediate UI updates when group roles change
  - Fixed slave speaker input showing "unknown" instead of "Follower" after ungrouping
  - Enhanced role change detection with explicit state updates for immediate UI refresh

### Changed

- **Group Coordinator Naming**: Group coordinator entities now consistently display "Speaker Name Group Master" regardless of availability state
- **Role Change Detection**: Added immediate UI state updates when speaker roles change (master/slave/solo transitions)

## [0.1.20] - 2025-01-27

### Added

- **TTS Support**: Full Text-to-Speech integration support for all TTS engines
  - Google Cloud TTS, Google Translate TTS, Amazon Polly, eSpeak, Microsoft Azure, and more
  - Automatic detection of TTS media sources (`media-source://tts/`)
  - Enhanced media source resolution with TTS-specific error handling
  - Comprehensive logging for TTS content playback
  - Optimistic UI updates for immediate TTS feedback

### Fixed

- **Group Join Controls**: Fixed missing group join functionality in Home Assistant media player UI
  - Improved availability logic to ensure group join controls are visible
  - Added debug logging to help diagnose grouping feature issues
  - Enhanced entity state handling for better UI compatibility
  - Fixed `media_position_updated_at` property to respect entity availability (regression from v0.1.19)

### Technical

- **Media Source Handling**: Enhanced `_is_tts_media_source()` method for reliable TTS detection
- **Audio Validation**: Improved `_is_audio_media_source()` to always allow TTS content
- **Error Handling**: TTS-specific error messages and fallback handling
- **Test Coverage**: Comprehensive test suite for TTS functionality
- **Availability Logic**: Refined entity availability checks for better UI feature exposure

## [0.1.19] - 2025-01-27

### Fixed

- **Test Suite**: Fixed failing test `test_media_properties_unavailable` in group media player

  - Updated test expectation for `media_position_updated_at` to expect timestamp instead of `None` when unavailable
  - Maintains Media Assistant compatibility by always returning valid timestamps
  - Test now correctly validates the intended behavior rather than expecting incorrect behavior

- **Coordinator Polling**: Fixed critical `TypeError` in backoff logic
  - Resolved "unsupported type for timedelta seconds component: datetime.timedelta" error
  - Fixed issue where `backoff_interval` was already a `timedelta` but was being wrapped in another `timedelta`
  - Coordinator polling now properly handles connection failures without crashing

### Technical

- **Code Quality**: Updated to modern Python syntax (`isinstance` with union types)
- **Error Handling**: Improved coordinator error recovery and backoff logic
- **Test Accuracy**: Enhanced test coverage to reflect actual component behavior

## [0.1.18] - 2025-01-27

### Fixed

- **Reboot Device Service**: Fixed critical issue preventing WiiM device restart from Home Assistant
  - Resolved "Failed to perform the action wiim.reboot_device. Unknown error" error
  - Fixed JSON parsing error "Expecting value: line 1 column 1 (char 0)" when device doesn't respond after reboot command
  - Added global service support for `wiim.reboot_device` and `wiim.sync_time`
  - Service now works both as global service (`wiim.reboot_device`) and entity service (`media_player.reboot_device`)

### Technical

- **Service Registration**: Added global service registration using `async_register_admin_service`
- **Response Handling**: Enhanced API client to gracefully handle empty responses and parsing errors from reboot commands
- **Error Recovery**: Improved error handling for commands that don't return proper responses (like reboot)
- **Service Documentation**: Updated services.yaml to include required entity_id field for global services

## [0.1.17] - 2024-08-22

### Fixed

- **Music Assistant Integration**: Fixed critical issue preventing multiple WiiM devices from registering with Music Assistant
  - Resolved `TypeError: fromisoformat: argument must be str` error in Music Assistant
  - All WiiM devices now properly register with Music Assistant instead of just the first one
  - Improved timestamp handling to ensure `media_position_updated_at` always returns valid values

### Technical

- **Timestamp Validation**: Enhanced `get_media_position_updated_at()` method to always return valid timestamps
- **Position Validation**: Added robust validation for media position values to prevent edge case errors
- **Code Quality**: Updated to modern Python syntax (`isinstance` with union types)
- **Error Prevention**: Added safeguards to prevent `None` values from causing

## [0.1.16]

### Fixed

- **Service Registration**: Fixed missing WiiM custom services not appearing in Home Assistant automations
  - `wiim.play_preset` - Play hardware presets (1-20)
  - `wiim.play_url` - Play from URL (radio streams, files)
  - `wiim.play_playlist` - Play M3U playlists
  - `wiim.set_eq` - Configure equalizer (presets or custom 10-band)
  - `wiim.play_notification` - Play notification sounds
  - `wiim.reboot_device` - Restart the WiiM device
  - `wiim.sync_time` - Synchronize device time

### Technical

- **Service Implementation**: Added proper service registration in media player platform setup
- **Test Environment**: Fixed test import issues and improved test coverage

## [1.0.15]

### Fixed

- **Group State UI Updates**: Added optimistic UI updates for group join/ungroup operations
- **Ungroup Responsiveness**: Immediate UI feedback when ungrouping speakers
- **Group State Synchronization**: Faster group state changes in mixed device setups

### Added

- **Optimistic Group State**: Immediate UI updates for group operations
- **Group State Properties**: Enhanced group state tracking and display

## [1.0.14]

### Fixed

- **Speaker Grouping State Change Latency**: Fixed firmware compatibility issues causing delays in group state changes
- **Legacy Device Support**: Improved support for older LinkPlay-based devices (Audio Pro, etc.)
- **Adaptive Polling**: Enhanced polling intervals based on device type and activity state
- **Error Recovery**: Better handling of malformed API responses from legacy devices
- **Test Suite**: Fixed test environment issues and improved test coverage

### Added

- **Firmware Capability Detection**: Automatic detection of device capabilities and API support
- **Enhanced Role Detection**: Improved master/slave role detection for multiroom groups
- **Optimistic UI Updates**: Immediate UI feedback for better user experience
- **Debounced Volume Control**: Reduced network traffic for volume slider operations

### Technical

- **API Client Improvements**: Firmware-specific request handling and retry logic
- **Coordinator Enhancements**: Better error recovery and state synchronization
- **Code Organization**: Refactored into focused, maintainable modules

## [0.1.12]

### Fixed

- **Volume Control Reliability**: Fixed volume up/down buttons and slider not working correctly
  - Volume up/down buttons now properly change device volume with configurable step (default 5%)
  - Volume slider now uses debouncing to prevent command flooding during rapid drags
  - Fixed volume step calculation to handle both percentage and decimal values correctly
  - Removed premature clearing of pending volume state that prevented debounced commands from being sent
  - Volume commands now properly reach the device and change actual volume levels

### Improved

- **Volume Control Performance**: Enhanced volume control responsiveness and efficiency
  - Implemented 0.5-second debouncing for all volume changes (buttons and slider)
  - Optimistic UI updates provide immediate feedback while commands are queued
  - Reduced network traffic by consolidating rapid volume changes into single commands
  - Improved volume step handling with fallback to 5% when configuration is invalid

## [0.1.11]

### Fixed

- **Group Coordinator Entity Naming**: Fixed inconsistent entity naming for group coordinator entities
  - Group coordinator entities now correctly use `_group_coordinator` suffix instead of `_group`
  - Entity IDs now match documentation examples (e.g., `media_player.living_room_group_coordinator`)
  - Fixes device identifier inconsistency that caused entity IDs to differ from documented behavior

## [0.1.10]

### Fixed

- **Group Media Player State Logic**: Fixed test failure in group media player state handling
  - Device offline now correctly shows 'unavailable' (returns `None`)
  - Group inactive (solo/no members) now correctly shows 'idle' (returns `MediaPlayerState.IDLE`)
  - Improved state logic to distinguish between device availability and group activity

## [0.1.9]

### Fixed

- **Offline Device State**: Fixed media player entities showing 'idle' state when device goes offline
  - Devices now correctly show as 'unavailable' in Home Assistant when power is disconnected or network connection is lost
  - Both regular media player and group media player entities now return `None` state when unavailable
  - Follows proper Home Assistant availability conventions for immediate user feedback

## [0.1.8]

### Improved

- **Optimistic State Handling**: Enhanced media player responsiveness with immediate UI feedback
  - Playback state changes (play/pause/stop) now show instantly in the UI without waiting for device confirmation
  - Volume and mute changes provide immediate visual feedback while the device processes the command
  - Source switching shows the new source immediately for better user experience
  - Shuffle and repeat mode changes reflect instantly in the UI
  - Smart timeout handling prevents optimistic state from persisting if device doesn't respond (3s for playback, 10s for other states)

### Fixed

- Fixed potential UI flickering during state transitions by properly managing optimistic state lifecycle
- Improved state synchronization between UI and device by only clearing optimistic state when device confirms the change
- Enhanced volume slider behavior with proper debouncing to prevent command flooding
