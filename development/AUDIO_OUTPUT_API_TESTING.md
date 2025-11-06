# Quick Reference: WiiM Audio Output API Testing Commands

## Prerequisites

- Use **HTTPS** (not HTTP) - device uses SSL/TLS
- Use `-k` flag to bypass certificate verification (self-signed cert)
- Replace `<DEVICE_IP>` with your WiiM device IP (e.g., `192.168.1.68`)

## Current Implementation (Known to Work)

### Get Current Output Status

```bash
curl -s -k "https://<DEVICE_IP>/httpapi.asp?command=getNewAudioOutputHardwareMode"
```

**Response:**

```json
{ "hardware": "2", "source": "0", "audiocast": "0" }
```

**Mode Values:**

- `1` = Optical Out
- `2` = Line Out
- `3` = Coax Out
- `4` = Bluetooth Out

### Set Output Mode

```bash
curl -s -k "https://<DEVICE_IP>/httpapi.asp?command=setAudioOutputHardwareMode:<mode>"
```

**Example:**

```bash
curl -s -k "https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:2"
```

## Findings

✅ **Working Endpoints:**

- `getNewAudioOutputHardwareMode` - Returns current output status
- `setAudioOutputHardwareMode:<mode>` - Sets output mode

❌ **Not Supported (all return "unknown command"):**

- `getSoundCardModeSupportList`
- `getActiveSoundCardOutputMode`
- `getSoundCardModeList`
- `getAudioOutputModeList`
- `getOutputModeList`
- `getSupportedOutputModes`

**Conclusion:** There is **no API endpoint** to get a list of available output modes. The codebase must use a hardcoded list.

## Testing Headphone Support (Issue #86)

**Easy Browser Test:** Just open this URL with headphones connected:
`https://192.168.1.68/httpapi.asp?command=getNewAudioOutputHardwareMode`
(Replace IP with your device IP)

### Step 1: Get current status with headphones connected

1. Connect headphones to WiiM Ultra front panel
2. Select headphones from front panel
3. **Open this URL in your browser** (replace IP with your device IP):
   - `https://192.168.1.68/httpapi.asp?command=getNewAudioOutputHardwareMode`
   - You'll see JSON like: `{"hardware":"2","source":"0","audiocast":"0"}`
   - **Check the `hardware` field value** - this tells us the mode number for headphones

**Or use curl:**

```bash
curl -s -k "https://192.168.1.68/httpapi.asp?command=getNewAudioOutputHardwareMode"
```

**Expected responses:**

- If headphones are mode `0`: `{"hardware":"0","source":"0","audiocast":"0"}`
- If headphones are mode `5`: `{"hardware":"5","source":"0","audiocast":"0"}`
- If headphones are mode `2`: `{"hardware":"2","source":"0","audiocast":"0"}` (same as Line Out - unlikely)

### Step 2: Test setting headphone mode (once mode value is known)

```bash
# Test mode 0 (if that's the headphone mode)
curl -s -k "https://<DEVICE_IP>/httpapi.asp?command=setAudioOutputHardwareMode:0"

# Test mode 5 (if that's the headphone mode)
curl -s -k "https://<DEVICE_IP>/httpapi.asp?command=setAudioOutputHardwareMode:5"
```

## Quick Test Commands

**Test in Browser (Easiest):**

- Current status: `https://192.168.1.68/httpapi.asp?command=getNewAudioOutputHardwareMode`
- Set to Line Out: `https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:2`
- Set to Optical Out: `https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:1`
- Set to Coax Out: `https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:3`
- Set to Bluetooth Out: `https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:4`
- Set to Headphone Out (if mode 0): `https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:0`

```bash
# Current status
curl -s -k "https://192.168.1.68/httpapi.asp?command=getNewAudioOutputHardwareMode"

# Set to Line Out (mode 2)
curl -s -k "https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:2"

# Set to Optical Out (mode 1)
curl -s -k "https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:1"

# Set to Coax Out (mode 3)
curl -s -k "https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:3"

# Set to Bluetooth Out (mode 4)
curl -s -k "https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:4"

# Set to Headphone Out (mode 0 - needs verification)
curl -s -k "https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:0"
```

## Next Steps

1. **For Issue #86:** Test with headphones connected to verify the mode value
   - Headphone support has been added with mode `0` (needs verification)
   - If mode `0` is incorrect, update `AUDIO_OUTPUT_MODES` in `const.py`

## Implementation Status

✅ **Headphone Out support added** (Issue #86)

- Added mode `0` = "Headphone Out" to `AUDIO_OUTPUT_MODES` mapping
- Conditionally shown only for Ultra devices
- **Needs verification:** Mode value `0` is an educated guess - user should test

**To verify:**

1. Connect headphones to WiiM Ultra front panel
2. Select headphones from front panel
3. **Open in browser:** `https://<YOUR_DEVICE_IP>/httpapi.asp?command=getNewAudioOutputHardwareMode`
   - Example: `https://192.168.1.68/httpapi.asp?command=getNewAudioOutputHardwareMode`
4. Check the `hardware` field value in the JSON response
5. If it's not `0`, update the mapping in `const.py` with the correct value
6. **Report back on Issue #86** with the mode value you found!
