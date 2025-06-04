# Multiroom Audio Guide

Complete guide to WiiM multiroom audio setup and management in Home Assistant.

## 🎵 Overview

WiiM speakers use the LinkPlay protocol for synchronized multiroom audio. This integration provides multiple ways to view and manage multiroom groups:

1. **Native HA Grouping** - Built-in grouping button support
2. **Group Entities** - Optional virtual group controllers
3. **Enhanced Attributes** - Detailed group status in device info
4. **Custom Services** - Advanced group management through Developer Tools
5. **Script Templates** - Pre-made automation scripts

### 🚀 Recent Improvements (v0.4.16+)

✅ **Dramatically improved multiroom reliability** - Fixed critical API parsing bug that prevented proper group detection
✅ **Faster group status updates** - Masters now correctly detect and manage slave devices
✅ **Eliminated "Could not find master for slave" errors** - Slave devices reliably connect to their masters
✅ **More stable group operations** - Join/unjoin commands work consistently across all device combinations

## 🔧 Understanding Multiroom

### How It Works

- **Master Speaker**: Streams audio and controls the group
- **Slave Speakers**: Receive audio from the master speaker
- **Synchronization**: All speakers play audio in perfect sync (<1ms)
- **Group Control**: Volume and playback controlled from master or group entity

### Group Roles

| Role       | Description         | Control                    | Status Sensor                           |
| ---------- | ------------------- | -------------------------- | --------------------------------------- |
| **Solo**   | Independent speaker | Full control               | `sensor.speaker_multiroom_role: solo`   |
| **Master** | Group leader        | Controls group playback    | `sensor.speaker_multiroom_role: master` |
| **Slave**  | Group member        | Limited individual control | `sensor.speaker_multiroom_role: slave`  |

## 🚀 Quick Start: Creating Groups

### Method 1: Native HA Grouping (Recommended)

**Using the UI:**

1. Open any WiiM device's media player card
2. Click the **group icon** (chain link)
3. Select speakers to join the group

**Using Services:**

```yaml
# Create group via Home Assistant service
service: media_player.join
target:
  entity_id: media_player.living_room # Becomes master
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom
```

### Method 2: WiiM App

1. Use official WiiM or compatible LinkPlay app
2. Create group in the app
3. Changes automatically sync to Home Assistant within 5-10 seconds

### Method 3: Custom Services

Use these services in **Developer Tools > Services**:

```yaml
# Create new group
service: wiim.create_group
target:
  entity_id: media_player.living_room
data:
  group_members:
    - media_player.kitchen
    - media_player.dining_room

# Add device to existing group
service: wiim.add_to_group
target:
  entity_id: media_player.living_room  # Group master
data:
  target_entity: media_player.bedroom

# Remove from group
service: wiim.remove_from_group
target:
  entity_id: media_player.living_room
data:
  target_entity: media_player.kitchen

# Disband entire group
service: wiim.disband_group
target:
  entity_id: media_player.living_room
```

## 🎛️ Group Entities (Optional)

### What Are Group Entities?

Virtual media players that provide unified control of entire multiroom groups:

- **Purpose**: Single control point for group playback and volume
- **Creation**: User-enabled per device (not automatic)
- **Availability**: Only appears when device is master with slaves
- **Benefits**: Stable entity IDs for automations, group-wide controls

### Enabling Group Entities

**Step 1: Choose Master Device**

1. **Settings** → **Devices & Services** → **WiiM Audio**
2. Find your preferred master device
3. Click **Configure**
4. Enable **"Enable group control entity"**

**Step 2: Entity Creation**

- Group entity created: `media_player.{device_name}_group`
- Example: `media_player.living_room_group`
- Shows as **unavailable** until device becomes master

**Step 3: Using Group Entity**
When the device becomes master:

- Group entity becomes **available**
- Provides unified control of entire group
- Shows master's metadata with group member details

### Group Entity Features

**Unified Controls:**

- **Playback**: Play/pause/stop affects entire group
- **Volume**: Group volume with relative member adjustments
- **Navigation**: Next/previous track for whole group

**Group Volume Behavior:**
Group volume maintains relative relationships between speakers:

**Example:**

- Master: 80%, Slave 1: 40%, Slave 2: 60%
- Set group volume to 100%
- Result: Master: 100%, Slave 1: 50%, Slave 2: 75%

**Individual Member Control:**
Access per-speaker details via group entity attributes:

```yaml
# Group entity attributes
attributes:
  member_192_168_1_10_volume: 75
  member_192_168_1_10_mute: false
  member_192_168_1_10_name: "Kitchen"
  member_192_168_1_20_volume: 50
  member_192_168_1_20_mute: false
  member_192_168_1_20_name: "Bedroom"
```

## 🎛️ Viewing Group Status

### Method 1: Device Attributes

Click on any WiiM device → click "ℹ️" info button:

**Master devices show:**

- `wiim_role`: "master"
- `wiim_slaves`: List with names, IPs, volumes, mute status
- `wiim_slave_count`: Number of slaves

**Slave devices show:**

- `wiim_role`: "slave"
- `wiim_group_master`: Master's IP address
- `wiim_master_name`: Master's friendly name

**All devices show:**

