# WiiM Integration - Automation Examples

Ready-to-use automation scripts and dashboard configurations for your WiiM speakers.

## 🚀 Quick Start Scripts

Copy these to your `scripts.yaml`:

```yaml
# Party Mode - Group all speakers
wiim_party_mode:
  alias: "WiiM Party Mode"
  icon: mdi:party-popper
  sequence:
    - service: media_player.join
      target:
        entity_id: media_player.living_room
      data:
        group_members:
          - media_player.kitchen
          - media_player.bedroom
          - media_player.patio
    - service: media_player.volume_set
      target:
        entity_id: media_player.living_room
      data:
        volume_level: 0.7

# Ungroup All Speakers
wiim_ungroup_all:
  alias: "WiiM Ungroup All"
  icon: mdi:speaker-off
  sequence:
    - service: media_player.unjoin
      target:
        entity_id:
          - media_player.living_room
          - media_player.kitchen
          - media_player.bedroom
          - media_player.patio

# Morning Wake Up
wiim_morning_routine:
  alias: "WiiM Morning Routine"
  icon: mdi:weather-sunny
  sequence:
    - service: media_player.volume_set
      target:
        entity_id: media_player.bedroom
      data:
        volume_level: 0.2
    - service: wiim.play_preset
      target:
        entity_id: media_player.bedroom
      data:
        preset: 1
```

## ⏰ Time-Based Automations

### Morning Music Routine

```yaml
automation:
  - alias: "Morning Music"
    description: "Gentle wake-up music in bedroom"
    trigger:
      platform: time
      at: "07:00:00"
    condition:
      - condition: state
        entity_id: binary_sensor.workday_sensor
        state: "on"
      - condition: state
        entity_id: person.you
        state: "home"
    action:
      - service: media_player.volume_set
        target:
          entity_id: media_player.bedroom
        data:
          volume_level: 0.15
      - service: wiim.play_preset
        target:
          entity_id: media_player.bedroom
        data:
          preset: 1
      - delay: "00:15:00"
      - service: media_player.volume_set
        target:
          entity_id: media_player.bedroom
        data:
          volume_level: 0.25
```

### Evening Multiroom Setup

```yaml
automation:
  - alias: "Evening Multiroom"
    description: "Create dining group at dinner time"
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
          entity_id: media_player.dining_room
        data:
          group_members:
            - media_player.kitchen
            - media_player.living_room
      - service: media_player.volume_set
        target:
          entity_id: media_player.dining_room
        data:
          volume_level: 0.4
      - service: wiim.play_preset
        target:
          entity_id: media_player.dining_room
        data:
          preset: 3
```

### Bedtime Routine

```yaml
automation:
  - alias: "Bedtime Music"
    description: "Transition to sleep sounds"
    trigger:
      platform: time
      at: "22:30:00"
    action:
      # Gradually lower volume
      - service: media_player.volume_set
        target:
          entity_id:
            - media_player.living_room
            - media_player.kitchen
        data:
          volume_level: 0.1
      # Ungroup all speakers
      - delay: "00:02:00"
      - service: media_player.unjoin
        target:
          entity_id:
            - media_player.living_room
            - media_player.kitchen
            - media_player.bedroom
      # Start sleep sounds in bedroom only
      - service: media_player.volume_set
        target:
          entity_id: media_player.bedroom
        data:
          volume_level: 0.1
      - service: wiim.play_preset
        target:
          entity_id: media_player.bedroom
        data:
          preset: 6
```

## 🏠 Presence-Based Automations

### Welcome Home Music

```yaml
automation:
  - alias: "Welcome Home Music"
    description: "Start music when family arrives"
    trigger:
      platform: state
      entity_id: group.family
      from: "not_home"
      to: "home"
    condition:
      - condition: time
        after: "08:00:00"
        before: "22:00:00"
    action:
      - service: media_player.volume_set
        target:
          entity_id: media_player.living_room
        data:
          volume_level: 0.3
      - service: wiim.play_preset
        target:
          entity_id: media_player.living_room
        data:
          preset: 2

  - alias: "Away Mode"
    description: "Turn off all speakers when everyone leaves"
    trigger:
      platform: state
      entity_id: group.family
      to: "not_home"
      for: "00:15:00"
    action:
      - service: media_player.turn_off
        target:
          entity_id:
            - media_player.living_room
            - media_player.kitchen
            - media_player.bedroom
            - media_player.patio
```

## 🚨 Event-Driven Automations

### Doorbell Announcements

