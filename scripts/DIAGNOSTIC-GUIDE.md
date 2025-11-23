# Running Diagnostic Scripts in Home Assistant

If you have the WiiM integration installed in Home Assistant and want to run diagnostic scripts to troubleshoot issues, here's how:

## Quick Answer

**Yes, you can run pywiim's diagnostic tools!**

The `pywiim` library is already installed with the integration. You can download and run pywiim's `monitor_cli` script directly - it's a comprehensive diagnostic tool that shows all device state including audio output mode.

## Method 1: Using Home Assistant Terminal Add-on (Easiest)

1. **Install Terminal Add-on** (if not already installed):

   - Go to **Settings** → **Add-ons** → **Add-on Store**
   - Search for "Terminal & SSH" or "SSH & Web Terminal"
   - Install and start it

2. **Download and run pywiim's monitor_cli**:

   ```bash
   # Download the script from pywiim repository
   wget -q https://raw.githubusercontent.com/mjcumming/pywiim/main/scripts/monitor_cli.py -O /tmp/monitor_cli.py

   # Run it (pywiim library is already installed)
   python3 /tmp/monitor_cli.py <your_device_ip>

   # Example:
   python3 /tmp/monitor_cli.py 192.168.1.100
   ```

   This will show comprehensive device diagnostics including:

   - Audio output mode (`audio_output_mode`)
   - Available outputs (`available_outputs`)
   - Current playback state
   - Device capabilities
   - And much more!

## Method 2: Using SSH Access

If you have SSH access to your Home Assistant system:

1. **SSH into your Home Assistant system**

2. **Download and run pywiim's monitor_cli**:

   ```bash
   # Download the script
   wget -q https://raw.githubusercontent.com/mjcumming/pywiim/main/scripts/monitor_cli.py -O /tmp/monitor_cli.py

   # For Home Assistant OS/Supervised:
   python3 /tmp/monitor_cli.py <device_ip>

   # For Home Assistant Container:
   docker exec -it homeassistant python3 /tmp/monitor_cli.py <device_ip>
   ```

## Method 3: Run Locally on Your Computer

If you have Python installed on your computer:

1. **Install pywiim** (if not already installed):

   ```bash
   pip install pywiim>=2.1.10
   ```

2. **Download and run pywiim's monitor_cli**:

   ```bash
   # Download the script
   wget https://raw.githubusercontent.com/mjcumming/pywiim/main/scripts/monitor_cli.py -O monitor_cli.py

   # Run it
   python3 monitor_cli.py <device_ip>
   ```

## What monitor_cli Shows

The `monitor_cli` tool provides comprehensive diagnostics:

- ✅ Device connection status
- ✅ Current `audio_output_mode` value
- ✅ `available_outputs` list
- ✅ Playback state and metadata
- ✅ Device capabilities
- ✅ Network information
- ✅ Real-time updates (refreshes automatically)

**Key things to look for:**

- `audio_output_mode` - Should show current mode (e.g., "Line Out", "Optical Out")
- `available_outputs` - Should list all available output options
- If `audio_output_mode` is `None` or doesn't match any item in `available_outputs`, that's why Home Assistant shows "Unknown"

## Example Output

```
Device: WiiM Amp (192.168.1.100)
Status: Connected

Audio Output:
  Current Mode: Line Out
  Available: ['Line Out', 'Optical Out', 'Bluetooth Out']

Playback:
  State: play
  Source: spotify
  Volume: 45%

... (much more diagnostic information)
```

## Troubleshooting

**If you get "pywiim not installed":**

- The integration should have installed it automatically
- Try: `pip3 install --upgrade pywiim>=2.1.10` in the terminal

**If the script fails to download:**

- Check your internet connection
- Try accessing the URL directly: https://raw.githubusercontent.com/mjcumming/pywiim/main/scripts/monitor_cli.py
- Or download it manually from: https://github.com/mjcumming/pywiim/tree/main/scripts

**If you can't find your device IP:**

- Check Home Assistant → Settings → Devices & Services → WiiM
- Look at the device's entity ID or check your router's device list

## What to Share

When reporting issues, please share:

1. The full output from `monitor_cli` (especially the Audio Output section)
2. Your device model (WiiM Mini, Pro, Ultra, etc.)
3. Your Home Assistant version
4. Your integration version (Settings → Devices & Services → WiiM → Version)
5. Your pywiim version: `pip3 show pywiim | grep Version`

This helps us quickly identify if the issue is in pywiim, the integration, or the device itself.

## Quick One-Liner

For the fastest diagnosis, just run this in Home Assistant Terminal:

```bash
wget -q https://raw.githubusercontent.com/mjcumming/pywiim/main/scripts/monitor_cli.py -O /tmp/monitor_cli.py && python3 /tmp/monitor_cli.py <device_ip> | grep -A 5 "Audio Output"
```

This downloads, runs, and shows just the audio output diagnostics.
