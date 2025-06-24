# WiiM Integration - Frequently Asked Questions

Quick answers to common questions about the WiiM Home Assistant integration.

## General Questions

### What WiiM devices are supported?

All WiiM and LinkPlay-based devices are supported:

- **WiiM**: Mini, Pro, Pro Plus, Amp, Ultra
- **LinkPlay Partners**: Arylic, Audio Pro, DOSS, Dayton Audio, iEast, Muzo, Rakoit, GGMM, August, SoundBot, and many more
- **Requirements**: Device must support LinkPlay HTTP API

### Do I need the WiiM Home app?

**Not required** for basic operation, but recommended for:

- Initial WiFi setup
- Firmware updates
- Configuring presets
- Advanced audio settings
- Creating speaker groups (optional)

### What's the difference between this and the official LinkPlay integration?

| Feature            | WiiM Integration    | LinkPlay Integration |
| ------------------ | ------------------- | -------------------- |
| **Focus**          | User experience     | Technical accuracy   |
| **Multiroom**      | Full visual support | Basic support        |
| **Group Control**  | Dedicated entities  | Manual coordination  |
| **Polling**        | Smart adaptive      | Fixed interval       |
| **Device Support** | WiiM + LinkPlay     | LinkPlay only        |
| **Installation**   | HACS                | Core                 |

## Installation Questions

### Why can't I find the integration after installing?

1. **Clear browser cache**: Ctrl+F5 (Cmd+Shift+R on Mac)
2. **Restart Home Assistant**: Settings → System → Restart
3. **Check installation path**: `/config/custom_components/wiim/`
4. **Verify in logs**: Look for "Setup of domain wiim took X seconds"

### Why does HACS show "Repository structure for 0.1.0 is not compliant"?

This is a HACS bug with older versions. Solutions:

