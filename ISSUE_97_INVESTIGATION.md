# Issue #97 Investigation - Multiple Problems

**User Feedback**: After testing v0.2.17, user reported 4 separate issues. **Recommendation**: Split into separate issues for better tracking.

## Problem 1: Volume Level Missing Initially

**Symptom**: `volume_level` only appears after manually changing volume once.

**Root Cause Analysis**:
- **CRITICAL FINDING**: In `coordinator_polling.py:333-342`, when UPnP is enabled and has provided volume, we **remove volume from HTTP polling**
- At startup, UPnP may not have provided volume yet, but we're already excluding it from HTTP polling
- This creates a race condition: UPnP hasn't sent volume event yet, but HTTP polling is already disabled for volume
- **Note**: For Audio Pro devices, HTTP volume API might not work anyway, but we should still poll at startup for all devices
- Volume parsing in `api_parser.py:111-117` looks for `vol` field, but it's being removed before parsing

**Code Location**:
- `custom_components/wiim/coordinator_polling.py:333-342` (removes volume when UPnP active)
- `custom_components/wiim/coordinator_polling.py:868-890` (preserves UPnP volume)
- `custom_components/wiim/data.py:1218-1233` (`should_use_upnp_volume()` check)
- `custom_components/wiim/api_parser.py:110-117` (volume parsing)

