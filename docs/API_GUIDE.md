# WiiM/LinkPlay API Integration Guide

> **Purpose**: Document API compatibility, critical differences, group management commands, and defensive programming strategies for WiiM/LinkPlay devices.

---

## 📚 **API Documentation Sources**

**Official Documentation**: [Arylic LinkPlay API](https://developer.arylic.com/httpapi/)

| Source                                                                              | Coverage                   | Notes                       |
| ----------------------------------------------------------------------------------- | -------------------------- | --------------------------- |
| [WiiM API PDF](https://www.wiimhome.com/pdf/HTTP%20API%20for%20WiiM%20Products.pdf) | WiiM-specific enhancements | Accurate for WiiM devices   |
| [Arylic LinkPlay API](https://developer.arylic.com/httpapi/)                        | Core LinkPlay protocol     | Universal LinkPlay baseline |

---

## ⚡ **API Reliability Matrix**

### **✅ UNIVERSAL ENDPOINTS (Always Available)**

These endpoints work on **all LinkPlay devices** and form the foundation of our integration:

| Endpoint                  | Purpose             | Response                                    | Critical Notes                       |
| ------------------------- | ------------------- | ------------------------------------------- | ------------------------------------ |
| **`getPlayerStatus`**     | Core playback state | JSON with play/pause/stop, volume, position | **Most critical - always poll this** |
| **`wlanGetConnectState`** | WiFi connection     | Plain text: OK/FAIL/PROCESS                 | Network diagnostics                  |

### **⚠️ WiiM-ENHANCED ENDPOINTS (Probe Required)**

These endpoints are **WiiM-specific enhancements** that may not exist on pure LinkPlay devices:

| Endpoint          | WiiM Enhancement            | LinkPlay Fallback              | Probe Strategy                            |
| ----------------- | --------------------------- | ------------------------------ | ----------------------------------------- |
| **`getStatusEx`** | Rich device/group info      | Use basic `getStatus`          | Try once, remember result                 |
| **`getMetaInfo`** | Track metadata with artwork | Extract from `getPlayerStatus` | **Critical - many devices don't support** |
| **EQ endpoints**  | Equalizer controls          | None - feature missing         | Disable EQ UI if unsupported              |

### **❌ HIGHLY INCONSISTENT ENDPOINTS (Use Carefully)**

| Endpoint          | Issue                                  | Our Strategy                            |
| ----------------- | -------------------------------------- | --------------------------------------- |
| **`getStatus`**   | **DOESN'T WORK on WiiM devices!**      | Pure LinkPlay only - never rely on this |
| **EQ endpoints**  | Some devices have no EQ support at all | Probe on startup, disable if missing    |
| **`getMetaInfo`** | Missing on many older LinkPlay devices | Always have fallback metadata           |

**🚨 CRITICAL**: `getStatus` (basic LinkPlay endpoint) **does not work** on WiiM devices!

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

        # Test metadata support (critical!)
        try:
            await self._get_meta_info()
            self._metadata_supported = True
        except WiiMError:
            self._metadata_supported = False
            logger.warning("Device doesn't support getMetaInfo - no track artwork")
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

## 🎯 **LinkPlay Group Management API**

### **Essential Group Commands**

#### **Join Group Command**

```
ConnectMasterAp:JoinGroupMaster:<master_ip>:wifi0.0.0.0
```

- **Purpose**: Makes a device join another device's group as a slave
- **Target**: Send to the slave device's IP
- **Parameters**: `<master_ip>` - IP address of the master device

#### **Leave Group Command**

```
multiroom:SlaveKickout:<slave_ip>
```

- **Purpose**: Removes a slave from the group
- **Target**: Send to the master device's IP
- **Parameters**: `<slave_ip>` - IP address of slave to remove

#### **Ungroup Command**

```
multiroom:Ungroup
```

- **Purpose**: Disbands the entire group
- **Target**: Send to the master device's IP

### **Group Status Detection**

#### **Device Role from getStatusEx**

```json
{
  "group": "0", // Solo or Master
  "group": "1", // Slave
  "master_uuid": "...", // Present when slave
  "uuid": "..." // Device UUID
}
```

#### **Master's Slaves from getSlaveList**

```json
{
  "slaves": 2,
  "slave_list": [
    { "uuid": "slave1", "ip": "192.168.1.101", "name": "Kitchen" },
    { "uuid": "slave2", "ip": "192.168.1.102", "name": "Bedroom" }
  ]
}
```

### **Group Implementation Strategy**

#### **Group Role Logic**

1. **Slave**: `group == "1"` and has `master_uuid`
2. **Master**: `group == "0"` and `getSlaveList` shows slaves
3. **Solo**: `group == "0"` and no slaves

#### **Group Join Process**

```python
async def async_join_group(self, speakers: list[Speaker]) -> None:
    """Join multiple speakers into a group."""
    master = self  # This speaker becomes master
    slaves = speakers

    # API calls to create group
    for slave in slaves:
        await slave.coordinator.client.join_master(master.ip)

    # Update local state
    master.role = "master"
    master.group_members = [master] + slaves

    for slave in slaves:
        slave.role = "slave"
        slave.coordinator_speaker = master
        slave.group_members = [master] + slaves

    # Notify all entities
    for speaker in [master] + slaves:
        speaker.async_write_entity_states()
```

---

## 🔍 **Device Variations & Compatibility**

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

This API guide ensures our integration works reliably across the entire LinkPlay ecosystem while taking advantage of WiiM enhancements when available.
