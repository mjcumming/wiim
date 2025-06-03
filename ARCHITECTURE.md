# WiiM Integration Architecture Design v2.1 - SIMPLIFIED

## Overview

The WiiM integration follows a **pragmatic layered architecture** with clear separation of concerns, avoiding over-engineering while maintaining clean code structure.

## Core Design Principles

### 1. Single Responsibility Principle
Each class has ONE clear purpose and handles ONE aspect of the system.

### 2. Separation of Concerns - **SIMPLIFIED**
- **Entity Layer**: HA interface only (thin wrapper)
- **Controller Layer**: **Single controller** handling all media player complexity
- **Business Layer**: Speaker state management and coordination
- **API Layer**: Device communication

### 3. Pragmatic Controller Pattern
**One MediaPlayerController** handles all complex media player functionality, avoiding unnecessary abstraction while maintaining testability.

### 4. Event-Driven Architecture
State changes flow through the system via events, avoiding tight coupling.

### 5. Defensive Programming
All operations have graceful fallbacks and error handling.

## Simplified Architecture Layers

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
│  ├── Power Logic (on/off/toggle)                           │
│  └── Media Logic (artwork, metadata)                       │
├─────────────────────────────────────────────────────────────┤
│                     BUSINESS LAYER                          │
├─────────────────────────────────────────────────────────────┤
│  Speaker (data.py)                                         │
│  ├── Device State Management                               │
│  ├── Group Membership                                      │
│  ├── Role Detection (master/slave/solo)                    │
│  └── State Change Events                                   │
├─────────────────────────────────────────────────────────────┤
│                   COORDINATION LAYER                        │
├─────────────────────────────────────────────────────────────┤
│  WiiMCoordinator (coordinator.py)                          │
│  ├── Adaptive Polling (1s playing, 5s idle)               │
│  ├── API Capability Detection                              │
│  ├── State Normalization                                   │
│  └── Error Recovery                                        │
├─────────────────────────────────────────────────────────────┤
│                       API LAYER                             │
├─────────────────────────────────────────────────────────────┤
│  WiiMClient (api.py)                                       │
│  ├── Protocol Detection (HTTP/HTTPS)                       │
│  ├── Request/Response Handling                             │
│  ├── Error Handling                                        │
│  └── Session Management                                     │
└─────────────────────────────────────────────────────────────┘
```

## MediaPlayerController Design - **SINGLE CONTROLLER**

### Why Single Controller?

✅ **Right Balance**: Separates complexity without over-abstraction
✅ **Maintainable**: All media player logic in one place
✅ **Testable**: Can unit test complex logic separately from HA entity
✅ **Understandable**: New developers find everything in one file
✅ **Faster**: Less files, less indirection, easier debugging

### MediaPlayerController Interface

```python
class MediaPlayerController:
    """Single controller handling ALL media player complexity.

    This controller encapsulates:
    - Volume management with master/slave coordination
    - Playback control with group awareness
    - Source selection with EQ and mode management
    - Group operations with validation and state sync
    - Power control with device coordination
    - Media metadata and artwork handling
    """

    def __init__(self, speaker: Speaker):
        self.speaker = speaker
        self.hass = speaker.hass

    # ===== VOLUME CONTROL =====
    async def set_volume(self, volume: float) -> None:
        """Set volume with master/slave logic"""

    async def set_mute(self, mute: bool) -> None:
        """Set mute with master/slave logic"""

    async def volume_up(self, step: float = None) -> None:
        """Volume up with configurable step"""

    async def volume_down(self, step: float = None) -> None:
        """Volume down with configurable step"""

    def get_volume_level(self) -> float | None:
        """Get effective volume (master/slave aware)"""

    def is_volume_muted(self) -> bool | None:
        """Get effective mute state (master/slave aware)"""

    # ===== PLAYBACK CONTROL =====
    async def play(self) -> None:
        """Start playback (master/slave aware)"""

    async def pause(self) -> None:
        """Pause playback (master/slave aware)"""

    async def stop(self) -> None:
        """Stop playback"""

    async def next_track(self) -> None:
        """Next track (master/slave aware)"""

    async def previous_track(self) -> None:
        """Previous track (master/slave aware)"""

    async def seek(self, position: float) -> None:
        """Seek to position"""

    def get_playback_state(self) -> MediaPlayerState:
        """Get current playback state"""

    # ===== SOURCE & AUDIO CONTROL =====
    async def select_source(self, source: str) -> None:
        """Select source, handle slave group leaving"""

    async def set_eq_preset(self, preset: str) -> None:
        """Set EQ preset"""

    async def set_shuffle(self, shuffle: bool) -> None:
        """Set shuffle mode with repeat coordination"""

    async def set_repeat(self, repeat: str) -> None:
        """Set repeat mode (off/one/all)"""

    def get_source_list(self) -> list[str]:
        """Get sources (master/slave aware)"""

    def get_current_source(self) -> str | None:
        """Get current source (master/slave aware)"""

    def get_shuffle_state(self) -> bool | None:
        """Get shuffle state"""

    def get_repeat_mode(self) -> str | None:
        """Get repeat mode"""

    def get_sound_mode_list(self) -> list[str]:
        """Get available EQ presets"""

    def get_sound_mode(self) -> str | None:
        """Get current EQ preset"""

    # ===== GROUP MANAGEMENT =====
    async def join_group(self, group_members: list[str]) -> None:
        """HA native join with WiiM multiroom backend"""

    async def leave_group(self) -> None:
        """Leave current group"""

    def get_group_members(self) -> list[str]:
        """Get group member entity IDs"""

    def get_group_leader(self) -> str | None:
        """Get group leader entity ID"""

    # ===== POWER CONTROL =====
    async def turn_on(self) -> None:
        """Turn device on"""

    async def turn_off(self) -> None:
        """Turn device off"""

    async def toggle_power(self) -> None:
        """Toggle power state"""

    def is_powered_on(self) -> bool:
        """Get power state"""

    # ===== MEDIA METADATA =====
    async def get_media_image(self) -> tuple[bytes, str] | None:
        """Get album artwork with SSL handling"""

    def get_media_title(self) -> str | None:
        """Get clean track title"""

    def get_media_artist(self) -> str | None:
        """Get clean artist name"""

    def get_media_album(self) -> str | None:
        """Get clean album name"""

    def get_media_duration(self) -> int | None:
        """Get track duration"""

    def get_media_position(self) -> int | None:
        """Get current position"""

    def get_media_position_updated_at(self) -> float | None:
        """Get position update timestamp"""

    def get_media_image_url(self) -> str | None:
        """Get media image URL"""

    # ===== ADVANCED FEATURES =====
    async def play_preset(self, preset: int) -> None:
        """Play preset (1-6)"""

    async def play_url(self, url: str) -> None:
        """Play URL"""

    async def browse_media(self, media_content_type=None, media_content_id=None):
        """Browse media for presets"""
