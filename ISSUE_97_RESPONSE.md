# Response to Issue #97 Follow-up

Thank you for testing v0.2.17 and providing detailed feedback! We've addressed the volume issue and need some clarification on the other problems you reported.

## ✅ Issue #1: Volume Level Missing Initially - FIXED

We've identified and fixed the root cause: there was a race condition at startup where UPnP eventing hadn't sent the first volume event yet, but we were already excluding volume from HTTP polling.

**Fix**: The integration now always polls HTTP volume at startup, and only switches to UPnP volume once it has actually provided volume data (not just subscribed). This ensures volume is always available immediately.

**Status**: Fixed in latest commit. Please test and let us know if the volume now appears correctly at startup.

---

## ❓ Issue #2: State Stays Idle When Playing (DLNA/Music Assistant)

We need some clarification to help diagnose this:

1. **What exactly do you mean by "state"?**
   - Is the player showing as `idle` in Home Assistant's media player entity (player state: playing/paused/idle)?
   - Or is the metadata (title/artist/album) not showing up (metadata state)?
   - Or both?

2. **When does this happen?**
   - Does it occur when the speaker is NOT grouped (solo)?
   - Or only when grouped with other speakers?
   - This helps us determine if it's a DLNA-specific issue or a multiroom issue.

3. **UPnP Events**: Since we primarily track playback state via UPnP events (especially for Audio Pro devices which don't support HTTP playback state), can you check your logs for:
   - "📡 Received UPnP NOTIFY" messages when playing DLNA
   - What does the `TransportState` show in those events?
   - Compare with Spotify - are UPnP events being received for both?

4. **HTTP API Test**: When playing DLNA, can you test the HTTP API directly in a browser:
   ```
   https://<device-ip>/httpapi.asp?command=getPlayerStatus
   ```
   (or `http://` if HTTPS doesn't work)
   - What does the `state`, `play_status`, or `status` field show?
   - Compare with Spotify - what's different?

5. **Official App**: What does the official WiiM/LinkPlay app show for playback state when playing DLNA? Does it show "Playing" correctly?

**Action**: Please create a **new GitHub issue** for this problem so we can track it independently. Include the answers to the questions above.

---

## ❓ Issue #3: Source Missing for DLNA

We need some information to help diagnose this:

1. **HTTP API Test**: When playing DLNA, can you test the HTTP API directly in a browser:
   ```
   https://<device-ip>/httpapi.asp?command=getPlayerStatus
   ```
   - What does the `mode` field show? (should be "2" for DLNA per our MODE_MAP)
   - What does the `source` field show?
   - Share the raw JSON response if possible

2. **Official App**: What does the official WiiM/LinkPlay app show for source when playing DLNA?
   - Does it show "DLNA" or "Network" or something else?
   - This confirms what the device actually reports

3. **When does it happen?**
   - Is it always missing for DLNA, or only sometimes?
   - Does it work correctly for other sources (Spotify, Bluetooth)?

**Action**: Please create a **new GitHub issue** for this problem so we can track it independently. Include the information above.

---

## ❓ Issue #4: Integration Trying to Connect to Router IP (192.168.178.1)

This might actually be expected behavior, but we need to confirm:

**Expected Behavior**: During SSDP discovery, the integration checks ALL UPnP devices on your network to see if they're LinkPlay/WiiM devices. This means we will make ONE validation call to every UPnP device, including routers (if they advertise UPnP services that match our SSDP filters).

**Questions**:
1. **Is this just one call during initial discovery?** (This is expected - we check all UPnP devices)
2. **Or is it repeated calls during normal operation?** (This would be a problem)
3. **What's the exact error message?** 
   - What API call is being made to 192.168.178.1?
   - Is it a discovery attempt or an API call during normal operation?
4. **Check your logs**: 
   - Look for "SSDP discovery from:" messages
   - Does it show the router IP in discovery?
   - Does validation fail? (Should see "SSDP discovery validation failed" or similar)

If it's just one call during discovery that fails validation, that's expected and harmless. If it's repeated calls during normal operation, that's a bug we need to fix.

**Action**: Please create a **new GitHub issue** for this if it's causing problems (repeated calls, not just one discovery attempt). Include the information above.

---

## Summary

- ✅ **Volume issue**: Fixed - please test
- ❓ **State issue**: Need clarification - please create new issue
- ❓ **Source issue**: Need information - please create new issue  
- ❓ **Router IP**: Need to confirm if it's a problem - please create new issue if needed

Thank you for your patience and detailed feedback! Creating separate issues will help us track and fix each problem independently.

