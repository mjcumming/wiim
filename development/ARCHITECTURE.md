# WiiM Integration Architecture Design

## Overview

The WiiM integration follows a **simplified pragmatic architecture** with clear separation of concerns, avoiding over-engineering while maintaining clean code structure.

## Core Design Principles

### 1. Single Responsibility Principle

Each class has ONE clear purpose and handles ONE aspect of the system.

### 2. Separation of Concerns

- **Entity Layer**: HA interface only (thin wrapper)
- **Controller Layer**: **Single controller** handling all media player complexity
- **Business Layer**: Speaker state management and coordination
- **API Layer**: Device communication

### 3. Pragmatic Controller Pattern

**One MediaPlayerController** handles all complex media player functionality, avoiding unnecessary abstraction while maintaining testability.

### 4. Event-Driven Architecture

State changes flow through the system via events, avoiding tight coupling. The integration uses UPnP eventing (following the Samsung/DLNA pattern) for real-time state synchronization with HTTP polling fallback.

### 5. UPnP Eventing Architecture (Samsung/DLNA Pattern)

The integration follows the **Samsung/DLNA UPnP eventing pattern** using `async_upnp_client` for real-time state synchronization:

**Design Pattern Reference:**

- **Primary Pattern**: Samsung/DLNA DMR integration (`homeassistant/components/dlna_dmr/media_player.py`)
- **Library**: `async_upnp_client` with `DmrDevice` wrapper
- **NOT Sonos pattern**: We use `async_upnp_client`, not the Sonos-specific `soco` library

**Architecture:**

1. **UPnP Client** (`upnp_client.py`): Wraps `async_upnp_client` for device communication

   - Creates `DmrDevice` wrapper using SSDP discovery info
   - Manages `AiohttpNotifyServer` for receiving event callbacks
   - Uses `event_handler.async_subscribe()` for individual service subscriptions

2. **UPnP Eventer** (`upnp_eventer.py`): Manages subscription lifecycle

   - Subscribes to AVTransport and RenderingControl services individually
   - Handles subscription renewals (renews at 80% of timeout)
   - Processes NOTIFY events and updates speaker state
   - Gracefully falls back to HTTP polling on failure

3. **State Management**: Centralized state via `WiiMState` dataclass
   - Tracks all UPnP state variables
   - Provides unified interface for entity updates

**Subscription Flow:**

```
Device Discovery (SSDP) → Create UpnpClient → Start NotifyServer →
Subscribe to Services (AVTransport, RenderingControl) →
Receive NOTIFY Events → Update Speaker State → Update HA Entities
```

**Fallback Behavior:**

- If subscription fails → HTTP polling continues (no functionality loss)
- If callbacks unreachable (Docker/WSL) → HTTP polling with clear warnings
- Auto-recovery: Periodically attempts to re-establish subscriptions

**Configuration:**

- Default: `"auto"` (try UPnP, fallback to polling like DLNA DMR/SamsungTV)
- Options: `"upnp"` (force UPnP), `"disabled"` / `"polling_only"` (HTTP polling only)

### 6. Defensive Programming

All operations have graceful fallbacks and error handling.

### 7. File Size Policy (Soft-/Hard-Limit)

To keep modules focused and reviews short we aim for **≤ 300 LOC** per file (excluding comments, blank lines and imports).

- 301-400 LOC → CI issues a size-warning; please consider splitting.
- > 400 LOC → CI fails unless the file begins with `# pragma: allow-long-file <issue>` **and** the PR description justifies why the code cannot be split.

This mirrors the updated cursor_rules.md guidance and will be enforced by the `ruff-size-check` job in GitHub Actions.

## Design Decisions & Exclusions

### Power Control - Intentionally Excluded ⚠️

**Decision**: Power control is **intentionally excluded** from this integration.

**Rationale**:

- WiiM devices have **inconsistent power control implementation** across different models and firmware versions
- Some devices don't support power control via API
- Power states are often unreliable or incorrectly reported
- Physical power buttons and auto-sleep functionality vary significantly between models
- Network connectivity requirements conflict with true "off" states
- Implementing power control would require device-specific workarounds that compromise reliability

**Alternative**: Users should rely on:

- Physical power buttons on devices
- Auto-sleep functionality built into WiiM devices
- Network-level controls (smart switches) if needed
- WiiM's native power management features

This decision prioritizes **reliable core functionality** over potentially problematic power features.

### Speaker Lookup Pattern

```python
# Simple helper functions replace complex registry
def find_speaker_by_uuid(hass: HomeAssistant, uuid: str) -> Speaker | None:
    """Find speaker by UUID using config entry iteration."""
    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, uuid)
    if entry and entry.entry_id in hass.data.get(DOMAIN, {}):
        return get_speaker_from_config_entry(hass, entry)
    return None

def find_speaker_by_ip(hass: HomeAssistant, ip: str) -> Speaker | None:
    """Find speaker by IP address using config entry iteration."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_HOST) == ip:
            return get_speaker_from_config_entry(hass, entry)
    return None
```

