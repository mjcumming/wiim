# WiiM vs LinkPlay API Compatibility Guide

> **Purpose**: Document critical differences between WiiM and LinkPlay HTTP APIs, known limitations, and defensive programming strategies.

---

## 🚨 **Critical Understanding**

WiiM devices use **enhanced LinkPlay firmware** with additional endpoints and capabilities. However:

- **Pure LinkPlay devices** (Arylic, etc.) may lack WiiM-specific enhancements
- **Endpoint availability varies significantly** across manufacturers and firmware versions
- **Our integration must work universally** across the entire LinkPlay ecosystem

---

## 📚 **API Documentation Sources**

| Source                                                                                            | Coverage                   | Reliability                    |
| ------------------------------------------------------------------------------------------------- | -------------------------- | ------------------------------ |
| **[WiiM API Documentation](https://www.wiimhome.com/pdf/HTTP%20API%20for%20WiiM%20Products.pdf)** | WiiM-specific enhancements | ✅ Accurate for WiiM devices   |
| **[Arylic LinkPlay API](https://developer.arylic.com/httpapi/#multiroom-multizone)**              | Core LinkPlay protocol     | ✅ Universal LinkPlay baseline |

---

## ⚡ **Endpoint Reliability Matrix**

### **✅ UNIVERSAL ENDPOINTS (Always Available)**

These endpoints work on **all LinkPlay devices** and should be the foundation of our integration:

| Endpoint                  | Purpose             | Response                                    | Notes                                |
| ------------------------- | ------------------- | ------------------------------------------- | ------------------------------------ |
| **`getPlayerStatus`**     | Core playback state | JSON with play/pause/stop, volume, position | **Most critical - always poll this** |
| **`wlanGetConnectState`** | WiFi connection     | Plain text: OK/FAIL/PROCESS                 | **Network diagnostics**              |

### **⚠️ WiiM-ENHANCED ENDPOINTS (Probe Required)**

These endpoints are **WiiM-specific enhancements** that may not exist on pure LinkPlay devices:

| Endpoint                    | WiiM Enhancement            | LinkPlay Fallback              | Probe Strategy                        |
| --------------------------- | --------------------------- | ------------------------------ | ------------------------------------- |
| **`getStatusEx`**           | Rich device/group info      | Use basic `getStatus`          | Try once, remember result             |
| **`getMetaInfo`**           | Track metadata with artwork | Extract from `getPlayerStatus` | Critical - many devices don't support |
| **`EQLoad`/`EQOn`/`EQOff`** | Equalizer controls          | None - feature missing         | Disable EQ UI if unsupported          |

### **❌ HIGHLY INCONSISTENT ENDPOINTS (Use Carefully)**

These endpoints have **significant variability** across LinkPlay implementations:

| Endpoint               | Issue                                          | Our Strategy                            |
| ---------------------- | ---------------------------------------------- | --------------------------------------- |
| **`getStatus`**        | **DOESN'T WORK on WiiM devices!**              | Pure LinkPlay only - never rely on this |
| **EQ endpoints**       | Some devices have no EQ support at all         | Probe on startup, disable if missing    |
| **`getMetaInfo`**      | Missing on many older LinkPlay devices         | Always have fallback metadata           |
| **Multiroom commands** | Different implementations across manufacturers | Use WiiM method, fallback to LinkPlay   |

**🚨 CRITICAL**: `getStatus` (basic LinkPlay endpoint) **does not work** on WiiM devices. This means:

- **WiiM devices**: Must use `getStatusEx` for device info
- **Pure LinkPlay devices**: Can use `getStatus` as fallback when `getStatusEx` fails
- **Never assume** `getStatus` works universally

---

## 🛡️ **Defensive Programming Patterns**

### **1. Capability Probing**

Always test endpoint availability on first connection:

```python
class WiiMClient:
    def __init__(self):
        # Capability flags - None means untested
        self._statusex_supported: bool | None = None
        self._metadata_supported: bool | None = None
        self._eq_supported: bool | None = None

    async def probe_capabilities(self):
        """Test endpoint support once on initial connection"""

        # Test WiiM-enhanced device info
        try:
            await self._get_status_ex()
            self._statusex_supported = True
        except WiiMError:
            self._statusex_supported = False
            logger.info("Device uses basic LinkPlay API (no getStatusEx)")

        # Test metadata support (critical!)
        try:
            await self._get_meta_info()
            self._metadata_supported = True
        except WiiMError:
            self._metadata_supported = False
            logger.warning("Device doesn't support getMetaInfo - no track artwork")

        # Test EQ support
        try:
            await self._get_eq_status()
            self._eq_supported = True
        except WiiMError:
            self._eq_supported = False
            logger.info("Device has no EQ support")
```

### **2. Graceful Fallbacks**

Always have fallbacks for unreliable endpoints:

```python
async def get_device_info(self) -> dict:
    """Get device info with WiiM enhancement fallback"""
    if self._statusex_supported:
        try:
            return await self._get_status_ex()
        except WiiMError:
            self._statusex_supported = False  # Remember failure

    # Fallback to basic LinkPlay
    return await self._get_status()

async def get_track_metadata(self) -> dict:
    """Get track metadata with basic info fallback"""
    if self._metadata_supported:
        try:
            result = await self._get_meta_info()
            if result and result.get("metaData"):
                return result["metaData"]
        except WiiMError:
            self._metadata_supported = False  # Disable forever

    # Fallback: Extract from basic player status
    status = await self.get_player_status()
    return {
        "title": status.get("title", "Unknown Track"),
        "artist": status.get("artist", "Unknown Artist"),
        "album": status.get("album", ""),
        # Note: No artwork available in basic status
    }
```

### **3. Never Fail Hard**

Missing advanced features shouldn't break core functionality:

```python
async def update_eq_status(self):
    """Update EQ status only if device supports it"""
    if not self._eq_supported:
        return None  # Silently skip - device has no EQ

    try:
        return await self._get_eq_status()
    except WiiMError:
        self._eq_supported = False  # Disable permanently
        logger.warning("EQ support disabled - device doesn't support EQ endpoints")
        return None
```

---

## 🔍 **Known Device Variations**

### **WiiM Devices**

- ✅ **Full API support** - All endpoints should work
- ✅ **getStatusEx** - Enhanced device info
- ✅ **getMetaInfo** - Rich track metadata with artwork
- ⚠️ **EQ support** - Varies by model (Pro vs Mini)

### **Pure LinkPlay Devices (Arylic, etc.)**

- ✅ **Basic endpoints** - getPlayerStatus, getStatus always work
- ❌ **No getStatusEx** - Use basic getStatus instead
- ❌ **No getMetaInfo** - Extract metadata from getPlayerStatus
- ❌ **Variable EQ** - Many devices have no EQ at all

### **Third-Party LinkPlay**

- ⚠️ **Unpredictable** - Each manufacturer may customize differently
- ✅ **Basic playback** - Core functions usually work
- ❌ **Advanced features** - Often missing or non-standard

---

## 📋 **Integration Requirements**

### **Must Support**

1. **Universal playback control** (play/pause/stop/volume)
2. **Basic device identification** (name, IP, MAC)
3. **Group management** using core LinkPlay commands
4. **Graceful degradation** when advanced features missing

### **Should Support (With Fallbacks)**

1. **Rich metadata** (when getMetaInfo available)
2. **Enhanced device info** (when getStatusEx available)
3. **EQ controls** (when device supports it)

### **Must Not Require**

1. **WiiM-specific endpoints** for core functionality
2. **EQ support** for basic operation
3. **Advanced metadata** for music playback

---

## 🧪 **Testing Strategy**

### **Device Testing Matrix**

| Device Type              | Test Focus                                          |
| ------------------------ | --------------------------------------------------- |
| **WiiM Pro/Mini**        | Full feature testing - all endpoints should work    |
| **Arylic devices**       | Basic LinkPlay functionality + graceful degradation |
| **Third-party LinkPlay** | Core playback + probe all enhanced features         |

### **Critical Test Scenarios**

1. **Metadata Fallback**: Verify graceful handling when getMetaInfo fails
2. **EQ Degradation**: Ensure integration works when EQ endpoints missing
3. **Basic LinkPlay**: Test with pure LinkPlay device (no WiiM enhancements)
4. **Connection Errors**: Verify probe failures don't break startup

---

## 🚨 **Implementation Warnings**

### **DO NOT**

- ❌ **Assume getMetaInfo works** - many devices don't support it
- ❌ **Require EQ endpoints** - often missing entirely
- ❌ **Use only WiiM API docs** - covers enhanced features only
- ❌ **Fail hard on missing features** - always have fallbacks

### **DO**

- ✅ **Probe capabilities once** - remember results permanently
- ✅ **Use getPlayerStatus as foundation** - universally supported
- ✅ **Implement graceful fallbacks** - for all enhanced features
- ✅ **Log missing capabilities** - for user troubleshooting

---

## 🔍 **Real-World Examples from Our Codebase**

### **EQ Status Detection - Already Implemented Defensively**

Our current `api.py` already handles EQ inconsistencies with sophisticated fallback logic:

```python
async def get_eq_status(self) -> bool:
    """Return *True* if the device reports that EQ is enabled.

    Not all firmware builds implement ``EQGetStat`` – many return the
    generic ``{"status":"Failed"}`` payload instead.  In that case we
    fall back to calling ``getEQ``: if the speaker answers *anything*
    other than *unknown command* we assume that EQ support is present
    and therefore enabled.
    """

    try:
        response = await self._request(API_ENDPOINT_EQ_STATUS)

        # Normal, spec-compliant reply → {"EQStat":"On"|"Off"}
        if "EQStat" in response:
            return str(response["EQStat"]).lower() == "on"

        # Some firmwares return {"status":"Failed"} for unsupported
        # commands – treat this as *unknown* and use a heuristic.
        if str(response.get("status", "")).lower() == "failed":
            # If /getEQ succeeds we take that as evidence that the EQ
            # subsystem is operational which implies it is *enabled*.
            try:
                await self._request(API_ENDPOINT_EQ_GET)
                return True
            except WiiMError:
                return False

        # Fallback – any other structure counts as EQ disabled.
        return False

    except WiiMError:
        # On explicit request errors assume EQ disabled so callers can
        # still proceed without raising.
        return False
```

**This demonstrates perfect defensive programming**:

1. Try the proper `EQGetStat` endpoint first
2. Handle `{"status":"Failed"}` as "maybe supported"
3. Use `getEQ` as a detection heuristic
4. Never fail hard - always return a reasonable default

### **Metadata Fallback - getMetaInfo Issues**

Our `get_meta_info()` method already handles devices that don't support enhanced metadata:

```python
async def get_meta_info(self) -> dict[str, Any]:
    """Get current track metadata including album art."""
    try:
        response = await self._request("/httpapi.asp?command=getMetaInfo")
        return response.get("metaData", {})
    except Exception as e:
        # Devices with older firmware return plain "OK" instead of JSON.
        # Treat this as an expected condition rather than an error.
        _LOGGER.debug("get_meta_info not supported on %s: %s", self.host, e)
        return {}
```

**This shows exactly what you mentioned**:

- `getMetaInfo` is **inconsistent across devices**
- Some return `"OK"` instead of JSON
- We treat this as **expected**, not an error
- Graceful fallback to empty metadata

### **Protocol Detection - HTTP vs HTTPS**

Our `_request()` method tries multiple protocols automatically:

```python
# Try protocols in python-linkplay order: HTTPS first, then HTTP fallback
protocols_to_try = [
    ("https", 443, self._get_ssl_context()),  # HTTPS primary
    ("https", 4443, self._get_ssl_context()),  # HTTPS alternate port
    ("http", 80, None),  # HTTP fallback
]
```

**This handles LinkPlay device variations**:

- Some devices use HTTPS with self-signed certificates
- Others use HTTP only
- Port variations across manufacturers
- Automatic fallback without user intervention

---

This compatibility guide ensures our integration works reliably across the entire LinkPlay ecosystem while taking advantage of WiiM enhancements when available.
