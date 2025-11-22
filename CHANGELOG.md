# Changelog

All notable changes to unified WiiM Audio integration will be documented in this file.

## [1.0.15] - 2024-11-21

### Fixed

- **CRITICAL: Position Display**: Fixed bug where position would "run away" and exceed track duration (e.g., showing 6:18 for a 4:00 track).
  - Root Cause: The "Smart Update" logic updated the position value but sometimes kept the old timestamp, causing the frontend to double-count elapsed time.
  - Fix: Ensure position and timestamp are ALWAYS updated together atomically.
- **Duration Display**: Fixed "00:00" duration issue by returning `None` when duration is 0.

## [1.0.14] - 2024-11-21

### Fixed

- **Duration Display**: Fixed "00:00" duration issue by returning `None` when duration is 0 (unknown).
- **Position Jitter**: Implemented Sonos-style "Smart Update" logic.
  - Only updates `media_position_updated_at` timestamp if reported position deviates significantly (> 1.5s) from expected position.
  - Prevents progress bar from jumping backward/forward due to network latency or polling jitter.
  - Ensures smooth playback progress on web dashboard.
- **Startup/State Transitions**: Improved handling of position updates during Play/Pause transitions and initial startup.

### Added

- **Debug Logging**: Enhanced coordinator logging to show position, duration, and play state on every poll when playing.

## [1.0.13] - 2024-11-21

### Fixed

- **Critical**: Fixed seek controls not working
  - Root cause: `supported_features` was @property accessing `self.media_duration` at wrong time
  - Solution: Update `_attr_supported_features` during coordinator update (LinkPlay pattern)
  - SEEK feature now properly enabled/disabled based on actual duration value
  - Added debug logging to track seek operations

### Technical Details

- Moved from `@property supported_features()` to `_update_supported_features()` method
- Called during coordinator update to set `_attr_supported_features`
- Base class @cached_property returns `_attr_supported_features`
- SEEK enabled when `_attr_media_duration > 0`, disabled otherwise

## [1.0.12] - 2024-11-21

### Added

- **Diagnostic logging**: Added warnings when pywiim returns invalid duration values
  - Logs position, duration, state, and title when duration is None/0 during playback
  - Helps identify root cause of "duration=00:00" web dashboard issues
  - See `DEBUGGING_DURATION_ISSUE.md` for troubleshooting guide

### Note

If you see duration showing **00:00** on the web dashboard:

1. Enable debug logging for `custom_components.wiim`
2. Look for "PyWiim returned invalid duration!" warnings in logs
3. Report to pywiim library - this indicates pywiim is not properly parsing duration from the device

## [1.0.11] - 2024-11-21

### Fixed

- **Critical**: Fixed property mutation bug causing incorrect position/duration on web dashboard
  - Moved timestamp management from property getters to coordinator update handler
  - Following LinkPlay's `_update_properties()` pattern during `_handle_coordinator_update()`
  - Properties now read `_attr` values instead of mutating state
  - Fixes web dashboard showing duration=00:00 and nonsensical position values

### Technical Details

**Root Cause**: Mutating state in property getters caused race conditions when properties were accessed multiple times during state calculation. The web dashboard would call `media_position` and `media_duration` properties repeatedly, triggering timestamp updates at wrong times.

**Solution**: Implement LinkPlay pattern - update `_attr` values during coordinator updates, properties just return those values. No mutation in getters.

## [1.0.10] - 2024-11-21

### Fixed

- **Critical**: Fixed media position display discrepancy between iOS and web dashboard
  - Implemented Home Assistant best practice: integration now manages `media_position_updated_at` timestamp
  - Following Sonos/LinkPlay pattern: timestamp updates when PLAYING, freezes when PAUSED, clears when IDLE
  - Position advancement now handled entirely by HA frontend for smooth, consistent display
  - Fixed missing `dt_util` import that caused NameError at runtime

### Changed

- **Requirements**: Updated to `pywiim>=2.1.0` (removes position estimation - HA frontend handles it)
- **Architecture**: Simplified position tracking - read raw position from pywiim, manage timestamp ourselves

### Technical Details

- Position display formula (handled by HA): `current_position = media_position + (now - media_position_updated_at)`
- Integration provides static position and timestamp; frontend calculates live position
- Eliminates competing estimation logic between pywiim and HA
- Matches standard Home Assistant integration patterns

## [1.0.9] - 2024-11-21

### 🎉 First Stable Release

This is the first stable release of the WiiM Audio integration for Home Assistant, built on the powerful `pywiim` library for reliable device communication.

**What's Included:**

- ✅ Complete media player control (play, pause, stop, volume, seek)
- ✅ Full multiroom/grouping support via pywiim
- ✅ Automatic device discovery (SSDP, Zeroconf, UPnP)
- ✅ Media position tracking with smooth progress updates
- ✅ Audio quality sensors (sample rate, bit depth, bit rate)
- ✅ 10-band EQ control and audio output mode selection
- ✅ Bluetooth device management
- ✅ Sleep timer and alarm support
- ✅ TTS (Text-to-Speech) support
- ✅ Scene restoration with EQ presets
- ✅ Comprehensive diagnostics and health monitoring
- ✅ 39% test coverage (66/73 tests passing)

**Device Info Display:**

- Hardware: Device firmware version
- Software: PyWiiM library version
- Serial Number: Device MAC address

