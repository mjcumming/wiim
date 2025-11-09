# Issue #103 Analysis: Playback State Remains Idle and Metadata Doesn't Update

## Problem Summary

From the user's report:

- **Playback state stays `idle`** when audio is playing (DLNA, Spotify sources)
- **Metadata (title/artist/album) doesn't update**
- **UPnP subscription failures** are occurring: `Failed (re-)subscribing to: uuid:...`
- **Bluetooth works correctly** (state updates properly)
- **HTTP API shows correct status**: `"status":"play"` but Home Assistant shows `idle`
- **Grouped devices**: State/metadata eventually propagate but with 20-30 second delay

## Root Cause Analysis

### 1. UPnP Resubscription Failures

The user's logs show:

```
Failed (re-)subscribing to: uuid:c3b8c896-1dd1-11b2-88f9-fceb09991650
```

**Issue**: When UPnP resubscription fails (after initial subscription succeeds), the integration doesn't properly handle the failure:

- `_on_event()` receives empty `state_variables` (indicates resubscription failure)
- Code logs it as debug but doesn't mark subscriptions as failed
- `_upnp_eventer` still exists, so HTTP polling tries to preserve UPnP state
- But UPnP state is stale/not updating, so playback state never updates

**Location**: `upnp_eventer.py:152-157` - empty state_variables are logged but subscriptions aren't marked as failed

### 2. HTTP Polling State Overwriting

When UPnP subscriptions fail (initial or resubscription), HTTP polling should be the primary source of truth. However:

**Current behavior**:

- HTTP polling creates new `PlayerStatus` model from API response
- But if `_upnp_eventer` exists (even if broken), code tries to preserve UPnP volume
- For playback state: HTTP polling should always win when UPnP is broken

**Location**: `coordinator_polling.py:902-940` - UPnP state preservation logic may be interfering

### 3. State Merge Logic Issue

The `_merge_upnp_state_to_coordinator()` method merges UPnP state into coordinator, but:

- If UPnP resubscription fails, UPnP state becomes stale
- HTTP polling creates fresh state, but stale UPnP state might be overwriting it
- Need to check if UPnP is actually working before merging

**Location**: `data.py:1254-1333` - merge logic doesn't check if UPnP is actually working

### 4. DLNA/Spotify Source-Specific Issues

The user reports that:

- **Bluetooth works** (state updates correctly)
- **DLNA/Spotify don't work** (state stays idle)

This suggests:

- HTTP API parsing might be correct (Bluetooth works)
- But UPnP events for DLNA/Spotify might not be arriving
- Or UPnP state for these sources is being incorrectly merged

## Proposed Fixes

### Fix 1: Detect and Handle Resubscription Failures

**File**: `upnp_eventer.py`

When `_on_event()` receives empty `state_variables`, this indicates resubscription failure. We should:

1. Mark subscriptions as failed
2. Clear `_upnp_eventer` reference
3. Log warning that we're falling back to HTTP polling
4. Trigger coordinator refresh to get state from HTTP

```python
def _on_event(self, service, state_variables):
    if not state_variables:
        _LOGGER.warning(
            "UPnP resubscription failed for %s - falling back to HTTP polling",
            self.upnp_client.host
        )
        # Mark as failed and trigger fallback
        self._subscriptions_failed = True
        # Trigger coordinator refresh
        async_dispatcher_send(self.hass, f"wiim_upnp_failed_{self.device_uuid}")
        return
```

### Fix 2: Don't Preserve Stale UPnP State

**File**: `coordinator_polling.py`

When HTTP polling creates new state, only preserve UPnP state if:

1. UPnP subscriptions are actually working (not failed)
2. UPnP has recently provided data (within last 30 seconds)

```python
# Only preserve UPnP state if it's actually working
if speaker and speaker._upnp_eventer and not speaker._subscriptions_failed:
    # Check if UPnP state is recent (within 30 seconds)
    if speaker._upnp_state and speaker._upnp_state._last_update_ts:
        time_since_upnp = time.time() - speaker._upnp_state._last_update_ts
        if time_since_upnp < 30:
            # UPnP is working, preserve its state
            ...
```

### Fix 3: HTTP Polling Should Always Win for Playback State

**File**: `coordinator_polling.py`

When UPnP subscriptions have failed, HTTP polling should be the authoritative source for playback state:

```python
# If UPnP subscriptions failed, HTTP polling is authoritative
if speaker and speaker._subscriptions_failed:
    # Don't try to preserve UPnP state - use HTTP polling state directly
    # HTTP polling state is already correct in status_model
    pass
```

### Fix 4: Better Resubscription Failure Detection

**File**: `upnp_client.py` or `upnp_eventer.py`

We need to detect when `async_upnp_client`'s auto-resubscribe fails. The empty `state_variables` is one indicator, but we should also:

1. Track subscription renewal timestamps
2. Detect if no events arrive for extended period (when device is playing)
3. Mark subscriptions as failed if resubscription fails multiple times

## Testing Plan

1. **Test UPnP resubscription failure**:

   - Start with working UPnP
   - Simulate resubscription failure (network issue, device restart)
   - Verify HTTP polling takes over and state updates correctly

2. **Test DLNA playback**:

   - Play DLNA source
   - Verify state updates to `playing` via HTTP polling
   - Verify metadata updates

3. **Test Spotify playback**:

   - Play Spotify source
   - Verify state updates to `playing` via HTTP polling
   - Verify metadata updates

4. **Test grouped devices**:
   - Group Audio Pro speaker with WiiM master
   - Verify state propagates correctly
   - Verify no 20-30 second delay

## Related Code Locations

- `upnp_eventer.py:145-157` - `_on_event()` handles empty state_variables
- `data.py:1254-1333` - `_merge_upnp_state_to_coordinator()` merges UPnP state
- `coordinator_polling.py:902-940` - UPnP state preservation logic
- `data.py:1448-1467` - UPnP subscription failure handling
- `data.py:1590-1612` - UPnP event callback handler

## Next Steps

1. Implement Fix 1 (detect resubscription failures)
2. Implement Fix 2 (don't preserve stale UPnP state)
3. Implement Fix 3 (HTTP polling wins when UPnP fails)
4. Test with DLNA and Spotify sources
5. Verify grouped device behavior
