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
- **Audio Pro devices**: Including newer MkII models (A10 MkII, A15 MkII, A28, C10 MkII)
- **Other LinkPlay devices**: DOSS, Dayton Audio, iEast, and many more

### Enhanced Device Compatibility

The integration includes enhanced validation with automatic protocol fallback:

- **Multi-Protocol Support**: Automatically tries HTTPS (443, 4443) and HTTP (80, 8080)
- **Graceful Fallback**: Devices that can't be auto-configured are still offered for manual setup
- **Legacy Device Support**: Special handling for older LinkPlay-based devices

If a device is discovered but shows "Validation failed" in the logs, it may still work with manual IP configuration.

## Discovery and Validation Issues

### Understanding Validation Failures

The integration tries multiple protocols and ports when validating devices:

1. **HTTPS on port 443** (standard)
2. **HTTPS on port 4443** (alternative)
3. **HTTP on port 80** (standard)
4. **HTTP on port 8080** (alternative)

**Common validation failure reasons:**

- **SSL Certificate Issues**: Some devices don't have proper SSL certificates
- **Port Differences**: Devices may use non-standard ports
- **Protocol Restrictions**: Some devices only support HTTP, not HTTPS
- **Slow Response**: Older devices may be slow to respond to API calls

### Manual Configuration Workaround

If auto-discovery fails, you can still manually configure the device:

1. Note the IP address from the discovery logs
2. Use **Settings → Devices & Services → Add Integration → WiiM Audio**
3. Select **"Enter IP manually"** when prompted
4. Enter the device's IP address

The device should work normally after manual configuration, even if auto-validation failed.

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

### Audio Pro Devices

Audio Pro devices span multiple generations with different API implementations:

#### **Generation Overview**

| Generation   | Models                            | Protocol    | Integration Support |
| ------------ | --------------------------------- | ----------- | ------------------- |
| **Original** | C3, C5, Drumfire                  | HTTP (80)   | ✅ Full support     |
| **MkII**     | A10 MkII, A15 MkII, A28, C10 MkII | HTTPS (443) | ✅ Full support     |
| **W-Series** | A15 W, A28 W, A38 W, A48 W        | HTTPS (443) | ✅ Full support     |

#### **Common Issues & Solutions**

**Problem: "Validation failed" during discovery**

- **Cause**: MkII/W-Series devices use HTTPS instead of HTTP
- **Solution**: Use manual IP configuration (works perfectly)
- **Status**: This is expected behavior, not a bug

**Problem: Device shows as "unavailable" after setup**

- **Cause**: Firmware differences in status reporting
- **Solution**: Check network connectivity and try restarting the device
- **Workaround**: Manual setup often resolves availability issues

**Problem: Metadata shows "Unknown Artist/Title"**

- **Cause**: Audio Pro devices may not provide rich metadata via HTTP API
- **Solution**: This is normal for streaming content - use display names instead
- **Alternative**: Enable debug logging to see raw API responses

#### **Multiroom Behavior**

Audio Pro devices integrate seamlessly with WiiM devices in multiroom groups:

- **Master/Slave roles** work identically to WiiM devices
- **Group volume control** functions normally
- **Source synchronization** works across generations
- **EQ controls** available on supported models (Pro series)

#### **Best Practices**

1. **Use manual setup** if auto-discovery shows validation warnings
2. **Enable debug logging** when troubleshooting API issues
3. **Check firmware version** - newer firmware often improves compatibility
4. **Test with simple operations** (play/pause/volume) before complex automations

**Note**: All Audio Pro devices work fully with the integration once properly configured. The "validation failed" messages during discovery are cosmetic and don't affect functionality.
