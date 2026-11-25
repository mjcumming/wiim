# WiiM Integration - Quick Start Guide

WiiM Audio adds WiiM and other LinkPlay speakers to Home Assistant as media players with multiroom grouping.

Device communication is handled by the [pywiim](https://github.com/mjcumming/pywiim) library.

## What You Can Do

The essentials:

- Play, pause, stop, turn off, and control your music
- Adjust volume and mute speakers
- Group speakers together for multiroom audio
- Browse and play your presets
- Switch between audio sources (Bluetooth, AirPlay, Line In)

When you're ready for more:

- Set alarms and sleep timers (WiiM devices)
- Change equalizer settings
- Enqueue URLs and read the queue position and count (device dependent)
- Build multiroom automations
- Watch audio quality and device health
- Make text-to-speech announcements

## Installation

### Marketplace or HACS (recommended)

1. Go to **Settings** > **Marketplace** and search for "WiiM Audio". On Home Assistant 2026.10 and older, open HACS from the sidebar and search there.
2. Select **Install**. In HACS the button is **Download**.
3. Restart Home Assistant.
4. Go to **Settings** > **Devices & services** > **Add integration**, search for **WiiM** and follow the dialog.

### Manual Installation

1. Download `wiim.zip` from the [latest release](https://github.com/mjcumming/wiim/releases/latest)
2. Extract it to `/config/custom_components/wiim/`
3. Restart Home Assistant
4. Add the integration under **Settings** > **Devices & services**

### Beta versions

Betas are published as GitHub pre-releases. Go to **Settings** > **Devices & services** > **Marketplace** (**HACS** on Home Assistant 2026.10 and older), open the WiiM Audio device, enable its **Pre-release** entity and turn it on. Turn it off to stay on stable releases.

## Quick Start

### Your First Speaker

Speakers are discovered automatically. Go to **Settings** > **Devices & services** and add the discovered devices.

If your speaker isn't found, add it by IP address: **Settings** > **Devices & services** > **Add integration** > **WiiM**.

### Playing Music

Use any Home Assistant media player card or action:

```yaml
action: media_player.media_play
target:
  entity_id: media_player.living_room
```

### Grouping Speakers

Create a multiroom group:

```yaml
action: media_player.join
target:
  entity_id: media_player.living_room
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom
```

The group master entity is shown while that speaker leads a group, and hidden when it doesn't:

```yaml
# Control the whole group with one entity
action: media_player.volume_set
target:
  entity_id: media_player.living_room_group_master
data:
  volume_level: 0.5
```

### Ungrouping Speakers

Return a speaker to independent playback:

```yaml
action: media_player.unjoin
target:
  entity_id: media_player.living_room
```

## Understanding Your Entities

Every speaker gets these entities:

- `media_player.{device_name}` - Your speaker (use this for Music Assistant)
- `media_player.{device_name}_group_master` - Group master (hidden unless this speaker leads a group)
- `sensor.{device_name}_multiroom_role` - Shows if the speaker is Solo, Master, or Slave
- `sensor.{device_name}_current_input` - The current source
- `light.{device_name}_led` - The status LED
- Device Status and Firmware diagnostic sensors

These are created only when the speaker supports them:

- Audio Output Mode, EQ Preset, Parametric EQ Preset, RoomFit, Channel, DAC Filter and Standby Timeout selects
- Subwoofer, Main speaker bass and 12V trigger switches
- Subwoofer Level and Channel balance numbers
- Display light
- Firmware Update (WiiM devices)
- Bluetooth Output and audio quality sensors (sample rate, bit depth, bit rate)

The Reboot and Sync Time buttons are created when you turn on the Maintenance Buttons option.

## Tips

1. Check `sensor.{device}_multiroom_role` to see if a speaker is Solo, Master (leading a group), or Slave (following a master).

2. When controlling a multiroom group, use the `*_group_master` entity instead of individual speakers.

3. Give your speakers DHCP reservations so their IP addresses don't change.

4. If you use Music Assistant, add only the individual speaker entities, and leave the group master entities out.

## Supported Devices

- **WiiM**: Mini, Pro, Pro Plus, Amp, Amp Pro, Amp Ultra, Ultra, Sound, Sound Lite
- **LinkPlay compatible**: Arylic, Audio Pro, Dayton Audio, DOSS, Edifier (MS50A), iEast, and others
- **Requirements**: Home Assistant 2024.12.0+ on the same network as the speakers

## Documentation

- **[User Guide](user-guide.md)** - Feature reference and configuration
- **[Automation Cookbook](automation-cookbook.md)** - Automation examples
- **[FAQ & Troubleshooting](faq-and-troubleshooting.md)** - Quick answers and solutions
- **[TTS Guide](TTS_GUIDE.md)** - Text-to-speech announcements

## Acknowledgments

- **[pywiim](https://github.com/mjcumming/pywiim)** - The Python library that handles WiiM/LinkPlay device communication
- **WiiM** - For the audio hardware
- **LinkPlay** - For the underlying multiroom protocol
- **Home Assistant Community** - For feedback, testing, and contributions

## Disclaimer

This integration is not affiliated with WiiM or LinkPlay. All trademarks belong to their respective owners.

---

**Having issues?** Check the [FAQ & Troubleshooting](faq-and-troubleshooting.md) guide or enable debug logging:

```yaml
logger:
  logs:
    custom_components.wiim: debug
    pywiim: debug
```
