# WiiM Audio Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/mjcumming/ha-wiim-integration.svg)](https://github.com/mjcumming/ha-wiim-integration/releases)
[![License](https://img.shields.io/github/license/mjcumming/ha-wiim-integration.svg)](LICENSE)

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
   - Add: `https://github.com/mjcumming/ha-wiim-integration`
   - Category: Integration

2. **Install Integration**

   - Search for "WiiM Audio"
   - Click Download → Restart Home Assistant

3. **Add Integration**
   - Settings → Devices & Services → Add Integration
   - Search "WiiM Audio" → Follow setup wizard

### Manual Installation

1. Download latest release from [GitHub](https://github.com/mjcumming/ha-wiim-integration/releases)
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

- **🐛 Bug Reports**: [GitHub Issues](https://github.com/mjcumming/ha-wiim-integration/issues)
- **💬 Discussions**: [Home Assistant Community](https://community.home-assistant.io/)
- **🔄 Feature Requests**: [GitHub Discussions](https://github.com/mjcumming/ha-wiim-integration/discussions)
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
