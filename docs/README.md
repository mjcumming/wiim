# WiiM Integration - Quick Start Guide

Transform your WiiM and LinkPlay speakers into powerful Home Assistant media players with full multiroom support.

## ✨ Key Features

- 🎵 **Complete Media Control** - Play, pause, volume, source selection
- 🏠 **Multiroom Audio** - Synchronized playback across speaker groups
- 🎛️ **Group Volume Controls** - Dedicated entities for group control
- 🔧 **No Dependencies** - Uses only Home Assistant's built-in libraries
- 🚀 **Auto-Discovery** - Automatically finds speakers on your network
- 🎯 **Smart Source Detection** - Shows "Spotify" instead of "WiFi"

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

### Device Options

Configure each speaker individually via **Configure** button:

| Option                   | Default | Description                 |
| ------------------------ | ------- | --------------------------- |
| **Volume Step**          | 5%      | Volume button increment     |
| **Enable Group Control** | Off     | Create virtual group entity |

## 🎵 Basic Usage

### Essential Entities (Always Available)

- **Media Player** - `media_player.{device_name}` - Full device control
- **🔴 Role Sensor** - `sensor.{device_name}_multiroom_role` - Shows group status
  - States: `Solo`, `Master`, `Slave`
  - **CRITICAL** for multiroom understanding

### Smart Source Detection

Shows what you actually care about:

- **Amazon Music** 🎵 (instead of "WiFi")
- **Spotify** 🎵 (instead of "Network")
- **AirPlay** 📱 (instead of "Mode 99")

### Quick Multiroom Setup

1. Open any WiiM media player card
2. Click the **group icon** (chain link)
3. Select speakers to join the group

Or use automation:

```yaml
service: media_player.join
target:
  entity_id: media_player.living_room
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom
```

## 🎛️ Dashboard Integration

### Basic Media Control

```yaml
type: media-control
entity: media_player.living_room
```

### Group Control Dashboard

```yaml
type: horizontal-stack
cards:
  - type: button
    tap_action:
      action: call-service
      service: media_player.join
      service_data:
        entity_id: media_player.living_room
        group_members:
          - media_player.kitchen
          - media_player.bedroom
    name: Create Group
    icon: mdi:speaker-multiple
```

## 🔧 Troubleshooting

### Common Issues

**No devices found:**

- Ensure HA and speakers on same network
- Check firewall allows UPnP/SSDP (port 1900)
- Try manual IP configuration

**Connection errors:**

- Verify speaker IP is correct
- Check speaker is powered on
- Integration handles SSL certificates automatically

**Groups not working:**

- Verify all speakers on same firmware version
- Check network allows multicast traffic
- Use role sensor to monitor group status

### Debug Logging

```yaml
# configuration.yaml
logger:
  logs:
    custom_components.wiim: debug
```

## 📚 More Information

- **[Complete User Guide](user-guide.md)** - All features and advanced configuration
- **[Automation Examples](automation-examples.md)** - Ready-to-use scripts
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions
- **[GitHub Issues](https://github.com/mjcumming/wiim/issues)** - Report bugs
- **[HA Community](https://community.home-assistant.io/)** - Get help

## 🙏 Support the Project

If this integration helps you enjoy your music, consider:

- ⭐ **Star the repo** on GitHub
- 🐛 **Report issues** you encounter
- 💡 **Share automation examples**
- 📖 **Improve documentation**

---

_This integration is not affiliated with WiiM or LinkPlay. All trademarks belong to their respective owners._
