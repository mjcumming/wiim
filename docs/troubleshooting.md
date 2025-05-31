# Troubleshooting Guide

This guide helps resolve common issues with the WiiM Audio integration.

## HACS Download Issues

### Problem: "Got status code 404" Download Error

**Error Message**:

```
Download failed - Got status code 404 when trying to download
https://github.com/mjcumming/wiim/releases/download/v0.3.0/wiim.zip
```

**Root Cause**: HACS is trying to download an older version (v0.3.0) that doesn't have a proper ZIP file attached.

**Solutions**:

1. **Force Latest Version**:

   - HACS → Integrations → WiiM Audio → ⋮ menu → **Redownload**
   - Select **v0.3.2** or latest version
   - Restart Home Assistant

2. **Clear HACS Cache**:

   - Settings → System → **Restart Home Assistant**
   - HACS → Integrations → Try install again

3. **Manual Installation** (if HACS fails):

   - Download latest `wiim.zip` from [GitHub Releases](https://github.com/mjcumming/wiim/releases/latest)
   - Extract to `/config/custom_components/wiim/`
   - Restart Home Assistant

4. **Complete Reinstall**:
   - Remove integration from HACS and Home Assistant
   - Fresh install from HACS with latest version

### Problem: "Integration 'wiim' not found"

This error occurs when the integration isn't properly loaded:

**Solutions**:

- Verify files are in `/config/custom_components/wiim/`
- Check manifest.json is valid
- Restart Home Assistant after installation
- Clear browser cache (Ctrl+F5)

---

## Quick Diagnostics

### Check Integration Status

1. **Settings** → **Devices & Services** → **WiiM Audio**
2. Look for error messages or unavailable devices
3. Check entity states in **Developer Tools** → **States**

### Basic Network Test

```bash
# Test connectivity to your speakers
ping 192.168.1.100  # Replace with your speaker IP
telnet 192.168.1.100 8080  # Test HTTP port
```

### Enable Debug Logging

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.wiim: debug
    custom_components.wiim.api: debug
    custom_components.wiim.coordinator: debug
    custom_components.wiim.config_flow: debug
```

---

## Installation Issues

### Integration Not Found

**Problem**: Can't find "WiiM Audio" when adding integration

**Solutions**:

- **Clear Cache**: Hard refresh browser (Ctrl+F5)
- **Restart HA**: **Settings** → **System** → **Restart**
- **Check Files**: Verify integration files in `/config/custom_components/wiim/`
- **HACS**: Ensure HACS installation completed successfully

**Verify Installation**:

```bash
# Check file structure
ls -la /config/custom_components/wiim/
# Should show: __init__.py, manifest.json, etc.
```

### HACS Download Failed

**Problem**: HACS shows "Download failed" error

**Solutions**:

- **Network**: Check internet connectivity
- **Retry**: Wait 5-10 minutes and try again
- **GitHub**: Check if GitHub is accessible
- **Manual**: Use manual installation as fallback

**HACS Troubleshooting**:

1. **HACS Logs**: Check HACS section in HA logs
2. **Rate Limits**: GitHub API rate limiting (wait 1 hour)
3. **Repository**: Verify repository URL is correct

### Files in Wrong Location

**Problem**: Integration installed but not recognized

**Correct Structure**:

```
/config/
├── custom_components/
│   └── wiim/
│       ├── __init__.py
│       ├── manifest.json
│       ├── config_flow.py
│       ├── media_player.py
│       ├── api.py
│       ├── coordinator.py
│       └── ...
└── configuration.yaml
```

**Common Mistakes**:

- Files in `/config/wiim/` instead of `/config/custom_components/wiim/`
- Missing `custom_components` directory
- Extra folder level: `/config/custom_components/wiim/wiim/`

---

## Discovery Issues

### No Devices Found

**Problem**: Auto-discovery finds no speakers

**Network Troubleshooting**:

1. **Same Subnet**: Ensure HA and speakers on same network
2. **VLAN**: Check VLAN configuration allows multicast
3. **Firewall**: Allow UPnP/SSDP traffic (port 1900)
4. **WiFi**: Verify speakers connected to correct WiFi network

**Manual Discovery**:

```yaml
# Find speaker IPs
nmap -sn 192.168.1.0/24 | grep -B2 -A1 "WiiM\|LinkPlay"

# Test speaker HTTP API
curl -k https://192.168.1.100/httpapi.asp?command=getStatusEx
```

**Solutions**:

- Use manual IP configuration instead of auto-discovery
- Check router DHCP table for speaker IPs
- Use WiiM app to find speaker network information
- Temporarily disable firewall to test

### Discovery Finds Wrong Devices

**Problem**: Integration detects non-WiiM devices

**Filtering**:

- Integration automatically filters for WiiM/LinkPlay devices
- False positives should be ignored during setup
- Only select actual WiiM speakers in setup wizard

### Speaker Shows as Unavailable

**Problem**: Device discovered but shows unavailable

**Network Issues**:

- **IP Changed**: Speaker got new IP from DHCP
- **Network**: Connectivity issues between HA and speaker
- **SSL**: Certificate problems (integration handles this)

**Solutions**:

1. **Reconfigure**: Remove and re-add device with current IP
2. **Static IP**: Set DHCP reservation for speaker
3. **Network**: Check switch/router configuration
4. **Power Cycle**: Restart speaker and HA

---

## Connection Problems

### Session Closed Errors

**Problem**: `RuntimeError: Session is closed` in logs

**Explanation**: HTTP session interrupted during HA restart or network issues

**Solutions**:

- **Automatic**: Integration automatically recovers
- **Manual**: Restart integration if persistent
- **Network**: Check network stability

**Prevention**:

- Use stable network connection
- Avoid frequent HA restarts during speaker use
- Consider wired connection for HA server

### SSL Certificate Issues

**Problem**: SSL/TLS connection errors

**Built-in Handling**:

- Integration includes WiiM certificate
- Automatically falls back to insecure mode
- No user action typically required

**Manual Solutions**:

```yaml
# Force debug logging for SSL issues
logger:
  logs:
    custom_components.wiim.api: debug
    aiohttp.client: debug
```

### Timeout Errors

**Problem**: Requests timing out frequently

**Causes**:

- **Network Congestion**: Too much traffic
- **Distance**: Speaker too far from WiFi access point
- **Interference**: WiFi interference on 2.4GHz

**Solutions**:

- **Polling Interval**: Increase to 10-15 seconds
- **Network**: Improve WiFi signal strength
- **Channel**: Change WiFi channel to less congested frequency
- **Access Point**: Add WiFi access point closer to speakers

---

## Multiroom Issues

### Group Entity Not Appearing

**Problem**: Group entity never shows up

**Checklist**:

- [x] Group entity enabled in device options
- [x] Device is actually master (has slaves)
- [x] Integration restarted after enabling
- [x] Entity not disabled in entity registry

**Debugging**:

```yaml
# Check device options
Settings → Devices & Services → WiiM Audio → Configure

# Check entity registry
Developer Tools → States → search "group"

# Check coordinator data
Developer Tools → States → media_player.your_speaker
# Look for group_role: "master"
```

### Volume Jumps Unexpectedly

**Problem**: Group volume changes dramatically

**Understanding Group Volume**:

- Group volume = maximum volume of all members
- Changes apply relatively to maintain balance
- Not absolute volume setting

**Example Issue**:

```yaml
# Before: Master 100%, Slave 20%
# Group shows: 100% (maximum)
# Set group to 50%
# After: Master 50%, Slave 10% (scaled proportionally)
```

**Solutions**:

- Use individual speaker controls for fine-tuning
- Understand relative volume behavior is by design
- Check group entity attributes for individual volumes

### Speakers Keep Leaving Groups

**Problem**: Groups unstable, speakers disconnect

**Network Causes**:

- **WiFi Issues**: Poor signal, interference
- **IP Changes**: DHCP reassigning addresses
- **Timing**: Network delays causing sync issues

**Solutions**:

1. **Static IPs**: Use DHCP reservations
2. **WiFi**: Improve signal strength/quality
3. **Firmware**: Update speaker firmware
4. **Network**: Check for packet loss

**Network Diagnostics**:

```bash
# Test stability
ping -c 100 192.168.1.100  # Check packet loss
mtr 192.168.1.100         # Network path analysis
```

### Master/Slave Role Confusion

**Problem**: Speakers show wrong roles

**Role Detection**:

- Integration polls `multiroom:getSlaveList` endpoint
- Role determined by presence in slave lists
- Updates within 5-10 seconds of changes

**Manual Reset**:

```yaml
# Force role refresh
service: homeassistant.reload_config_entry
target:
  entity_id: media_player.speaker_name
```

---

## Audio Issues

### No Sound from Speakers

**Problem**: Control works but no audio

**Basic Checks**:

- **Volume**: Check speaker volume levels
- **Mute**: Verify speakers not muted
- **Source**: Check selected audio source
- **Input**: Verify audio input/stream

**WiiM App Test**:

1. Use official WiiM app to test audio
2. If WiiM app works, issue is HA integration
3. If WiiM app fails, issue is speaker/network

### Audio Out of Sync

**Problem**: Multiroom speakers not synchronized

**LinkPlay Sync**:

- Sync handled by LinkPlay protocol
- Integration doesn't control sync timing
- Issues usually network-related

**Solutions**:

- **Network**: Improve WiFi quality
- **Interference**: Reduce 2.4GHz interference
- **Regroup**: Remove and re-add speakers to group
- **Firmware**: Update all speaker firmware

### EQ/Sound Settings Not Working

**Problem**: Equalizer controls have no effect

**EQ Support**:

- Not all speakers support EQ
- Check `sound_mode_list` attribute
- Some firmware versions have limited EQ

**Debugging**:

```yaml
# Check EQ support
Developer Tools → States → media_player.speaker
# Look for: sound_mode_list, eq_enabled attributes

# Test EQ manually
service: wiim.set_eq
target:
  entity_id: media_player.speaker
data:
  preset: "rock"
```

---

## Performance Issues

### High CPU Usage

**Problem**: Integration using excessive CPU

**Causes**:

- **Polling**: Too frequent status updates
- **Groups**: Many speakers in complex groups
- **Errors**: Repeated connection failures

**Solutions**:

1. **Increase Intervals**: Set polling to 10-15 seconds
2. **Simplify Groups**: Reduce group complexity
3. **Fix Networks**: Resolve connection issues

### Slow Response Times

**Problem**: Commands take long to execute

**Optimization**:

```yaml
# Device-specific settings
Settings → Devices → Configure

Polling Interval: 10 seconds    # Reduce load
Volume Step: 5%                 # Reasonable increment
Group Entity: Only if needed    # Reduce entities
```

### Memory Usage Growing

**Problem**: Integration memory usage increases over time

**Monitoring**:

```yaml
# Monitor integration performance
Developer Tools → Statistics
# Look for custom_components.wiim memory usage
```

**Solutions**:

- Restart Home Assistant monthly
- Check for memory leaks in logs
- Report persistent issues to GitHub

---

## Advanced Troubleshooting

### Raw API Testing

Test speaker APIs directly:

```bash
# Basic status
curl -k "https://192.168.1.100/httpapi.asp?command=getStatusEx"

# Multiroom info
curl -k "https://192.168.1.100/httpapi.asp?command=multiroom:getSlaveList"

# Set volume
curl -k "https://192.168.1.100/httpapi.asp?command=setPlayerCmd:vol:50"

# Play/pause
curl -k "https://192.168.1.100/httpapi.asp?command=setPlayerCmd:play"
curl -k "https://192.168.1.100/httpapi.asp?command=setPlayerCmd:pause"
```

### Integration State Inspection

```yaml
# Check coordinator data
Developer Tools → States →
# Search for: sensor.speaker_name_*

# Check internal state
Developer Tools → Template →
{{ state_attr('media_player.speaker_name', 'group_members') }}
{{ state_attr('media_player.speaker_name', 'group_role') }}
```

### Network Packet Capture

For complex network issues:

```bash
# Capture UPnP/SSDP traffic
sudo tcpdump -i any port 1900

# Capture HTTP API traffic
sudo tcpdump -i any host 192.168.1.100 and port 8080
```

---

## Getting Help

### Before Reporting Issues

1. **Enable Debug Logging** (see above)
2. **Reproduce Issue** with logging enabled
3. **Check Logs** for relevant error messages
4. **Test Basic Connectivity** (ping, curl)
5. **Try WiiM App** to isolate integration vs speaker issues

### Information to Include

When reporting issues, provide:

- **Home Assistant version**
- **Integration version**
- **Speaker model(s)**
- **Network setup** (WiFi, VLANs, etc.)
- **Relevant log entries**
- **Steps to reproduce**

### Community Resources

- **GitHub Issues**: [Report bugs/features](https://github.com/mjcumming/wiim/issues)
- **HA Community**: [Ask questions](https://community.home-assistant.io/)
- **Documentation**: [Integration guides](../README.md)

### Debug Data Collection

```yaml
# Full debug logging
logger:
  default: info
  logs:
    custom_components.wiim: debug
    homeassistant.components.media_player: debug
    homeassistant.helpers.entity_platform: debug
```

**Log Locations**:

- **UI**: Settings → System → Logs
- **File**: `/config/home-assistant.log`
- **Docker**: `docker logs homeassistant`

---

## Preventive Measures

### Network Best Practices

- Use DHCP reservations for speakers
- Ensure strong WiFi signal coverage
- Keep speakers on same subnet as HA
- Monitor network performance regularly

### Integration Maintenance

- Update integration regularly
- Monitor logs for warnings
- Test multiroom functionality monthly
- Keep speaker firmware updated

### Home Assistant Health

- Regular HA updates
- Monitor system resources
- Backup configuration regularly
- Use supervision monitoring if available
