# WiiM/LinkPlay API Integration Guide

> **Purpose**: Complete technical reference for WiiM/LinkPlay devices covering API compatibility, implementation details, defensive programming, testing strategies, and production deployment.

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

### **1. Capability Probing Implementation**

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

### **2. Graceful Fallbacks Implementation**

Always have fallbacks for unreliable endpoints:

```python
async def get_device_info(self) -> dict:
    """Get device info with WiiM enhancement fallback"""
    if self._statusex_supported:
        try:
            return await self._request(API_ENDPOINT_STATUS)
        except WiiMError:
            self._statusex_supported = False  # Remember failure

    # Fallback to basic LinkPlay
    return await self._request(API_ENDPOINT_PLAYER_STATUS)

async def get_track_metadata(self) -> dict:
    """Get track metadata with basic info fallback"""
    if self._metadata_supported:
        try:
            result = await self._request("/httpapi.asp?command=getMetaInfo")
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

### **3. Never Fail Hard Implementation**

Missing advanced features shouldn't break core functionality:

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
        # On explicit request error, still proceed without raising.
        return False
```

---

## 🎯 **LinkPlay Group Management API**

### **Essential Group Commands**

#### **Create Master Command**

```
setMultiroom:Master
```

- **Purpose**: Makes the current device a multiroom master
- **Target**: Send to the device that should become master

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

- **Purpose**: Disbands the entire group or leaves current group
- **Target**: Send to any device in the group

**NOTE**: The group join command for slaves is not currently known/implemented.
The ConnectMasterAp commands are for WiFi access point connections, not multiroom grouping.

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

**CORRECT API FORMAT (Fixed in v2.1.0):**

```json
{
  "slaves": 1, // Integer count (always present)
  "wmrm_version": "4.2",
  "slave_list": [
    // Array of slave objects (when slaves > 0)
    {
      "name": "Master Bedroom",
      "uuid": "FF31F09EFFF1D2BB4FDE2B3F",
      "ip": "192.168.1.116",
      "version": "4.2",
      "type": "WiiMu-A31",
      "channel": 0,
      "volume": 63,
      "mute": 0,
      "battery_percent": 0,
      "battery_charging": 0
    }
  ]
}
```

**Response when no slaves (standalone mode):**

```json
{
  "slaves": 0,
  "wmrm_version": "4.2"
}
```

**CRITICAL PARSING FIX:**

- Prior to v2.1.0, our integration incorrectly expected `slaves` to sometimes be a list
- This caused the infamous "SLAVE LIST ISSUE: reports N slaves but slaves field is integer" error
- **Fixed**: `slaves` is always an integer count, `slave_list` contains the actual slave objects
- **Impact**: Multiroom group detection now works reliably

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

    # Create group on master first
    await master.coordinator.client.create_group()

    # NOTE: Slave join commands are not implemented yet
    # The ConnectMasterAp command is for WiFi, not multiroom grouping
    raise NotImplementedError("Multiroom join commands not implemented yet")

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

- ✅ **Basic endpoints** - getPlayerStatus, basic status always work
- ❌ **No getStatusEx** - Use basic status instead
- ❌ **No getMetaInfo** - Extract metadata from getPlayerStatus
- ❌ **Variable EQ** - Many devices have no EQ at all

### **Third-Party LinkPlay**

- ⚠️ **Unpredictable** - Each manufacturer may customize differently
- ✅ **Basic playback** - Core functions usually work
- ❌ **Advanced features** - Often missing or non-standard

---

## 🧪 **Testing & Build Strategy**

### **Testing Infrastructure**

Our testing uses a phased approach with comprehensive coverage:

```python
# tests/run_tests.py - Main test runner
def run_all_tests(verbose: bool = False) -> bool:
    """Run all tests with proper error handling."""
    results = []

    # Phase 1: Unit tests
    results.append(("Unit Tests", run_unit_tests(verbose)))

    # Phase 2: Integration tests
    results.append(("Integration Tests", run_integration_tests(verbose)))

    # Phase 3: Linting
    results.append(("Linting", run_linting()))

    return all(result for _, result in results)
```

### **Critical Test Areas**

1. **Metadata Fallback**: Verify graceful handling when getMetaInfo fails
2. **EQ Degradation**: Ensure integration works when EQ endpoints missing
3. **Basic LinkPlay**: Test with pure LinkPlay device (no WiiM enhancements)
4. **Connection Errors**: Verify probe failures don't break startup

### **Linting & Code Quality**

We maintain strict code quality standards:

```bash
# Fixed linting issues in our build:
python -m ruff check custom_components/wiim/ --fix --unsafe-fixes

# Common issues we resolved:
# - F401: Unused imports (removed CONF_ENABLE_DIAGNOSTIC_ENTITIES)
# - UP031: Format specifiers (converted % formatting to f-strings)
# - B904: Exception chaining (added 'from err' to raise statements)
```

