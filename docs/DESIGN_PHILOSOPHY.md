# WiiM Integration – Design Philosophy & Principles

> **Goal**: Document the core design decisions, principles, and philosophical choices that guide our WiiM integration architecture.

---

## 🎯 **Core Design Philosophy**

### **"Sonos-Inspired, Home Assistant Native"**

We're building a **world-class audio integration** that follows Home Assistant's premier audio integration (Sonos) while being perfectly tailored for WiiM/LinkPlay devices.

---

## 🏗️ **Architectural Principles**

### **1. Single Source of Truth Pattern**

- **One central data registry** (`WiimData`) owns all speaker state
- **No duplicate registries** - eliminate conflicts with HA's device registry
- **UUID-based identification** - stable, immutable speaker identity

```python
# Central truth: hass.data[DOMAIN].speakers[uuid] = Speaker()
WiimData.speakers: dict[str, Speaker]  # UUID → Speaker mapping
```

### **2. Rich Domain Objects**

- **Business logic lives in `Speaker`** class, not entities
- **Entities are thin UI adapters** that delegate to Speaker
- **Smart objects, dumb views** pattern

```python
# Rich Speaker with business logic (like SonosSpeaker)
class Speaker:
    async def async_join_group(self, speakers: list[Speaker]) -> None:
        # All group logic here, not in entities

# Thin entity that delegates
class WiiMMediaPlayer(WiimEntity, MediaPlayerEntity):
    async def async_join(self, group_members: list[str]) -> None:
        speakers = self.speaker.resolve_entity_ids(group_members)
        await self.speaker.async_join_group(speakers)  # Delegate!
```

### **3. Event-Driven Architecture**

- **Dispatcher-based communication** between Speaker ↔ Entities
- **No tight coupling** - components communicate through events
- **State changes cascade automatically**

```python
# Speaker notifies all entities when state changes
def async_write_entity_states(self) -> None:
    async_dispatcher_send(self.hass, f"wiim_state_updated_{self.uuid}")

# Entities listen for their speaker's events
async def async_added_to_hass(self) -> None:
    async_dispatcher_connect(self.hass, f"wiim_state_updated_{self.speaker.uuid}", self.async_write_ha_state)
```

### **4. Clean Separation of Concerns**

Each component has **one clear responsibility**:

| Component         | Responsibility                                 |
| ----------------- | ---------------------------------------------- |
| `Speaker`         | Device state, business logic, group management |
| `WiimEntity`      | HA entity interface, event handling            |
| `WiiMCoordinator` | Data fetching, smart polling                   |
| `WiiMClient`      | HTTP/API communication                         |
| `WiimData`        | Central registry, speaker lifecycle            |

### **5. Home Assistant Native Patterns**

- **Use HA's device registry** - no custom device management
- **Follow HA entity patterns** - proper inheritance, state management
- **Leverage HA's coordinator pattern** - clean data updates
- **Use HA's service registration** - proper service delegation

### **6. User-Centric Entity Design**

- **Minimize cognitive load** - users should see only what they need
- **Optional advanced features** - power users can enable diagnostics
- **Clear entity purpose** - every entity should solve a real user problem
- **No internal implementation details** - hide polling, debugging, refresh controls

```python
# BAD: Exposing internal functionality to users
class WiiMRefreshButton(ButtonEntity):
    """Manual refresh button for immediate state updates."""
    # Forces coordinator refresh - internal implementation detail

class WiiMSmartPollingSwitch(SwitchEntity):
    """Smart polling enable/disable switch."""
    # Exposes optimization internals to users

# GOOD: Only user-facing functionality
class WiiMRoleSensor(SensorEntity):
    """Shows 'Not Grouped', 'Master', or 'Slave'."""
    # Solves real user need: understanding multiroom status

class WiiMRebootButton(ButtonEntity):
    """Device reboot for troubleshooting."""
    # Useful maintenance action users actually need
```

### **Entity Filtering Strategy**

**PROBLEM**: Too many entities overwhelm users and create maintenance burden:

