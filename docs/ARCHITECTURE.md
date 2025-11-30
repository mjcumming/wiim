# WiiM Home Assistant Integration - Architecture & Design

## Table of Contents

1. [Core Principles](#core-principles)
2. [Architecture Overview](#architecture-overview)
3. [Component Responsibilities](#component-responsibilities)
4. [Data Flow](#data-flow)
5. [Project Structure](#project-structure)
6. [Development Rules](#development-rules)
7. [Testing Strategy](#testing-strategy)
8. [Code Patterns](#code-patterns)

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
│   ├── const.py               # Constants
│   └── models.py              # Data models
│
├── tests/                      # Automated tests (pytest)
│   ├── unit/                   # Unit tests (fast, mocked)
│   ├── integration/            # Integration tests
│   ├── conftest.py             # Shared fixtures
│   └── run_tests.py            # Test runner
│
├── scripts/                    # Manual validation tests
│   ├── test-complete-suite.py # E2E test suite
│   └── test-real-devices.py   # Real device tests
│
├── docs/                       # Documentation
│   ├── ARCHITECTURE.md         # This file
│   ├── testing-strategy.md     # Testing approach
│   └── user-guide.md           # User documentation
│
└── development/                # Developer guides
    └── README.md               # Development guide
```

### File Naming Rules

- ✅ **DO**: Use hyphens for multi-word files: `test-complete-suite.py`
- ❌ **DON'T**: Use underscores: `test_complete_suite.py`
- ✅ **DO**: Use lowercase: `config-flow.py`
- ✅ **DO**: Use descriptive names: `group-media-player.py`

### Code Organization Rules

1. **One class per file** (when possible)
2. **Keep files < 500 LOC** (split if larger)
3. **Group related functionality** (e.g., all volume code together)
4. **Import order**: stdlib → third-party → local

## Development Rules

### Rule 1: pywiim is Source of Truth

**NEVER work around pywiim issues in the integration.**

If pywiim doesn't provide something:

1. Fix it in pywiim
2. Update pywiim dependency
3. Remove any workarounds

### Rule 2: Thin Glue Layer

**Only code that directly glues pywiim to HA belongs here.**

- ✅ Entity creation
- ✅ Config flow
- ✅ Reading from pywiim
- ✅ Calling pywiim methods
- ❌ Device communication logic
- ❌ State management
- ❌ Business logic

### Rule 3: Test-Driven Development

**Every bug fix requires a test.**

1. Write failing test
2. Verify it fails
3. Fix the bug
4. Verify test passes
5. Add edge cases

### Rule 4: Follow HA Patterns

**Use Home Assistant's recommended patterns.**

- `DataUpdateCoordinator` for polling
- `CoordinatorEntity` for entities
- `ConfigFlow` for setup
- Public HA APIs only

### Rule 5: Type Hints Required

**All code must have type hints.**

```python
def async_set_volume_level(self, volume: float) -> None:
    """Set volume level."""
    pass
```

### Rule 6: Error Handling

**Fail loudly with actionable messages.**

```python
# ✅ Good
raise HomeAssistantError(f"Failed to set volume on {self.name}: {err}") from err

# ❌ Bad
raise HomeAssistantError("Error")
```

## Testing Strategy

### Test Categories

#### 1. Unit Tests (`tests/unit/`)

- **Purpose**: Fast, isolated tests
- **Speed**: Seconds
- **Devices**: Mocked
- **When**: Every commit, pre-release
- **Coverage Target**: 80%+

#### 2. Integration Tests (`tests/integration/`)

- **Purpose**: Realistic scenarios
- **Speed**: Seconds to minutes
- **Devices**: Mocked or test containers
- **When**: Pre-release, PR validation

#### 3. Manual Validation (`scripts/`)

- **Purpose**: Real device testing
- **Speed**: Minutes
- **Devices**: Real
- **When**: Before major releases

### Test Requirements

1. **Every bug fix** → Regression test
2. **New feature** → Unit + integration tests
3. **Edge cases** → Test None, missing attributes, errors
4. **Coverage** → Aim for 80%+

### Running Tests

```bash
# All tests
make test

# Unit tests only
pytest tests/unit/ -v

# Specific test
pytest tests/unit/test_media_player.py::test_volume_step -v

# With coverage
pytest --cov=custom_components.wiim --cov-report=html
```

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
        await self.coordinator.async_request_refresh()
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
    await self.coordinator.async_request_refresh()
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

## References

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [pywiim Library](https://github.com/mjcumming/pywiim)
- [LinkPlay API Docs](https://developer.arylic.com/httpapi/)
