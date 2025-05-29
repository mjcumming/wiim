# Automation & Scripting Guide

Complete guide to automating WiiM speakers with Home Assistant.

## 🎯 Overview

This guide covers:

- **Basic Automations** - Time-based, event-driven controls
- **Multiroom Automation** - Group management and coordination
- **Advanced Patterns** - Templates, scenes, and complex workflows
- **Dashboard Controls** - Lovelace automation interfaces
- **Voice Integration** - TTS and announcements

## ⚡ Quick Start Scripts

### Copy & Paste Scripts

Add these to your `scripts.yaml` file:

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
        entity_id: media_player.living_room_group
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
    - service: media_player.play_preset
      target:
        entity_id: media_player.bedroom
      data:
        preset: 1 # Morning playlist

# Evening Wind Down
wiim_evening_routine:
  alias: "WiiM Evening Routine"
  icon: mdi:weather-night
  sequence:
    - service: media_player.join
      target:
        entity_id: media_player.living_room
      data:
        group_members:
          - media_player.kitchen
    - service: media_player.volume_set
      target:
        entity_id: media_player.living_room_group
      data:
        volume_level: 0.3
    - service: media_player.play_preset
      target:
        entity_id: media_player.living_room_group
      data:
        preset: 5 # Relaxing music
```

## 🤖 Time-Based Automations

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
        entity_id: person.john
        state: "home"
    action:
      - service: media_player.volume_set
        target:
          entity_id: media_player.bedroom
        data:
          volume_level: 0.15
      - service: media_player.play_preset
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
          entity_id: media_player.dining_room_group
        data:
          volume_level: 0.4
      - service: media_player.play_preset
        target:
          entity_id: media_player.dining_room_group
        data:
          preset: 3 # Dinner music
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
      # Gradually lower volume on all speakers
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
      - service: media_player.play_preset
        target:
          entity_id: media_player.bedroom
        data:
          preset: 6 # Sleep sounds
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
            - media_player.bedroom
      # Pause all active speakers
      - service: media_player.media_pause
        target:
          entity_id:
            - media_player.living_room
            - media_player.kitchen
            - media_player.bedroom
      # Make announcement on group or main speaker
      - service: tts.speak
        target:
          entity_id: >
            {% if states('media_player.living_room_group') != 'unavailable' %}
              media_player.living_room_group
            {% else %}
              media_player.living_room
            {% endif %}
        data:
          message: "Someone is at the front door"
      # Wait and restore previous state
      - delay: "00:00:10"
      - service: scene.turn_on
        target:
          entity_id: scene.before_doorbell
```

### Presence-Based Control

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
      - condition: state
        entity_id: media_player.living_room
        state: "off"
    action:
      - service: media_player.turn_on
        target:
          entity_id: media_player.living_room
      - delay: "00:00:03"
      - service: media_player.volume_set
        target:
          entity_id: media_player.living_room
        data:
          volume_level: 0.3
      - service: media_player.play_preset
        target:
          entity_id: media_player.living_room
        data:
          preset: 2 # Welcome home playlist

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

## 🎚️ Dynamic Control Automations

### Volume Scheduling

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

### Smart Source Switching

```yaml
automation:
  - alias: "TV Audio Handoff"
    description: "Switch speakers to line input when TV turns on"
    trigger:
      platform: state
      entity_id: media_player.living_room_tv
      to: "on"
    condition:
      - condition: state
        entity_id: media_player.living_room
        state: "on"
    action:
      # Store current source and volume
      - service: input_text.set_value
        target:
          entity_id: input_text.previous_source
        data:
          value: "{{ state_attr('media_player.living_room', 'source') }}"
      # Switch to line input
      - service: media_player.select_source
        target:
          entity_id: media_player.living_room
        data:
          source: "Line In"
      - service: media_player.volume_set
        target:
          entity_id: media_player.living_room
        data:
          volume_level: 0.6

  - alias: "TV Audio Restore"
    description: "Restore previous source when TV turns off"
    trigger:
      platform: state
      entity_id: media_player.living_room_tv
      to: "off"
      for: "00:01:00"
    condition:
      - condition: state
        entity_id: media_player.living_room
        attribute: source
        state: "Line In"
    action:
      - service: media_player.select_source
        target:
          entity_id: media_player.living_room
        data:
          source: "{{ states('input_text.previous_source') }}"
```

## 🎵 Playlist & Content Automation

### Mood-Based Playlists

```yaml
automation:
  - alias: "Weather-Based Music"
    description: "Choose playlist based on weather"
    trigger:
      platform: state
      entity_id: input_boolean.auto_music
      to: "on"
    action:
      - service: media_player.play_preset
        target:
          entity_id: media_player.living_room
        data:
          preset: >
            {% set weather = states('weather.home') %}
            {% if weather == 'sunny' %}
              2
            {% elif weather in ['rainy', 'cloudy'] %}
              5
            {% elif weather == 'snowy' %}
              6
            {% else %}
              1
            {% endif %}

# Required input helpers
input_boolean:
  auto_music:
    name: Auto Music Mode
    icon: mdi:music-circle

input_text:
  previous_source:
    name: Previous Audio Source
    max: 20
```