```yaml
automation:
  - alias: "Doorbell Announcement"
    description: "Pause music and announce doorbell"
    trigger:
      platform: state
      entity_id: binary_sensor.front_door_button
      to: "on"
    action:
      # Store current state
      - service: scene.create
        data:
          scene_id: before_doorbell
          snapshot_entities:
            - media_player.living_room
            - media_player.kitchen
      # Pause active speakers
      - service: media_player.media_pause
        target:
          entity_id:
            - media_player.living_room
            - media_player.kitchen
      # Make announcement
      - service: tts.speak
        target:
          entity_id: media_player.living_room
        data:
          message: "Someone is at the front door"
      # Restore after 10 seconds
      - delay: "00:00:10"
      - service: scene.turn_on
        target:
          entity_id: scene.before_doorbell
```

### Smart Volume Adjustment

```yaml
automation:
  - alias: "Dynamic Volume Control"
    description: "Adjust volume based on time of day"
    trigger:
      - platform: state
        entity_id:
          - media_player.living_room
          - media_player.kitchen
        to: "playing"
    action:
      - service: media_player.volume_set
        target:
          entity_id: "{{ trigger.entity_id }}"
        data:
          volume_level: >
            {% set hour = now().hour %}
            {% if 6 <= hour < 8 %}
              0.2
            {% elif 8 <= hour < 18 %}
              0.4
            {% elif 18 <= hour < 22 %}
              0.5
            {% else %}
              0.15
            {% endif %}
```

## 📱 Dashboard Controls

### Group Management Card

```yaml
# Add to configuration.yaml
input_select:
  wiim_group_presets:
    name: WiiM Group Presets
    options:
      - "Solo (No Groups)"
      - "Kitchen + Dining"
      - "Living Room Zone"
      - "Party Mode (All)"
      - "Quiet Hours"
    initial: "Solo (No Groups)"
    icon: mdi:speaker-multiple
```

### Group Preset Automation

```yaml
automation:
  - alias: "Apply WiiM Group Preset"
    description: "Apply selected group configuration"
    trigger:
      platform: state
      entity_id: input_select.wiim_group_presets
    action:
      - choose:
          - conditions:
              - condition: state
                entity_id: input_select.wiim_group_presets
                state: "Solo (No Groups)"
            sequence:
              - service: script.wiim_ungroup_all
          - conditions:
              - condition: state
                entity_id: input_select.wiim_group_presets
                state: "Kitchen + Dining"
            sequence:
              - service: media_player.join
                target:
                  entity_id: media_player.kitchen
                data:
                  group_members:
                    - media_player.dining_room
          - conditions:
              - condition: state
                entity_id: input_select.wiim_group_presets
                state: "Party Mode (All)"
            sequence:
              - service: script.wiim_party_mode
```

### System Status Dashboard

```yaml
type: entities
title: WiiM System
entities:
  - entity: sensor.living_room_multiroom_role
    name: Living Room
  - entity: sensor.kitchen_multiroom_role
    name: Kitchen
  - entity: sensor.bedroom_multiroom_role
    name: Bedroom
  - entity: input_select.wiim_group_presets
    name: Group Preset
```

## 🎵 Role-Based Automations

### Master Speaker Control

```yaml
automation:
  - alias: "Control Via Master Only"
    description: "Send commands to group master"
    trigger:
      platform: state
      entity_id: input_boolean.music_mode
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

### Group Formation Detection

```yaml
automation:
  - alias: "Notify Group Formation"
    description: "Alert when speakers join groups"
    trigger:
      platform: state
      entity_id:
        - sensor.living_room_multiroom_role
        - sensor.kitchen_multiroom_role
        - sensor.bedroom_multiroom_role
      to: "Master"
    action:
      - service: notify.mobile_app
        data:
          message: "{{ trigger.to_state.name }} is now controlling a speaker group"
```

## 🛠️ Maintenance Automations

### Health Check

```yaml
automation:
  - alias: "WiiM Health Check"
    description: "Daily maintenance and sync"
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
      # Check for offline devices
      - repeat:
          for_each: >
            {{ states.media_player
              | selectattr('entity_id', 'match', 'media_player..*')
              | selectattr('state', 'equalto', 'unavailable')
              | map(attribute='entity_id') | list }}
          sequence:
            - service: wiim.reboot_device
              target:
                entity_id: "{{ repeat.item }}"
            - delay: "00:01:00"
```

## 📚 Template Helpers

Add these to `configuration.yaml`:

```yaml
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
          | selectattr('entity_id', 'match', 'media_player..*')
          | selectattr('state', 'equalto', 'playing')
          | list | length }}

input_boolean:
  music_mode:
    name: Music Mode
    icon: mdi:music-circle

  party_mode:
    name: Party Mode
    icon: mdi:party-popper
```

## 🎯 Pro Tips

1. **Use Role Sensor**: Always check multiroom role before sending commands
2. **Group First**: Create groups before setting volume/playback
3. **Test Commands**: Use Developer Tools to test before adding to automations
4. **Error Handling**: Add `continue_on_error: true` for robust automations
5. **Timing**: Add small delays between group operations for reliability

For more advanced patterns, see the [complete user guide](user-guide.md).