### Missing Device Discovery

When speakers detect missing group members, they trigger discovery flows:

```python
async def _trigger_missing_device_discovery(self, device_uuid: str, device_name: str):
    """Trigger discovery flow for missing device."""
    await self.hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY, "unique_id": device_uuid},
        data={
            "device_uuid": device_uuid,
            "device_name": device_name,
            "discovery_source": "missing_device",
        }
    )
```

This creates a config flow where users can provide the IP address for known UUIDs.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    HOME ASSISTANT LAYER                     │
├─────────────────────────────────────────────────────────────┤
│  WiiMMediaPlayer (media_player.py)                         │
│  ├── HA Media Player Interface (THIN)                      │
│  ├── Property Delegation → Controller                      │
│  └── Command Delegation → Controller                       │
├─────────────────────────────────────────────────────────────┤
│                    CONTROLLER LAYER                         │
├─────────────────────────────────────────────────────────────┤
│  MediaPlayerController (media_controller.py)               │
│  ├── Volume Logic (master/slave coordination)              │
│  ├── Playback Logic (master/slave aware)                   │
│  ├── Source Logic (EQ, shuffle, repeat)                    │
│  ├── Group Logic (join/unjoin validation)                  │
│  └── Media Logic (artwork, metadata)                       │
├─────────────────────────────────────────────────────────────┤
│                     BUSINESS LAYER                          │
├─────────────────────────────────────────────────────────────┤
│  Speaker (data.py)                      │
│  ├── Device State Management                               │
│  ├── Group Membership (simple lookup)                     │
│  ├── Role Detection (master/slave/solo)                    │
│  ├── Missing Device Discovery                              │
│  └── State Change Events                                   │
│                                                             │
│  Helper Functions (data.py)                                │
│  ├── find_speaker_by_uuid() - config entry iteration      │
│  ├── find_speaker_by_ip() - config entry iteration        │
│  ├── get_all_speakers() - config entry iteration          │
│  └── update_speaker_ip() - config entry updates           │
├─────────────────────────────────────────────────────────────┤
│                   COORDINATION LAYER                        │
├─────────────────────────────────────────────────────────────┤
│  WiiMCoordinator (coordinator.py + 9 specialized modules)   │
│  ├── coordinator.py              # Main coordinator facade      │
│  ├── coordinator_backoff.py      # Failure handling & backoff   │
│  ├── coordinator_endpoints.py    # API endpoint management     │
│  ├── coordinator_eq.py           # EQ functionality            │
│  ├── coordinator_metadata.py     # Metadata processing         │
│  ├── coordinator_multiroom.py    # Group coordination          │
│  ├── coordinator_normalise.py    # Data normalization          │
│  ├── coordinator_polling.py      # Smart polling (788 LOC)     │
│  └── coordinator_role.py         # Role detection              │
├─────────────────────────────────────────────────────────────┤
│                       API LAYER                             │
├─────────────────────────────────────────────────────────────┤
│  WiiMClient (api.py + 9 specialized modules)               │
│  ├── api.py                    # Main client facade           │
│  ├── api_base.py              # Base functionality           │
│  ├── api_constants.py         # API constants & mappings     │
│  ├── api_device.py            # Device operations            │
│  ├── api_diag.py              # Diagnostics & health         │
│  ├── api_eq.py                # EQ operations                │
│  ├── api_group.py             # Group operations             │
│  ├── api_parser.py            # Response parsing             │
│  ├── api_playback.py          # Playback controls            │
│  └── api_preset.py            # Preset management            │
└─────────────────────────────────────────────────────────────┘
```

## MediaPlayerController Design - **MIXIN-BASED FACADE**

### Architecture Evolution

The MediaPlayerController evolved from a monolithic design to a **mixin-based architecture** for better maintainability and separation of concerns:

✅ **Modular Design**: Functionality split across focused mixins
✅ **Single Responsibility**: Each mixin handles one domain of functionality
✅ **Testable Components**: Each mixin can be tested independently
✅ **Clean Interface**: Unified facade presents clean API to media player entity
✅ **Maintainable**: Natural code boundaries instead of arbitrary size limits

### MediaPlayerController Architecture

```python
class MediaPlayerController(
    MediaControllerCoreMixin,
    MediaControllerGroupMixin,
    MediaControllerMediaMixin,
):
    """Facade controller combining ALL media player complexity through focused mixins.

    This controller facade combines specialized mixins:
    - MediaControllerCoreMixin: Volume, playback, source control
    - MediaControllerGroupMixin: Group management and entity resolution
    - MediaControllerMediaMixin: Media metadata, image handling, advanced features

    Each mixin handles a specific domain of functionality, promoting maintainability
    and testability while presenting a unified interface to the media player entity.
    """
