# WiiM Integration Troubleshooting Guide

## Connection Issues

### Common Error Messages

The integration uses the `pywiim` library for all device communication. Most connection issues are handled automatically by the library.

#### Connection Errors

**If you see connection errors:**

1. **Check network connectivity** - Ensure Home Assistant and your WiiM device are on the same network
2. **Verify device IP** - Check that the device's IP address hasn't changed (use DHCP reservations)
3. **Check firewall** - Ensure UDP port 1900 (UPnP/SSDP) is allowed for discovery
4. **Power cycle device** - Try restarting the WiiM device

#### Discovery Issues

**If devices aren't discovered automatically:**

- SSDP/UPnP discovery may find non-WiiM devices - this is normal
- The `pywiim` library validates devices and only connects to compatible ones
- If auto-discovery fails, use manual IP configuration

### Debug Logging

To see detailed connection information, enable debug logging:

```yaml
logger:
  default: info
  logs:
    custom_components.wiim: debug
    custom_components.wiim.config_flow: debug
    pywiim: debug # For debugging pywiim library interactions
```

### Manual Configuration

If auto-discovery doesn't work:

1. Find your device's IP address (router admin panel, WiiM app, or network scanner)
2. Go to **Settings → Devices & Services → Add Integration → WiiM Audio**
3. Select **"Enter IP manually"** when prompted
4. Enter the device's IP address

### Device Compatibility

The integration supports all WiiM and LinkPlay-compatible devices:

- **WiiM devices**: Mini, Pro, Pro Plus, Amp, Ultra
- **Arylic devices**: Up2Stream Amp 2.0, 2.1, S10+
- **Other LinkPlay devices**: DOSS, Dayton Audio, iEast, and many more

Device communication and protocol handling are managed by the `pywiim` library, which supports multiple protocols and automatically handles compatibility.

## Music Assistant Integration

### Entity Types

The integration creates two types of entities per speaker:

1. **Individual Speaker** (`media_player.speaker_name`)

   - Controls individual speaker
   - Compatible with Music Assistant
   - Use these for Music Assistant integration

2. **Group Coordinator** (`media_player.speaker_name_group_coordinator`)
   - Controls multiroom groups
   - **Dynamic naming**: Changes based on speaker role
     - Solo: `"Speaker Name"` (e.g., "Living Room")
     - Group Master: `"Speaker Name Group Master"` (e.g., "Living Room Group Master")
   - For Home Assistant multiroom control only
   - **Do not use with Music Assistant**

### Music Assistant Configuration

1. In Music Assistant, select **Home Assistant Player Provider**
2. Choose only the **individual speaker entities** (not group coordinators)
3. Group coordinators are marked with `music_assistant_excluded: true` attribute

### Troubleshooting Music Assistant

**Problem**: Only one player shows in Music Assistant

**Solution**:

- Check that you selected individual speakers, not group coordinators
- Group coordinators have names ending with "Group" or "group coordinator"
- Individual speakers have clean names like "Living Room" or "Kitchen"

## Getting Help

If you're still experiencing issues:

1. **Enable debug logging** (see above)
2. **Check the logs** for specific error messages
3. **Report issues** on GitHub with:
   - Device model and firmware version
   - Debug logs (including `pywiim` logs)
   - Steps to reproduce the problem

## Technical Notes

### Integration Architecture

This integration is a **wrapper around the `pywiim` library**:

- All device communication is handled by `pywiim`
- Protocol detection, connection management, and error handling are managed by the library
- The integration focuses on Home Assistant-specific concerns (entities, coordinators, config flow)

### Library Version

The integration requires `pywiim>=1.0.22`. If you encounter issues:

- Check that `pywiim` is up to date
- Review `pywiim` documentation for library-specific troubleshooting
- Report library issues to the `pywiim` project if appropriate
