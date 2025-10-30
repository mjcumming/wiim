# WiiM TTS (Text-to-Speech) Guide

The WiiM integration now supports TTS announcements with role-aware group coordination, allowing you to send text-to-speech messages to your WiiM speakers.

## Basic Usage

### Simple TTS Announcement

```yaml
service: media_player.play_media
target:
  entity_id: media_player.living_room
data:
  media_content_type: music
  media_content_id: "media-source://tts?message=Hello, this is a test announcement"
  announce: true
```

### TTS with Custom Volume

```yaml
service: media_player.play_media
target:
  entity_id: media_player.living_room
data:
  media_content_type: music
  media_content_id: "media-source://tts?message=Volume test"
  announce: true
  extra:
    tts_volume: 75 # 75% volume
```

## Group Behavior

### Automatic Group Coordination

- **Solo Speakers**: TTS plays directly on the speaker
- **Master Speakers**: TTS plays on the master and all slaves in the group
- **Slave Speakers**: TTS is automatically delegated to the master for group-wide announcement

### Example: Group TTS

```yaml
# Send to master - plays on entire group
service: media_player.play_media
target:
  entity_id: media_player.living_room  # Master speaker
data:
  media_content_type: music
  media_content_id: "media-source://tts?message=Dinner is ready"
  announce: true

# Send to slave - automatically delegates to master
service: media_player.play_media
target:
  entity_id: media_player.kitchen  # Slave speaker
data:
  media_content_type: music
  media_content_id: "media-source://tts?message=Dinner is ready"
  announce: true
```

## Advanced Options

### Force Local TTS

Force TTS to play on a specific speaker, even if it's a slave:

```yaml
service: media_player.play_media
target:
  entity_id: media_player.kitchen
data:
  media_content_type: music
  media_content_id: "media-source://tts?message=Kitchen only message"
  announce: true
  extra:
    tts_behavior: "force_local"
```

### Force Group TTS

Ensure TTS plays group-wide (delegates to master if slave):

```yaml
service: media_player.play_media
target:
  entity_id: media_player.kitchen
data:
  media_content_type: music
  media_content_id: "media-source://tts?message=Group announcement"
  announce: true
  extra:
    tts_behavior: "force_group"
```

### Auto Behavior (Default)

Let the system decide based on speaker role:

```yaml
service: media_player.play_media
target:
  entity_id: media_player.kitchen
data:
  media_content_type: music
  media_content_id: "media-source://tts?message=Smart announcement"
  announce: true
  extra:
    tts_behavior: "auto" # Default behavior
```

## Group Coordinator TTS

Use the group coordinator entity for group-wide announcements:

```yaml
service: media_player.play_media
target:
  entity_id: media_player.living_room_group_coordinator
data:
  media_content_type: music
  media_content_id: "media-source://tts?message=Group announcement"
  announce: true
```

## TTS Behavior Options

| Behavior         | Solo Speaker  | Master Speaker | Slave Speaker       |
| ---------------- | ------------- | -------------- | ------------------- |
| `auto` (default) | Plays locally | Plays on group | Delegates to master |
| `force_local`    | Plays locally | Plays locally  | Plays locally       |
| `force_group`    | Plays locally | Plays on group | Delegates to master |

## Volume Control

### Default TTS Volume

- **70% of current volume** (minimum 30%)
- Automatically adjusted for optimal TTS clarity

### Custom TTS Volume

```yaml
service: media_player.play_media
target:
  entity_id: media_player.living_room
data:
  media_content_type: music
  media_content_id: "media-source://tts?message=Custom volume test"
  announce: true
  extra:
    tts_volume: 80 # 80% volume (0-100)
```

## State Management

TTS announcements automatically:

1. **Save current state** (volume, mute, playback)
2. **Pause current playback** (if playing)
3. **Set TTS volume**
4. **Play TTS audio**
5. **Wait for completion**
6. **Restore original state**

## Error Handling

### Slave Without Master

If a slave speaker has no coordinator:

```yaml
# This will raise an error
service: media_player.play_media
target:
  entity_id: media_player.orphaned_slave
data:
  media_content_type: music
  media_content_id: "media-source://tts?message=This will fail"
  announce: true
```

Error: `Slave speaker 'orphaned_slave' cannot play TTS independently`

### Network Issues

TTS will fail gracefully with network issues and restore original state.

## Integration with TTS Services

### Google Cloud TTS

```yaml
service: tts.cloud_say
data:
  entity_id: media_player.living_room
  message: "Hello from Google Cloud TTS"
```

### Local TTS

```yaml
service: tts.picotts_say
data:
  entity_id: media_player.living_room
  message: "Hello from local TTS"
```

## Automation Examples

### Doorbell Announcement

```yaml
automation:
  - alias: "Doorbell TTS"
    trigger:
      platform: state
      entity_id: binary_sensor.doorbell
      to: "on"
    action:
      - service: media_player.play_media
        target:
          entity_id: media_player.living_room_group_coordinator
        data:
          media_content_type: music
          media_content_id: "media-source://tts?message=Someone is at the door"
          announce: true
```

### Weather Alert

```yaml
automation:
  - alias: "Weather Alert TTS"
    trigger:
      platform: state
      entity_id: sensor.weather_alert
      to: "severe"
    action:
      - service: media_player.play_media
        target:
          entity_id: media_player.living_room
        data:
          media_content_type: music
          media_content_id: "media-source://tts?message=Severe weather warning"
          announce: true
          extra:
            tts_volume: 90
```

## Troubleshooting

### TTS Not Working

1. **Check speaker role**: Ensure the speaker is available and has the correct role
2. **Verify TTS engine**: Make sure your TTS engine is working
3. **Check logs**: Look for TTS-related errors in the logs

### Group Issues

1. **Verify group status**: Check that the group is active
2. **Check master-slave relationship**: Ensure slaves have a valid coordinator
3. **Test individual speakers**: Try TTS on individual speakers first

### Volume Issues

1. **Check current volume**: TTS volume is based on current speaker volume
2. **Verify TTS volume setting**: Custom TTS volume should be 0-100
3. **Test volume restoration**: Original volume should be restored after TTS

## Technical Details

### Supported TTS Engines

- All Home Assistant TTS engines
- Google Cloud TTS
- Local TTS engines (picoTTS, etc.)
- Custom TTS engines

### Media Source Format

TTS uses the standard Home Assistant media source format:

```
media-source://tts?message=<text>&engine=<engine>&language=<lang>
```

### Timeout

TTS completion detection has a 30-second timeout by default.

### State Restoration

- Volume and mute state are always restored
- Playback state is conditionally restored (only if it was playing before TTS)
