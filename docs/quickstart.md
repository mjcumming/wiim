# WiiM Integration - Quick Start Guide

Transform your WiiM and LinkPlay speakers into powerful Home Assistant media players with full multiroom support.

## ✨ Key Features

- 🎵 **Complete Media Control** - Play, pause, volume, source selection
- 🏠 **Virtual Group Players** - Single entity controls entire speaker groups
- 📻 **Media Browser** - Browse presets, quick stations, and HA media sources
- 🎛️ **Advanced Audio** - EQ presets, custom curves, source management
- 🔧 **No Dependencies** - Uses only Home Assistant's built-in libraries
- 🚀 **Auto-Discovery** - Automatically finds speakers on your network
- 🎯 **Smart Source Detection** - Shows "Spotify" instead of "WiFi"
- ⚡ **Adaptive Polling** - 1-second updates during playback

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

## 🚀 Initial Setup

### Auto-Discovery

The integration automatically finds WiiM speakers on your network using UPnP/SSDP and Zeroconf.

1. **Settings** → **Devices & Services**
2. New WiiM devices appear in discovered integrations
3. Click **Configure** and follow setup wizard

### Manual Configuration

If auto-discovery doesn't work:

1. **Add Integration** manually
2. Enter speaker IP address when prompted
3. Integration validates connection and creates entities

## 🎵 Basic Usage

### Essential Entities

Each speaker creates these entities:

- **Media Player** - `media_player.{device_name}` - Full playback control
- **Group Coordinator** - `media_player.{device_name}_group_coordinator` - Controls entire group when master
- **Role Sensor** - `sensor.{device_name}_multiroom_role` - Shows `Solo`/`Master`/`Slave` status

### Quick Multiroom Setup

1. Open any WiiM media player card
2. Click the **group icon** (🔗)
3. Select speakers to join the group

Or use services:

```yaml
service: media_player.join
target:
  entity_id: media_player.living_room
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom
```

The group coordinator entity (`media_player.living_room_group_coordinator`) automatically appears when groups form!

## 📚 Complete Documentation

### Core Guides

- **[📖 User Guide](docs/user-guide.md)** - All features and configuration options
- **[🎭 Group Behavior](docs/group-behavior.md)** - Deep dive into multiroom audio
- **[🎵 Media Formats](docs/media-formats.md)** - Supported formats and streaming services
- **[🛠️ Services Reference](docs/services.md)** - Complete service documentation

### Practical Resources

- **[🤖 Automation Cookbook](docs/automation-examples.md)** - Ready-to-use automations
- **[❓ FAQ](docs/faq.md)** - Quick answers to common questions
- **[🔧 Troubleshooting](docs/troubleshooting.md)** - Fix common issues
- **[📊 Diagnostics](docs/diagnostics.md)** - Understanding sensor data

## 🎛️ Quick Examples

### Virtual Group Control

```yaml
# Single entity controls entire group!
type: media-control
entity: media_player.living_room_group_coordinator
```

### Smart Automations

```yaml
# Target only group masters
service: media_player.volume_set
target:
  entity_id: >
    {{ states.sensor
       | selectattr('entity_id', 'match', '.*_multiroom_role$')
       | selectattr('state', 'eq', 'Master')
       | map(attribute='entity_id')
       | map('replace', 'sensor.', 'media_player.')
       | map('replace', '_multiroom_role', '_group_coordinator')
       | list }}
data:
  volume_level: 0.5
```

### Media Browser

Access through any media player card:

- **Presets** - Hardware presets from WiiM app
- **Quick Stations** - Your custom stations (see [FAQ](docs/faq.md#tips--tricks))
- **Media Library** - Browse HA media sources

## ⚠️ Breaking Changes (v2.0+)

If upgrading from v1.x:

- `number.{device}_group_volume` → Use `media_player.{device}_group_coordinator`
- `switch.{device}_group_mute` → Use `media_player.{device}_group_coordinator`

See [Migration Guide](docs/faq.md#volume-questions) for details.

## 🔧 Troubleshooting

### Quick Fixes

**No devices found:**

- Ensure HA and speakers on same network/VLAN
- Check firewall allows UPnP (port 1900)
- Try manual IP configuration

**Groups not working:**

- Check all speakers have same firmware
- Use wired connection for master speaker
- Ensure multicast traffic allowed

**Connection errors:**

- Verify speaker IP hasn't changed
- Power cycle the speaker
- Check [Troubleshooting Guide](docs/troubleshooting.md)

### Debug Mode

```yaml
logger:
  logs:
    custom_components.wiim: debug
```

## 🙏 Support the Project

If this integration enhances your audio experience:

- ⭐ **Star the repo** on [GitHub](https://github.com/mjcumming/wiim)
- 🐛 **Report issues** with debug logs
- 💡 **Share** your automation examples
- 📖 **Contribute** documentation improvements
- 💬 **Join** the discussion on [HA Community](https://community.home-assistant.io/)

---

_This integration is not affiliated with WiiM or LinkPlay. All trademarks belong to their respective owners._
