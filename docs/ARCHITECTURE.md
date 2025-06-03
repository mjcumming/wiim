# WiiM Integration – Technical Architecture

> **Goal**: Document the technical architecture, component relationships, data flow, and implementation details of our Sonos-inspired WiiM integration.

---

## 🏗️ **System Overview**

### **High-Level Architecture**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Home Assistant Core                          │
├─────────────────────────────────────────────────────────────────┤
│                      WiiM Integration                           │
│                                                                 │
│  ┌──────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │  WiimData    │    │   Speaker   │    │    WiimEntity       │ │
│  │  (Registry)  │◄──►│  (Business  │◄──►│   (UI Adapter)      │ │
│  │              │    │   Logic)    │    │                     │ │
│  └──────────────┘    └─────────────┘    └─────────────────────┘ │
│         ▲                    ▲                       ▲          │
│         │                    │                       │          │
│  ┌──────▼──────┐    ┌────────▼────────┐    ┌────────▼─────────┐ │
│  │ Coordinator │    │   WiiMClient    │    │   Entity Types   │ │
│  │ (Polling)   │    │   (HTTP API)    │    │ (Media, Sensor,  │ │
│  │             │    │                 │    │  Button, etc.)   │ │
│  └─────────────┘    └─────────────────┘    └──────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
         ▲                        ▲
         │                        │
   ┌─────▼─────┐            ┌─────▼─────┐
   │   Smart   │            │   WiiM    │
   │  Polling  │            │  Device   │
   │  Manager  │            │ (LinkPlay)│
   └───────────┘            └───────────┘
```

---

## 🧩 **Core Components**

### **1. WiimData - Central Registry**

**Purpose**: Single source of truth for all speaker state and relationships.

```python
@dataclass
class WiimData:
    """Central registry for all WiiM speakers (like SonosData)."""

    hass: HomeAssistant

    # Primary registry: UUID → Speaker
    speakers: dict[str, Speaker] = field(default_factory=dict)

    # Fast lookups (replaces custom device_registry.py)
    entity_id_mappings: dict[str, Speaker] = field(default_factory=dict)

    # Operational data
    discovery_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def get_speaker_by_ip(self, ip: str) -> Speaker | None:
        """O(n) lookup by IP address."""
        return next((s for s in self.speakers.values() if s.ip == ip), None)

    def get_speaker_by_entity_id(self, entity_id: str) -> Speaker | None:
        """O(1) lookup by entity ID."""
        return self.entity_id_mappings.get(entity_id)
```

**Responsibilities**:

- ✅ Store all discovered speakers
- ✅ Provide fast lookups (UUID, IP, entity_id)
- ✅ Manage speaker lifecycle
- ✅ Replace custom `device_registry.py`

---

### **2. Speaker - Rich Business Object**

**Purpose**: Contains all business logic, device state, and group management.

```python
class Speaker:
    """Rich speaker object with business logic (like SonosSpeaker)."""

    def __init__(self, hass: HomeAssistant, uuid: str, coordinator: WiiMCoordinator):
        self.hass = hass
        self.uuid = uuid
        self.coordinator = coordinator

        # Device properties
        self.name: str = ""
        self.model: str = ""
        self.firmware: str | None = None
        self.ip: str = ""
        self.mac: str = ""

        # Group state
        self.role: str = "solo"  # solo/master/slave
        self.group_members: list[Speaker] = []
        self.coordinator_speaker: Speaker | None = None

        # HA integration
        self.device_info: DeviceInfo | None = None
        self._available: bool = True

    # Device lifecycle
    async def async_setup(self, entry: ConfigEntry) -> None:
        """Complete speaker setup and HA device registration."""

    async def async_shutdown(self) -> None:
        """Clean shutdown of speaker resources."""

    # State management
    def async_write_entity_states(self) -> None:
        """Notify all entities of state changes (event-driven)."""
        async_dispatcher_send(self.hass, f"wiim_state_updated_{self.uuid}")

    def update_from_coordinator_data(self) -> None:
        """Update speaker state from coordinator data."""

    # Group management (moved from media_player.py)
    async def async_join_group(self, speakers: list[Speaker]) -> None:
        """Join this speaker to a group."""

    async def async_leave_group(self) -> None:
        """Remove this speaker from its group."""

    def get_group_member_entity_ids(self) -> list[str]:
        """Get entity IDs of all group members."""

    # Business logic helpers
    @property
    def available(self) -> bool:
        return self._available and self.coordinator.last_update_success

    @property
    def is_group_coordinator(self) -> bool:
        return self.role == "master" or (self.role == "solo" and not self.group_members)

    def get_playback_state(self) -> MediaPlayerState:
        """Calculate current playback state from coordinator data."""
