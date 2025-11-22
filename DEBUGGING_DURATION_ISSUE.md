# Debugging Duration=00:00 Issue

## The Problem

Sometimes the web dashboard shows:
- Position: Correct (e.g., 07:25)
- Duration: **00:00** (WRONG!)

## Root Cause

PyWiim is returning `None` or `0` for `player.media_duration` while `player.media_position` has a valid value.

## Diagnostic Logging Added (v1.0.12)

The integration now logs warnings when this happens:

```
WARNING: Master Bedroom: PyWiim returned invalid duration! position=445, duration=None, state=playing, title=Brand New Day
```

##What to Check

### 1. Enable Debug Logging

Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.wiim: debug
```

### 2. Look for Warning Messages

When duration shows 00:00, check Home Assistant logs for:
```
PyWiim returned invalid duration!
```

This will show:
- Current position value
- Duration value (likely `None` or `0`)
- Playback state
- Track title

### 3. Report to PyWiim

If you see these warnings, the issue is in pywiim v2.1.0 not properly parsing duration from the device. Report to: https://github.com/your-pywiim-repo/issues

Include:
- The warning message from logs
- What source you're playing from (Spotify, Tidal, NAS, etc.)
- Device model (WiiM Mini/Pro/Amp/Ultra)

## Possible PyWiim Issues

1. **Parsing Error**: Device reports duration in unexpected format
2. **Timing Issue**: Duration not yet available when position is
3. **Source-Specific**: Some sources (Spotify, Tidal) don't report duration immediately
4. **Device Firmware**: Specific firmware versions might have issues

## Workarounds

None currently - this needs to be fixed in pywiim library.

## Technical Details

### Data Flow
```
Device → PyWiim → HA Integration → Web Dashboard
         ^^^^^^
         Problem is here - returning None/0 for duration
```

### Code Location
`custom_components/wiim/media_player.py` lines 154-195:
- `_update_position_from_coordinator()` reads values from pywiim
- If `player.media_duration` is None/0, that's what we display
- Warning is logged when playing with invalid duration

