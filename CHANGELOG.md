# Changelog

All notable changes to this project will be documented in this file.

## [0.4.13] - 2025-01-06

### Fixed

- **Major UX improvement: Intelligent device filtering for join/unjoin lists**
- Only WiiM devices that can actually be joined now appear in grouping interface
- Eliminated confusion from non-WiiM devices (HomePod, Sony TV, etc.) in join lists
- Slaves and active group masters no longer appear as joinable options

### Improved

- **Dynamic grouping feature enablement based on device state**
- Solo devices: ✅ Can be joined (GROUPING enabled)
- Slaves: ❌ Cannot be joined (GROUPING disabled)
- Active masters: ❌ Cannot be joined (GROUPING disabled)
- Much cleaner and more intuitive grouping interface

### Technical

- Replaced static `GROUPING` feature with dynamic `supported_features` property
- Implemented intelligent `_can_be_grouped()` logic based on device role and state
- Enhanced device state awareness for grouping operations
- Improved logging for grouping feature decisions

## [0.4.12] - 2025-01-06

### Improved

- **Enhanced join/unjoin UX in Home Assistant Actions UI**
- Virtual master entities no longer appear in join/unjoin device lists
- Cleaner device selection when creating multiroom groups
- Virtual masters already have "Master" in their names for clear identification

### Technical

- Removed `MediaPlayerEntityFeature.GROUPING` from virtual master entities
- Virtual masters represent group coordinators and shouldn't be joinable to other groups
- Reduces confusion in Home Assistant's native grouping interface

## [0.4.11] - 2025-01-06

### Fixed

- **Fixed GitHub Actions workflow shell parsing errors**
- Resolved `MEDIA_SEEK: command not found` and `hass: command not found` errors
- Fixed issue where backticks in changelog were interpreted as shell commands
- Improved changelog content escaping in release workflow

### Technical

- Enhanced GitHub Actions workflow to safely handle special characters in changelog
- Added proper environment variable usage for release notes content
- Prevented shell interpretation of markdown code blocks during release creation

## [0.4.10] - 2025-01-06

### Fixed

- **Fixed critical AttributeError during entity initialization**
- Resolved "NoneType object has no attribute 'data'" error in StateManager
- Fixed linter error with invalid `MEDIA_SEEK` feature

### Improved

- Added lazy initialization for StateManager to prevent timing issues
- Added fallback method when StateManager is unavailable during startup
- Enhanced error handling during entity initialization phase
- Better robustness during Home Assistant startup sequence

### Technical

- StateManager now initializes safely after `hass` attribute is available
- Improved entity lifecycle management during coordinator updates
- Removed invalid MediaPlayerEntityFeature that doesn't exist in current HA

## [0.4.9] - 2025-01-06

### Removed

- **Removed unnecessary "Home Assistant Grouping" configuration option**
- Simplified configuration by always enabling `MediaPlayerEntityFeature.GROUPING`

### Improved

- JOIN button and `media_player.join`/`unjoin` service calls now always available
- Cleaner configuration UI with less confusing options
- Better adherence to Home Assistant's grouping design principles

### Technical

- Home Assistant's grouping system is designed to delegate to integration methods
- No need for users to toggle basic HA functionality on/off
- Reduced configuration complexity and potential user confusion

## [0.4.8] - 2025-01-06

### Fixed

- Fixed GitHub workflow: Added missing step ID and modernized actions
- Resolved "Input required and not supplied: upload_url" error
- Updated to maintained action (softprops/action-gh-release@v2)

### Technical

- Fixed workflow orchestration issue preventing asset uploads
- Simplified asset upload process using modern GitHub Actions
- All previous fixes from 0.4.5-0.4.7 included

## [0.4.7] - 2025-01-06

### Fixed

- Resolved GitHub release workflow issue where release already existed
- Fixed persistent tag conflict in automated release process

### Technical

- Updated version to 0.4.7 to avoid existing release conflicts
- All fixes from 0.4.5 and 0.4.6 included

## [0.4.6] - 2025-01-06 (Workflow Issue)

### Fixed

- Resolved GitHub release workflow tag conflict issue
- Fixed version tag mismatch in release process

### Technical

- Updated version to 0.4.6 to resolve tag conflicts
- Cleaned up existing v0.4.5 tag for proper release workflow

## [0.4.5] - 2025-01-06 (Internal)

### Fixed

- Fixed `join_players` method to prevent `NotImplementedError` exceptions
- Improved error handling for multiroom group operations
- Added timeout protection (30s) for async operations in sync wrapper methods
- Enhanced `unjoin_player` method with better error handling

### Added

- Comprehensive documentation for resolving LinkPlay integration conflicts
- Detailed troubleshooting guide in README
- Better error logging for group operations
- Timeout protection to prevent hanging operations

### Changed

- `join_players` and `unjoin_player` methods now catch and log errors instead of raising them
- Improved async coroutine detection and execution in sync wrapper methods
- Enhanced documentation with conflict resolution strategies

### Documentation

- Added section on resolving conflicts with built-in LinkPlay integration
- Enhanced troubleshooting guide with multiple resolution options
- Added service documentation and usage examples
- Improved README structure and clarity

## [0.4.4] - 2024-12-XX

### Added

- Enhanced multiroom group management
- Improved device discovery and status parsing
- Better error handling and logging
- Added comprehensive service calls

### Changed

- Improved coordinator refresh mechanisms
- Enhanced device state management
- Better entity lifecycle management

### Fixed

- Various stability improvements
- Connection handling improvements
- Group synchronization issues

## [0.4.3] - Previous releases

### Various improvements and bug fixes in earlier versions

---

**Note**: This changelog covers recent versions. For a complete history, see the Git commit log.
