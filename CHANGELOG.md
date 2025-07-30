# Changelog

All notable changes to the WiiM Audio integration will be documented in this file.

## [1.0.14] - 2024-12-19

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