```

### Mixin Architecture

#### MediaControllerCoreMixin (671 LOC)

**Core media player functionality:**

- Volume control with master/slave coordination
- Playback control (play, pause, stop, seek, next/previous)
- Source selection with EQ and mode management
- Shuffle/repeat mode coordination
- Output mode selection (Line Out, Optical, Bluetooth)

#### MediaControllerGroupMixin (182 LOC)

**Group management operations:**

- Join/leave group with validation
- Entity ID to Speaker object resolution
- Group member tracking and relationships
- Master/slave group coordination

#### MediaControllerMediaMixin (313 LOC)

**Media handling and advanced features:**

- Media metadata retrieval (title, artist, album, duration, position)
- Media image handling with SSL support and caching
- Preset playback (1-6 slots, dynamic detection)
- URL playback functionality

### Why Mixin-Based Architecture?

**Benefits over monolithic approach:**

1. **Natural Boundaries**: Each mixin represents a logical domain
2. **Independent Testing**: Mixins can be unit tested separately
3. **Focused Maintenance**: Changes isolated to relevant domains
4. **Clear Dependencies**: Explicit composition over inheritance
5. **Future Extension**: Easy to add new functionality as mixins

**Compared to original monolithic design:**

- **Before**: 886+ LOC single file with mixed concerns
- **After**: 3 focused mixins (182-671 LOC each) + 72 LOC facade
- **Result**: Better maintainability, clearer boundaries, independent testability

### Interface Compatibility

The mixin architecture maintains **100% interface compatibility** with the original design. All public methods remain available through the facade pattern, ensuring seamless integration with the existing media player entity.

## Entity Architecture

### Beyond Media Player: Comprehensive Entity Coverage

The integration provides **10 entity types** beyond the core media player, offering comprehensive device control and monitoring:

#### Core Media Player (1 entity)

- **WiiMMediaPlayer** (`media_player.py`) - Main media playback interface

#### Device Control & Monitoring (9 additional entities)

**Binary Sensors** (`binary_sensor.py`)

- Device connectivity status
- Group membership state
- Playback activity indicators

**Buttons** (`button.py`)

- Preset playback buttons (1-6)
- Device control shortcuts
- Quick action triggers

**Group Media Player** (`group_media_player.py`)

- Multi-device group control
- Synchronized playback across speakers
- Group volume management

**Light** (`light.py`)

- LED brightness control
- Status indicator lighting
- Ambient lighting features

**Number** (`number.py`)

- Volume step configuration
- EQ parameter adjustments
- Custom numeric controls

**Select** (`select.py`)

- Source selection dropdown
- EQ preset selection
- Output mode selection

**Sensors** (`sensor.py`)

- Device temperature
- Network signal strength (RSSI)
- Firmware version info
- Playback statistics

**Switches** (`switch.py`)

- EQ enable/disable toggles
- Audio enhancement switches
- Device feature toggles

**Updates** (`update.py`)

- Firmware update notifications
- Update installation controls
- Version management

### Entity Integration Benefits

This comprehensive entity coverage provides:

- **Full device control** through native HA interfaces
- **Rich device monitoring** with detailed status information
- **User-friendly controls** via HA dashboards and voice assistants
- **Automation triggers** based on device states and events

## Data Flow Architecture

### State Updates (Event-Driven)

```
API Response → Coordinator → Speaker → MediaPlayerController → Entity → HA
     ↓              ↓           ↓              ↓                ↓      ↓
  Parse/Norm    State Mgmt   Business      All Media         Props   UI
                                Logic      Player Logic
```

### User Commands (Command Pattern)

```
HA Service → Entity → MediaPlayerController → Speaker → Coordinator → API
     ↓         ↓              ↓                ↓           ↓           ↓
  Validate   Delegate    All Complex Logic   State       Request    Device
                        (Volume/Group/etc)   Update
