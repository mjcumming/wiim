# WiiM Integration - Complete User Guide

Comprehensive guide covering all features, configuration, and usage patterns for the WiiM Audio integration.

## 🎵 Core Features

### Media Player Controls

**Playback Controls**

- **Play/Pause/Stop**: Standard media controls
- **Next/Previous Track**: Navigate playlists
- **Seek**: Jump to specific position
- **Shuffle/Repeat**: Toggle playback modes

**Volume Management**

- **Absolute Volume**: Set exact levels (0-100%)
- **Relative Steps**: Configurable increment size
- **Mute Control**: Independent mute toggle
- **Group Volume**: Synchronized multi-speaker control

**Smart Source Detection**

Shows meaningful information instead of technical details:

| What You See        | Technical Reality | When Used              |
| ------------------- | ----------------- | ---------------------- |
| **Amazon Music** 🎵 | WiFi              | Streaming from Amazon  |
| **Spotify** 🎵      | WiFi              | Streaming from Spotify |
| **AirPlay** 📱      | WiFi              | Casting from iOS/Mac   |
| **Bluetooth** 📱    | Bluetooth         | Direct BT connection   |
| **Line In** 🔌      | Line In           | Physical audio input   |

### Audio Enhancement

**Equalizer Control**

- **Presets**: Flat, Rock, Jazz, Classical, Pop, Bass, Treble, Vocal
- **Custom EQ**: 10-band control (-12dB to +12dB)
- **Real-time**: Immediate audio changes

**Format Support**

- **Lossless**: FLAC, WAV, ALAC up to 24-bit/192kHz
- **Compressed**: MP3, AAC, OGG
- **Streaming**: All major services supported

## 🏠 Multiroom Audio

### Understanding Speaker Roles

Every WiiM speaker has a role that determines its behavior:

| Role       | Description         | Behavior                                     |
| ---------- | ------------------- | -------------------------------------------- |
| **Solo**   | Independent speaker | Plays its own content, controls only itself  |
| **Master** | Group coordinator   | Controls group playback, synchronizes slaves |
| **Slave**  | Group member        | Follows master's playback and timing         |

### Essential Role Sensor

**Critical for automation** - Always visible, never hidden:

```yaml
sensor.living_room_multiroom_role: "Master"
sensor.kitchen_multiroom_role: "Slave"
sensor.bedroom_multiroom_role: "Solo"
```

Use in automations to target only masters or detect group changes.

### Group Coordinator Entities

When a speaker becomes master **with slaves**, a virtual group coordinator appears:

```yaml
media_player.living_room_group_coordinator
```

**Key Features:**

- Only exists when actively coordinating a group (master + slaves)
- Provides unified control for volume, mute, and playback
- Shows member details in attributes
- Automatically appears/disappears with group changes

### Creating Groups

**Method 1: Home Assistant Service**

```yaml
service: media_player.join
target:
  entity_id: media_player.living_room # Becomes master
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom
```

**Method 2: WiiM Home App**

- Groups sync to HA automatically within 5 seconds
- Useful for initial setup and testing

### Group Volume Behavior

The group coordinator displays the **maximum volume** of any member:

```yaml
# Example: Master at 80%, Slave at 40%
# Group coordinator shows: 80% (the maximum)
# Set group volume to 60%
# Result: Both speakers set to 60%
```

**Individual control** remains available:

```yaml
# Adjust single speaker within group
service: media_player.volume_set
target:
  entity_id: media_player.kitchen
data:
  volume_level: 0.3
```

### Group Mute Behavior

A group is muted **only when ALL members are muted**:

```yaml
# Mute entire group
service: media_player.volume_mute
target:
  entity_id: media_player.living_room_group_coordinator
data:
  is_volume_muted: true
# Result: ALL speakers muted
```

## ⚙️ Configuration

### Device Options

Configure each speaker via **Configure** button:

| Option          | Default | Range | Description             |
| --------------- | ------- | ----- | ----------------------- |
| **Volume Step** | 5%      | 1-50% | Volume button increment |

### Essential Entities Created

**Always Available:**

- `media_player.{device_name}` - Main device control
- `sensor.{device_name}_multiroom_role` - Group role status
- `media_player.{device_name}_group_coordinator` - Group controller (when master with slaves)

**Optional:**

- `button.{device_name}_reboot` - Device restart
- `button.{device_name}_sync_time` - Time synchronization

### Network Requirements

**Required Ports**

- **HTTPS**: 443 (primary API)
- **HTTP**: 8080 (fallback)
- **UPnP/SSDP**: 1900 (discovery)

**Network Setup**

- Home Assistant and speakers on same subnet
- Multicast traffic allowed between devices
- DHCP reservations recommended for stable IPs

## 🎛️ Services Reference

### WiiM-Specific Services

**`wiim.play_preset`** - Play hardware preset (1-20)

```yaml
service: wiim.play_preset
target:
  entity_id: media_player.living_room
data:
  preset: 1
```

**`wiim.play_url`** - Play from URL (radio streams, files)

```yaml
service: wiim.play_url
target:
  entity_id: media_player.living_room
data:
  url: "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_two"
```

**`wiim.set_eq`** - Configure equalizer

```yaml
# Use preset
service: wiim.set_eq
target:
  entity_id: media_player.living_room
data:
  preset: "rock"

# Custom EQ (10 bands: 31.5Hz to 16kHz)
service: wiim.set_eq
target:
  entity_id: media_player.living_room
data:
  preset: "custom"
  custom_values: [-2, 0, 2, 3, 1, 0, 0, -1, 2, 4]
```

