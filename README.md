# WiiM Audio Integration for Home Assistant

<p align="center">
  <img src="images/logo.png" alt="WiiM Integration Logo" width="200"/>
</p>

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/mjcumming/wiim.svg)](https://github.com/mjcumming/wiim/releases)
[![License](https://img.shields.io/github/license/mjcumming/wiim.svg)](https://github.com/mjcumming/wiim/blob/main/LICENSE)

> ⭐ **Love this integration?** Please star us on GitHub if you use this integration! It helps others discover the project and shows your support for the development effort.

Transform your WiiM and LinkPlay speakers into powerful Home Assistant media players with full multiroom support. No additional dependencies required.

## Why Choose This Integration?

- **🏠 Native Integration** - Built entirely within Home Assistant's framework
- **🎵 Complete Media Control** - Full transport controls, volume, sources, presets
- **🔗 True Multiroom** - Uses Home Assistant's native grouping for reliable sync
- **⚡ Zero Dependencies** - No external Python packages needed
- **🚀 Auto-Discovery** - Finds speakers automatically on your network
- **📱 Universal Compatibility** - Works with all Home Assistant dashboards and voice assistants

## Supported Devices

- **WiiM**: Mini, Pro, Pro Plus, Amp, Ultra
- **LinkPlay Compatible**: Arylic, Audio Pro, Dayton Audio, DOSS, and many more
- **Requirements**: Home Assistant 2024.12.0+ on same network as speakers

## Quick Start

### 1. Install via HACS (Recommended)

1. **Add to HACS**: Integrations → ⋮ → Custom repositories → Add `https://github.com/mjcumming/wiim`
2. **Install**: Search "WiiM Audio" → Download → Restart Home Assistant
3. **Configure**: Settings → Devices & Services → Add Integration → "WiiM Audio"

### 2. Manual Installation

1. Download [latest release](https://github.com/mjcumming/wiim/releases)
2. Extract to `/config/custom_components/wiim/`
3. Restart Home Assistant and add integration

## Key Features

| Feature              | Description                                                        |
| -------------------- | ------------------------------------------------------------------ |
| **Media Control**    | Play, pause, stop, next/previous, seek                             |
| **Volume Control**   | Individual and synchronized group volume                           |
| **Smart Sources**    | Detects streaming services (Spotify, Amazon Music, etc.)           |
| **Audio Output**     | Control hardware output modes (Line Out, Optical, Coax, Bluetooth) |
| **Multiroom Groups** | Synchronized playback across speaker groups                        |
| **Quick Stations**   | Custom radio station list in Browse Media                          |
| **EQ Control**       | 10-band equalizer with presets                                     |
| **Presets**          | Hardware preset buttons (device dependent, up to 20)               |
| **Auto-Discovery**   | Finds speakers automatically via UPnP/Zeroconf                     |

## Usage Examples

### Multiroom Audio

```yaml
# Create speaker group
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

### Custom Radio Stations

Create `wiim_stations.yaml` in your config folder:

```yaml
- name: BBC Radio 2
  url: http://stream.live.vc.bbcmedia.co.uk/bbc_radio_two
- name: Groove Salad (SomaFM)
  url: http://ice2.somafm.com/groovesalad-128-mp3
```

Access via **Browse Media → Quick Stations** on any WiiM device.

### Audio Output Control

```yaml
# Switch to Bluetooth output
- service: select.select_option
  target: select.living_room_audio_output_mode
  data:
    option: "Bluetooth Out"

# Switch to Line Out
- service: select.select_option
  target: select.living_room_audio_output_mode
  data:
    option: "Line Out"
```

### Automation Examples

```yaml
# Morning radio
- service: media_player.play_media
  target: media_player.kitchen
  data:
    media_content_type: url
    media_content_id: "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_two"

# Play preset button
- service: wiim.play_preset
  target: media_player.living_room
  data:
    preset: 1
```

## Advanced Services

| Service              | Description                             |
| -------------------- | --------------------------------------- |
| `wiim.play_preset`   | Play hardware preset (device dependent) |
| `wiim.play_url`      | Play audio from URL                     |
| `wiim.set_eq`        | Set equalizer presets or custom values  |
| `wiim.reboot_device` | Reboot device                           |

## Source Customization

### Why Source Renaming Isn't Supported

The WiiM integration doesn't support custom source names for several reasons:

- **Device Limitation**: Source names come directly from the device's firmware and API
- **Consistency**: Other major integrations (Sonos, Denon, Yamaha) also don't support source renaming
- **API Compatibility**: The device expects specific source names for proper functionality
- **Automation Reliability**: Custom names could break existing automations and scripts

### How to Work Around This

Instead of renaming sources, you can customize the display in several ways:

#### 1. Rename the Media Player Entity

```yaml
# In customize.yaml
media_player.living_room_speaker:
  friendly_name: "Living Room TV Audio"
```

#### 2. Use Templates in Automations

```yaml
# In automations.yaml
- alias: "When HDMI is selected"
  trigger:
    platform: state
    entity_id: media_player.living_room_speaker
    attribute: source
    to: "HDMI"
  action:
    - service: notify.persistent_notification
      data:
        message: "TV audio is now active"
```

#### 3. Create Custom Dashboard Cards

```yaml
# In Lovelace dashboard
type: entities
entities:
  - entity: media_player.living_room_speaker
    name: "TV Audio"
    secondary_info: "{{ states('media_player.living_room_speaker').attributes.source }}"
```

## Diagnostics & Troubleshooting

When experiencing issues, you can download comprehensive diagnostic information to help with troubleshooting:

1. **Device Diagnostics**: Go to Settings → Devices & Services → WiiM Audio → (Select device) → Download Diagnostics
2. **Integration Diagnostics**: Go to Settings → Devices & Services → WiiM Audio → (⋮ Menu) → Download Diagnostics

The diagnostics include:

- Device information (model, firmware, network status)
- Multiroom group configuration and roles
- Media playback state and current sources
- API polling status and error tracking
- EQ settings and sound modes

**All sensitive data (IP addresses, MAC addresses, network names) is automatically redacted.**

## Documentation

- **[📚 Quick Start Guide](docs/README.md)** - Installation and basic setup
- **[🎛️ User Guide](docs/user-guide.md)** - Complete features and configuration
- **[🤖 Automation Cookbook](docs/automation-cookbook.md)** - Ready-to-use automation patterns
- **[❓ FAQ](docs/FAQ.md)** - Quick answers to common questions
- **[🔧 Troubleshooting](docs/troubleshooting.md)** - Fix common issues and network problems

## Support & Community

- **🐛 Issues**: [GitHub Issues](https://github.com/mjcumming/wiim/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/mjcumming/wiim/discussions)
- **🏠 Community**: [Home Assistant Community](https://community.home-assistant.io/)

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines:

- Code improvements and bug fixes
- Documentation updates
- Testing on different speaker models
- Example automations and scripts

## Acknowledgments

This integration builds upon excellent work from:

- [python-linkplay](https://github.com/Velleman/python-linkplay) - Comprehensive LinkPlay library
- [LinkPlay HA Integration](https://github.com/nagyrobi/home-assistant-custom-components-linkplay) - Original LinkPlay integration

## License

MIT License - see [LICENSE](LICENSE) for details.

---

_This integration is not affiliated with WiiM or LinkPlay. All trademarks belong to their respective owners._
