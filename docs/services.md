# WiiM Integration - Services Reference

Complete documentation for all WiiM integration services with examples and use cases.

## Media Control Services

### `wiim.play_preset`

Play a preset configured in the WiiM Home app.

| Parameter | Required | Type    | Description                            |
| --------- | -------- | ------- | -------------------------------------- |
| `preset`  | Yes      | integer | Preset number (1-20, device dependent) |

**Examples:**

```yaml
# Play preset 1 (e.g., BBC Radio)
service: wiim.play_preset
target:
  entity_id: media_player.living_room
data:
  preset: 1

# Play preset on multiple speakers
service: wiim.play_preset
target:
  entity_id:
    - media_player.living_room
    - media_player.kitchen
data:
  preset: 3

# In an automation
automation:
  - alias: "Morning Radio"
    trigger:
      platform: time
      at: "07:00:00"
    action:
      service: wiim.play_preset
      target:
        entity_id: media_player.bedroom
      data:
        preset: 1
```

**Notes:**

- Preset numbers depend on device model (typically 1-6 or 1-20)
- Presets are configured in the WiiM Home app
- Empty preset slots will produce no action

---

### `wiim.play_url`

Play media from a URL (radio streams, podcasts, audio files).

| Parameter | Required | Type   | Description                     |
| --------- | -------- | ------ | ------------------------------- |
| `url`     | Yes      | string | HTTP/HTTPS URL of media to play |

**Examples:**

```yaml
# Play internet radio stream
service: wiim.play_url
target:
  entity_id: media_player.living_room
data:
  url: "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_two"

# Play podcast episode
service: wiim.play_url
target:
  entity_id: media_player.office
data:
  url: "https://example.com/podcast/episode123.mp3"

# Play local network file
service: wiim.play_url
target:
  entity_id: media_player.bedroom
data:
  url: "http://192.168.1.100:8123/local/music/song.flac"
```

**Supported Formats:**

- Streams: HTTP/HTTPS radio streams, HLS
- Files: MP3, FLAC, WAV, AAC, OGG, M4A
- Protocols: HTTP, HTTPS (self-signed certificates supported)

---

### `wiim.play_playlist`

Play an M3U/M3U8 playlist file.

| Parameter      | Required | Type   | Description              |
| -------------- | -------- | ------ | ------------------------ |
| `playlist_url` | Yes      | string | URL of M3U/M3U8 playlist |

**Examples:**

```yaml
# Play radio station playlist
service: wiim.play_playlist
target:
  entity_id: media_player.kitchen
data:
  playlist_url: "http://example.com/stations.m3u"

# Play custom playlist from local server
service: wiim.play_playlist
target:
  entity_id: media_player.whole_house_group
data:
  playlist_url: "http://192.168.1.100:8080/playlists/party.m3u8"
```

---

### `wiim.play_notification`

Play a notification sound with automatic resume of previous playback.

| Parameter | Required | Type   | Description               |
| --------- | -------- | ------ | ------------------------- |
| `url`     | Yes      | string | URL of notification sound |

**Examples:**

```yaml
# Doorbell notification
service: wiim.play_notification
target:
  entity_id: media_player.living_room
data:
  url: "http://192.168.1.100:8123/local/sounds/doorbell.mp3"

# TTS notification with restore
service: wiim.play_notification
target:
  entity_id: media_player.kitchen
data:
  url: "{{ tts_url }}"  # From TTS service

# Emergency alert to all speakers
service: wiim.play_notification
target:
  entity_id: all
data:
  url: "http://192.168.1.100:8123/local/sounds/alert.wav"
```

**Behavior:**

- Current playback is paused
- Notification plays at current volume
- Previous playback resumes automatically
- Works with grouped speakers

## Audio Control Services

### `wiim.set_eq`

Configure equalizer settings (presets or custom).

