# WiiM Artwork Fix for Older LinkPlay Devices

## Issue Summary

Media artwork was not working on older LinkPlay devices (Audio Pro C3, C5, C10 speakers) after the refactor from v0.1.0 to v0.1.4. The artwork worked fine on newer WiiM devices and with other integrations (old unofficial LinkPlay, DLNA), but failed with the current WiiM integration.

## Root Cause

Older LinkPlay devices don't support the `getMetaInfo` command, which is the primary method the WiiM integration uses to fetch rich metadata including artwork. These devices return "unknown command" when `getMetaInfo` is called.

The fallback system for basic metadata extraction was not comprehensive enough to find artwork URLs in the various field names that older LinkPlay firmware versions use.

## Solution Implemented

### 1. Enhanced Basic Metadata Extraction (`coordinator_metadata.py`)

**Improved artwork field search:**

- Added more artwork field names that older LinkPlay devices use
- Prioritized the most common fields first
- Added fields like `art`, `picture`, `albumcover`, `track_image`

**Multiple extraction approaches:**

1. **Basic status fields** - First tries the most common artwork fields
2. **Fresh status fetch** - Fetches fresh `getPlayerStatus` for more fields
3. **Nested object search** - Searches nested objects for artwork
4. **Alternative API endpoints** - Tries `get_device_info()` and `get_player_status()` endpoints

**Enhanced validation:**

- Validates that artwork URLs actually look like URLs before using them
- Better error handling and fallback logic
- Enhanced debug logging to troubleshoot artwork issues

### 2. Improved Track Change Detection (`coordinator_polling.py`)

**Artwork change detection:**

- Enhanced `_track_changed()` function to also detect artwork URL changes
- Triggers metadata updates when artwork changes even if track info stays the same
- Provides specific logging for artwork vs. track changes

### 3. Existing Cache Management

The media player entity already had excellent artwork cache management:

- Clears media image cache when track or artwork URL changes
- Handles the special case where devices keep the same URL but change content
- Provides immediate feedback with optimistic state handling

## Field Names Searched (in priority order)

1. **Primary fields:** `albumArtURI`, `albumart`, `cover_url`, `cover`
2. **Secondary fields:** `albumArtUri`, `albumarturi`, `art_url`, `artwork_url`, `pic_url`, `entity_picture`
3. **Alternative fields:** `thumbnail`, `image`, `coverart`, `cover_art`, `album_art`, `artworkUrl`, `imageUrl`, `art`, `picture`, `albumcover`, `track_image`

## Testing the Fix

### Quick Test

1. Restart Home Assistant with the updated integration
2. Play music on your Audio Pro device
3. Check if artwork appears in the media player entity
4. Check logs for artwork-related debug messages

### Detailed Test

Use the provided test script:

```bash
cd /path/to/wiim/integration
python test_artwork_fix.py <your_device_ip>
```

### Expected Log Messages

For older devices, you should see logs like:

```
🎨 Artwork extracted from basic status for 192.168.x.x (status.albumArtURI): http://...
```

## Files Modified

1. **`coordinator_metadata.py`**

   - Enhanced `_extract_basic_metadata()` function
   - Added more artwork field names and extraction approaches
   - Better validation and debugging

2. **`coordinator_polling.py`**
   - Enhanced `_track_changed()` function to detect artwork changes
   - Fixed tuple unpacking for artwork tracking

## Compatibility

- ✅ **Older LinkPlay devices** (Audio Pro C3, C5, C10) - Enhanced support
- ✅ **Newer WiiM devices** - Unchanged, still uses `getMetaInfo`
- ✅ **Mixed environments** - Automatically detects device capabilities

## Debugging

If artwork still doesn't work:

1. **Enable debug logging** in Home Assistant:

   ```yaml
   logger:
     default: info
     logs:
       custom_components.wiim.coordinator_metadata: debug
       custom_components.wiim.coordinator_polling: debug
   ```

2. **Check for artwork-related log messages:**

   - `🎨 Artwork extracted from basic status...` (success)
   - `❌ No valid artwork URL found...` (failure)
   - `Device info fields for X.X.X.X: [...]` (debugging info)

3. **Run the test script** to see exactly what fields your device provides

4. **Verify device is playing media** - artwork is only available during playback

This fix restores the v0.1.0 functionality while maintaining all the improvements made in subsequent versions.
