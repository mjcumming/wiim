# WiiM Integration - Developer Guide

> **Purpose**: Complete development guide covering architecture, design principles, coding standards, and implementation patterns for the WiiM Home Assistant integration.

---

## 🎯 **Project Overview**

### **Vision & Goals**

The WiiM integration is designed as a **world-class Home Assistant integration** following Sonos-inspired patterns with Speaker-centric architecture.

**Success Metrics**:

- ✅ **Architecture Excellence**: Clean, maintainable, Sonos-inspired patterns
- ✅ **Code Quality**: 71% code reduction, event-driven updates
- ✅ **User Experience**: Essential-only entities (15 → 2-5 by default)
- ✅ **Universal Compatibility**: Works on all WiiM/LinkPlay devices
- ✅ **Production Ready**: Defensive polling, graceful API fallbacks

### **Core Achievements**

| Component         | Before         | After            | Improvement        |
| ----------------- | -------------- | ---------------- | ------------------ |
| **Smart Polling** | 525 lines      | 100 lines        | 80% reduction      |
| **Media Player**  | 1,762 lines    | 247 lines        | 86% reduction      |
| **Entity Count**  | 15/device      | 2-5/device       | 85% reduction      |
| **Architecture**  | Mixed patterns | 100% Sonos-style | Clean & consistent |

---

## 🏗️ **Architecture Overview**

### **Speaker-Centric Design**

The integration follows the **"Single Source of Truth"** pattern with rich Speaker objects:

```python
# Central registry
WiimData.speakers: dict[str, Speaker]  # UUID → Speaker mapping

# Rich business objects
class Speaker:
    async def async_join_group(self, speakers: list[Speaker]) -> None:
        # All group logic in Speaker, not entities

    def get_playback_state(self) -> MediaPlayerState:
        # Business logic in Speaker class
```

### **Event-Driven Communication**

```python
# Speaker notifies entities of state changes
def async_write_entity_states(self) -> None:
    async_dispatcher_send(self.hass, f"wiim_state_updated_{self.uuid}")

# Entities listen for their speaker's events
async def async_added_to_hass(self) -> None:
    async_dispatcher_connect(self.hass, f"wiim_state_updated_{self.speaker.uuid}",
                           self.async_write_ha_state)
```

### **Thin Entity Wrappers**

```python
# Entities delegate to Speaker business logic
class WiiMMediaPlayer(WiimEntity, MediaPlayerEntity):
    @property
    def state(self) -> MediaPlayerState:
        return self.speaker.get_playback_state()  # Perfect delegation

    async def async_join(self, group_members: list[str]) -> None:
        speakers = self.speaker.resolve_entity_ids_to_speakers(group_members)
        await self.speaker.async_join_group(speakers)  # Business logic in Speaker
```

---

## 🎨 **Design Principles**

### **1. Sonos-Inspired Patterns**

**Why Sonos as Reference?**

- Most mature audio integration in Home Assistant
- Handles complex grouping scenarios elegantly
- Event-driven architecture that scales
- Clean entity separation with rich business objects
- Battle-tested patterns used by millions

### **2. Essential-Only Entity Design**

**CRITICAL: Role Sensor Always Visible**

The role sensor is **NEVER optional** because multiroom understanding is core functionality:

```python
# ALWAYS CREATE: Role sensor - ESSENTIAL for multiroom understanding
entities.append(WiiMRoleSensor(speaker))  # ← NEVER hidden

# States: "Solo", "Master", "Slave" (clear and direct)
```

**Why Role Sensor is Always Enabled:**

1. **🎯 Multiroom is CORE functionality** - not diagnostic
2. **🔧 Essential for troubleshooting** - users need to see group state
3. **🏠 Required for automations** - group status drives logic
4. **📱 UI navigation** - users must know which speaker controls the group

### **3. Defensive API Programming**

**CRITICAL**: WiiM/LinkPlay API endpoints have significant inconsistencies:

