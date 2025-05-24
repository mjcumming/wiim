# Multiroom Guide

This guide explains how to set up and manage multiroom audio with WiiM speakers and Home Assistant.

## Understanding Multiroom

### How It Works

WiiM speakers use the LinkPlay protocol for synchronized multiroom audio:

- **Master Speaker**: Streams audio and controls the group
- **Slave Speakers**: Receive audio from the master speaker
- **Synchronization**: All speakers play audio in perfect sync
- **Group Control**: Volume and playback controlled from master or group entity

### Group Roles

Each speaker has one of three roles:

| Role       | Description         | Control                    | Status                                  |
| ---------- | ------------------- | -------------------------- | --------------------------------------- |
| **Solo**   | Independent speaker | Full control               | `sensor.speaker_multiroom_role: solo`   |
| **Master** | Group leader        | Controls group playback    | `sensor.speaker_multiroom_role: master` |
| **Slave**  | Group member        | Limited individual control | `sensor.speaker_multiroom_role: slave`  |

---

## Creating Groups

### Method 1: WiiM App (Recommended)

1. **Open WiiM App**

   - Use official WiiM or compatible LinkPlay app

2. **Create Group**

   - Select master speaker
   - Add slave speakers to group
   - Choose group name

3. **Home Assistant Sync**
   - Changes automatically detected within 5-10 seconds
   - Group entities created if enabled for master speaker

### Method 2: Home Assistant

Create groups directly from Home Assistant:

```yaml
# Join speakers to create group
service: media_player.join
target:
  entity_id: media_player.living_room # Master
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom
```

**Result**: Living Room becomes master, Kitchen and Bedroom become slaves.

### Method 3: Lovelace UI

1. **Media Player Card**

   - Open master speaker card
   - Click group icon (chain link)
   - Select speakers to join

2. **Speaker Selection**
   - Choose which speakers to include
   - Master speaker controls group

---

## Group Entities

### What Are Group Entities?

Virtual media players that control entire multiroom groups:

- **Purpose**: Unified control of all group members
- **Creation**: User-enabled per device (not automatic)
- **Availability**: Only appears when device is master with slaves

### Enabling Group Entities

#### Step 1: Choose Master Device

Enable group entity on the speaker you want to control groups:

1. **Settings** → **Devices & Services** → **WiiM Audio**
2. Find the device entry for your preferred master
3. Click **Configure**
4. Enable **"Enable group control entity"**

#### Step 2: Entity Creation

- Group entity created: `media_player.{device_name}_group`
- Example: `media_player.living_room_group`
- Shows as **unavailable** until device becomes master

#### Step 3: Using Group Entity

When the device becomes master of a group:

- Group entity becomes **available**
- Provides unified control of entire group
- Shows group status and metadata

### Group Entity Features

#### Unified Controls

- **Playback**: Play/pause/stop affects entire group
- **Volume**: Group volume control with relative adjustments
- **Navigation**: Next/previous track for whole group

#### Volume Behavior

Group volume maintains relative relationships between speakers:

**Example Scenario**:

- Master: 80% volume
- Slave 1: 40% volume
- Slave 2: 60% volume

**Set Group Volume to 100%**:

- Master: 100% (was 80%, max in group)
- Slave 1: 50% (was 40%, scaled proportionally)
- Slave 2: 75% (was 60%, scaled proportionally)

#### Individual Control

Access per-speaker controls via group entity attributes:

```yaml
# Group entity attributes show individual speaker status
attributes:
  member_192_168_1_10_volume: 75
  member_192_168_1_10_mute: false
  member_192_168_1_10_name: "Kitchen"
  member_192_168_1_20_volume: 50
  member_192_168_1_20_mute: false
  member_192_168_1_20_name: "Bedroom"
```

---

## Managing Groups

### Group Status Monitoring

Check group status through sensors and attributes:

#### Role Sensors

Each speaker has a role sensor:

```yaml
sensor.living_room_multiroom_role: "master"
sensor.kitchen_multiroom_role: "slave"
sensor.bedroom_multiroom_role: "slave"
sensor.office_multiroom_role: "solo"
```

#### Group Attributes

Master speaker shows group information:

```yaml
# Master speaker attributes
group_members: ["192.168.1.20", "192.168.1.30"]
group_master: "192.168.1.10"
group_role: "master"
slave_count: 2
```

### Modifying Groups

#### Adding Speakers

```yaml
service: media_player.join
target:
  entity_id: media_player.living_room # Existing master
data:
  group_members:
    - media_player.kitchen # Existing slave
    - media_player.bedroom # Existing slave
    - media_player.dining_room # New slave
```

#### Removing Speakers

```yaml
# Remove specific speaker from group
service: media_player.unjoin
target:
  entity_id: media_player.bedroom
```

#### Disbanding Groups

```yaml
# Master disbands entire group
service: media_player.unjoin
target:
  entity_id: media_player.living_room # Master
```

**Result**: All speakers return to solo mode.

---