### Multi-Zone Content Sync

```yaml
automation:
  - alias: "Follow Me Music"
    description: "Move music to room with motion"
    trigger:
      platform: state
      entity_id:
        - binary_sensor.living_room_motion
        - binary_sensor.kitchen_motion
        - binary_sensor.bedroom_motion
      to: "on"
    condition:
      - condition: template
        value_template: >
          {{ trigger.entity_id.replace('binary_sensor.', '').replace('_motion', '')
             != state_attr('media_player.living_room', 'room_with_activity') }}
    action:
      - service: input_text.set_value
        target:
          entity_id: input_text.active_room
        data:
          value: "{{ trigger.entity_id.replace('binary_sensor.', '').replace('_motion', '') }}"
      # Move music to active room
      - service: media_player.unjoin
        target:
          entity_id:
            - media_player.living_room
            - media_player.kitchen
            - media_player.bedroom
      - delay: "00:00:02"
      - service: media_player.turn_on
        target:
          entity_id: "media_player.{{ states('input_text.active_room') }}"
      - service: media_player.volume_set
        target:
          entity_id: "media_player.{{ states('input_text.active_room') }}"
        data:
          volume_level: 0.4
```

## 🗣️ Voice & TTS Integration

### Advanced Announcements

```yaml
automation:
  - alias: "Smart Announcements"
    description: "Context-aware announcements"
    trigger:
      platform: event
      event_type: call_service
      event_data:
        domain: tts
        service: speak
    action:
      # Determine best speaker for announcement
      - service: tts.speak
        target:
          entity_id: >
            {% set active_speakers = states.media_player
              | selectattr('entity_id', 'match', 'media_player.wiim_.*')
              | selectattr('state', 'equalto', 'playing') | list %}
            {% if active_speakers | length > 0 %}
              {% if states('media_player.living_room_group') != 'unavailable' %}
                media_player.living_room_group
              {% else %}
                {{ active_speakers[0].entity_id }}
              {% endif %}
            {% else %}
              media_player.living_room
            {% endif %}
        data:
          message: "{{ trigger.event.data.service_data.message }}"
          options:
            volume_level: >
              {% set hour = now().hour %}
              {% if 22 <= hour or hour <= 6 %}
                0.3
              {% else %}
                0.6
              {% endif %}
```

### Intercom System

```yaml
# Intercom between rooms
script:
  wiim_intercom:
    alias: "WiiM Intercom"
    fields:
      from_room:
        description: "Source room"
        example: "living_room"
      to_room:
        description: "Target room"
        example: "bedroom"
      message:
        description: "Message to announce"
        example: "Dinner is ready"
    sequence:
      - service: media_player.volume_set
        target:
          entity_id: "media_player.{{ to_room }}"
        data:
          volume_level: 0.8
      - service: tts.speak
        target:
          entity_id: "media_player.{{ to_room }}"
        data:
          message: "Message from {{ from_room }}: {{ message }}"
      - delay: "00:00:05"
      - service: media_player.volume_set
        target:
          entity_id: "media_player.{{ to_room }}"
        data:
          volume_level: 0.4
```

## 🎛️ Dashboard Controls

### Dynamic Group Selector

```yaml
# Add to configuration.yaml
input_select:
  wiim_group_presets:
    name: WiiM Group Presets
    options:
      - "Solo (No Groups)"
      - "Kitchen + Dining"
      - "Living Room Zone"
      - "Upstairs Rooms"
      - "Party Mode (All)"
      - "Quiet Hours"
    initial: "Solo (No Groups)"
    icon: mdi:speaker-multiple

# Automation to apply group selection
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
                state: "Living Room Zone"
            sequence:
              - service: media_player.join
                target:
                  entity_id: media_player.living_room
                data:
                  group_members:
                    - media_player.kitchen
                    - media_player.dining_room
          - conditions:
              - condition: state
                entity_id: input_select.wiim_group_presets
                state: "Upstairs Rooms"
            sequence:
              - service: media_player.join
                target:
                  entity_id: media_player.master_bedroom
                data:
                  group_members:
                    - media_player.guest_bedroom
                    - media_player.office
          - conditions:
              - condition: state
                entity_id: input_select.wiim_group_presets
                state: "Party Mode (All)"
            sequence:
              - service: script.wiim_party_mode
          - conditions:
              - condition: state
                entity_id: input_select.wiim_group_presets
                state: "Quiet Hours"
            sequence:
              - service: script.wiim_ungroup_all
              - service: media_player.volume_set
                target:
                  entity_id:
                    - media_player.living_room
                    - media_player.kitchen
                    - media_player.bedroom
                data:
                  volume_level: 0.15
```

### System Status Template

