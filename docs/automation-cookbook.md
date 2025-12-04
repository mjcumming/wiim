# WiiM Integration - Automation Cookbook

Essential automation patterns for your WiiM speakers. Copy these proven examples and adapt to your setup.

## 🚀 Quick Start Scripts

Add these to your `scripts.yaml`:

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
        entity_id: media_player.living_room_group_coordinator
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

## ⏰ Alarms and Sleep Timers

### Morning Alarm with Music

Wake up to your favorite music using WiiM's built-in alarm:

```yaml
automation:
  alias: "Bedroom Morning Alarm"
  description: "Set daily alarm for weekday mornings (WiiM devices only)"
  trigger:
    platform: time
    at: "22:00:00" # Set alarm the night before
  condition:
    - condition: time
      weekday:
        - mon
        - tue
        - wed
        - thu
        - fri
  action:
    # Set alarm for 7:00 AM local time (convert to UTC!)
    # For EST (UTC-5): 7:00 AM = 12:00:00 UTC
    # For PST (UTC-8): 7:00 AM = 15:00:00 UTC
    - service: wiim.update_alarm
      target:
        entity_id: media_player.bedroom
      data:
        alarm_id: 0
        time: "12:00:00" # 7:00 AM EST in UTC
        trigger: "daily"
        operation: "playback"
```

### Weekend vs Weekday Alarm

Different alarm times for weekends:

```yaml
automation:
  - alias: "Set Weekday Alarm"
    trigger:
      platform: time
      at: "22:00:00"
    condition:
      - condition: time
        weekday:
          - mon
          - tue
          - wed
          - thu
    action:
      - service: wiim.update_alarm
        target:
          entity_id: media_player.bedroom
        data:
          alarm_id: 0
          time: "12:00:00" # 7:00 AM EST
          trigger: "daily"
          operation: "playback"

  - alias: "Set Weekend Alarm"
    trigger:
      platform: time
      at: "22:00:00"
    condition:
      - condition: time
        weekday:
          - fri
          - sat
    action:
      - service: wiim.update_alarm
        target:
          entity_id: media_player.bedroom
        data:
          alarm_id: 0
          time: "14:00:00" # 9:00 AM EST
          trigger: "daily"
          operation: "playback"
```

### Sleep Timer Automation

Automatically set sleep timer when starting bedtime music:

```yaml
automation:
  alias: "Bedtime Music with Sleep Timer"
  description: "Play sleep sounds and auto-shutoff after 30 minutes"
  trigger:
    platform: state
    entity_id: input_boolean.bedtime_mode
    to: "on"
  action:
    # Start playing sleep sounds
    - service: wiim.play_preset
      target:
        entity_id: media_player.bedroom
      data:
        preset: 6 # Your sleep sounds preset
    # Set volume low
    - service: media_player.volume_set
      target:
        entity_id: media_player.bedroom
      data:
        volume_level: 0.15
    # Set 30 minute sleep timer
    - service: wiim.set_sleep_timer
      target:
        entity_id: media_player.bedroom
      data:
        sleep_time: 1800 # 30 minutes in seconds
```

### Gradual Volume Sleep Timer

Fade volume before sleep timer ends:

```yaml
automation:
  alias: "Fade to Sleep"
  trigger:
    platform: state
    entity_id: input_boolean.sleep_mode
    to: "on"
  action:
    # Start music
    - service: wiim.play_preset
      target:
        entity_id: media_player.bedroom
      data:
        preset: 6
    # Initial volume
    - service: media_player.volume_set
      target:
        entity_id: media_player.bedroom
      data:
        volume_level: 0.3
    # Wait 15 minutes
    - delay: "00:15:00"
    # Reduce volume
    - service: media_player.volume_set
      target:
        entity_id: media_player.bedroom
      data:
        volume_level: 0.15
    # Wait 10 minutes
    - delay: "00:10:00"
    # Further reduce
    - service: media_player.volume_set
      target:
        entity_id: media_player.bedroom
      data:
        volume_level: 0.05
    # Set sleep timer for final 5 minutes
    - service: wiim.set_sleep_timer
      target:
        entity_id: media_player.bedroom
      data:
        sleep_time: 300
```

