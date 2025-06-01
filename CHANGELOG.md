# Changelog

All notable changes to this project will be documented in this file.

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