```

### WiiMMediaPlayer Entity (THIN WRAPPER)

```python
class WiiMMediaPlayer(WiimEntity, MediaPlayerEntity):
    """Thin HA interface wrapper - delegates everything to controller"""

    def __init__(self, speaker: Speaker):
        super().__init__(speaker)
        self.controller = MediaPlayerController(speaker)

    # ===== PROPERTIES (delegate to controller) =====
    @property
    def volume_level(self) -> float | None:
        return self.controller.get_volume_level()

    @property
    def is_volume_muted(self) -> bool | None:
        return self.controller.is_volume_muted()

    @property
    def state(self) -> MediaPlayerState:
        return self.controller.get_playback_state()

    @property
    def shuffle(self) -> bool | None:
        return self.controller.get_shuffle_state()

    @property
    def repeat(self) -> str | None:
        return self.controller.get_repeat_mode()

    @property
    def sound_mode(self) -> str | None:
        return self.controller.get_sound_mode()

    # ===== COMMANDS (delegate to controller) =====
    async def async_set_volume_level(self, volume: float) -> None:
        await self.controller.set_volume(volume)
        await self._async_execute_command_with_refresh("volume")

    async def async_mute_volume(self, mute: bool) -> None:
        await self.controller.set_mute(mute)
        await self._async_execute_command_with_refresh("mute")

    async def async_media_play(self) -> None:
        await self.controller.play()
        await self._async_execute_command_with_refresh("play")

    async def async_set_shuffle(self, shuffle: bool) -> None:
        await self.controller.set_shuffle(shuffle)
        await self._async_execute_command_with_refresh("shuffle")

    async def async_join(self, group_members: list[str]) -> None:
        await self.controller.join_group(group_members)
        await self._async_execute_command_with_refresh("group")
```

## File Organization

```
wiim/
├── custom_components/wiim/
│   ├── __init__.py                     # Integration setup
│   ├── config_flow.py                  # Configuration flow
│   ├── const.py                        # Constants and mappings
│   │
│   # ===== API LAYER (10 files) =====
│   ├── api.py                          # Main API client facade
│   ├── api_base.py                      # Base API functionality
│   ├── api_constants.py                 # API constants & mappings
│   ├── api_device.py                    # Device operations
│   ├── api_diag.py                      # Diagnostics & health
│   ├── api_eq.py                        # EQ operations
│   ├── api_group.py                     # Group operations
│   ├── api_parser.py                    # Response parsing
│   ├── api_playback.py                  # Playback controls
│   ├── api_preset.py                    # Preset management
│   │
│   # ===== COORDINATION LAYER (10 files) =====
│   ├── coordinator.py                    # Main coordinator facade
│   ├── coordinator_backoff.py            # Failure handling & backoff
│   ├── coordinator_endpoints.py          # API endpoint management
│   ├── coordinator_eq.py                 # EQ functionality
│   ├── coordinator_metadata.py           # Metadata processing
│   ├── coordinator_multiroom.py          # Group coordination
│   ├── coordinator_normalise.py          # Data normalization
│   ├── coordinator_polling.py            # Smart polling (788 LOC)
│   ├── coordinator_role.py               # Role detection
│   │
│   # ===== BUSINESS LAYER (5 files) =====
│   ├── data.py                         # Speaker management & business logic
│   ├── data_helpers.py                 # Helper functions (lookup utilities)
│   ├── models.py                       # Pydantic models for typed data-flow
│   ├── entity.py                       # Base entity class
│   ├── firmware_capabilities.py        # Device capability detection
│   │
│   # ===== MEDIA PLAYER LAYER (7 files) =====
│   ├── media_player.py                 # HA interface (THIN wrapper)
│   ├── media_controller.py             # Controller facade (MIXIN-BASED)
│   ├── media_controller_core.py        # Core media functionality (671 LOC)
│   ├── media_controller_group.py       # Group management (182 LOC)
│   ├── media_controller_media.py       # Media handling (313 LOC)
│   ├── media_image_cache.py            # Image caching utilities
│   ├── media_player_browser.py         # Media browsing support
│   │
│   # ===== ADDITIONAL ENTITY TYPES (9 files) =====
│   ├── binary_sensor.py                # Binary sensors (connectivity, etc.)
│   ├── button.py                       # Control buttons (presets, etc.)
│   ├── group_media_player.py           # Group media player entity
│   ├── light.py                        # LED controls
│   ├── number.py                       # Numeric controls
│   ├── select.py                       # Selection controls (sources, EQ)
│   ├── sensor.py                       # Device sensors
│   ├── switch.py                       # Toggle switches
│   ├── update.py                       # Firmware update entity
│   │
│   # ===== UTILITIES & SERVICES (6 files) =====
│   ├── services/                       # Service registration
│   │   ├── __init__.py
│   │   ├── media.py                   # Media services
│   │   └── device.py                  # Device services
│   ├── system_health.py                # Home Assistant system health
│   ├── diagnostics.py                   # Debug diagnostics
│   ├── media_player_commands.py        # Command processing
│   │
│   # ===== TESTS & CONFIGURATION =====
│   ├── tests/                          # Comprehensive test coverage
│   │   ├── unit/                       # Unit tests
│   │   ├── integration/               # Integration tests
│   │   └── conftest.py                 # Test configuration
│   ├── manifest.json                   # Integration manifest
│   ├── services.yaml                   # Service definitions
│   ├── strings.json                    # Translation strings
│   └── translations/                   # UI translations
```

This architecture provides:
✅ **Modular design** with clear separation of concerns across 40+ focused files
✅ **Mixin-based composition** for maintainable and testable media player logic
✅ **Smart polling** with adaptive intervals (1s playing → 5s idle → 60s health checks)
✅ **Typed data-flow** with comprehensive Pydantic models and validation
✅ **Performance optimization** with threading patterns for heavy operations
✅ **Standard HA patterns** throughout (config entries as source of truth)
✅ **Simple speaker management** using config entry iteration (no custom registries)
✅ **Automatic discovery** for missing group devices via integration flows
✅ **Comprehensive entity coverage** with 10 entity types beyond basic media player
✅ **Advanced features** including group management, EQ controls, and preset playback

## Typed Data-Flow with Pydantic Models

### Comprehensive Model Architecture

All API payloads are parsed into **strongly-typed Pydantic models** for robust data handling and validation:

#### Core Models (`models.py`)

```python
# Device Information
DeviceInfo          # getStatusEx responses (name, firmware, capabilities)
PlayerStatus        # getPlayerStatus responses (playback, volume, metadata)
SlaveInfo          # Multiroom slave device information
MultiroomInfo      # Complete multiroom group state