### Smart Sleep Timer Based on Presence

Only set sleep timer if everyone is home:

```yaml
automation:
  alias: "Conditional Sleep Timer"
  trigger:
    platform: time
    at: "22:30:00"
  condition:
    - condition: state
      entity_id: group.family
      state: "home"
    - condition: state
      entity_id: media_player.bedroom
      state: "playing"
  action:
    - service: wiim.set_sleep_timer
      target:
        entity_id: media_player.bedroom
      data:
        sleep_time: 1800
```

### Clear Sleep Timer Automation

Cancel sleep timer when you get up early:

```yaml
automation:
  alias: "Cancel Sleep Timer on Movement"
  trigger:
    platform: state
    entity_id: binary_sensor.bedroom_motion
    to: "on"
  condition:
    - condition: time
      after: "05:00:00"
      before: "07:00:00"
  action:
    - service: wiim.clear_sleep_timer
      target:
        entity_id: media_player.bedroom
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
      - service: wiim.play_preset
        target:
          entity_id: media_player.dining_room_group_coordinator
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
      # Gradually lower volume on active groups
      - service: media_player.volume_set
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
          volume_level: 0.1
      # Wait then ungroup all
      - delay: "00:02:00"
      - service: script.wiim_ungroup_all
      # Start sleep sounds in bedroom only
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
      - service: wiim.play_preset
        target:
          entity_id: media_player.living_room
        data:
          preset: 2
      - service: media_player.volume_set
        target:
          entity_id: media_player.living_room
        data:
          volume_level: 0.3

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

### Source Change Detection

**Note**: The media player entity's `source` attribute shows the current input (Bluetooth, AirPlay, Line In, etc.). You can trigger automations when the source changes:

```yaml
automation:
  - alias: "Bluetooth Connected"
    description: "Adjust volume when Bluetooth source is selected"
    trigger:
      platform: state
      entity_id: media_player.living_room
      attribute: source
      to: "Bluetooth"
    action:
      - service: media_player.volume_set
        target:
          entity_id: media_player.living_room
        data:
          volume_level: 0.6
      - service: notify.mobile_app
        data:
          message: "Bluetooth connected to Living Room speaker"
```

### Bluetooth Output Detection

**Recommended**: Use the **Audio Output Mode** select entity to detect when Bluetooth output is active. This entity shows "BT: [Device Name]" when outputting audio to a Bluetooth device (e.g., headphones, soundbar).

```yaml
automation:
  - alias: "Bluetooth Output Active"
    description: "Notify when audio is being sent to Bluetooth device"
    trigger:
      platform: state
      entity_id: select.living_room_audio_output_mode
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state.startswith('BT:') }}"
    action:
      - service: notify.mobile_app
        data:
          message: "Audio now playing to: {{ trigger.to_state.state }}"

  - alias: "Bluetooth Output Deactivated"
    description: "Notify when switching away from Bluetooth output"
    trigger:
      platform: state
      entity_id: select.living_room_audio_output_mode
    condition:
      - condition: template
        value_template: >
          {{ trigger.from_state.state.startswith('BT:') and
             not trigger.to_state.state.startswith('BT:') }}
    action:
      - service: notify.mobile_app
        data:
          message: "Switched from Bluetooth to {{ trigger.to_state.state }}"
```

**Check Specific Bluetooth Device:**

```yaml
condition:
  - condition: state
    entity_id: select.living_room_audio_output_mode
    state: "BT: Sony WH-1000XM4"
```

**Check Any Bluetooth Output (Template):**

```yaml
condition:
  - condition: template
    value_template: "{{ states('select.living_room_audio_output_mode').startswith('BT:') }}"