**Supported Devices:**

- WiiM Mini, Pro, Pro Plus, Amp, Ultra
- LinkPlay-compatible devices (Arylic, Audio Pro, Dayton Audio, DOSS, etc.)

**Requirements:**

- Home Assistant 2024.12.0+
- PyWiiM library 2.0.14+

## [1.0.0-beta.8] - 2024-11-21

### Changed

- **Device Info Organization**: Reorganized version display for better clarity
  - **Hardware**: Now shows device firmware (e.g., "Linkplay 4.8.731953")
  - **Software**: Now shows pywiim library version (e.g., "pywiim 2.0.17")
  - **Serial Number**: Now shows device MAC address
  - More logical separation: hardware firmware vs software library
  - Better for support and troubleshooting

## [1.0.0-beta.7] - 2024-11-21

### Changed

- **PyWiiM Version Display**: Show pywiim version as separate line in Device Info
  - Now displays as "Hardware: pywiim 2.0.17" on its own line
  - More clear and readable than combining with firmware version
  - Easy to see at a glance for support and troubleshooting

## [1.0.0-beta.6] - 2024-11-21

### Changed

- **PyWiiM Version Display**: Moved pywiim library version to Device Info box
  - Now displays in firmware field as "Linkplay 4.8.731953 (pywiim 2.0.16)"
  - More visible and accessible than sensor attribute
  - Appears alongside device model and manufacturer information
  - Useful for quick verification of library version during support

## [1.0.0-beta.5] - 2024-11-21

### Removed

- **Update Platform**: Removed deprecated firmware update platform
  - Firmware updates should be managed through WiiM app or device web interface
  - Update platform was not reliable for tracking firmware update status
  - Reboot button documentation updated to note it applies downloaded firmware updates

### Changed

- **Bluetooth Device Update**: Refactored to synchronous operation for better reliability

  - "BT Update Paired Devices" now blocks until device list is refreshed
  - Improved error handling and state updates
  - More predictable behavior when updating paired device list

- **Reboot Button**: Enhanced documentation to clarify firmware update behavior
  - Rebooting device will apply any downloaded firmware updates
  - Clarified use cases for reboot button

### Technical

- **Code Cleanup**: Removed 1,600+ lines of unused test files and old test infrastructure
- **Platform List**: Cleaned up platform registration to remove deprecated update platform

## [1.0.0-beta.4] - 2024-11-21

### Added

- **PyWiim Library Version Sensor**: Added `pywiim_version` attribute to Device Status diagnostic sensor
  - Shows the currently loaded pywiim library version (e.g., "2.0.16")
  - Useful for support and troubleshooting
  - Helps identify version-specific issues
  - Located in diagnostic sensor attributes alongside firmware versions

### Technical

- **Version Tracking**: Gracefully handles missing `__version__` attribute with fallback to "unknown"
- **Diagnostic Enhancement**: Better visibility into integration and library versions for debugging

## [1.0.0-beta.3] - 2024-11-21

### Fixed

- **Media Position and Seek**: Fixed media position tracking and seek functionality
  - Added missing `media_position_updated_at` property to both media player entities
  - Home Assistant now correctly tracks playback position with smooth progress bar updates
  - Seek controls now work properly with pywiim's position estimation system
  - Position updates every second during playback using pywiim's hybrid approach (HTTP polling + UPnP events + position estimation)
  - Fixed issue where progress bar would appear frozen during playback

### Technical

- **Position Tracking**: Properly converts pywiim's Unix timestamp to datetime objects for Home Assistant
- **Error Handling**: Added validation for malformed timestamps from pywiim
- **Integration Compliance**: Follows Home Assistant patterns used by Sonos, Cast, and other media player integrations

## [1.0.0-beta.2] - 2024-11-21

### Fixed

- **Discovery Filtering**: Fixed already-configured devices appearing in the discovered devices list
  - SSDP, Zeroconf, and integration discovery now check if devices are already configured BEFORE validation
  - Prevents duplicate discovery notifications for devices that are already set up
  - Improves user experience by showing only truly new devices

### Added

- **Automatic Slave Discovery**: When adding a master device with slaves, the integration now automatically discovers and prompts to add the slave devices
  - Queries master device for its slave list after adding
  - Triggers discovery flows for any unconfigured slaves
  - Works even when slaves don't broadcast SSDP/Zeroconf (because they're in slave mode)
  - Non-invasive: slaves can be added without unjoining the group
  - Ensures all devices in a multiroom setup are easily discovered and configured

## [0.3.0] - 2025-11-17

### Changed

- **Major Refactor**: Migrated all device communication logic to standalone `pywiim` package
  - Integration now acts as a thin wrapper between Home Assistant and `pywiim` library
  - All HTTP API communication, UPnP handling, and device logic moved to `pywiim>=1.0.57`
  - Improved maintainability and separation of concerns
  - No functional changes for users - all features remain the same
  - Better code organization: HA-specific code in integration, device logic in `pywiim`

### Removed

- Internal API module (replaced by `pywiim` package)
- Temporary testing documentation files

### Developer Notes

- Integration now requires `pywiim>=1.0.57` package (automatically installed)
- See `development/HA_INTEGRATION_GUIDE.md` for integration patterns with `pywiim`
- All device communication now goes through `pywiim.WiiMClient` and `pywiim.Player` classes

