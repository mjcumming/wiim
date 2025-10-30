# UPnP Eventing Testing Guide

## Overview

This document describes how to test whether WiiM devices properly support UPnP DLNA DMR eventing and how to diagnose UPnP-related issues.

## Background

WiiM/LinkPlay devices advertise themselves via SSDP (Simple Service Discovery Protocol) with UPnP service types including:

- `urn:schemas-upnp-org:device:MediaRenderer:1`
- `urn:schemas-upnp-org:service:AVTransport:1`
- `urn:schemas-upnp-org:service:RenderingControl:1`

However, advertising these services doesn't guarantee proper UPnP eventing support. This testing guide helps verify actual functionality.

## Testing Process

### Phase 1: Verify description.xml Accessibility

WiiM devices should respond to UPnP description requests on **port 49152**:

```bash
curl http://192.168.1.68:49152/description.xml
```

**Expected**: XML document describing device and services
**If fails**: Device may not support UPnP properly

### Phase 2: Use Diagnostic Script

We provide a comprehensive diagnostic script that tests all aspects of UPnP support:

```bash
cd /workspaces/wiim
python scripts/test_upnp_description.py 192.168.1.68
```

**The script tests:**

1. Whether `description.xml` is accessible
2. Whether the XML can be parsed by `async_upnp_client`
3. Whether AVTransport service is advertised
4. Whether RenderingControl service is advertised
5. Overall UPnP eventing support assessment

**Example successful output:**

```
======================================================
Testing UPnP Support for WiiM Device: 192.168.1.68
======================================================

[1] Fetching description.xml from http://192.168.1.68:49152/description.xml...
    ✅ Successfully fetched description.xml (2847 bytes)

[2] Parsing UPnP device description...
    ✅ Successfully created UPnP device
       Device Type: urn:schemas-upnp-org:device:MediaRenderer:1
       Manufacturer: WiiM
       Model: WiiM Pro

[3] Checking for DLNA DMR services...
    → Found service: urn:upnp-org:serviceId:AVTransport
    → Found service: urn:upnp-org:serviceId:RenderingControl

    ✅ AVTransport service found
       → Required for play/pause/stop events
    ✅ RenderingControl service found
       → Required for volume/mute events

======================================================
✅ RESULT: Device SUPPORTS UPnP DLNA DMR eventing
======================================================
```

### Phase 3: Test in Home Assistant

After verifying UPnP support with the diagnostic script, test in Home Assistant:

1. **Check Logs During Integration Setup**

Look for these log messages in `/config/home-assistant.log`:

```
✅ UPnP client created successfully for Main Floor Speakers (completed in 0.45s)
✅ UPnP client initialized for 192.168.1.68: AVTransport=True, RenderingControl=True
✅ UPnP event subscriptions established for Main Floor Speakers (0.12s) - will receive real-time events
```

2. **What to Look For:**

   - ✅ Client creation completes in < 1 second
   - ✅ Both AVTransport and RenderingControl services found
   - ✅ Subscriptions establish successfully
   - ✅ No timeout errors

3. **Common Failure Patterns:**

**Timeout during description.xml fetch:**

```
❌ Timeout fetching UPnP description from http://192.168.1.68:49152/description.xml after 5 seconds
⚠️  Failed to create UPnP client for Main Floor Speakers (after 5.01s): Timeout fetching UPnP description
    - continuing with HTTP polling only
```

**Cause**: Device doesn't respond on port 49152 or network issue
**Resolution**: Device doesn't support UPnP eventing, HTTP polling will be used

**Device rejects subscription:**

```
Device Main Floor Speakers rejected UPnP subscription (0.15s): UPnP Error 412
    - will use HTTP polling instead
```

**Cause**: Device advertises services but doesn't accept SUBSCRIBE requests
**Resolution**: HTTP polling fallback works fine

**Services not found:**

```
⚠️  Device 192.168.1.68 does not advertise AVTransport service - UPnP eventing may not work
```

**Cause**: Incomplete UPnP implementation
**Resolution**: Integration will use HTTP polling

## Integration Behavior

The WiiM integration follows the **DLNA DMR pattern** where UPnP eventing is an **optimization, not a requirement**.

### Successful UPnP Setup

- Integration receives real-time events for state changes
- Faster UI updates (instant vs 1-second polling)
- Reduced network traffic

### Failed UPnP Setup (Graceful Fallback)

- Integration uses HTTP polling (1s playing, 5s idle)
- **All functionality still works perfectly**
- Slight delay in state updates (1 second max)
- Slightly more network traffic (negligible)

## Troubleshooting

### Issue: Silent Failure (No Error Messages)

**Symptoms**: Integration loads but no UPnP log messages appear

**Diagnosis**:

```python
# Check if _setup_upnp_subscriptions is being called
# Look in logs for: "📡 Initializing UPnP event subscriptions"
```

**Solutions**:

1. Check that config entry has UPnP enabled (future config option)
2. Verify device is reachable on port 49152
3. Run diagnostic script to verify UPnP support

