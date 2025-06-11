# WiiM Integration - Complete User Guide

This guide covers all features and advanced configuration for the WiiM Audio integration.

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
Our integration shows meaningful source information:

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

### Understanding Multiroom Roles

**Critical Role Sensor** - Always visible, never hidden:

```yaml
sensor.living_room_multiroom_role: "Master"
sensor.kitchen_multiroom_role: "Slave"
sensor.bedroom_multiroom_role: "Solo"
```

**Role Meanings:**

- **Solo**: Independent speaker operation
- **Master**: Group leader controlling all slaves
- **Slave**: Group member following master

### Creating Groups

**Method 1: Native HA Grouping (Recommended)**

```yaml
service: media_player.join
target:
  entity_id: media_player.living_room # Becomes master
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom
```

**Method 2: UI Group Button**

1. Open any WiiM media player card
2. Click the group icon (chain link)
3. Select speakers to include

**Method 3: WiiM App**

- Create groups in official WiiM app
- Changes sync to Home Assistant automatically

### Group Volume Behavior

Group volume maintains relative relationships:

```yaml
# Before: Master 80%, Slave 40%
# Set group volume to 100%
# After: Master 100%, Slave 50% (scaled proportionally)
```

### Virtual Group Entities (Optional)

Enable per-device via **Configure** → **"Enable group control entity"**:

- **Entity**: `media_player.{device_name}_group`
- **Availability**: Only when device is master with slaves
- **Controls**: Unified playback and volume for entire group
- **Attributes**: Shows individual member status

## ⚙️ Configuration

### Device Options

Configure each speaker via **Configure** button:

| Option                   | Default | Range  | Description                 |
| ------------------------ | ------- | ------ | --------------------------- |
| **Volume Step**          | 5%      | 1-50%  | Volume button increment     |
| **Enable Group Control** | Off     | On/Off | Create virtual group entity |

### Entity Management

**Essential Entities (Always Created)**

- `media_player.{device_name}` - Main device control
- `sensor.{device_name}_multiroom_role` - Group role status

**Optional Entities**

- `button.{device_name}_reboot` - Device restart
- `button.{device_name}_sync_time` - Time synchronization
- `media_player.{device_name}_group` - Group controller (if enabled)

### Network Requirements

**Required Ports**

- **HTTPS**: 443 (primary API)
- **HTTP**: 8080 (fallback)
- **UPnP/SSDP**: 1900 (discovery)

**Network Setup**

- Home Assistant and speakers on same subnet
- Multicast traffic allowed between devices
- DHCP reservations recommended for stable IPs

## 🎛️ Dashboard Integration

### Basic Media Control

```yaml
type: media-control
entity: media_player.living_room
```

### Multi-Speaker Dashboard

```yaml
type: grid
columns: 2
cards:
  - type: media-control
    entity: media_player.living_room
  - type: media-control
    entity: media_player.kitchen
  - type: media-control
    entity: media_player.bedroom
  - type: media-control
    entity: media_player.living_room_group
```

### Group Control Buttons

```yaml
type: horizontal-stack
cards:
  - type: button
    tap_action:
      action: call-service
      service: script.wiim_party_mode
    name: Party Mode
    icon: mdi:party-popper
  - type: button
    tap_action:
      action: call-service
      service: script.wiim_ungroup_all
    name: Ungroup All
    icon: mdi:speaker-off
```

### System Status Template

```yaml
template:
  - sensor:
      name: "WiiM System Status"
      state: >
        {% set masters = states.sensor
          | selectattr('entity_id', 'match', '.*multiroom_role$')
          | selectattr('state', 'equalto', 'Master') | list %}
        {% set playing = states.media_player
          | selectattr('entity_id', 'match', 'media_player..*')
          | selectattr('state', 'equalto', 'playing') | list %}
        {% if masters | length > 0 %}
          {{ masters | length }} groups, {{ playing | length }} playing
        {% else %}
          {{ playing | length }} speakers active
        {% endif %}
```

## 🔧 Custom Services

### Media Services