**Questions for User**:
1. **Test HTTP API directly**: Open browser and go to:
   ```
   https://<device-ip>/httpapi.asp?command=getPlayerStatus
   ```
   (or `http://` if device doesn't support HTTPS)
   - Check if `vol` field is present in the JSON response
   - Share the raw JSON response
   - **Test at startup** (before any volume changes)

2. **Check UPnP status**: Is UPnP eventing working? Check logs for:
   - "UPnP event subscriptions" messages
   - Any UPnP subscription failures
   - When does first UPnP volume event arrive? (might be after HTTP polling already excluded it)

**Potential Fix**:
- **Always poll volume at startup** - don't exclude HTTP volume until UPnP has **actually provided** volume data (not just subscribed)
- Add fallback: if UPnP volume is None, use HTTP volume
- Fix the race condition: poll HTTP volume initially, then switch to UPnP once it provides data

---

## Problem 2: State Stays Idle When Playing (DLNA/Music Assistant)

**Symptom**: State remains `idle` when playing via DLNA/Music Assistant, especially when grouped. **Works fine with Spotify**.

**Key Question**: Why does Spotify work but DLNA doesn't? This suggests the API returns different data for different sources.

**Important Context**:
- **We're mostly tracking state using UPnP events** (`upnp_eventer.py:236-239` parses `TransportState`)
- **Audio Pro devices don't support HTTP API playback state** - they rely on UPnP
- State detection in `data.py:722-760` reads from `status_model.play_state`, which comes from either:
  - HTTP API (`api_parser.py:84-86`) - for WiiM devices
  - UPnP events (`data.py:1254-1266`) - merged into status_model via `_merge_upnp_state_to_coordinator()`

**ACTION REQUIRED**: 
- **Please clarify what "state" means**:
  - Is the player showing as `idle` in Home Assistant (player state)?
  - Or is metadata (title/artist) not showing (metadata state)?
  - Or both?
- **Please create a separate GitHub issue** for this problem so we can track it independently

**Code Location**:
- `custom_components/wiim/data.py:722-760` (state detection - reads from status_model)
- `custom_components/wiim/data.py:1254-1266` (UPnP state → PlayerStatus conversion)
- `custom_components/wiim/upnp_eventer.py:236-239` (UPnP TransportState parsing)
- `custom_components/wiim/api_parser.py:84-86` (HTTP play_state parsing)

**Questions for User**:
1. **Clarify what "state" means**:
   - Is the player showing as `idle` in Home Assistant?
   - Or is metadata (title/artist) not showing?
   - Or both?

2. **Test HTTP API directly**: When playing DLNA, check:
   ```
   https://<device-ip>/httpapi.asp?command=getPlayerStatus
   ```
   - What does the `state`, `play_status`, or `status` field show?
   - Compare with Spotify - what's different?
   - **Note**: For Audio Pro, HTTP API might not have playback state

3. **Check UPnP events**: Enable debug logging and check:
   - Are UPnP events being received? (look for "📡 Received UPnP NOTIFY" messages)
   - What does `TransportState` show in UPnP events when playing DLNA?
   - Compare with Spotify - what's different?

4. **Check WiiM/LinkPlay app**: What does the official app show for state when playing DLNA?
   - Does it show "Playing" correctly?
   - This confirms if it's an API issue or our parsing issue

5. **Test without grouping**: Does the issue occur when the speaker is NOT grouped?
   - If it only happens when grouped, it's a multiroom issue
   - If it happens solo too, it's a DLNA source detection issue

**Potential Fix**:
- For Audio Pro devices, rely entirely on UPnP for playback state (HTTP doesn't support it)
- Check if UPnP `TransportState` is being parsed correctly for DLNA
- Add logging to see what UPnP events contain when playing DLNA vs Spotify
- Consider using position/duration changes as state indicators if TransportState is missing

---

## Problem 3: Source Missing for DLNA

**Symptom**: Source is sometimes missing when using DLNA (Music Assistant). Works fine with Spotify/Bluetooth.

**Key Question**: What does the WiiM/LinkPlay app show for source when using DLNA?

**Root Cause Analysis**:
- Source detection in `data.py:961-1006` looks for `source` or `mode` fields from HTTP API
- If both are None/empty, source will be None
- DLNA might return `mode=2` (per MODE_MAP) but we need to verify
- **Note**: User said "this is not a group speaker issue" - so it's a DLNA source detection issue
- We're using UPnP for DLNA - maybe we should get source from UPnP instead of HTTP?

**ACTION REQUIRED**: 
- **Please create a separate GitHub issue** for this problem so we can track it independently

**Code Location**:
- `custom_components/wiim/data.py:961-1006` (source detection)
- `custom_components/wiim/const.py:242-270` (SOURCE_MAP)
- `custom_components/wiim/const.py:117-137` (MODE_MAP - mode 2 = dlna)

**Questions for User**:
1. **Test HTTP API directly**: When playing DLNA, check:
   ```
   https://<device-ip>/httpapi.asp?command=getPlayerStatus
   ```
   - What does the `mode` field show? (should be "2" for DLNA)
   - What does the `source` field show?
   - Share the raw JSON response

2. **Check WiiM/LinkPlay app**: What does the official app show for source when playing DLNA?
   - Does it show "DLNA" or "Network" or something else?
   - This confirms what the device actually reports

3. **Check UPnP**: Since we use UPnP for DLNA, maybe source should come from UPnP metadata?
   - Check if UPnP events include source information

**Potential Fix**:
- Verify MODE_MAP correctly maps mode "2" to "dlna"
- Check if we should use UPnP metadata for DLNA source instead of HTTP
- Add fallback: if HTTP doesn't have source but UPnP is active, use UPnP source

---

## Problem 4: Integration Trying to Connect to Router IP

**Symptom**: Integration attempts to communicate with `192.168.178.1` (Fritz!Box router), not a LinkPlay device.

**Key Question**: Is this just one call during discovery (expected) or repeated calls (problem)?

**Root Cause Analysis**:
- **Expected behavior**: During SSDP discovery (`config_flow.py:667-714`), we check ALL UPnP devices to see if they're LinkPlay/WiiM devices
- This means we will make ONE validation call to every UPnP device on the network, including routers
- Router might be advertising UPnP services that match our SSDP filters in `manifest.json` (AVTransport, RenderingControl, etc.)
- **Current validation**: `validate_wiim_device()` in `config_flow.py:96-184` should catch non-LinkPlay devices and fail validation
- If router responds to `get_status()` with something that looks valid, it might pass validation (unlikely but possible)
- **Note**: We filter WSL2 IPs (`192.168.65.x`) in UPnP code, but not router IPs

**Questions for User**:
1. **Is this just one call during discovery?** (This is expected - we check all UPnP devices)
2. **Or is it repeated calls during normal operation?** (This would be a problem)
3. **Does validation fail?** (Check logs - should see "SSDP discovery validation failed" or similar)

**Code Location**:
- `custom_components/wiim/config_flow.py:667-714` (SSDP discovery)
- `custom_components/wiim/config_flow.py:96-184` (device validation)
- `custom_components/wiim/upnp_client.py:201,246` (WSL2 IP filtering - but not router IPs)
- `custom_components/wiim/coordinator_multiroom.py` (multiroom coordination)

**Questions for User**:
1. **When does this happen?**
   - During initial discovery?
   - During normal operation?
   - When grouped?
   - Check logs for the exact error/timing

2. **What's the error message?**
   - What API call is being made to 192.168.178.1?
   - Is it a discovery attempt or an API call?
   - Check logs for the full stack trace

3. **Check SSDP discovery logs**:
   - Look for "SSDP discovery from:" messages
   - Does it show router IP in discovery?
   - Does validation fail or pass?

**Potential Fix**:
- Add explicit router IP filtering in `validate_wiim_device()` (common router IPs: .1, .254, gateway IPs)
- Filter router IPs in SSDP discovery before validation
- Validate discovered devices more strictly (check for LinkPlay UUID/manufacturer in response)
- Add logging to track where router IP is coming from
- Check if router is advertising UPnP services that match our SSDP filters in manifest.json

---

## Recommended Next Steps

1. **Split into 4 separate GitHub issues** - One issue per problem for better tracking
2. **Ask user to test HTTP API directly** - Use browser to check raw API responses
3. **Verify with official app** - Check what WiiM/LinkPlay app shows vs our integration
4. **Check UPnP status** - Verify UPnP is working and providing data

## Action Items for User

### For Each Issue, Please:

1. **Test HTTP API directly in browser**:
   ```
   https://<device-ip>/httpapi.asp?command=getPlayerStatus
   ```
   (or `http://` if HTTPS doesn't work)
   - Copy the raw JSON response
   - Test when playing DLNA vs Spotify
   - Test when volume is missing vs present

2. **Check official WiiM/LinkPlay app**:
   - What does it show for volume/state/source?
   - Does it match what our integration shows?
   - This helps determine if it's an API issue or our parsing issue

3. **Enable debug logging**:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.wiim: debug
       custom_components.wiim.api_parser: debug
       custom_components.wiim.data: debug
       custom_components.wiim.coordinator_polling: debug
       custom_components.wiim.upnp_client: debug
   ```

4. **Check logs for**:
   - "Using UPnP volume" messages (volume issue)
   - Raw API responses when volume/state/source are missing
   - Any attempts to connect to 192.168.178.1 (router IP issue)
   - UPnP subscription status

## Specific Questions by Issue

### Issue 1 (Volume):
- Does HTTP API return `vol` field? (test in browser)
- Is UPnP eventing working? (check logs for UPnP messages)
- Does volume appear after UPnP sends first event?

### Issue 2 (State):
- What does HTTP API return for `state`/`play_status` when playing DLNA? (test in browser)
- What does official app show for state?
- Does it happen when NOT grouped? (to rule out multiroom issue)

### Issue 3 (Source):
- What does HTTP API return for `mode` when playing DLNA? (should be "2")
- What does official app show for source?
- Is this a DLNA-specific issue or all network sources?

### Issue 4 (Router IP):
- When exactly does this happen? (discovery, normal operation, grouping?)
- What's the exact error message?
- Check logs for where 192.168.178.1 is coming from