# Enhanced Metadata
TrackMetadata      # Rich track information (artwork, genres, etc.)
EQInfo            # EQ presets and current settings
PollingMetrics    # Performance and health metrics
```

#### Model Benefits

✅ **Type Safety**: Compile-time validation of API responses
✅ **Field Validation**: Automatic data normalization and validation
✅ **Future-Proof**: Extra fields allowed for firmware compatibility
✅ **Documentation**: Self-documenting data structures
✅ **Performance**: Efficient serialization with `model_dump()`

### Data Flow Pipeline

1. **API Layer** (`api_*.py` modules)

   - Raw HTTP responses → Pydantic models
   - Automatic field validation and normalization
   - Error handling for malformed responses

2. **Coordination Layer** (`coordinator_*.py` modules)

   - Model enrichment with derived data
   - State management and caching
   - Cross-device coordination logic

3. **Business Layer** (`data.py`, `data_helpers.py`)

   - Speaker relationship management
   - Entity registry coordination
   - Group state synchronization

4. **Entity Layer** (all `*.py` entity files)
   - Model consumption for HA state
   - Type-safe property access
   - Event-driven state updates

### Validation Features

**Field Validators**:

- Source normalization (`spotify` → `spotify`)
- Duration handling (0 → None for streaming)
- EQ preset validation (dict → string)
- Play state normalization (`none` → `idle`)

**Configuration**:

- `extra="allow"` for firmware compatibility
- `populate_by_name=True` for flexible field access
- Field aliases for API key mapping

**Error Handling**:

- Graceful fallbacks for missing fields
- Legacy device compatibility
- Comprehensive validation logging

## Smart Polling Strategy

### Advanced Multi-Tier Polling Architecture

The WiiM integration implements a sophisticated **multi-tier polling system** that dynamically adapts to device state, user activity, and firmware capabilities:

### Polling Frequency Matrix

| Data Type          | Frequency                             | Trigger                    | Rationale                                          |
| ------------------ | ------------------------------------- | -------------------------- | -------------------------------------------------- |
| **Player Status**  | 1s playing → 5s idle → 5s after 10min | Adaptive                   | Real-time position updates during active listening |
| **Multiroom Info** | 15s + on activity                     | Time + track/source change | Role detection, users group via app/voice          |
| **Device Info**    | 60s                                   | Health check only          | Static data (name, model, firmware)                |
| **Metadata**       | On track change                       | Track/source change        | Only if supported, many devices fail this          |
| **EQ Status**      | With device info                      | 60s                        | Settings change infrequently                       |
| **EQ Presets**     | Startup only                          | Once                       | Firmware-defined, never change                     |
| **Radio Presets**  | Startup only                          | Once                       | Users rarely modify during sessions                |

### Adaptive Player Status Polling

```python
def _determine_adaptive_interval(coordinator, status_model: PlayerStatus, role: str) -> int:
    """Smart polling interval based on playback state and activity.

    Strategy:
    - 1s when actively playing (real-time position updates)
    - 5s when idle/paused
    - 5s after 10 minutes of no activity (prevent endless fast polling)
    """
    is_playing = str(status_model.play_state or "").lower() in ("play", "playing", "load")

    # Extended idle timeout (10+ minutes) prevents endless fast polling
    if coordinator._last_playing_time:
        idle_duration = time.time() - coordinator._last_playing_time
        if idle_duration > 600:  # 10 minutes
            is_playing = False

    return 1 if is_playing else 5  # seconds
