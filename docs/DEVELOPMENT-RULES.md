# Development Rules & Guidelines

This file is the **integration rules contract**: how we build, how we talk to each other, and where durable decisions live. It complements **[ARCHITECTURE.md](ARCHITECTURE.md)** (how the code is shaped) and **[adr/README.md](adr/README.md)** (numbered decisions).

**Cursor / agents:** persistent seed context lives in **[`.cursor/rules/wiim-project.mdc`](../.cursor/rules/wiim-project.mdc)** (`alwaysApply: true`) and **[`AGENTS.md`](../AGENTS.md)** at the repo root—both point here.

## Rules map (read this first)

| Topic | What you need to know | Where |
| ----- | ---------------------- | ----- |
| **What this integration does** | Custom integration for **Home Assistant** that exposes WiiM / LinkPlay devices as entities (media players, sensors, etc.) and services. It does **not** reimplement the device protocol. | [ARCHITECTURE.md](ARCHITECTURE.md#architecture-overview); repo [README](../README.md) |
| **How it works** | **Coordinator** polls / listens; **entities** read coordinator + call **pywiim** `Player` / services; config via **ConfigFlow**. Data flows: device ↔ pywiim ↔ coordinator ↔ entities. | [ARCHITECTURE.md](ARCHITECTURE.md) (overview, data flow, components) |
| **How it uses pywiim** | **pywiim owns** HTTP/UPnP, parsing, multiroom, capabilities. This repo is a **thin glue layer**: map HA ↔ pywiim only. **Do not** paper over device bugs in the integration—**fix pywiim** (we maintain **both** repos; ship a library release + manifest bump when needed). **Do not edit a sibling pywiim checkout from here**—**Rule 2c**. **Operational gating**—**ADR 0007**. | **Rule 2 / 2a / 2b / 2c / 3**; [ADR 0007](adr/0007-capability-gating-strict-contract.md); [development/HA_INTEGRATION_GUIDE.md](../development/HA_INTEGRATION_GUIDE.md); upstream [HA_INTEGRATION](https://github.com/mjcumming/pywiim/blob/main/docs/integration/HA_INTEGRATION.md) |
| **How we talk to each other** | **Issue** (or Discussion for open questions) before speculative code. **PR** references the issue; **review** addresses comments. If anything is ambiguous, **stop and ask**—no guessing. Deviations from these rules need **issue + explicit design sign-off**. | **Non-negotiables** §3; [CONTRIBUTING.md](../CONTRIBUTING.md) |
| **How we make contracts** | **User-facing:** behavior and releases = **CHANGELOG** + **user docs** (`docs/user-guide.md`, FAQ, TTS guide). **Machine/install:** `manifest.json`, `requirements.txt` / pywiim pin. **API surface:** public HA entity/service schemas only—no private HA internals. **Maintainer invariants:** **ADRs** when we must not “unlearn” a trade-off (see Rule 8). | CHANGELOG; `manifest.json`; **Rule 8**; [adr/README.md](adr/README.md) |
| **How we do ADRs** | Numbered files in **`docs/adr/`**. Use when a PR encodes a **long-lived** guarantee, trade-off, or reversal—not for every bugfix. Draft with **Status: Proposed** if needed. Template: **[0000-template.md](adr/0000-template.md)**. | **Rule 8**; [adr/README.md](adr/README.md) |

**Nothing “disappeared”**—rules were always split across this file, **ARCHITECTURE.md**, **CONTRIBUTING.md**, and changelogs. This table is the **index** so you land in the right place on day one.

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
- Get approval before deviating (for integration-level trade-offs, capture intent in **[docs/adr/](adr/README.md)** — see Rule 8)

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

We maintain **both** [mjcumming/wiim](https://github.com/mjcumming/wiim) (this integration) and [mjcumming/pywiim](https://github.com/mjcumming/pywiim) (the library). “Fix upstream” means **open a pywiim PR** when the fault is in the library—not “ignore it because another team owns it.”

If pywiim doesn't provide something:

1. **FIX IT IN PYWIIM** - Implement or repair it in the library, release, then bump the integration’s `manifest.json` requirement if needed
2. **DO NOT** add fallback detection logic in the integration to compensate
3. **DO NOT** add conditional checks for missing features that belong on `Player`/client
4. **DO NOT** duplicate device protocol logic here to avoid touching pywiim

**Why:**

- pywiim is THE source of truth for device behavior
- Working around creates technical debt and splits fixes between repos
- Library fixes benefit every consumer of pywiim, not only Home Assistant
- Integration stays a thin wrapper

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

### Rule 2b: Fix in the right repository (integration vs pywiim)

**Same maintainers, two products**—choose the layer that matches the bug.

| Fix belongs in **WiiM integration** (`custom_components/wiim/`) when… | Fix belongs in **pywiim** when… |
| ----------------------------------------------------------------------- | --------------------------------- |
| HA entity state, attributes, or service schema are wrong or incomplete | HTTP command, response parsing, URL encoding, or API semantics are wrong |
| Coordinator refresh timing, debouncing, or HA-specific error mapping | `Player` / `Group` / client behavior, capability flags, multiroom routing |
| Config flow, device registry, translations, diagnostics formatting | Anything that would still be wrong if you called pywiim from a plain Python script (no HA) |

**Heuristic:** If you need to read LinkPlay/WiiM **wire format** or **undocumented firmware behavior** to fix it → **pywiim**. If you only need **Home Assistant platform rules** → **integration**.

**pywiim checkout:** the library repo includes **`pywiim.code-workspace`** (VS Code: venv, ruff, format-on-save). Use a multi-root workspace in your editor if you often edit **wiim + pywiim** together.

**Home Assistant–oriented library docs** (read before inventing patterns): [HA_INTEGRATION.md](https://github.com/mjcumming/pywiim/blob/main/docs/integration/HA_INTEGRATION.md), [HA_CAPABILITIES.md](https://github.com/mjcumming/pywiim/blob/main/docs/integration/HA_CAPABILITIES.md), [API_REFERENCE.md](https://github.com/mjcumming/pywiim/blob/main/docs/integration/API_REFERENCE.md), and the rest of **`docs/integration/`** in the pywiim tree.

### Rule 2c: Do not edit the pywiim library from this repository (agents / automation)

When your task is **WiiM Home Assistant integration** work in **this** repo (`mjcumming/wiim`):

- **Do not** modify the **pywiim** source tree (e.g. a sibling checkout like `core/pywiim`, `../pywiim`, or any path outside this integration repo) to “finish” an integration change.
- **Consume** pywiim by **released version only**: bump `custom_components/wiim/pywiim-version.txt`, `manifest.json` `requirements`, run **`pip install pywiim==…`** in the venv you use for tests/dev, and follow **Rule 2b** to open PRs on **[mjcumming/pywiim](https://github.com/mjcumming/pywiim)** for real library fixes.

**Why:** The integration workspace and the library workspace are **separate checkouts**. Editing pywiim “next door” from an integration task creates unreviewed library drift and wrong git history. Agents default to **integration-only edits here**; **pywiim changes ship from the pywiim repo.**

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

### Rule 8: ADRs for invariants learned the hard way

**Not every PR needs an ADR.** Most fixes belong in **CHANGELOG** + tests only.

**Add or update a numbered ADR** (`docs/adr/NNNN-slug.md`, see [template](adr/0000-template.md)) when the PR encodes a **long-lived contract** we must not accidentally undo later—for example:

- A **user-visible guarantee** or **explicit non-guarantee** (e.g. multiroom + TTS, `supported_features`, scene restore behavior).
- A **non-obvious trade-off** discovered in production (firmware quirks, HA API limits, “why we don’t do X”).
- **Reversing** a documented approach (supersede the old ADR; say so in CHANGELOG).

If it is important but not fully baked, open an ADR with **Status: Proposed** and link the issue/PR—or track in a GitHub issue until the ADR lands.

**Do not** rely on chat, closed PR threads, or tribal memory alone for those cases—the next person (or model) will not have that context.

## Mental Checklist

Before writing code, ask yourself:

1. **What user story am I solving?** (quote the Issue #)
2. **Where does this logic belong?** (`pywiim` ↔ `coordinator.py` ↔ entity/service)
3. **What data do I need from the device?** (via `pywiim` client methods)
4. **How will I test success & failure?** (unit tests)
5. **How does this interact with multi-room state?**
6. **What happens if the device is offline?** (timeouts, retries)
7. **How will this appear in Home Assistant UI?** (state, attributes, services)
8. **Does this change a long-lived invariant?** If yes → **ADR** (Rule 8), not only CHANGELOG—use **Proposed** status while in flight if needed.

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
  - Codecov requires **75% patch coverage** for new/changed code (see `scripts/check-before-push.sh`; override with `CODECOV_PATCH_TARGET` if the dashboard target changes)
  - Patch coverage = coverage of lines you added or modified in your PR
  - This is separate from overall project coverage
  - New/changed lines should have corresponding tests so the patch stays above the target
  - Codecov will fail the CI check if patch coverage is below the target
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
- [ ] **Patch coverage ≥ 75% (Codecov requirement; run `./scripts/check-before-push.sh` to verify)**
- [ ] Docs/changelog updated (if needed)
- [ ] **ADR / design capture** (if applicable): long-lived trade-off or reversal → new or updated `docs/adr/NNNN-*.md` + issue link (Rule 8; **Proposed** OK until accepted)
- [ ] Tested on real device (if applicable)
- [ ] Follows architecture patterns
- [ ] Type hints on all functions
- [ ] Error handling with actionable messages

## Common Pitfalls

| Symptom                            | Root Cause                  | Fix                                     |
| ---------------------------------- | --------------------------- | --------------------------------------- |
| Accidentally imported HA internals | Breaking core encapsulation | Use public helpers only                 |
| Working around pywiim issues       | Wrong layer for fix         | Fix in pywiim (same maintainers); see **Rule 2b** |
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
   - ✅ **Architecture Decision Records** (`docs/adr/`) — invariants and trade-offs (Rule 8)
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
   - ✅ `docs/adr/` - ADRs when behavior or documented contracts change (Rule 8)
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
- `adr/` - Numbered ADRs + template
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

- When architectural decisions are made (**prefer an ADR** in `docs/adr/` for the durable part—Rule 8)
- When patterns are established
- When bugs reveal design issues
- When new requirements emerge
- When documentation rules are violated

**If asked to remember something, update this file or the appropriate documentation immediately.**