```

**Responsibilities**:

- ✅ Device state and properties
- ✅ Group management logic
- ✅ Business rule enforcement
- ✅ Event dispatching to entities
- ✅ HA device registration

---

### **3. WiimEntity - Event-Driven Base Class**

**Purpose**: Thin base class that connects HA entities to Speaker objects.

```python
class WiimEntity(Entity):
    """Base class for all WiiM entities (like SonosEntity)."""

    _attr_should_poll = False  # Event-driven, no polling
    _attr_has_entity_name = True

    def __init__(self, speaker: Speaker) -> None:
        """Initialize with speaker reference."""
        self.speaker = speaker

    async def async_added_to_hass(self) -> None:
        """Set up event listening and entity registration."""
        # Register in central mapping
        data: WiimData = self.hass.data[DOMAIN]["data"]
        data.entity_id_mappings[self.entity_id] = self.speaker

        # Listen for speaker state changes
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"wiim_state_updated_{self.speaker.uuid}",
                self.async_write_ha_state,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up entity registration."""
        data: WiimData = self.hass.data[DOMAIN]["data"]
        data.entity_id_mappings.pop(self.entity_id, None)

    @property
    def device_info(self) -> DeviceInfo:
        """Delegate to speaker (single source of truth)."""
        return self.speaker.device_info

    @property
    def available(self) -> bool:
        """Delegate to speaker."""
        return self.speaker.available
```

**Responsibilities**:

- ✅ HA entity lifecycle management
- ✅ Event-driven state updates
- ✅ Entity ↔ Speaker mapping
- ✅ Delegate device_info to Speaker

---

### **4. Platform Entities - Thin Adapters**

**Purpose**: Minimal entity implementations that delegate to Speaker.

```python
class WiiMMediaPlayer(WiimEntity, MediaPlayerEntity):
    """WiiM media player - thin wrapper around Speaker."""

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = speaker.uuid

    # State properties (delegate to speaker)
    @property
    def state(self) -> MediaPlayerState:
        return self.speaker.get_playback_state()

    @property
    def volume_level(self) -> float | None:
        return self.speaker.get_volume_level()

    @property
    def group_members(self) -> list[str]:
        return self.speaker.get_group_member_entity_ids()

    # Control methods (delegate to speaker)
    async def async_play(self) -> None:
        await self.speaker.coordinator.client.play()
        self.speaker.async_write_entity_states()

    async def async_join(self, group_members: list[str]) -> None:
        speakers = self.speaker.resolve_entity_ids_to_speakers(group_members)
        await self.speaker.async_join_group(speakers)
```

---

## 🔄 **Data Flow Architecture**

### **1. Speaker Discovery & Setup**

```
Integration Setup
       ↓
Create WiiMCoordinator (with WiiMClient)
       ↓
First data fetch
       ↓
Create/Update Speaker in WiimData
       ↓
Speaker.async_setup() → HA device registration
       ↓
Create entities (MediaPlayer, Sensor, etc.)
       ↓
Entities register in WiimData.entity_id_mappings
```

### **2. State Updates (Event-Driven)**

```
Coordinator fetches new data
       ↓
Speaker.update_from_coordinator_data()
       ↓
Speaker.async_write_entity_states()
       ↓
async_dispatcher_send("wiim_state_updated_{uuid}")
       ↓
All entities for this speaker update automatically
```

### **3. User Actions (Command Flow)**

```
User calls service (e.g., media_player.join)
       ↓
Entity method (e.g., WiiMMediaPlayer.async_join)
       ↓
Speaker method (e.g., Speaker.async_join_group)
       ↓
API calls via WiiMClient
       ↓
Coordinator refresh
       ↓
State update flow (see above)
```

---

## 🎯 **Component Interactions**

### **WiimData ↔ Speaker**

- `WiimData` owns Speaker lifecycle
- `WiimData` provides Speaker lookups
- Speaker registers itself in WiimData

### **Speaker ↔ WiiMCoordinator**

- Speaker gets fresh data from Coordinator
- Speaker triggers Coordinator refreshes
- Coordinator manages polling intervals

### **Speaker ↔ Entities**

- Entities delegate state queries to Speaker
- Entities delegate commands to Speaker
- Speaker notifies entities via events

### **Speaker ↔ WiiMClient**

- Speaker triggers API calls via Client
- Client provides protocol abstraction
- Client handles connection management

---

## 📁 **File Structure**

```
custom_components/wiim/
├── __init__.py              # Integration setup, WiimData creation
├── data.py                  # WiimData, Speaker classes
├── entity.py                # WiimEntity base class
├── coordinator.py           # WiiMCoordinator (polling logic)
├── client.py                # WiiMClient (HTTP API) [renamed from api.py]
├── smart_polling.py         # SmartPollingManager (pure logic)
├── const.py                 # Constants and enums
├── config_flow.py           # Configuration flow
├── strings.json             # UI strings
├── services.yaml            # Service definitions
├── manifest.json            # Integration manifest
│
├── platforms/               # Entity platforms
│   ├── media_player.py      # WiiMMediaPlayer (~200 LOC)
│   ├── sensor.py            # WiiMSensor
│   ├── button.py            # WiiMButton
│   ├── number.py            # WiiMNumber
│   ├── switch.py            # WiiMSwitch
│   └── binary_sensor.py     # WiiMBinarySensor
│
├── services/                # Service implementations
│   ├── media_services.py    # Media control services
│   ├── group_services.py    # Grouping services
│   └── device_services.py   # Device management services
│
└── utils/                   # Utilities
    ├── discovery.py         # Device discovery helpers
    └── exceptions.py        # Custom exceptions
```

---

## ⚡ **Smart Polling Architecture**

### **Polling Tiers**

| Activity Level | Interval | Trigger Conditions                    |
| -------------- | -------- | ------------------------------------- |
| **Active**     | 1s       | Currently playing, recent user action |
| **Recent**     | 5s       | Played within last 5 minutes          |
| **Idle**       | 30s      | No recent activity, groups exist      |
| **Deep Sleep** | 120s     | Solo speaker, no activity             |

### **Integration with Coordinator**

```python
class WiiMCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, client, speaker: Speaker):
        self.speaker = speaker
        self.smart_polling = SmartPollingManager(speaker.uuid)

    async def _async_update_data(self) -> dict:
        # Fetch data
        data = await self.client.get_all_status()

        # Update speaker from data
        self.speaker.update_from_coordinator_data(data)

        # Notify smart polling of activity
        activity_hints = {
            "is_playing": data.get("status", {}).get("state") == "play",
            "recent_user_action": self.speaker.has_recent_user_action(),
            "group_active": len(self.speaker.group_members) > 0
        }

        # Get next interval
        next_interval = self.smart_polling.get_next_interval(activity_hints)
        self.update_interval = timedelta(seconds=next_interval)

        return data
```

---

## 🏃‍♂️ **Group Management Architecture**

### **Group State Model**

```python
# Speaker roles
class SpeakerRole(str, Enum):
    SOLO = "solo"        # Single speaker, no group
    MASTER = "master"    # Group coordinator
    SLAVE = "slave"      # Group member

# Group operations
class Speaker:
    async def async_join_group(self, speakers: list[Speaker]) -> None:
        """
        Join multiple speakers into a group.
        First speaker becomes master, others become slaves.
        """
        master = self  # This speaker becomes master
        slaves = speakers

        # API calls to create group
        for slave in slaves:
            await slave.coordinator.client.join_master(master.ip)

        # Update local state
        master.role = SpeakerRole.MASTER
        master.group_members = [master] + slaves

        for slave in slaves:
            slave.role = SpeakerRole.SLAVE
            slave.coordinator_speaker = master
            slave.group_members = [master] + slaves

        # Notify all entities
        for speaker in [master] + slaves:
            speaker.async_write_entity_states()
```

### **Virtual Group Entity**

```python
class WiiMGroupMediaPlayer(WiimEntity, MediaPlayerEntity):
    """Virtual entity for group control (same device as master)."""

    def __init__(self, speaker: Speaker):
        super().__init__(speaker)  # Same device_info as master!
        self._attr_unique_id = f"{speaker.uuid}_group"

    @property
    def name(self) -> str:
        return f"{self.speaker.name} Group"

    # Group-specific controls
    async def async_join(self, group_members: list[str]) -> None:
        # Add new members to existing group

    async def async_unjoin(self) -> None:
        # Disband entire group
```

---

## 🧪 **Testing Architecture**

### **Test Structure**

```
tests/
├── unit/
│   ├── test_wiim_data.py        # Central registry tests
│   ├── test_speaker.py          # Speaker business logic
│   ├── test_entity.py           # WiimEntity base tests
│   ├── test_coordinator.py      # Coordinator tests
│   ├── test_smart_polling.py    # Polling logic tests
│   └── test_group_management.py # Group scenarios
│
├── integration/
│   ├── test_media_player.py     # Media player entity tests
│   ├── test_setup.py            # Integration setup tests
│   └── test_discovery.py        # Device discovery tests
│
├── fixtures/
│   ├── mock_speakers.py         # Speaker test fixtures
│   ├── mock_api_responses.py    # API response fixtures
│   └── conftest.py              # Pytest configuration
│
└── scenarios/
    ├── test_multiroom.py        # Complex multiroom scenarios
    └── test_error_handling.py   # Error condition tests
```

### **Test Philosophy**

- **Unit tests** for individual components (Speaker, WiimData, etc.)
- **Integration tests** for entity behavior
- **Scenario tests** for complex user workflows
- **Mock API responses** for consistent testing

---

## 📊 **Performance Characteristics**

### **Memory Usage**

| Component | Memory per Speaker   | Notes                       |
| --------- | -------------------- | --------------------------- |
| Speaker   | ~2KB                 | Device state and references |
| WiimData  | ~1KB                 | Registry overhead           |
| Entities  | ~500B each           | Thin wrappers               |
| **Total** | **~4KB per speaker** | Scales linearly             |

### **API Efficiency**

| Operation           | API Calls         | Smart Polling Benefit |
| ------------------- | ----------------- | --------------------- |
| **Idle monitoring** | 1 call/120s       | 90% reduction         |
| **Active playback** | 1 call/1s         | Real-time updates     |
| **Group operation** | 1 call per member | Coordinated updates   |

---

## 🔐 **Error Handling Strategy**

### **Failure Isolation**

- Speaker failures don't affect other speakers
- Entity failures don't affect Speaker state
- Network errors trigger smart backoff

### **Recovery Patterns**

```python
# Speaker-level error handling
class Speaker:
    async def async_handle_error(self, error: Exception) -> None:
        if isinstance(error, ConnectionError):
            self._available = False
            self.async_write_entity_states()  # Update entities
            # Retry with exponential backoff
        elif isinstance(error, APIError):
            # Log and continue with stale data
            pass
```

---

## 🎯 **Migration Strategy**

### **Phase-by-Phase Migration**

1. **Phase 1**: Create new architecture alongside old
2. **Phase 2**: Migrate entities to new base classes
3. **Phase 3**: Move business logic to Speaker
4. **Phase 4**: Delete old device registry
5. **Phase 5**: Clean up legacy code

### **Backward Compatibility**

- Entity names and IDs remain unchanged
- Service APIs remain consistent
- User configuration preserved
- Device registry entries migrated automatically

---

This architecture provides the foundation for a **world-class WiiM integration** that scales from single speakers to complex multiroom setups while maintaining Home Assistant best practices throughout.

## 🔗 **LinkPlay Group Management API**

### **Essential Group Commands**

The WiiM integration uses specific LinkPlay HTTP API commands for group management:

#### **Join Group Command**

```
ConnectMasterAp:JoinGroupMaster:<master_ip>:wifi0.0.0.0
```

- **Purpose**: Makes a device join another device's group as a slave
- **Target**: Send to the slave device's IP
- **Implementation**: `Speaker.async_join_group()`

#### **Leave Group Commands**

```
multiroom:SlaveKickout:<slave_ip>    # Remove slave from group
multiroom:Ungroup                    # Disband entire group
```

- **Purpose**: Remove slaves or disband groups
- **Target**: Send to master device's IP
- **Implementation**: `Speaker.async_leave_group()`

### **Group Management Flow**

1. **Group Join**: Master sends `ConnectMasterAp` to each slave
2. **Group Leave**: Slaves trigger `SlaveKickout`, masters use `Ungroup`
3. **State Updates**: All coordinators refresh after group operations
4. **Entity Updates**: Event system propagates changes to all entities

This LinkPlay API integration provides reliable multiroom functionality while maintaining the Speaker-centric architecture.

## 11. Strategic Refactor (2025-06) - COMPLETED ✅

The integration has been successfully migrated to a **Sonos-style** architecture. The refactoring work has been completed and the integration now follows Home Assistant's premier audio integration patterns.

### **🎯 Refactoring Achievements**

The integration now successfully implements all target architectural patterns:

| **Component**        | **Previous State**    | **Current State (Sonos-style)**              | **Status**  |
| -------------------- | --------------------- | -------------------------------------------- | ----------- |
| **Data Layer**       | Basic device registry | Rich `Speaker` class like `SonosSpeaker`     | ✅ Complete |
| **Entity Base**      | Mixed patterns        | Event-driven `WiimEntity` like `SonosEntity` | ✅ Complete |
| **Media Player**     | 1,762 lines monolith  | 247 lines thin wrapper (like Sonos)          | ✅ Complete |
| **Device Registry**  | Custom 25KB registry  | HA registry only                             | ✅ Complete |
| **Event System**     | None                  | Dispatcher-based (like Sonos)                | ✅ Complete |
| **Group Management** | Scattered logic       | Centralized in `Speaker`                     | ✅ Complete |

### **Architecture Transformation Results**

#### **Speaker-Centric Business Logic**

```python
# Rich Speaker class with complete business logic
class Speaker:
    async def async_join_group(self, speakers: list[Speaker]) -> None:
        """LinkPlay group management with ConnectMasterAp API"""

    def get_playback_state(self) -> MediaPlayerState:
        """Business logic in Speaker, not entity"""

    def async_write_entity_states(self) -> None:
        """Event-driven entity updates"""
```

#### **Thin Entity Wrappers**

```python
# Media Player reduced from 1,762 → 247 lines
class WiiMMediaPlayer(WiimEntity, MediaPlayerEntity):
    @property
    def state(self) -> MediaPlayerState:
        return self.speaker.get_playback_state()  # Delegate to Speaker

    async def async_join(self, group_members: list[str]) -> None:
        speakers = self.speaker.resolve_entity_ids_to_speakers(group_members)
        await self.speaker.async_join_group(speakers)  # Perfect delegation
```

#### **Event-Driven Architecture**

```python
# WiimEntity base provides event-driven updates
class WiimEntity(Entity):
    _attr_should_poll = False  # Zero polling needed

    async def async_added_to_hass(self) -> None:
        async_dispatcher_connect(
            self.hass,
            f"wiim_state_updated_{self.speaker.uuid}",
            self.async_write_ha_state,
        )
```

### **Performance & Quality Improvements**

- **86% Code Reduction**: Media player simplified from 1,762 → 247 lines
- **Zero Entity Polling**: All entities use event-driven updates
- **Perfect Delegation**: All business logic centralized in Speaker class
- **Clean Group Management**: LinkPlay API integration with proper Speaker coordination
- **HA Native Patterns**: Full compliance with Home Assistant device registry patterns

### **Platform Implementation Excellence**

All 6 platforms follow identical architecture patterns:

- **media_player.py** (247 lines) - Core audio control
- **sensor.py** (169 lines) - Device monitoring
- **button.py** (143 lines) - Device management
- **number.py** (174 lines) - Configuration settings
- **switch.py** (211 lines) - Feature toggles
- **binary_sensor.py** (170 lines) - Status monitoring

### **Integration Setup**

```python
# Clean integration setup using new architecture
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Create central registry
    hass.data[DOMAIN]["data"] = WiimData(hass)

    # Create rich Speaker object
    speaker = get_or_create_speaker(hass, device_uuid, coordinator)
    await speaker.async_setup(entry)

    # Platform setup delegates to Speaker
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
```

The refactoring successfully transformed the WiiM integration into a **world-class Home Assistant integration** that serves as a reference implementation for complex audio device integrations, demonstrating best practices in architecture, performance, and maintainability.

## 12. Post-Refactoring Cleanup (2025-06) - IN PROGRESS ⚠️

While the major architectural transformation is complete, some cleanup work is being performed to fully eliminate legacy dependencies and ensure optimal performance.

### **🧹 Current Cleanup Tasks**

#### **Platform File Structure Correction**

**Issue**: Platform files were in a `platforms/` subdirectory but Home Assistant expects them in the root component directory.

**Solution**:

- ✅ Moved all platform files from `platforms/` to root directory
- ✅ Fixed relative imports from `from ..const` to `from .const`
- ✅ Verified all 6 platforms load correctly

**Files affected**:

- `media_player.py`, `sensor.py`, `button.py`, `number.py`, `switch.py`, `binary_sensor.py`

#### **Device Registry Dependency Removal**

**Issue**: Coordinator still references legacy `device_registry.py` despite Speaker-centric architecture being complete.

**Solution**: ✅ **COMPLETE**

- ✅ Removed `device_registry.py` entirely (was 118-line shim, now deleted)
- ✅ Removed all `device_registry` imports and references from coordinator
- ✅ Replaced device registry lookups with Speaker/WiimData equivalents
- ✅ Simplified group validation methods (complex logic moved to Speaker objects)
- ✅ All functionality now handled by Speaker class and WiimData registry

**Key Changes**:

- Coordinator role detection now uses Speaker objects directly
- Group member queries delegate to Speaker.get_group_member_entity_ids()
- Group validation simplified since Speaker objects handle consistency
- IP tracking moved to Speaker-level management
- Zero legacy dependencies remaining

### **🎯 Cleanup Benefits**

After cleanup completion:

- **Cleaner Architecture**: Zero legacy dependencies remaining
- **Better Performance**: Remove unnecessary registry layer overhead
- **Simplified Codebase**: Eliminate duplicate/conflicting state management
- **Full Sonos Alignment**: Complete adherence to reference patterns

### **🔧 Implementation Notes**

The cleanup maintains our core architectural principles:

- **Speaker-Centric Logic**: All business logic remains in Speaker class
- **Event-Driven Updates**: No change to dispatcher-based entity updates
- **Clean Delegation**: Platform entities continue thin wrapper pattern
- **Zero Breaking Changes**: All user-facing functionality preserved

This cleanup work represents the final step in achieving a completely clean, Sonos-inspired architecture with no legacy remnants.

## 🎯 **Entity Filtering System**

### **Overview**

The WiiM integration implements smart entity filtering to avoid overwhelming users with unnecessary diagnostic entities while still providing advanced functionality when needed.

### **Platform Categories**

| Category        | Default   | Description              | Platforms                      |
| --------------- | --------- | ------------------------ | ------------------------------ |
| **Core**        | Always On | Essential functionality  | `media_player`, `number`       |
| **Maintenance** | On        | Device management        | `button`                       |
| **Diagnostic**  | Off       | Advanced troubleshooting | `sensor` (advanced)            |
| **Network**     | Off       | Network monitoring       | `sensor` (IP), `binary_sensor` |
| **Audio**       | Off       | Audio feature controls   | `switch` (EQ)                  |

### **Configuration Options**

Users control entity creation through **Settings → Configure** for each device:

```python
# Configuration constants
CONF_ENABLE_MAINTENANCE_BUTTONS = "enable_maintenance_buttons"    # Default: True
CONF_ENABLE_DIAGNOSTIC_ENTITIES = "enable_diagnostic_entities"    # Default: False
CONF_ENABLE_NETWORK_MONITORING = "enable_network_monitoring"      # Default: False
CONF_ENABLE_EQ_CONTROLS = "enable_eq_controls"                    # Default: False
```

### **Platform Implementation**

Each platform checks user preferences before creating entities:

```python
# Example: sensor.py
async def async_setup_entry(hass, config_entry, async_add_entities):
    speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    entry = hass.data[DOMAIN][config_entry.entry_id]["entry"]

    entities = []

    # Always create essential sensors
    entities.append(WiiMRoleSensor(speaker))  # Most useful for users

    # Optional sensors based on user preferences
    if entry.options.get(CONF_ENABLE_NETWORK_MONITORING, False):
        entities.append(WiiMIPSensor(speaker))

    if entry.options.get(CONF_ENABLE_DIAGNOSTIC_ENTITIES, False):
        entities.extend([
            WiiMActivitySensor(speaker),
            WiiMPollingIntervalSensor(speaker),
        ])
```

### **Entity Reduction Results**

| **Before**                                | **After**                        |
| ----------------------------------------- | -------------------------------- |
| 15 entities per device                    | 3 entities by default            |
| All diagnostic entities visible           | Hidden by default                |
| Internal polling controls exposed         | Removed entirely                 |
| Redundant sensors (playing, group active) | Removed                          |
| Manual refresh button                     | Removed (internal functionality) |

### **Integration Setup with Filtering**

The integration dynamically determines which platforms to load:

```python
# __init__.py
CORE_PLATFORMS = [Platform.MEDIA_PLAYER, Platform.NUMBER]

OPTIONAL_PLATFORMS = {
    CONF_ENABLE_MAINTENANCE_BUTTONS: Platform.BUTTON,
    CONF_ENABLE_DIAGNOSTIC_ENTITIES: Platform.SENSOR,
    CONF_ENABLE_NETWORK_MONITORING: Platform.BINARY_SENSOR,
    CONF_ENABLE_EQ_CONTROLS: Platform.SWITCH,
}

def get_enabled_platforms(entry: ConfigEntry) -> list[Platform]:
    platforms = CORE_PLATFORMS.copy()
    for config_key, platform in OPTIONAL_PLATFORMS.items():
        if entry.options.get(config_key, config_key == CONF_ENABLE_MAINTENANCE_BUTTONS):
            platforms.append(platform)
    return platforms
```

This approach ensures only needed platforms are loaded, reducing resource usage and entity clutter.
