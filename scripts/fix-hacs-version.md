# Fix HACS Download Issue

If you're experiencing the "404 download error" for v0.3.0, follow these steps:

## Method 1: Force Update to Latest Version

1. **In Home Assistant**:

   - Go to **HACS** → **Integrations**
   - Find **WiiM Audio (LinkPlay)**
   - Click the **⋮** menu → **Redownload**
   - Select **v0.3.2** (latest version)

2. **Clear HACS Cache**:
   - **Settings** → **System** → **Restart Home Assistant**
   - After restart, try installing again

## Method 2: Manual Installation

If HACS continues to fail:

1. **Download from GitHub**:

   - Visit: https://github.com/mjcumming/wiim/releases/latest
   - Download `wiim.zip`

2. **Manual Install**:
   - Extract to `/config/custom_components/wiim/`
   - Restart Home Assistant

## Method 3: Remove and Reinstall

1. **Remove Integration**:

   - HACS → Integrations → WiiM Audio → Remove
   - **Settings** → **Devices & Services** → Remove WiiM entries

2. **Reinstall**:
   - HACS → Integrations → Explore & Download
   - Search "WiiM Audio" → Install latest version

## Verify Fix

After installation:

- Check **Settings** → **Devices & Services**
- Should see "WiiM Audio (LinkPlay)" available
- No more "Integration 'wiim' not found" errors in logs

## Prevention

The auto-release workflow now ensures all future versions will have proper ZIP files attached.