| Parameter       | Required | Type   | Description                 |
| --------------- | -------- | ------ | --------------------------- |
| `preset`        | Yes      | string | EQ preset name or "custom"  |
| `custom_values` | No\*     | list   | 10 band values (-12 to +12) |

\*Required when preset is "custom"

**Available Presets:**

- `flat` - Neutral response
- `acoustic` - Enhanced vocals and instruments
- `bass` - Boosted low frequencies
- `classical` - Optimized for orchestral music
- `dance` - Club-style bass boost
- `electronic` - Enhanced synthetic sounds
- `jazz` - Warm mids and controlled bass
- `pop` - Vocal presence and clarity
- `rock` - Powerful mids and highs
- `treble` - Bright, detailed highs
- `vocal` - Voice enhancement
- `custom` - User-defined 10-band EQ

**Examples:**

```yaml
# Apply rock preset
service: wiim.set_eq
target:
  entity_id: media_player.living_room
data:
  preset: "rock"

# Custom EQ curve
service: wiim.set_eq
target:
  entity_id: media_player.studio
data:
  preset: "custom"
  custom_values:
    - -2  # 31.5 Hz
    - 0   # 63 Hz
    - 2   # 125 Hz
    - 3   # 250 Hz
    - 1   # 500 Hz
    - 0   # 1 kHz
    - 0   # 2 kHz
    - -1  # 4 kHz
    - 2   # 8 kHz
    - 4   # 16 kHz

# Night mode (reduced bass)
service: wiim.set_eq
target:
  entity_id: media_player.bedroom
data:
  preset: "custom"
  custom_values: [-6, -4, -2, 0, 0, 0, 0, 0, -1, -2]
```

**Frequency Bands:**

1. 31.5 Hz - Sub-bass
2. 63 Hz - Bass
3. 125 Hz - Lower midrange
4. 250 Hz - Midrange
5. 500 Hz - Upper midrange
6. 1 kHz - Presence
7. 2 kHz - Brilliance
8. 4 kHz - High-mids
9. 8 kHz - Highs
10. 16 kHz - Air/sparkle

## Device Management Services

### `wiim.reboot_device`

Reboot the WiiM device (useful for applying updates or resolving issues).

**Examples:**

```yaml
# Reboot single device
service: wiim.reboot_device
target:
  entity_id: media_player.living_room

# Reboot all WiiM devices (maintenance)
service: wiim.reboot_device
target:
  entity_id:
    - media_player.living_room
    - media_player.kitchen
    - media_player.bedroom

# Scheduled reboot automation
automation:
  - alias: "Weekly WiiM Maintenance"
    trigger:
      platform: time
      at: "03:00:00"
    condition:
      platform: time
      weekday: sun
    action:
      - service: wiim.reboot_device
        target:
          entity_id: all
      - delay: "00:02:00"  # Wait for reboot
      - service: wiim.sync_time
        target:
          entity_id: all
```

**Notes:**

- Device will be unavailable for 30-60 seconds
- Current playback will stop
- Groups may need to be reformed
- Firmware updates are applied during reboot

---

### `wiim.sync_time`

Synchronize device clock with Home Assistant time.

**Examples:**

```yaml
# Sync single device
service: wiim.sync_time
target:
  entity_id: media_player.kitchen

# Sync all devices after DST change
service: wiim.sync_time
target:
  entity_id: all

# Daily time sync automation
automation:
  - alias: "Daily Time Sync"
    trigger:
      platform: time
      at: "04:00:00"
    action:
      service: wiim.sync_time
      target:
        entity_id: group.all_wiim_speakers
```

**Why Sync Time?**

- Ensures accurate timestamps in device logs
- Fixes playback position tracking
- Required for scheduled device actions
- Corrects drift after power loss

## Standard Media Player Services

WiiM devices support all standard Home Assistant media player services:

### Volume Control

