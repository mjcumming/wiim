# Changelog

All notable changes to the WiiM Audio integration will be documented in this file.

## [0.1.7] - 2024-12-27

### Improved

- **Optimistic State Handling**: Enhanced media player responsiveness with immediate UI feedback
  - Playback state changes (play/pause/stop) now show instantly in the UI without waiting for device confirmation
  - Volume and mute changes provide immediate visual feedback while the device processes the command
  - Source switching shows the new source immediately for better user experience
  - Shuffle and repeat mode changes reflect instantly in the UI
  - Smart timeout handling prevents optimistic state from persisting if device doesn't respond (3s for playback, 10s for other states)

### Fixed

- Fixed potential UI flickering during state transitions by properly managing optimistic state lifecycle
- Improved state synchronization between UI and device by only clearing optimistic state when device confirms the change
- Enhanced volume slider behavior with proper debouncing to prevent command flooding