| Endpoint              | Reliability        | Strategy                             |
| --------------------- | ------------------ | ------------------------------------ |
| **`getPlayerStatus`** | ✅ Universal       | Foundation - always use              |
| **`getMetaInfo`**     | ⚠️ Inconsistent    | Probe once, fallback to basic        |
| **`getStatusEx`**     | ⚠️ WiiM-specific   | Try first, fallback to `getStatus`   |
| **EQ endpoints**      | ❌ Highly variable | Probe capability, disable if missing |

```python
# Defensive programming pattern
async def get_track_metadata(self) -> dict:
    if self._metadata_supported:
        try:
            return await self._get_meta_info()
        except WiiMError:
            self._metadata_supported = False  # Remember failure

    # Always have fallback
    status = await self.get_player_status()
    return {"title": status.get("title", "Unknown")}
```

---

## 💻 **Development Standards**

### **Code Quality Rules**

| Rule               | Requirement          | Rationale                         |
| ------------------ | -------------------- | --------------------------------- |
| **File Size**      | < 500 LOC            | Easier to understand and maintain |
| **Entity Polling** | Event-driven only    | No `_attr_should_poll = True`     |
| **Business Logic** | In Speaker class     | Entities are thin UI adapters     |
| **Error Handling** | Graceful degradation | Never fail hard on API issues     |
| **Type Hints**     | Required everywhere  | Self-documenting code             |

### **Coding Patterns**

**DO:**

```python
# ✅ Rich Speaker with business logic
class Speaker:
    async def async_join_group(self, speakers: list[Speaker]) -> None:
        # Business logic here

# ✅ Thin entity that delegates
class WiiMMediaPlayer(WiimEntity, MediaPlayerEntity):
    async def async_join(self, group_members: list[str]) -> None:
        await self.speaker.async_join_group(speakers)  # Delegate!

# ✅ Event-driven updates
_attr_should_poll = False  # Always event-driven
```

**DON'T:**

```python
# ❌ Heavy entities with business logic
class WiiMMediaPlayer(CoordinatorEntity):
    def __init__(self, coordinator):  # 1,762 lines of everything
        # Device info setup, group management, state calc, API calls...

# ❌ Polling entities
_attr_should_poll = True  # Use events instead

# ❌ Complex smart polling
class SmartPollingManager:  # 500+ lines of optimization
```

### **Entity Design Rules**

1. **Essential Only**: Only create entities users actually need
2. **Role Sensor Critical**: Always visible - multiroom status is core
3. **Thin Wrappers**: Entities delegate to Speaker business logic
4. **Event-Driven**: Zero polling, all state updates via events
5. **Clean Names**: Device-based entity IDs, no IP addresses

---

## 🔧 **Implementation Patterns**

### **Platform Setup Pattern**

```python
# Every platform follows this pattern
async def async_setup_entry(hass, config_entry, async_add_entities):
    speaker: Speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    entry = hass.data[DOMAIN][config_entry.entry_id]["entry"]

    entities = []

    # ALWAYS CREATE: Essential entities
    entities.append(WiiMCoreEntity(speaker))

    # OPTIONAL: Based on user configuration
    if entry.options.get(CONF_ENABLE_OPTIONAL_FEATURES, False):
        entities.extend([WiiMOptionalEntity(speaker)])

    async_add_entities(entities)
```

### **Entity Base Class Pattern**

```python
class WiimEntity(Entity):
    """Base for all WiiM entities - event-driven, no polling."""

    _attr_should_poll = False  # ALWAYS event-driven
    _attr_has_entity_name = True  # Clean entity IDs

    def __init__(self, speaker: Speaker) -> None:
        self.speaker = speaker

    async def async_added_to_hass(self) -> None:
        # Register for speaker events
        async_dispatcher_connect(
            self.hass, f"wiim_state_updated_{self.speaker.uuid}",
            self.async_write_ha_state
        )
```

### **API Client Pattern**

```python
class WiiMClient:
    def __init__(self):
        # Capability flags - None means untested
        self._metadata_supported: bool | None = None
        self._eq_supported: bool | None = None

    async def get_track_metadata(self) -> dict:
        # Try enhanced endpoint first
        if self._metadata_supported is not False:
            try:
                result = await self._get_meta_info()
                if self._metadata_supported is None:
                    self._metadata_supported = True
                return result
            except WiiMError:
                self._metadata_supported = False

        # Always have fallback
        return await self._get_basic_metadata()
```

