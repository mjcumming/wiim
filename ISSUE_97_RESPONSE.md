# Response to Issue #97 Follow-up

Thank you for testing v0.2.17 and providing detailed feedback! I've addressed the volume issue and need some clarification on the other problems you reported.

**Note**: I see from [issue #98](https://github.com/mjcumming/wiim/issues/98) that you mentioned grouping seems to work now with the new version - that's great! The state/source issues you're experiencing are what I'm focusing on here.

## ✅ Issue #1: Volume Level Missing Initially - FIXED

I've identified and fixed the root cause: there was a race condition at startup where UPnP eventing hadn't sent the first volume event yet, but the integration was already excluding volume from HTTP polling.

**Fix**: The integration now always polls HTTP volume at startup, and only switches to UPnP volume once it has actually provided volume data (not just subscribed). This ensures volume is always available immediately.

**Status**: Fixed in latest commit. Please test and let me know if the volume now appears correctly at startup.

**Note**: I understand you've switched back to v0.1.28 due to the state/source issues. Once I get these resolved, you should be able to use the latest version with both grouping and state/source working correctly.

---

## ❓ Issue #2: State Stays Idle When Playing (DLNA/Music Assistant)

I need some clarification to help diagnose this. **Please create a new GitHub issue** for this problem so I can track it independently.

**Questions:**

1. **What exactly do you mean by "state"?**
   - Is the player showing as `idle` in Home Assistant's media player entity (player state: playing/paused/idle)?
   - Or is the metadata (title/artist/album) not showing up (metadata state)?
   - Or both?

2. **When does this happen?**
   - Does it occur when the speaker is NOT grouped (solo)?
   - Or only when grouped with other speakers?
   - This helps determine if it's a DLNA-specific issue or a multiroom issue.

3. **UPnP vs HTTP State**: I suspect UPnP events might be overwriting HTTP state. Can you check:
   - Enable debug logging: `custom_components.wiim: debug`
   - Look for "📡 Received UPnP NOTIFY" messages when playing DLNA
   - What does the `TransportState` show in those events? (check the LastChange XML in debug logs)
   - Compare with Spotify - are UPnP events being received for both?
   - **Key question**: Does the state briefly show "playing" after a restart, then switch to "idle"? (This would confirm UPnP is overwriting HTTP state)

4. **HTTP API Test**: When playing DLNA, can you test the HTTP API directly in a browser:
   ```
   https://<device-ip>/httpapi.asp?command=getPlayerStatus
   ```
   (or `http://` if HTTPS doesn't work, or try `getStatusEx` for Audio Pro)
   - What does the `state`, `play_status`, or `status` field show?
   - Compare with Spotify - what's different?

5. **Official App**: What does the official WiiM/LinkPlay app show for playback state when playing DLNA? Does it show "Playing" correctly?

**Action**: Please create a **new GitHub issue** for this problem and include the answers to the questions above.

---

## ❓ Issue #3: Source Missing for DLNA

I need some information to help diagnose this:

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

**Action**: Please create a **new GitHub issue** for this problem so I can track it independently. Include the information above.

---

## ❓ Issue #4: Integration Trying to Connect to Router IP (192.168.178.1)

This might actually be expected behavior, but I need to confirm:

**Expected Behavior**: During SSDP discovery, the integration checks ALL UPnP devices on your network to see if they're LinkPlay/WiiM devices. This means it will make ONE validation call to every UPnP device, including routers (if they advertise UPnP services that match our SSDP filters).

**Questions**:
1. **Is this just one call during initial discovery?** (This is expected - the integration checks all UPnP devices)
2. **Or is it repeated calls during normal operation?** (This would be a problem)
3. **What's the exact error message?**
   - What API call is being made to 192.168.178.1?
   - Is it a discovery attempt or an API call during normal operation?
4. **Check your logs**:
   - Look for "SSDP discovery from:" messages
   - Does it show the router IP in discovery?
   - Does validation fail? (Should see "SSDP discovery validation failed" or similar)

If it's just one call during discovery that fails validation, that's expected and harmless. If it's repeated calls during normal operation, that's a bug I need to fix.

**Action**: Please create a **new GitHub issue** for this if it's causing problems (repeated calls, not just one discovery attempt). Include the information above.

---

## Summary

- ✅ **Volume issue**: Fixed - please test
- ❓ **State issue**: Need clarification - **please create new issue #99** (or next available)
- ❓ **Source issue**: Need information - **please create new issue #100** (or next available)
- ❓ **Router IP**: Need to confirm if it's a problem - **please create new issue #101** (or next available) if it's causing problems

**Important**: I suspect the state issue might be caused by UPnP events overwriting HTTP state. Before I implement a fix, I need to confirm this is actually happening. The debug logging questions above will help verify this theory.

Thank you for your patience and detailed feedback! Creating separate issues will help track and fix each problem independently.

**P.S.**: I see you mentioned in issue #98 that grouping seems to work now - that's excellent! Once I get the state/source issues sorted out, you should be able to use the latest version with everything working properly. I appreciate you taking the time to test when you can (household harmony is important! 😊).

