# WiiM/LinkPlay API Integration Guide

> **Purpose**: Complete technical reference for WiiM/LinkPlay devices covering API compatibility, implementation details, defensive programming, testing strategies, and production deployment.

---

## 📚 **API Documentation Sources**

**Official Documentation**: [Arylic LinkPlay API](https://developer.arylic.com/httpapi/)

| Source                                                                                    | Coverage                   | Notes                               |
| ----------------------------------------------------------------------------------------- | -------------------------- | ----------------------------------- |
| [WiiM API PDF](https://www.wiimhome.com/pdf/HTTP%20API%20for%20WiiM%20Products.pdf)       | WiiM-specific enhancements | Accurate for WiiM devices           |
| [Arylic LinkPlay API](https://developer.arylic.com/httpapi/)                              | Core LinkPlay protocol     | Universal LinkPlay baseline         |
| [OpenAPI Specification](https://github.com/cvdlinden/wiim-httpapi/blob/main/openapi.yaml) | Complete API reference     | OpenAPI 3.0 spec with all endpoints |

**OpenAPI Reference**: The [WiiM HTTP API OpenAPI Specification](https://github.com/cvdlinden/wiim-httpapi/blob/main/openapi.yaml) provides a comprehensive, machine-readable reference for all available endpoints, request parameters, and response structures. This is the most complete and up-to-date API documentation available.

---

## 🎯 **WiiM Source Architecture**

### **Two-Layer Source System**

WiiM devices have a **hierarchical source system** that our integration handles intelligently:

#### **Layer 1: Input/Connection (Technical)**

Physical and connection-level inputs:

- **WiFi/Network** - Internet streaming input
- **Bluetooth** - Bluetooth audio input
- **Line In** - Analog audio input
- **Optical** - Digital optical input
- **Coaxial** - Digital coaxial input

#### **Layer 2: Service/Content (User-Facing)**

Streaming services and protocols:

- **Amazon Music** - Streaming service
- **Spotify** - Streaming service
- **Tidal** - Streaming service
- **AirPlay** - Apple casting protocol
- **DLNA** - Network media protocol
- **Preset 1-6** - Saved stations/playlists

### **API Field Mapping**

Our integration detects the appropriate layer from multiple API fields:

```json
{
  "source": "wifi", // Input layer (connection method)
  "mode": "wifi", // Alternative input field
  "input": "network", // Physical input type
  "streaming_service": "amazon", // Service layer (priority!)
  "app_name": "Amazon Music", // Friendly service name
  "albumArtURI": "https://m.media-amazon.com/...", // Service inference
  "preset": null, // Preset mode
  "play_mode": "normal" // Playback state
}
```

### **Detection Priority**

Our `get_current_source()` method uses this hierarchy:

1. **Explicit service fields** (`streaming_service`, `app_name`)
2. **Service inference** (from `source` field mapping)
3. **Artwork URL patterns** (Amazon URLs → "Amazon Music")
4. **Input fallback** (WiFi, Bluetooth, Line In)

### **User Experience Impact**

**Before (confusing):**

- Source: "WiFi" (when streaming Amazon Music)
- Source: "WiFi" (when streaming Spotify)
- Source: "Network" (when using AirPlay)

**After (meaningful):**

- Source: "Amazon Music" 🎵
- Source: "Spotify" 🎵
- Source: "AirPlay" 📱

This matches user expectations and premium integration standards.

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
    fall back to calling ``EQGetBand``: if the speaker answers with a
    valid response (status "OK") we assume that EQ support is present
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
            # If EQGetBand succeeds we take that as evidence that the EQ
            # subsystem is operational which implies it is *enabled*.
            try:
                response = await self._request(API_ENDPOINT_EQ_GET)
                # Verify we got a valid response (not "unknown command")
                if isinstance(response, dict) and response.get("status") == "OK":
                    return True
                return False
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

#### **Join Group Command**

```
ConnectMasterAp:JoinGroupMaster:eth<master_ip>:wifi0.0.0.0
```

- **Purpose**: Join this device as slave to a master's multiroom group
- **Target**: Send to the **slave device's IP** (using slave's protocol!)
- **Parameters**: `<master_ip>` - IP address of the master device
- **Example**: To join 192.168.1.101 to master 192.168.1.100:
  ```
  https://192.168.1.101/httpapi.asp?command=ConnectMasterAp:JoinGroupMaster:eth192.168.1.100:wifi0.0.0.0
  ```

**🚨 CRITICAL**: Command must be sent **TO the slave device** using **the slave's protocol** (HTTP or HTTPS). Using the master's protocol will cause SSL/connection failures with mixed-protocol devices.

### **Group Status Detection**

#### **Device Role from getStatusEx**

```json
{
  "group": "0", // Solo or Master
  "group": "1", // Slave
  "master_uuid": "...", // Present when slave
  "uuid": "...", // Device UUID
  "wmrm_version": "4.2" // WiiM MultiRoom protocol version
}
```

**wmrm_version** indicates the multiroom protocol version:

- **2.0**: Legacy LinkPlay protocol (older devices, Audio Pro Gen 1)
- **4.2**: Current router-based multiroom protocol (WiiM, Audio Pro Gen 2+/W-Gen)

**⚠️ Compatibility**: Devices can only group with matching `wmrm_version` - this is a protocol-level requirement. Devices with version 2.0 cannot join groups with version 4.2 devices.

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

    # 1. Create group on master first (if not already master)
    if master.role != "master":
        await master.coordinator.client.create_group()

    # 2. Send join command TO each slave using slave's client/protocol
    for slave in slaves:
        # CRITICAL: Use slave's coordinator/client, not master's
        await slave.coordinator.client.join_slave(master.ip_address)

    # 3. Update local state
    master.role = "master"
    master.group_members = [master] + slaves

    for slave in slaves:
        slave.role = "slave"
        slave.coordinator_speaker = master
        slave.group_members = [master] + slaves

    # 4. Notify all entities
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
- ✅ **Device metadata** - Standard LinkPlay device info endpoints available
- ❌ **No getMetaInfo** - Extract metadata from getPlayerStatus
- ❌ **Variable EQ** - Many devices have no EQ at all

### **Third-Party LinkPlay**

- ⚠️ **Unpredictable** - Each manufacturer may customize differently
- ✅ **Basic playback** - Core functions usually work
- ❌ **Advanced features** - Often missing or non-standard

#### **Audio Pro Specific Considerations**

Audio Pro devices have unique characteristics due to their generational evolution and require special handling in our integration:

**⚠️ Generation 1 Audio Pro NOT SUPPORTED:**

Generation 1 devices (A10, A26, A36, C3, C5, C10 without MkII designation) are **not supported** by this integration due to:

- HTTP-only protocol (no HTTPS support)
- Limited/inconsistent HTTP API implementation
- Multiroom protocol version 2.0 (incompatible with modern wmrm_version 4.2)
- No firmware update path to modern features

**✅ Supported Models**: MkII generation (firmware v4.2.8020+) and W-generation devices with HTTPS and wmrm_version 4.2.

**API Protocol Evolution:**

- **Original Generation**: HTTP (port 80) - standard LinkPlay API
- **MkII Generation**: HTTPS (port 443) - enhanced security, same commands
- **W-Generation**: HTTPS (port 443) - latest features, backward compatible

**Enhanced Integration Features:**

**🔍 Generation Detection:**
Our integration automatically detects Audio Pro generations for optimized handling:

```python
# Automatic detection based on model name and firmware
generation = detect_audio_pro_generation(device_info)
# Returns: "original", "mkii", "w_generation", or "unknown"
```

**⚡ Protocol Priority System:**
Smart protocol ordering based on device generation:

```python
# Generation-specific protocol priorities
if generation == "mkii":
    capabilities["protocol_priority"] = ["https", "http"]  # HTTPS first
elif generation == "w_generation":
    capabilities["protocol_priority"] = ["https", "http"]  # HTTPS first
else:  # original
    capabilities["protocol_priority"] = ["http", "https"]  # HTTP first
```

**🛡️ Enhanced Response Validation:**
Comprehensive Audio Pro response handling system:

```python
def _validate_audio_pro_response(self, response: dict[str, Any], endpoint: str) -> dict[str, Any]:
    """Handle Audio Pro specific response variations."""
    # Handles empty responses, string responses, and field normalization
    # Audio Pro devices may return different formats than WiiM devices
```

**Common Response Differences:**

- **Empty responses**: Audio Pro devices may return empty responses that need safe defaults
- **String responses**: Some endpoints return plain text instead of JSON
- **Field variations**: Different field names (`player_state` vs `state`, `vol` vs `volume`)
- **Error formats**: More likely to return plain text errors vs structured JSON

**Field Normalization:**
Our integration automatically maps Audio Pro field variations:

```python
# Audio Pro → Standard field mappings
field_mappings = {
    "player_state": "state",    # Audio Pro specific → standard
    "play_status": "state",     # Alternative Audio Pro field
    "vol": "volume",            # Volume field variations
    "muted": "mute",            # Mute state variations
}
```

**Integration Strategy:**

- **Multi-protocol probing**: HTTP → HTTPS → fallback ports with generation-aware ordering
- **Graceful degradation**: Works even when validation fails during discovery
- **Manual setup friendly**: Always allows IP-based configuration with clear guidance
- **Generation-aware timeouts**: Optimized retry counts and timeouts per generation

**Best Practices:**

- **Always probe protocols**: Don't assume HTTP works (MkII+ devices use HTTPS)
- **Accept validation failures**: They're often cosmetic for Audio Pro devices
- **Enable fallback modes**: Use manual setup when auto-discovery shows warnings
- **Check device generation**: Logging shows which generation optimizations are active

### **Firmware Detection & Updates**

#### **What the API Provides**

The LinkPlay/WiiM API provides firmware **detection and update status**, but **NOT** firmware installation control:

**✅ Available via API:**

- Current firmware version (`firmware` field)
- Update availability flag (`VersionUpdate` - "0" or "1")
- Latest available version (`NewVer` field when update available)
- Multiroom protocol version (`wmrm_version`)
- Security version (`security_version`)

**❌ NOT Available via API:**

- Firmware download/installation via HTTP API
- Check for updates on demand
- Update progress monitoring
- Rollback to previous versions

**How Firmware Updates Actually Work:**

1. **Download**: WiiM servers push firmware to device automatically
2. **Installation**: User triggers via WiiM Home app OR device reboots when update staged
3. **API Role**: Can only detect current version and if update is ready, can trigger reboot

#### **API Detection**

```python
# Get firmware information from getStatusEx endpoint
device_info = await client.get_device_info()

# Current firmware version
firmware = device_info.get("firmware")         # e.g., "4.6.328252"

# Update availability (device downloaded update, ready to install)
version_update = device_info.get("VersionUpdate")  # "0" = no update, "1" = update ready
latest_version = device_info.get("NewVer")         # e.g., "4.6.329100" (when update ready)

# Protocol versions
wmrm_version = device_info.get("wmrm_version")         # e.g., "4.2"
security_version = device_info.get("security_version") # e.g., "2.0"
```

#### **Integration Implementation**

Our integration provides:

1. **Firmware Sensor**: Always-visible diagnostic sensor showing current firmware

   - Entity: `sensor.<device>_firmware`
   - Shows: "4.6.328252" (current version)
   - Attributes: MCU version, DSP version, BLE version, update availability

2. **Update Entity**: Shows update status and allows installation
   - Entity: `update.<device>_firmware_update`
   - Shows: Current version vs latest available
   - Action: "Install" button triggers reboot (if update staged)
   - Disabled by default (enable in entity settings if desired)

#### **Critical Firmware Version Milestones**

| Version       | Introduced             | Key Features/Changes                                          |
| ------------- | ---------------------- | ------------------------------------------------------------- |
| **v4.2.8020** | Router-based multiroom | Default mode (no WiFi Direct needed), wmrm_version 4.2        |
| **v4.6+**     | Enhanced features      | Slow stream handling, notification sounds, improved stability |
| **v4.8+**     | Security updates       | Enhanced HTTPS security (security_version 2.0)                |

**Impact on Integration:**

- Pre-v4.2.8020: May use WiFi Direct mode, less stable multiroom
- v4.2.8020+: Router-based multiroom, better network integration
- v4.6+: Better compatibility with various audio sources
- v4.8+: Improved HTTPS handling

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
- ❌ **Assume HTTP protocol** - Audio Pro MkII+ devices use HTTPS
- ❌ **Expect consistent field names** - Audio Pro uses different field variations
- ❌ **Use master's protocol for slave commands** - each device has its own protocol
- ❌ **Group devices with different wmrm_version** - protocol incompatibility will cause failures

### **DO**

- ✅ **Probe capabilities once** - remember results permanently
- ✅ **Use getPlayerStatus as foundation** - universally supported
- ✅ **Implement graceful fallbacks** - for all enhanced features
- ✅ **Log missing capabilities** - for user troubleshooting
- ✅ **Test multiple protocols** - HTTP and HTTPS with fallback ports
- ✅ **Normalize field names** - handle Audio Pro field variations automatically
- ✅ **Send commands to target device** - multiroom join goes TO slave, using slave's protocol

### **Audio Pro Specific Warnings**

**Protocol Assumptions:**

```python
# ❌ WRONG: Assume HTTP always works
await client.get_status()  # Fails on Audio Pro MkII devices

# ✅ CORRECT: Let integration handle protocol detection
# Integration automatically tries HTTPS first for Audio Pro devices
```

**Response Format Assumptions:**

```python
# ❌ WRONG: Assume always JSON
response = await client._request("/httpapi.asp?command=getPlayerStatus")
# Audio Pro may return string responses that need parsing

# ✅ CORRECT: Use our response validation
# Integration automatically handles Audio Pro response variations
```

**Field Name Assumptions:**

```python
# ❌ WRONG: Assume standard field names
state = response.get("state")  # May be "player_state" on Audio Pro

# ✅ CORRECT: Use normalized fields
# Integration maps Audio Pro fields to standard names automatically
```

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

## 🔊 **Audio Output Mode Control**

### **Hardware Output Management**

WiiM devices with multiple output options (like the WiiM Amp) support hardware output mode switching through dedicated API endpoints. This allows users to control which physical output the audio is routed to.

#### **API Endpoints**

**Get Current Output Status:**

```
GET https://<device_ip>/httpapi.asp?command=getNewAudioOutputHardwareMode
```

**Response:**

```json
{
  "hardware": "2", // Current hardware output mode (1-4)
  "source": "0", // Bluetooth output status (0=disabled, 1=active)
  "audiocast": "0" // Audio cast status (0=disabled, 1=active)
}
```

**Set Output Mode:**

```
GET https://<device_ip>/httpapi.asp?command=setAudioOutputHardwareMode:<mode>
```

#### **Output Mode Mapping**

| API Mode | Output Type   | Description                  | Device Support     |
| -------- | ------------- | ---------------------------- | ------------------ |
| **1**    | Optical Out   | SPDIF/Optical digital output | WiiM Amp, Pro Plus |
| **2**    | Line Out      | AUX/Analog line output       | WiiM Amp, Pro Plus |
| **3**    | Coax Out      | Coaxial digital output       | WiiM Amp, Pro Plus |
| **4**    | Bluetooth Out | Bluetooth audio output       | WiiM Amp, Pro Plus |

#### **Implementation Strategy**

Our integration provides:

1. **Select Entity**: `select.<device>_audio_output_mode` for easy mode switching
2. **Status Sensors**: Individual sensors for Bluetooth and audio cast status
3. **Automation Support**: Full automation integration for output switching
4. **Real-time Updates**: 15-second polling for status changes

#### **Bluetooth Output Behavior**

The `source` field indicates when Bluetooth output is active:

- **`"source": "0"`**: Bluetooth output disabled (using hardware outputs)
- **`"source": "1"`**: Bluetooth output active (audio routed to paired Bluetooth device)

**Important**: Bluetooth output is controlled by firmware auto-connection behavior, not direct API commands. When a previously paired Bluetooth device becomes available, the WiiM automatically switches to Bluetooth output.

#### **User Experience**

**Before**: Users had to manually switch output modes using the WiiM app
**After**: Complete output control through Home Assistant automations and UI

```yaml
# Example automation: Switch to Bluetooth when headphones connect
- alias: "Switch to Bluetooth Output"
  trigger:
    platform: device_tracker
    entity_id: device_tracker.headphones
    to: "home"
  action:
    - service: select.select_option
      target: select.living_room_audio_output_mode
      data:
        option: "Bluetooth Out"
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

| Command       | Endpoint                        | Response Type | Notes                         |
| ------------- | ------------------------------- | ------------- | ----------------------------- |
| Player Status | `getPlayerStatus`               | JSON          | Universal - always works      |
| Device Info   | `getStatusEx`                   | JSON          | WiiM enhanced - probe first   |
| Metadata      | `getMetaInfo`                   | JSON          | Often missing - have fallback |
| Audio Output  | `getNewAudioOutputHardwareMode` | JSON          | Hardware output status        |
| Multiroom     | `multiroom:getSlaveList`        | JSON          | Only works on masters         |

#### **Get Track Metadata**

**Endpoint:**

```
GET /httpapi.asp?command=getMetaInfo
```

**Response:** Track metadata with album art and audio quality information

**Example Response:**

```json
{
  "metaData": {
    "album": "Country Heat",
    "title": "Old Dirt Roads",
    "subtitle": "",
    "artist": "Owen Riegling",
    "albumArtURI": "https://m.media-amazon.com/images/I/51iU0odzJwL.jpg",
    "sampleRate": "44100",
    "bitDepth": "16",
    "bitRate": "63",
    "trackId": "s6707"
  }
}
```

**Response Fields:**

- `metaData`: Metadata object containing track information
  - `album`: Album name
  - `title`: Track title
  - `subtitle`: Track subtitle (may be empty)
  - `artist`: Artist name
  - `albumArtURI`: URL to the album artwork image
  - `sampleRate`: Audio sample rate in Hz (e.g., "44100", "48000")
  - `bitDepth`: Audio bit depth in bits (e.g., "16", "24")
  - `bitRate`: Audio bit rate in kbps (e.g., "63", "320")
  - `trackId`: Track identifier (service-specific)

**Observations:**

- Not all devices support this endpoint - many older LinkPlay devices return errors
- When unavailable, metadata must be extracted from `getPlayerStatus` (which has limited fields)
- Album artwork is only available via this endpoint
- Audio quality fields (sampleRate, bitDepth, bitRate) provide detailed audio stream information
- Fields may contain "unknow" or "un_known" when metadata is unavailable
- `trackId` is service-specific and may vary by streaming service

### **Audio Output Controls**

| Command    | Endpoint                            | Parameters | Notes                    |
| ---------- | ----------------------------------- | ---------- | ------------------------ |
| Get Output | `getNewAudioOutputHardwareMode`     | None       | Hardware output status   |
| Set Output | `setAudioOutputHardwareMode:<mode>` | mode: 1-4  | Set hardware output mode |

### **Fade Effects**

| Command  | Endpoint                 | Parameters | Notes                   |
| -------- | ------------------------ | ---------- | ----------------------- |
| Get Fade | `GetFadeFeature`         | None       | Get fade effects status |
| Set Fade | `SetFadeFeature:<value>` | value: 0/1 | Enable/disable fade     |

#### **Get Fade Effects Status**

**Endpoint:**

```
GET /httpapi.asp?command=GetFadeFeature
```

**Response:**

```json
{
  "FadeFeature": 1 // 0 = disabled, 1 = enabled
}
```

**Observations:**

- Fade effects provide smooth transitions between tracks (fade out/in)
- When enabled, tracks fade out at the end and fade in at the start
- Useful for seamless playback experience

#### **Set Fade Effects**

**Endpoint:**

```
GET /httpapi.asp?command=SetFadeFeature:1
```

**Parameters:**

- `0`: Disable fade effects
- `1`: Enable fade effects

**Response:** `OK` on success

**Example:**

```
# Enable fade effects
GET /httpapi.asp?command=SetFadeFeature:1

# Disable fade effects
GET /httpapi.asp?command=SetFadeFeature:0
```

### **Volume Control Settings**

| Command          | Endpoint                   | Parameters | Notes                 |
| ---------------- | -------------------------- | ---------- | --------------------- |
| Set Fixed Volume | `setVolumeControl:<value>` | value: 0/1 | Set fixed volume mode |

#### **Set Fixed Volume Mode**

**Endpoint:**

```
GET /httpapi.asp?command=setVolumeControl:1
```

**Parameters:**

- `0`: Variable volume (normal mode - volume can be adjusted)
- `1`: Fixed volume (volume changes are prevented)

**Response:** `OK` on success

**Status Reading:**
Fixed volume status is read from the `getStatusEx` endpoint:

```json
{
  "volume_control": "0" // "0" = variable, "1" = fixed
}
```

**Use Cases:**

- **Fixed volume mode**: Useful when using line-out to external amplifier where you want to prevent volume changes
- **Variable volume mode**: Normal operation where volume can be adjusted via API or device controls

**Example:**

```
# Enable fixed volume mode
GET /httpapi.asp?command=setVolumeControl:1

# Disable fixed volume (return to variable)
GET /httpapi.asp?command=setVolumeControl:0
```

**Audio Output Modes:**

- **Mode 1**: Optical Out (SPDIF)
- **Mode 2**: Line Out (AUX/Analog)
- **Mode 3**: Coax Out (Coaxial)
- **Mode 4**: Bluetooth Out

**Response Format:**

```json
{
  "hardware": "2", // Current hardware output mode
  "source": "0", // Bluetooth output status (0=disabled, 1=active)
  "audiocast": "0" // Audio cast status (0=disabled, 1=active)
}
```

### **EQ Controls**

| Command     | Endpoint          | Parameters                   | Notes                          |
| ----------- | ----------------- | ---------------------------- | ------------------------------ |
| EQ Status   | `EQGetStat`       | None                         | May return {"status":"Failed"} |
| EQ Enable   | `EQOn`            | None                         | Enable EQ processing           |
| EQ Disable  | `EQOff`           | None                         | Disable EQ processing          |
| Get Presets | `EQGetList`       | None                         | Returns array of preset names  |
| Load Preset | `EQLoad:<preset>` | preset: "Flat", "Rock", etc. | Device-specific presets        |
| Get EQ      | `EQGetBand`       | None                         | Current EQ settings            |

#### **Get Available EQ Presets**

**Endpoint:**

```
GET /httpapi.asp?command=EQGetList
```

**Response:** Array of preset names (varies by device/firmware)

**Example Response:**

```json
[
  "Acoustic",
  "Bass Booster",
  "Bass Reducer",
  "Classical",
  "Dance",
  "Deep",
  "Electronic",
  "Flat",
  "Game",
  "Hip-Hop",
  "Jazz",
  "Latin",
  "Loudness",
  "Lounge",
  "Movie",
  "Piano",
  "Pop",
  "R&B",
  "Rock",
  "Small Speakers",
  "Spoken Word",
  "Treble Booster",
  "Treble Reducer",
  "Vocal Booster"
]
```

**Observations:**

- Preset availability varies by device model and firmware version
- Some devices may return a subset of these presets
- Integration uses this endpoint to dynamically extend available presets at startup
- Not all devices support EQ - endpoint may return error on unsupported devices

#### **Set Equalizer Preset**

**Endpoint:**

```
GET /httpapi.asp?command=EQLoad:<preset>
```

**Parameters:**

- `preset`: Preset name (e.g., "Classical", "Rock", "Hip-Hop", "Bass Booster")

**Response:** Detailed EQ configuration with 10-band equalizer settings

**Example Response:**

```json
{
  "EQStat": "On",
  "Name": "Classical",
  "pluginURI": "http://moddevices.com/plugins/caps/Eq10HP",
  "EQBand": [
    { "index": 0, "param_name": "band31Hz", "value": 4.8 },
    { "index": 1, "param_name": "band63Hz", "value": 3.8 },
    { "index": 2, "param_name": "band125Hz", "value": 3.0 },
    { "index": 3, "param_name": "band250Hz", "value": 2.5 },
    { "index": 4, "param_name": "band500Hz", "value": -1.5 },
    { "index": 5, "param_name": "band1kHz", "value": -1.5 },
    { "index": 6, "param_name": "band2kHz", "value": 0.0 },
    { "index": 7, "param_name": "band4kHz", "value": 2.2 },
    { "index": 8, "param_name": "band8kHz", "value": 3.2 },
    { "index": 9, "param_name": "band16kHz", "value": 3.8 }
  ],
  "channelMode": "Stereo",
  "status": "OK",
  "source_name": "wifi"
}
```

**Response Fields:**

- `EQStat`: EQ status ("On" or "Off")
- `Name`: Preset name
- `pluginURI`: MOD Devices plugin URI reference
- `EQBand`: Array of 10-band equalizer settings
  - `index`: Band index (0-9)
  - `param_name`: Frequency band name
  - `value`: Gain value in dB (typically -12.0 to +12.0)
- `channelMode`: Channel mode (typically "Stereo")
- `status`: Operation status ("OK" or "Failed")
- `source_name`: Current audio source

**Frequency Bands:**

- Band 0: 31 Hz (sub-bass)
- Band 1: 63 Hz (bass)
- Band 2: 125 Hz (low-mid)
- Band 3: 250 Hz (mid)
- Band 4: 500 Hz (mid)
- Band 5: 1 kHz (mid-high)
- Band 6: 2 kHz (high-mid)
- Band 7: 4 kHz (high)
- Band 8: 8 kHz (high)
- Band 9: 16 kHz (ultra-high)

**Parameter Encoding:**

- Preset names with spaces should be URL encoded (e.g., "Bass Booster" → "Bass+Booster")
- Some preset names contain special characters (e.g., "R&B") that may need encoding

#### **Get Current EQ Settings**

**Endpoint:**

```
GET /httpapi.asp?command=EQGetBand
```

**Response:** Current EQ configuration with 10-band equalizer settings (same format as `EQLoad` response)

**Example Response:**

```json
{
  "status": "OK",
  "EQLevel": 1,
  "source_name": "wifi",
  "EQStat": "On",
  "Name": "Flat",
  "pluginURI": "http://moddevices.com/plugins/caps/Eq10HP",
  "channelMode": "Stereo",
  "EQBand": [
    { "index": 0, "param_name": "band31hz", "value": 50 },
    { "index": 1, "param_name": "band63hz", "value": 50 },
    { "index": 2, "param_name": "band125hz", "value": 50 },
    { "index": 3, "param_name": "band250hz", "value": 50 },
    { "index": 4, "param_name": "band500hz", "value": 50 },
    { "index": 5, "param_name": "band1khz", "value": 50 },
    { "index": 6, "param_name": "band2khz", "value": 50 },
    { "index": 7, "param_name": "band4khz", "value": 50 },
    { "index": 8, "param_name": "band8khz", "value": 50 },
    { "index": 9, "param_name": "band16khz", "value": 50 }
  ]
}
```

**Response Fields:**

- `status`: Operation status ("OK" or "Failed")
- `EQLevel`: EQ level (typically 1)
- `source_name`: Current audio source
- `EQStat`: EQ status ("On" or "Off")
- `Name`: Current preset name (or "Custom" if using custom EQ)
- `pluginURI`: MOD Devices plugin URI reference
- `channelMode`: Channel mode (typically "Stereo")
- `EQBand`: Array of 10-band equalizer settings
  - `index`: Band index (0-9)
  - `param_name`: Frequency band name (lowercase in response)
  - `value`: Gain value (0-100 scale for custom EQ, or dB values for presets)

**Observations:**

- Returns current EQ settings whether using a preset or custom EQ
- Response format matches `EQLoad` response structure
- Value scale may differ: custom EQ uses 0-100, presets may use dB values
- Parameter names in response are lowercase (e.g., "band31hz" vs "band31Hz" in `EQLoad`)

**Note:** The `getEQ` endpoint does not exist on WiiM devices. Use `EQGetBand` instead.

---

## ⚠️ **Unofficial/Undocumented Endpoints**

These endpoints are **not officially documented** by WiiM and have been discovered through reverse engineering and community research. They may change or be removed in future firmware updates. **Use at your own risk.**

### **Bluetooth Operations**

#### **Bluetooth Device Discovery**

Start Bluetooth Discovery:

```
GET /httpapi.asp?command=startbtdiscovery:3
```

- **Parameters**: Discovery duration in seconds (typically 3-10 seconds)
- **Response**: `OK` when discovery starts

Get Discovery Results:

```
GET /httpapi.asp?command=getbtdiscoveryresult
```

**Response (Actual API Format):**

```json
{
  "num": 1,
  "scan_status": 3,
  "list": [
    {
      "name": "DELL27KITCHEN",
      "ad": "ac:5a:fc:02:2c:a8",
      "ct": 0,
      "role": "Audio Sink"
    }
  ]
}
```

**Response Fields:**

- `num`: Number of devices found
- `scan_status`: Scan status value
  - `0`: Not started
  - `1`: Initializing
  - `2`: ??? (rarely seen, unknown state)
  - `3`: Scanning (in progress)
  - `4`: Finished scanning (complete)
- `list`: Array of discovered Bluetooth devices
  - `name`: Device name (e.g., "DELL27KITCHEN")
  - `ad`: MAC address (e.g., "ac:5a:fc:02:2c:a8") - **Note**: API uses `ad` not `mac`
  - `ct`: Connection type (0=unknown, may vary)
  - `role`: Device role (e.g., "Audio Sink", "Audio Source")
  - `rssi`: Signal strength (optional, may not always be present)

**Important Notes:**

- The API returns `list` (not `bt_device`) and uses `ad` (not `mac`) for the MAC address
- The integration normalizes this format internally for consistency
- `scan_status` must be checked before reading results (status 3 = complete)
- Wait at least the scan duration + a few seconds before checking results

### **Audio Settings**

#### **SPDIF Sample Rate Configuration**

Get SPDIF Sample Rate:

```
GET /httpapi.asp?command=getSpdifOutSampleRate
```

- **Response**: Sample rate in Hz (e.g., "48000")

Set SPDIF Switch Delay:

```
GET /httpapi.asp?command=setSpdifOutSwitchDelayMs:800
```

- **Parameters**: Delay in milliseconds (0-3000ms)
- **Response**: `OK` on success
- **Notes**: Only relevant when output interface is SPDIF (optical)

#### **Channel Balance Control**

Get Left/Right Channel Balance:

```
GET /httpapi.asp?command=getChannelBalance
```

- **Response**: Balance value from -1.0 (fully left) to 1.0 (fully right)

Set Channel Balance:

```
GET /httpapi.asp?command=setChannelBalance:0.5
```

- **Parameters**: Balance value from -1.0 to 1.0
- **Response**: `OK` on success, `Failed` on error

### **Squeezelite (LMS) Integration**

WiiM devices support integration with Lyrion Music Server (LMS, formerly Logitech Media Server) through the Squeezelite protocol. This allows the WiiM device to act as a Squeezelite player and connect to LMS instances on your network.

#### **Get Squeezelite State**

**Endpoint:**

```
GET /httpapi.asp?command=Squeezelite:getState
```

**Response:**

```json
{
  "default_server": "192.168.1.4:3483",
  "state": "connected",
  "discover_list": ["192.168.1.4:3483", "192.168.1.123:3483"],
  "connected_server": "192.168.1.4:3483",
  "auto_connect": 1
}
```

**Response Fields:**

- `default_server`: The LMS instance to which the player would connect automatically
- `state`: Current connection state
  - `discovering`: Player is discovering LMS instances on the network
  - `connected`: Player is connected to an LMS server
- `discover_list`: Array of LMS instances found in the player's network (IP:port format)
- `connected_server`: Currently connected LMS server (IP:port format, only present when connected)
- `auto_connect`: Auto-connect flag (0=disabled, 1=enabled)

**Observations:**

- `discover_list` may contain multiple LMS instances if multiple servers are on the network
- `default_server` is the preferred server for auto-connection
- State transitions from `discovering` to `connected` when a server is found and connected

#### **Trigger LMS Discovery**

**Endpoint:**

```
GET /httpapi.asp?command=Squeezelite:discover
```

**Response:** `OK`

**Purpose:** Manually trigger discovery of LMS instances on the network. Useful when:

- A new LMS server is added to the network
- Network configuration changes
- Previous discovery didn't find all servers

**Note:** Discovery may take several seconds. Check state with `Squeezelite:getState` after triggering.

#### **Enable/Disable Auto-Connect**

**Endpoint:**

```
GET /httpapi.asp?command=Squeezelite:autoConnectEnable:1
```

**Parameters:**

- `1`: Enable auto-connect (player will automatically connect to `default_server` on startup)
- `0`: Disable auto-connect (manual connection required)

**Response:** `OK`

**Use Cases:**

- Enable auto-connect for seamless integration with a primary LMS server
- Disable auto-connect when using multiple LMS servers or manual control

#### **Connect to LMS Server**

**Endpoint:**

```
GET /httpapi.asp?command=Squeezelite:connectServer:192.168.1.123
```

**Parameters:**

- LMS server IP address (required)
- Optional port (default: 3483) - format: `IP:PORT` or just `IP`

**Examples:**

```
# Connect to server with default port
GET /httpapi.asp?command=Squeezelite:connectServer:192.168.1.123

# Connect to server with custom port
GET /httpapi.asp?command=Squeezelite:connectServer:192.168.1.123:9000
```

**Response:** `OK` on success

**Important Notes:**

- Server must be in the `discover_list` from previous discovery
- If server is not discovered, connection will fail
- Device will switch audio source to Squeezelite when connected
- Disconnection from current audio source may occur

### **LED and Button Controls**

These endpoints control the physical interface elements of the WiiM device, including the status LED and touch button controls.

#### **Status LED Control**

**Endpoint:**

```
GET /httpapi.asp?command=LED_SWITCH_SET:0
```

**Parameters:**

- `1`: Enable status LED (LED will show device status)
- `0`: Disable status LED (LED will be off)

**Response:** `OK` on success

**Examples:**

```
# Disable status LED
GET /httpapi.asp?command=LED_SWITCH_SET:0

# Enable status LED
GET /httpapi.asp?command=LED_SWITCH_SET:1
```

**Observations:**

- This is an alternative to the standard `setLED` command
- Status LED typically shows connection status, playback state, or error conditions
- Disabling LED may be desired for bedroom/quiet environments
- LED state persists across device reboots

**Note:** Some devices may not have a status LED, in which case this command may have no effect or return an error.

#### **Touch Button Controls**

**Endpoint:**

```
GET /httpapi.asp?command=Button_Enable_SET:1
```

**Parameters:**

- `1`: Enable touch controls (buttons on device are active)
- `0`: Disable touch controls (buttons on device are inactive)

**Response:** `OK` on success

**Examples:**

```
# Disable touch controls
GET /httpapi.asp?command=Button_Enable_SET:0

# Enable touch controls
GET /httpapi.asp?command=Button_Enable_SET:1
```

**Use Cases:**

- Disable touch controls to prevent accidental button presses
- Enable/disable controls for child-proofing or public installations
- Toggle controls based on automation rules (e.g., disable during sleep hours)

**Important Notes:**

- When disabled, physical buttons on the device will not respond
- Remote control and API commands continue to work regardless of button state
- Button state persists across device reboots
- Some device models may not have touch controls (e.g., devices with only physical buttons)

### **Unofficial Endpoint Considerations**

**Error Handling:**

- All endpoints use GET method regardless of operation type
- Error responses vary but typically include "Failed" or error status
- Success responses are typically "OK" or structured JSON

**Parameter Encoding:**

- URL encode parameters when they contain spaces or special characters
- Boolean values use `1` for true, `0` for false
- Array parameters are typically colon-separated

**Firmware Compatibility:**

- These endpoints may not be available on all firmware versions
- Behavior may vary between WiiM device models
- Test thoroughly before using in production automations

**Rate Limiting:**

- Avoid rapid successive calls to the same endpoint
- Some endpoints may have internal cooldown periods
- Discovery operations should not be run continuously

---

## 📋 **OpenAPI Spec Commands Not Currently Used**

The [OpenAPI Specification](https://github.com/cvdlinden/wiim-httpapi/blob/main/openapi.yaml) includes several endpoints that our integration does not currently implement. These may be candidates for future enhancements:

### **Alarm Clock Operations**

- `getAlarmClock` - Get alarm clock settings
- `setAlarmClock` - Set alarm clock configuration
- `alarmStop` - Stop active alarm

### **Bluetooth Advanced Operations** (Implemented)

These endpoints are now implemented in the integration:

#### **Bluetooth Device History**

- `getbthistory` - Get Bluetooth connection history (previously paired devices)

  - **Response**: `{"num": 0, "scan_status": 3}` or list of devices
  - Returns devices that have been paired before, even if not currently in range
  - **Device Fields**:
    - `name`: Device friendly name (e.g., "TOZO-T6")
    - `ad`: MAC address (format: "19:12:25:08:0f:b7")
    - `mac`: Alternative MAC address field (same as `ad`)
    - `ct`: Connection status (0=not connected, 1=connected)
    - `role`: Device role ("Audio Sink" for headphones/speakers, "Audio Source" for input devices)
  - **Important**: This endpoint reliably enumerates ALL devices that have been paired with the WiiM, making it suitable for populating device selection menus without requiring scanning
  - **Polling Strategy**: Fetched once at startup, then only when Bluetooth output is active (to track connected device)

#### **Bluetooth Connection Status**

- `getbtpairstatus` - Get Bluetooth pairing status

  - **Response**: `{"result": 0}` (0=not paired, 1=paired)
  - Used to determine if Bluetooth device is currently connected
  - Polled every 15 seconds when Bluetooth output is active

#### **Bluetooth Connection Control**

- `connectbta2dpsynk:MAC_ADDRESS` - Connect to Bluetooth device by MAC address

  - **Parameters**: MAC address in format `AA:BB:CC:DD:EE:FF` or `AA-BB-CC-DD-EE-FF`
  - **Response**: `OK` on success
  - **Timeout**: 30 seconds (device takes ~15 seconds to respond)
  - **Behavior**: Automatically switches output mode to "Bluetooth Out" when connection succeeds
  - **Note**: Device must have been previously paired via WiiM app - this endpoint only connects to known devices

- `disconnectbta2dpsynk` - Disconnect current Bluetooth connection
  - **Response**: `OK` on success

#### **Bluetooth Discovery** (Legacy - not used in current implementation)

- `clearbtdiscoveryresult` - Clear Bluetooth discovery results
  - **Response**: `OK` on success
  - **Note**: Discovery scanning is not implemented - pairing is done via WiiM app, connection is done via `connectbta2dpsynk`

#### **Implementation Notes**

- **Pairing**: Must be done via WiiM app - Home Assistant integration cannot pair new devices
- **Connection**: Home Assistant can connect to previously paired devices using `connectbta2dpsynk`
- **History Reliability**: `getbthistory` always returns complete list of paired devices, making it reliable for UI population
- **Polling Strategy**:
  - History fetched once at startup (for dropdown population)
  - Only polls when BT output is active (to track connected device)
  - Manual refresh available via UI option

### **Audio Hardware Capabilities**

- `getActiveSoundCardOutputMode` - Get current sound card output mode
- `getSoundCardModeSupportList` - Get supported sound card modes
- `getAuxVoltageSupportList` - Get auxiliary voltage support list
- `getSpdifOutMaxCap` - Get SPDIF output maximum capability
- `getCoaxOutMaxCap` - Get coaxial output maximum capability

### **Network Configuration**

- `getStaticIP` - Get static IP info (deprecated - use `getStaticIpInfo`)
- `getWlanBandConfig` - Get WiFi band configuration
- `getWlanRoamConfig` - Get WiFi roaming configuration
- `getNetworkPreferDNS` - Get preferred DNS settings
- `getIPV6Enable` - Get IPv6 enable status

### **Device Management**

- `setDeviceName` - Set device name (UPnP/DLNA/AirPlay)
- `setSSID` - Set device SSID (hex format)
- `setNetwork` - Set WiFi password and security
- `restoreToDefault` - Factory reset
- `setPowerWifiDown` - Turn off WiFi signal

### **Remote Control Features**

- `getMvRemoteSilenceUpdateTime` - Get remote silence update time
- `getMvRemoteUpdateStart` - Get remote update start status
- `getMvRemoteUpdateStartCheck` - Check remote update start
- `getMvRemoteUpdateStatus` - Get remote update status
- `getMvRomBurnPrecent` - Get ROM burn percentage

### **Other Features**

- `GetFadeFeature` - Get fade feature settings
- `audio_cast` - Audio cast operations
- `setLightOperationBrightConfig` - Set LED brightness configuration

**Note**: These endpoints may not be available on all devices or firmware versions. Before implementing, test thoroughly and verify device support.

---

This API guide ensures our integration works reliably across the entire LinkPlay ecosystem while taking advantage of WiiM enhancements when available. It's based on real implementation experience, testing, and production deployment.
