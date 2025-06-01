# WiiM Audio Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/mjcumming/wiim.svg)](https://github.com/mjcumming/wiim/releases)
[![License](https://img.shields.io/github/license/mjcumming/wiim.svg)](LICENSE)

Transform your WiiM and LinkPlay speakers into powerful Home Assistant `media_player` entities with full multiroom support, no additional dependencies required.

## ✨ Key Features

- 🎵 **Complete Media Control** - Play, pause, volume, source selection, presets
- 🏠 **Multiroom Audio** - Synchronized playback across speaker groups
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

| Feature          | Status | Notes                          |
| ---------------- | ------ | ------------------------------ |
| Play/Pause/Stop  | ✅     | Full transport control         |
| Volume Control   | ✅     | Absolute and relative          |
| Source Selection | ✅     | WiFi, Bluetooth, Line In, etc. |
| Preset Buttons   | ✅     | Hardware buttons 1-6           |
| Multiroom Groups | ✅     | Master/slave synchronization   |
| Equalizer        | ✅     | 10-band EQ + presets           |
| Auto Discovery   | ✅     | UPnP/SSDP + Zeroconf           |
| Group Entities   | ✅     | Virtual group controllers      |
| Media Browser    | 🚧     | Coming soon                    |

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

**⚡ Made with ❤️ by the Home Assistant community**

_This integration is not affiliated with WiiM or LinkPlay. All trademarks belong to their respective owners._

## Resolving LinkPlay Conflicts

**Important**: This integration may conflict with Home Assistant's built-in LinkPlay integration. If you see errors like "Cannot connect to host X.X.X.X:80" in your logs, follow these steps:

### Option 1: Disable Built-in LinkPlay Integration

Add this to your `configuration.yaml`:

```yaml
# Disable built-in linkplay integration to prevent conflicts
default_config:

# Exclude linkplay from discovery
discovery:
  ignore:
    - linkplay
# If you have the linkplay integration already configured, remove it:
# linkplay:  # <- Remove or comment out this entire section
```

### Option 2: Network-Level Blocking

If the built-in integration continues to interfere, you can block it at the network level by adding this to your router's firewall or using a local firewall rule to block port 80 traffic from Home Assistant to your WiiM devices (while allowing our custom integration's HTTPS traffic on port 443).

### Option 3: Manual Entity Cleanup

If you have duplicate entities from the built-in linkplay integration:

1. Go to Settings → Devices & Services
2. Find any "LinkPlay" integrations (not "WiiM Audio (LinkPlay)")
3. Remove them
4. Go to Settings → Entities
5. Search for "linkplay" entities and remove any duplicates
6. Restart Home Assistant

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

### Diagnostic Services

- `wiim.diagnose_entities` - Run diagnostic checks
- `wiim.cleanup_stale_entities` - Clean up orphaned entities
- `wiim.auto_maintain` - Automated maintenance tasks

## Troubleshooting

### Connection Issues

1. **Verify Network Connectivity**: Ensure your WiiM device is on the same network as Home Assistant
2. **Check Firewall Settings**: Make sure ports 80 and 443 are accessible
3. **Update Firmware**: Ensure your WiiM device has the latest firmware
4. **Restart Devices**: Try restarting both Home Assistant and your WiiM device

### LinkPlay Conflicts

If you see errors mentioning "linkplay" or connection failures to port 80:

1. Disable the built-in LinkPlay integration (see above)
2. Remove any existing LinkPlay entities
3. Restart Home Assistant
4. Re-add your devices using this WiiM integration

### Group Management Issues

- Ensure all devices are on the same firmware version
- Check that devices are on the same network subnet
- Try disbanding and recreating groups if sync issues occur

### Entity Cleanup

If you have duplicate or orphaned entities:

1. Use the `wiim.diagnose_entities` service to identify issues
2. Use `wiim.cleanup_stale_entities` to remove orphaned entities
3. For severe issues, use `wiim.nuclear_reset_entities` (removes ALL WiiM entities)

## Support

- **GitHub Issues**: https://github.com/mjcumming/wiim/issues
- **Home Assistant Community**: Search for "WiiM" in the community forums
- **Documentation**: Full documentation available in the GitHub repository

## Version History

### 0.4.6

- Resolved GitHub release workflow tag conflict issue
- Fixed version tag mismatch in release process
- All fixes from 0.4.5 included

### 0.4.5

- Fixed `join_players` method to prevent NotImplementedError
- Improved error handling for group operations
- Added timeout protection for async operations
- Enhanced documentation for LinkPlay conflicts

### 0.4.4

- Enhanced multiroom group management
- Improved device discovery and status parsing
- Better error handling and logging
- Added comprehensive service calls

## Contributing

Contributions are welcome! Please see the GitHub repository for development guidelines and how to submit pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