## [0.2.28] - 2025-11-13

### Fixed

- **Scene Restoration with EQ Presets**: Fixed scene restoration failing when restoring media player state with EQ presets on devices that don't support EQ or return invalid JSON responses
  - `async_select_sound_mode` now checks if EQ is supported before attempting to set it
  - Gracefully handles empty/invalid JSON responses for EQ commands (similar to reboot commands)
  - Scene restoration continues even if EQ preset setting fails, allowing other attributes to be restored
  - Resolves GitHub issue #108 where scene restoration failed with "Invalid JSON response" error on UP2STREAM_PRO_V3 devices

## [0.2.27] - 2025-11-12

### Added

- **Enhanced Debug Logging**: Added debug logging for HTTP API responses, mode-to-source mapping, and UPnP state merge decisions

### Fixed

- **UPnP State Merging**: Fixed stale UPnP state overwriting valid HTTP state when subscriptions fail
  - Only merges critical fields (play_state, source) when UPnP is healthy
  - Validates artwork URLs before merging
- **Audio Pro HTTP Play State**: Fixed incorrect assumption - original Audio Pro devices DO provide HTTP play_state (only MkII requires UPnP)

## [0.2.26] - 2025-11-12

### Fixed

- **Legacy Audio Pro Playback State**: Fixed original Audio Pro devices incorrectly preserving UPnP play_state when HTTP API provides it
- **Arylic Source Selection**: Fixed source selection for Arylic devices by properly handling hyphen format variants (e.g., "line-in")

## [0.2.25] - 2025-11-07

### Fixed

- **Audio Pro Metadata and Playback State**: Fixed Audio Pro devices showing "Idle" state and no metadata when playing via WiiM app
  - HTTP polling now preserves UPnP metadata (title, artist, album, artwork) when HTTP API doesn't provide it
  - HTTP polling now preserves UPnP playback state when HTTP API doesn't provide it
  - Critical for Audio Pro devices playing via WiiM app - HTTP API doesn't return metadata or play_state, but UPnP events do contain it
  - Follows same pattern as volume preservation for Audio Pro devices
  - Resolves GitHub issue #101 where Audio Pro speakers showed "Idle" state and no metadata when playing via WiiM app

## [0.2.24] - 2025-11-10

### Changed

- **Join/Unjoin Flow**: Simplified group join and unjoin operations for better stability

  - Virtual group master now enables/disables immediately (optimistic update)
  - Slaves wait for device to confirm role before updating (prevents conflicts with polling)
  - Removed retry logic and manual state manipulation - let device state flow naturally
  - Metadata clears immediately on unjoin for instant UI feedback
  - Eliminates flickering and state conflicts between optimistic updates and polling

- **UPnP Health Checking**: Removed unreliable UPnP health detection
  - Events only occur on state changes, making health detection unreliable
  - Polling interval now always uses fast polling (1s) when playing, regardless of UPnP status
  - UPnP events supplement HTTP polling but don't replace it (following DLNA DMR pattern)

### Added

- **Diagnostics Enhancements**: Added comprehensive statistics tracking
  - HTTP polling statistics: total polls, success rate, response times, failure tracking
  - Command statistics: total commands, success rate, failure tracking
  - All statistics available in device diagnostics for troubleshooting

## [0.2.23] - 2025-11-09

### Changed

- **UPnP Subscription Handling**: Refactored to follow DLNA DMR pattern from Home Assistant core

  - Replaced pessimistic `_subscriptions_failed` flag with optimistic `check_available` flag
  - Trusts `auto_resubscribe=True` to recover from temporary failures
  - HTTP polling and UPnP now work cooperatively rather than one being authoritative
  - Enhanced diagnostic logging and improved diagnostics to show `check_available` and `upnp_working` status

- **UPnP Health Tracking**: Added health monitoring based on event arrival

  - New `is_upnp_working()` method tracks recent events (within 5 minutes)
  - Adaptive polling: 5 seconds when UPnP working, 1 second when playing without UPnP, 5 seconds when idle

