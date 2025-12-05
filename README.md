# WiiM Audio Integration for Home Assistant

<p align="center">
  <img src="images/logo.png" alt="WiiM Integration Logo" width="200"/>
</p>

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/mjcumming/wiim.svg)](https://github.com/mjcumming/wiim/releases)
[![License](https://img.shields.io/github/license/mjcumming/wiim.svg)](https://github.com/mjcumming/wiim/blob/main/LICENSE)
[![Home Assistant](https://img.shields.io/badge/home%20assistant-2024.12.0+-blue.svg)](https://www.home-assistant.io/)
[![Maintenance](https://img.shields.io/maintenance/yes/2025.svg)](https://github.com/mjcumming/wiim)
[![Quality Scale](https://img.shields.io/badge/quality%20scale-silver-brightgreen.svg)](https://www.home-assistant.io/docs/quality_scale/)
[![Project Status](https://img.shields.io/badge/project%20status-active-success.svg)](https://github.com/mjcumming/wiim)
[![CI](https://img.shields.io/github/actions/workflow/status/mjcumming/wiim/tests.yaml?branch=main&label=CI)](https://github.com/mjcumming/wiim/actions/workflows/tests.yaml)
[![codecov](https://codecov.io/gh/mjcumming/wiim/branch/main/graph/badge.svg)](https://codecov.io/gh/mjcumming/wiim)
[![GitHub Issues](https://img.shields.io/github/issues/mjcumming/wiim.svg)](https://github.com/mjcumming/wiim/issues)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/mjcumming/wiim.svg)](https://github.com/mjcumming/wiim/pulls)

> ⭐ **Love this integration?** Please star us on GitHub if you use this integration! It helps others discover the project and shows your support for the development effort.

Transform your WiiM and LinkPlay speakers into powerful Home Assistant media players with full multiroom support. Built on the brand new, fully async [`pywiim`](https://github.com/mjcumming/pywiim) library we wrote for reliable, high-performance device communication.

## Why Choose This Integration?

- **🎵 Complete Media Control** - Full transport controls, volume, sources, presets, TTS, and media browsing
- **🔗 True Multiroom** - Uses Home Assistant's native grouping for reliable synchronized playback
- **⚡ Powered by pywiim** - Built on the brand new, fully async [`pywiim`](https://github.com/mjcumming/pywiim) library we wrote for robust, high-performance device communication
- **🚀 Auto-Discovery** - Finds speakers automatically via UPnP/SSDP/Zeroconf
- **📱 Universal Compatibility** - Works with all Home Assistant dashboards, voice assistants, and media sources
- **⚡ Hybrid State Updates** - UPnP events for real-time updates + HTTP polling for reliability
- **🎛️ Advanced Audio** - 10-band EQ, audio quality sensors, output mode control, and format support
- **⏰ Timer & Alarms** - Sleep timer and alarm management for WiiM devices
- **📊 Rich Diagnostics** - Comprehensive statistics, health monitoring, and troubleshooting tools
- **🔄 Scene Support** - Full scene restoration including EQ presets and playback state
- **🎯 Smart Features** - Optimistic UI updates, adaptive polling, and intelligent source detection

## Supported Devices

- **WiiM**: Mini, Pro, Pro Plus, Amp, Ultra
- **LinkPlay Compatible**: Arylic, Audio Pro (including Gen1: A26, C10, C5a and MkII models), Dayton Audio, DOSS, and many more
- **Enhanced Compatibility**: Automatic protocol fallback for devices with non-standard configurations
- **Requirements**: Home Assistant 2024.12.0+ on same network as speakers

## Quick Start

### 1. Install via HACS (Recommended)

1. **Find in HACS**: HACS → Integrations → Search "WiiM Audio"
2. **Install**: Download → Restart Home Assistant
3. **Configure**: Settings → Devices & Services → Add Integration → "WiiM Audio"

### 2. Manual Installation

1. Download [latest release](https://github.com/mjcumming/wiim/releases)
2. Extract to `/config/custom_components/wiim/`
3. Restart Home Assistant and add integration

## Key Features

### 🎵 Media Playback & Control

| Feature              | Description                                                                       |
| -------------------- | --------------------------------------------------------------------------------- |
| **Media Control**    | Play, pause, stop, next/previous, seek with resume support                        |
| **Volume Control**   | Individual and synchronized group volume with debouncing                          |
| **Smart Sources**    | Detects streaming services (Spotify, Amazon Music, Apple Music, etc.)             |
| **Media Browser**    | Browse Home Assistant media sources, DLNA servers, and custom radio stations      |
| **TTS Support**      | Full Text-to-Speech integration for all TTS engines (Google, Amazon, Azure, etc.) |
| **Shuffle & Repeat** | Toggle shuffle and repeat modes for playlists                                     |
| **Presets**          | Hardware preset buttons (device dependent, up to 20)                              |
| **URL Playback**     | Play audio from any URL (radio streams, files, playlists)                         |

### 🎛️ Audio Enhancement

| Feature            | Description                                                                   |
| ------------------ | ----------------------------------------------------------------------------- |
| **EQ Control**     | 10-band equalizer with 24 presets (Flat, Rock, Jazz, Classical, Pop, etc.)    |
| **Custom EQ**      | Fine-tune each of 10 frequency bands (-12dB to +12dB)                         |
| **Audio Output**   | Control hardware output modes (Line Out, Optical, Coax, Bluetooth, Headphone) |
| **Audio Quality**  | Real-time sensors for sample rate, bit depth, and bit rate                    |
| **Format Support** | Lossless (FLAC, WAV, ALAC up to 24-bit/192kHz) and compressed formats         |

### 🏠 Multiroom & Grouping

| Feature                | Description                                                     |
| ---------------------- | --------------------------------------------------------------- |
| **Multiroom Groups**   | Synchronized playback across speaker groups with perfect timing |
| **Group Coordinators** | Virtual entities for unified group control                      |
| **Role Detection**     | Automatic master/slave/solo role detection with sensors         |
| **Group Volume**       | Synchronized volume control across all group members            |
| **Smart Grouping**     | Uses Home Assistant's native grouping for reliable sync         |

### ⏰ Timer & Alarm Features (WiiM Devices)

| Feature              | Description                                                       |
| -------------------- | ----------------------------------------------------------------- |
| **Sleep Timer**      | Set sleep timer (0-7200 seconds) to automatically turn off device |
| **Alarm Management** | Create and manage up to 3 alarms with daily/weekly schedules      |
| **Alarm Control**    | Full alarm creation, update, and deletion via services            |

### 📊 Sensors & Diagnostics

| Feature               | Description                                      |
| --------------------- | ------------------------------------------------ |
| **Role Sensor**       | Shows current multiroom role (Master/Slave/Solo) |
| **Input Sensor**      | Current audio input source                       |
| **Audio Quality**     | Sample rate, bit depth, and bit rate sensors     |
| **Diagnostic Sensor** | Comprehensive device health and statistics       |
| **Firmware Sensor**   | Device firmware version tracking                 |
| **Bluetooth Status**  | Bluetooth output and connected device status     |

### 🔧 Advanced Features

| Feature                  | Description                                                                   |
| ------------------------ | ----------------------------------------------------------------------------- |
| **Auto-Discovery**       | Finds speakers automatically via UPnP/SSDP/Zeroconf                           |
| **Real-Time Updates**    | UPnP event subscriptions for instant state changes with HTTP polling fallback |
| **Scene Support**        | Full scene restoration including EQ presets and playback state                |
| **Optimistic Updates**   | Immediate UI feedback for all controls                                        |
| **Enhanced Diagnostics** | Comprehensive device diagnostics with statistics and health monitoring        |
| **Protocol Fallback**    | Automatic HTTP/HTTPS protocol detection with multi-port fallback              |
| **Audio Pro Support**    | Full support for Audio Pro MkII with mTLS client certificate authentication   |

## How It Works

The integration uses a **hybrid approach** combining UPnP event subscriptions and HTTP polling for optimal reliability and responsiveness:

- **UPnP Events (Primary)**: Real-time state updates via DLNA DMR event subscriptions

  - Instant updates when device state changes (play/pause/volume/mute)
  - Reduces network traffic and improves responsiveness
  - Automatically falls back to polling if UPnP becomes unavailable

- **HTTP Polling (Fallback)**: Adaptive polling strategy ensures reliability
  - 1-second polling during active playback for position updates
  - 5-second polling when idle for resource efficiency
  - Always available as fallback if UPnP subscriptions fail
  - Gracefully handles network issues and device restarts

This dual approach ensures you get the best of both worlds: real-time responsiveness when UPnP is working, and reliable operation even when it's not.

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
# Morning radio with TTS announcement
- alias: "Morning Routine"
  trigger:
    platform: time
    at: "07:00:00"
  action:
    - service: tts.google_translate_say
      target:
        entity_id: media_player.kitchen
      data:
        message: "Good morning! Starting your favorite radio station."
    - service: media_player.play_media
      target:
        entity_id: media_player.kitchen
      data:
        media_content_type: url
        media_content_id: "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_two"

# Play preset button
- service: wiim.play_preset
  target:
    entity_id: media_player.living_room
  data:
    preset: 1

# Set sleep timer before bed
- alias: "Bedtime Sleep Timer"
  trigger:
    platform: time
    at: "22:30:00"
  action:
    - service: wiim.set_sleep_timer
      target:
        entity_id: media_player.bedroom
      data:
        sleep_time: 3600 # 1 hour

# Create morning alarm
- service: wiim.update_alarm
  target:
    entity_id: media_player.bedroom
  data:
    alarm_id: 0
    time: "07:00:00" # UTC time
    trigger: "daily"
    operation: "playback"

# Set EQ for different music types
- alias: "Rock Music EQ"
  trigger:
    platform: state
    entity_id: media_player.living_room
    attribute: source
    to: "Spotify"
  action:
    - service: wiim.set_eq
      target:
        entity_id: media_player.living_room
      data:
        preset: "rock"
```

## Actions (Services)

> **Note**: Home Assistant now calls "services" as "actions" in the UI. Both terms refer to the same functionality.

### Media Playback Actions

| Action                   | Description                                       |
| ------------------------ | ------------------------------------------------- |
| `wiim.play_preset`       | Play hardware preset (device dependent, up to 20) |
| `wiim.play_url`          | Play audio from URL (radio streams, files)        |
| `wiim.play_playlist`     | Play M3U playlist from URL                        |
| `wiim.play_notification` | Play notification sound with auto volume restore  |

### Queue Management Actions

> **⚠️ Limited Device Support**: Queue browsing (`get_queue`) only works on **WiiM Amp and Ultra with USB drive connected**. Other devices (Mini, Pro, Pro Plus) do not support ContentDirectory service. Queue position/count is available on all devices. See [pywiim documentation](https://github.com/mjcumming/pywiim/tree/main/docs) for details.

| Action                   | Description                                                      |
| ------------------------ | ---------------------------------------------------------------- |
| `wiim.play_queue`        | Play from queue at specific position (requires UPnP AVTransport) |
| `wiim.remove_from_queue` | Remove item from queue at position (requires UPnP AVTransport)   |
| `wiim.get_queue`         | Get queue contents with metadata (Amp/Ultra + USB only)          |

### Audio & EQ Actions

| Action        | Description                                    |
| ------------- | ---------------------------------------------- |
| `wiim.set_eq` | Set equalizer presets or custom 10-band values |

### Timer & Alarm Actions (WiiM Devices Only)

| Action                   | Description                             |
| ------------------------ | --------------------------------------- |
| `wiim.set_sleep_timer`   | Set sleep timer (0-7200 seconds)        |
| `wiim.clear_sleep_timer` | Clear active sleep timer                |
| `wiim.update_alarm`      | Create/update alarm (3 slots, UTC time) |

### Device Management Actions

| Action               | Description                                 |
| -------------------- | ------------------------------------------- |
| `wiim.reboot_device` | Reboot device (temporarily unavailable)     |
| `wiim.sync_time`     | Synchronize device time with Home Assistant |

### Unofficial API Actions

⚠️ **Advanced users only** - These actions use reverse-engineered API endpoints that may not work on all firmware versions:

| Action                     | Description                       |
| -------------------------- | --------------------------------- |
| `wiim.scan_bluetooth`      | Scan for nearby Bluetooth devices |
| `wiim.set_channel_balance` | Adjust left/right channel balance |

See the [User Guide](docs/user-guide.md) for complete action documentation with examples.

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

## Platforms & Entities

The integration creates multiple entity types for comprehensive control:

### Media Player

- Main media player entity with full transport controls
- Group coordinator entities for multiroom groups
- Browse media support for all Home Assistant media sources

### Sensors

- **Multiroom Role** - Current role (Master/Slave/Solo)
- **Input Source** - Current audio input
- **Audio Quality** - Sample rate, bit depth, bit rate (when available)
- **Firmware Version** - Device firmware tracking
- **Bluetooth Status** - Bluetooth output and connected device
- **Diagnostic** - Comprehensive device health and statistics

### Select Entities

- **Audio Output Mode** - Line Out, Optical, Coax, Bluetooth, Headphone (device dependent)
- **EQ Preset** - 24 equalizer presets
- **Sound Mode** - Audio processing modes

### Buttons

- **Sync Time** - Synchronize device clock
- **Reboot Device** - Restart device
- **Clear Sleep Timer** - Clear active sleep timer

### Switches

- **Mute** - Toggle mute state
- **Shuffle** - Toggle shuffle mode
- **Repeat** - Toggle repeat mode

### Lights (Device Dependent)

- **Status LED** - Control device LED indicators

## Diagnostics & Troubleshooting

When experiencing issues, you can download comprehensive diagnostic information to help with troubleshooting:

1. **Device Diagnostics**: Go to Settings → Devices & Services → WiiM Audio → (Select device) → Download Diagnostics
2. **Integration Diagnostics**: Go to Settings → Devices & Services → WiiM Audio → (⋮ Menu) → Download Diagnostics

The diagnostics include:

- Device information (model, firmware, network status)
- Multiroom group configuration and roles
- Media playback state and current sources
- **HTTP polling statistics** (total polls, success rate, response times)
- **Command statistics** (total commands, success rate, failure tracking)
- UPnP subscription status and health
- EQ settings and sound modes
- Audio output configuration

**All sensitive data (IP addresses, MAC addresses, network names) is automatically redacted.**

### Real-time Device Monitoring

For real-time device monitoring and debugging, use the `monitor_cli` tool from the `pywiim` library:

```bash
# Install pywiim
pip3 install pywiim

# Monitor a device (replace with your device IP)
python3 -m pywiim.cli.monitor_cli YOUR_DEVICE_IP
```

This shows real-time device state including audio output mode, playback state, and multiroom status. Use `--verbose` for detailed logging or `--no-tui` for scrolling log output. Press `Ctrl+C` to stop.

## Documentation

- **[📚 Quick Start Guide](docs/README.md)** - Installation and basic setup
- **[🎛️ User Guide](docs/user-guide.md)** - Complete features and configuration
- **[🤖 Automation Cookbook](docs/automation-cookbook.md)** - Ready-to-use automation patterns
- **[❓ FAQ & Troubleshooting](docs/faq-and-troubleshooting.md)** - Quick answers to common questions and solutions to common problems

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

- **[pywiim](https://github.com/mjcumming/pywiim)** - The brand new, fully async Python library we wrote that powers this integration's device communication
- [python-linkplay](https://github.com/Velleman/python-linkplay) - Comprehensive LinkPlay library (inspiration for pywiim)
- [LinkPlay HA Integration](https://github.com/nagyrobi/home-assistant-custom-components-linkplay) - Original LinkPlay integration

## License

MIT License - see [LICENSE](LICENSE) for details.

---

_This integration is not affiliated with WiiM or LinkPlay. All trademarks belong to their respective owners._