```

## Data Flow Architecture - **SIMPLIFIED**

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

## File Organization - **SIMPLIFIED**

```
wiim/
├── custom_components/wiim/
│   ├── __init__.py                     # Integration setup
│   ├── config_flow.py                  # Configuration flow
│   ├── const.py                        # Constants and mappings
│   │
│   ├── api.py                          # ✅ API layer (existing)
│   ├── coordinator.py                  # ✅ Coordination layer (existing)
│   ├── data.py                         # ✅ Business layer (existing)
│   ├── entity.py                       # ✅ Base entity (existing)
│   │
│   ├── media_player.py                 # 🔄 HA interface (THIN - delegates to controller)
│   ├── media_controller.py             # 🆕 NEW: ALL media player logic (single file)
│   │
│   ├── services/                       # 🔄 Service registration
│   │   ├── __init__.py
│   │   ├── media.py                   # Media services
│   │   └── device.py                  # Device services
│   │
│   └── tests/                          # 🔄 Test coverage
│       ├── unit/
│       │   ├── test_media_controller.py  # Controller unit tests
│       │   └── test_media_player.py      # Entity integration tests
│       ├── integration/
│       └── conftest.py
```

## Implementation Benefits

### What We Gain ✅
- **Separation of Concerns**: Entity focuses on HA interface, controller on complex logic
- **Testability**: Can unit test controller logic separately from HA entity
- **Maintainability**: All media player complexity in one well-organized file
- **Performance**: No unnecessary abstraction layers or complex delegation chains
- **Debuggability**: One place to look for media player issues

### What We Avoid ❌
- **Over-abstraction**: No unnecessary controller hierarchies
- **Over-engineering**: No complex factory patterns or event systems
- **Maintenance Overhead**: No multiple small files for simple functionality
- **Performance Overhead**: No deep delegation chains

## Next Steps

This simplified architecture provides:
✅ **Clear separation** without over-engineering
✅ **Testable components** with practical boundaries
✅ **Maintainable codebase** with logical organization
✅ **Fast implementation** with minimal abstraction
✅ **Easy debugging** with centralized logic

The single controller pattern gives us all the benefits of separation while avoiding unnecessary complexity.