```

### Conditional Data Fetching

````python
async def async_update_data(coordinator) -> dict[str, Any]:
    """Smart polling implementation with optimized frequency per data type."""

    # ALWAYS: Player Status (adaptive frequency)
    status_model = await fetch_player_status(coordinator.client)

    # CONDITIONAL: Based on timing and activity
    fetch_tasks = []

    # Device info (health check - every 60s)
    if _should_update_device_info(coordinator):
        fetch_tasks.append(fetch_device_info(coordinator.client))

    # Multiroom (role detection - 15s + on activity)
    if _should_update_multiroom(coordinator, track_changed):
        fetch_tasks.append(coordinator._fetch_multiroom_info())

    # Metadata (only on track change, if supported)
    if track_changed and coordinator._metadata_supported is not False:
        fetch_tasks.append(coordinator._fetch_track_metadata(status_model))

    # Execute conditional fetches in parallel

## Coordinator Performance Optimization

### Threading Pattern for Heavy Operations

The WiiM coordinator implements a **4-phase optimization pattern** to eliminate asyncio warnings (>100ms operations) while maintaining event loop responsiveness:

#### Phase 1: Fast HTTP Calls (Main Thread)
```python
# Quick HTTP requests with minimal processing
status_raw = await coordinator.client.get_player_status()
fetch_tasks = [coordinator.client.get_device_info(), ...]
results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
````

#### Phase 2: Quick Result Processing (Main Thread)

```python
# Simple assignments and error handling - no heavy operations
raw_data = {"status_raw": status_raw}
if isinstance(results[idx], Exception):
    # Handle errors quickly
else:
    raw_data["device_raw"] = results[idx]
```

#### Phase 3: Heavy Processing (Background Thread Pool)

```python
# Offload CPU-intensive operations to thread pool
processed_data = await asyncio.to_thread(_process_heavy_operations, raw_data)

# With fallback for older Python versions
with ThreadPoolExecutor(max_workers=1) as executor:
    processed_data = await hass.loop.run_in_executor(executor, func, data)
```

#### Phase 4: Light Final Assembly (Main Thread)

```python
# Quick data structure assembly using pre-processed results
data = {
    "status_model": processed_data.get("status_model"),
    "device_model": processed_data.get("device_model"),
    # ... other fields
}
```

### Heavy Operations Moved to Thread Pool

The following CPU-intensive operations are processed in background threads:

- **Pydantic Model Validation**: `PlayerStatus.model_validate(raw_data)`
- **Model Serialization**: `model.model_dump(exclude_none=True)`
- **Device Info Normalization**: Complex data transformations
- **Metadata Processing**: Large JSON structure manipulation

### Performance Benefits

- **HTTP Operations**: ~10-30ms (main thread)
- **Heavy Processing**: 50-100ms+ (background thread)
- **Event Loop Impact**: Only HTTP time (eliminates asyncio warnings)

### Standard HA Pattern

This follows established Home Assistant coordinator patterns:

- `hass.async_add_executor_job()` - Standard for blocking operations
- `asyncio.to_thread()` - Modern Python 3.9+ approach
- `ThreadPoolExecutor` with `run_in_executor()` - Full control option

Used extensively in core integrations: Venstar, Tado, NextBus, Canary, etc.

### Performance Logging

```python
coordinator._last_response_time = (time.perf_counter() - _start_time) * 1000.0
_LOGGER.debug(
    "=== OPTIMIZED UPDATE SUCCESS for %s (%.1fms total: %.1fms HTTP + %.1fms processing) ===",
    coordinator.client.host,
    coordinator._last_response_time,
    http_time,
    heavy_time,
)
```

    if fetch_tasks:
        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

```

### Key Benefits

- **80% reduction** in unnecessary API calls during idle periods
- **Real-time responsiveness** during active playback (1s position updates)
- **Smart capability detection** - stop trying unsupported endpoints
- **Activity-triggered updates** - fresh data when users interact
- **Graceful degradation** - existing data used when calls skipped
- **10-minute idle timeout** - prevents endless fast polling on paused content

### User Experience Focus

The polling strategy prioritizes **user experience scenarios**:

1. **Active listening** - 1s polling for smooth position tracking
2. **Group management** - Quick role detection when users group speakers
3. **Source switching** - Fresh metadata when changing inputs
4. **Extended idle** - Reduced polling when device unused for 10+ minutes
5. **Device health** - Regular connectivity checks without spam

This approach delivers responsive UI updates while being respectful of device resources and network bandwidth.

## Cursor AI Development Guidance

### Current Implementation Overview

**File Structure (40+ files)**:
```

