# WiiM Integration Enhancement - TODO Tracker

## 🎯 Project Overview

Three major improvements to enhance the WiiM Home Assistant integration:

1. ✅ **Adaptive Polling** - Smart 1s/5s polling based on playback state
2. 🎬 **Virtual Group Media Player** - Unified group control following Sonos patterns
3. 🎵 **Media Browser Enhancement** - Browse HA media sources

---

## ✅ PHASE 1: ADAPTIVE POLLING [COMPLETE]

### Core Implementation ✅

- [x] **coordinator_polling.py**: Added `_determine_adaptive_interval()` function
- [x] **Polling Logic**: 1-second during playback, 5-second when idle
- [x] **Group Awareness**: Master checks slave playback states
- [x] **Error Handling**: Graceful fallback to safe intervals
- [x] **Diagnostics**: Added polling state to sensor attributes

### Testing ✅

- [x] **test_adaptive_polling.py**: Core functionality tests
- [x] **Integration Tests**: Verified polling switches correctly
- [x] **Error Cases**: Exception handling validated

### Benefits Delivered ✅

- [x] **Performance**: Reduced unnecessary polling by 80% during idle
- [x] **Responsiveness**: Near real-time updates during playback
- [x] **Efficiency**: Group-aware polling prevents redundant fast polling

---

## 🎬 PHASE 2: VIRTUAL GROUP MEDIA PLAYER [IN PROGRESS]

### Step 1: Core Entity Creation 🔄

- [ ] **group_media_player.py**: Create `WiiMGroupMediaPlayer` class
  - [ ] Persistent entity with dynamic availability
  - [ ] Available only when speaker is master with slaves
  - [ ] Proper device linkage via `via_device`
  - [ ] Dynamic naming based on group composition
- [ ] **Entity Properties**:
  - [ ] `available` property (master + has slaves)
  - [ ] `name` property (dynamic: "Living Room + Kitchen")
  - [ ] `supported_features` (mirror coordinator features)
  - [ ] `state` property (mirror coordinator playback state)

### Step 2: Control Implementation 🔄

- [ ] **Volume Controls**:
  - [ ] `volume_level` (show max volume of group)
  - [ ] `is_volume_muted` (muted only if ALL muted)
  - [ ] `async_set_volume_level()` (set all members)
  - [ ] `async_mute_volume()` (mute/unmute all members)
- [ ] **Playback Controls**:
  - [ ] `async_media_play()` (via coordinator)
  - [ ] `async_media_pause()` (via coordinator)
  - [ ] `async_media_stop()` (via coordinator)
  - [ ] `async_media_next_track()` (via coordinator)
  - [ ] `async_media_previous_track()` (via coordinator)

### Step 3: Media Information 🔄

- [ ] **Media Properties**:
  - [ ] `media_title` (from coordinator)
  - [ ] `media_artist` (from coordinator)
  - [ ] `media_album_name` (from coordinator)
  - [ ] `media_duration` (from coordinator)
  - [ ] `media_position` (from coordinator)
- [ ] **Group Management**:
  - [ ] `async_unjoin()` (dissolve group)
  - [ ] `extra_state_attributes` (group member info)
  - [ ] Group composition change detection

### Step 4: Platform Integration 🔄

- [ ] **media_player.py**: Update `async_setup_entry()`
  - [ ] Always create both entities
  - [ ] Group player availability controlled dynamically
- [ ] **Entity Lifecycle**:
  - [ ] Proper state updates when group forms/dissolves
  - [ ] Change logging for group composition
  - [ ] Availability transition logging

### Step 5: Migration & Cleanup 📋

- [ ] **Deprecation Strategy**:
  - [ ] Add deprecation warnings for old entities
  - [ ] `number.group_volume` → `media_player.group_coordinator`
  - [ ] `switch.group_mute` → `media_player.group_coordinator`
- [ ] **Entity Registry Cleanup**:
  - [ ] Migration helper in `__init__.py`
  - [ ] Remove old entities from registry
  - [ ] Log migration actions
- [ ] **Documentation**:
  - [ ] Migration guide with automation examples
  - [ ] Dashboard card migration examples
  - [ ] Breaking changes documentation

### Step 6: Testing 📋

- [ ] **test_group_media_player.py**: Comprehensive test suite
  - [ ] Availability logic (master with slaves)
  - [ ] Volume synchronization tests
  - [ ] Media info mirroring tests
  - [ ] Group formation/dissolution tests
  - [ ] Error handling tests
