# WiiM Integration Troubleshooting Guide

## Connection Issues

### Common Error Messages

#### 1. "Connection lost to [IP], will retry with protocol probe"

**Cause**: The integration is trying to connect to devices that may not be WiiM/LinkPlay devices or are offline.

**Solution**:

- This is normal behavior during discovery
- The integration will automatically retry with different protocols
- If persistent, check if the IP addresses are actually WiiM devices

#### 2. "get_player_status failed: Request to [IP] failed: 404"

**Cause**: Some devices don't support the `getPlayerStatusEx` API call (older firmware or non-WiiM devices).

**Solution**:

- This is expected for non-WiiM devices discovered via SSDP
- The integration will automatically skip these devices
- No action required - this is handled gracefully

#### 3. "SSDP DISCOVERY validation failed for host: [IP]"

**Cause**: SSDP discovery found devices that aren't WiiM/LinkPlay compatible.

**Solution**:

- This is normal - SSDP discovers many UPnP devices on your network
- The integration validates each device and only connects to compatible ones
- No action required

### Debug Logging

To see detailed connection information, enable debug logging:

```yaml
logger:
  default: info
  logs:
    custom_components.wiim: debug
    custom_components.wiim.api_base: debug
    custom_components.wiim.config_flow: debug
```

### Expected Behavior

The integration will:

1. **Discover devices** via SSDP/Zeroconf
2. **Validate each device** to ensure it's WiiM/LinkPlay compatible
3. **Skip incompatible devices** with debug-level logging
4. **Connect only to valid devices** and create entities

### Device Compatibility

The integration supports:

- **WiiM devices**: Mini, Pro, Pro Plus, Amp, Ultra
- **Arylic devices**: Up2Stream Amp 2.0, 2.1, S10+
- **Other LinkPlay devices**: Audio Pro, DOSS, Dayton Audio, etc.

## LED Control Issues

### Arylic Device LED Commands

Arylic devices use different LED commands than standard WiiM devices:

**Experimental Commands** (based on user research):

- LED On/Off: `MCU+PAS+RAKOIT:LED:1` / `MCU+PAS+RAKOIT:LED:0`
- Brightness: `MCU+PAS+RAKOIT:LEDBRIGHTNESS:50` (0-100%)

**Fallback**: If Arylic commands fail, the integration will try standard WiiM commands.

**Note**: These commands are experimental. If they don't work, please report the issue with your specific Arylic model.

### Standard WiiM LED Commands

Standard WiiM devices use:

- LED On/Off: `setLED:1` / `setLED:0`
- Brightness: `setLEDBrightness:50` (0-100%)

## Music Assistant Integration

### Entity Types

The integration creates two types of entities per speaker:

1. **Individual Speaker** (`media_player.speaker_name`)

   - Controls individual speaker
   - Compatible with Music Assistant
   - Use these for Music Assistant integration

2. **Group Coordinator** (`media_player.speaker_name_group_coordinator`)
   - Controls multiroom groups
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
   - Debug logs
   - Steps to reproduce the problem

## Device-Specific Notes

### Arylic Devices

- LED commands are experimental
- Some models may not support all features
- Report specific model issues on GitHub

### Legacy Devices

- Older firmware may not support all API calls
- Some features may be limited
- Consider firmware updates if available
