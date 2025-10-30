# Smart Polling Strategy Implementation

## Overview

The WiiM integration implements a sophisticated **smart polling strategy** that optimizes API call frequency based on data type, user activity, and device capabilities. This approach delivers responsive user experience while minimizing unnecessary network traffic and device load.

## Design Philosophy

### User Experience First

- **1-second polling** during active playback for real-time position updates
- **15-second polling** for group changes (users group via app/voice commands)
- **Activity-triggered updates** when users change tracks or sources
- **10-minute idle timeout** to prevent endless fast polling

### Resource Efficiency

- **80% reduction** in API calls during idle periods
- **Conditional fetching** based on actual need
- **Capability detection** to stop trying unsupported endpoints
- **Parallel execution** of independent API calls

### Graceful Degradation

- **Existing data reuse** when calls are skipped
- **Fallback strategies** for failed endpoints
- **Error handling** without breaking the entire update cycle

## Polling Frequency Matrix

| Data Type          | Base Frequency                 | Additional Triggers     | Rationale                  |
| ------------------ | ------------------------------ | ----------------------- | -------------------------- |
| **Player Status**  | 1s playing / 5s idle (no UPnP) | Adaptive based on state | Core UI responsiveness     |
|                    | 5s always (UPnP working) 📡    | UPnP provides real-time | UPnP optimization          |
| **Multiroom Info** | 15s                            | Track/source changes    | Role detection, grouping   |
| **Device Info**    | 60s                            | None                    | Health check only          |
| **Metadata**       | Never                          | Track changes only      | Many devices don't support |
| **EQ Status**      | 60s                            | None                    | Settings rarely change     |
| **EQ Presets**     | Once                           | Startup only            | Firmware-defined           |
| **Radio Presets**  | Once                           | Startup only            | User rarely modifies       |

## UPnP Eventing Optimization 📡

When UPnP eventing is working, the integration automatically reduces HTTP polling frequency:

### Why This Works

- **UPnP provides:** Play/pause/stop, position, volume, track changes (real-time via events)
- **HTTP still needed for:** EQ settings, audio output mode, grouping state, shuffle/repeat
- **Result:** HTTP polling becomes backup + non-UPnP data only

### Automatic Detection

The integration checks if UPnP is working:

- ✅ Subscriptions are healthy (`_push_healthy = True`)
- ✅ Events have been received (`_event_count > 0`)
- ✅ Automatically reduces polling to 5s (from 1s when playing)

### Graceful Fallback

If UPnP stops working (network issues, device firmware bugs):

- ❌ UPnP health check fails
- ⚡ Automatically increases polling back to 1s
- 📡 User experience remains smooth

## Performance Benefits

### Quantified Improvements

- **80% reduction** in API calls during idle periods
- **80% reduction** when playing with UPnP (1s → 5s)
- **3-5x faster** initial device setup (parallel calls)
- **10-minute timeout** prevents endless fast polling
- **Real-time updates** during active listening

### Before vs After

```
BEFORE (Fixed 5s polling):
- Player status: Every 5s (always)
- Device info: Every 5s (always)
- Multiroom: Every 5s (always)
- Metadata: Every 5s (often fails)
- EQ info: Every 5s (rarely changes)
Total: 5 API calls every 5s = 1 call/second

AFTER (Smart polling):
- Player status: 1s playing / 5s idle
- Device info: Every 60s
- Multiroom: Every 15s + on activity
- Metadata: Only on track change (if supported)
- EQ info: Every 60s
Idle total: ~0.2 calls/second (80% reduction)
Playing total: ~1.2 calls/second (real-time updates)
```

This smart polling strategy delivers the responsive user experience users expect while being respectful of device resources and network constraints.