- **State Merging**: Simplified UPnP state merging logic
  - Always merges UPnP state when available
  - Audio Pro devices rely on UPnP for player state (HTTP doesn't provide it)
  - Other devices use HTTP for state, UPnP for real-time optimization

### Fixed

- **Adaptive Polling**: Fixed test failure by properly mocking UPnP health check

## [0.2.22] - 2025-11-09

### Fixed

- **Audio Pro Metadata Display**: Fixed metadata not showing when playing music via WiiM app on Audio Pro speakers

  - Prevents empty metadata events from clearing existing metadata during track transitions
  - Metadata is now preserved when device is playing/transitioning, only cleared when truly stopped/idle
  - Fixes issue where metadata would disappear during track changes when playing from WiiM app
  - Resolves issue #101 where Audio Pro speakers showed "Idle" state and no metadata when playing via WiiM app
  - UPnP metadata events are now properly filtered to prevent premature clearing during playback

## [0.2.21] - 2025-11-09

### Fixed

- **UPnP Resubscription Failure Handling**: Fixed playback state remaining idle and metadata not updating when UPnP subscriptions fail

  - Detects UPnP resubscription failures (empty state_variables) and marks subscriptions as failed
  - HTTP polling now becomes authoritative when UPnP subscriptions fail, ensuring state updates correctly
  - Prevents stale UPnP state from overwriting correct HTTP polling state
  - Auto-recovers when UPnP subscriptions resume working
  - Following DLNA DMR pattern from Home Assistant core for proper fallback behavior
  - Resolves issue #103 where DLNA and Spotify sources showed idle state even when playing
  - Fixes metadata (title/artist/album) not updating for DLNA and Spotify sources when UPnP fails

## [0.2.20] - 2025-11-09

### Fixed

- **DLNA Source Detection**: Fixed missing source attribute during DLNA playback

  - Improved mode-to-source mapping logic to handle cases where API returns mode but not source field
  - Source is now correctly derived from mode value when source field is missing, None, or invalid
  - Resolves issue #104 where DLNA playback (mode="2") was not showing correct source
  - Added debug logging to trace mode-to-source mapping for troubleshooting

- **Audio Pro Volume State**: Improved volume handling for Audio Pro devices
  - Audio Pro devices now exclude volume from HTTP polling immediately when UPnP is subscribed
  - Prevents HTTP polling from setting volume to None on Audio Pro devices (which don't provide volume via HTTP API)
  - Volume state now properly preserved from UPnP for Audio Pro devices

### Added

- **Ultra Headphone Out Support**: Added support for Headphone Out mode on WiiM Ultra devices
  - Ultra devices can now select "Headphone Out" as an audio output mode (hardware=4, source=0)
  - Automatically disconnects Bluetooth when switching to Headphone Out mode
  - Headphone Out option only appears for Ultra devices (only device with headphone jack)
  - Resolves issue #86 for proper Ultra device audio output mode handling

## [0.2.19] - 2025-11-08

### Fixed

- **Resume Playback**: Fixed play command restarting tracks when paused by using resume() API endpoint
  - Play button now properly resumes from current position when device is paused
  - Added play/pause toggle support with proper resume functionality
- **Audio Pro Volume State**: Fixed volume showing as unavailable on Audio Pro devices after UPnP subscription
  - Requests initial UPnP state immediately after subscription for immediate volume availability
  - Prevents volume appearing as "Unavailable" during startup
- **Audio Pro URL Playback**: Fixed relative URL playback failures on Audio Pro devices
  - Media source URLs now properly converted to absolute URLs for Audio Pro compatibility
  - Applies to TTS, media sources, and direct URL playback

## [0.2.18] - 2025-11-07

### Fixed

- **EQ Endpoint Migration**: Fixed EQ information retrieval by migrating from non-existent `getEQ` endpoint to `EQGetBand`
  - Updated endpoint constant to use correct `EQGetBand` command
  - Enhanced response parsing to handle `Name` and `EQStat` fields from EQGetBand response
  - Updated error messages and documentation to reflect correct endpoint usage

## [0.2.17] - 2025-11-07

### Fixed

- **State & Status Reporting for Older Audio Pro Devices**: Fixed issue where older Audio Pro LinkPlay-based speakers showed incorrect playback state and volume information
  - Audio output API (`getNewAudioOutputHardwareMode`) is now only called on devices that support it
  - Capability detection properly identifies devices that don't support this endpoint
  - Prevents repeated API failures that were causing state updates to fail
  - Resolves issues #97 and #98 where devices appeared as `idle` when playing and volume showed as `Unavailable`
  - Improved exception handling to catch all error types including `WiiMConnectionError` with JSON parsing errors

## [0.2.16] - 2025-11-06

### Fixed

- **Media Source Integration**: Fixed Home Assistant warning about missing `entity_id` parameter in `media_source.async_resolve_media()` call
  - Now properly passes `entity_id` parameter when resolving media sources
  - Resolves Home Assistant frame helper warning about deprecated API usage
  - Ensures compatibility with current Home Assistant media source requirements

## [0.2.15] - 2025-11-06

### Fixed

- **Source Selection Bug**: Fixed issue where source selection from the media player entity UI was not working
  - Source selection now correctly uses the exact API source name from the device's `input_list` when available
  - Ensures proper mapping between friendly display names and device API source IDs
  - Falls back to reverse mapping from SOURCE_MAP if input_list is not available
  - Resolves issue #95 where users could select sources but the device wouldn't change

## [0.2.14] - 2025-11-06

### Added

- **Phono Input Support**: Added Phono input source support for WiiM Ultra devices

  - Phono input now appears in source selection dropdown
  - Proper source mapping for phono/phono_in API values

- **Headphone Out Support**: Added Headphone Out audio output mode (mode 0) for WiiM Ultra

  - Headphone Out option available in audio output mode select entity
  - Mode value verification pending (see Issue #86)

- **Input List Tracking**: Enhanced device info tracking with input_list field

  - Devices now track available input sources from API
  - Enables future dynamic source list generation based on device capabilities

### Changed

- **Code Cleanup**: Reduced excessive debug logging throughout codebase

  - Removed verbose debug logs from volume control, playback commands, and media controller
  - Cleaned up formatting and improved code readability
  - Reduced log noise while maintaining essential error logging

### Technical

- **Media Controller**: Enhanced `_fetch_media_image()` to handle local static files
- **Device Info Model**: Added `input_list` field to DeviceInfo Pydantic model
- **Constants**: Added Phono source mapping and Headphone Out mode to constants
- **Test Cleanup**: Removed redundant test code and improved test structure

## [0.2.13] - 2025-11-05

### Added

- **Bluetooth Device Selection in Audio Output Mode**: Integrated Bluetooth device selection directly into the Audio Output Mode select entity
  - Shows all previously paired Bluetooth devices as selectable options (e.g., "BT Device 1 - TOZO-T6")
  - Automatically fetches Bluetooth device history at startup for immediate availability
  - Includes "BT Update Paired Devices" option to manually refresh the list after pairing new devices via WiiM app
  - No constant polling - only fetches when needed or when Bluetooth output is active

### Changed

- **Bluetooth Polling Optimization**: Reduced unnecessary Bluetooth history polling
  - History fetched once at startup (for dropdown population)
  - Only polls when Bluetooth output is active (to track connected device)
  - Manual refresh available via "BT Update Paired Devices" option

## [0.2.12] - 2025-11-04

### Changed

- **Media Browser Filtering**: Enhanced media browser to automatically filter out non-audio content
  - Added content filter to show only audio-compatible media types in the browser
  - Video and other non-audio media types are now automatically excluded
  - Uses Home Assistant's native content_filter API for proper media source filtering
  - Improved media library browsing with direct source access for DLNA and other media sources
  - Better handling of media-source:// URLs using proper Home Assistant API

## [0.2.11] - 2025-10-31

### Changed

- **Enhanced Diagnostic Logging**: Added comprehensive INFO/WARNING level logging for volume control and media browsing
  - Volume commands now log at INFO level with speaker name, volume percentage, and step changes
  - API volume requests log endpoint URLs and device hosts
  - Media browser operations log content types and IDs for troubleshooting
  - All errors include full exception details and stack traces for better debugging
  - Helps diagnose issues when volume control or media browsing has no effect

## [0.2.10] - 2025-10-31

### Fixed

- **Media Browser**: Fixed issue where media library showed no items when selecting WiiM speaker

  - Improved media source detection to properly show Media Library entry even when children are initially empty
  - Lookup now checks `can_expand` property to determine if media sources are browsable

- **Playback Control**: Fixed play button restarting song when already playing
  - Added state check before sending play command - if device is already playing, command is skipped
  - Triggers refresh to get latest metadata/position when already playing (helps with external app playback)
  - Prevents song restart when user presses play while music is already playing

### Changed

- **State Detection**: Simplified playback state detection logic

  - Removed metadata-based assumptions about playing state
  - Now uses only documented API states: "play", "pause", "stop", "load", "idle"
  - Handles common variations: "playing", "paused", "stopped"
  - More reliable and consistent with actual API responses

- **Multiroom UI Responsiveness**: Improved multiroom group UI updates with immediate refresh triggers
  - When creating or dissolving multiroom groups via Home Assistant, all affected devices now trigger immediate coordinator refreshes
  - Role changes (master/slave/solo) now appear in UI almost instantly instead of waiting up to 30 seconds for next poll cycle
  - Added debug logging to track refresh triggers with graceful error handling

### Technical

- **Code Quality**: Fixed linting issues (removed unused imports, sorted imports)

## [0.2.1] - 2025-10-30

### Fixed

- **Audio Output Mode Select Entity**: Fixed capability detection for audio output mode control
  - Added `capabilities` property to `WiiMClient` to properly expose device capabilities
  - Resolves issue where audio output select entity was greyed out/unavailable
  - Ensures WiiM devices are properly detected and audio output control is enabled
  - Affected GitHub issue: #79

## [0.2.0] - 2025-10-30

### Added

- **UPnP Event System**: Real-time device state updates via UPnP DLNA DMR eventing

  - Automatic subscription to AVTransport and RenderingControl UPnP services
  - Instant state updates when device state changes (play/pause/volume/mute)
  - Follows Home Assistant patterns (Samsung TV, DLNA DMR) using `async_upnp_client`
  - Automatic resubscription with health monitoring and diagnostics
  - Reduces polling frequency while improving responsiveness
  - Works with WiiM Pro, Mini, Amp, and compatible LinkPlay devices

- **UPnP Health Monitoring**: New diagnostic sensor for UPnP event health

  - Shows UPnP push health status (healthy/degraded/unavailable)
  - Tracks event counts and last notification timestamps
  - Helps diagnose UPnP connectivity issues
  - Available in device diagnostics

- **UPnP Testing Tools**: Comprehensive diagnostic script for UPnP support verification
  - Test UPnP description.xml accessibility
  - Verify AVTransport and RenderingControl service availability
  - Validate UPnP eventing capability before enabling feature
  - Located at `scripts/test_upnp_description.py`

### Changed

- **Polling Strategy**: Optimized polling intervals with UPnP event system

  - Basic device status: 30 seconds (down from 15) when UPnP is healthy
  - Device info: 120 seconds (unchanged)
  - Multiroom status: 30 seconds (unchanged)
  - Falls back to aggressive polling if UPnP becomes unhealthy
  - Reduces network traffic while maintaining responsiveness

- **Sensor Platform**: Enhanced sensor filtering and capability detection
  - Role sensor always created (essential for multiroom understanding)
  - Input sensor always created (commonly used)
  - Bluetooth output sensor only created when device supports it
  - Audio quality sensors only created when metadata endpoint is available
  - Diagnostic sensor always available for troubleshooting
  - Firmware sensor always created for support purposes

### Technical

- **UPnP Architecture**: Modular implementation following HA core patterns

  - `upnp_client.py` - UPnP client wrapper for `async_upnp_client`
  - `upnp_eventer.py` - Event subscription manager with health tracking
  - `state.py` - State management with UPnP event integration
  - Clean separation of concerns with proper error handling

- **Event Processing**: Efficient LastChange XML parsing

  - Parses AVTransport and RenderingControl XML notifications
  - Extracts play state, volume, mute, track info from events
  - Dispatcher-based state updates to media player entities
  - Handles subscription renewals and resubscription failures gracefully

- **Capability Detection**: Smart sensor creation based on device capabilities
  - Checks coordinator capabilities for audio output support
  - Validates metadata endpoint availability before creating quality sensors
  - Graceful fallback when capability detection fails
  - Reduces entity clutter for devices without features

### Documentation

- **UPnP Testing Guide**: Added comprehensive UPnP testing documentation

  - Step-by-step verification process
  - Diagnostic script usage examples
  - Troubleshooting common UPnP issues
  - Located at `development/UPNP_TESTING.md`

- **Polling Strategy**: Updated polling documentation with UPnP integration
  - Documented adaptive polling based on UPnP health
  - Explained fallback behavior when UPnP unavailable
  - Located at `development/POLLING_STRATEGY.md`

## [0.1.46] - 2025-01-27

### Fixed

- **Audio Pro Client Certificate Loading**: Fixed critical bug preventing Audio Pro devices (A15 MkII, etc.) from connecting
  - Client certificate was never being loaded due to incorrect API usage (`load_cert_chain()` doesn't accept `cadata` parameter)
  - Certificate now properly loaded from temporary file for mutual TLS authentication
  - Audio Pro devices requiring client certificate on port 4443 now connect successfully
  - Improved logging to INFO/WARNING level so certificate loading issues are visible

### Changed

- **Enhanced SSL Certificate Logging**: Certificate loading now logs at INFO level with clear success/failure indicators

## [0.1.45] - 2025-10-28

### Fixed

- **Audio Pro Discovery Bug**: Fixed critical bug preventing Audio Pro devices from being discovered
  - Fixed conditional logic where Audio Pro devices with failed validation were rejected instead of offering manual setup
  - Corrected recognition of a real UUID versus host IP address fallback
  - Devices that fail validation now properly detected and handled per device type
  - Resolves GitHub issue #80

### Testing

- **Discovery Flow Coverage**: Added comprehensive test suite for zeroconf/SSDP discovery (15 new tests)
  - Tests cover successful discovery, failed validation, Audio Pro handling, and edge cases
  - Config flow coverage improved from 10% to 31%
  - Tests prevent regression of Audio Pro discovery issues

### Fixed

- **Setup Retry Log Noise**: Reduced excessive error logging for persistent connection failures during initial setup
  - Added smart logging escalation that reduces log levels for repeated setup retries
  - First 2 attempts log at WARNING level (normal to see)
  - Next 2 attempts (3-4) log at DEBUG level (reduce noise)
  - After 4+ attempts log at ERROR level (device likely offline)
  - Tracks retry count across Home Assistant's automatic retry mechanism
  - Successfully resolves GitHub issue: "most stubborn speaker in the world"
  - Addresses repeated "Failed to communicate with [IP]" error messages during setup

### Testing

- **Setup Retry Testing**: Added test to verify logging escalation works correctly

  - Ensures logging levels adjust properly for multiple consecutive retry attempts
  - Prevents regression of log spam issue in the future

- **Capability Detection Retry**: Reduced logging noise during capability detection failures
  - Same smart escalation applies to device capability detection phase
  - Prevents repeated WARNING messages for devices that fail to connect during discovery

## [0.1.44] - 2025-10-27

### Fixed

- **Audio Output Entity Access**: Fixed capability detection for audio output entities
  - Corrected access to device capabilities (coordinator vs client)
  - WiiM devices now properly maintain audio output support even when API probes fail
  - Prevents greyed-out audio output entities on unsupported devices
  - Ensures proper audio output control on supported devices

## [0.1.43] - 2025-10-27

### Fixed

- **Audio Pro Connectivity Regression**: Fixed protocol/port mismatch in fallback logic
  - Corrected HTTPS/HTTP port assignments (HTTPS on 443/4443/8443, HTTP on 80/8080)
  - Resolves "Cannot connect to host" errors after primary connection attempts fail
  - Addresses GitHub issue #80

## [0.1.42] - 2025-10-26

### Fixed

- **Audio Pro MkII Initial Connection**: Fixed discovery failing to connect to Audio Pro MkII devices
  - Speculative port 4443 discovery with client certificate during initial setup
  - Resolves "Failed to communicate" errors on first connection

## [0.1.41] - 2025-01-27

### Added

- Unofficial API services (Bluetooth scan, channel balance, SPDIF delay, LMS, touch buttons)
- Channel balance number entity (`number.*_channel_balance`)

### Fixed

- Audio Pro connectivity: add HTTPS 8443 fallback, attempt client cert mTLS on 4443, and auto-fallback from `getPlayerStatusEx` to `getStatusEx`

### Technical

- Improved validation/logging and concise service schemas

## [0.1.40] - 2025-10-26

### Fixed

- **Group Media Player Image Fetching**: Fixed ImportError when fetching media images for group coordinator entities
  - Changed import from non-existent `MediaControllerMedia` to correct `MediaPlayerController` class
  - Group media player now properly delegates to MediaPlayerController for image fetching

## [0.1.39] - 2025.10.26

### Added

- **Unofficial API Endpoints Support**: Added support for reverse-engineered WiiM HTTP API endpoints

  - Bluetooth device scanning and discovery
  - Audio settings (SPDIF sample rate, channel balance)
  - Squeezelite/Lyrion Music Server (LMS) integration
  - Touch button controls and alternative LED methods
  - All endpoints clearly marked as unofficial and may not work on all firmware versions

- **New Home Assistant Services**:
  - `wiim.scan_bluetooth` - Scan for nearby Bluetooth devices
  - `wiim.set_channel_balance` - Adjust left/right channel balance
  - `wiim.set_spdif_delay` - Set SPDIF sample rate switch delay
  - `wiim.discover_lms_servers` - Search for LMS servers on network
  - `wiim.connect_lms_server` - Connect to Lyrion Music Server
  - `wiim.set_auto_connect_lms` - Enable/disable LMS auto-connect
  - `wiim.set_touch_buttons` - Enable/disable device touch buttons

### Fixed

- **Audio Pro MkII Support**: Added full support for Audio Pro MkII devices (A10 MkII, A15 MkII, A28, C10 MkII)
  - Client certificate authentication (mTLS) on port 4443
  - Automatic protocol/port detection (4443 → 8443 → 443)
  - API endpoint fallbacks for limited command set
  - Generation-specific capability profiles

### Documentation

- **Unofficial API Documentation**: Added comprehensive documentation for reverse-engineered endpoints
- **Service Examples**: Added automation examples for new services in user guide
- **Safety Warnings**: Clear warnings about firmware compatibility and testing requirements

### Technical

- **Modular API Architecture**: Extended the mixin-based API architecture with new modules (BluetoothAPI, AudioSettingsAPI, LMSAPI, MiscAPI)
- **Audio Pro Response Handling**: Added generation-aware response validation and normalization
- **Device Capability Detection**: Enhanced firmware capability detection for Audio Pro devices
- **Error Handling**: Improved error handling with proper WiiM-specific exceptions
- **Code Quality**: Enhanced linting compliance and consistent code style

## [0.1.38] - 2025.10.25

### Fixed

- **Audio Pro Device Discovery**: Enhanced discovery and validation for Audio Pro devices

  - Added graceful fallback for Audio Pro devices that fail auto-discovery validation
  - Improved protocol prioritization (HTTPS first for MkII/W-Series devices)
  - Enhanced error messages and user guidance for Audio Pro device setup

- **Player Status Sync**: Fixed player status updates when controlled by external apps
  - Improved detection of playback state changes from WiiM/Audio Pro mobile apps
  - Enhanced polling to capture status changes from external control sources

## [0.1.37] - 2025.01.27

### Fixed

- **Code Quality**: Improved linting compliance and code organization
  - Fixed assert statements in test files
  - Removed unused imports and variables
  - Organized import statements across test files
  - Reduced linting errors from 79 to 53 (ruff) and 31 to 17 (flake8)

## [0.1.35] - 2025.10.24

### Added

- **Enhanced Audio Pro Support**: Comprehensive compatibility for Audio Pro MkII and W-Generation devices
  - Automatic protocol detection (HTTP/HTTPS) based on device generation
  - Enhanced response validation for Audio Pro specific API variations
  - Generation-aware optimizations (MkII, W-Generation, Original)
  - Improved device naming and validation feedback

### Fixed

- **Discovery Improvements**: Enhanced device discovery and validation
  - Better handling of Audio Pro devices during initial setup
  - Improved error messages for connection validation failures
  - Enhanced device capability detection for newer Audio Pro models

### Technical

- **Protocol Priority System**: Smart HTTPS/HTTP ordering based on device capabilities
- **Audio Pro Response Handling**: Enhanced parsing for Audio Pro API variations
- **Generation Detection**: Automatic Audio Pro generation detection for optimized settings
- **Enhanced Logging**: Clear Audio Pro specific validation and error messages

## [0.1.34] - 2025.10.23

### Fixed

- **Discovery and Validation**: Enhanced device discovery and connection validation
  - Improved error handling for Audio Pro devices during setup
  - Better validation feedback for connection issues
  - Enhanced device capability detection

### Technical

- **Protocol Detection**: Improved HTTP/HTTPS protocol detection for Audio Pro devices
- **Error Handling**: Enhanced error messages and validation feedback

## [0.1.33] - 2025-10-23

### Fixed

- **IPv6 Port Parsing**: Fixed IPv6 address parsing with ports in brackets format `[2001:db8::1]:8080`
- **Discovery Improvements**: Enhanced device discovery and validation for Audio Pro devices

### Technical

- **IPv6 Support**: Improved IPv6 address handling in WiiMClient constructor
- **Protocol Detection**: Enhanced HTTP/HTTPS protocol detection for Audio Pro devices

## [0.1.32] - 2025-10-23

### Added

- **Enhanced Device Validation**: Multi-protocol fallback system (HTTPS:443 → HTTPS:4443 → HTTP:80 → HTTP:8080)
- **Audio Pro MkII Support**: Added compatibility for A10 MkII, A15 MkII, A28, and C10 MkII models
- **Improved Discovery**: Enhanced zeroconf, SSDP, and integration discovery with better error handling

### Fixed

- **Validation Failures**: Devices that fail auto-validation are now offered for manual setup instead of being rejected
- **Protocol Compatibility**: Better handling of devices with non-standard HTTP/HTTPS configurations
- **Error Logging**: More detailed logging to help troubleshoot connection issues

### Technical

- **Graceful Degradation**: Enhanced error handling matches python-linkplay library's robust approach
- **Legacy Device Detection**: Improved firmware capability detection for newer Audio Pro models

## [0.1.31] - 2025-01-22

### Fixed

- **Auto Release Workflow**: Fixed version detection issue that was preventing releases from being created

## [0.1.30] - 2025-01-22

### Added

- **GitHub Star Request**: Added prominent call-to-action in README for users to star the repository

## [0.1.29] - 2025-01-22

### Added

- **Audio Output Mode Control**: Added comprehensive audio output mode selection and monitoring
  - **Audio Output Mode Select**: New select entity for controlling hardware output modes
  - **Output Modes**: Line Out, Optical Out, Coax Out, Bluetooth Out
  - **Bluetooth Output Status**: Sensor showing when Bluetooth output is active
  - **Audio Cast Status**: Sensor showing when audio cast mode is active
  - **Real-time Monitoring**: 15-second polling for output status updates
  - **Automation Support**: Full automation and script integration for output switching
  - **Device Compatibility**: Works with WiiM Amp and other devices with multiple output options

### Fixed

- **Source Field Display**: Fixed blank "Source" field in Home Assistant media player UI

  - **Apple Music Support**: Added proper mapping for Apple Music streaming service
  - **Source Mapping**: Streaming services (AirPlay, Spotify, Apple Music, etc.) now show their actual service names in the UI instead of generic "Ethernet"
  - **UI Consistency**: Source dropdown now shows only physical input sources (Bluetooth, Line In, Optical, etc.) - network streaming services are handled automatically
  - **Media Content Source**: Implemented `media_content_source` property for streaming service identification

- **Audio Output Mode Stability**: Fixed audio output mode constantly changing from "Line Out" to blank

  - **Polling Optimization**: Improved 15-second polling interval for audio output status
  - **Data Flow**: Fixed audio output data propagation from API to status model
  - **Error Handling**: Added robust error handling for test environments and production

- **Source List Restoration**: Restored all previously supported input sources
  - **Complete Source List**: Re-added Coaxial, HDMI, ARC, USB, and Line In 2 to selectable sources
  - **User Experience**: Maintains compatibility with existing automations and configurations
  - **Device Support**: Full support for all WiiM device input types

### Technical

- **API Integration**: Added `getNewAudioOutputHardwareMode` and `setAudioOutputHardwareMode` API endpoints
- **Output Mode Mapping**: Proper mapping between API values and user-friendly mode names
- **Status Propagation**: Audio output data integrated into device status model
- **Entity Architecture**: New select platform entity for output mode control
- **Sensor Enhancement**: Additional sensors for Bluetooth and audio cast status monitoring
- **Polling Optimization**: Efficient 15-second polling interval for output status updates
- **Source System**: Enhanced two-layer source system (Input/Connection + Service/Content)
- **Code Quality**: Removed temporary debugging code, improved error handling, and enhanced test compatibility

## [0.1.27] - 2025-01-15

### Fixed

- **Critical NAS Duration Display Issue**: Fixed incorrect song length display when playing from NAS sources
  - Root cause was `media_position_updated_at` returning `float` (Unix timestamp) instead of `datetime.datetime` object
  - Home Assistant's optimistic playback time calculations require proper datetime objects to function correctly
  - Duration now displays correctly during both playback and pause states for NAS sources
  - Fixed by converting Unix timestamps to datetime objects using `utc_from_timestamp()`
  - Addresses GitHub issue #77: Song Length Wrong from NAS

### Technical

- **Data Type Compliance**: `media_position_updated_at` now returns proper `datetime.datetime | None` type
- **Timestamp Conversion**: Added proper Unix timestamp to datetime conversion for Music Assistant compatibility
- **Code Cleanup**: Removed unnecessary duration tracking workaround code that was added to try to fix the wrong problem
- **Architecture Compliance**: Follows established Home Assistant patterns used by other integrations (Sonos, Cast, Bang & Olufsen)

## [0.1.24] - 2025-10-15

### Added

- **Audio Quality Sensors**: Added comprehensive audio quality monitoring sensors
  - **Audio Quality Sensor**: Consolidated sensor showing sample rate, bit depth, and bit rate
  - **Sample Rate Sensor**: Individual sensor for current track's sample rate (Hz)
  - **Bit Depth Sensor**: Individual sensor for current track's bit depth (bits)
  - **Bit Rate Sensor**: Individual sensor for current track's bit rate (kbps)
  - Sensors automatically detect and display audio quality information from getMetaInfo API
  - Only created for devices that support metadata (getMetaInfo endpoint)
  - Provides detailed audio specifications for audiophiles and technical users
  - Addresses GitHub issue #78: Metadata Info sensors request

### Technical

- **Metadata Processing**: Enhanced TrackMetadata model with audio quality fields
- **Field Extraction**: Added robust audio quality field extraction from getMetaInfo responses
- **Sensor Architecture**: Integrated audio quality sensors into existing sensor platform
- **Device Compatibility**: Graceful handling of devices without metadata support

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
