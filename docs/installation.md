# Installation Guide

This guide walks you through installing the WiiM Audio integration for Home Assistant.

## Prerequisites

### System Requirements

- **Home Assistant**: Version 2024.12.0 or newer
- **Network**: Home Assistant and WiiM speakers on same network/VLAN
- **Ports**: UPnP/SSDP traffic allowed (ports 1900, 8080-8090)

### Supported Devices

- All WiiM products (Mini, Pro, Pro Plus, Amp)
- LinkPlay-compatible speakers (Arylic, Audio Pro, Dayton Audio, etc.)
- Any device supporting the LinkPlay HTTP API

---

## Method 1: HACS Installation (Recommended)

### Step 1: Install HACS

If you don't have HACS installed:

1. Follow the [HACS installation guide](https://hacs.xyz/docs/setup/prerequisites)
2. Restart Home Assistant after HACS installation

### Step 2: Add WiiM Integration

1. **Open HACS**

   - Go to **Settings** → **Add-ons, Backups & Supervisor** → **HACS**

2. **Find Integration**

   - Click **Integrations** tab
   - Click **Explore & Download Repositories**
   - Search for **"WiiM Audio"** or **"LinkPlay"**

3. **Install**

   - Click on **WiiM Audio (LinkPlay)**
   - Click **Download**
   - Select latest version
   - Wait for download completion

4. **Restart Home Assistant**
   - **Settings** → **System** → **Restart**

### Step 3: Configure Integration

1. **Add Integration**

   - **Settings** → **Devices & Services**
   - Click **Add Integration**
   - Search **"WiiM"**

2. **Setup Options**
   - **Auto-Discovery**: Select discovered speakers
   - **Manual Entry**: Enter IP addresses if auto-discovery fails

---

## Method 2: Manual Installation

### Step 1: Download Files

1. **Get Latest Release**

   - Visit [GitHub Releases](https://github.com/mjcumming/wiim/releases)
   - Download latest `wiim.zip` file

2. **Extract Files**
   - Unzip the downloaded file
   - You should see `custom_components/wiim/` folder

### Step 2: Copy to Home Assistant

1. **Locate Config Directory**

   - Find your Home Assistant configuration directory
   - Usually `/config/` in Docker, `~/.homeassistant/` for pip installation

2. **Copy Integration**

   ```bash
   # Create custom_components if it doesn't exist
   mkdir -p /config/custom_components/

   # Copy wiim integration
   cp -r custom_components/wiim/ /config/custom_components/
   ```

3. **Verify Structure**
   ```
   /config/
   ├── custom_components/
   │   └── wiim/
   │       ├── __init__.py
   │       ├── manifest.json
   │       ├── config_flow.py
   │       ├── media_player.py
   │       └── ... (other files)
   └── configuration.yaml
   ```

### Step 3: Restart and Configure

1. **Restart Home Assistant**

   - **Settings** → **System** → **Restart**

2. **Add Integration**
   - **Settings** → **Devices & Services**
   - Click **Add Integration**
   - Search **"WiiM Audio"**

---

## Setup Wizard

### Auto-Discovery

The integration automatically discovers WiiM/LinkPlay speakers on your network.

1. **Select Devices**

   - Choose speakers from discovered list
   - Each speaker becomes a separate integration entry

2. **Device Names**
   - Uses speaker's configured name from WiiM app
   - Can be changed later in Home Assistant

### Manual Configuration

If auto-discovery doesn't work:

1. **Enter IP Address**

   - Find speaker IP in your router's DHCP table
   - Or use WiiM app → Settings → About

2. **Validation**
   - Integration tests connection to each speaker
   - Shows error if unreachable

### Device Options

Configure each speaker individually:

| Setting              | Purpose                  | Default   | Notes                        |
| -------------------- | ------------------------ | --------- | ---------------------------- |
| **Polling Interval** | Status update frequency  | 5 seconds | Lower = more responsive      |
| **Volume Step**      | Volume button increment  | 5%        | Matches your preference      |
| **Group Entity**     | Virtual group controller | Off       | Enable for multiroom masters |

---

## Post-Installation

### Verify Installation

1. **Check Entities**

   - **Settings** → **Devices & Services** → **WiiM Audio**
   - Each speaker should show with media_player entity

2. **Test Functionality**
   - Try volume control
   - Test play/pause
   - Check device attributes

### Configure Lovelace

Add media player cards to your dashboard:

```yaml
type: media-control
entity: media_player.living_room_speaker
```

### Enable Features

Optional features to configure:

- **Group Entities**: For multiroom control
- **Debug Logging**: For troubleshooting
- **Automation**: Using WiiM speakers in automations

---

## Troubleshooting Installation

### Common Issues

#### Integration Not Found

**Problem**: Can't find "WiiM Audio" in Add Integration
**Solutions**:

- Clear browser cache and refresh
- Restart Home Assistant after manual installation
- Check that files are in correct location

#### Download Failed (HACS)

**Problem**: HACS shows download error
**Solutions**:

- Check internet connection
- Try again after a few minutes
- Use manual installation as fallback

#### No Devices Discovered

**Problem**: Auto-discovery finds no speakers
**Solutions**:

- Check network connectivity (ping speaker IP)
- Ensure speakers and HA on same network/VLAN
- Try manual configuration with IP addresses
- Check firewall settings for UPnP/SSDP

#### Connection Errors

**Problem**: "Cannot connect to device" during setup
**Solutions**:

- Verify speaker IP address is correct
- Check speaker is powered on and connected to network
- Try different network ports (443, 80)
- Temporarily disable firewall to test

#### SSL Certificate Errors

**Problem**: SSL/TLS connection issues
**Solutions**:

- Integration automatically handles self-signed certificates
- No user action needed - uses built-in fallback
- Enable debug logging if issues persist

### Debug Information

Enable detailed logging for troubleshooting:

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.wiim: debug
    custom_components.wiim.api: debug
    custom_components.wiim.coordinator: debug
```

### Getting Help

If installation issues persist:

1. **Check Logs**

   - **Settings** → **System** → **Logs**
   - Look for errors containing "wiim"

2. **Community Support**

   - [Home Assistant Community Forum](https://community.home-assistant.io/)
   - [GitHub Issues](https://github.com/mjcumming/wiim/issues)

3. **Bug Reports**
   - Include Home Assistant version
   - Include integration version
   - Include relevant log entries
   - Describe network setup

---

## Next Steps

After successful installation:

- [Configuration Guide](configuration.md) - Customize integration settings
- [Multiroom Setup](multiroom.md) - Configure speaker groups
- [Troubleshooting](troubleshooting.md) - Resolve common issues
- [Features Guide](features.md) - Explore all capabilities