### **Build Process**

```bash
# Complete build pipeline
make clean          # Clean artifacts
make check-all      # Run all quality checks
make build          # Build integration package
make release        # Full release build
```

---

## 🚀 **Production Implementation Details**

### **API Client Implementation**

#### **Connection Handling**

```python
async def _request(self, endpoint: str, method: str = "GET", **kwargs) -> dict:
    """Make request with smart protocol detection and SSL handling."""
    protocols = ["https", "http"]  # Try HTTPS first (WiiM requirement)
    ports = [443, 80, 8080]

    for protocol in protocols:
        for port in ports:
            try:
                # Create SSL context that accepts self-signed certs
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                connector = aiohttp.TCPConnector(ssl=ssl_context)

                async with self._session.get(
                    f"{protocol}://{self.host}:{port}{endpoint}",
                    timeout=self._timeout,
                    connector=connector
                ) as response:
                    return await response.json()

            except Exception:
                continue  # Try next protocol/port combination
```

#### **Status Parsing**

```python
def _parse_player_status(self, raw: dict[str, Any]) -> dict[str, Any]:
    """Parse raw status with comprehensive field mapping."""
    data = {}

    # Map raw keys to normalized keys
    for k, v in raw.items():
        key = self._STATUS_MAP.get(k, k)
        data[key] = v

    # Decode hex-encoded metadata
    data["title"] = _hex_to_str(raw.get("Title")) or raw.get("title")
    data["artist"] = _hex_to_str(raw.get("Artist")) or raw.get("artist")
    data["album"] = _hex_to_str(raw.get("Album")) or raw.get("album")

    # Volume normalization (0-1 float)
    if (vol := raw.get("vol")) is not None:
        try:
            vol_int = int(vol)
            data["volume_level"] = vol_int / 100
            data["volume"] = vol_int
        except ValueError:
            _LOGGER.warning("Invalid volume value: %s", vol)

    # Convert mute state to boolean
    if "mute" in data:
        try:
            data["mute"] = bool(int(data["mute"]))
        except (TypeError, ValueError):
            data["mute"] = bool(data["mute"])

    return data
```

### **Coordinator Implementation**

#### **Defensive Data Fetching**

```python
async def _async_update_data(self) -> dict[str, Any]:
    """Fetch all device data with defensive error handling."""
    data = {"status": {}, "multiroom": {}, "metadata": {}, "eq": {}}

    # Core status (always required)
    try:
        data["status"] = await self.client.get_player_status()
    except Exception as err:
        _LOGGER.error("Failed to get player status: %s", err)
        raise UpdateFailed(f"Failed to get player status: {err}") from err

    # Enhanced info (defensive)
    try:
        if self._statusex_supported is not False:
            device_info = await self.client.get_device_info()
            if device_info:
                data["status"].update(device_info)
                if self._statusex_supported is None:
                    self._statusex_supported = True
    except Exception:
        if self._statusex_supported is None:
            self._statusex_supported = False
            _LOGGER.info("Device doesn't support getStatusEx")

    # Multiroom info (defensive)
    data["multiroom"] = await self._get_multiroom_info_defensive()

    # Track metadata (defensive)
    data["metadata"] = await self._get_track_metadata_defensive()

    # EQ info (defensive)
    data["eq"] = await self._get_eq_info_defensive()

    return data
```

### **Media Controller Architecture**

We use a controller pattern to handle complex media player logic:

```python
class MediaPlayerController:
    """Single controller handling ALL media player complexity."""

    async def set_volume(self, volume: float) -> None:
        """Set volume with master/slave logic."""
        try:
            # Implement master/slave logic
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                # Slave should control master volume
                await self.speaker.coordinator_speaker.coordinator.client.set_volume(volume)
            else:
                # Master or solo speaker controls directly
                await self.speaker.coordinator.client.set_volume(volume)
        except Exception as err:
            raise HomeAssistantError(f"Failed to set volume: {err}") from err
```

---

## 📋 **Integration Requirements & Best Practices**

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

## 🔧 **Development Workflow**

### **Setup & Dependencies**

```bash
# Install development dependencies
pip install -r requirements_test.txt

# Setup pre-commit hooks
pre-commit install

# Run development setup
./setup-dev.sh
```

### **Testing Commands**

```bash
# Run all tests
python tests/run_tests.py

# Run specific test types
python tests/run_tests.py --unit
python tests/run_tests.py --integration
python tests/run_tests.py --lint

# Run specific test file
python tests/run_tests.py --file tests/unit/test_data.py
```

### **Build Commands**

