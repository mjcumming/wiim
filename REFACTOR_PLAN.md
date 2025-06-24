# WiiM Integration Refactor Plan - Phase 2

> **Status**: API & Coordinator refactor ✅ COMPLETE (Phase 1) | Media Layer refactor 🚧 IN PROGRESS (Phase 2)

---

## 📊 Current State Summary

### ✅ Phase 1 Complete (Committed: 9755a83)

- **API modules**: 9 focused files (~200 LOC each) - api_base.py, api_device.py, etc.
- **Coordinator modules**: 8 focused files (~150 LOC each) - coordinator_polling.py, etc.
- **Test coverage**: Complete test suite for all new modules
- **Architecture**: Facade pattern, backward compatibility maintained

### 🎯 Phase 2 Targets (3 Large Files)

| File                  | Current Size     | Target    | Issues                                 |
| --------------------- | ---------------- | --------- | -------------------------------------- |
| `media_player.py`     | 1,178 LOC (44KB) | 4 modules | Entity complexity, optimistic state    |
| `media_controller.py` | 886 LOC (36KB)   | 3 modules | Missing `_image_cache`, business logic |
| `data.py`             | 742 LOC (29KB)   | 3 modules | Variable assignment bug, Speaker class |

**Total Reduction Target**: 2,806 LOC → ~10 focused modules (~250 LOC avg)

---

## 🚧 Phase 2: Media Layer Refactor

### Critical Fixes First

- [ ] **Fix `media_controller.py:90`** - Remove missing `_image_cache._clear()` call
- [ ] **Fix `data.py:534`** - Variable `val` assignment issue in `_status_field()`

### 1. Media Player Refactor (`media_player.py` → 4 modules)

**Current Issues**: 1,178 lines doing entity interface, optimistic state, commands, media browsing

```
media_player.py           # 300 LOC - Core HA entity interface & delegation
media_player_commands.py  # 250 LOC - Command methods with optimistic updates
media_player_media.py     # 200 LOC - Media browsing, quick stations, hex decoding
media_player_state.py     # 150 LOC - Optimistic state management helpers
```

#### Progress Tracker

- [ ] **media_player_state.py** - Extract optimistic state management
  - [ ] Optimistic volume/mute/state tracking
  - [ ] Debouncer logic
  - [ ] State clearing helpers
- [ ] **media_player_media.py** - Extract media browsing
  - [ ] `async_browse_media()` implementation
  - [ ] Quick stations YAML loading
  - [ ] Hex URL decoding helper
- [ ] **media_player_commands.py** - Extract command methods
  - [ ] Volume commands (set/up/down/mute)
  - [ ] Playback commands (play/pause/stop/seek)
  - [ ] Source/mode commands (source/sound/shuffle/repeat)
  - [ ] Group commands (join/leave)
- [ ] **media_player.py** - Refactor core entity
  - [ ] Core MediaPlayerEntity class
  - [ ] Property delegation to controller
  - [ ] Import updates & facade pattern

### 2. Media Controller Refactor (`media_controller.py` → 3 modules)

**Current Issues**: 886 lines handling all business logic, complex master/slave logic

```
media_controller.py          # 300 LOC - Main controller class & volume/playback
media_controller_group.py    # 250 LOC - Group management & master/slave logic
media_controller_media.py    # 200 LOC - Media metadata, image fetching, advanced features
```

#### Progress Tracker

- [ ] **Fix missing `_image_cache` issue** - Critical fix first
- [ ] **media_controller_media.py** - Extract media handling
  - [ ] Media metadata methods
  - [ ] Image cache & fetching (`get_media_image()`)
  - [ ] Preset & URL playback
- [ ] **media_controller_group.py** - Extract group logic
  - [ ] Group join/leave operations
  - [ ] Master/slave coordination
  - [ ] Member entity ID resolution
- [ ] **media_controller.py** - Refactor core controller
  - [ ] Volume/playback control
  - [ ] Source management
  - [ ] Core controller initialization

### 3. Data Layer Refactor (`data.py` → 3 modules)

**Current Issues**: 742 lines with Speaker class doing everything, group logic, helpers

```
data.py              # 300 LOC - Core Speaker class & basic properties
data_group.py        # 200 LOC - Group state management & multiroom logic
data_helpers.py      # 150 LOC - Lookup functions, device registration, IP updates
```

#### Progress Tracker

- [ ] **Fix variable assignment bug** - Critical fix first
- [ ] **data_helpers.py** - Extract helper functions
  - [ ] Speaker lookup functions (`find_speaker_by_uuid`, etc.)
  - [ ] Config entry helpers (`get_speaker_from_config_entry`)
  - [ ] IP update logic
- [ ] **data_group.py** - Extract group management
  - [ ] Group state update methods
  - [ ] Master/slave relationship management
  - [ ] Missing device discovery triggers
- [ ] **data.py** - Refactor core Speaker class
  - [ ] Basic Speaker initialization
  - [ ] Device info & coordinator integration
  - [ ] Core properties & typed model shortcuts

---

## 📅 Implementation Timeline

### Week 1: Critical Fixes & Helper Extraction

- **Day 1-2**: Fix critical linter errors
- **Day 3-4**: Extract `data_helpers.py` and test
- **Day 5-7**: Extract `media_player_state.py` and test

### Week 2: Media & Group Logic

- **Day 8-10**: Extract `media_controller_media.py` and test
- **Day 11-14**: Extract `data_group.py` and test

### Week 3: Commands & Core Refactor

- **Day 15-17**: Extract `media_player_commands.py` and test
- **Day 18-21**: Extract `media_controller_group.py` and test

### Week 4: Integration & Polish

- **Day 22-24**: Refactor core classes to use extracted modules
- **Day 25-28**: Comprehensive testing & documentation

---

## 🎯 Success Metrics

- ✅ **Size**: All modules <300 LOC (following API refactor success)
- ✅ **Functionality**: All features working, zero regressions
- ✅ **Testing**: 100% existing test pass rate maintained
- ✅ **Architecture**: Clean separation, maintainable code
- ✅ **Compatibility**: No breaking changes to public interfaces

---

## 🛡️ Risk Mitigation

1. **Incremental Approach**: One module extraction per commit
2. **Critical Fixes First**: Address linter errors before refactoring
3. **Facade Pattern**: Maintain existing imports for compatibility
4. **Comprehensive Testing**: Validate each extraction step
5. **Branch Strategy**: Feature branches for each major extraction

---

## 📝 Notes

- Following successful API refactor pattern from Phase 1
- Maintaining flat file structure for HA/HACS compatibility
- Preserving [cursor rules][memory:7814000417010377508]] for maintainable code
- All extractions maintain backward compatibility

---

**Next Action**: Fix critical linter errors then begin helper extraction

_Updated: Phase 2 planning complete, ready to begin implementation_