```python
# BEFORE: 15 entities per device - user confusion
WiiM Device "Living Room" created 15 entities:
✓ media_player.living_room          # ← Actually useful
✓ sensor.living_room_ip             # Network info (sometimes useful)
✓ sensor.living_room_role           # Group status (useful)
✗ sensor.living_room_activity       # Internal polling detail
✗ sensor.living_room_interval       # Internal polling detail
✗ binary_sensor.living_room_playing # Duplicates media_player state
✗ binary_sensor.living_room_grouped # Duplicates role sensor
✗ button.living_room_refresh        # Internal implementation detail
✗ switch.living_room_smart_polling  # Internal optimization toggle
... and 6 more entities
```

**SOLUTION**: Smart categorization with user control:

| Entity Type        | Default        | Rationale                                |
| ------------------ | -------------- | ---------------------------------------- |
| **Essential**      | Always         | Core functionality users expect          |
| **Maintenance**    | Optional (On)  | Useful troubleshooting, not overwhelming |
| **Diagnostic**     | Optional (Off) | Developer/advanced troubleshooting only  |
| **Network**        | Optional (Off) | Specific use case (network monitoring)   |
| **Audio Features** | Optional (Off) | Device-specific capabilities             |

**Design Decisions**:

1. **Default to minimal** - only 3 entities by default
2. **User controls complexity** - enable advanced features when needed
3. **Remove redundancy** - don't duplicate information available elsewhere
4. **Hide internal details** - polling, debugging, refresh controls are implementation details
5. **Logical grouping** - related entities enabled together

---

## 🎨 **Design Decisions**

### **Why Sonos as Our Reference Model?**

1. **Most mature audio integration** in Home Assistant
2. **Handles complex grouping scenarios** elegantly
3. **Event-driven architecture** that scales
4. **Clean entity separation** with rich business objects
5. **Battle-tested patterns** used by millions

### **Why Rich Speaker Objects?**

**BEFORE** (anti-pattern):

```python
# Heavy, complex entities with mixed responsibilities
class WiiMMediaPlayer(CoordinatorEntity):
    def __init__(self, coordinator):  # 1,762 lines of everything
        # Device info setup
        # Group management
        # State calculation
        # API calls
        # Service logic
```

**AFTER** (clean pattern):

```python
# Thin entity that delegates to rich Speaker
class WiiMMediaPlayer(WiimEntity, MediaPlayerEntity):
    def __init__(self, speaker: Speaker):  # ~200 lines, focused
        super().__init__(speaker)  # Speaker owns the complexity

    @property
    def state(self) -> MediaPlayerState:
        return self.speaker.get_playback_state()  # Delegate!
```

### **Why Event-Driven Communication?**

- **Loose coupling** - entities don't need to know about each other
- **Automatic updates** - state changes propagate instantly
- **Easy testing** - mock events to test scenarios
- **Scalable** - add new entities without touching existing code

### **Why Eliminate Custom Device Registry?**

**PROBLEM**: Our 25KB `device_registry.py` duplicates HA's functionality:

```python
# CONFLICTS with HA patterns
class WiiMDeviceRegistry:
    self._devices: dict[str, DeviceState] = {}  # Duplicate!
    self._ip_to_uuid: dict[str, str] = {}      # Custom lookup
```

**SOLUTION**: Use HA's registry + lightweight lookups:

```python
# CLEAN: Let HA handle devices, we handle speaker lookup
class WiimData:
    speakers: dict[str, Speaker] = {}           # UUID → Speaker
    entity_id_mappings: dict[str, Speaker] = {} # entity_id → Speaker
```

### **Configuration vs Entity Controls Philosophy**

**PROBLEM**: Users confused by redundant controls in both options menu and as entities:

```python
# BEFORE: Confusing duplication
Options Menu: "Status Update Frequency" (1-60 seconds)
Entity: "Base Polling Interval" (1-300 seconds)
# → Users don't know which one to use!

Options Menu: "enable_maintenance_buttons"
# → Raw field names instead of user-friendly labels
```

**SOLUTION**: Clear separation of configuration vs runtime controls:

```python
# AFTER: Clean separation
✅ OPTIONS MENU (Device Configuration):
- "🔄 Update Frequency" - Sets base polling interval
- "🔊 Volume Step Size" - Sets volume increment percentage
- "👥 Group Controls" - Enable/disable group management
- "🔧 Maintenance Buttons" - Show/hide maintenance entities
- "📊 Diagnostic Sensors" - Show/hide advanced debugging

✅ ENTITIES (Runtime Controls):
- Volume Step (number) - Quick runtime adjustment of volume steps
- Reboot (button) - Device maintenance actions
- Sync Time (button) - Device maintenance actions
# NO polling interval entity - handled in options only
```

**DESIGN PRINCIPLES**:

1. **Options Menu** = Device configuration (requires restart to take effect)
2. **Entities** = Runtime controls (immediate effect, frequently used)
3. **No Duplication** = Each setting has ONE place to control it
4. **User-Friendly Labels** = No raw field names like "enable_maintenance_buttons"

**BENEFITS**:

- ✅ **Eliminates confusion** about which control to use
- ✅ **Reduces entity clutter** (removed redundant polling entity)
- ✅ **Clear mental model** for users
- ✅ **Better UX** with proper translations and labels

### **Polling Strategy: Simple & Reliable vs Complex & Optimized**

**CRITICAL DESIGN DECISION**: We chose simple, predictable polling over complex "smart" optimization.

**REJECTED APPROACH: Complex Smart Polling**

```python
# REJECTED: 500+ lines of "smart" polling complexity
class SmartPollingManager:
    # 5 activity levels with different intervals
    # Multiple caches with state synchronization
    # Position prediction with drift detection
    # Bandwidth metrics and optimization tracking
    # Conditional API calls based on activity
    # Complex state machines for activity detection

# RESULT: 500+ lines to save ~360KB/hour on local network
```

**CHOSEN APPROACH: Simple State-Aware Polling**