- `wiim_available_devices`: Other WiiM devices available for grouping

### Method 2: Role Sensors

Each speaker has a role sensor:

```yaml
sensor.living_room_multiroom_role: "master"
sensor.kitchen_multiroom_role: "slave"
sensor.bedroom_multiroom_role: "slave"
sensor.office_multiroom_role: "solo"
```

## 🏠 Dashboard Integration

### Basic Group Control Buttons

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

### System Status Display

```yaml
type: entities
title: WiiM System Status
entities:
  - entity: sensor.living_room_multiroom_role
    name: Living Room Role
  - entity: sensor.kitchen_multiroom_role
    name: Kitchen Role
  - entity: sensor.bedroom_multiroom_role
    name: Bedroom Role
```

### Volume Control Grid

```yaml
type: grid
square: false
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

## 🤖 Automation Examples

### Time-Based Grouping

```yaml
automation:
  - alias: "Evening Multiroom Setup"
    trigger:
      platform: time
      at: "18:00:00"
    action:
      - service: media_player.join
        target:
          entity_id: media_player.living_room
        data:
          group_members:
            - media_player.kitchen
            - media_player.dining_room
      - service: media_player.volume_set
        target:
          entity_id: media_player.living_room_group
        data:
          volume_level: 0.4
```

### Presence-Based Control

```yaml
automation:
  - alias: "Party Mode When Guests Arrive"
    trigger:
      platform: state
      entity_id: input_boolean.party_mode
      to: "on"
    action:
      - service: wiim.create_group
        target:
          entity_id: media_player.living_room
        data:
          group_members:
            - media_player.kitchen
            - media_player.dining_room
            - media_player.patio
```

## 🔧 Advanced Configuration

### Group Preset Selector

Add to `configuration.yaml`:

```yaml
input_select:
  wiim_group_presets:
    name: WiiM Group Presets
    options:
      - "Solo (No Groups)"
      - "Kitchen + Dining"
      - "Upstairs Rooms"
      - "Party Mode (All)"
    initial: "Solo (No Groups)"
    icon: mdi:speaker-multiple
```

### System Overview Sensor

Add template sensor to monitor entire WiiM system:

```yaml
template:
  - sensor:
      name: "WiiM Group Status"
      state: >
        {% set masters = states.sensor
          | selectattr('entity_id', 'match', '.*multiroom_role$')
          | selectattr('state', 'equalto', 'master') | list %}
        {{ masters | length }} groups active
      attributes:
        total_devices: >
          {{ states.sensor
            | selectattr('entity_id', 'match', '.*multiroom_role$')
            | list | length }}
        groups: >
          {% set groups = [] %}
          {% for entity in states.sensor
            | selectattr('entity_id', 'match', '.*multiroom_role$')
            | selectattr('state', 'equalto', 'master') %}
            {% set master_name = entity.entity_id.replace('_multiroom_role', '').replace('sensor.', '') %}
            {% set slaves = states.sensor
              | selectattr('entity_id', 'match', '.*multiroom_role$')
              | selectattr('state', 'equalto', 'slave') | list %}
            {% set group = {
              'master': master_name,
              'slaves': slaves | map(attribute='entity_id') |
                map('replace', '_multiroom_role', '') |
                map('replace', 'sensor.', '') | list,
              'total_devices': 1 + slaves | length
            } %}
            {% set groups = groups + [group] %}
          {% endfor %}
          {{ groups }}
```

## 🐛 Troubleshooting

### Common Issues

**Groups not appearing:**

- Check devices are on same network/VLAN
- Verify UPnP/SSDP traffic allowed (ports 1900, 8080-8090)
- Update device firmware to latest version

**Service calls failing:**

- Verify entity IDs are correct (check Developer Tools → States)
- Ensure devices are powered on and responsive
- Check Home Assistant logs for specific errors

**Attributes not showing:**

- Restart Home Assistant after configuration changes
- Clear browser cache and refresh
- Enable debug logging: `custom_components.wiim: debug`

**Volume jumps unexpectedly:**

- Group volume represents maximum member volume
- Changes apply relatively to maintain speaker balance
- Check individual device volumes in group entity attributes

### Debug Information

Enable detailed logging:

```yaml
logger:
  default: warning
  logs:
    custom_components.wiim: debug
    custom_components.wiim.coordinator: debug
    custom_components.wiim.group_media_player: debug
```

## 🎯 Best Practices

### Network Setup

- Keep all speakers on same subnet
- Use DHCP reservations for stable IP addresses
- Ensure strong WiFi signal for all speakers
- Allow multicast traffic between devices

### Home Assistant Configuration

- Use 5-10 second polling intervals for grouped speakers
- Enable group entities only on devices you'll use as masters
- Use smaller volume steps (1-5%) for fine control
- Test group commands manually before adding to automations

### Group Management

- Choose centrally located speaker as master
- Use descriptive names in WiiM app
- Test groups before important events
- Have individual speaker controls ready as backup

## 📚 Related Documentation

- **[Installation Guide](installation.md)** - Initial setup
- **[Troubleshooting](troubleshooting.md)** - Common issues
- **[Examples](../examples/)** - Ready-to-use scripts and cards
- **[API Reference](api-reference.md)** - Technical details
