# UPnP Architecture Guide

**Date**: 2025-01-27
**Purpose**: Explain how the WiiM integration uses UPnP for event notifications and how it differs from HTTP API control

---

## 🎯 **Overview**

The WiiM integration uses a **hybrid approach**:

- **UPnP**: For real-time event notifications (play/pause, volume, track changes)
- **HTTP API**: For all device control and configuration

This differs from some other implementations (like [WiiM Play](https://github.com/shumatech/wiimplay)) which use UPnP for both events and transport control.

---

## 📡 **UPnP Usage: Events Only**

### **What We Use UPnP For**

✅ **Event Notifications** (via DLNA DMR pattern):

- Play/pause/stop state changes
- Volume changes
- Mute state changes
- Track metadata updates
- Position updates

❌ **What We DON'T Use UPnP For**:

- Playback control (play, pause, stop, next, previous)
- Volume control
- Source selection
- EQ settings
- Audio output mode
- Group management
- Any device configuration

**All control operations use the HTTP API** (`/httpapi.asp?command=...`)

---

## 🏗️ **Architecture**

### **UPnP Event Flow**

```
Device State Change (play/pause/volume)
    ↓
UPnP Service (AVTransport/RenderingControl)
    ↓
UPnP Event Notification (via callback URL)
    ↓
UpnpEventer receives event
    ↓
Merges event state into coordinator
    ↓
Home Assistant entity updates
```

### **HTTP API Control Flow**

```
User Action (play/pause/volume)
    ↓
Media Controller sends HTTP API command
    ↓
Device executes command
    ↓
UPnP event notification (if UPnP working)
    OR
HTTP polling detects change (if UPnP not working)
    ↓
Coordinator updates state
    ↓
Home Assistant entity updates
```

---

## 🔄 **Why This Hybrid Approach?**

### **Advantages**

1. **Reliability**: HTTP API is always available, even if UPnP fails
2. **Consistency**: All control uses same API, regardless of UPnP status
3. **Simplicity**: Single control path (HTTP API) is easier to maintain
4. **Feature Completeness**: HTTP API supports all WiiM-specific features (EQ, audio output, groups, etc.)
5. **Graceful Degradation**: If UPnP fails, HTTP polling works perfectly

### **Comparison with WiiM Play**

**WiiM Play Approach:**

- UPnP for transport control (play/pause/seek/volume)
- HTTP API for device-specific features (EQ, audio output, balance, fade)

**Our Approach:**

- UPnP for events only (notifications)
- HTTP API for everything (control + device features)

**Why We Chose This:**

- Home Assistant pattern: Most integrations use HTTP API for control
- Simpler codebase: One control path instead of two
- Better error handling: HTTP API errors are easier to handle than UPnP SOAP errors
- Feature parity: HTTP API supports everything, UPnP doesn't (no EQ, no groups, etc.)

---

## 📚 **Implementation Details**

### **UPnP Client Setup**

Following the **DLNA DMR pattern** (same as Samsung TV and DLNA DMR integrations):

```python
# From upnp_client.py
class UpnpClient:
    """UPnP client wrapper using async-upnp-client DmrDevice pattern."""

    async def _initialize(self):
        # Create UPnP device from description.xml
        factory = UpnpFactory(requester, non_strict=True)
        device = await factory.async_create_device(self.description_url)

        # Create DmrDevice wrapper for subscriptions
        self._dmr_device = DmrDevice(device, event_handler)

        # Get services
        self._av_transport_service = device.service("urn:schemas-upnp-org:service:AVTransport:1")
        self._rendering_control_service = device.service("urn:schemas-upnp-org:service:RenderingControl:1")
```

### **Event Subscription**

```python
# From data.py _setup_upnp_subscriptions()
try:
    self._device.on_event = self._on_event
    await self._device.async_subscribe_services(auto_resubscribe=True)
except UpnpResponseError as err:
    # Device rejected subscription - fall back to HTTP polling
    _LOGGER.debug("Device rejected subscription: %r", err)
```

### **Event Handling**

```python
# From upnp_eventer.py
class UpnpEventer:
    """Handles UPnP events and merges into coordinator state."""

    def _on_event(self, service, state_variables):
        # Parse UPnP event state variables
        # Merge into coordinator state
        # Trigger entity update
```

### **State Merging**

Events are merged into the coordinator's state, which is then used by HTTP polling as the source of truth:

```python
# From data.py
def _merge_upnp_state_to_coordinator(self):
    """Merge UPnP event state into coordinator."""
    if self._upnp_eventer and self._upnp_eventer.last_state:
        # Merge UPnP state into coordinator
        # HTTP polling will use this as baseline
```

---

## 🔍 **UPnP Services Used**

### **AVTransport Service**

**Purpose**: Transport state events (play/pause/stop, track changes)

**Events We Listen To:**

- `TransportState` - Current playback state
- `CurrentTrackMetaData` - Track metadata
- `CurrentTrack` - Current track number
- `CurrentTrackDuration` - Track duration
- `RelativeTimePosition` - Current position

**We DON'T Use:**

- `Play()` - We use HTTP API `setPlayerCmd:play`
- `Pause()` - We use HTTP API `setPlayerCmd:pause`
- `Stop()` - We use HTTP API `setPlayerCmd:stop`
- `Seek()` - We use HTTP API `setPlayerCmd:seek`

### **RenderingControl Service**

**Purpose**: Volume and mute events

**Events We Listen To:**

- `Volume` - Current volume level
- `Mute` - Mute state

**We DON'T Use:**

- `SetVolume()` - We use HTTP API `setPlayerCmd:vol:<level>`
- `SetMute()` - We use HTTP API `setPlayerCmd:mute:<state>`

---

## ⚙️ **Configuration**

### **UPnP Discovery**

UPnP devices are discovered via SSDP (Simple Service Discovery Protocol):

```python
# From config_flow.py
# SSDP discovery provides:
ssdp_info = {
    "location": "http://192.168.1.68:49152/description.xml",
    "st": "urn:schemas-upnp-org:device:MediaRenderer:1",
    "usn": "uuid:FF31F09E-1A50-2011-3B0A-3918FF31F09E",
}
```

### **Description URL**

WiiM devices serve UPnP description on **port 49152** (HTTP, not HTTPS):

```
http://<device_ip>:49152/description.xml
```

### **Callback URL**

UPnP events are delivered to a callback URL on Home Assistant:

```
http://<ha_ip>:<random_port>/notify/<subscription_id>
```

**Important**: The callback URL must be reachable from the device's network. This can be problematic in Docker/WSL environments (see `DOCKER_NETWORKING.md`).

---

## 🛡️ **Fallback Strategy**

### **Graceful Degradation**

If UPnP fails at any stage, the integration falls back to HTTP polling:

1. **Description fetch fails** → HTTP polling
2. **Service not found** → HTTP polling
3. **Subscription rejected** → HTTP polling
4. **Events not arriving** → HTTP polling (but no way to detect this reliably)

### **HTTP Polling Fallback**

When UPnP is unavailable:

- **Playing state**: Poll every 1 second
- **Idle state**: Poll every 5 seconds
- **All functionality works perfectly**

This is the same polling strategy used when UPnP is working (UPnP events supplement polling, don't replace it).

---

## 📊 **Benefits of Our Approach**

### **1. Reliability**

- ✅ HTTP API always works (even if UPnP fails)
- ✅ Graceful fallback to polling
- ✅ No single point of failure

### **2. Simplicity**

- ✅ Single control path (HTTP API)
- ✅ Consistent error handling
- ✅ Easier to debug

### **3. Feature Completeness**

- ✅ All WiiM features available via HTTP API
- ✅ UPnP doesn't support EQ, groups, audio output, etc.
- ✅ No need to mix UPnP and HTTP for different features

### **4. Performance**

- ✅ UPnP events provide instant updates (when working)
- ✅ HTTP polling provides reliable updates (always working)
- ✅ Best of both worlds

---

## 🔗 **Related Documentation**

- **[UPNP_TESTING.md](UPNP_TESTING.md)** - Testing and troubleshooting UPnP support
- **[DOCKER_NETWORKING.md](DOCKER_NETWORKING.md)** - Docker/WSL networking for UPnP
- **[API_GUIDE.md](API_GUIDE.md)** - HTTP API reference (used for all control)
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Overall integration architecture

---

## 🎓 **Key Takeaways**

1. **UPnP is for events, not control** - We use HTTP API for all control operations
2. **Hybrid approach** - UPnP provides real-time events, HTTP API provides control
3. **Graceful fallback** - If UPnP fails, HTTP polling works perfectly
4. **DLNA DMR pattern** - We follow the same pattern as Samsung TV and DLNA DMR integrations
5. **Optional optimization** - UPnP is nice-to-have, not required for functionality

---

## 🔮 **Future Considerations**

Potential enhancements:

1. **Config Option**: Allow users to disable UPnP if causing issues
2. **Statistics**: Track event arrival rate vs polling rate
3. **Automatic Fallback**: Detect when events stop arriving and switch to polling
4. **Better Diagnostics**: More detailed UPnP health metrics

But remember: **UPnP is an optimization, not a requirement**. The integration works great with HTTP polling alone.