```yaml
# Set absolute volume (0.0 to 1.0)
service: media_player.volume_set
target:
  entity_id: media_player.living_room
data:
  volume_level: 0.5

# Relative volume adjustment
service: media_player.volume_up
target:
  entity_id: media_player.living_room

service: media_player.volume_down
target:
  entity_id: media_player.living_room

# Mute control
service: media_player.volume_mute
target:
  entity_id: media_player.living_room
data:
  is_volume_muted: true
```

### Playback Control

```yaml
# Transport controls
service: media_player.media_play
service: media_player.media_pause
service: media_player.media_stop
service: media_player.media_next_track
service: media_player.media_previous_track

# Seek to position (seconds)
service: media_player.media_seek
target:
  entity_id: media_player.living_room
data:
  seek_position: 120

# Play specific media
service: media_player.play_media
target:
  entity_id: media_player.living_room
data:
  media_content_type: music
  media_content_id: "http://stream.example.com/radio.mp3"
```

### Source & Mode Selection

```yaml
# Select input source
service: media_player.select_source
target:
  entity_id: media_player.living_room
data:
  source: "Bluetooth"

# Select sound mode (EQ preset)
service: media_player.select_sound_mode
target:
  entity_id: media_player.living_room
data:
  sound_mode: "Jazz"

# Shuffle control
service: media_player.shuffle_set
target:
  entity_id: media_player.living_room
data:
  shuffle: true

# Repeat mode
service: media_player.repeat_set
target:
  entity_id: media_player.living_room
data:
  repeat: "all"  # off, all, one
```

### Grouping Services

```yaml
# Create/extend group
service: media_player.join
target:
  entity_id: media_player.living_room  # Becomes coordinator
data:
  group_members:
    - media_player.kitchen
    - media_player.dining_room

# Leave group
service: media_player.unjoin
target:
  entity_id: media_player.kitchen
```

## Service Response Data

Some services return data that can be used in automations:

```yaml
# Example: Get current EQ setting
service: wiim.get_eq_status
target:
  entity_id: media_player.living_room
response_variable: eq_status

# Use in condition
condition: template
value_template: "{{ eq_status.preset == 'rock' }}"
```

## Error Handling

Services may fail for various reasons. Handle errors gracefully:

```yaml
# With error handling
- alias: "Safe Preset Play"
  sequence:
    - service: wiim.play_preset
      target:
        entity_id: media_player.living_room
      data:
        preset: 1
      continue_on_error: true
    - condition: template
      value_template: "{{ not states.media_player.living_room.state == 'playing' }}"
    - service: notify.mobile_app
      data:
        message: "Failed to play preset on Living Room speaker"
```

## Best Practices

1. **Use Entity Checks**: Verify device availability before sending commands
2. **Add Delays**: Allow time for device state changes (especially after reboot)
3. **Group Commands**: Use target lists to control multiple speakers efficiently
4. **Error Recovery**: Include fallback actions for critical automations
5. **Volume Safety**: Set reasonable volume limits for automated playback

## Tips & Tricks

### Dynamic Volume Based on Time

```yaml
service: media_player.volume_set
target:
  entity_id: media_player.bedroom
data:
  volume_level: >
    {% set hour = now().hour %}
    {% if 6 <= hour < 8 %} 0.2
    {% elif 8 <= hour < 22 %} 0.4
    {% else %} 0.1
    {% endif %}
```

### Conditional EQ

```yaml
# Apply EQ based on source
- choose:
    - conditions:
        - condition: state
          entity_id: media_player.living_room
          attribute: source
          state: "Bluetooth"
      sequence:
        - service: wiim.set_eq
          target:
            entity_id: media_player.living_room
          data:
            preset: "vocal" # Optimize for phone calls
```

### Group-Aware Volume

```yaml
# Set volume based on group size
service: media_player.volume_set
target:
  entity_id: media_player.living_room_group_coordinator
data:
  volume_level: >
    {% set members = state_attr('media_player.living_room_group_coordinator', 'group_members') | length %}
    {% if members > 3 %} 0.6
    {% elif members > 1 %} 0.5
    {% else %} 0.4
    {% endif %}
```
