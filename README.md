# WiiM Audio Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/mjcumming/wiim.svg)](https://github.com/mjcumming/wiim/releases)
[![License](https://img.shields.io/github/license/mjcumming/wiim.svg)](https://github.com/mjcumming/wiim/blob/main/LICENSE)

Transform your WiiM and LinkPlay speakers into powerful Home Assistant `media_player` entities with full multiroom support, no additional dependencies required.

## ✨ Key Features

- 🎵 **Complete Media Control** - Play, pause, volume, source selection, presets
- 🏠 **Multiroom Audio** - Synchronized playback across speaker groups
- 🎚️ **Group Volume Controls** - Dedicated entities for synchronized group volume and mute
- 🔧 **No Dependencies** - Uses only Home Assistant's built-in libraries
- 🚀 **Auto-Discovery** - Automatically finds speakers on your network
- ⚡ **Responsive** - Adaptive polling for immediate UI updates
- 🎛️ **Advanced Controls** - EQ, grouping, diagnostics, and more

## 🛠️ Supported Devices

- **WiiM**: Mini, Pro, Pro Plus, Amp, Ultra
- **LinkPlay Compatible**: Arylic, Audio Pro, Dayton Audio, DOSS, and many more
- **Requirements**: Home Assistant 2024.12.0+ on same network as speakers

## 📦 Installation

### Via HACS (Recommended)

1. **Add Integration to HACS**

   - Open HACS → Integrations
   - Click ⋮ → Custom repositories
   - Add: `https://github.com/mjcumming/wiim`
   - Category: Integration

2. **Install Integration**

   - Search for "WiiM Audio"
   - Click Download → Restart Home Assistant

3. **Add Integration**
   - Settings → Devices & Services → Add Integration
   - Search "WiiM Audio" → Follow setup wizard

### Manual Installation

1. Download latest release from [GitHub](https://github.com/mjcumming/wiim/releases)
2. Extract to `/config/custom_components/wiim/`
3. Restart Home Assistant
4. Add integration via Settings → Devices & Services

## 🚀 Quick Start

1. **Auto-Discovery**: The integration automatically finds WiiM speakers on your network
2. **Configuration**: Each speaker becomes a media player entity
3. **Multiroom**: Enable group entities in device options for multiroom control
4. **Enjoy**: Control speakers from Home Assistant dashboards and automations

## 📖 Documentation

- **[Complete Setup Guide](docs/README.md)** - Full documentation index
- **[Installation Details](docs/installation.md)** - Detailed installation instructions
- **[Multiroom Setup](docs/multiroom.md)** - Synchronized audio across speakers
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions
- **[Examples](examples/)** - Ready-to-use scripts and automations

## 🎵 Usage Examples

### Basic Control

```yaml
# Play preset 3 on living room speaker
service: media_player.play_preset
target:
  entity_id: media_player.living_room
data:
  preset: 3
```

### Multiroom Groups

```yaml
# Create synchronized group
service: media_player.join
target:
  entity_id: media_player.living_room
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom
```

### Automation

```yaml
# Morning music routine
automation:
  - alias: "Morning Music"
    trigger:
      platform: time
      at: "07:00:00"
    action:
      - service: media_player.volume_set
        target:
          entity_id: media_player.kitchen
        data:
          volume_level: 0.3
```

## 🔧 Features Matrix

| Feature          | Status | Notes                             |
| ---------------- | ------ | --------------------------------- |
| Play/Pause/Stop  | ✅     | Full transport control            |
| Volume Control   | ✅     | Absolute and relative             |
| Group Volume     | ✅     | Synchronized group volume control |
| Group Mute       | ✅     | Synchronized group mute control   |
| Source Selection | ✅     | WiFi, Bluetooth, Line In, etc.    |
| Preset Buttons   | ✅     | Hardware buttons 1-6              |
| Multiroom Groups | ✅     | Master/slave synchronization      |
| Equalizer        | ✅     | 10-band EQ + presets              |
| Auto Discovery   | ✅     | UPnP/SSDP + Zeroconf              |
| Group Entities   | ✅     | Virtual group controllers         |

## 🤝 Community & Support

- **🐛 Bug Reports**: [GitHub Issues](https://github.com/mjcumming/wiim/issues)
- **💬 Discussions**: [Home Assistant Community](https://community.home-assistant.io/)
- **🔄 Feature Requests**: [GitHub Discussions](https://github.com/mjcumming/wiim/discussions)
- **📖 Wiki**: [Documentation](docs/)

## 🙏 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

- Code contributions and bug fixes
- Documentation improvements
- Testing on different speaker models
- Example automations and scripts

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

---

_This integration is not affiliated with WiiM or LinkPlay. All trademarks belong to their respective owners._

## Usage

Once configured, your WiiM devices will appear as media player entities. You can:

- Control playback from the media player card
- Use voice assistants for control
- Create automations with the rich service calls
- Group devices for multiroom audio
- Adjust equalizer settings
- Monitor device status and diagnostics

## Services

The integration provides many service calls for advanced control:

### Media Services

- `wiim.play_preset` - Play a stored preset (1-6)
- `wiim.play_url` - Play audio from a URL
- `wiim.play_playlist` - Play an M3U playlist
- `wiim.play_notification` - Play notification sounds
- `wiim.set_eq` - Set equalizer presets or custom values

### Group Services

- `wiim.create_group_with_members` - Create a multiroom group
- `wiim.add_to_group` - Add device to existing group
- `wiim.remove_from_group` - Remove device from group
- `wiim.disband_group` - Disband the entire group

### Device Services

- `wiim.reboot_device` - Reboot the device
- `wiim.sync_time` - Sync device time with Home Assistant

## Troubleshooting

### Connection Issues

1. **Verify Network Connectivity**: Ensure your WiiM device is on the same network as Home Assistant
2. **Check Firewall Settings**: Make sure ports 80 and 443 are accessible
3. **Update Firmware**: Ensure your WiiM device has the latest firmware
4. **Restart Devices**: Try restarting both Home Assistant and your WiiM device

### Group Management Issues

- Ensure all devices are on the same firmware version
- Check that devices are on the same network subnet
- Try disbanding and recreating groups if sync issues occur

## Support

- **GitHub Issues**: https://github.com/mjcumming/wiim/issues
- **Home Assistant Community**: Search for "WiiM" in the community forums
- **Documentation**: Full documentation available in the GitHub repository

## Contributing

Contributions are welcome! Please see the GitHub repository for development guidelines and how to submit pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🎯 **Key Features**

| Feature                  | Status | Description                            |
| ------------------------ | ------ | -------------------------------------- |
| Media Control            | ✅     | Play, Pause, Stop, Next/Previous       |
| Volume Control           | ✅     | Volume adjustment and mute             |
| **Hierarchical Sources** | ✅     | **Smart source detection (see below)** |
| Source Selection         | ✅     | WiFi, Bluetooth, Line In, etc.         |
| Sound Modes              | ✅     | EQ presets and audio enhancement       |
| Shuffle & Repeat         | ✅     | Playback mode controls                 |
| Track Position           | ✅     | Seek support with position tracking    |
| Cover Art                | ✅     | Album artwork with change detection    |
| Multiroom Control        | ✅     | Group management and synchronization   |
| Device Discovery         | ✅     | Automatic network discovery            |

### 🔍 **Hierarchical Source Detection**

Our integration uses **intelligent source detection** that prioritizes what users actually care about:

#### **What You See vs. Technical Details**

| **You See (Priority 1)** | **Technical Reality (Priority 2)** | **When Used**          |
| ------------------------ | ---------------------------------- | ---------------------- |
| **Amazon Music** 🎵      | WiFi                               | Streaming from Amazon  |
| **Spotify** 🎵           | WiFi                               | Streaming from Spotify |
| **AirPlay** 📱           | WiFi                               | Casting from iOS/Mac   |
| **Bluetooth** 📱         | Bluetooth                          | Direct BT connection   |
| **Line In** 🔌           | Line In                            | Physical audio input   |

#### **Why This Matters**

- **Before**: Users saw confusing technical details like "WiFi" when streaming
- **After**: Users see meaningful information like "Amazon Music"
- **Smart Detection**: Uses artwork URLs, metadata, and API fields to identify streaming services
- **Fallback Logic**: Shows input type (WiFi, Bluetooth) when service can't be detected

This matches how other premium integrations work (Sonos shows "Spotify", not "Network").