### Issue: Timeout After 5 Seconds

**Symptoms**:

```
❌ Timeout fetching UPnP description from http://192.168.1.68:49152/description.xml after 5 seconds
```

**Common Causes**:

1. **Device doesn't support UPnP** - Some WiiM/LinkPlay devices may not implement UPnP eventing
2. **Firewall blocking port 49152** - Check network/firewall rules
3. **Device firmware too old** - Update device firmware to latest version
4. **Network congestion** - Test during low-traffic period

**Resolution**: Integration falls back to HTTP polling automatically

### Issue: Callback URL Issues (Docker/WSL)

**Symptoms**:

```
⚠️  CRITICAL: Callback URL uses Docker bridge network IP (172.x.x.x)
    - devices on your LAN CANNOT reach this for UPnP events!
```

**Cause**: Home Assistant running in Docker/WSL with bridge networking

**Solutions**:

1. **Use host networking** (recommended):

   ```yaml
   # docker-compose.yml
   network_mode: host
   ```

2. **Set callback_host in integration options**:

   - Navigate to integration settings
   - Set "UPnP Callback Host" to your LAN IP (e.g., 192.168.1.100)

3. **Accept polling fallback**: UPnP eventing won't work, HTTP polling is fine

## Decision Tree

```
Does device respond to description.xml on port 49152?
├─ NO → Device doesn't support UPnP → Use HTTP polling (works fine)
└─ YES → Can async_upnp_client parse it?
    ├─ NO → Malformed UPnP → Use HTTP polling
    └─ YES → Does it advertise AVTransport + RenderingControl?
        ├─ NO → Incomplete UPnP → Use HTTP polling
        └─ YES → Does device accept SUBSCRIBE?
            ├─ NO → Device rejects subscriptions → Use HTTP polling
            └─ YES → UPnP eventing should work!
                     └─ Are events arriving?
                        ├─ YES → ✅ UPnP working perfectly
                        └─ NO → Check callback URL reachability
                                  → Fix networking OR use HTTP polling
```

## Recommendations

### For Development

- **Always test with diagnostic script first** before debugging integration code
- **Use host networking in Docker** to avoid callback URL issues
- **Check logs carefully** - our improved error messages show exactly what failed

### For Production

- **UPnP is optional** - integration works great without it
- **HTTP polling is reliable** - 1-second updates are perfectly fine for media players
- **Don't over-engineer** - if UPnP fails, polling works

### For Users

- If you see "continuing with HTTP polling" messages, **everything is fine**
- The integration will work perfectly with 1-second state updates
- Only concern yourself with UPnP if you need sub-second real-time updates

## UPnP Eventing Approach (DLNA DMR Pattern)

The integration follows the **standard DLNA DMR pattern** from Home Assistant core - no fallback timer, just trust `auto_resubscribe=True`:

### How It Works

```python
try:
    self._device.on_event = self._on_event
    await self._device.async_subscribe_services(auto_resubscribe=True)
except UpnpResponseError as err:
    # Device rejected subscription - this is OK, will poll instead
    _LOGGER.debug("Device rejected subscription: %r", err)
except UpnpError as err:
    # Other error - clean up
    _LOGGER.debug("Error while subscribing: %r", err)
    raise
```

### Why No Fallback Timer?

**Problem**: How can you detect "callback URL unreachable" (Docker/WSL) without a timer?

**Answer**: You can't reliably:

- UPnP only generates events on state changes (play/pause, volume, track change)
- Idle device = no state changes = no events (this is **normal, not an error**)
- Any timer would have false positives if device is idle when integration starts

### For Docker/WSL Users

If callback URL is unreachable, you'll see in diagnostics:

- `event_count: 0` (no events arriving)
- `callback_url: http://172.x.x.x:xxxxx` (unreachable internal IP)

**Fix**: Configure `upnp_callback_host` in integration options with your LAN IP, or use `network_mode: host`.

### Benefits

- ✅ **Standard pattern**: Matches DLNA DMR and Samsung TV integrations exactly
- ✅ **No false positives**: Idle devices won't be flagged as broken
- ✅ **Simpler code**: Trust `async_upnp_client` to handle subscriptions and renewals
- ✅ **Clear diagnostics**: Easy to verify if UPnP is working

## Future Improvements

Potential enhancements if UPnP proves reliable:

1. **Config Option**: `upnp_events: auto | enabled | disabled` (default: auto)
2. **Statistics**: Track event arrival rate vs polling rate
3. **Automatic Fallback**: Switch to polling if events stop arriving
4. **Callback URL Auto-Detection**: Better Docker/WSL network handling

## Conclusion

WiiM devices **do advertise UPnP services** but actual UPnP eventing support varies by device model and firmware version. The integration is designed to:

1. **Try UPnP first** - Attempt subscription on startup
2. **Fail gracefully** - Fall back to HTTP polling if UPnP fails
3. **Work reliably** - HTTP polling provides excellent user experience

**Bottom line**: Whether UPnP works or not, the integration delivers a great experience.
