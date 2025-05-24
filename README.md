# WiiM Audio Integration for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
[![Community Forum][forum-shield]][forum]

![WiiM Logo](https://github.com/home-assistant/brands/raw/master/core_integrations/linkplay/icon.png)

**Transform your WiiM and LinkPlay speakers into smart Home Assistant media players with full multiroom support.**

This integration provides comprehensive control over WiiM and LinkPlay-based audio devices, including advanced multiroom management, individual device control, and seamless Home Assistant integration.

---

## ✨ Features

### 🎵 **Media Control**

- **Playback Control**: Play, pause, stop, next/previous track, seek
- **Volume Management**: Individual volume control, configurable step size, group volume coordination
- **Source Selection**: Switch between Wi-Fi, Bluetooth, Line-in, Optical, USB sources
- **Presets**: Trigger device preset keys 1-6 via Home Assistant

### 🎛️ **Audio Enhancement**

- **Equalizer Control**: 10-band EQ with presets (Rock, Jazz, Classical, etc.) or custom curves
- **Sound Modes**: Quick access to audio presets via Home Assistant UI
- **Enable/Disable EQ**: Toggle equalizer on/off

### 🏠 **Multiroom Audio**

- **Group Management**: Create, join, and leave multiroom groups
- **Group Volume Control**: Unified volume control maintaining speaker relationships
- **Individual Control**: Fine-tune each speaker while in a group
- **Virtual Group Entities**: Optional group media players (user-controlled)
- **Real-time Sync**: Changes made in WiiM app automatically reflected in HA

### 📱 **Home Assistant Integration**

- **Auto-Discovery**: Automatic detection via UPnP/SSDP and Zeroconf
- **Config Flow**: User-friendly setup wizard
- **Device Options**: Per-device configuration (polling interval, volume step, group entities)
- **Rich Metadata**: Track info, album art, artist, streaming service detection
- **State Management**: Power state, playback status, connectivity monitoring

### 🔧 **Device Management**

- **Diagnostics**: Group role sensors, IP address tracking, Wi-Fi signal monitoring
- **Maintenance**: Remote reboot, time synchronization
- **Responsive Polling**: Adaptive polling rates (1s during playback, 10s when idle)
- **Error Recovery**: Automatic reconnection and session management

---

## 🚀 Quick Start

### Prerequisites

- Home Assistant 2024.12.0 or newer
- WiiM or LinkPlay-compatible speakers on your network
- Network access between HA and speakers (same VLAN/subnet recommended)

### Installation

#### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click **Explore & Download Repositories**
4. Search for **"WiiM Audio (LinkPlay)"**
5. Click **Download**
6. Restart Home Assistant

#### Manual Installation

1. Download the latest release from [GitHub Releases][releases]
2. Extract the `custom_components/wiim` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

### Setup

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **"WiiM Audio"**
4. Follow the setup wizard:
   - **Auto-Discovery**: Select discovered devices
   - **Manual**: Enter device IP addresses

---

## ⚙️ Configuration

### Device Options

Each device can be individually configured:

| Option               | Description                      | Default   | Range  |
| -------------------- | -------------------------------- | --------- | ------ |
| **Polling Interval** | How often to check device status | 5 seconds | 1-60s  |
| **Volume Step**      | Volume change increment          | 5%        | 1-50%  |
| **Group Entity**     | Create virtual group controller  | Disabled  | On/Off |

### Group Entity Setup

Enable **"Group Entity"** for devices you want to control multiroom groups:

1. **Settings** → **Devices & Services** → **WiiM Audio**
2. Click **Configure** on the master device
3. Enable **"Enable group control entity"**
4. Group entity appears when device acts as master

**Example**: Enable on "Living Room" → `media_player.living_room_group` created

---

## 🏠 Multiroom Guide

### Creating Groups

**Option 1: WiiM App**

1. Use official WiiM app to create groups
2. Changes automatically detected by Home Assistant

**Option 2: Home Assistant**

```yaml
service: media_player.join
target:
  entity_id: media_player.living_room
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom
```

### Group Controls

- **Master Device**: Controls playback for entire group
- **Group Entity**: Unified volume/control (if enabled)
- **Individual Devices**: Fine-tune specific speakers

### Group Volume Behavior

- **Group Volume**: Maximum of all member volumes
- **Volume Changes**: Applied relatively to maintain speaker balance
- **Example**: Master 80%, Slave 40% → Set group to 100% → Master 100%, Slave 60%

---

## 🛠️ Services

### Media Player Services

```yaml
# Play preset (1-6)
service: media_player.play_preset
target:
  entity_id: media_player.living_room
data:
  preset: 3

# Toggle power
service: media_player.toggle_power
target:
  entity_id: media_player.living_room

# Set equalizer
service: wiim.set_eq
target:
  entity_id: media_player.living_room
data:
  preset: "rock"
  # OR custom values:
  custom_values: [2, 4, 3, 0, -2, 1, 3, 2, 1, 0]
```

### Maintenance Services

```yaml
# Reboot device
service: wiim.reboot_device
target:
  entity_id: media_player.living_room

# Sync device time
service: wiim.sync_time
target:
  entity_id: media_player.living_room
```

---

## 🔍 Troubleshooting

### Common Issues

#### Devices Not Discovered

- **Check Network**: Ensure HA and speakers on same network/VLAN
- **Firewall**: Allow UPnP/SSDP traffic (ports 1900, 8080-8090)
- **Manual Setup**: Add devices by IP if auto-discovery fails

#### Group Volume Issues

- **Understanding Relative Volume**: Group volume represents the maximum member volume
- **Balancing**: Individual device volumes maintain their relative relationships
- **Troubleshooting**: Check individual device volumes in group entity attributes

#### Connection Errors

- **Session Timeouts**: Integration automatically recovers from network interruptions
- **SSL Issues**: Uses device-specific certificates with fallback to insecure mode
- **Polling**: Increase polling interval if experiencing frequent disconnections

### Debug Logging

```yaml
logger:
  default: warning
  logs:
    custom_components.wiim: debug
```

### Getting Help

- **GitHub Issues**: [Report bugs or request features][issues]
- **Home Assistant Community**: [Community forum thread][forum]
- **Documentation**: [Detailed guides](docs/)

---

## 🏗️ Development

### Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

1. Fork the repository
2. Create a development branch
3. Set up Home Assistant development environment
4. Install integration in development mode
5. Make changes and test
6. Submit pull request

### Architecture

- **API Client** (`api.py`): HTTP communication with WiiM devices
- **Coordinator** (`coordinator.py`): Data polling and state management
- **Media Player** (`media_player.py`): Main entity implementation
- **Config Flow** (`config_flow.py`): Setup wizard and options

---

## 📋 Supported Devices

### WiiM Products

- WiiM Mini
- WiiM Pro
- WiiM Pro Plus
- WiiM Amp

### LinkPlay Compatible

- Arylic speakers
- Audio Pro speakers
- Dayton Audio speakers
- Many other LinkPlay-based devices

**Note**: Any device exposing the LinkPlay HTTP API should work.

---

## 🤝 Community

### Links

- **GitHub Repository**: [ha-wiim-integration][github]
- **Home Assistant Forum**: [Community discussion][forum]
- **Issue Tracker**: [Bug reports & features][issues]

### Contributors

- **Michael Cumming** ([@mjcumming]) - Original developer
- **Community contributors** - See [GitHub contributors][contributors]

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **WiiM** for creating excellent audio products
- **LinkPlay** for the underlying platform
- **Home Assistant** community for support and feedback
- **python-linkplay** project for API insights

---

**Enjoying the integration? ⭐ Star the repository and share with others!**

[releases-shield]: https://img.shields.io/github/release/mjcumming/ha-wiim-integration.svg?style=for-the-badge
[releases]: https://github.com/mjcumming/ha-wiim-integration/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/mjcumming/ha-wiim-integration.svg?style=for-the-badge
[commits]: https://github.com/mjcumming/ha-wiim-integration/commits/main
[license-shield]: https://img.shields.io/github/license/mjcumming/ha-wiim-integration.svg?style=for-the-badge
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[hacs]: https://github.com/hacs/integration
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[github]: https://github.com/mjcumming/ha-wiim-integration
[issues]: https://github.com/mjcumming/ha-wiim-integration/issues
[contributors]: https://github.com/mjcumming/ha-wiim-integration/graphs/contributors