```yaml
# Add to configuration.yaml
template:
  - sensor:
      name: "WiiM System Status"
      state: >
        {% set masters = states.sensor
          | selectattr('entity_id', 'match', '.*multiroom_role$')
          | selectattr('state', 'equalto', 'master') | list %}
        {% set playing = states.media_player
          | selectattr('entity_id', 'match', 'media_player.wiim_.*')
          | selectattr('state', 'equalto', 'playing') | list %}
        {% if masters | length > 0 %}
          {{ masters | length }} groups, {{ playing | length }} playing
        {% elif playing | length > 0 %}
          {{ playing | length }} speakers playing
        {% else %}
          All speakers idle
        {% endif %}
      attributes:
        total_devices: >
          {{ states.media_player
            | selectattr('entity_id', 'match', 'media_player.wiim_.*')
            | list | length }}
        active_groups: >
          {{ states.sensor
            | selectattr('entity_id', 'match', '.*multiroom_role$')
            | selectattr('state', 'equalto', 'master')
            | map(attribute='entity_id')
            | map('replace', '_multiroom_role', '')
            | map('replace', 'sensor.', '')
            | list }}
        playing_devices: >
          {{ states.media_player
            | selectattr('entity_id', 'match', 'media_player.wiim_.*')
            | selectattr('state', 'equalto', 'playing')
            | map(attribute='entity_id')
            | map('replace', 'media_player.', '')
            | list }}
```

## 🎯 Advanced Patterns

### Scene-Based Audio

```yaml
# Audio scenes for different activities
scene:
  - name: "Dinner Party"
    entities:
      media_player.dining_room:
        state: "playing"
        volume_level: 0.4
        source: "WiFi"
      media_player.kitchen:
        state: "playing"
        volume_level: 0.3
      media_player.living_room:
        state: "playing"
        volume_level: 0.5
      input_select.wiim_group_presets:
        state: "Living Room Zone"

  - name: "Movie Night"
    entities:
      media_player.living_room:
        state: "on"
        source: "Line In"
        volume_level: 0.7
      media_player.kitchen:
        state: "off"
      media_player.bedroom:
        state: "off"

  - name: "Sleep Time"
    entities:
      media_player.living_room:
        state: "off"
      media_player.kitchen:
        state: "off"
      media_player.bedroom:
        state: "playing"
        volume_level: 0.1
        preset: 6 # Sleep sounds
```

### Conditional Group Management

```yaml
automation:
  - alias: "Smart Group Formation"
    description: "Create groups based on who's home and time"
    trigger:
      - platform: state
        entity_id: group.family
      - platform: time_pattern
        hours: "/1" # Check every hour
    condition:
      - condition: time
        after: "08:00:00"
        before: "22:00:00"
    action:
      - choose:
          # Parents home, kids away - adult music zones
          - conditions:
              - condition: state
                entity_id: person.parent1
                state: "home"
              - condition: state
                entity_id: person.parent2
                state: "home"
              - condition: state
                entity_id: group.kids
                state: "not_home"
            sequence:
              - service: input_select.select_option
                target:
                  entity_id: input_select.wiim_group_presets
                data:
                  option: "Living Room Zone"
          # Family time - keep separate zones
          - conditions:
              - condition: state
                entity_id: group.family
                state: "home"
              - condition: time
                after: "17:00:00"
                before: "20:00:00"
            sequence:
              - service: input_select.select_option
                target:
                  entity_id: input_select.wiim_group_presets
                data:
                  option: "Kitchen + Dining"
        default:
          # Default to individual control
          - service: input_select.select_option
            target:
              entity_id: input_select.wiim_group_presets
            data:
              option: "Solo (No Groups)"
```

## 🔧 Maintenance Automations

### Automatic Device Maintenance

```yaml
automation:
  - alias: "WiiM Health Check"
    description: "Monitor and maintain WiiM devices"
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
      # Check for offline devices and restart if needed
      - repeat:
          for_each: >
            {{ states.media_player
              | selectattr('entity_id', 'match', 'media_player.wiim_.*')
              | selectattr('state', 'equalto', 'unavailable')
              | map(attribute='entity_id') | list }}
          sequence:
            - service: wiim.reboot_device
              target:
                entity_id: "{{ repeat.item }}"
            - delay: "00:01:00"

  - alias: "WiiM Usage Statistics"
    description: "Log daily usage for optimization"
    trigger:
      platform: time
      at: "23:59:00"
    action:
      - service: logbook.log
        data:
          name: "WiiM Daily Summary"
          message: >
            Total play time today: {{ (states.sensor.wiim_total_play_time.state | int) // 3600 }} hours.
            Most used speaker: {{ states.sensor.wiim_most_used_device.state }}.
            Groups created: {{ states.sensor.wiim_daily_groups.state }}.
```

## 📚 Related Documentation

- **[Configuration Guide](configuration.md)** - Device setup and options
- **[Multiroom Guide](multiroom.md)** - Group management details
- **[Troubleshooting](troubleshooting.md)** - Debug automation issues
- **[Examples](../examples/)** - Additional scripts and configurations
