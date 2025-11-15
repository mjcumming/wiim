# WiiM Integration - FAQ

Quick answers to frequently asked questions.

## General Questions

### What WiiM devices are supported?

All WiiM and LinkPlay-based devices:

- **WiiM**: Mini, Pro, Pro Plus, Amp, Ultra
- **LinkPlay Partners**: Arylic, DOSS, Dayton Audio, iEast, and many more

### Do I need the WiiM Home app?

**Not required** for basic operation, but recommended for:

- Initial WiFi setup and firmware updates
- Configuring presets and advanced audio settings
- Creating speaker groups (optional)

## Installation Questions

### Why can't I find the integration after installing?

1. Clear browser cache (Ctrl+F5) and restart Home Assistant
2. Verify files are in `/config/custom_components/wiim/`
3. Check logs: Settings → System → Logs (look for "wiim" entries)

### Why aren't my speakers discovered automatically?

Common causes:

- Different network/VLAN (HA and speakers must be on same subnet)
- Firewall blocking UDP port 1900 (UPnP/SSDP)
- Router settings (enable multicast/IGMP snooping)

**Solution**: Use manual setup with IP address.

### How do I find my speaker's IP address?

- **Router admin panel**: Check DHCP client list
- **WiiM Home app**: Device Settings → About
- **Network scanner**: Use Fing or similar app

## Multiroom Questions

### What is the role sensor and why should I care?

Shows multiroom status: `Solo`/`Master`/`Slave`

Essential for:

- Targeting only masters in automations
- Detecting group formation/dissolution
- Understanding group relationships

### Why does my group keep breaking apart?

Common fixes:

1. Use wired connection for master speaker
2. Improve WiFi signal and reduce interference
3. Use DHCP reservations for stable IPs
4. Update all speakers to same firmware
5. Check router settings (disable AP isolation)

### What's the group coordinator entity?

When a speaker becomes master with slaves:

```yaml
media_player.living_room_group_coordinator
```

- Only exists when actively coordinating a group
- Provides unified control for entire group
- Automatically appears/disappears with group changes
- **Dynamic naming**: Changes based on speaker role
  - Solo: `"Living Room"`
  - Group Master: `"Living Room Group Master"`

## Volume Questions

### How does group volume work?

The group coordinator shows the **maximum volume** of any member and sets all speakers to the same level when adjusted.

```yaml
# Use group coordinator to control entire group
service: media_player.volume_set
target:
  entity_id: media_player.living_room_group_coordinator
data:
  volume_level: 0.5
```

### Can I maintain relative volumes?

Not currently. Use scenes to save/restore volume relationships:

```yaml
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

- **Lossless**: FLAC, WAV, ALAC up to 24-bit/192kHz
- **Compressed**: MP3, AAC, OGG up to 320kbps
- **Streaming**: HTTP/HTTPS streams, HLS, DLNA

### Why won't my media play?

Check in order:

1. Format supported? (Try MP3 first)
2. URL accessible? (Test in browser)
3. Network reachable from speaker?
4. Use media browser to test known-good content

### How do I play TuneIn/Radio stations?

Get the direct stream URL:

```yaml
# Good - Direct stream
media_content_id: "http://stream.radio.com/station.mp3"

# Bad - Web player page
media_content_id: "http://tunein.com/station"
```

Use [Radio Browser](https://www.radio-browser.info) to find stream URLs.

### Why does the stop button behave differently with Bluetooth?

**Bluetooth sources** have limited playback control compared to network sources:

- **Network sources** (WiFi, AirPlay, streaming): Support both pause and stop
- **Bluetooth sources**: Only support pause (not stop)

The integration automatically handles this by using pause instead of stop when Bluetooth is the active source. This ensures the stop button always works, regardless of the input source.

**Note**: This is a device limitation, not an integration issue. The behavior is consistent across all WiiM devices.

## Control Questions

### Why do some buttons not work?

Not all speakers support all features:

- **EQ**: Pro/Pro Plus/Ultra only
- **Presets**: Check available slots in WiiM app
- **Sources**: Varies by model

### How do I use the equalizer?

```yaml
# Select preset
service: media_player.select_sound_mode
target:
  entity_id: media_player.living_room
data:
  sound_mode: "Rock"

# Custom EQ
service: wiim.set_eq
target:
  entity_id: media_player.living_room
data:
  preset: "custom"
  custom_values: [0, +2, +4, +2, 0, 0, -2, 0, +2, +4]
```

## Troubleshooting Questions

### What do error messages mean?

| Error                | Meaning        | Solution       |
| -------------------- | -------------- | -------------- |
| `Connection timeout` | Can't reach    | Check network  |
| `Invalid response`   | Firmware issue | Update speaker |
| `Unknown command`    | Not supported  | Check model    |

### How do I enable debug logging?

```yaml
# configuration.yaml
logger:
  logs:
    custom_components.wiim: debug
```

Then check: Settings → System → Logs

### Where do I report bugs?

1. Check [existing issues](https://github.com/mjcumming/wiim/issues)
2. Enable debug logging and reproduce issue
3. Create issue with HA version, integration version, speaker model, logs, and steps to reproduce

## Tips & Tricks

### Quick Station Switching

```yaml
input_select:
  radio_station:
    options: [BBC Radio 2, Jazz FM, Classic FM]

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

# Restore later
- service: scene.turn_on
  target:
    entity_id: scene.speaker_groups
```

**Need more help?**

- [User Guide](user-guide.md) - Complete feature reference
- [Automation Cookbook](automation-cookbook.md) - Ready-to-use examples
- [Troubleshooting Guide](troubleshooting.md) - Fix common issues
- [GitHub Discussions](https://github.com/mjcumming/wiim/discussions)
- [HA Community](https://community.home-assistant.io/)
