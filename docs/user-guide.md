# WiiM Integration - User Guide

Complete guide to using your WiiM speakers with Home Assistant.

> **Built on [pywiim](https://github.com/mjcumming/pywiim)** - This integration uses the pywiim library for all device communication, providing reliable and feature-rich control of your speakers.

---

## Part 1: Essential Features

Everything you need for everyday use - playing music, controlling volume, and grouping speakers.

### 🎵 Basic Playback

**Play, Pause, and Stop**

```yaml
service: media_player.media_play
target:
  entity_id: media_player.living_room

service: media_player.media_pause
target:
  entity_id: media_player.living_room

service: media_player.media_stop
target:
  entity_id: media_player.living_room
```

**Next and Previous Track**

```yaml
service: media_player.media_next_track
target:
  entity_id: media_player.living_room

service: media_player.media_previous_track
target:
  entity_id: media_player.living_room
```

### 🔊 Volume Control

**Set Volume**

```yaml
service: media_player.volume_set
target:
  entity_id: media_player.living_room
data:
  volume_level: 0.5 # 0.0 to 1.0 (0% to 100%)
```

**Volume Up/Down**

```yaml
service: media_player.volume_up
target:
  entity_id: media_player.living_room

service: media_player.volume_down
target:
  entity_id: media_player.living_room
```

**Mute**

```yaml
service: media_player.volume_mute
target:
  entity_id: media_player.living_room
data:
  is_volume_muted: true
```

**Volume Step Size** - Configurable in device options (default: 5%)

### 📻 Playing Media

**Play from URL**

```yaml
service: wiim.play_url
target:
  entity_id: media_player.living_room
data:
  url: "http://ice2.somafm.com/groovesalad-128-mp3"
```

> **⚠️ Note:** WiiM devices accept play commands silently even if the stream fails (geo-blocked, invalid URL, etc.). If nothing plays, check that the device state changed to "playing". HTTP streams are more reliable than HTTPS. See [FAQ](faq-and-troubleshooting.md#q-i-sent-a-play-command-but-nothing-happened---no-error-shown) for troubleshooting.

**Play Preset** (configured in WiiM app)

```yaml
service: wiim.play_preset
target:
  entity_id: media_player.living_room
data:
  preset: 1 # Preset number 1-20
```

**Using Home Assistant Media Browser**

Access via any media player card → **Browse Media**:

- Hardware presets from WiiM app (with cover art)
- Home Assistant media sources
- Refreshes automatically every 30 seconds

### 🎚️ Audio Sources

**Switch Input Source**

```yaml
service: media_player.select_source
target:
  entity_id: media_player.living_room
data:
  source: "Bluetooth" # or "Line In", "Optical", "USB", etc.
```

**Smart Source Detection**

The integration shows what's actually playing instead of technical details:

| Display      | Actual Input | Description            |
| ------------ | ------------ | ---------------------- |
| Amazon Music | WiFi         | Streaming from Amazon  |
| Spotify      | WiFi         | Streaming from Spotify |
| AirPlay      | WiFi         | Casting from iOS/Mac   |
| Bluetooth    | Bluetooth    | Direct BT connection   |
| Line In      | Line In      | Physical audio input   |

### 🏠 Multiroom Grouping

**Understanding Speaker Roles**

Every speaker has a role that determines its behavior:

| Role       | What It Means              | What You See               |
| ---------- | -------------------------- | -------------------------- |
| **Solo**   | Playing independently      | Speaker works on its own   |
| **Master** | Controlling other speakers | Speaker is leading a group |
| **Slave**  | Following another speaker  | Speaker is part of a group |

**The Role Sensor** - Essential for automations:

```yaml
sensor.living_room_multiroom_role: "Master"
sensor.kitchen_multiroom_role: "Slave"
sensor.bedroom_multiroom_role: "Solo"
```

**Create a Group**

```yaml
service: media_player.join
target:
  entity_id: media_player.living_room # This becomes the master
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom
```

**Ungroup Speakers**

```yaml
service: media_player.unjoin
target:
  entity_id: media_player.living_room
```

### 👥 Group Coordinator (Virtual Group Master)

When a speaker becomes a master controlling other speakers, a special **group coordinator** entity automatically appears:

```yaml
media_player.living_room_group_coordinator
```

**What It Does:**

- Controls the entire group with one entity
- Automatically appears when a speaker has slaves
- Automatically disappears when the group is disbanded
- Shows group status and all member speakers

**Using the Group Coordinator:**

```yaml
# Control entire group volume
service: media_player.volume_set
target:
  entity_id: media_player.living_room_group_coordinator
data:
  volume_level: 0.5

# Mute entire group
service: media_player.volume_mute
target:
  entity_id: media_player.living_room_group_coordinator
data:
  is_volume_muted: true
```

**Group Volume Behavior:**

- Displays the **maximum volume** of any member
- Setting volume applies the same level to all speakers
- Individual speakers can still be adjusted separately

**Group Mute Behavior:**

- Group is muted only when **ALL** members are muted
- Muting the group mutes all speakers
- Unmuting the group unmutes all speakers

### 📱 Dashboard Cards

**Basic Media Control**

```yaml
type: media-control
entity: media_player.living_room
```

**Group Control**

```yaml
type: media-control
entity: media_player.living_room_group_coordinator
```

**System Status**

```yaml
type: entities
title: Speaker Status
entities:
  - sensor.living_room_multiroom_role
  - sensor.kitchen_multiroom_role
  - sensor.bedroom_multiroom_role
```

---

## Part 2: Advanced Features

Power user features for customization, automation, and advanced control.

### ⏰ Alarms and Timers

**Sleep Timer** (WiiM devices only)

Set a timer to automatically stop playback:

```yaml
# Set sleep timer for 30 minutes
service: wiim.set_sleep_timer
target:
  entity_id: media_player.living_room
data:
  sleep_time: 1800  # Seconds (0-7200)

# Clear sleep timer
service: wiim.clear_sleep_timer
target:
  entity_id: media_player.living_room
```

**Alarm Clock** (WiiM devices only)

WiiM devices support 3 alarm slots (0-2). Alarm times must be in **UTC format**.

```yaml
# Create a daily alarm at 7:00 AM UTC
service: wiim.update_alarm
target:
  entity_id: media_player.bedroom
data:
  alarm_id: 0
  time: "07:00:00"  # UTC time (HH:MM:SS)
  trigger: "daily"  # or "2" for ALARM_TRIGGER_DAILY
  operation: "playback"  # or "1" for ALARM_OP_PLAYBACK

# Update existing alarm (change time only)
service: wiim.update_alarm
target:
  entity_id: media_player.bedroom
data:
  alarm_id: 0
  time: "08:00:00"  # New UTC time
```

**Important:** Alarm times are in UTC. Convert your local time to UTC when setting alarms. For example, 7:00 AM EST (UTC-5) would be `12:00:00` in UTC.

### 🎚️ Equalizer Control

**Select EQ Preset**

Available presets: Flat, Rock, Jazz, Classical, Pop, Bass, Treble, Vocal

```yaml
service: media_player.select_sound_mode
target:
  entity_id: media_player.living_room
data:
  sound_mode: "Rock"
```

**Custom EQ** (10-band control: 31.5Hz to 16kHz)

```yaml
service: wiim.set_eq
target:
  entity_id: media_player.living_room
data:
  preset: "custom"
  custom_values: [-2, 0, 2, 3, 1, 0, 0, -1, 2, 4] # -12dB to +12dB per band
```

### 🔊 Audio Output Modes

**Select Output Mode**

Available options vary by device model:

```yaml
service: select.select_option
target:
  entity_id: select.living_room_audio_output_mode
data:
  option: "Line Out" # or "Optical Out", "Coaxial Out", "HDMI ARC"
```

**Bluetooth Output**

Connect to previously paired Bluetooth devices:

```yaml
# Select paired Bluetooth device
service: select.select_option
target:
  entity_id: select.living_room_audio_output_mode
data:
  option: "BT Device 1 - TOZO-T6"
```

**Note:** Bluetooth pairing must be done via the WiiM app. Home Assistant can only connect to already-paired devices.

### 🎤 Text-to-Speech

The integration supports TTS announcements with automatic group coordination. See the [TTS Guide](TTS_GUIDE.md) for complete details.

**Basic TTS Example:**

```yaml
service: media_player.play_media
target:
  entity_id: media_player.living_room
data:
  media_content_type: music
  media_content_id: "media-source://tts?message=Hello, this is a test"
  announce: true
```

### 🔧 Device Maintenance

**Reboot Device**

```yaml
service: wiim.reboot_device
target:
  entity_id: media_player.living_room
```

**Sync Time**

```yaml
service: wiim.sync_time
target:
  entity_id: media_player.living_room
```

### 🎯 Group-Aware Automations

**Target Only Master Speakers**

```yaml
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

**Detect Role Changes**

```yaml
automation:
  - alias: "Group Formation Alert"
    trigger:
      platform: state
      entity_id: sensor.living_room_multiroom_role
      to: "Master"
    action:
      service: notify.mobile_app
      data:
        message: "Living Room is now controlling a speaker group"
```

### 📋 Queue Management

Queue management requires UPnP support. Check device capabilities in the entity attributes.

> **⚠️ Limited Device Support**: Full queue browsing (`get_queue`) only works on **WiiM Amp and WiiM Ultra with a USB drive connected**. These devices expose the UPnP ContentDirectory service required for queue retrieval. Other devices (Mini, Pro, Pro Plus) function as UPnP renderers only and do not support queue browsing. Queue position and count are available on all devices via the `queue_position` and `queue_count` entity attributes.
>
> See [pywiim documentation](https://github.com/mjcumming/pywiim/tree/main/docs) for technical details.

**Play from Queue Position** (requires UPnP AVTransport)

```yaml
service: wiim.play_queue
target:
  entity_id: media_player.living_room
data:
  queue_position: 0 # 0-based index
```

**Remove from Queue** (requires UPnP AVTransport)

```yaml
service: wiim.remove_from_queue
target:
  entity_id: media_player.living_room
data:
  queue_position: 3 # Remove item at position 3
```

**Get Queue Contents** (WiiM Amp/Ultra + USB only)

```yaml
service: wiim.get_queue
target:
  entity_id: media_player.living_room
# Returns: queue items with title, artist, album, URL
# Only works on WiiM Amp/Ultra with USB drive connected
```

**Check Queue Support**

You can check if your device supports queue operations by looking at the `capabilities` attribute:

```yaml
# In a template or automation
{{ state_attr('media_player.living_room', 'capabilities').queue_browse }}  # Full queue retrieval
{{ state_attr('media_player.living_room', 'capabilities').queue_add }}     # Add/remove from queue
```

### ⚠️ Unofficial API Actions

These actions use reverse-engineered endpoints that may not work on all firmware versions. Test thoroughly before using in production.

**Audio Settings**

```yaml
# Channel balance (-1.0 left to 1.0 right)
service: wiim.set_channel_balance
target:
  entity_id: media_player.living_room
data:
  balance: 0.2 # Slightly right
```

**Bluetooth Scanning**

```yaml
# Scan for nearby Bluetooth devices
service: wiim.scan_bluetooth
target:
  entity_id: media_player.living_room
data:
  duration: 5 # Scan for 5 seconds (3-10 recommended)
```

---

## Part 3: Configuration & Reference

Complete reference for all entities, configuration options, and technical details.

### 📊 Available Entities

**Media Players**

- `media_player.{device_name}` - Main device control
- `media_player.{device_name}_group_coordinator` - Virtual group master (appears when master has slaves)

**Sensors** (always created)

- `sensor.{device_name}_multiroom_role` - Current role (Solo/Master/Slave)
- `sensor.{device_name}_input` - Current audio input source
- `sensor.{device_name}_firmware` - Firmware version
- `sensor.{device_name}_diagnostic` - Comprehensive device health

**Audio Quality Sensors** (when supported)

- `sensor.{device_name}_audio_quality` - Overall quality indicator
- `sensor.{device_name}_sample_rate` - Sample rate (Hz)
- `sensor.{device_name}_bit_depth` - Bit depth
- `sensor.{device_name}_bit_rate` - Bit rate (kbps)

**Bluetooth Sensor** (when supported)

- `sensor.{device_name}_bluetooth_output` - Bluetooth output status

**Selects**

- `select.{device_name}_audio_output_mode` - Output mode selection (Line Out, Optical, Bluetooth, etc.)

**Switches**

- Various control switches (mute, shuffle, repeat)

**Buttons** (optional - enable in device options)

- `button.{device_name}_reboot` - Restart device
- `button.{device_name}_sync_time` - Sync device clock

**Lights** (device dependent)

- `light.{device_name}_status_led` - Control front panel LED

**Binary Sensors** (optional - enable network monitoring)

- `binary_sensor.{device_name}_connectivity` - Connection status

### ⚙️ Configuration Options

Configure via **Device Options** (Settings → Devices & Services → WiiM Audio → Device → Configure):

| Option                         | Default | Range  | Description                       |
| ------------------------------ | ------- | ------ | --------------------------------- |
| **Volume Step**                | 5%      | 1-50%  | Volume button increment           |
| **Enable Maintenance Buttons** | Off     | On/Off | Show reboot and sync time buttons |
| **Enable Network Monitoring**  | Off     | On/Off | Show connectivity binary sensor   |

### 🌐 Network Requirements

**Required Ports**

- **HTTPS**: 443 (primary API)
- **HTTP**: 8080 (fallback)
- **UPnP/SSDP**: 1900 (discovery)

**Network Setup**

- Home Assistant and speakers on same subnet
- Multicast traffic allowed between devices
- DHCP reservations recommended for stable IPs

### 📋 Supported Audio Formats

**Lossless**

- FLAC, WAV, ALAC up to 24-bit/192kHz

**Compressed**

- MP3, AAC, OGG up to 320kbps

**Streaming**

- HTTP/HTTPS streams, HLS, DLNA

### 🔍 Diagnostics

Download comprehensive diagnostic information:

1. **Device Diagnostics**: Settings → Devices & Services → WiiM Audio → Device → Download Diagnostics
2. **Integration Diagnostics**: Settings → Devices & Services → WiiM Audio → ⋮ → Download Diagnostics

Includes device info, group configuration, playback state, polling statistics, and more. All sensitive data is automatically redacted.

### 🐛 Debug Logging

```yaml
logger:
  logs:
    custom_components.wiim: debug
    pywiim: debug
```

### 💡 Best Practices

**Network Optimization**

- Use DHCP reservations for stable IP addresses
- Ensure strong WiFi signal for all devices
- Allow multicast traffic between speakers
- Keep HA and speakers on same subnet

**Automation Guidelines**

- Always check role sensor before group commands
- Use group coordinators for group operations
- Add small delays between group operations
- Include error handling with `continue_on_error: true`

**Performance Tips**

- Integration uses adaptive polling (fast during playback, slow when idle)
- Monitor entity count (3-4 entities per speaker typically)
- Test multiroom functionality regularly
- Keep speaker firmware updated

### 🎵 Music Assistant Integration

**Compatible Entities:**

- Use individual speaker entities: `media_player.{device_name}`
- **Do not** use group coordinators with Music Assistant

**Why?**

- Group coordinators are marked with `music_assistant_excluded: true`
- Music Assistant provides its own group management
- Individual speakers integrate seamlessly with Music Assistant

---

## 📚 Related Documentation

- **[Quick Start Guide](README.md)** - Installation and first steps
- **[Automation Cookbook](automation-cookbook.md)** - Ready-to-use automation examples
- **[FAQ & Troubleshooting](faq-and-troubleshooting.md)** - Common questions and solutions
- **[TTS Guide](TTS_GUIDE.md)** - Text-to-speech setup and usage

---

**Need Help?** Check the [FAQ & Troubleshooting](faq-and-troubleshooting.md) guide or visit the [GitHub Discussions](https://github.com/mjcumming/wiim/discussions).
