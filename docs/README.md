# WiiM Integration - Quick Start Guide

Transform your WiiM and LinkPlay speakers into powerful Home Assistant media players with seamless multiroom audio.

> **Built on [pywiim](https://github.com/mjcumming/pywiim)** - This integration leverages the excellent pywiim library for all device communication, allowing us to focus on providing the best Home Assistant experience possible.

## 🎯 What You Can Do

**The Essentials (What Most Users Need)**

- 🎵 Play, pause, stop, turn off, and control your music
- 🔊 Adjust volume and mute speakers
- 🏠 Group speakers together for multiroom audio
- 📻 Browse and play your favorite presets
- 🎛️ Switch between audio sources (Bluetooth, AirPlay, Line In)

**Advanced Features (When You're Ready)**

- ⏰ Set alarms and sleep timers
- 🎚️ Customize equalizer settings
- 🔗 Create complex multiroom automations
- 📊 Monitor audio quality and device health
- 🎤 Text-to-speech announcements

## 📦 Installation

### Via HACS (Recommended)

1. **Install**
   - Open HACS → Integrations
   - Search for "WiiM Audio" → Download → Restart Home Assistant

2. **Configure**
   - Settings → Devices & Services → Add Integration
   - Search "WiiM Audio" → Follow setup wizard

### Manual Installation

1. Download latest release from [GitHub](https://github.com/mjcumming/wiim/releases)
2. Extract to `/config/custom_components/wiim/`
3. Restart Home Assistant
4. Add integration via Settings → Devices & Services

## 🚀 Quick Start

### Your First Speaker

Speakers are automatically discovered. Go to **Settings** → **Devices & Services** and configure discovered devices.

**Can't find your speaker?** Add it manually using its IP address (Settings → Devices & Services → Add Integration → WiiM Audio).

### Playing Music

Use any Home Assistant media player card or service:

```yaml
service: media_player.media_play
target:
  entity_id: media_player.living_room
```

### Grouping Speakers

Create a multiroom group:

```yaml
service: media_player.join
target:
  entity_id: media_player.living_room
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom
```

The **group coordinator** entity automatically appears when speakers are grouped:

```yaml
# Control entire group with one entity
service: media_player.volume_set
target:
  entity_id: media_player.living_room_group_coordinator
data:
  volume_level: 0.5
```

### Ungrouping Speakers

Return speakers to independent playback:

```yaml
service: media_player.unjoin
target:
  entity_id: media_player.living_room
```

## 🎛️ Understanding Your Entities

Each speaker creates these entities:

**Always Available:**

- `media_player.{device_name}` - Your speaker (use this for Music Assistant)
- `media_player.{device_name}_group_coordinator` - Virtual group master (appears when speaker controls other speakers)
- `sensor.{device_name}_multiroom_role` - Shows if speaker is Solo, Master, or Slave

**Optional (Based on Configuration):**

- Audio quality sensors (sample rate, bit depth)
- Bluetooth output sensor
- Firmware version sensor
- Diagnostic sensor
- Audio output mode selector
- Maintenance buttons (reboot, sync time)

## 💡 Pro Tips

1. **Use the Role Sensor** - Check `sensor.{device}_multiroom_role` to see if a speaker is Solo, Master (controlling a group), or Slave (following a master)

2. **Group Coordinators for Groups** - When controlling a multiroom group, use the `*_group_coordinator` entity instead of individual speakers

3. **DHCP Reservations** - Assign static IPs to your speakers to prevent connection issues

4. **Individual Speakers for Music Assistant** - If using Music Assistant, add only the individual speaker entities (not group coordinators)

## 🛠️ Supported Devices

- **WiiM**: Mini, Pro, Pro Plus, Amp, Ultra
- **LinkPlay Compatible**: Arylic, Dayton Audio, DOSS, iEast, and many more
- **Requirements**: Home Assistant 2024.12.0+ on same network as speakers

## 📚 Documentation

- **[User Guide](user-guide.md)** - Complete feature reference and configuration
- **[Automation Cookbook](automation-cookbook.md)** - Ready-to-use automation examples
- **[FAQ & Troubleshooting](faq-and-troubleshooting.md)** - Quick answers and solutions
- **[TTS Guide](TTS_GUIDE.md)** - Text-to-speech announcements

## 🙏 Acknowledgments

This integration wouldn't be possible without:

- **[pywiim](https://github.com/mjcumming/pywiim)** - The robust Python library handling all WiiM/LinkPlay device communication
- **WiiM** - For creating excellent audio hardware
- **LinkPlay** - For the underlying multiroom protocol
- **Home Assistant Community** - For feedback, testing, and contributions

## ⚠️ Disclaimer

This integration is not affiliated with WiiM or LinkPlay. All trademarks belong to their respective owners.

---

**Having Issues?** Check the [FAQ & Troubleshooting](faq-and-troubleshooting.md) guide or enable debug logging:

```yaml
logger:
  logs:
    custom_components.wiim: debug
    pywiim: debug
```
