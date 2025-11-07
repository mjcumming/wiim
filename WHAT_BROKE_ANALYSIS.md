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
- **v0.1.28**: Got `play_state` directly from HTTP `getStatusEx`/`getPlayerStatusEx` response
  - Audio Pro devices use `getStatusEx` (not `getPlayerStatusEx`)
  - HTTP response might not include `state` field, or it might be missing/incorrect
  - But we were polling frequently (every 5-15s), so even if state was sometimes missing, it would update
- **v0.2.0+**: Relies on UPnP `TransportState` events merged into `status_model`
  - **We DO have HTTP fallback** if UPnP isn't working (documented in UPNP_TESTING.md)
  - **Problem**: When UPnP is "healthy" (subscribed and receiving events), we reduce HTTP polling frequency (30s instead of 15s)
  - If UPnP events aren't providing correct `TransportState` for DLNA sources, we're stuck with:
    - Slower HTTP polling (30s instead of 15s)
    - HTTP response might not have `state` field anyway (Audio Pro limitation)
  - **Key issue**: UPnP might be "healthy" (subscribed) but not providing correct state for DLNA

### 2. Source Detection
- **v0.1.28**: Got `source`/`mode` directly from HTTP `getStatusEx` response
  - Polled frequently (every 5-15s), so source would update regularly
- **v0.2.0+**: Still gets source from HTTP, but:
  - HTTP polling frequency reduced when UPnP is healthy (30s instead of 15s)
  - If UPnP is "healthy" but not providing state, we're polling HTTP less frequently
  - Source might be missing if HTTP response doesn't include it or polling is too slow

### 3. Volume (Already Fixed)
- We were excluding HTTP volume when UPnP was subscribed (even if it hadn't provided data yet)
- **Fixed**: Now only exclude HTTP volume after UPnP has actually provided volume data

## Root Cause

The integration switched from **HTTP-first** to **UPnP-first** for state, but:
1. **Audio Pro devices DO respond to HTTP** (`getStatusEx`), but the HTTP response might not include `state` field or it might be unreliable
2. **We DO have HTTP fallback** if UPnP isn't working, BUT:
   - When UPnP is "healthy" (subscribed and receiving events), we reduce HTTP polling frequency
   - If UPnP is subscribed but not providing correct state for DLNA, we're stuck with slower HTTP polling
   - HTTP response might not have state anyway (Audio Pro limitation)
3. **The real issue**: UPnP might be "healthy" (subscribed) but not providing correct `TransportState` for DLNA sources on Audio Pro devices

## Potential Fixes

1. **Check UPnP state quality**: If UPnP is subscribed but not providing state updates, don't consider it "healthy" for polling reduction
2. **For Audio Pro devices**: Don't reduce HTTP polling frequency even if UPnP is healthy (Audio Pro HTTP state might be unreliable, but we should still poll it)
3. **DLNA-specific handling**: Check if UPnP `TransportState` is being parsed correctly for DLNA sources
4. **Use both sources**: Don't exclude HTTP state/source when UPnP is active - use both and prefer UPnP when available, but fall back to HTTP if UPnP state is missing
5. **State validation**: If UPnP provides state, use it. If not, try HTTP. If HTTP doesn't have state, that's an Audio Pro limitation we need to work around

## Code Locations to Check

- `coordinator_polling.py`: HTTP polling frequency reduction when UPnP is healthy
- `data.py:1254-1266`: UPnP state → PlayerStatus conversion (might not handle DLNA correctly)
- `upnp_eventer.py:236-239`: UPnP TransportState parsing (might not parse DLNA state correctly)
- `data.py:961-1006`: Source detection (still uses HTTP, but polling might be too slow)

