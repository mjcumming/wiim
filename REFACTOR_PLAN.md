# WiiM Integration Refactor Plan - Phase 2

> **Status**: API & Coordinator refactor ✅ COMPLETE (Phase 1) | Media Layer refactor 🚧 IN PROGRESS (Phase 2)

---

## 📊 Current State Summary

### ✅ Phase 1 Complete (Committed: 9755a83)

- **API modules**: 9 focused files (~200 LOC each) - api_base.py, api_device.py, etc.
- **Coordinator modules**: 8 focused files (~150 LOC each) - coordinator_polling.py, etc.
- **Test coverage**: Complete test suite for all new modules
- **Architecture**: Facade pattern, backward compatibility maintained

### 🎯 Phase 2 Targets - Updated Focus

| File                  | Current Size     | Target    | Status                                                      |
| --------------------- | ---------------- | --------- | ----------------------------------------------------------- |
| `media_player.py`     | 1,178 LOC (44KB) | 4 modules | 🎯 **PRIMARY TARGET** - Entity complexity, optimistic state |
| `media_controller.py` | 886 LOC (36KB)   | 3 modules | 🎯 **SECONDARY TARGET** - Business logic extraction         |
| `data.py`             | 694 LOC (29KB)   | ✅ DONE   | ✅ **COMPLETE** - Strategic decision: good size             |

**Updated Reduction Target**: 2,064 LOC → ~7 focused modules (~280 LOC avg)
**Progress**: 1 of 3 complete (data layer) → Focus on media layer

---

## 🚧 Phase 2: Media Layer Refactor

### Critical Fixes First ✅ COMPLETE (commit: 86b7069)

- [x] **Fix `media_controller.py:90`** - Remove missing `_image_cache._clear()` call
- [x] **Fix `data.py:534`** - Variable `val` assignment issue in `_status_field()`
- [x] **Fix `data.py` import redefinition** - Removed duplicate WiiMDeviceInfo import

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

### 3. Data Layer Refactor ✅ STRATEGIC DECISION: COMPLETE

**Original Issues**: 742 lines → **Resolved**: Now 694 LOC (much more manageable)

```
data.py              # 694 LOC - Cohesive Speaker class with integrated group logic ✅ GOOD SIZE
data_helpers.py      # 142 LOC - Lookup functions, device registration, IP updates ✅ COMPLETE
```

#### Progress Tracker ✅ COMPLETE

- [x] **Fix variable assignment bug** - Critical fix first ✅ COMPLETE
- [x] **data_helpers.py** - Extract helper functions ✅ COMPLETE (commit: e6a8846)
  - [x] Speaker lookup functions (`find_speaker_by_uuid`, etc.)
  - [x] Config entry helpers (`get_speaker_from_config_entry`)
  - [x] IP update logic
- [x] **Strategic decision**: Keep remaining code together (cohesive, tightly coupled group logic)

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

**Next Action**: ✅ Data layer complete → Extract media_player_state.py (Day 5-7) from 1,178-line media_player.py

_Updated: Phase 2 planning complete, ready to begin implementation_
