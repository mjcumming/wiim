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
  - **CRITICAL PROBLEM**: UPnP state is **actively overwriting** HTTP state via `_merge_upnp_state_to_coordinator()`
  - When UPnP events arrive, they update `status_model` with UPnP state (including incorrect `play_status` for DLNA)
  - Even if HTTP polling provides correct state, UPnP events arrive more frequently and **overwrite** it
  - **Result**: State shows "idle" because UPnP is constantly providing wrong state and overwriting correct HTTP state
  - **Additional issue**: HTTP polling frequency reduced (30s instead of 15s) when UPnP is healthy, making it even harder for HTTP to "win"

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
3. **The real issue**: UPnP is providing **incorrect** `TransportState` for DLNA sources on Audio Pro devices, and this incorrect state is **overwriting** correct HTTP state via `_merge_upnp_state_to_coordinator()`

## Potential Fixes

1. **Don't merge UPnP state if it's incorrect**: Check if UPnP state makes sense before merging (e.g., if playing but UPnP says idle, don't overwrite)
2. **For Audio Pro + DLNA**: Don't merge UPnP `play_state` for DLNA sources on Audio Pro devices - rely on HTTP instead
3. **State priority**: Use HTTP state as source of truth for Audio Pro devices, only use UPnP for volume/mute
4. **DLNA-specific handling**: Check if UPnP `TransportState` is being parsed correctly for DLNA sources - might need different parsing logic
5. **Conditional merging**: Only merge UPnP state if it's not obviously wrong (e.g., if HTTP says playing but UPnP says idle, trust HTTP)

## Code Locations to Check

- `coordinator_polling.py`: HTTP polling frequency reduction when UPnP is healthy
- `data.py:1254-1266`: UPnP state → PlayerStatus conversion (might not handle DLNA correctly)
- `upnp_eventer.py:236-239`: UPnP TransportState parsing (might not parse DLNA state correctly)
- `data.py:961-1006`: Source detection (still uses HTTP, but polling might be too slow)
