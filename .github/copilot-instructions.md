# WiiM Home Assistant Integration - Development Rules

## Architecture

This integration is a **thin glue layer** between the `pywiim` library and Home Assistant.

### Core Principle

**If it's not directly gluing pywiim to HA, it shouldn't be here.**

- ✅ Entity creation
- ✅ Reading from pywiim
- ✅ Calling pywiim methods
- ✅ Config flow
- ❌ Device communication logic
- ❌ State management
- ❌ Business logic

### Component Responsibilities

- **`__init__.py`**: Setup entry, create pywiim client/coordinator
- **`coordinator.py`**: Thin wrapper around pywiim Player
- **`data.py`**: Minimal Speaker wrapper (holds coordinator)
- **`entity.py`**: Base entity class
- **Platform files** (`media_player.py`, `sensor.py`, etc.): Read from coordinator, call pywiim

### Data Flow

```
Device → pywiim Player → Coordinator.data → Entity Properties
Entity Method → Coordinator.player → pywiim Client → Device
```

## Critical Rules

### 1. pywiim is Source of Truth

**NEVER work around pywiim issues in the integration.**

If pywiim doesn't provide something:

1. **FIX IT IN PYWIIM** - Go fix the pywiim library directly
2. **DO NOT** add fallback detection logic
3. **DO NOT** add conditional checks for missing features
4. **DO NOT** work around pywiim bugs

### 2. File Location

**Every file must live inside `custom_components/wiim/` - this is the ONLY directory you may touch.**

- ✅ Modify files in `custom_components/wiim/`
- ❌ Never modify `homeassistant/` core folders
- ❌ Never import private HA internals

### 3. Test-Driven Development

**Every bug fix requires a test.**

1. Write failing test (reproduces bug)
2. Verify test fails
3. Fix the bug
4. Verify test passes
5. Add edge cases

### 4. Follow HA Patterns

**Use Home Assistant's recommended patterns.**

- `DataUpdateCoordinator` for polling
- `CoordinatorEntity` for entities
- `ConfigFlow` for setup
- Public HA APIs only

## Code Patterns

### Reading from pywiim

```python
@property
def volume_level(self) -> float | None:
    """Return volume level from pywiim Player."""
    player = self._get_player()
    return player.volume_level if player else None
```

### Calling pywiim Methods

```python
async def async_set_volume_level(self, volume: float) -> None:
    """Set volume via pywiim."""
    try:
        await self.coordinator.player.set_volume(volume)
        await self.coordinator.async_request_refresh()
    except WiiMError as err:
        raise HomeAssistantError(f"Failed to set volume: {err}") from err
```

### Config Entry Options

```python
@property
def volume_step(self) -> float:
    """Read from config entry options."""
    if hasattr(self, "speaker") and self.speaker.config_entry:
        return self.speaker.config_entry.options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
    return DEFAULT_VOLUME_STEP
```

### Safe Attribute Access

```python
# ✅ Good - safe access
upnp_client = getattr(player, "_upnp_client", None)
has_upnp = upnp_client is not None

# ❌ Bad - direct access
has_upnp = coordinator.upnp_client is not None  # AttributeError!
```

## Testing

### Test Structure

- **`tests/unit/`**: Unit tests (fast, isolated, mocked) - PRIMARY
- **`tests/integration/`**: Integration tests (realistic scenarios)
- **`scripts/`**: Manual validation (real devices) - SECONDARY

### Test Requirements

- Every bug fix → Regression test
- New feature → Unit + integration tests
- Edge cases → Test None, missing attributes, errors
- Coverage target: 80%+

### Running Tests

```bash
make test              # All tests
pytest tests/unit/     # Unit tests only
make test-quick        # Quick test (no coverage)
```

## File Naming

### Code Files

- ✅ Use lowercase: `media_player.py`
- ✅ Use underscores: `group_media_player.py`
- ❌ Don't use hyphens: `media-player.py`

### Documentation Files

- ✅ Use hyphens: `testing-strategy.md`
- ✅ Use YYYY.MM.DD format: `2025.11.28-architecture.md`
- ❌ Don't use underscores: `testing_strategy.md`

## Documentation

### Documentation Rules

**CRITICAL: Do not create documentation files unless explicitly requested.**

1. **Do NOT create progress/summary files**

   - ❌ No "TEST-SUITE-SUMMARY.md", "COVERAGE-PROGRESS.md", "FINAL-SUMMARY.md"
   - ❌ No "look what I did" documentation
   - ❌ No temporary status files
   - ✅ Update existing documentation instead

2. **Only create when:**

   - ✅ Explicitly requested by user
   - ✅ Needed for long-term reference
   - ✅ Replacing existing documentation
   - ✅ User-facing documentation

3. **Update existing files:**
   - ✅ `tests/README.md` - Test information
   - ✅ `docs/TESTING-CONSOLIDATED.md` - Testing strategy
   - ✅ `docs/ARCHITECTURE.md` - Architecture
   - ✅ `docs/DEVELOPMENT-RULES.md` - Rules

### Existing Documentation

- **`docs/ARCHITECTURE.md`**: Complete architecture guide
- **`docs/DEVELOPMENT-RULES.md`**: Development rules
- **`docs/TESTING-CONSOLIDATED.md`**: Testing strategy
- **`docs/test-directories-explained.md`**: Test directory explanation
- **`tests/README.md`**: Test quick reference
- **`development/README.md`**: Quick start guide
- **`docs/user-guide.md`**: User guide
- **`docs/faq-and-troubleshooting.md`**: FAQ

## Code Quality

### Requirements

- Type hints required on all functions
- Docstrings required on public methods
- Error handling with actionable messages
- Follow Home Assistant development guidelines

### Standards

- File size: < 500 LOC (split if larger)
- Function size: < 50 LOC (extract if larger)
- Complexity: < 10 (simplify if larger)

## Logging

### Log Levels

- **DEBUG**: Normal operation details
- **INFO**: Important state changes
- **WARNING**: Recoverable issues
- **ERROR**: Actual problems

### Format

```python
# ✅ Good - includes device name
_LOGGER.info("[%s] Volume set to %d%%", self.name, int(volume * 100))

# ❌ Bad - no context
_LOGGER.info("Volume set")
```

## When to Update This File

- When architectural decisions are made
- When patterns are established
- When bugs reveal design issues
- When asked to remember something important

**If asked to remember something, update this file or the appropriate documentation immediately.**