custom*components/wiim/
├── api.py + 9 specialized API modules (api*\_.py)
├── coordinator.py + 9 coordinator modules (coordinator\_\_.py)
├── media*controller.py + 3 mixins (media_controller*\*.py)
├── 10 entity types (binary_sensor.py, button.py, etc.)
├── models.py (Pydantic models for typed data-flow)
├── data.py + data_helpers.py (business logic)
└── 40+ total files with clear separation of concerns

````

### Key Architectural Patterns

**1. Mixin-Based Media Controller**:
```python
class MediaPlayerController(
    MediaControllerCoreMixin,    # Volume, playback, source (671 LOC)
    MediaControllerGroupMixin,   # Group management (182 LOC)
    MediaControllerMediaMixin    # Metadata, artwork (313 LOC)
):
    """Facade pattern providing unified interface to complex functionality"""
````

**2. Multi-Coordinator Architecture**:

- `coordinator.py` - Main coordinator facade
- `coordinator_polling.py` - Smart polling (788 LOC, adaptive intervals)
- `coordinator_backoff.py` - Failure handling
- `coordinator_metadata.py` - Metadata processing
- 6+ specialized coordinator modules

**3. Typed Data-Flow**:

- All API responses → Pydantic models (`models.py`)
- Field validation and normalization
- `extra="allow"` for firmware compatibility
- Automatic model serialization with `model_dump()`

### Implementation Guidelines

**File Organization**:

- Keep modules focused: 300-600 LOC per file (natural boundaries)
- One responsibility per class/module
- Use composition over inheritance (mixin pattern)
- Clear naming: `MediaControllerCoreMixin`, not `CoreMediaController`

**API Integration**:

- WiiM devices: Full feature set with HTTPS support
- Legacy LinkPlay: Graceful degradation and compatibility mode
- Smart capability detection (don't try unsupported endpoints)
- Defensive programming with comprehensive error handling

**State Management**:

- Config entries as source of truth (no custom registries)
- Event-driven updates via dispatcher signals
- Speaker lookup via `find_speaker_by_uuid()` helpers
- Missing device discovery through integration flows

**Testing Strategy**:

- Unit tests: Mock HTTP with `respx`, use snapshot JSONs
- Integration tests: HA test harness, verify entity states
- Group tests: Multi-device scenarios with synchronization
- Coverage target: ≥90%

**Development Workflow**:

- `make validate` - Check refactor integrity before commits
- `make test` - Run full test suite
- `make pre-commit` - All validation checks
- Use validation scripts in `/scripts/` for systematic checks

### Common Patterns & Anti-Patterns

**✅ DO**:

- Use existing coordinator modules for data access
- Implement proper error handling with graceful fallbacks
- Add comprehensive logging for debugging
- Follow Pydantic model patterns for data validation
- Use mixin composition for complex functionality

**❌ AVOID**:

- Direct API calls from entities (use coordinator data)
- Hard-coded device assumptions (use capability detection)
- Monolithic files >600 LOC (split at natural boundaries)
- Raw dict manipulation (use typed models)
- Blocking operations in event loop (use threading)

### Performance Considerations

**Smart Polling**:

- 1s during playback, 5s idle, 60s health checks
- Activity-triggered updates for responsive UI
- Firmware-aware intervals (legacy devices get conservative polling)

**Threading**:

- HTTP operations in main thread (~10-30ms)
- Heavy processing in background threads (50-100ms)
- 4-phase optimization pattern eliminates asyncio warnings

**Memory Management**:

- Image caching with automatic cleanup
- Connection pooling via aiohttp sessions
- Graceful degradation for resource-constrained devices

### Integration Points

**Home Assistant Integration**:

- Standard config entry pattern
- Entity registry for device management
- Service registration for custom functionality
- Translation strings for multi-language support

**Multi-Device Coordination**:

- Master/slave role detection via API
- Group state synchronization
- Automatic discovery for missing devices
- Cross-device volume coordination

This guidance ensures AI development assistants understand the current sophisticated architecture and can contribute effectively to the codebase.

## Logging Guidelines - Home Assistant Compliance

### Core Logging Principles

The integration follows **Home Assistant's standard logging patterns** for consistency, performance, and user experience.

#### 1. Logger Naming

✅ **Correct Pattern**:

```python
import logging

_LOGGER = logging.getLogger(__name__)
```

Each module uses its own logger based on module name, following HA's standard pattern.

#### 2. Lazy Logging (Performance)

✅ **Correct Pattern** (avoids string formatting when logging disabled):

```python
_LOGGER.debug("Processing data for %s: %s", device_name, data)
```

❌ **Avoid** (always formats string, even when DEBUG disabled):

```python
_LOGGER.debug(f"Processing data for {device_name}: {data}")  # BAD
```

#### 3. Conditional Expensive Logging

For expensive operations (large dicts, complex formatting), check if DEBUG is enabled first:

✅ **Correct Pattern**:

```python
if _LOGGER.isEnabledFor(logging.DEBUG):
    _LOGGER.debug("Full HTTP response: %s", large_dict)