---

## 🧪 **Testing Strategy**

### **Test Structure**

```
tests/
├── unit/
│   ├── test_speaker.py          # Speaker business logic
│   ├── test_entity.py           # WiimEntity base tests
│   ├── test_coordinator.py      # Defensive polling tests
│   └── test_api_client.py       # API capability probing
├── integration/
│   ├── test_media_player.py     # End-to-end entity tests
│   ├── test_multiroom.py        # Group management scenarios
│   └── test_setup.py            # Integration setup tests
└── fixtures/
    ├── mock_speakers.py         # Speaker test data
    └── api_responses.py         # WiiM API response fixtures
```

### **Testing Principles**

1. **Unit Tests**: Test Speaker business logic independently
2. **Integration Tests**: Test entity behavior with mocked Speaker
3. **API Tests**: Test defensive programming and fallbacks
4. **Group Tests**: Test complex multiroom scenarios

---

## 📊 **Performance Guidelines**

### **Fixed 5-Second Polling**

**Simple, Reliable Strategy**:

- **5 seconds** - Fixed polling interval for all states
- **API capability probing** with graceful fallbacks
- **No complexity** - Consistent, predictable behavior

```python
# Simple fixed polling logic
self.update_interval = timedelta(seconds=5)  # Always 5 seconds
```

### **Memory Efficiency**

| Component | Memory per Speaker   | Notes                       |
| --------- | -------------------- | --------------------------- |
| Speaker   | ~2KB                 | Device state and references |
| Entities  | ~500B each           | Thin wrappers               |
| **Total** | **~4KB per speaker** | Scales linearly             |

---

## 🔗 **API Integration**

### **LinkPlay Group Management**

**Essential Commands**:

```bash
# Join group
ConnectMasterAp:JoinGroupMaster:<master_ip>:wifi0.0.0.0

# Leave group
multiroom:SlaveKickout:<slave_ip>

# Disband group
multiroom:Ungroup
```

**Implementation**:

```python
async def async_join_group(self, speakers: list[Speaker]) -> None:
    master = self  # This speaker becomes master
    for slave in speakers:
        await slave.coordinator.client.join_master(master.ip)
    # Update Speaker objects and notify entities
    self.async_write_entity_states()
```

### **API Reliability Matrix**

