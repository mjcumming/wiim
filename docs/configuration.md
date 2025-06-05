# Configuration Guide

Complete setup and configuration guide for the WiiM Audio integration.

## 🚀 Initial Setup

### Device Discovery

The integration automatically discovers WiiM speakers on your network using:

1. **UPnP/SSDP** - Discovers MediaRenderer devices
2. **Zeroconf** - Finds `_linkplay._tcp.local.` services
3. **Manual Entry** - Direct IP address configuration

### Adding Devices

**Automatic Discovery:**

1. Go to **Settings** → **Devices & Services**
2. New WiiM devices appear in discovered integrations
3. Click **Configure** and follow the setup wizard

**Manual Addition:**

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **"WiiM Audio"**
3. Enter device IP address when prompted
4. Integration validates connection and creates entities

## ⚙️ Device Configuration

### Device Options

Each device can be individually configured via **Configure** button:

| Option                   | Description                 | Default | Range  |
| ------------------------ | --------------------------- | ------- | ------ |
| **Volume Step**          | Volume button increment     | 5%      | 1-50%  |
| **Enable Group Control** | Create virtual group entity | Off     | On/Off |

**Changes apply immediately** - no restart required.

**Note**: Polling interval is fixed at 5 seconds and not user-configurable.

### Advanced Entity Options

Control which entities are created per device:

**Essential Entities** (always enabled):

- `media_player.device_name` - Main media player
- `number.device_name_volume_step` - Volume step configuration

**Optional Entities** (enable via options):

- `sensor.device_name_multiroom_role` - Group role (solo/master/slave)
- `sensor.device_name_ip_address` - Current IP address
- `button.device_name_reboot` - Device reboot control
- `button.device_name_sync_time` - Time synchronization
- `media_player.device_name_group` - Group control entity

## 🎛️ Group Configuration

### Virtual Group Entities

Group entities provide unified control of multiroom groups:

**Enabling Group Entities:**

1. **Settings** → **Devices & Services** → **WiiM Audio**
2. Click **Configure** on desired master device
3. Enable **"Enable group control entity"**
4. Group entity appears: `media_player.device_name_group`

**Group Entity Behavior:**

- Only available when device is master with slaves
- Provides group-wide playback and volume control
- Shows per-member status in attributes
- Stable entity ID for automations

### Group Volume Control

**Group Volume Logic:**

- Group volume = maximum volume of all members
- Changes applied relatively to maintain balance
- Individual speakers keep their volume relationships

**Example:**

```yaml
# Before: Master 80%, Slave 40%
# Set group volume to 100%
# After: Master 100%, Slave 50%
```

## 📱 Entity Management

### Entity Naming Convention

**Device Entities:**

- `media_player.living_room_speaker` - Main device
- `sensor.living_room_multiroom_role` - Group role
- `number.living_room_volume_step` - Volume step
- `button.living_room_reboot` - Maintenance button

**Group Entities:**

- `media_player.living_room_group` - Group controller

### Entity Organization

**Device Registry:**

- All entities grouped under device's friendly name
- Uses device name from WiiM app, not IP address
- Group entities attach to master device (not separate device)

**Entity Categories:**

- **Essential**: Core media player functionality
- **Configuration**: User-adjustable settings
- **Diagnostic**: Status and monitoring
- **Maintenance**: Device management tools

## 🔧 System Integration

### Supported Features

**Media Player Features:**

```yaml
supported_features:
  - PLAY, PAUSE, STOP
  - NEXT_TRACK, PREVIOUS_TRACK
  - VOLUME_SET, VOLUME_MUTE
  - SEEK, SHUFFLE_SET, REPEAT_SET
  - GROUPING, SELECT_SOURCE
  - BROWSE_MEDIA # Coming soon
```

**Custom Services:**

- `wiim.play_preset` - Play hardware preset buttons (1-6)
- `wiim.play_url` - Play media from URL
- `wiim.play_playlist` - Play M3U playlists
- `wiim.set_eq` - Set equalizer presets or custom values
- `wiim.play_notification` - Play notification sounds
- `wiim.reboot_device` - Device maintenance
- `wiim.sync_time` - Clock synchronization

### Network Requirements

**Ports & Protocols:**

- **HTTPS**: Port 443 (primary API)
- **HTTP**: Port 8080 (fallback)
- **UPnP/SSDP**: Port 1900 (discovery)
- **Multicast**: For group synchronization

**Network Setup:**

- Home Assistant and speakers on same subnet/VLAN
- Multicast traffic allowed between devices
- Stable IP addresses (DHCP reservations recommended)

## 📊 Monitoring & Diagnostics

### Debug Logging

Enable detailed logging for troubleshooting:

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.wiim: debug
    custom_components.wiim.api: debug
    custom_components.wiim.coordinator: debug
```

### Entity Attributes

**Device Attributes:**

```yaml
# Media player attributes
firmware_version: "4.6.328252"
hardware_model: "UP2STREAM_PRO_V3"
ip_address: "192.168.1.100"
group_role: "master"
group_members: ["192.168.1.101", "192.168.1.102"]
available_sources: ["WiFi", "Bluetooth", "Line In"]
```

**Group Attributes:**

```yaml
# Group entity attributes
member_192_168_1_101_volume: 60
member_192_168_1_101_mute: false
member_192_168_1_101_name: "Kitchen"
member_192_168_1_102_volume: 40
member_192_168_1_102_mute: false
member_192_168_1_102_name: "Bedroom"
```

## 🎯 Best Practices

### Performance Optimization

**Polling Intervals:**

- **Fixed interval**: 5 seconds for all states
- **User configurable**: 1-60 seconds range
- **Consistent load**: Predictable resource usage

**Resource Management:**

- Enable only needed diagnostic entities
- Use group entities sparingly (only on intended masters)
- Monitor Home Assistant resource usage

### Automation Guidelines

**Entity Selection:**

- Use stable entity IDs in automations
- Prefer group entities for multiroom control
- Test entity availability before automation

**Error Handling:**

```yaml
# Example automation with error handling
automation:
  - alias: "Safe Volume Control"
    trigger:
      platform: time
      at: "07:00:00"
    condition:
      - condition: state
        entity_id: media_player.living_room
        state: "on"
    action:
      - service: media_player.volume_set
        target:
          entity_id: media_player.living_room
        data:
          volume_level: 0.3
        continue_on_error: true
```

## 🔄 Maintenance

### Routine Maintenance

**Monthly Tasks:**

- Check device firmware updates
- Review entity naming and organization
- Update device IP reservations if needed
- Test multiroom functionality

**Troubleshooting Steps:**

1. Check network connectivity
2. Verify device power and status
3. Review Home Assistant logs
4. Test device responsiveness
5. Restart integration if needed

### Configuration Backup

**Important Configuration:**

- Device options settings
- Group entity preferences
- Automation entity references
- Custom service configurations

Export device configuration via Home Assistant backup system.

## 📚 Related Documentation

- **[Installation Guide](installation.md)** - Initial setup and installation
- **[Multiroom Guide](multiroom.md)** - Detailed multiroom configuration
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions
- **[Examples](../examples/)** - Configuration examples and templates