**`wiim.reboot_device`** - Restart device

```yaml
service: wiim.reboot_device
target:
  entity_id: media_player.living_room
```

**`wiim.sync_time`** - Sync device clock

```yaml
service: wiim.sync_time
target:
  entity_id: media_player.living_room
```

### Standard Media Player Services

All standard HA media player services work:

```yaml
# Volume control
service: media_player.volume_set
target:
  entity_id: media_player.living_room
data:
  volume_level: 0.5

# Playback control
service: media_player.media_play
service: media_player.media_pause
service: media_player.media_stop

# Source selection
service: media_player.select_source
target:
  entity_id: media_player.living_room
data:
  source: "Bluetooth"

# Group management
service: media_player.join
service: media_player.unjoin
```

## 📱 Dashboard Integration

### Basic Media Control

```yaml
type: media-control
entity: media_player.living_room
```

### Group Coordinator Control

```yaml
# Control entire group with single card
type: media-control
entity: media_player.living_room_group_coordinator
```

### Group Management Interface

```yaml
# Group preset selector
input_select:
  wiim_groups:
    name: Speaker Groups
    options:
      - "All Solo"
      - "Downstairs"
      - "Whole House"
    initial: "All Solo"
```

### System Status Dashboard

```yaml
type: entities
title: WiiM System Status
entities:
  - entity: sensor.living_room_multiroom_role
    name: Living Room Role
  - entity: sensor.kitchen_multiroom_role
    name: Kitchen Role
  - entity: sensor.wiim_active_groups
    name: Active Groups
  - entity: sensor.wiim_playing_devices
    name: Playing Now
```

## 🎯 Advanced Patterns

### Group-Aware Automations

**Target Only Masters:**

```yaml
# Control group masters for efficiency
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

**Detect Group Changes:**

```yaml
automation:
  - alias: "Monitor Group Formation"
    trigger:
      platform: state
      entity_id: sensor.living_room_multiroom_role
      to: "Master"
    action:
      - service: notify.mobile_app
        data:
          message: "Living Room is now controlling a speaker group"
```

### Conditional Logic

```yaml
# Different behavior based on role
automation:
  - alias: "Smart Evening Music"
    trigger:
      platform: time
      at: "18:00:00"
    action:
      - service: media_player.volume_set
        target:
          entity_id: media_player.bedroom
        data:
          volume_level: >
            {% if is_state('sensor.bedroom_multiroom_role', 'Solo') %}
              0.3
            {% else %}
              0.2  {# Lower when part of group #}
            {% endif %}
```

### Template Helpers

```yaml
# Add to configuration.yaml
template:
  - sensor:
      name: "WiiM Active Groups"
      state: >
        {{ states.sensor
          | selectattr('entity_id', 'match', '.*multiroom_role$')
          | selectattr('state', 'equalto', 'Master')
          | list | length }}

  - sensor:
      name: "WiiM Playing Devices"
      state: >
        {{ states.media_player
          | selectattr('entity_id', 'match', 'media_player\..*')
          | selectattr('state', 'equalto', 'playing')
          | list | length }}
```

## 📊 Diagnostics & Monitoring

### Device Status Information

Each device provides a comprehensive status sensor:

```yaml
sensor.living_room_device_status: "Wi-Fi −55 dBm"
```

**Key Attributes Available:**

- `firmware` - Current firmware version
- `wifi_rssi` - Signal strength in dBm
- `uptime` - Seconds since last reboot
- `group` - Current multiroom role
- `connection` - wifi/wired connection type

### Health Monitoring

```yaml
# Weekly maintenance automation
automation:
  - alias: "WiiM Health Check"
    trigger:
      platform: time
      at: "03:00:00"
    condition:
      platform: time
      weekday: sun
    action:
      - service: wiim.sync_time
        target:
          entity_id: all
```

## 🛠️ Best Practices

### Network Optimization

- Use DHCP reservations for stable IP addresses
- Ensure strong WiFi signal for all devices
- Allow multicast traffic between speakers
- Keep HA and speakers on same subnet

### Automation Guidelines

- Always check role sensor before sending group commands
- Use group coordinators for group operations
- Add small delays between group operations
- Include error handling with `continue_on_error: true`

### Performance Tips

- Use adaptive polling efficiently (integration handles this)
- Monitor entity count (3 entities per speaker with groups enabled)
- Test multiroom functionality regularly
- Keep speaker firmware updated

## 🎵 Media Browser

Access via any media player card → **Browse Media**:

- **Presets** - Hardware presets from WiiM app with cover art
- **Quick Stations** - Your custom radio stations
- **Media Sources** - Browse HA media library

The preset list refreshes every 30 seconds with names and artwork from the WiiM app.

## 🔧 Maintenance

### Routine Tasks

- **Monthly**: Check device firmware updates
- **Monthly**: Review network performance
- **As Needed**: Update DHCP reservations

### Error Recovery

```yaml
# Restore groups after network issues
automation:
  - alias: "Reform Groups After Network Issue"
    trigger:
      platform: state
      entity_id: binary_sensor.network_connected
      from: "off"
      to: "on"
      for: "00:00:30"
    action:
      - delay: "00:00:30"
      - service: script.restore_speaker_groups
```

This guide covers essential usage patterns. For ready-to-use automation examples, see [Automation Cookbook](automation-cookbook.md). For troubleshooting, see [Troubleshooting Guide](troubleshooting.md).