Based on [WiiM HTTP API analysis](https://www.wiimhome.com/pdf/HTTP%20API%20for%20WiiM%20Products.pdf), we need different polling for different endpoints:

```python
# CHOSEN: Simple, state-aware polling (~50 lines)
class WiiMCoordinator:
    async def _async_update_data(self):
        # Always get playback status (most important)
        status = await self.client.get_player_status()

        # State-aware polling based on playback
        if status.get("status") == "play":
            # When playing: fast updates for smooth position
            interval = 1  # 1 second for position updates
        else:
            # When idle: normal polling
            interval = 5  # 5 seconds default

        # Get device info less frequently
        if self._should_update_device_info():
            device_info = await self.client.get_status_ex()

        # Get metadata only when track changes
        if self._track_changed(status):
            metadata = await self.client.get_meta_info()

        return {"status": status, "device_info": device_info}
```

**SIMPLE SMART POLLING RULES**:

| Endpoint              | When            | Frequency           | Rationale                          |
| --------------------- | --------------- | ------------------- | ---------------------------------- |
| **`getPlayerStatus`** | Always          | 1s playing, 5s idle | Position updates need to be smooth |
| **`getStatusEx`**     | Periodic        | Every 30-60s        | Device info changes rarely         |
| **`getMetaInfo`**     | On track change | As needed           | Only when song changes             |
| **EQ endpoints**      | Periodic        | Every 60s           | EQ settings change very rarely     |

**USER CONFIGURATION**:

```python
# Simple user options
Options Menu:
- "Playing Update Rate" (1-5 seconds, default 1s)
- "Idle Update Rate" (5-60 seconds, default 5s)

# Automatic behavior:
# - Fast polling when playing for smooth position
# - Slower polling when idle to reduce overhead
# - Track metadata only fetched when needed
```

**BENEFITS OF SIMPLE STATE-AWARE APPROACH**:

- ✅ **Smooth playback** - 1s updates during playback for position tracking
- ✅ **Efficient when idle** - 5s updates when not playing
- ✅ **Simple logic** - ~50 lines vs 500+ lines
- ✅ **User control** - Two simple settings users understand
- ✅ **API-optimized** - Follows WiiM API usage patterns
- ✅ **Debuggable** - Clear, predictable behavior

**REJECTED COMPLEX OPTIMIZATIONS**:

- ❌ 5+ activity levels with complex state machines
- ❌ Multiple data caches requiring synchronization
- ❌ Position prediction algorithms
- ❌ Bandwidth usage metrics and optimization
- ❌ Complex activity detection with timestamps

**DESIGN PRINCIPLE**: **"Match polling to API purpose and user needs"**

Different WiiM API endpoints have different update requirements:

- **Playback status**: Needs frequent updates during playback
- **Device info**: Rarely changes, infrequent polling is fine
- **Track metadata**: Only when track changes

This approach provides smooth user experience during playback while being efficient during idle periods.

---

## 🎯 **Quality Principles**

### **1. Test-Driven Architecture**

- **90%+ test coverage** requirement
- **Each component has focused unit tests**
- **Integration tests for user scenarios**

### **2. Developer Experience**

- **Clear, documented APIs** for each component
- **Easy to extend** - adding new entities/services is simple
- **Self-documenting code** with type hints and docstrings

### **3. Performance First**

- **Smart polling** reduces API calls by 90%
- **Event-driven updates** minimize unnecessary work
- **Efficient data structures** with O(1) lookups

### **4. Maintainability**

- **Small, focused files** (< 500 LOC each)
- **Clear component boundaries**
- **No circular dependencies**
- **Deprecation strategies** for breaking changes

---

## 🚀 **Success Metrics**

### **Code Quality**

| Metric                    | Target          | Rationale                         |
| ------------------------- | --------------- | --------------------------------- |
| **File Size**             | < 500 LOC       | Easier to understand and maintain |
| **Test Coverage**         | 90%+            | Confidence in changes             |
| **Cyclomatic Complexity** | < 10 per method | Simple, testable code             |

### **Architecture Quality**

| Metric                     | Target | Rationale                            |
| -------------------------- | ------ | ------------------------------------ |
| **Component Coupling**     | Low    | Independent, testable components     |
| **Responsibility Clarity** | High   | Each class has one clear job         |
| **API Consistency**        | High   | Predictable patterns across codebase |

### **User Experience**

| Metric               | Target       | Rationale                       |
| -------------------- | ------------ | ------------------------------- |
| **Setup Time**       | < 30 seconds | Fast device discovery and setup |
| **Group Operations** | < 3 seconds  | Responsive multiroom control    |
| **State Updates**    | < 1 second   | Real-time UI feedback           |

---

## 🔮 **Future-Proofing Decisions**

### **1. Extensible Entity Framework**

New platform support is **trivial**:

```python
# Adding a new entity type
class WiiMNewEntity(WiimEntity, NewEntityType):
    def __init__(self, speaker: Speaker):
        super().__init__(speaker)  # Inherits all Speaker goodness
        # Platform-specific logic only
```

### **2. Service-Oriented Architecture**

New services are **isolated and testable**:

```python
# New service implementation
class NewWiiMService:
    @staticmethod
    async def new_feature(speaker: Speaker, params: dict) -> None:
        # Focused, testable business logic
```

### **3. Protocol Independence**

Architecture supports **future protocols**:

```python
# WiiMClient abstraction allows protocol changes
class WiiMClient:
    async def get_status(self) -> dict:
        # Could be HTTP, WebSocket, etc.
```

---

## 📚 **Design Inspirations**

### **Primary Reference**

- **Sonos Integration** - Event-driven, rich speaker objects, clean entity separation

### **Secondary Patterns**

- **ESPHome Integration** - Device-centric architecture
- **Philips Hue Integration** - Bridge pattern with device registry
- **Cast Integration** - Media player grouping patterns

### **Anti-Patterns to Avoid**

- **Monolithic entities** with mixed responsibilities
- **Custom device registries** that conflict with HA
- **Tight coupling** between components
- **Synchronous operations** in async contexts

---

## 🎊 **The End Goal**

A **best-in-class Home Assistant integration** that:

✅ **Feels native** - follows all HA patterns and conventions
✅ **Performs excellently** - smart polling, event-driven updates
✅ **Scales gracefully** - handles 1 speaker or 20 speakers equally well
✅ **Tests comprehensively** - 90%+ coverage with robust scenarios
✅ **Maintains easily** - clear architecture, focused components
✅ **Extends trivially** - new features are simple to add

**In short**: The integration **other integration developers study** to learn best practices.
