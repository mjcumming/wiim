# WiiM Home Assistant Integration - Architecture & Design

## Table of Contents

1. [Core Principles](#core-principles)
2. [Architecture Overview](#architecture-overview)
3. [Component Responsibilities](#component-responsibilities)
4. [Data Flow](#data-flow)
5. [Project Structure](#project-structure)
6. [Code Patterns](#code-patterns)
7. [Decision Log](#decision-log)

## Core Principles

### 1. Thin Glue Layer

**This integration is a thin glue layer between pywiim and Home Assistant.**

- ✅ **DO**: Create HA entities, read from pywiim, call pywiim methods
- ❌ **DON'T**: Implement device communication, business logic, or state management

### 2. pywiim is Source of Truth

**All device communication and logic belongs in pywiim.**

- ✅ **DO**: Use pywiim's Player, Client, and Group objects
- ❌ **DON'T**: Work around pywiim issues in the integration
- ❌ **DON'T**: Add fallback logic for missing pywiim features

### 3. Home Assistant Patterns

**Follow Home Assistant development guidelines strictly.**

- Use `DataUpdateCoordinator` for polling
- Use `ConfigFlow` for setup
- Use `CoordinatorEntity` for entities
- Use public HA APIs only

### 4. Test-Driven Development

**Every bug fix requires a test.**

- Write failing test first (TDD)
- Verify test fails (reproduces bug)
- Fix the bug
- Verify test passes
- Add edge cases

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Home Assistant                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Media Player │  │   Sensors    │  │   Switches   │     │
│  │   Entity     │  │   Entities   │  │   Entities   │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │              │
│         └──────────────────┼──────────────────┘             │
│                            │                                  │
│                    ┌───────▼────────┐                        │
│                    │  Coordinator   │                        │
│                    │  (pywiim)      │                        │
│                    └───────┬────────┘                        │
└────────────────────────────┼─────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   pywiim       │
                    │   Library      │
                    │  (HTTP API)    │
                    └────────┬───────┘
                             │
                    ┌────────▼────────┐
                    │   WiiM Device   │
                    │   (Hardware)    │
                    └─────────────────┘
```

### Layer Responsibilities

1. **Home Assistant Layer** (`custom_components/wiim/`)

   - Entity creation and management
   - Config flow and options
   - Device registry
   - Service definitions

2. **pywiim Layer** (external library)

   - Device communication
   - State management
   - Polling strategy
   - Business logic

3. **Device Layer** (hardware)
   - LinkPlay firmware
   - HTTP API
   - UPnP/SSDP

## Component Responsibilities

### Core Components

#### `__init__.py`

- **Purpose**: Integration setup and entry point
- **Responsibilities**:
  - Create pywiim client and coordinator
  - Register platforms
  - Handle config entry lifecycle
- **DO NOT**: Implement device communication logic

#### `coordinator.py`

- **Purpose**: Thin wrapper around pywiim's Player
- **Responsibilities**:
  - Wrap pywiim Player in DataUpdateCoordinator
  - Handle polling intervals
  - Provide data to entities
- **DO NOT**: Implement polling logic (pywiim handles this)

#### `data.py`

- **Purpose**: Minimal Speaker wrapper
- **Responsibilities**:
  - Hold coordinator reference
  - Provide device info
  - Link config entry to coordinator
- **DO NOT**: Store device state (pywiim Player has this)

#### `entity.py`

- **Purpose**: Base entity class
- **Responsibilities**:
  - Common entity functionality
  - Device info
  - Availability
- **DO NOT**: Platform-specific logic

### Platform Components

#### `media_player.py`

- **Purpose**: Media player entity
- **Pattern**: Read from `coordinator.data["player"]`, call `coordinator.player.method()`
- **Key Properties**:
  - `volume_level`: `player.volume_level`
  - `volume_step`: `config_entry.options.get(CONF_VOLUME_STEP)`
  - `state`: `player.play_state`
  - `source`: `player.source`

#### `sensor.py`

- **Purpose**: Sensor entities (role, input, diagnostics)
- **Pattern**: Read from `coordinator.data["player"]`
- **Key Sensors**:
  - Role sensor (always enabled)
  - Input sensor
  - Diagnostic sensors (optional)

#### `group_media_player.py`

- **Purpose**: Virtual group coordinator entity
- **Pattern**: Appears when master has slaves
- **Key Properties**:
  - `volume_level`: `group.volume_level` (MAX of all)
  - `is_volume_muted`: `group.is_muted` (ALL muted)

#### `config_flow.py`

- **Purpose**: Configuration and options flow
- **Pattern**: Use pywiim discovery, store minimal config
- **Key Flows**:
  - Discovery (SSDP/Zeroconf)
  - Manual entry
  - Options (volume step, feature toggles)

### Platform Pattern

Each platform file follows the same pattern:

1. **Read from pywiim**: `coordinator.data["player"]`
2. **Call pywiim**: `coordinator.player.method()`
3. **Handle errors**: Catch WiiMError, raise HomeAssistantError

## Data Flow

### State Updates

```
Device → pywiim Player → Coordinator.data → Entity Properties
```

1. **Device** sends HTTP response
2. **pywiim Player** parses and stores state
3. **Coordinator** updates `data["player"]`
4. **Entities** read from `coordinator.data["player"]`

### Commands

```
Entity Method → Coordinator.player → pywiim Client → Device HTTP API
```

1. **Entity** calls `async_set_volume_level(0.5)`
2. **Coordinator.player** calls `player.set_volume(0.5)`
3. **pywiim Client** sends HTTP request
4. **Device** receives and processes

## Project Structure

### Directory Layout

```
wiim/
├── custom_components/wiim/    # Integration code (ONLY place to modify)
│   ├── __init__.py            # Setup entry point
│   ├── config_flow.py         # Config & options flow
│   ├── coordinator.py         # pywiim wrapper
│   ├── data.py                # Speaker wrapper
│   ├── entity.py              # Base entity
│   ├── media_player.py        # Media player entity
│   ├── group_media_player.py  # Group coordinator entity
│   ├── sensor.py              # Sensor entities
│   ├── switch.py              # Switch entities
│   ├── select.py              # Select entities
│   ├── number.py              # Number entities
│   ├── button.py              # Button entities
│   ├── light.py               # Light entity (LED)
│   ├── binary_sensor.py       # Binary sensor entities
│   ├── services.py            # Custom services
│   ├── diagnostics.py         # Diagnostics
│   ├── system_health.py       # System health
│   ├── const.py               # Constants
│   ├── models.py              # Data models
│   ├── manifest.json          # Integration manifest
│   ├── strings.json           # Translation strings
│   ├── services.yaml          # Service definitions
│   └── translations/          # Translation files
│
├── tests/                      # Automated tests (pytest)
│   ├── unit/                   # Unit tests (fast, isolated, mocked)
│   ├── integration/            # Integration tests
│   ├── fixtures/               # Test fixtures
│   ├── conftest.py             # All pytest fixtures (consolidated)
│   └── run_tests.py            # Test runner
│
├── scripts/                    # Real-device validation tests
│   ├── test-smoke.py           # Quick smoke tests
│   ├── test-automated.py       # Automated device tests
│   ├── test-multiroom-comprehensive.py  # Multiroom tests
│   └── pre-release-check.py    # Pre-release validation
│
├── docs/                       # Documentation
│   ├── INDEX.md                # Documentation index
│   ├── ARCHITECTURE.md         # This file
│   ├── DEVELOPMENT-RULES.md    # Development rules
│   ├── TESTING-CONSOLIDATED.md # Testing strategy
│   ├── user-guide.md           # User guide
│   ├── faq-and-troubleshooting.md # FAQ
│   ├── automation-cookbook.md  # Automation examples
│   └── TTS_GUIDE.md            # TTS guide
│
├── development/                # Developer guides
│   └── HA_INTEGRATION_GUIDE.md # pywiim integration reference
│
├── .github/                    # GitHub configuration
│   ├── copilot-instructions.md # AI assistant rules
│   └── workflows/              # CI/CD workflows
│
├── CHANGELOG.md                # Version changelog
├── CONTRIBUTING.md             # Contribution guide
├── README.md                   # Project README
├── Makefile                    # Build and test commands
└── pyproject.toml              # Project configuration
```

### File Naming Rules

#### Code Files

- ✅ **DO**: Use lowercase with underscores: `media_player.py`
- ✅ **DO**: Match class name: `WiiMMediaPlayer` → `media_player.py`
- ❌ **DON'T**: Use hyphens: `media-player.py` (Python doesn't allow)

#### Test Files

- ✅ **DO**: Match source file: `test_media_player.py` for `media_player.py`
- ✅ **DO**: Use `test_` prefix: `test_config_flow.py`

#### Documentation Files

- ✅ **DO**: Use hyphens: `testing-strategy.md`
- ✅ **DO**: Use YYYY.MM.DD format for dated docs
- ❌ **DON'T**: Use underscores: `testing_strategy.md`

#### Script Files

- ✅ **DO**: Use hyphens: `test-complete-suite.py`
- ❌ **DON'T**: Use underscores: `test_complete_suite.py`

### Code Organization

#### Import Order

1. **Standard library**
2. **Third-party** (homeassistant, pywiim)
3. **Local** (custom_components.wiim)

#### Class Organization

1. **Imports**
2. **Constants**
3. **Helper functions**
4. **Main class**
   - `__init__`
   - Properties
   - Methods (grouped by functionality)

#### Method Organization (within a class)

1. **Initialization** (`__init__`)
2. **Properties** (read-only)
3. **State methods** (read state)
4. **Control methods** (change state)
5. **Helper methods** (private)

## Code Patterns

### Pattern 1: Reading from pywiim

```python
@property
def volume_level(self) -> float | None:
    """Return volume level from pywiim Player."""
    player = self._get_player()
    return player.volume_level if player else None
```

### Pattern 2: Calling pywiim Methods

```python
async def async_set_volume_level(self, volume: float) -> None:
    """Set volume via pywiim."""
    try:
        await self.coordinator.player.set_volume(volume)
    except WiiMError as err:
        raise HomeAssistantError(f"Failed to set volume: {err}") from err
```

### Pattern 3: Config Entry Options

```python
@property
def volume_step(self) -> float:
    """Read from config entry options."""
    if hasattr(self, "speaker") and self.speaker.config_entry:
        return self.speaker.config_entry.options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
    return DEFAULT_VOLUME_STEP
```

### Pattern 4: Safe Attribute Access

```python
# ✅ Good - safe access
upnp_client = getattr(player, "_upnp_client", None)
has_upnp = upnp_client is not None

# ❌ Bad - direct access
has_upnp = coordinator.upnp_client is not None  # AttributeError!
```

### Pattern 5: Error Handling

```python
try:
    await self.coordinator.player.set_volume(volume)
except WiiMConnectionError as err:
    # Connection errors are transient
    _LOGGER.warning("Connection issue: %s", err)
    raise HomeAssistantError(f"Device temporarily unreachable") from err
except WiiMError as err:
    # Other errors are actual problems
    _LOGGER.error("Failed to set volume: %s", err, exc_info=True)
    raise HomeAssistantError(f"Failed to set volume: {err}") from err
```

## Decision Log

### Architecture Decisions

| Date       | Decision                | Rationale                                 |
| ---------- | ----------------------- | ----------------------------------------- |
| 2025-11-28 | Thin glue layer pattern | Keeps integration simple, logic in pywiim |
| 2025-11-28 | Two test directories    | Automated (tests/) vs manual (scripts/)   |
| 2025-11-28 | Test-driven development | Prevents regression bugs                  |

### Design Patterns

- **Coordinator Pattern**: All entities use DataUpdateCoordinator
- **Entity Pattern**: CoordinatorEntity for all platforms
- **Config Pattern**: ConfigFlow for setup, OptionsFlow for options
- **Service Pattern**: Custom services in services.py

## Related Documentation

### Internal Docs

- **[DEVELOPMENT-RULES.md](DEVELOPMENT-RULES.md)** - Detailed development rules and guidelines
- **[TESTING-CONSOLIDATED.md](TESTING-CONSOLIDATED.md)** - Complete testing strategy
- **[../development/README.md](../development/README.md)** - Developer quick-start guide
- **[../development/HA_INTEGRATION_GUIDE.md](../development/HA_INTEGRATION_GUIDE.md)** - pywiim integration patterns reference

### External References

- **[Home Assistant Developer Docs](https://developers.home-assistant.io/)** - Official HA development guidelines
- **[pywiim Library](https://github.com/mjcumming/pywiim)** - Core library (all device communication)
- **[pywiim HA Integration Guide](https://github.com/mjcumming/pywiim/blob/main/docs/integration/HA_INTEGRATION.md)** - Upstream integration patterns
- **[pywiim API Reference](https://github.com/mjcumming/pywiim/blob/main/docs/integration/API_REFERENCE.md)** - Full API documentation
- **[LinkPlay API Docs](https://developer.arylic.com/httpapi/)** - Hardware API reference
