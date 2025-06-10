# WiiM Audio Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/mjcumming/wiim.svg)](https://github.com/mjcumming/wiim/releases)
[![License](https://img.shields.io/github/license/mjcumming/wiim.svg)](https://github.com/mjcumming/wiim/blob/main/LICENSE)

Transform your WiiM and LinkPlay speakers into powerful Home Assistant `media_player` entities with full multiroom support, no additional dependencies required.

## 🤝 Acknowledgments

This integration builds upon the excellent work of the LinkPlay community:

- [python-linkplay](https://github.com/Velleman/python-linkplay) - A comprehensive Python library for LinkPlay device control
- [LinkPlay Home Assistant Integration](https://github.com/nagyrobi/home-assistant-custom-components-linkplay) - The original Home Assistant integration for LinkPlay devices

## 🎯 Why Another Integration?

While existing solutions are excellent, this integration takes a different approach:

- **Native Home Assistant**: Built entirely within Home Assistant's framework, with no external dependencies
- **Standard Media Player**: Fully implements Home Assistant's media player platform for seamless integration
- **True Multiroom**: Leverages Home Assistant's built-in media player grouping for reliable multiroom control
- **Simplified Setup**: No additional Python packages or system dependencies required
- **Future-Proof**: Direct integration with Home Assistant's core features and updates

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

### Dashboard Integration

```yaml
# Example media player card configuration
type: media-player
entity: media_player.living_room
show_volume_buttons: true
show_play_pause: true
show_source: true
show_group: true
```

## 🔧 Features Matrix

| Feature          | Status | Notes                             |
| ---------------- | ------ | --------------------------------- |
| Play/Pause/Stop  | ✅     | Full transport control            |
| Volume Control   | ✅     | Absolute and relative             |
| Group Volume     | ✅     | Native HA group volume control    |
| Group Mute       | ✅     | Native HA group mute control      |
| Source Selection | ✅     | WiFi, Bluetooth, Line In, etc.    |
| Preset Buttons   | ✅     | Hardware buttons 1-6              |
| Multiroom Groups | ✅     | Native HA media player grouping   |
| Equalizer        | ✅     | 10-band EQ + presets              |
| Auto Discovery   | ✅     | UPnP/SSDP + Zeroconf              |
| Group Entities   | ✅     | Native HA group entities          |
| Voice Control    | ✅     | Works with all HA voice assistants|
| Dashboards       | ✅     | Compatible with all HA cards      |

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

The integration fully supports Home Assistant's native media player grouping system:

```yaml
# Create or join a group
service: media_player.join
target:
  entity_id: media_player.living_room
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom

# Remove from group
service: media_player.unjoin
target:
  entity_id: media_player.living_room
```

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


