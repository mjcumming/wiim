# Changelog

All notable changes to the WiiM Audio (LinkPlay) integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-01-XX

### 🎉 Major Features Added

#### User Experience Improvements

- **User-Controlled Group Entities**: Group entities are now optional and user-controlled per device
  - No more automatic creation of confusing group entities
  - Enable via device options: "Create a master group entity for this device"
  - Group entities only appear when device is actually master with slaves
- **Proper Device Organization**: Fixed group entities attaching to correct master device
  - No more separate "WiiM Group 192.168.1.68" device entries
  - Group entities now appear under the master device where they belong
- **Improved Entity Names**: Better entity naming conventions
  - Device names use friendly names from WiiM app instead of IP addresses
  - Clearer entity descriptions and help text

#### Documentation Overhaul

- **Professional Documentation**: Complete documentation rewrite with user-focused guides
  - Comprehensive installation guide with troubleshooting
  - Detailed multiroom setup guide with examples
  - Features showcase with all capabilities
  - Professional README with badges and proper structure
- **HACS Integration**: Proper HACS configuration for easy installation
  - `hacs.json` with proper metadata
  - LinkPlay branding alignment with Home Assistant standards
  - Quality scale: Gold tier integration

#### Enhanced Reliability

- **Session Error Recovery**: Fixed "Session is closed" RuntimeError
  - Automatic session recreation and retry logic
  - Graceful handling of Home Assistant restarts during playback
  - Better network interruption recovery
- **Improved Config Flow**: Enhanced device discovery and setup
  - Better error handling during device validation
  - Fixed linter errors and improved code quality
  - More reliable auto-discovery with fallback options

### 🛠️ Technical Improvements

- **Manifest Updates**: Aligned with Home Assistant standards

  - Updated branding to reference LinkPlay compatibility
  - Proper icon usage (`mdi:speaker-multiple`)
  - Quality scale designation
  - Correct dependency specifications

- **Code Quality**: Fixed linter warnings and improved maintainability
  - Resolved variable initialization issues in config flow
  - Better error handling throughout codebase
  - Improved type hints and documentation

### 📖 Documentation

- **Installation Guide** (`docs/installation.md`): Step-by-step setup instructions
- **Multiroom Guide** (`docs/multiroom.md`): Complete multiroom management guide
- **Features Guide** (`docs/features.md`): Comprehensive feature documentation
- **Troubleshooting Guide** (`docs/troubleshooting.md`): Common issues and solutions
- **Professional README**: Marketing-quality documentation with feature showcase

### 🔧 Configuration Changes

- **Device Options Enhanced**:
  - "Create a master group entity for this device" - Controls group entity creation
  - Clear descriptions and help text for all options
  - Better UI organization and user guidance

### 🐛 Bug Fixes

- **Group Entity Issues**:

  - Fixed group entities appearing under wrong device
  - Resolved entity naming confusion
  - Corrected device attachment for group players

- **Session Management**:

  - Fixed RuntimeError: "Session is closed" during HA restarts
  - Improved connection stability and recovery
  - Better handling of network interruptions

- **Config Flow**:
  - Fixed linter errors in discovery code
  - Improved variable initialization
  - Better error handling for edge cases

### ⚠️ Breaking Changes

- **Group Entity Behavior**: Group entities are no longer created automatically

  - **Migration**: Users wanting group entities must enable them per device in options
  - **Benefit**: Cleaner default setup with optional advanced features

- **Device Organization**: Group entities now attach to master device instead of creating separate devices
  - **Migration**: Existing group entities may need to be reconfigured
  - **Benefit**: Proper entity organization under correct devices

---

## [0.1.1] - 2024-12-XX

### 🐛 Bug Fixes

- **Documentation**: Removed broken documentation URL from manifest

  - Temporary fix to prevent users from seeing template repository
  - Professional documentation planned for next release

- **Error Handling**: Improved error messages during device setup
  - Better validation of device connectivity
  - Clearer error messages for troubleshooting

### 🔧 Maintenance

- **Code Cleanup**: Minor code improvements and comment updates
- **Logging**: Enhanced debug logging for troubleshooting

---

## [0.1.0] - 2024-11-XX

### 🎉 Initial Release

#### Core Features

- **Media Player Control**: Full Home Assistant media player implementation

  - Play, pause, stop, next/previous track
  - Volume control with configurable step size
  - Source selection (Wi-Fi, Bluetooth, Line-in, Optical, USB)
  - Playback modes (normal, repeat, shuffle)

- **Multiroom Audio**: Complete LinkPlay multiroom support

  - Automatic group detection and management
  - Master/slave role tracking
  - Group volume coordination
  - Real-time synchronization

- **Device Discovery**: Multiple discovery methods
  - UPnP/SSDP automatic discovery
  - Zeroconf mDNS discovery
  - Manual IP configuration
  - Proper device filtering for WiiM/LinkPlay devices

#### Audio Enhancement

- **Equalizer Control**: 10-band EQ with presets and custom curves

  - Built-in presets (Rock, Jazz, Classical, etc.)
  - Custom EQ curves with -12dB to +12dB range
  - Sound mode selection via Home Assistant UI

- **Hardware Presets**: Support for device preset buttons 1-6
  - Quick access to favorite stations/playlists
  - Integration with device front panel controls

#### Home Assistant Integration

- **Config Flow**: User-friendly setup wizard

  - Auto-discovery with manual fallback
  - Device validation and error handling
  - Options flow for per-device configuration

- **Entity Management**: Comprehensive entity support
  - Media player entities with rich attributes
  - Optional diagnostic sensors
  - Configurable polling intervals
  - Device information and status monitoring

#### Advanced Features

- **Error Recovery**: Robust error handling and recovery

  - Automatic session management
  - SSL certificate handling with fallback
  - Network interruption recovery
  - Intelligent retry logic

- **Performance Optimization**: Efficient resource usage
  - Adaptive polling rates based on activity
  - Minimal CPU and network overhead
  - Proper session cleanup and management

#### Supported Devices

- **WiiM Products**: Mini, Pro, Pro Plus, Amp
- **LinkPlay Compatible**: Arylic, Audio Pro, Dayton Audio, and others
- **API Compatibility**: Any device supporting LinkPlay HTTP API

---

## Development Guidelines

### Versioning Strategy

- **Major Version** (X.0.0): Breaking changes, major feature additions
- **Minor Version** (0.X.0): New features, significant improvements
- **Patch Version** (0.0.X): Bug fixes, documentation updates

### Release Process

1. Update version in `manifest.json`
2. Update this CHANGELOG.md
3. Create GitHub release with tag
4. HACS automatic distribution

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines and how to contribute to this project.

---

**Links:**

- [GitHub Repository](https://github.com/mjcumming/ha-wiim-integration)
- [Home Assistant Community](https://community.home-assistant.io/)
- [Issue Tracker](https://github.com/mjcumming/ha-wiim-integration/issues)
