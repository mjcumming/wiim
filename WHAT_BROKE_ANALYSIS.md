# What Broke Between v0.1.28 and v0.2.0+ (State/Source Issues)

## The Major Change: UPnP Integration (v0.2.0)

**v0.1.28 (Working)**:
- Relied **entirely on HTTP polling** for state and source
- Simple, direct approach: poll `getPlayerStatus` every 5-15 seconds
- Got state/source directly from HTTP API response
- Worked for Audio Pro devices even if HTTP API wasn't perfect

**v0.2.0+ (Broken for Audio Pro + DLNA)**:
- Added **UPnP Event System** as primary source for state
- Changed to **UPnP-first** approach for playback state
- Reduced HTTP polling frequency when UPnP is healthy
- Started merging UPnP state into `status_model` via `_merge_upnp_state_to_coordinator()`

## What Broke

### 1. State Detection
- **v0.1.28**: Got `play_state` directly from HTTP `getPlayerStatus` response
- **v0.2.0+**: Relies on UPnP `TransportState` events merged into `status_model`
- **Problem**: For Audio Pro devices playing DLNA:
  - Audio Pro devices don't support HTTP API playback state (as we noted)
  - We now rely on UPnP for state
  - But UPnP might not be providing correct `TransportState` for DLNA sources
  - No fallback to HTTP state when UPnP doesn't provide it

### 2. Source Detection
- **v0.1.28**: Got `source`/`mode` directly from HTTP `getPlayerStatus` response
- **v0.2.0+**: Still gets source from HTTP, but:
  - HTTP polling frequency reduced when UPnP is healthy (30s instead of 15s)
  - If UPnP is "healthy" but not providing state, we're polling HTTP less frequently
  - Source might be missing if HTTP response doesn't include it or polling is too slow

### 3. Volume (Already Fixed)
- We were excluding HTTP volume when UPnP was subscribed (even if it hadn't provided data yet)
- **Fixed**: Now only exclude HTTP volume after UPnP has actually provided volume data

## Root Cause

The integration switched from **HTTP-first** to **UPnP-first** for state, but:
1. Audio Pro devices don't support HTTP playback state API
2. We rely on UPnP for state, but UPnP might not work correctly for DLNA sources on Audio Pro
3. No proper fallback mechanism when UPnP doesn't provide state/source

## Potential Fixes

1. **For Audio Pro devices**: Always use HTTP for source detection (don't reduce polling frequency)
2. **State fallback**: If UPnP doesn't provide state, fall back to HTTP (even if it's not perfect for Audio Pro)
3. **DLNA-specific handling**: Check if UPnP `TransportState` is being parsed correctly for DLNA sources
4. **Don't exclude HTTP state/source**: Unlike volume, we shouldn't exclude HTTP state/source when UPnP is active - use both and prefer UPnP when available

## Code Locations to Check

- `coordinator_polling.py`: HTTP polling frequency reduction when UPnP is healthy
- `data.py:1254-1266`: UPnP state → PlayerStatus conversion (might not handle DLNA correctly)
- `upnp_eventer.py:236-239`: UPnP TransportState parsing (might not parse DLNA state correctly)
- `data.py:961-1006`: Source detection (still uses HTTP, but polling might be too slow)