```

**Alternative: Template Trigger for Any Source Change**

```yaml
automation:
  - alias: "Source Change Notification"
    description: "Notify when input source changes"
    trigger:
      platform: template
      value_template: >
        {{ states.media_player.living_room.attributes.source !=
           state_attr('media_player.living_room', 'source') }}
    action:
      - service: notify.mobile_app
        data:
          message: >
            Input changed to: {{ states.media_player.living_room.attributes.source }}
```

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
      # Make announcement (uses TTS)
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

### Dynamic Volume Control

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

## 📱 Group Management Dashboard

### Group Preset Selector

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
    initial: "Solo (No Groups)"
    icon: mdi:speaker-multiple

# Automation to apply presets
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

### Control Only Group Masters

```yaml
automation:
  - alias: "Control Via Masters Only"
    description: "Send commands to group masters for efficiency"
    trigger:
      platform: state
      entity_id: input_boolean.music_mode
      to: "on"
    action:
      - service: media_player.media_play
        target:
          entity_id: >
            {{ states.sensor
               | selectattr('entity_id', 'match', '.*_multiroom_role$')
               | selectattr('state', 'eq', 'Master')
               | map(attribute='entity_id')
               | map('replace', 'sensor.', 'media_player.')
               | map('replace', '_multiroom_role', '')
               | list }}
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

### Weekly Health Check

```yaml
automation:
  - alias: "WiiM Health Check"
    description: "Weekly maintenance and sync"
    trigger:
      platform: time
      at: "03:00:00"
    condition:
      platform: time
      weekday: sun
    action:
      # Sync time on all devices
      - service: wiim.sync_time
        target:
          entity_id:
            - media_player.living_room
            - media_player.kitchen
            - media_player.bedroom
      # Check for offline devices and reboot if needed
      - repeat:
          for_each: >
            {{ states.media_player
              | selectattr('entity_id', 'match', 'media_player\..*')
              | selectattr('state', 'equalto', 'unavailable')
              | map(attribute='entity_id') | list }}
          sequence:
            - service: wiim.reboot_device
              target:
                entity_id: "{{ repeat.item }}"
            - delay: "00:01:00"
```

## 📚 Template Helpers

Essential templates for WiiM automations:

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

input_boolean:
  music_mode:
    name: Music Mode
    icon: mdi:music-circle

  party_mode:
    name: Party Mode
    icon: mdi:party-popper
```

## 🎯 Pro Tips

1. **Use Role Sensors**: Always check `sensor.{device}_multiroom_role` before sending commands
2. **Group First**: Create groups before setting volume/playback
3. **Master Control**: Use group coordinators (`*_group_coordinator`) for group operations
4. **Error Handling**: Add `continue_on_error: true` for robust automations
5. **Timing**: Add small delays between group operations for reliability

## 📱 Quick Station Switching

```yaml
input_select:
  radio_station:
    options:
      - BBC Radio 2
      - Jazz FM
      - Classic FM

automation:
  - trigger:
      platform: state
      entity_id: input_select.radio_station
    action:
      service: media_player.play_media
      target:
        entity_id: media_player.living_room
      data:
        media_content_type: music
        media_content_id: >
          {% set stations = {
            'BBC Radio 2': 'http://stream.live.vc.bbcmedia.co.uk/bbc_radio_two',
            'Jazz FM': 'http://jazz.fm/stream',
            'Classic FM': 'http://classic.fm/stream'
          } %}
          {{ stations[trigger.to_state.state] }}
```

## 📚 More Resources

- **[🎛️ User Guide](user-guide.md)** - Complete features and configuration reference
- **[❓ FAQ & Troubleshooting](faq-and-troubleshooting.md)** - Quick answers and solutions

---

**Need help getting started?** Check our [Quick Start Guide](README.md) for installation and basic setup.
