# Running Diagnostic Scripts in Home Assistant

If you have the WiiM integration installed in Home Assistant and want to run diagnostic scripts to troubleshoot issues, here's how:

## Quick Answer

**Yes, you can run pywiim's diagnostic tools!**

The `pywiim` library is already installed with the integration. However, **the Home Assistant Terminal add-on does not include Python** - it's a minimal Docker container with only a shell. You'll need to either:

- Use SSH access to run commands in the Home Assistant container (Method 1 or 2)
- Run the script locally on your computer (Method 3)

The `monitor_cli` script is a comprehensive diagnostic tool that shows all device state including audio output mode.

## Method 1: Using SSH Add-on (Recommended for Home Assistant)

**⚠️ Important:** The Home Assistant Terminal add-on is a Docker container that does **not** include Python or pip by default. You cannot run Python scripts directly in it.

Instead, use the **SSH & Web Terminal** add-on with protected mode disabled:

1. **Install SSH & Web Terminal Add-on** (if not already installed):

   - Go to **Settings** → **Add-ons** → **Add-on Store**
   - Search for "SSH & Web Terminal"
   - Install and start it

2. **Disable Protected Mode**:

   - Open the SSH & Web Terminal add-on configuration
   - **Disable "Protected mode"** (this grants access outside the terminal container)
   - Save and restart the add-on

3. **Access the Home Assistant container**:

   ```bash
   # SSH into your Home Assistant system, then download the script:
   docker exec -it homeassistant wget -q https://github.com/mjcumming/pywiim/raw/refs/heads/main/pywiim/cli/monitor_cli.py -O /tmp/monitor_cli.py

   # Run it (pywiim library is already installed in the Home Assistant container)
   docker exec -it homeassistant python3 /tmp/monitor_cli.py <your_device_ip>

   # Example:
   docker exec -it homeassistant python3 /tmp/monitor_cli.py 192.168.1.100
   ```

   This will show comprehensive device diagnostics including:

   - Audio output mode (`audio_output_mode`)
   - Available outputs (`available_outputs`)
   - Current playback state
   - Device capabilities
   - And much more!

## Method 2: Using Direct SSH Access

If you have SSH access to your Home Assistant system (not via add-on):

1. **SSH into your Home Assistant system**

2. **Download and run pywiim's monitor_cli**:

   ```bash
   # Download the script
   wget -q https://github.com/mjcumming/pywiim/raw/refs/heads/main/pywiim/cli/monitor_cli.py -O /tmp/monitor_cli.py

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
   wget https://github.com/mjcumming/pywiim/raw/refs/heads/main/pywiim/cli/monitor_cli.py -O monitor_cli.py

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

- The integration should have installed it automatically in the Home Assistant container
- If running in the Home Assistant container: `docker exec -it homeassistant pip3 install --upgrade pywiim>=2.1.10`
- If running locally: `pip3 install --upgrade pywiim>=2.1.10`
- **Note:** The Home Assistant Terminal add-on cannot install packages - it doesn't have Python or pip

**If the script fails to download:**

- Check your internet connection
- Try accessing the URL directly: https://github.com/mjcumming/pywiim/raw/refs/heads/main/pywiim/cli/monitor_cli.py
- Or download it manually from: https://github.com/mjcumming/pywiim/tree/main/pywiim/cli

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

**For Home Assistant Container** (via SSH with protected mode disabled):

```bash
docker exec -it homeassistant bash -c "wget -q https://github.com/mjcumming/pywiim/raw/refs/heads/main/pywiim/cli/monitor_cli.py -O /tmp/monitor_cli.py && python3 /tmp/monitor_cli.py <device_ip> | grep -A 5 'Audio Output'"
```

**For local computer** (if you have Python installed):

```bash
wget -q https://github.com/mjcumming/pywiim/raw/refs/heads/main/pywiim/cli/monitor_cli.py -O /tmp/monitor_cli.py && python3 /tmp/monitor_cli.py <device_ip> | grep -A 5 "Audio Output"
```

This downloads, runs, and shows just the audio output diagnostics.