1. Click "Download" anyway - it works fine
2. Or manually download from [GitHub Releases](https://github.com/mjcumming/wiim/releases)
3. Update HACS to latest version

### Can I run this alongside the core LinkPlay integration?

**Yes**, but:

- Use different devices for each integration
- Don't add same device to both
- May see duplicate discovery notifications

## Discovery & Setup Questions

### Why aren't my speakers discovered automatically?

Common causes:

- **Different network/VLAN**: HA and speakers must be on same subnet
- **Firewall blocking**: Allow UDP port 1900 (SSDP/UPnP)
- **Router settings**: Enable multicast/IGMP snooping
- **Use manual setup**: Add by IP address instead

### How do I find my speaker's IP address?

Multiple methods:

1. **Router admin panel**: Check DHCP client list
2. **WiiM Home app**: Device Settings → About
3. **Network scanner**: Use Fing or similar app
4. **Home Assistant**: Developer Tools → Services → `wiim.discover`

### Why does my speaker show as "Unavailable"?

Check these in order:

1. **Ping the device**: `ping 192.168.1.x`
2. **Power cycle speaker**: Unplug for 10 seconds
3. **Check IP changed**: Router may have assigned new IP
4. **Remove and re-add**: With current IP address

## Multiroom Questions

### What is the role sensor and why should I care?

The role sensor shows multiroom status:

```yaml
sensor.living_room_multiroom_role: "Master" # Controls group
sensor.kitchen_multiroom_role: "Slave" # Follows master
sensor.bedroom_multiroom_role: "Solo" # Independent
```

**Why it matters**:

- Automations can target only masters
- Shows group relationships clearly
- Detects group formation/dissolution
- Essential for multiroom understanding

### How do groups work differently than Sonos?

| Aspect        | WiiM/LinkPlay       | Sonos        |
| ------------- | ------------------- | ------------ |
| **Sync**      | Master broadcasts   | Mesh network |
| **Latency**   | ~20ms               | ~5ms         |
| **Stability** | Good on same switch | Excellent    |
| **Max Size**  | 10 speakers         | 32 speakers  |

### Why does my group keep breaking apart?

Common fixes:

1. **Use wired for master**: Most stable configuration
2. **Fix WiFi**: Improve signal, reduce interference
3. **Static IPs**: Use DHCP reservations
4. **Same firmware**: Update all speakers
5. **Check router**: Disable AP isolation

### What's the new group coordinator entity?

When a speaker becomes master, a virtual media player appears:

```yaml
media_player.living_room_group_coordinator
```

Benefits:

- Single entity controls entire group
- Shows in standard media player cards
- Includes member details in attributes
- Automatically appears/disappears

## Volume Questions

### How does group volume work?

**Current behavior**: Sets all speakers to same absolute level

```yaml
# Before: Master 80%, Slave 40%
# Set group to 50%
# After: Both at 50%
```

**Individual control** still available:

```yaml
# Adjust single speaker in group
service: media_player.volume_set
target:
  entity_id: media_player.kitchen
data:
  volume_level: 0.3
```

### Why does volume jump when grouping?

Group volume shows the **loudest** member. When you adjust group volume, all speakers sync to that level. This prevents accidentally blasting quiet speakers.

### Can I maintain relative volumes?

Not currently, but workarounds exist:

```yaml
# Save relative volumes before grouping
scene:
  - name: "Speaker Volumes"
    entities:
      media_player.living_room:
        volume_level: 0.6
      media_player.kitchen:
        volume_level: 0.3
```

## Playback Questions

### What audio formats are supported?

**Lossless**: FLAC, WAV, ALAC up to 24-bit/192kHz
**Compressed**: MP3, AAC, OGG up to 320kbps
**Streaming**: HTTP/HTTPS streams, HLS, DLNA

See [Media Formats Guide](media-formats.md) for complete list.

### Why won't my media play?

Check in order:

1. **Format supported?** Try MP3 first
2. **URL accessible?** Test in browser
3. **Network path?** Must be reachable from speaker
4. **Use media browser** to test known-good content

### How do I play TuneIn/Radio stations?

Get the direct stream URL:

```yaml
# Good - Direct stream
media_content_id: "http://stream.radio.com/station.mp3"

# Bad - Web player page
media_content_id: "http://tunein.com/station"
```

Use [Radio Browser](https://www.radio-browser.info) to find stream URLs.

### Can I play from my NAS/Plex/Jellyfin?

Yes, via DLNA or direct URLs:

```yaml
# DLNA browsing
- Enable DLNA on your server
- Speaker will discover automatically

# Direct URL
service: media_player.play_media
data:
  media_content_id: "http://nas.local:32400/music/song.mp3"
```

## Control Questions

### Why do some buttons not work?

Not all speakers support all features:

- **EQ**: Pro/Pro Plus/Ultra only
- **Presets**: Check available slots in WiiM app
- **Sources**: Varies by model (no optical on Mini)

### How do I use the equalizer?

```yaml
# Select preset
service: media_player.select_sound_mode
target:
  entity_id: media_player.living_room
data:
  sound_mode: "Rock"

# Or use service for custom EQ
service: wiim.set_eq
data:
  preset: "custom"
  custom_values: [0, +2, +4, +2, 0, 0, -2, 0, +2, +4]
```

### What's the difference between sources and apps?

**Sources**: Physical inputs or protocols

- WiFi, Bluetooth, Line In, Optical

**Apps**: Streaming services

- Spotify, Tidal, Amazon Music

The integration shows both where appropriate.

## Performance Questions

### How often does the integration poll devices?

**Adaptive polling**:

- Playing: Every 1 second
- Idle: Every 5 seconds
- After commands: Immediate

### Will this slow down my Home Assistant?

Impact is minimal:

- **CPU**: <0.5% per speaker
- **Network**: ~2KB/s when playing
- **Database**: ~50 entries/hour/speaker

### How many speakers can I have?

Practical limits:

- **5-10 speakers**: No issues
- **10-20 speakers**: May notice slight lag
- **20+ speakers**: Consider multiple HA instances

## Troubleshooting Questions

### What do the error messages mean?

| Error                | Meaning             | Solution                          |
| -------------------- | ------------------- | --------------------------------- |
| `Connection timeout` | Can't reach speaker | Check network                     |
| `Invalid response`   | Firmware issue      | Update speaker                    |
| `Unknown command`    | Feature unsupported | Check compatibility               |
| `SSL error`          | Certificate issue   | Integration handles automatically |

### How do I enable debug logging?

Add to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.wiim: debug
    custom_components.wiim.coordinator: debug
```

Then check logs at Settings → System → Logs

### Where do I report bugs?

1. **First**: Check [existing issues](https://github.com/mjcumming/wiim/issues)
2. **Enable debug logging** and reproduce
3. **Create issue** with:
   - HA version
   - Integration version
   - Speaker model
   - Debug logs
   - Steps to reproduce

## Advanced Questions

### Can I control speakers from Node-RED?

Yes! Use standard HA service calls:

```json
{
  "domain": "media_player",
  "service": "play_media",
  "target": {
    "entity_id": "media_player.living_room"
  },
  "data": {
    "media_content_type": "music",
    "media_content_id": "http://stream.url"
  }
}
```

### How do I template group-aware automations?

```yaml
# Find all masters
{% set masters = states.sensor
   | selectattr('entity_id', 'match', '.*_multiroom_role$')
   | selectattr('state', 'eq', 'Master')
   | map(attribute='entity_id')
   | map('replace', 'sensor.', 'media_player.')
   | map('replace', '_multiroom_role', '')
   | list %}

# Find specific speaker's role
{% set role = states('sensor.living_room_multiroom_role') %}
```

### Can I create custom services?

Yes, via `python_scripts`:

```python
# python_scripts/wiim_custom.py
speaker = hass.states.get('media_player.living_room')
if speaker.state == 'playing':
    hass.services.call('media_player', 'volume_set', {
        'entity_id': 'media_player.living_room',
        'volume_level': 0.5
    })
```

### What's the roadmap?

Current priorities:

1. ~~Virtual group media players~~ ✅
2. ~~Adaptive polling~~ ✅
3. ~~Media browser for HA sources~~ ✅
4. Preset management UI
5. Advanced scheduling
6. Energy monitoring

## Tips & Tricks

### Quick Station Switching

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
        media_content_id: >
          {% set stations = {
            'BBC Radio 2': 'http://stream.bbc.co.uk/radio2',
            'Jazz FM': 'http://jazz.fm/stream',
            'Classic FM': 'http://classic.fm/stream'
          } %}
          {{ stations[trigger.to_state.state] }}
```

### Group Memory

```yaml
# Save current group config
- service: scene.create
  data:
    scene_id: speaker_groups
    snapshot_entities:
      - sensor.living_room_multiroom_role
      - sensor.kitchen_multiroom_role
      - sensor.bedroom_multiroom_role

# Restore later
- service: scene.turn_on
  target:
    entity_id: scene.speaker_groups
```

### Volume Ramping

```yaml
# Gradually increase volume
- repeat:
    count: 10
    sequence:
      - service: media_player.volume_up
        target:
          entity_id: media_player.bedroom
      - delay: "00:00:02"
```

Still have questions? Ask in:

- [GitHub Discussions](https://github.com/mjcumming/wiim/discussions)
- [Home Assistant Community](https://community.home-assistant.io/)
- [Discord #wiim channel](https://discord.gg/home-assistant)
