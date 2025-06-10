# Contributing to WiiM Integration

Thank you for your interest in contributing to the WiiM Home Assistant integration! This document provides guidelines and best practices for contributing.

## Development Guidelines

### Non-negotiables

1. **File Location**: Every file must live inside `custom_components/wiim/` - this is the only directory you may touch.
   - Never modify `homeassistant/` core folders
   - Never import private HA internals

2. **Follow Guidelines**: Follow this guide line-by-line. Deviations require an Issue + signed-off design note from the Tech Lead.

3. **Ask Questions**: If you are confused, STOP → ask in GitHub Discussion. Guessing = bugs + rework.

### Golden Rules

1. **Spec > Ego** - build only what the ticket describes
2. Follow Home Assistant Dev Guidelines
3. Follow HACS repo standards & semantic versioning
4. LinkPlay API is canonical - WiiM quirks wrapped in code, never leak
5. Keep modules small, composable, and typed (< 200 LOC)
6. Track all work (Issue → Branch → PR → Review)
7. Fail loudly with actionable log messages

### Mental Checklist

Before writing code, ask yourself:

1. What user story am I solving? (quote the Issue #)
2. Where does this logic belong? (`api.py` ↔ `coordinator.py` ↔ entity/service)
3. What data do I need from the device? (`getStatusEx`, `getPlayerStatus`, etc.)
4. How will I test success & failure? (unit + integration test)
5. How does this interact with multi-room state?
6. What happens if the device is offline? (timeouts, retries)
7. How will this appear in Home Assistant UI? (state, attributes, services)

If any answer is fuzzy—stop and clarify.

### Common Pitfalls

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Accidentally imported `homeassistant.components.media_player` internals | Breaking core encapsulation | Refactor to use public helpers only |
| Group slider only moves host | Missing service loop | Implement `set_group_volume` helper |
| JSON decode error | Field hex-encoded | Use `bytes.fromhex().decode()` to parse `Title`, `Artist` |

### PR Checklist

- [ ] Code confined to `custom_components/wiim/`
- [ ] Fulfils Issue #___ ✅
- [ ] Added/updated unit + integration tests
- [ ] Passes `pre-commit` & coverage ≥ 90%
- [ ] Docs/changelog updated
- [ ] Tested on real device (model & firmware listed)

## When in Doubt

1. Re-read this file
2. Open GitHub Discussion with "QUESTION:" prefix
3. Wait for sign-off before coding 