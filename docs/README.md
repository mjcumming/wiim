# WiiM Integration - Quick Start Guide

Transform your WiiM and LinkPlay speakers into powerful Home Assistant media players with full multiroom support.

## 📋 Quick Navigation

- [✨ Key Features](#-key-features)
- [📦 Installation](#-installation)
- [🚀 Quick Setup](#-quick-setup)
- [🏠 Multiroom Setup](#-quick-multiroom-setup)
- [🔧 Troubleshooting](#-troubleshooting)
- [📚 Complete Documentation](#-complete-documentation)

## ✨ Key Features

- 🎵 **Complete Media Control** - Play, pause, volume, source selection
- 🏠 **Virtual Group Coordinators** - Single entity controls entire speaker groups
- 📻 **Media Browser** - Browse presets and HA media sources
- 🎛️ **Advanced Audio** - EQ presets and source management
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

   - Open HACS → Integrations → ⋮ → Custom repositories
   - Add: `https://github.com/mjcumming/wiim`
   - Category: Integration

2. **Install Integration**

   - Search for "WiiM Audio" → Download → Restart HA

3. **Add Integration**
   - Settings → Devices & Services → Add Integration
   - Search "WiiM Audio" → Follow setup wizard

### Manual Installation

1. Download latest release from [GitHub](https://github.com/mjcumming/wiim/releases)
2. Extract to `/config/custom_components/wiim/`
3. Restart Home Assistant
4. Add integration via Settings → Devices & Services

## 🚀 Quick Setup

### Auto-Discovery

Speakers are automatically found using UPnP/SSDP. Go to **Settings** → **Devices & Services** and configure discovered devices.

### Manual Configuration

If auto-discovery doesn't work, add integration manually and enter the speaker's IP address.

## 🎵 Essential Entities

Each speaker creates:

- **Media Player** - `media_player.{device_name}` - Full device control
- **Group Coordinator** - `media_player.{device_name}_group_coordinator` - Controls entire group (appears when master with slaves)
- **Role Sensor** - `sensor.{device_name}_multiroom_role` - Shows `Solo`/`Master`/`Slave` status

## 🏠 Quick Multiroom Setup

### Create Groups

```yaml
service: media_player.join
target:
  entity_id: media_player.living_room
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom
```

### Control Groups

The group coordinator entity automatically appears:

```yaml
# Control entire group with single entity
type: media-control
entity: media_player.living_room_group_coordinator
```

### Smart Automations

```yaml
# Target only group masters for efficiency
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

### Debug Mode

```yaml
logger:
  logs:
    custom_components.wiim: debug
```

## 📚 Complete Documentation

- **[🎛️ User Guide](user-guide.md)** - All features and configuration options
- **[🤖 Automation Cookbook](automation-cookbook.md)** - Ready-to-use automation patterns
- **[❓ FAQ](FAQ.md)** - Quick answers to common questions
- **[🔧 Troubleshooting](troubleshooting.md)** - Fix common issues and network problems

## 🎯 Pro Tips

1. **Use Role Sensors** - Check `sensor.{device}_multiroom_role` before sending commands
2. **Group Coordinators** - Use `*_group_coordinator` entities for group operations
3. **DHCP Reservations** - Assign static IPs to prevent connection issues
4. **Media Browser** - Access presets through any media player card → Browse Media

## 🙏 Support the Project

If this integration enhances your audio experience:

- ⭐ **Star the repo** on [GitHub](https://github.com/mjcumming/wiim)
- 🐛 **Report issues** with debug logs
- 💡 **Share** automation examples
- 💬 **Join** discussions on [HA Community](https://community.home-assistant.io/)

---

_This integration is not affiliated with WiiM or LinkPlay. All trademarks belong to their respective owners._