```yaml
# Play hardware preset (1-6)
service: wiim.play_preset
target:
  entity_id: media_player.living_room
data:
  preset: 3

# Play URL
service: wiim.play_url
target:
  entity_id: media_player.living_room
data:
  url: "http://stream.radio.station/live"

# Set equalizer
service: wiim.set_eq
target:
  entity_id: media_player.living_room
data:
  preset: "rock"  # or "custom" with custom_values
```

### Device Services

```yaml
# Reboot device
service: wiim.reboot_device
target:
  entity_id: media_player.living_room

# Sync device time
service: wiim.sync_time
target:
  entity_id: media_player.living_room
```

### Group Services

```yaml
# Create group with specific members
service: wiim.create_group
target:
  entity_id: media_player.living_room
data:
  group_members:
    - media_player.kitchen
    - media_player.dining_room

# Disband group
service: wiim.disband_group
target:
  entity_id: media_player.living_room
```

## 📊 Monitoring & Diagnostics

### Entity Attributes

**Media Player Attributes**

```yaml
# Device information
firmware_version: "4.6.328252"
hardware_model: "UP2STREAM_PRO_V3"
ip_address: "192.168.1.100"
group_role: "master"
group_members: ["192.168.1.101", "192.168.1.102"]
available_sources: ["WiFi", "Bluetooth", "Line In"]
```

**Group Entity Attributes**

```yaml
# Individual member status
member_192_168_1_101_volume: 60
member_192_168_1_101_mute: false
member_192_168_1_101_name: "Kitchen"
```

### Debug Logging

```yaml
# configuration.yaml
logger:
  logs:
    custom_components.wiim: debug
    custom_components.wiim.api: debug
    custom_components.wiim.coordinator: debug
```

## 🎯 Best Practices

### Performance Optimization

- Use stable IP addresses (DHCP reservations)
- Enable group entities only where needed
- Monitor Home Assistant resource usage
- Test multiroom functionality regularly

### Automation Guidelines

```yaml
# Use role sensor for group-aware automation
automation:
  - alias: "Control Master Speaker Only"
    trigger:
      platform: state
      entity_id: input_boolean.play_everywhere
      to: "on"
    action:
      - service: media_player.media_play
        target:
          entity_id: >
            {% for entity in states.sensor %}
              {% if entity.entity_id.endswith('_multiroom_role') and entity.state == 'Master' %}
                {{ entity.entity_id.replace('sensor.', 'media_player.').replace('_multiroom_role', '') }}
              {% endif %}
            {% endfor %}
```

### Network Best Practices

- Keep all speakers on same subnet/VLAN
- Ensure strong WiFi signal for all devices
- Allow multicast traffic between speakers
- Monitor network performance regularly

## 🔄 Maintenance

### Routine Tasks

- **Monthly**: Check device firmware updates
- **Monthly**: Review entity organization
- **Monthly**: Test multiroom functionality
- **As Needed**: Update IP reservations

### Health Monitoring

```yaml
automation:
  - alias: "WiiM Health Check"
    trigger:
      platform: time
      at: "03:00:00"
    action:
      # Sync time on all devices
      - service: wiim.sync_time
        target:
          entity_id:
            - media_player.living_room
            - media_player.kitchen
            - media_player.bedroom
```

## 📚 Advanced Topics

### Scene-Based Audio

```yaml
scene:
  - name: "Dinner Party"
    entities:
      media_player.dining_room:
        state: "playing"
        volume_level: 0.4
      media_player.kitchen:
        state: "playing"
        volume_level: 0.3
      input_select.music_mode:
        state: "Ambient"
```

### Conditional Grouping

```yaml
automation:
  - alias: "Smart Evening Grouping"
    trigger:
      platform: time
      at: "18:00:00"
    condition:
      - condition: state
        entity_id: group.family
        state: "home"
    action:
      - service: media_player.join
        target:
          entity_id: media_player.living_room
        data:
          group_members:
            - media_player.dining_room
            - media_player.kitchen
```

## 📚 Preset Browser

Open the media-player card → three-dot menu → *Browse Media* → *Presets*.

You'll see all presets configured in the WiiM Home app (names, cover art) and can start playback with a single click.

The list refreshes every 30 seconds; empty slots are hidden automatically.

This guide covers the essential user-facing features. For automation examples, see [automation-examples.md](automation-examples.md). For technical details, see [../development/](../development/).
