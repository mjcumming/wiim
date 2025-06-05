# WiiM Integration - Troubleshooting

Quick solutions for common issues with the WiiM Audio integration.

## 🚨 Common Issues & Quick Fixes

### HACS Download Issues

**Error**: "Got status code 404" when downloading from HACS

**Solutions**:

1. **Force Latest Version**: HACS → Integrations → WiiM Audio → ⋮ → **Redownload** → Select latest version
2. **Clear HACS Cache**: Restart Home Assistant, then try HACS install again
3. **Manual Installation**: Download from [GitHub Releases](https://github.com/mjcumming/wiim/releases/latest), extract to `/config/custom_components/wiim/`

### Integration Not Found

**Problem**: Can't find "WiiM Audio" when adding integration

**Solutions**:

- Clear browser cache (Ctrl+F5) and refresh
- Restart Home Assistant: **Settings** → **System** → **Restart**
- Verify files are in `/config/custom_components/wiim/`
- Check integration loaded: **Settings** → **System** → **Logs** (look for "wiim" entries)

### No Devices Discovered

**Problem**: Auto-discovery finds no speakers

**Quick Checks**:

- Ensure Home Assistant and speakers on same network/VLAN
- Check firewall allows UPnP/SSDP traffic (port 1900)
- Verify speakers have network connectivity (can you ping them?)

**Solutions**:

1. **Use Manual Setup**: Settings → Add Integration → Enter speaker IP directly
2. **Find Speaker IPs**: Check router DHCP table or use WiiM app → Settings → About
3. **Network Test**: `ping 192.168.1.100` (replace with speaker IP)

### Speakers Show as Unavailable

**Problem**: Devices discovered but show unavailable

**Common Causes & Fixes**:

- **IP Changed**: Speaker got new DHCP address → Use DHCP reservations
- **Network Issues**: Check switch/router → Power cycle network equipment
- **SSL Problems**: Integration handles certificates automatically → No action needed

**Quick Fix**: Remove and re-add device with current IP address

## 🔧 Multiroom Issues

### Groups Not Working

**Problem**: Speakers won't group or keep disconnecting

**Essential Checks**:

```yaml
# Check role sensors to understand group state
sensor.living_room_multiroom_role: "Master"
sensor.kitchen_multiroom_role: "Slave"
sensor.bedroom_multiroom_role: "Solo"
```

**Solutions**:

1. **Firmware**: Update all speakers to same firmware version
2. **Network**: Ensure multicast traffic allowed between devices
3. **IP Stability**: Use DHCP reservations for all speakers
4. **Signal**: Improve WiFi signal strength/quality

### Group Volume Jumps

**Problem**: Volume changes unexpectedly in groups

**Understanding**: Group volume = maximum member volume, changes apply relatively

**Example**:

```yaml
# Before: Master 80%, Slave 40% → Group shows 80%
# Set group to 50% → Master 50%, Slave 25% (scaled proportionally)
```

**Solution**: Use individual speaker controls for fine-tuning

### Role Sensor Issues

**Problem**: Speakers show wrong roles or "unknown"

**Debug Steps**:

```yaml
# Check entity states
Developer Tools → States → Search "multiroom_role"

# Force refresh
service: homeassistant.reload_config_entry
target:
  entity_id: media_player.speaker_name
```

## 🌐 Network Troubleshooting

### Connection Errors

**Quick Network Tests**:

```bash
# Test basic connectivity
ping 192.168.1.100

# Test HTTP port
curl -k "https://192.168.1.100/httpapi.asp?command=getStatusEx"

# Check UPnP/SSDP traffic
# Ensure port 1900 is open and multicast allowed
```

**Common Fixes**:

- **Firewall**: Temporarily disable to test
- **VLANs**: Ensure HA and speakers on same VLAN
- **WiFi**: Move closer to access point or add WiFi extender

### SSL Certificate Errors

**Problem**: SSL/TLS connection failures

**Good News**: Integration automatically handles WiiM's self-signed certificates

**If Issues Persist**:

- Integration falls back to HTTP automatically
- Check logs for specific SSL errors
- Verify speaker firmware is updated

## 📱 Control Issues

### Media Controls Not Working

**Basic Checks**:

1. **Speaker State**: Is device powered on and responsive?
2. **Network**: Can you control via WiiM app?
3. **Integration**: Check for errors in HA logs

**Test Commands**:

```yaml
# Test basic controls in Developer Tools → Services
service: media_player.volume_set
target:
  entity_id: media_player.living_room
data:
  volume_level: 0.5
```

### Audio But No Control

**Problem**: Music plays but HA controls don't work

**Solutions**:

1. **WiiM App Test**: If WiiM app works, issue is integration
2. **API Test**: Try manual API call (see above)
3. **Restart Integration**: Settings → Integrations → WiiM → Restart

### EQ/Source Issues

**Problem**: Equalizer or source selection not working

**Check Support**:

```yaml
# View available options in entity attributes
Developer Tools → States → media_player.speaker_name
# Look for: sound_mode_list, source_list
```

**Note**: Not all speakers support all features

## 🐛 Debug Information

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.wiim: debug
    custom_components.wiim.api: debug
    custom_components.wiim.coordinator: debug
```

### View Logs

- **UI**: Settings → System → Logs
- **File**: `/config/home-assistant.log`
- **Docker**: `docker logs homeassistant`

### Key Log Patterns

Look for these in logs:

```
ERROR custom_components.wiim.api: Connection failed
WARNING custom_components.wiim.coordinator: Device offline
INFO custom_components.wiim: Group state changed
```

## 🔄 Reset & Recovery

### Integration Reset

1. **Remove Integration**: Settings → Integrations → WiiM → Delete
2. **Clear Cache**: Restart Home Assistant
3. **Reinstall**: Add integration fresh
4. **Reconfigure**: Set up devices again

### Network Reset

1. **Power Cycle**: Restart speakers, router, HA
2. **WiFi Reset**: Reconnect speakers to WiFi
3. **IP Reset**: Clear DHCP leases, assign new IPs
4. **Test**: Verify basic connectivity before HA setup

### Factory Reset Speaker

**Last Resort**: If speaker completely unresponsive

1. Use WiiM app or hardware reset procedure
2. Reconfigure speaker network settings
3. Re-add to Home Assistant

## 📞 Getting Help

### Before Reporting Issues

1. **Enable Debug Logging** (see above)
2. **Reproduce Issue** with logging enabled
3. **Check Network**: Test basic connectivity
4. **Try WiiM App**: Verify issue isn't speaker-related

### Information to Include

- Home Assistant version
- Integration version
- Speaker model(s)
- Network setup details
- Relevant log entries
- Steps to reproduce

### Community Resources

- **GitHub Issues**: [Report bugs](https://github.com/mjcumming/wiim/issues)
- **HA Community**: [Get help](https://community.home-assistant.io/)
- **Discussions**: [Feature requests](https://github.com/mjcumming/wiim/discussions)

## 🎯 Prevention Tips

### Network Best Practices

- Use DHCP reservations for stable IPs
- Ensure strong WiFi coverage for all speakers
- Keep HA and speakers on same subnet
- Allow multicast/UPnP traffic

### Integration Maintenance

- Update integration regularly via HACS
- Monitor logs for warnings
- Test multiroom after HA updates
- Keep speaker firmware current

### Quick Health Check

```yaml
# Test basic functionality monthly
service: media_player.volume_set
target:
  entity_id: media_player.living_room
data:
  volume_level: 0.3

# Check role sensors
Developer Tools → States → Search "multiroom_role"

# Verify network connectivity
ping [speaker_ip]
```

Most issues resolve with network improvements or integration restart. For complex problems, enable debug logging and check the logs for specific error messages.
