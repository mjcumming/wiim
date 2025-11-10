# Statistics Tracking Proposal

## Current State

We already track some metrics:

- `_last_response_time` - Last HTTP polling response time (ms)
- `_core_comm_failures` - HTTP polling failure count
- `_audio_output_error_count` - Audio output API error count
- `_command_failure_count` - Command failure count
- `_backoff.consecutive_failures` - Backoff failure tracking
- `_player_status_working`, `_device_info_working`, `_multiroom_working` - Boolean flags
- UPnP: `_event_count`, `_last_notify_ts`

## What Other Integrations Do

**Z-Wave JS** (most comprehensive):

- Exposes statistics as sensors:
  - Commands TX/RX (successful)
  - Commands dropped TX/RX
  - Timeout responses
  - RTT (round trip time)
  - RSSI (signal strength)
  - Last seen timestamp

**Most other integrations:**

- Just track `last_update_success` (built into DataUpdateCoordinator)
- Some track error counts internally
- Diagnostics show basic info

## What Would Be Useful for WiiM

### HTTP Polling Statistics

- **Success count** - Total successful HTTP polls
- **Failure count** - Total failed HTTP polls
- **Response time** - Average/min/max HTTP response time (ms)
- **Last success time** - Timestamp of last successful poll
- **Last failure time** - Timestamp of last failed poll
- **Current polling interval** - What interval is being used now

### UPnP Statistics

- **Event count** - Total UPnP events received
- **Events per minute** - Recent event arrival rate
- **Last event time** - Timestamp of last UPnP event
- **Subscription status** - Active/Not Active
- **Subscription age** - How long subscriptions have been active

### Command Statistics

- **Command success count** - Successful commands sent
- **Command failure count** - Failed commands
- **Last command time** - When last command was sent
- **Last command failure time** - When last command failed

## Implementation Options

### Option 1: Enhanced Diagnostics Only (Simplest)

- Add statistics to diagnostics output
- No new entities
- Easy to implement
- Users check diagnostics when troubleshooting

**Pros:**

- Simple, no UI clutter
- Follows current pattern
- Easy to maintain

**Cons:**

- Not visible in UI
- Users have to download diagnostics

### Option 2: Optional Statistics Sensors (Like Z-Wave JS)

- Add sensors for key metrics
- Disabled by default (entity_registry_enabled_default=False)
- Users can enable if they want

**Pros:**

- Visible in UI
- Can be used in automations/dashboards
- Follows Z-Wave JS pattern

**Cons:**

- More code to maintain
- More entities (even if disabled)
- Might be overkill

### Option 3: Hybrid Approach (Recommended)

- Enhanced diagnostics (always available)
- Optional statistics sensors for power users
- Sensors disabled by default

## Recommendation

**Start with Option 1 (Enhanced Diagnostics)**:

- Add HTTP polling statistics to diagnostics
- Add UPnP statistics to diagnostics
- Add command statistics to diagnostics
- Keep it simple, no new entities

**Consider Option 2 later** if users request it:

- Only add sensors if there's demand
- Follow Z-Wave JS pattern
- Disabled by default

## What to Track

### HTTP Polling

```python
http_polling_stats = {
    "total_polls": int,  # Total polls attempted
    "successful_polls": int,  # Successful polls
    "failed_polls": int,  # Failed polls
    "success_rate": float,  # Percentage (0-100)
    "avg_response_time_ms": float,  # Average response time
    "min_response_time_ms": float,  # Minimum response time
    "max_response_time_ms": float,  # Maximum response time
    "last_success_time": str | None,  # ISO timestamp
    "last_failure_time": str | None,  # ISO timestamp
    "current_interval": int,  # Current polling interval (seconds)
    "consecutive_failures": int,  # Current consecutive failures
}
```

### UPnP

```python
upnp_stats = {
    "total_events": int,  # Total events received
    "events_last_minute": int,  # Events in last 60 seconds
    "events_last_hour": int,  # Events in last hour
    "last_event_time": str | None,  # ISO timestamp
    "subscription_active": bool,  # Are subscriptions active?
    "subscription_age_seconds": int | None,  # How long subscriptions have been active
    "avt_subscription_expires": str | None,  # When AVTransport subscription expires
    "rcs_subscription_expires": str | None,  # When RenderingControl subscription expires
}
```

### Commands

```python
command_stats = {
    "total_commands": int,  # Total commands sent
    "successful_commands": int,  # Successful commands
    "failed_commands": int,  # Failed commands
    "success_rate": float,  # Percentage (0-100)
    "last_command_time": str | None,  # ISO timestamp
    "last_command_failure_time": str | None,  # ISO timestamp
    "recent_failures": int,  # Failures in last 30 seconds
}
```

## Implementation Notes

- Track counters in coordinator (reset on restart)
- Calculate rates on-demand (don't store rolling windows)
- Use time.time() for timestamps
- Include in diagnostics output
- Consider resetting counters on integration restart (or persist?)

## Conclusion

**Yes, stats tracking would be valuable**, especially for:

- Diagnosing slow updates (HTTP polling performance)
- Understanding UPnP event arrival (is it working?)
- Debugging command failures

**Start simple**: Enhanced diagnostics first, sensors later if needed.