```bash
# Quick development check
make dev-check

# Full release build
make release

# Show project statistics
make stats
```

---

## 🎵 **Multiroom Group Controls**

### **Group Volume & Mute Entities**

We provide dedicated entities for synchronized group control that solve the primary multiroom UX challenges:

#### **Group Volume Control** (Number Platform)

- **Entity Type**: `number` (slider)
- **Availability**: Only when speaker is group master with active members
- **Behavior**: Sets volume on all group members simultaneously
- **Error Handling**: Continues if individual speakers fail, logs partial failures
- **Dynamic Naming**: Shows group composition (e.g., "Main Floor + Kitchen Group Volume")

#### **Group Mute Control** (Switch Platform)

- **Entity Type**: `switch` (toggle)
- **Availability**: Only when speaker is group master with active members
- **Behavior**: Mutes/unmutes all group members simultaneously
- **Coordination**: Uses `asyncio.gather()` for parallel execution across all speakers

### **Implementation Architecture**

#### **Entity Lifecycle Management**

```python
# Entities start hidden and become available based on group state
_attr_entity_registry_enabled_default = False

@property
def available(self) -> bool:
    """Only available when speaker is master with active group members."""
    return (
        self.speaker.available
        and self.speaker.role == "master"
        and len(self.speaker.group_members) > 0
    )
```

#### **Synchronized Group Operations**

```python
async def async_set_native_value(self, value: float) -> None:
    """Set volume for entire group simultaneously."""
    tasks = []

    # Master volume
    tasks.append(self._set_speaker_volume(self.speaker, value, "master"))

    # Slave volumes
    for slave in self.speaker.group_members:
        if slave != self.speaker:
            tasks.append(self._set_speaker_volume(slave, value, "slave"))

    # Execute all changes simultaneously
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

### **User Experience Benefits**

✅ **Solves Primary UX Problem**: Easy group volume control without entity confusion
✅ **Smart Visibility**: Appears/disappears based on actual group state
✅ **Rich Information**: State attributes show group membership and size
✅ **Robust Error Handling**: Partial failures don't break group operations
✅ **HA Conventions**: Proper platform separation (number/switch vs media_player)

### **Phase 1 vs Phase 2 Strategy**

**Phase 1 (Implemented)**: Group volume & mute controls

- Addresses 80% of multiroom UX problems
- Minimal complexity, maximum benefit
- Individual media players still available for granular control

**Phase 2 (Future)**: Virtual group media player

- Complete group entity with unified playback control
- Higher complexity, entity lifecycle management
- Decision pending based on Phase 1 user feedback

---

## 📊 **API Endpoint Reference**

### **Core Playback**

| Command  | Endpoint                       | Parameters        | Response |
| -------- | ------------------------------ | ----------------- | -------- |
| Play     | `setPlayerCmd:play`            | None              | "OK"     |
| Pause    | `setPlayerCmd:pause`           | None              | "OK"     |
| Stop     | `setPlayerCmd:stop`            | None              | "OK"     |
| Next     | `setPlayerCmd:next`            | None              | "OK"     |
| Previous | `setPlayerCmd:prev`            | None              | "OK"     |
| Volume   | `setPlayerCmd:vol:<level>`     | level: 0-100      | "OK"     |
| Mute     | `setPlayerCmd:mute:<state>`    | state: 0/1        | "OK"     |
| Seek     | `setPlayerCmd:seek:<position>` | position: seconds | "OK"     |

### **Status Queries**

| Command       | Endpoint                 | Response Type | Notes                         |
| ------------- | ------------------------ | ------------- | ----------------------------- |
| Player Status | `getPlayerStatus`        | JSON          | Universal - always works      |
| Device Info   | `getStatusEx`            | JSON          | WiiM enhanced - probe first   |
| Metadata      | `getMetaInfo`            | JSON          | Often missing - have fallback |
| Multiroom     | `multiroom:getSlaveList` | JSON          | Only works on masters         |

### **EQ Controls**

| Command     | Endpoint          | Parameters                   | Notes                          |
| ----------- | ----------------- | ---------------------------- | ------------------------------ |
| EQ Status   | `EQGetStat`       | None                         | May return {"status":"Failed"} |
| EQ Enable   | `EQOn`            | None                         | Enable EQ processing           |
| EQ Disable  | `EQOff`           | None                         | Disable EQ processing          |
| Load Preset | `EQLoad:<preset>` | preset: "Flat", "Rock", etc. | Device-specific presets        |
| Get EQ      | `getEQ`           | None                         | Current EQ settings            |

---

This API guide ensures our integration works reliably across the entire LinkPlay ecosystem while taking advantage of WiiM enhancements when available. It's based on real implementation experience, testing, and production deployment.
