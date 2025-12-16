# WiiM Integration - FAQ & Troubleshooting

Quick answers to common questions and solutions to common problems.

---

## 📋 Frequently Asked Questions

### General Questions

**Q: What WiiM devices are supported?**

All WiiM and LinkPlay-based devices:

- **WiiM**: Mini, Pro, Pro Plus, Amp, Ultra
- **LinkPlay Partners**: Arylic, DOSS, Dayton Audio, iEast, and many more

**Q: Do I need the WiiM Home app?**

Not required for basic operation, but recommended for:

- Initial WiFi setup and firmware updates
- Configuring presets and advanced audio settings
- Initial speaker pairing (groups sync to Home Assistant automatically)

**Q: What is this pywiim library I keep seeing mentioned?**

[pywiim](https://github.com/mjcumming/pywiim) is a Python library that handles all communication with WiiM and LinkPlay devices. This integration is a thin wrapper around pywiim, focusing on providing the best Home Assistant experience while pywiim handles the device protocol complexity.

### Installation Questions

**Q: Why can't I find the integration after installing?**

1. Clear browser cache (Ctrl+F5) and restart Home Assistant
2. Verify files are in `/config/custom_components/wiim/`
3. Check logs: Settings → System → Logs (look for "wiim" entries)

**Q: Why aren't my speakers discovered automatically?**

Common causes:

- Different network/VLAN (HA and speakers must be on same subnet)
- Firewall blocking UDP port 1900 (UPnP/SSDP)
- Router settings (enable multicast/IGMP snooping)

**Solution:** Use manual setup with IP address.

**Q: How do I find my speaker's IP address?**

- **Router admin panel**: Check DHCP client list
- **WiiM Home app**: Device Settings → About
- **Network scanner**: Use Fing or similar app

### Multiroom Questions

**Q: What is the role sensor and why should I care?**

Shows multiroom status: `Solo`/`Master`/`Slave`

Essential for:

- Targeting only masters in automations
- Detecting group formation/dissolution
- Understanding group relationships

The role sensor is **always visible** - it's one of the most important entities for multiroom automation.

**Q: What's the difference between the speaker entity and the group coordinator?**

- **Speaker entity** (`media_player.living_room`): Controls individual speaker, always present
- **Group coordinator** (`media_player.living_room_group_coordinator`): Virtual entity that appears when speaker is master with slaves, controls entire group

Use the speaker entity for individual control and Music Assistant integration. Use the group coordinator for controlling the whole group at once.

**Q: What's the group coordinator entity?**

When a speaker becomes master with slaves, a virtual group coordinator appears:

```yaml
media_player.living_room_group_coordinator
```

Features:

- Only exists when actively coordinating a group (master + slaves)
- Provides unified control for entire group
- Automatically appears/disappears with group changes
- Name changes based on role:
  - Solo: `"Living Room"`
  - Group Master: `"Living Room Group Master"`

**Q: Why does my group keep breaking apart?**

Common fixes:

1. Use wired connection for master speaker
2. Improve WiFi signal and reduce interference
3. Use DHCP reservations for stable IPs
4. Update all speakers to same firmware
5. Check router settings (disable AP isolation, enable multicast)

**Q: Can I use groups created in the WiiM app?**

Yes! Groups created in the WiiM Home app automatically sync to Home Assistant within 5 seconds. The integration detects group changes and updates entities accordingly.

### Volume Questions

**Q: How does group volume work?**

The group coordinator shows the **maximum volume** of any member and sets all speakers to the same level when adjusted.

```yaml
# Use group coordinator to control entire group
service: media_player.volume_set
target:
  entity_id: media_player.living_room_group_coordinator
data:
  volume_level: 0.5
```

**Q: Can I maintain relative volumes between speakers in a group?**

Not currently. When you set the group coordinator volume, all speakers are set to the same level.

**Workaround:** Use scenes to save/restore volume relationships:

```yaml
scene:
  - name: "Speaker Volumes"
    entities:
      media_player.living_room:
        volume_level: 0.6
      media_player.kitchen:
        volume_level: 0.3
```

### Playback Questions

**Q: What audio formats are supported?**

- **Lossless**: FLAC, WAV, ALAC up to 24-bit/192kHz
- **Compressed**: MP3, AAC, OGG up to 320kbps
- **Streaming**: HTTP/HTTPS streams, HLS, DLNA

**Q: Why won't my media play?**

Check in order:

1. Format supported? (Try MP3 first)
2. URL accessible? (Test in browser)
3. Network reachable from speaker?
4. Use media browser to test known-good content

**Q: I sent a play command but nothing happened - no error shown?**

⚠️ **This is a known device limitation.** WiiM/LinkPlay devices accept play commands silently even when playback fails. The device returns "success" to the integration, but the stream may fail to play due to:

- **Geo-restrictions** - Stream blocked in your region
- **Invalid URL** - Stream moved or no longer available
- **HTTPS issues** - Some HTTPS streams have certificate problems
- **Network issues** - Device can't reach the stream server
- **Format issues** - Unsupported codec or container

**How to troubleshoot:**

1. Check the device state - is it showing "playing"?
2. Try a known-working stream: `http://ice2.somafm.com/groovesalad-128-mp3`
3. Try HTTP instead of HTTPS (more reliable)
4. Check if the stream works in a browser
5. Enable debug logging to see device responses

**Note:** This is a firmware limitation, not an integration bug. The device simply doesn't report stream failures back to Home Assistant.

**Q: What streams are known to work reliably?**

These HTTP streams are tested and reliable:

```yaml
# SomaFM (Various genres)
http://ice2.somafm.com/groovesalad-128-mp3   # Ambient/Chill
http://ice2.somafm.com/secretagent-128-mp3   # Lounge
http://ice2.somafm.com/dronezone-128-mp3     # Ambient
http://ice2.somafm.com/indiepop-128-mp3      # Indie Pop

# BBC (UK)
http://stream.live.vc.bbcmedia.co.uk/bbc_radio_two

# NPR (US)
http://npr-ice.streamguys1.com/live.mp3
```

HTTP streams are generally more reliable than HTTPS on WiiM devices.

**Q: How do I play TuneIn/Radio stations?**

Get the direct stream URL (not the web player page):

```yaml
# Good - Direct stream
media_content_id: "http://stream.radio.com/station.mp3"

# Bad - Web player page
media_content_id: "http://tunein.com/station"
```

Use [Radio Browser](https://www.radio-browser.info) to find stream URLs.

**Q: Why does the stop button behave differently with Bluetooth?**

**Bluetooth sources** have limited playback control compared to network sources:

- **Network sources** (WiFi, AirPlay, streaming): Support both pause and stop
- **Bluetooth sources**: Only support pause (not stop)

The integration automatically handles this by using pause instead of stop when Bluetooth is the active source. This is a device limitation, not an integration issue.

**Q: How do I completely stop Bluetooth playback?**

If pause/stop commands don't reliably stop Bluetooth playback, you can stop it by switching to another input source:

```yaml
# Switch to WiFi (or another available source) to disconnect Bluetooth
service: media_player.select_source
target:
  entity_id: media_player.your_device
data:
  source: "WiFi"  # or "Line In", "Optical", etc. - any available source
```

Switching sources will disconnect Bluetooth and stop playback. You can create an automation or script to do this automatically when you want to stop Bluetooth playback.

### Control Questions

**Q: Why do some buttons not work?**

Not all speakers support all features:

- **EQ**: Pro/Pro Plus/Ultra only
- **Presets**: Check available slots in WiiM app
- **Sources**: Varies by model
- **Alarms/Sleep Timer**: WiiM devices only

**Q: How do I use the equalizer?**

```yaml
# Select preset
service: media_player.select_sound_mode
target:
  entity_id: media_player.living_room
data:
  sound_mode: "Rock"

# Custom EQ (10 bands: 31.5Hz to 16kHz)
service: wiim.set_eq
target:
  entity_id: media_player.living_room
data:
  preset: "custom"
  custom_values: [0, +2, +4, +2, 0, 0, -2, 0, +2, +4]
```

### Alarm & Timer Questions

**Q: How do I set an alarm?**

WiiM devices support 3 alarm slots (0-2). Times must be in **UTC**:

```yaml
service: wiim.update_alarm
target:
  entity_id: media_player.bedroom
data:
  alarm_id: 0
  time: "07:00:00" # UTC time
  trigger: "daily"
  operation: "playback"
```

Remember to convert your local time to UTC!

**Q: How do I set a sleep timer?**

```yaml
service: wiim.set_sleep_timer
target:
  entity_id: media_player.living_room
data:
  sleep_time: 1800 # 30 minutes in seconds (0-7200)
```

**Q: My alarm didn't go off at the right time!**

Alarm times are in **UTC**, not your local time. Convert your local time to UTC when setting alarms. For example:

- 7:00 AM EST (UTC-5) = 12:00:00 UTC
- 7:00 AM PDT (UTC-7) = 14:00:00 UTC

---

## 🔧 Troubleshooting

### Connection Issues

**Problem: Can't connect to speaker**

**Solutions:**

1. Check network connectivity - HA and speaker on same network?
2. Verify device IP - hasn't changed? (use DHCP reservations)
3. Check firewall - UDP port 1900 allowed?
4. Power cycle device - try restarting speaker
5. Test direct access - can you access speaker via WiiM app?

**Problem: Speakers not discovered automatically**

**Solutions:**

- SSDP/UPnP discovery may find non-WiiM devices (this is normal)
- The pywiim library validates devices before connecting
- If auto-discovery fails, use manual IP configuration
- Check multicast is enabled on your network

**Problem: Speaker keeps disconnecting**

**Solutions:**

1. Assign static IP via DHCP reservation
2. Improve WiFi signal strength
3. Check for IP conflicts on network
4. Update speaker firmware
5. Disable any aggressive power-saving on router

### Multiroom Issues

**Problem: Groups not forming**

**Solutions:**

1. Ensure all speakers on same firmware version
2. Check speakers are on same network/subnet
3. Verify multicast traffic is allowed
4. Try creating group in WiiM app first
5. Check router multicast/IGMP settings

**Problem: Group coordinator not appearing**

**Reasons:**

- Group coordinator only appears when master **has slaves**
- Solo speakers and slave speakers don't show group coordinator
- Check role sensor: must show "Master" with slaves present

**Problem: Group audio out of sync**

**Solutions:**

1. Use wired connection for master speaker
2. Reduce WiFi interference
3. Update all speakers to same firmware
4. Reduce distance between speakers
5. Check network bandwidth

### Music Assistant Integration

**Problem: Only one player shows in Music Assistant**

**Solution:**

- Check that you selected **individual speaker entities**, not group coordinators
- Group coordinators have names ending with "Group" or "group coordinator"
- Individual speakers have clean names like "Living Room" or "Kitchen"
- Look for the `music_assistant_excluded: true` attribute (group coordinators have this)

**Problem: Music Assistant can't control my speakers**

**Solution:**

1. In Music Assistant, select **Home Assistant Player Provider**
2. Choose only **individual speaker entities** (not group coordinators)
3. Let Music Assistant handle its own grouping
4. Individual speaker entities work seamlessly with Music Assistant

### Debug Logging

Enable debug logging to diagnose issues:

```yaml
logger:
  default: info
  logs:
    custom_components.wiim: debug
    pywiim: debug # For pywiim library debugging
```

View logs: Settings → System → Logs

### Error Messages

| Error                                     | Meaning                     | Solution                         |
| ----------------------------------------- | --------------------------- | -------------------------------- |
| `Connection timeout`                      | Can't reach device          | Check network, verify IP         |
| `Invalid response`                        | Firmware issue              | Update speaker firmware          |
| `Unknown command`                         | Not supported               | Check device model capabilities  |
| `Slave speaker cannot play independently` | TTS to slave without master | Target master or use force_local |

### Performance Issues

**Problem: Slow response from speakers**

**Solutions:**

1. Check WiFi signal strength
2. Verify network isn't congested
3. Reduce polling frequency (integration auto-adjusts)
4. Check Home Assistant system resources
5. Update speaker firmware

**Problem: Entities not updating**

**Solutions:**

1. Check speaker is online in WiiM app
2. Verify network connectivity
3. Enable debug logging to see polling
4. Restart integration
5. Check for Home Assistant updates

### Getting Help

If you're still experiencing issues:

1. **Enable debug logging** (see above)
2. **Download diagnostics**
   - Device: Settings → Devices & Services → WiiM → Device → ⋮ → Download Diagnostics
3. **Check existing issues** on [GitHub](https://github.com/mjcumming/wiim/issues)
4. **Create new issue** with:
   - Device model and firmware version
   - Home Assistant version
   - Debug logs (including pywiim logs)
   - Diagnostic download
   - Steps to reproduce the problem

### Real-time Monitoring with monitor_cli

For real-time device monitoring, install pywiim on your computer:

**Windows:**

```cmd
pip install pywiim
python -m pywiim.cli.monitor_cli YOUR_DEVICE_IP
```

**Mac/Linux:**

```bash
pip3 install pywiim
python3 -m pywiim.cli.monitor_cli YOUR_DEVICE_IP
```

This shows real-time device state including audio output mode, playback state, and multiroom status. Press Ctrl+C to stop.

**Options:**

- `--verbose` - Enable verbose logging
- `--no-tui` - Use scrolling log instead of fixed display

### Technical Notes

**Integration Architecture**

This integration is a **wrapper around the pywiim library**:

- All device communication handled by pywiim
- Protocol detection, connection management, and error handling managed by library
- Integration focuses on Home Assistant-specific concerns (entities, coordinators, config flow)

**Library Version**

The integration requires `pywiim>=1.0.22`. If you encounter issues:

- Check that pywiim is up to date
- Review pywiim documentation for library-specific troubleshooting
- Report library issues to the pywiim project if appropriate

---

## 💡 Pro Tips

1. **Use Role Sensors** - Check `sensor.{device}_multiroom_role` before sending commands
2. **DHCP Reservations** - Assign static IPs to prevent connection issues
3. **Group Coordinators** - Use `*_group_coordinator` entities for group operations
4. **Network Monitoring** - Enable connectivity sensor for better diagnostics
5. **Keep Firmware Updated** - Check WiiM app regularly for updates

---

## 📚 Related Documentation

- **[Quick Start Guide](README.md)** - Installation and first steps
- **[User Guide](user-guide.md)** - Complete feature reference
- **[Automation Cookbook](automation-cookbook.md)** - Ready-to-use examples
- **[TTS Guide](TTS_GUIDE.md)** - Text-to-speech setup

---

**Still need help?** Visit [GitHub Discussions](https://github.com/mjcumming/wiim/discussions) or the [Home Assistant Community](https://community.home-assistant.io/).
