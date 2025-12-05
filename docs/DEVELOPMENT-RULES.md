# Development Rules & Guidelines

## Non-Negotiables

### 1. File Location

**Every file must live inside `custom_components/wiim/` - this is the ONLY directory you may touch.**

- ✅ Modify files in `custom_components/wiim/`
- ❌ Never modify `homeassistant/` core folders
- ❌ Never import private HA internals
- ❌ Never create files outside `custom_components/wiim/` (except tests/docs)

### 2. Follow Guidelines

**Follow this guide line-by-line. Deviations require an Issue + signed-off design note.**

- Read the architecture document first
- Understand the pattern before coding
- Ask questions if unclear
- Get approval before deviating

### 3. Ask Questions

**If you are confused, STOP → ask in GitHub Discussion. Guessing = bugs + rework.**

## Golden Rules

### Rule 1: Spec > Ego

**Build only what the ticket describes.**

- Don't add "nice to have" features
- Don't refactor unrelated code
- Don't optimize prematurely
- Focus on the issue at hand

### Rule 2: pywiim is Source of Truth

**NEVER work around pywiim issues in the integration.**

If pywiim doesn't provide something:

1. **FIX IT IN PYWIIM** - Go fix the pywiim library directly
2. **DO NOT** add fallback detection logic
3. **DO NOT** add conditional checks for missing features
4. **DO NOT** work around pywiim bugs

**Why:**

- pywiim is THE source of truth
- Working around creates technical debt
- Fixes belong in pywiim so ALL users benefit
- Integration should be thin wrapper, not compensating

### Rule 2a: Reference Upstream Documentation

**ALWAYS reference upstream pywiim documentation guides instead of duplicating content.**

When working with pywiim integration patterns or API usage:

1. **Reference** `/development/HA_INTEGRATION_GUIDE.md` for Home Assistant integration patterns
2. **Reference** the upstream [HA Integration Guide](https://github.com/mjcumming/pywiim/blob/main/docs/integration/HA_INTEGRATION.md) for detailed patterns
3. **Reference** the upstream [API Reference](https://github.com/mjcumming/pywiim/blob/main/docs/integration/API_REFERENCE.md) for API documentation
4. **DO NOT** duplicate upstream documentation content in this repository
5. **DO NOT** create local copies of upstream guides (they become stale)

**When pywiim version is updated:**

1. **Update** the review date in `/development/HA_INTEGRATION_GUIDE.md`
2. **Update** the pywiim version tracked in that file (if documented)
3. **Check** if upstream guides have changed and note any breaking changes
4. **Update** `manifest.json` with the new minimum pywiim version requirement
5. **Document** in CHANGELOG.md the pywiim version update

**Why:**

- Upstream documentation is maintained alongside library changes
- Prevents documentation drift and stale information
- Single source of truth reduces maintenance burden
- Version tracking ensures compatibility awareness

### Rule 3: Thin Glue Layer

**If it's not directly gluing pywiim to HA, it shouldn't be here.**

- ✅ Entity creation
- ✅ Reading from pywiim
- ✅ Calling pywiim methods
- ✅ Config flow
- ❌ Device communication logic
- ❌ State management
- ❌ Business logic

### Rule 4: Test-Driven Development

**Every bug fix requires a test.**

1. Write failing test (reproduces bug)
2. Verify test fails
3. Fix the bug
4. Verify test passes
5. Add edge cases

### Rule 5: Follow HA Patterns

**Use Home Assistant's recommended patterns.**

- `DataUpdateCoordinator` for polling
- `CoordinatorEntity` for entities
- `ConfigFlow` for setup
- Public HA APIs only

### Rule 6: Type Hints Required

**All code must have type hints.**

```python
def async_set_volume_level(self, volume: float) -> None:
    """Set volume level."""
    pass
```

### Rule 7: Error Handling

**Fail loudly with actionable messages.**

```python
# ✅ Good
raise HomeAssistantError(f"Failed to set volume on {self.name}: {err}") from err

# ❌ Bad
raise HomeAssistantError("Error")
```

## Mental Checklist

Before writing code, ask yourself:

1. **What user story am I solving?** (quote the Issue #)
2. **Where does this logic belong?** (`pywiim` ↔ `coordinator.py` ↔ entity/service)
3. **What data do I need from the device?** (via `pywiim` client methods)
4. **How will I test success & failure?** (unit tests)
5. **How does this interact with multi-room state?**
6. **What happens if the device is offline?** (timeouts, retries)
7. **How will this appear in Home Assistant UI?** (state, attributes, services)

**If any answer is fuzzy—stop and clarify.**

## Code Quality Standards

### File Size

- **Target**: < 500 LOC per file
- **Action**: Split if larger
- **Exception**: Large entity files (media_player.py) may exceed

### Function Size

- **Target**: < 50 LOC per function
- **Action**: Extract helper functions
- **Exception**: Complex state machines may exceed

### Complexity

- **Target**: Cyclomatic complexity < 10
- **Action**: Simplify logic, extract methods
- **Exception**: State machines may exceed

### Type Hints

- **Required**: All function signatures
- **Required**: All class attributes
- **Optional**: Local variables (but recommended)

### Docstrings

- **Required**: All public methods
- **Required**: All classes
- **Optional**: Private methods (but recommended)

## File Naming Conventions

### Code Files

- ✅ Use lowercase: `media_player.py`
- ✅ Use underscores for words: `group_media_player.py`
- ❌ Don't use hyphens: `media-player.py` (Python doesn't allow)
- ❌ Don't use camelCase: `MediaPlayer.py`

### Documentation Files

- ✅ Use hyphens: `testing-strategy.md`
- ✅ Use YYYY.MM.DD format for dated docs: `2025.11.28-architecture.md`
- ❌ Don't use underscores: `testing_strategy.md`

### Test Files

- ✅ Match source file: `test_media_player.py` for `media_player.py`
- ✅ Use `test_` prefix: `test_config_flow.py`
- ✅ Group by component: `test_media_player.py`, `test_sensor.py`

## Import Organization

### Import Order

1. **Standard library**
2. **Third-party** (homeassistant, pywiim)
3. **Local** (custom_components.wiim)

### Example

```python
# Standard library
from typing import Any
import logging

# Third-party
from homeassistant.components.media_player import MediaPlayerEntity
from pywiim.exceptions import WiiMError

# Local
from .const import DOMAIN
from .entity import WiimEntity
```

## Logging Standards

### Log Levels

- **DEBUG**: Normal operation details, state changes
- **INFO**: Important state changes, setup completion
- **WARNING**: Recoverable issues, deprecated features
- **ERROR**: Actual problems requiring attention

### Log Format

```python
# ✅ Good - includes device name
_LOGGER.info("[%s] Volume set to %d%%", self.name, int(volume * 100))

# ❌ Bad - no context
_LOGGER.info("Volume set")
```

### Include Context

- Device name: `[Device Name]`
- Entity ID: `entity_id`
- Operation: What you're doing
- Result: Success/failure

## Testing Requirements

### Test Coverage

- **CRITICAL: Codecov Patch Coverage Requirement**
  - Codecov requires **77.88% patch coverage** for new/changed code
  - Patch coverage = coverage of lines you added or modified in your PR
  - This is separate from overall project coverage (currently 77.64%)
  - **Every new line of code must have corresponding tests**
  - Codecov will fail the CI check if patch coverage is below 77.88%
  - Always add tests when adding or modifying code
- **Minimum**: 10% (current requirement)
- **Target**: 80%+
- **Focus**: Core functionality first

### Test Types

1. **Unit Tests** (`tests/unit/`)

   - Fast, isolated, mocked
   - Run on every commit
   - Test all code paths

2. **Manual Validation** (`scripts/`)
   - Real devices
   - Before major releases
   - User acceptance

### Test Requirements

- ✅ **Every new code addition → Write tests immediately**
- ✅ **Every code modification → Update/add tests for changed functionality**
- ✅ Every bug fix → Regression test
- ✅ New feature → Unit tests
- ✅ Edge cases → Test None, missing attributes, errors
- ✅ All tests must pass before merge
- ✅ Verify patch coverage with `pytest --cov` before committing

## PR Checklist

Before submitting a PR:

- [ ] Code confined to `custom_components/wiim/`
- [ ] Fulfils Issue #\_\_\_ ✅
- [ ] Added/updated unit tests for all new/changed code
- [ ] All tests pass: `make test`
- [ ] Passes linting: `make lint`
- [ ] Coverage ≥ 10% (target 80%+)
- [ ] **Patch coverage ≥ 77.88% (Codecov requirement - verify with `pytest --cov`)**
- [ ] Docs/changelog updated (if needed)
- [ ] Tested on real device (if applicable)
- [ ] Follows architecture patterns
- [ ] Type hints on all functions
- [ ] Error handling with actionable messages

## Common Pitfalls

| Symptom                            | Root Cause                  | Fix                                     |
| ---------------------------------- | --------------------------- | --------------------------------------- |
| Accidentally imported HA internals | Breaking core encapsulation | Use public helpers only                 |
| Working around pywiim issues       | Wrong layer for fix         | Fix in pywiim, not integration          |
| Missing type hints                 | Code quality                | Add type hints to all functions         |
| No error handling                  | Poor UX                     | Add try/except with actionable messages |
| Missing tests                      | Regression risk             | Write test before fixing bug            |
| Large files                        | Hard to maintain            | Split into smaller modules              |

## Documentation Guidelines

**Update existing files rather than creating new ones.**

### ❌ Do NOT Create

1. **Progress/Status Files**

   - ❌ "TEST-SUITE-SUMMARY.md"
   - ❌ "COVERAGE-PROGRESS.md"
   - ❌ "FINAL-SUMMARY.md"
   - ❌ "RESTRUCTURE-SUMMARY.md"
   - ❌ Any "look what I did" files

2. **Redundant Documentation**

   - ❌ Multiple files covering the same topic
   - ❌ Temporary status updates
   - ❌ Session-specific information

3. **Self-Congratulatory Files**
   - ❌ Files that just summarize work done
   - ❌ Files that duplicate existing information
   - ❌ Files that will become outdated quickly

### ✅ DO Create

1. **Long-Term Reference**

   - ✅ Architecture documentation
   - ✅ Development rules and guidelines
   - ✅ Testing strategy
   - ✅ User guides and FAQs

2. **When Explicitly Requested**

   - ✅ User asks for specific documentation
   - ✅ Replacing/consolidating existing files
   - ✅ New topic not covered elsewhere

3. **User-Facing Documentation**
   - ✅ Installation guides
   - ✅ Usage guides
   - ✅ Troubleshooting guides
   - ✅ API documentation

### ✅ DO Update

1. **Existing Documentation**

   - ✅ `tests/README.md` - Test information
   - ✅ `docs/TESTING-CONSOLIDATED.md` - Testing strategy
   - ✅ `docs/ARCHITECTURE.md` - Architecture changes
   - ✅ `docs/DEVELOPMENT-RULES.md` - This file (rules)
   - ✅ `docs/INDEX.md` - Documentation index

2. **Code Documentation**
   - ✅ Docstrings in code
   - ✅ Inline comments
   - ✅ Type hints

### Documentation Structure

#### `/docs/` - User and Developer Documentation

**Files**:

- `ARCHITECTURE.md` - Architecture and design
- `DEVELOPMENT-RULES.md` - Development rules
- `TESTING-CONSOLIDATED.md` - Testing strategy (includes test directory explanation)
- `PROJECT-STRUCTURE.md` - Project structure
- `INDEX.md` - Documentation index
- `user-guide.md` - User guide
- `faq-and-troubleshooting.md` - FAQ
- `bug-fix-testing-checklist.md` - Bug fix workflow

**Do NOT add**: Progress reports, summaries, temporary status

#### `/tests/README.md` - Test Quick Reference

**Content**:

- How to run tests
- Test structure
- Quick examples
- Coverage goals (current status)

**Do NOT add**: Detailed progress reports, session summaries

#### `/development/` - Developer Guides

**Files**:

- `README.md` - Quick start
- `TESTING.md` - Testing guide (if exists)

### Before Creating Documentation

Ask:

1. Does an existing file cover this?
2. Is this temporary or long-term?
3. Will this become outdated quickly?
4. Is this just a status update?

**If yes to any, update existing file instead.**

### Use Git for Progress Tracking

**Don't create files for:**

- Progress reports
- Status updates
- Session summaries
- Coverage milestones

**Use instead:**

- Git commits (with meaningful messages)
- Test output (`pytest --cov`)
- CI/CD reports
- Git history

## When to Update Rules

- When architectural decisions are made
- When patterns are established
- When bugs reveal design issues
- When new requirements emerge
- When documentation rules are violated

**If asked to remember something, update this file or the appropriate documentation immediately.**