- [ ] **Integration Testing**:
  - [ ] Real device testing (if available)
  - [ ] Multi-speaker group scenarios
  - [ ] Automation compatibility testing

### Expected Outcomes 🎯

- [ ] **User Experience**: Single entity for group control
- [ ] **Sonos Parity**: Following established HA patterns
- [ ] **Simplified Automations**: One entity instead of multiple
- [ ] **Better Discovery**: Clear group relationships in UI

---

## 🎵 PHASE 3: MEDIA BROWSER ENHANCEMENT [PLANNED]

### Step 1: Media Source Integration 📋

- [ ] **media_player_browser.py**: Extend `async_browse_media()`
  - [ ] Handle `media-source://` URLs
  - [ ] Add "Media Library" shelf to root
  - [ ] Implement audio format filtering
  - [ ] Nested browsing support
- [ ] **Content Filtering**:
  - [ ] Audio format compatibility check
  - [ ] MIME type validation
  - [ ] File extension fallback detection

### Step 2: Playback Integration 📋

- [ ] **media_player_commands.py**: Update `async_play_media()`
  - [ ] Media source URL resolution
  - [ ] `media_source.async_resolve_media()` integration
  - [ ] Error handling for unresolvable sources
  - [ ] Format validation before playback

### Step 3: Enhanced Browsing 📋

- [ ] **Dynamic Format Detection**:
  - [ ] Runtime audio format discovery
  - [ ] Smart MIME type handling
  - [ ] Extension-based format detection
- [ ] **User Experience**:
  - [ ] Unified browser interface
  - [ ] Clear media source organization
  - [ ] Responsive error messages

### Step 4: Testing & Validation 📋

- [ ] **test_media_browser_enhanced.py**: Test suite
  - [ ] Media source browsing tests
  - [ ] URL resolution tests
  - [ ] Format filtering tests
  - [ ] Error handling tests
- [ ] **Integration Testing**:
  - [ ] Local media file testing
  - [ ] HA Add-on compatibility
  - [ ] Various audio format testing

### Expected Outcomes 🎯

- [ ] **HA Ecosystem Integration**: Browse all HA media sources
- [ ] **Format Compatibility**: Only show playable content
- [ ] **Unified Interface**: Presets + Quick Stations + HA Media
- [ ] **Better Discovery**: Access to local music libraries

---

## 📈 Progress Tracking

### Overall Progress: 33% Complete (1/3 phases)

- ✅ **Phase 1**: Adaptive Polling - **COMPLETE**
- 🔄 **Phase 2**: Virtual Group Media Player - **0% Complete**
- 📋 **Phase 3**: Media Browser Enhancement - **0% Complete**

### Current Sprint: Phase 2 - Virtual Group Media Player

**Next Action**: Create `group_media_player.py` with `WiiMGroupMediaPlayer` class

### Key Milestones

- [x] **Dec 2024**: Adaptive polling implementation
- [ ] **Q1 2025**: Virtual group media player
- [ ] **Q1 2025**: Media browser enhancement
- [ ] **Q1 2025**: Documentation and migration guides

---

## 🚀 Quick Start Commands

### Run Tests

```bash
# All unit tests
python tests/run_tests.py --unit

# Specific feature tests
python -m pytest tests/unit/test_adaptive_polling.py -v
python -m pytest tests/unit/test_group_media_player.py -v  # When created

# Linting
python tests/run_tests.py --lint
```

### Development Workflow

```bash
# Create feature branch
git checkout -b feature/group-media-player

# Make incremental commits
git add -A && git commit -m "feat: add WiiMGroupMediaPlayer entity skeleton"

# Test changes
make test

# Push feature
git push origin feature/group-media-player
```

---

## 📝 Notes & Considerations

### Architecture Decisions

- **Sonos Pattern**: Following established HA group media player patterns
- **Backward Compatibility**: Deprecation warnings before breaking changes
- **Modular Design**: Each feature in separate modules for maintainability

### Technical Debt

- Remove problematic multiroom tests that don't affect core functionality
- Consider refactoring test mocking patterns for consistency
- Update documentation to reflect new architecture

### Future Enhancements

- Configuration options for adaptive polling intervals
- Advanced group management (create/join groups from HA)
- Enhanced media browser with search capabilities
- Voice assistant integration improvements

---

**Last Updated**: December 2024
**Next Review**: After Phase 2 completion
