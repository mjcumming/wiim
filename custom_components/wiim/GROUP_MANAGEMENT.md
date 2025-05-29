# WiiM Group Management Guide

This guide explains how to view slave players and manage WiiM multiroom groups using the Home Assistant UI.

## 📋 Overview

The WiiM integration provides several ways to view and manage multiroom groups:

1. **Enhanced Device Attributes** - View slave details in device "more info" dialogs
2. **Custom Services** - Easy group management through Developer Tools
3. **Script Templates** - Pre-made automation scripts for common group setups
4. **Template Sensors** - Visual overview of your entire WiiM system
5. **Built-in Grouping** - Native HA grouping button support

## 1. 🔍 Viewing Slave Players

### Method 1: Device Attributes (More Info Dialog)

Click on any WiiM device, then click the "i" info button to see detailed attributes:

**For Master devices:**
- `wiim_role`: "master"
- `wiim_slaves`: List of slave devices with names, IPs, volumes, and mute status
- `wiim_slave_count`: Number of slaves in the group

**For Slave devices:**
- `wiim_role`: "slave"
- `wiim_group_master`: IP address of the master device
- `wiim_master_name`: Friendly name of the master device

**For All devices:**
- `wiim_available_devices`: List of all other WiiM devices that can be grouped

### Method 2: Group Entity (When Enabled)

If you have "Enable Group Control" turned on in device options, a virtual group entity will appear:
- Entity name: `[Master Device Name] (Group)`
- Attributes show per-slave volume and mute controls
- Group-level volume and playback controls

## 2. 🎛️ Group Management Services

Use these services in **Developer Tools > Services** for manual group management:

### `wiim.create_group`
Create a new group with specified members
```yaml
service: wiim.create_group
target:
  entity_id: media_player.wiim_living_room  # Will become master
data:
  group_members:
    - media_player.wiim_kitchen
    - media_player.wiim_dining_room
```

### `wiim.add_to_group`
Add a device to an existing group
```yaml
service: wiim.add_to_group
target:
  entity_id: media_player.wiim_living_room  # Group master
data:
  target_entity: media_player.wiim_bedroom
```

### `wiim.remove_from_group`
Remove a device from a group
```yaml
service: wiim.remove_from_group
target:
  entity_id: media_player.wiim_living_room  # Group master
data:
  target_entity: media_player.wiim_kitchen
```

### `wiim.disband_group`
Completely break up a group
```yaml
service: wiim.disband_group
target:
  entity_id: media_player.wiim_living_room  # Any device in the group
```

## 3. 🚀 Quick Setup Scripts

Copy the contents of `group_management_example.yaml` to your `scripts.yaml` for instant group management buttons.

### Basic Dashboard Buttons

Add this to your dashboard:

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

### Advanced Dropdown Control

For dynamic group selection, add this to `configuration.yaml`:

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

Then the automation in the example file will automatically apply groups when you change the dropdown.

## 4. 📊 System Overview Sensor

Add the template sensor from `group_status_template.yaml` to get a real-time overview of your WiiM system:

### Dashboard Card Example

```yaml
type: markdown
content: |
  ## WiiM System Status

  **Groups:** {{ states('sensor.wiim_group_status') }}
  **Total Devices:** {{ state_attr('sensor.wiim_group_status', 'total_devices') }}

  {% for group in state_attr('sensor.wiim_group_status', 'groups') %}
  ### {{ group.master }} Group ({{ group.total_devices }} devices)
  - Master: {{ group.master }}
  {% for slave in group.slaves %}
  - Slave: {{ slave.name }} ({{ slave.ip }})
  {% endfor %}
  {% endfor %}
```

## 5. 🔗 Built-in HA Grouping

All WiiM devices support Home Assistant's native grouping:

1. **Group Button**: Click the chain-link icon on any media player card
2. **Service Calls**: Use `media_player.join` and `media_player.unjoin`
3. **Automation**: Create automations that call the grouping services

```yaml
# Example automation to group devices at 6 PM
automation:
  - alias: "Evening Music Setup"
    trigger:
      platform: time
      at: "18:00:00"
    action:
      - service: media_player.join
        target:
          entity_id: media_player.wiim_living_room
        data:
          group_members:
            - media_player.wiim_kitchen
            - media_player.wiim_dining_room
```

## 🎯 Recommendations

### For Simple Use:
- Use the built-in grouping button in media player cards
- Add a few script buttons to your dashboard for common group configurations

### For Power Users:
- Implement the dropdown selector for quick group switching
- Use the template sensor for system monitoring
- Create advanced automations based on time, presence, or media source

### For Custom Cards:
- Access the `wiim_slaves`, `wiim_available_devices`, and group status attributes
- Build custom Lovelace cards that show group topology
- Use the custom services in your card's tap actions

## 🐛 Troubleshooting

**Groups not appearing**:
- Check that devices are on the same network
- Verify device firmware is up to date
- Enable debug logging in device options

**Service calls failing**:
- Ensure entity IDs are correct (check Developer Tools > States)
- Verify devices are powered on and responsive
- Check Home Assistant logs for specific error messages

**Attributes not showing**:
- Restart Home Assistant after making changes
- Clear browser cache
- Check that integration is properly loaded

## 🔧 Advanced Customization

### Custom Card Integration

If you're building a custom Lovelace card, these attributes are available:

```javascript
// Get all WiiM devices
const wiimDevices = this.hass.states
  .filter(entity => entity.attributes.integration === 'wiim');

// Find masters with slaves
const masters = wiimDevices
  .filter(entity => entity.attributes.wiim_role === 'master'
    && entity.attributes.wiim_slave_count > 0);

// Get available devices for grouping
const availableDevices = entity.attributes.wiim_available_devices;
```

### API Integration

The custom services can be called from any Home Assistant integration or webhook:

```python
# Call service from Python script
hass.services.call('wiim', 'create_group', {
    'entity_id': 'media_player.wiim_living_room',
    'group_members': ['media_player.wiim_kitchen']
})
```

This gives you maximum flexibility to integrate WiiM grouping with any automation system!