External API documentation: [Arylic LinkPlay API](https://developer.arylic.com/httpapi/)

**Do NOT copy the entire API documentation into our repo** - just link to the official source.

---

## 🚀 **Development Workflow**

### **Adding New Features**

1. **Design**: Follow Speaker-centric patterns
2. **Implement**: Business logic in Speaker class
3. **Entity**: Thin wrapper that delegates to Speaker
4. **Test**: Unit tests for Speaker, integration tests for entity
5. **Document**: Update this guide with new patterns

### **Adding New Entities**

```python
# 1. Create entity class following patterns
class WiiMNewEntity(WiimEntity, NewEntityType):
    def __init__(self, speaker: Speaker):
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_new_feature"

# 2. Add to platform setup
async def async_setup_entry(hass, config_entry, async_add_entities):
    entities = [WiiMNewEntity(speaker)]
    async_add_entities(entities)

# 3. Add business logic to Speaker if needed
class Speaker:
    def get_new_feature_state(self) -> str:
        return self.coordinator.data.get("new_feature", "unknown")
```

### **Debugging Guidelines**

**Enable Debug Logging**:

```yaml
# configuration.yaml
logger:
  logs:
    custom_components.wiim: debug
```

**Common Debug Patterns**:

- **API Failures**: Check capability probing and fallbacks
- **Entity Updates**: Verify event dispatching works
- **Group Issues**: Check Speaker role states and group_members
- **Polling Problems**: Verify defensive polling intervals

---

## 📚 **Reference Documentation**

### **Core Files**

| File             | Purpose                          | Key Patterns                             |
| ---------------- | -------------------------------- | ---------------------------------------- |
| `data.py`        | Speaker class, WiimData registry | Business logic, event dispatching        |
| `entity.py`      | WiimEntity base class            | Event-driven, delegation                 |
| `coordinator.py` | Defensive polling                | Two-state polling, API fallbacks         |
| `api.py`         | WiiM HTTP client                 | Capability probing, graceful degradation |

### **External References**

- **Sonos Integration**: Our reference model for architecture patterns
- **Home Assistant Device Registry**: Core HA patterns we follow
- **LinkPlay API**: [Official documentation](https://developer.arylic.com/httpapi/)

---

## 📝 **Coding Standards & Workflow**

### **Development Rules**

| Rule               | Requirement          | Rationale                         |
| ------------------ | -------------------- | --------------------------------- |
| **File Size**      | < 500 LOC            | Easier to understand and maintain |
| **Entity Polling** | Event-driven only    | No `_attr_should_poll = True`     |
| **Business Logic** | In Speaker class     | Entities are thin UI adapters     |
| **Error Handling** | Graceful degradation | Never fail hard on API issues     |
| **Type Hints**     | Required everywhere  | Self-documenting code             |

### **Code Quality Guidelines**

**1. Clarity and Readability**

- Favor straightforward, self-explanatory code structures
- Include descriptive comments for complex logic
- Use meaningful variable and function names

**2. Python Best Practices**

- Follow PEP 8 style guidelines
- Use type hints for all function signatures
- Prefer async/await over synchronous operations
- Use dataclasses for configuration objects

**3. Home Assistant Patterns**

- Follow HA's entity lifecycle patterns
- Use HA's service call patterns
- Leverage HA's device registry properly
- Follow HA's configuration flow patterns

### **Testing Requirements**

**1. Test-Driven Development**

- Write tests before implementing features
- Minimum 85% test coverage required
- Test all error conditions and edge cases

**2. Test Structure**

```python
# Unit tests - test Speaker business logic
def test_speaker_join_group():
    """Test Speaker.async_join_group logic"""

# Integration tests - test entity behavior
def test_media_player_join():
    """Test WiiMMediaPlayer.async_join delegates to Speaker"""

# API tests - test defensive programming
def test_api_fallback_when_metadata_fails():
    """Test graceful fallback when getMetaInfo unavailable"""
```

**3. Test Categories**

- **Unit**: Speaker class business logic
- **Integration**: Entity platform behavior
- **API**: Client defensive programming
- **E2E**: Complete user scenarios

### **Error Handling Standards**

**1. Graceful Degradation**

```python
# ✅ Good - graceful fallback
async def get_metadata(self) -> dict:
    if self._metadata_supported:
        try:
            return await self._get_meta_info()
        except WiiMError:
            self._metadata_supported = False

    # Always have fallback
    return self._extract_basic_metadata()

# ❌ Bad - hard failure
async def get_metadata(self) -> dict:
    return await self._get_meta_info()  # Crashes if unsupported
```

**2. API Capability Management**

- Probe endpoint support once on startup
- Remember capability results permanently
- Never fail hard on missing advanced features
- Log capability limitations for troubleshooting

### **Version Control & Documentation**

**1. Commit Guidelines**

- Clear, descriptive commit messages
- Atomic commits (one logical change per commit)
- Reference issue numbers when applicable

**2. Documentation Requirements**

- Update documentation alongside code changes
- Keep architecture documentation current
- Document all public APIs and configuration options
- Include examples for complex features

### **Development Workflow**

**1. Feature Development Process**

```
1. Design - Follow Speaker-centric patterns
2. Test - Write unit tests for Speaker logic
3. Implement - Business logic in Speaker class
4. Entity - Create thin wrapper that delegates
5. Integration Test - Verify entity behavior
6. Documentation - Update relevant guides
```

**2. Code Review Checklist**

- [ ] Follows Speaker-centric architecture
- [ ] Entities are thin wrappers that delegate
- [ ] Event-driven (no polling entities)
- [ ] Graceful API error handling
- [ ] Comprehensive test coverage
- [ ] Documentation updated

---

This guide ensures all developers follow the established patterns that make this integration a **reference implementation** for complex audio device integrations in Home Assistant.
