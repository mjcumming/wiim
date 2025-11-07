# Issue #97 Investigation - Multiple Problems

**User Feedback**: After testing v0.2.17, user reported 4 separate issues. **Recommendation**: Split into separate issues for better tracking.

## Problem 1: Volume Level Missing Initially

**Symptom**: `volume_level` only appears after manually changing volume once.

**Root Cause Analysis**:
- Volume parsing in `api_parser.py:111-117` looks for `vol` field in API response
- If `vol` is missing or None, `volume_level` will be None
- Older Audio Pro devices may not return volume in initial status response
- Volume might be in a different field name (e.g., `volume`, `Volume`)

**Code Location**: 
- `custom_components/wiim/api_parser.py:110-117`
- `custom_components/wiim/data.py:716-720`

**Potential Fix**:
- Check for alternative volume field names (`volume`, `Volume`, `VOL`)
- Add fallback to check UPnP volume if HTTP polling doesn't have it
- Log when volume is missing to help diagnose

---

## Problem 2: State Stays Idle When Playing (DLNA/Music Assistant)

**Symptom**: State remains `idle` when playing via DLNA/Music Assistant, especially when grouped. Works fine with Spotify.

**Root Cause Analysis**:
- State detection in `data.py:722-760` relies on `play_state` field
- If `play_state` is None or empty, defaults to IDLE
- DLNA/Music Assistant may not set `play_state` correctly
- Grouped speakers (slaves) might show different state than master

**Code Location**:
- `custom_components/wiim/data.py:722-760`
- `custom_components/wiim/group_media_player.py:166-176`

**Potential Fix**:
- Check for alternative state indicators (position changes, metadata presence)
- For grouped speakers, check master's state if slave state is unclear
- Add logging when state is missing to see what fields are available
- Consider using position/duration changes as state indicators for DLNA

---

## Problem 3: Source Missing for DLNA

**Symptom**: Source is sometimes missing when using DLNA (Music Assistant). Works fine with Spotify/Bluetooth.

**Root Cause Analysis**:
- Source detection in `data.py:961-1006` looks for `source` or `mode` fields
- If both are None/empty, source will be None
- DLNA might not set these fields, or uses different field names
- SOURCE_MAP in `const.py:242-270` maps "dlna" but might not be detected

**Code Location**:
- `custom_components/wiim/data.py:961-1006`
- `custom_components/wiim/const.py:242-270`

**Potential Fix**:
- Check for DLNA-specific indicators (UPnP service, DLNA headers)
- Add fallback detection based on metadata or other fields
- Log available fields when source is missing

---

## Problem 4: Integration Trying to Connect to Router IP

**Symptom**: Integration attempts to communicate with `192.168.178.1` (Fritz!Box router), not a LinkPlay device.

**Root Cause Analysis**:
- Likely in UPnP discovery or multiroom coordination
- Could be SSDP discovery picking up router's UPnP services
- Multiroom coordination might be using wrong IP
- Could be a slave device reporting master IP incorrectly

**Code Location**:
- `custom_components/wiim/upnp_client.py` (UPnP discovery)
- `custom_components/wiim/upnp_eventer.py` (UPnP eventing)
- `custom_components/wiim/coordinator_multiroom.py` (multiroom coordination)
- `custom_components/wiim/config_flow.py` (device discovery)

**Potential Fix**:
- Filter out router IPs during discovery (check for common router IPs)
- Validate discovered devices are actually LinkPlay devices before adding
- Add logging to track where router IP is coming from
- Check multiroom slave/master IP resolution

---

## Recommended Next Steps

1. **Split into separate GitHub issues** - One issue per problem for better tracking
2. **Add enhanced logging** - Log raw API responses when volume/state/source are missing
3. **Test with DLNA source** - Need to see what fields DLNA actually returns
4. **Check grouped speaker behavior** - Verify state propagation from master to slaves
5. **Investigate router IP** - Add logging to trace where 192.168.178.1 is coming from

## Debugging Commands for User

Ask user to enable debug logging and check:
```yaml
logger:
  default: info
  logs:
    custom_components.wiim: debug
    custom_components.wiim.api_parser: debug
    custom_components.wiim.data: debug
    custom_components.wiim.coordinator_polling: debug
```

Then check logs for:
- Raw API responses when volume/state/source are missing
- Any attempts to connect to 192.168.178.1
- Multiroom coordination messages
- UPnP discovery events