```

This prevents expensive operations when DEBUG logging is disabled.

**Example from `coordinator.py`**:

```python
# Log full result if DEBUG is enabled, otherwise just keys
if _LOGGER.isEnabledFor(logging.DEBUG):
    _LOGGER.debug("Player status result for %s: %s", self.client.host, result)
else:
    _LOGGER.debug("Player status result for %s (keys=%s)", self.client.host, list(result.keys()))
```

#### 4. Log Levels

Use appropriate log levels following HA conventions:

- **DEBUG**: Detailed diagnostic information (raw API responses, state transitions, internal decisions)
- **INFO**: Significant events (device connection, state changes, user actions)
- **WARNING**: Recoverable issues (fallback to polling, retry attempts, deprecated features)
- **ERROR**: Unrecoverable errors (API failures, configuration issues)

#### 5. Raw HTTP Response Logging

Log raw HTTP responses for debugging API issues:

✅ **Correct Pattern** (from `api_base.py`):

```python
raw = await self._request(endpoint)
if _LOGGER.isEnabledFor(logging.DEBUG):
    _LOGGER.debug(
        "HTTP response from %s for %s: %s",
        endpoint,
        self.host,
        raw,
    )
```

This provides visibility into raw API data before parsing/validation.

#### 6. Logging When Operations Are Skipped

Log both success AND skip cases for debugging:

✅ **Correct Pattern** (from `api_parser.py`):

```python
if (mode_val := raw.get("mode")) is not None:
    current_source = data.get("source")
    if not current_source or current_source in ("unknown", "wifi", ""):
        # ... mapping logic ...
        _LOGGER.debug("Mapped mode %s to source '%s'", mode_val, mapped_source)
    else:
        _LOGGER.debug(
            "Skipping mode-to-source mapping: mode=%s, source already set to '%s'",
            mode_val,
            current_source,
        )
```

This helps diagnose why operations didn't execute as expected.

#### 7. State Merge Decision Logging

Log state merging decisions with context:

✅ **Correct Pattern** (from `data.py`):

```python
upnp_healthy = not self.check_upnp_available
_LOGGER.debug(
    "UPnP state merge for %s: check_upnp_available=%s, upnp_healthy=%s, upnp_play_state=%s",
    self.name,
    self.check_upnp_available,
    upnp_healthy,
    upnp_state.play_state if upnp_state else None,
)
```

This provides visibility into state merging logic and UPnP health status.

#### 8. Message Format Guidelines

Follow HA's message format conventions:

- ✅ No periods at end of messages
- ✅ No integration names/domains in messages (logger name provides context)
- ✅ No sensitive data (passwords, tokens, etc.)
- ✅ Use descriptive variable names in format strings

#### 9. What NOT to Do

❌ **Avoid Custom Verbosity Flags**:

```python
# BAD - Don't create custom flags
VERBOSE_DEBUG = False
if VERBOSE_DEBUG:
    _LOGGER.debug("...")
```

✅ **Use Standard HA Logging Configuration**:
Users control verbosity via HA's standard logging configuration (logger.yaml or Developer Tools → Services → `logger.set_level`).

#### 10. Performance Considerations

- **Lazy logging**: Always use format strings, not f-strings
- **Conditional expensive logging**: Check `isEnabledFor(logging.DEBUG)` before expensive operations
- **Appropriate log levels**: Don't log at DEBUG in hot paths unless necessary

### Logging Examples in Codebase

**Raw HTTP Response Logging** (`api_base.py`):

```python
raw = await self._request(endpoint)
if _LOGGER.isEnabledFor(logging.DEBUG):
    _LOGGER.debug("HTTP response from %s for %s: %s", endpoint, self.host, raw)
```

**Operation Skip Logging** (`api_parser.py`):

```python
_LOGGER.debug(
    "Skipping mode-to-source mapping: mode=%s, source already set to '%s'",
    mode_val,
    current_source,
)
```

**State Merge Logging** (`data.py`):

```python
_LOGGER.debug(
    "UPnP state merge for %s: check_upnp_available=%s, merging play_state=%s",
    self.name,
    self.check_upnp_available,
    upnp_state.play_state if upnp_state else None,
)
```

### Summary

✅ **We follow HA logging patterns**:

- Module-specific loggers via `logging.getLogger(__name__)`
- Lazy logging with format strings
- Appropriate log levels (DEBUG/INFO/WARNING/ERROR)
- Conditional expensive logging with `isEnabledFor()`
- Raw HTTP response logging for debugging
- Skip case logging for troubleshooting
- No custom verbosity flags

All logging is user-configurable via Home Assistant's standard logging configuration.
