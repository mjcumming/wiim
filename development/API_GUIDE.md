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

### **Audio Output Controls**

| Command    | Endpoint                            | Parameters | Notes                    |
| ---------- | ----------------------------------- | ---------- | ------------------------ |
| Get Output | `getNewAudioOutputHardwareMode`     | None       | Hardware output status   |
| Set Output | `setAudioOutputHardwareMode:<mode>` | mode: 1-4  | Set hardware output mode |

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
| Load Preset | `EQLoad:<preset>` | preset: "Flat", "Rock", etc. | Device-specific presets        |
| Get EQ      | `getEQ`           | None                         | Current EQ settings            |

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

**Response:**

```json
{
  "num": 3,
  "scan_status": 0,
  "bt_device": [
    {
      "name": "iPhone",
      "mac": "AA:BB:CC:DD:EE:FF",
      "rssi": -45
    }
  ]
}
```

**Notes:**

- `scan_status`: 0=Not started, 1=Initializing, 2=Scanning, 3=Complete
- Results include device names, MAC addresses, and RSSI values

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

#### **LMS Server Discovery and Connection**

Get Squeezelite State:

```
GET /httpapi.asp?command=Squeezelite:getState
```

**Response:**

```json
{
  "default_server": "192.168.1.4:3483",
  "state": "connected",
  "discover_list": ["192.168.1.4:3483"],
  "connected_server": "192.168.1.4:3483",
  "auto_connect": 1
}
```

**State values:**

- `discovering`: Searching for LMS instances
- `connected`: Connected to LMS server

Trigger LMS Discovery:

```
GET /httpapi.asp?command=Squeezelite:discover
```

Enable/Disable Auto-Connect:

```
GET /httpapi.asp?command=Squeezelite:autoConnectEnable:1
```

- **Parameters**: `1` to enable, `0` to disable
- **Response**: `OK`

Connect to LMS Server:

```
GET /httpapi.asp?command=Squeezelite:connectServer:192.168.1.123
```

- **Parameters**: LMS server IP address (with optional port)
- **Response**: `OK`

### **LED and Button Controls**

Set Status LED (Alternative Command):

```
GET /httpapi.asp?command=LED_SWITCH_SET:0
```

- **Parameters**: `1` to enable, `0` to disable status LED
- **Response**: `OK` on success
- **Note**: Alternative to standard `setLED` command

Set Touch Button Controls:

```
GET /httpapi.asp?command=Button_Enable_SET:1
```

- **Parameters**: `1` to enable, `0` to disable touch controls
- **Response**: `OK` on success

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

### **Bluetooth Advanced Operations**

- `getbthistory` - Get Bluetooth connection history
- `getbtpairstatus` - Get Bluetooth pairing status
- `clearbtdiscoveryresult` - Clear Bluetooth discovery results
- `connectbta2dpsynk` - Connect Bluetooth A2DP sync
- `disconnectbta2dpsynk` - Disconnect Bluetooth A2DP sync

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