## Advanced Configuration

### Multiple Group Entities

Enable group entities on multiple speakers for flexibility:

```yaml
# Living Room can control living room groups
living_room_group_entity: enabled

# Kitchen can control kitchen groups
kitchen_group_entity: enabled

# Office for work area groups
office_group_entity: enabled
```

**Benefit**: Different speakers can act as masters for different scenarios.

### Automation Examples

#### Auto-Group at Night

```yaml
automation:
  - alias: "Nighttime Audio Group"
    trigger:
      platform: time
      at: "22:00:00"
    action:
      - service: media_player.join
        target:
          entity_id: media_player.bedroom
        data:
          group_members:
            - media_player.bathroom
```

#### Volume Sync

```yaml
automation:
  - alias: "Sync Living Room Group Volume"
    trigger:
      platform: state
      entity_id: media_player.living_room_group
      attribute: volume_level
    action:
      # Custom logic to adjust individual speakers
```

#### Group Notifications

```yaml
automation:
  - alias: "Announce on Group"
    trigger:
      platform: state
      entity_id: binary_sensor.front_door
      to: "on"
    action:
      - service: tts.speak
        target:
          entity_id: media_player.living_room_group
        data:
          message: "Someone is at the front door"
```

---

## Troubleshooting

### Common Issues

#### Group Entity Not Appearing

**Problem**: Group entity never shows up
**Solutions**:

- Verify group entity is enabled in device options
- Check that device is actually master (has slaves)
- Restart Home Assistant integration
- Check entity registry for disabled entities

#### Volume Jumps Unexpectedly

**Problem**: Group volume changes dramatically
**Explanation**: Group volume is maximum of all members
**Solutions**:

- Use individual speaker controls for fine-tuning
- Understand relative volume behavior
- Check group entity attributes for individual volumes

#### Speakers Not Staying in Group

**Problem**: Speakers keep leaving groups
**Solutions**:

- Check network stability between speakers
- Ensure speakers have latest firmware
- Verify speakers are on same network segment
- Check for IP address conflicts

#### Group Commands Not Working

**Problem**: Group controls don't affect all speakers
**Solutions**:

- Verify master speaker is responding
- Check slave speaker connectivity
- Try ungrouping and regrouping speakers
- Restart speaker firmware if needed

### Debug Information

#### Group Status Logging

```yaml
logger:
  logs:
    custom_components.wiim.coordinator: debug
    custom_components.wiim.group_media_player: debug
```

#### Network Diagnostics

```bash
# Test connectivity between HA and speakers
ping 192.168.1.10  # Master
ping 192.168.1.20  # Slave 1
ping 192.168.1.30  # Slave 2

# Check UPnP discovery
nmap -sU -p 1900 192.168.1.0/24
```

### Advanced Troubleshooting

#### Manual Group Commands

Test group functionality directly:

```yaml
# Force create group (master becomes master)
service: wiim.create_group
target:
  entity_id: media_player.living_room

# Force join group (speaker becomes slave)
service: wiim.join_group
target:
  entity_id: media_player.kitchen
data:
  master_ip: "192.168.1.10"
```

#### Reset Group State

If groups get confused:

1. **Ungroup All**: Use WiiM app to ungroup all speakers
2. **Restart Integration**: Remove and re-add integration
3. **Reboot Speakers**: Power cycle all speakers
4. **Recreate Groups**: Set up groups again

---

## Best Practices

### Network Setup

- **Same Subnet**: Keep all speakers on same network segment
- **Static IPs**: Use DHCP reservations for stable addressing
- **Quality WiFi**: Ensure strong WiFi signal for all speakers
- **Bandwidth**: Multiroom needs ~1-2 Mbps per speaker

### Home Assistant Configuration

- **Polling Intervals**: Use 5-10 second intervals for grouped speakers
- **Group Entities**: Only enable on speakers you'll use as masters
- **Volume Steps**: Use smaller steps (1-5%) for fine control
- **Automation**: Test group commands manually before automation

### Group Management

- **Master Selection**: Choose centrally located speaker as master
- **Group Names**: Use descriptive names in WiiM app
- **Testing**: Test groups before important events/parties
- **Backup Plans**: Have individual speaker controls ready

---

## Comparison with Other Systems

### vs. Sonos

- **Pros**: More affordable, open protocol, Home Assistant integration
- **Cons**: Less mature ecosystem, fewer streaming services

### vs. Chromecast

- **Pros**: Better Home Assistant integration, physical controls
- **Cons**: Requires speaker hardware, limited voice control

### vs. Airplay 2

- **Pros**: Works with Android, more device options, local control
- **Cons**: Apple ecosystem has better integration

---

## Next Steps

- **Automation**: [Create automations using groups](../examples/automation.md)
- **Lovelace**: [Custom group control cards](../examples/lovelace.md)
- **Troubleshooting**: [Resolve common issues](troubleshooting.md)
- **Advanced**: [Custom group scenarios](../examples/advanced.md)
