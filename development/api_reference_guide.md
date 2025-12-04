# API Reference

Complete API reference for the `pywiim` library.

## Table of Contents

- [WiiMClient](#wiimclient)
- [Player](#player)
- [Models](#models)
- [Exceptions](#exceptions)
- [Group Object](#group-object)
- [Usage Examples](#usage-examples)
- [Output Selection](#output-selection-hardware--bluetooth)

## WiiMClient

Low-level HTTP client for device communication. **Most users should use the `Player` class instead**, which provides state caching, convenient properties, and a higher-level API.

The client is primarily used internally by the Player class, but may be accessed for advanced use cases via `player.client`.

### Initialization

```python
from pywiim import WiiMClient

client = WiiMClient(
    host="192.168.1.100",
    port=80,                    # Optional, default: 80
    timeout=5.0,                # Optional, default: 5.0
    ssl_context=None,           # Optional, for advanced use
    session=None,               # Optional, shared aiohttp session
    capabilities=None,          # Optional, pre-detected capabilities
)
```

### Properties

- `host: str` - Device hostname or IP address
- `base_url: str | None` - Base URL used for last successful request
- `capabilities: dict[str, Any]` - Device capabilities dictionary

### Methods

#### Connection Management

```python
async def close() -> None:
    """Close the client and clean up resources."""
```

#### Device Information

```python
async def get_device_info() -> dict[str, Any]:
    """Get device information as dictionary."""

async def get_device_info_model() -> DeviceInfo:
    """Get device information as Pydantic model."""

async def get_firmware_version() -> str:
    """Get device firmware version."""

async def get_mac_address() -> str:
    """Get device MAC address."""
```

#### Player Status

```python
async def get_player_status() -> dict[str, Any]:
    """Get player status with automatic capability detection."""

async def get_player_status_model() -> PlayerStatus:
    """Get player status as Pydantic model."""
```

## Player

High-level player interface with state caching and convenient properties.

### Initialization

```python
from pywiim import Player, WiiMClient

client = WiiMClient("192.168.1.100")
player = Player(client)

# Refresh state cache
await player.refresh()
```

### Properties

#### Device Identity & Connection

```python
player.name               # str | None - Device name (e.g., "Living Room")
player.model              # str | None - Device model (e.g., "WiiM Pro Plus")
player.firmware           # str | None - Firmware version
player.mac_address        # str | None - MAC address
player.uuid               # str | None - Device UUID
player.host               # str - IP/hostname
player.port               # int - Port number
player.discovered_endpoint  # str | None - Full endpoint URL (e.g., "https://192.168.1.100:443")
player.input_list         # list[str] - Raw input list from device ([] if unavailable)
```

#### Available Sources

```python
player.available_sources  # list[str] - Returns [] if unavailable
```

Returns list of user-selectable physical inputs plus the current source (when active):

1. **Always included**: Physical/hardware sources (Bluetooth, USB, Line In, Optical, Coax, AUX, HDMI) - user-selectable
2. **Conditionally included**: Current source (when active) - includes streaming services (AirPlay, Spotify, etc.) and multi-room follower sources. NOT user-selectable but included for correct UI state display
3. **NOT included**: Inactive streaming services - can't be manually selected and aren't currently playing
4. **Always excluded**: WiFi (it's the network connection, not a selectable source)

**Smart Detection Logic:**
- If `InputList` is provided: Filters device's `InputList` to remove unconfigured services
- If `plm_support` is available: Parses bitmask to detect physical inputs
- Fallback: Uses model-based detection for common inputs

**Why this matters**: Devices report all possible sources in their `InputList`, but streaming services aren't actually usable until you've logged in. This property returns only the sources that will actually work.

**Example:**
```python
await player.refresh()
sources = player.available_sources

# When idle (nothing playing):
# Returns: ["bluetooth", "line_in", "optical"]

# When playing from AirPlay:
# Returns: ["bluetooth", "line_in", "optical", "AirPlay"]

# When playing from Spotify:
# Returns: ["bluetooth", "line_in", "optical", "Spotify"]

# When following another device in multi-room:
# Returns: ["bluetooth", "line_in", "optical", "Master Bedroom"]

# Note: Source names preserve their original casing for proper UI display
```

#### EQ Presets

```python
player.eq_preset  # str | None
# Returns current EQ preset name, normalized to Title Case to match get_eq_presets() format.
# Example: "Flat", "Acoustic", "Rock" (not "flat", "acoustic", "rock")
```

Current EQ preset name from cached status.

#### Multiroom / Group Role

```python
player.role              # str - "solo", "master", or "slave"
player.is_solo           # bool - True if not in a group
player.is_master         # bool - True if group master
player.is_slave          # bool - True if slave in a group
player.group             # Group | None - Group object (for multi-player scenarios)
player.group_master_name # str | None - Safe accessor for group master's name
```

**Role Detection** - SINGLE source of truth:
- Role comes from device API state via `detect_role()` function
- Updated during `refresh()` from actual device multiroom status
- Cached in `player._detected_role` field
- **Independent of Group objects** - Group objects are for linking Player objects in Home Assistant, role reflects actual device state

**Example:**
```python
await player.refresh()
if player.is_master:
    print(f"Master with {len(player.group.slaves)} linked Player objects")
    # Note: In standalone monitoring, group.slaves may be empty
    # but is_master will still be True based on device API state
```

**Important:** 
- `player.role` reads device state, NOT Group object relationships
- Group objects (`player.group`) are optional and used by coordinators (like HA) to link Player objects
- A master device shows `is_master=True` even if no slave Player objects exist
- Role is always accurate regardless of whether Player objects are linked

#### Media Position and Duration

The Player provides real-time position tracking using a **hybrid approach** that combines HTTP polling, UPnP events, and position estimation for smooth updates:

```python
player.media_position  # int | None - Current position in seconds
player.media_duration  # int | None - Track duration in seconds
player.media_position_updated_at  # float | None - Unix timestamp of last update
```

**How Position Updates Work:**

1. **HTTP Polling** - `await player.refresh()` fetches current state (typically every 5-10s)
2. **UPnP Events** - Real-time notifications when tracks change or playback state changes (requires UPnP setup)
3. **Position Estimation** - Automatically ticks every second while playing for smooth progress bars

The `StateSynchronizer` intelligently merges these three sources, providing accurate position without constant network requests.

**Example - Simple Position Monitoring:**

```python
from pywiim import Player, WiiMClient

player = Player(WiiMClient("192.168.1.100"))
await player.refresh()

# Get current position and duration
position = player.media_position  # e.g., 120 (2:00)
duration = player.media_duration  # e.g., 240 (4:00)

if position and duration:
    progress = (position / duration) * 100
    print(f"{position}/{duration}s ({progress:.1f}%)")
```

**Example - Real-time Position Updates:**

```python
def on_state_changed():
    """Called every second while playing + on all state changes."""
    pos = player.media_position
    dur = player.media_duration
    if pos and dur:
        print(f"Position: {pos}/{dur}s")

player = Player(client, on_state_changed=on_state_changed)
await player.refresh()
await player.play()  # Callback fires automatically every second while playing
```

**Example - With UPnP for Real-time Events:**

```python
from pywiim.upnp import UpnpClient, UpnpEventer

# Setup UPnP for immediate track change notifications
upnp_client = UpnpClient("192.168.1.100")
player = Player(client, upnp_client=upnp_client)

eventer = UpnpEventer(
    upnp_client=upnp_client,
    on_event=lambda changes: player.update_from_upnp(changes)
)
await eventer.async_subscribe()

# Position now updates via:
# - UPnP events (immediate track changes)
# - Position estimation (smooth 1-second ticks)
# - HTTP polling (fallback + verification)
```

**Position Estimation:**
- Runs automatically in background while playing
- Updates every second for smooth UI progress
- Resets on track changes and seeks
- Clamps to duration to prevent overflow
- No manual intervention needed

#### Position & Duration Edge Cases

The library automatically handles several edge cases and device quirks related to position and duration tracking. Understanding these helps when building integrations:

##### 1. Time Unit Inconsistency (Issue [#75](https://github.com/mjcumming/wiim/issues/75))

**Problem**: The LinkPlay/WiiM API returns time values in different units depending on the source:
- Most sources (USB, Line In, etc.): **milliseconds** (1,000 ms = 1 second)
- Streaming services (Spotify, Tidal, Qobuz, etc.): **microseconds** (1,000,000 μs = 1 second)

**Solution**: The library uses intelligent auto-detection with a 10-hour threshold:

```python
# Values < 36,000,000 = treated as milliseconds
# Values ≥ 36,000,000 = treated as microseconds

# This works because most tracks are < 10 hours
# If a value would be > 10 hours in ms, it's likely μs instead
```

**Impact**: Position and duration values are always returned in **seconds** regardless of source. No manual conversion needed.

##### 2. Live Streams & Zero Duration

**Problem**: Web radio, internet radio, and live streams report `duration=0` because there's no defined end time.

**Solution**: The library converts zero duration to `None`:

```python
if player.media_duration is None:
    # Live stream, web radio, or duration unavailable
    # Don't show progress bar
    print("Live stream - no duration available")
else:
    # Normal track with known duration
    progress = (player.media_position / player.media_duration) * 100
    print(f"Progress: {progress:.1f}%")
```

**Sources affected**: `wifi`, `webradio`, `iheartradio`, `pandora`, `tunein`

##### 3. Position Exceeds Duration (Firmware Bugs)

**Problem**: Device firmware sometimes reports impossible states where position > duration.

**Solution**: The library has intelligent detection and correction:

```python
# Scenario A: Duration seems too short (< 2 minutes) but position is reasonable
# → Likely firmware bug in duration calculation
# → Hide duration, keep position
if position > 30 and duration < 120:
    media_duration = None  # Hide bad duration
    
# Scenario B: Position clearly exceeds reasonable duration
# → Likely firmware bug in position reporting
# → Reset position to 0
else:
    media_position = 0  # Reset bad position
```

**Additional protection**: Position is clamped to duration at the property level:

```python
# Position can never exceed duration
if player.media_position and player.media_duration:
    assert player.media_position <= player.media_duration  # Always True
```

##### 4. AirPlay Duration Interpretation

**Problem**: Early versions incorrectly interpreted the `totlen` field as "remaining time" instead of "total duration" for AirPlay sources.

**Solution**: Fixed in v1.0.75+. The `totlen` field is now correctly interpreted as total track duration for all sources, including AirPlay.

```python
# ✅ Correct (current): totlen = total duration
# AirPlay playing 4:00 track at 2:00 position:
#   position = 120 seconds (elapsed)
#   duration = 240 seconds (total)
#   progress = 50%
```

##### 5. Negative Position Values

**Problem**: Device API sometimes returns negative position values (invalid).

**Solution**: Negative values are filtered out:

```python
if player.media_position is not None:
    # Always ≥ 0, never negative
    # Negative values from API return None instead
    pass
```

##### 6. UPnP Position Updates

**Important limitation**: UPnP events provide position/duration **only when tracks start**, not continuously during playback.

```python
# ✅ UPnP sends position/duration in these scenarios:
# - Track changes (new song starts)
# - Playback starts from idle/stopped
# - Manual seek completes

# ❌ UPnP does NOT send position during continuous playback
# Position is estimated locally using a timer
# HTTP polling every 5 seconds corrects drift
```

This is why the library uses **hybrid position tracking** (UPnP events + local estimation + HTTP polling).

##### 7. Source-Specific Behavior Summary

Different sources have different position/duration characteristics:

| Source Type | Position | Duration | Time Unit | Notes |
|-------------|----------|----------|-----------|-------|
| **USB/Local Files** | ✅ Always | ✅ Always | milliseconds | Most reliable |
| **Spotify/Tidal/Qobuz** | ✅ Always | ✅ Always | **microseconds** | Auto-detected |
| **AirPlay** | ✅ Always | ✅ Always | milliseconds | totlen = total duration |
| **Bluetooth** | ✅ Usually | ✅ Usually | milliseconds | Depends on source device |
| **DLNA** | ✅ Usually | ✅ Usually | milliseconds | Depends on server |
| **Web Radio/WiFi** | ❌ Often N/A | ❌ `None` | - | Live streams |
| **Line In/Optical** | ❌ N/A | ❌ N/A | - | Real-time input |

##### 8. Best Practices for Integrations

When building UI or integrations, follow these patterns:

```python
# ✅ GOOD: Always check if duration exists before calculating progress
if player.media_position and player.media_duration:
    progress = (player.media_position / player.media_duration) * 100
    # Show progress bar
else:
    # Don't show progress bar (live stream or no playback)
    pass

# ✅ GOOD: Handle None values gracefully
position = player.media_position or 0
duration = player.media_duration or 0

# ✅ GOOD: Use position_updated_at to detect stale data
if player.media_position_updated_at:
    age = time.time() - player.media_position_updated_at
    if age > 30:
        # Position data is stale
        pass

# ❌ BAD: Assume position/duration always exist
progress = (player.media_position / player.media_duration) * 100  # May raise TypeError/ZeroDivisionError
```

**Summary**: The library handles all position/duration edge cases automatically. Your integration code should:
1. Always check for `None` before using position/duration
2. Don't show progress bars when duration is `None` (live streams)
3. Trust the returned values - they're already validated and clamped
4. Use the automatic position callbacks for smooth UI updates

#### Other Properties

```python
player.volume_level  # float | None (0.0-1.0)
player.is_muted  # bool | None
player.play_state  # str | None ("play", "pause", "idle", "load")
player.source  # str | None (normalized to Title Case, e.g., "AirPlay", "Spotify", "Line In")
player.media_title  # str | None (falls back to URL filename if no title)
player.media_artist  # str | None
player.media_album  # str | None
player.media_content_id  # str | None (URL if playing from play_url())
player.media_image_url  # str | None (cover art URL)
player.media_sample_rate  # int | None (Hz)
player.media_bit_depth  # int | None (bits)
player.media_bit_rate  # int | None (kbps)
player.media_codec  # str | None (e.g., "flac", "mp3", "aac")
player.upnp_health_status  # dict[str, Any] | None (health statistics)
player.upnp_is_healthy  # bool | None (True/False/None)
player.upnp_miss_rate  # float | None (0.0-1.0, miss rate)
player.shuffle  # bool | None
player.repeat  # str | None ("one", "all", "off")
```

#### UPnP Health Properties

UPnP health tracking monitors whether UPnP events are reliably catching state changes. Only available when UPnP client is provided to Player.

```python
# Health status dictionary (None if UPnP not enabled)
health = player.upnp_health_status
# Returns: {
#     "is_healthy": True,
#     "miss_rate": 0.05,  # 5% miss rate
#     "detected_changes": 20,
#     "missed_changes": 1,
#     "has_enough_samples": True
# }

# Simple health check
is_healthy = player.upnp_is_healthy  # True/False/None

# Miss rate (0.0 = perfect, 1.0 = all missed)
miss_rate = player.upnp_miss_rate  # 0.05 = 5% miss rate
```

**Note**: UPnP health tracking requires:
- UPnP client passed to `Player(..., upnp_client=upnp_client)`
- UPnP events being subscribed (via `UpnpEventer`)
- Player refresh being called regularly

#### Cover Art Methods

```python
# Fetch cover art image (with caching)
result = await player.fetch_cover_art(url=None)  # Returns (bytes, content_type) | None
# If url is None, uses current track's cover art URL
# If no URL available, fetches WiiM logo as fallback

# Get just the image bytes (convenience method)
image_bytes = await player.get_cover_art_bytes(url=None)  # Returns bytes | None
```

**Cover Art Features:**
- ✅ Automatic caching (in-memory, 1 hour TTL, max 10 images per player)
- ✅ Uses client's HTTP session for fetching
- ✅ Handles expired URLs gracefully
- ✅ Returns both image bytes and content type
- ✅ Cache cleanup on fetch (removes expired entries)
- ✅ Automatic WiiM logo fallback when no cover art available

### Properties

#### Connection Info

```python
player.host  # str - Device hostname or IP address
player.port  # int - Device port number
player.timeout  # float - Network timeout in seconds
```

#### Transport Support 

```python
# Use these to determine if next/prev buttons should be shown
player.supports_next_track      # bool - True if next track is supported
player.supports_previous_track  # bool - True if previous track is supported

# IMPORTANT: Use these properties, NOT queue_count!
# Spotify/streaming services have queue_count=0 but next/prev work perfectly.
```

### Methods

```python
# State management
await player.refresh()  # Fetch latest state from device

# Playback control
await player.play()
await player.pause()
await player.stop()
await player.next_track()
await player.previous_track()
await player.seek(position: int)  # Seek to position in seconds
await player.set_volume(volume: float)  # 0.0-1.0
await player.set_mute(muted: bool)
await player.set_source(source: str)
await player.clear_playlist()
await player.set_shuffle(enabled: bool)  # Preserves repeat state

# Media playback
await player.play_url(url: str, enqueue: str = "replace")  # Play URL directly
await player.play_playlist(playlist_url: str)  # Play M3U playlist
await player.play_notification(url: str)  # Play notification (auto volume handling)

# EQ control
await player.set_eq_preset(preset: str)
await player.get_eq()  # Returns dict[str, Any]
await player.get_eq_presets()  # Returns list[str]
await player.get_eq_status()  # Returns bool

# Audio output control
# Official WiiM API: 1=SPDIF (Optical), 2=AUX (Line Out), 3=COAX
await player.set_audio_output_mode(mode: str | int)  # "Line Out", "Optical Out", etc.

# LED control
await player.set_led(enabled: bool)
await player.set_led_brightness(brightness: int)  # 0-100

# Audio settings
await player.set_channel_balance(balance: float)  # -1.0 to 1.0

# Status and metadata fetchers
await player.get_multiroom_status()  # Returns dict[str, Any]
await player.get_audio_output_status()  # Returns dict[str, Any] | None
await player.get_meta_info()  # Returns dict[str, Any]

# Bluetooth workflow
await player.get_bluetooth_history()  # Returns list[dict[str, Any]]
await player.connect_bluetooth_device(mac_address: str)
await player.disconnect_bluetooth_device()
await player.get_bluetooth_pair_status()  # Returns dict[str, Any]
await player.scan_for_bluetooth_devices(duration: int = 3)  # Returns list[dict[str, Any]]

# Output selection (hardware modes + paired BT devices)
outputs = player.available_outputs  # Returns list[str]
bt_devices = player.bluetooth_output_devices  # Returns list[dict[str, str]]
await player.audio.select_output("Optical Out")  # Hardware mode
await player.audio.select_output("BT: Sony Speaker")  # Specific paired Bluetooth device

# Device management
await player.reboot()
await player.sync_time(ts: int | None = None)
```

### When to Use `refresh()`

**Command methods do NOT call `refresh()` internally.** State updates happen via UPnP events and coordinator polling in integrations.

#### ✅ Use `refresh()` for:

```python
# 1. One-off scripts without polling
player = Player(WiiMClient("192.168.1.100"))
await player.play()
await player.refresh()  # Get fresh state
print(f"Playing: {player.media_title}")

# 2. Initial state fetch
await player.refresh()  # Populate state cache
print(f"Volume: {player.volume_level}")

# 3. Explicit verification in tests
await player.set_volume(0.5)
await player.refresh()
assert player.volume_level == 0.5
```

#### ❌ Don't use `refresh()` after commands in integrations:

```python
# Integration with coordinator/polling
await player.play()
# ❌ await player.refresh()  # Unnecessary!
# State updates via:
# - UPnP events (immediate)
# - Coordinator polling (5-10 seconds)
```

**See also**: `docs/design/OPERATION_PATTERNS.md` for detailed patterns

### Seeking and Position Control

The `seek()` method allows you to jump to a specific position in the current track.

#### Basic Seek Usage

```python
# Seek to specific position (in seconds)
await player.seek(120)  # Jump to 2:00

# Seek to beginning
await player.seek(0)

# Seek to 50% through track
if player.media_duration:
    midpoint = player.media_duration // 2
    await player.seek(midpoint)
```

#### Advanced Seek Examples

```python
# Skip forward 30 seconds
if player.media_position and player.media_duration:
    new_pos = min(player.media_position + 30, player.media_duration)
    await player.seek(new_pos)

# Skip backward 10 seconds
if player.media_position:
    new_pos = max(player.media_position - 10, 0)
    await player.seek(new_pos)

# Seek to percentage of track
def seek_to_percent(player: Player, percent: float):
    """Seek to percentage (0.0-1.0) of track."""
    if player.media_duration:
        position = int(player.media_duration * percent)
        await player.seek(position)

# Seek to 75%
await seek_to_percent(player, 0.75)
```

#### How Seek Works

When you call `seek()`:
1. Command is sent to device via HTTP API
2. Cached state is updated immediately (optimistic update)
3. `on_state_changed` callback fires with new position
4. Position is confirmed by next UPnP event or HTTP poll
5. Position estimation resumes from new position

```python
def on_position_update():
    """Called immediately after seek, then every second while playing."""
    print(f"Position: {player.media_position}s")

player = Player(client, on_state_changed=on_position_update)

# Seek triggers immediate callback with optimistic update
await player.seek(60)  # Callback fires right away
# Then confirmed by UPnP event or next refresh()
```

#### Position Tracking for UI

For progress bars and time displays that update smoothly:

```python
import asyncio
from pywiim import Player, WiiMClient

async def monitor_playback():
    """Monitor playback with smooth position updates."""
    
    def on_state_changed():
        # Called every second while playing
        pos = player.media_position
        dur = player.media_duration
        
        if pos and dur:
            progress = (pos / dur) * 100
            mins, secs = divmod(pos, 60)
            dur_mins, dur_secs = divmod(dur, 60)
            print(f"{mins:02d}:{secs:02d} / {dur_mins:02d}:{dur_secs:02d} ({progress:.1f}%)")
    
    player = Player(WiiMClient("192.168.1.100"), on_state_changed=on_state_changed)
    await player.refresh()
    await player.play()
    
    # Position updates automatically every second via callback
    # No need to poll in a loop!
    await asyncio.sleep(60)  # Just keep the program running

asyncio.run(monitor_playback())
```

**Key Points:**
- No need to call `refresh()` after `seek()` - state updates automatically
- Position estimation provides smooth 1-second updates while playing
- Callbacks fire on seeks, track changes, and every second during playback
- Hybrid approach (HTTP + UPnP + estimation) ensures reliability

### Notification Playback

The `play_notification()` method uses the device's built-in `playPromptUrl` command for playing notification sounds (TTS, doorbell, alerts, etc.):

```python
await player.play_notification("https://example.com/doorbell.mp3")
```

#### How It Works

The device firmware handles everything automatically:
1. **Lowers current playback volume** (if something is playing)
2. **Plays the notification audio**
3. **Restores original volume** after completion

No timing logic, state saving, or manual restoration is needed - the device handles it internally.

#### Limitations

- **Only works in NETWORK or USB playback mode** - If the device is in a different mode (e.g., Line In, Optical), the notification may not play
- **Requires firmware 4.6.415145+** - Older firmware versions may not support this command

#### Use Cases

- TTS announcements (Home Assistant `tts.speak`)
- Doorbell sounds
- Alert notifications
- Timer/alarm sounds

This is the recommended approach for integrations that need to play announcements without interrupting the current audio source.

## Models

### DeviceInfo

Device information model.

```python
class DeviceInfo:
    uuid: str
    name: str | None
    model: str | None
    firmware: str | None
    mac: str | None
    ip: str | None
    preset_key: str | None
    input_list: list[str] | None  # Available input sources from InputList field
    plm_support: str | int | None  # Bitmask for physical input sources (smart detection)
```

**Note on `input_list` and `plm_support`:**

- `input_list`: Direct list of available sources from device's `InputList` field in `getStatusEx`. May be `None` if device doesn't provide it.
- `plm_support`: Bitmask indicating which physical inputs are available (from `plm_support` field in `getStatusEx`). Used for smart detection when `input_list` is not available. Bit positions:
  - bit1: LineIn (Aux)
  - bit2: Bluetooth
  - bit3: USB
  - bit4: Optical
  - bit6: Coaxial
  - bit8: LineIn 2
  - bit15: USBDAC (not a selectable source)

### PlayerStatus

Player status model.

```python
class PlayerStatus:
    play_state: str | None
    volume: float | None
    mute: bool | None
    source: str | None
    position: int | None
    duration: int | None
    title: str | None
    artist: str | None
    album: str | None
    image_url: str | None
```

## Exceptions

### WiiMError

Base exception for all WiiM errors.

```python
class WiiMError(Exception):
    """Base exception for WiiM errors."""
```

### WiiMRequestError

Raised when HTTP request fails.

```python
class WiiMRequestError(WiiMError):
    """Raised when HTTP request fails."""
    endpoint: str | None
    attempts: int
    last_error: Exception | None
    device_info: dict[str, str] | None
```

### WiiMResponseError

Raised when device returns error response.

```python
class WiiMResponseError(WiiMError):
    """Raised when device returns error response."""
    endpoint: str | None
    last_error: Exception | None
    device_info: dict[str, str] | None
```

### WiiMTimeoutError

Raised when request times out.

```python
class WiiMTimeoutError(WiiMRequestError):
    """Raised when request times out."""
```

### WiiMConnectionError

Raised when connection fails.

```python
class WiiMConnectionError(WiiMRequestError):
    """Raised when connection fails."""
```

### WiiMInvalidDataError

Raised when response data is invalid.

```python
class WiiMInvalidDataError(WiiMError):
    """Raised when response data is invalid."""
```

## Group Object

The `Group` object is a utility for managing multiroom groups. It's accessed via the master player and provides group-level operations.

### Accessing the Group

```python
from pywiim import Player

# Master player automatically has a group object when it's a master
if player.is_master and player.group:
    group = player.group

# Slave players reference the same group object
if slave_player.is_slave and slave_player.group:
    # This is the same Group object as the master's
    group = slave_player.group
    master = group.master  # Access the master player
```

### Group Properties

All Group properties compute dynamically (no caching) by reading from linked Player objects:

```python
# Volume and mute (computed properties)
group.volume_level  # float | None - MAX of all devices
group.is_muted      # bool | None - True only if ALL devices muted

# Playback state (from master)
group.play_state    # str | None - Master's play state

# Group members
group.master        # Player - The master player
group.slaves        # list[Player] - Linked slave players
group.all_players   # list[Player] - Master + all slaves
group.size          # int - Number of players (master + slaves)
```

**Important:**
- Properties read from Player objects on access (always current)
- No polling or refresh needed - reads cached Player state
- Virtual entities can use these for aggregated group state

### Group Operations

#### Playback Control

All playback commands delegate to the master player:

```python
# These all call master.play(), master.pause(), etc.
await group.play()
await group.pause()
await group.stop()
await group.next_track()
await group.previous_track()
```

**Automatic Routing:**
When a slave player's playback methods are called, they automatically route through the group:

```python
# Works the same whether called on master or slave
await slave_player.pause()
# → pywiim detects is_slave
# → routes to slave.group.pause()
# → calls master.pause()
# → master's callback fires

# Slave without group object raises WiiMError
```

#### Volume and Mute

Group-wide volume and mute operations adjust all devices:

```python
# Set volume on all devices (proportional adjustment)
await group.set_volume_all(0.5)
# If group volume is 50%, each device changes by same amount
# Master at 50% → 50%, Slave at 30% → 30%, etc.

# Mute/unmute all devices
await group.mute_all(True)   # Mute all
await group.mute_all(False)  # Unmute all
```

**Individual Volume Control:**
Players maintain independent volume control:

```python
# Adjust only the slave device
await slave_player.set_volume(0.5)
# → Command goes to slave device only
# → Slave's callback fires (slave entity updates)
# → Master's callback fires (virtual entity updates)
# → group.volume_level recomputes (MAX of all)
```

**Cross-Notification:**
When a slave's volume/mute changes, both slave and master callbacks fire:
- Slave callback → slave entity updates
- Master callback → virtual entity updates (reads group.volume_level)

#### Group Management

```python
# Create group (makes player a master)
group = await player.create_group()

# Join group (automatically handles all preconditions)
# - Works regardless of either player's current role
# - Disbands/leaves groups as needed automatically
await slave_player.join_group(master_player)

# Leave group (works for any role)
# - Solo: No-op (idempotent)
# - Master: Disbands entire group
# - Slave: Leaves group
# NO NEED to check player role before calling!
await player.leave_group()

# Disband group (explicit disband via Group object)
await group.disband()
```

### Example: Virtual Group Entity

```python
class VirtualGroupEntity:
    """Virtual entity representing a multiroom group."""
    
    def __init__(self, master_player: Player):
        self.master = master_player
    
    @property
    def group(self):
        return self.master.group
    
    @property
    def volume_level(self) -> float | None:
        """Group volume = MAX of all devices."""
        return self.group.volume_level if self.group else None
    
    @property
    def is_muted(self) -> bool | None:
        """Group mute = ALL devices muted."""
        return self.group.is_muted if self.group else None
    
    async def async_set_volume_level(self, volume: float):
        """Set volume on all group members."""
        if self.group:
            await self.group.set_volume_all(volume)
    
    async def async_media_pause(self):
        """Pause playback (routes to master)."""
        if self.group:
            await self.group.pause()
```

**Event Handling:**
- Virtual entity listens to master player's coordinator
- When any group member's volume changes, master's callback fires
- Virtual entity reads `group.volume_level` (computed property)
- No polling lag, immediate updates

## Usage Examples

### Basic Usage

```python
import asyncio
from pywiim import Player, WiiMClient

async def main():
    player = Player(WiiMClient("192.168.1.100"))
    
    # Refresh state cache
    await player.refresh()
    
    # Access cached properties
    print(f"Device: {player.device_name}")
    print(f"Playing: {player.play_state}")
    print(f"Volume: {player.volume_level}")
    
    # Control playback
    await player.set_volume(0.5)
    await player.play()
    
    await player.client.close()

asyncio.run(main())
```

### Error Handling

```python
from pywiim import Player, WiiMClient, WiiMError, WiiMRequestError

async def main():
    player = Player(WiiMClient("192.168.1.100"))
    
    try:
        await player.play()
    except WiiMRequestError as e:
        print(f"Request failed: {e}")
        print(f"Endpoint: {e.endpoint}")
        print(f"Attempts: {e.attempts}")
    except WiiMError as e:
        print(f"WiiM error: {e}")
    finally:
        await player.client.close()
```

### Capability Detection

```python
from pywiim import Player, WiiMClient

async def main():
    player = Player(WiiMClient("192.168.1.100"))
    await player.refresh()
    
    # Check capabilities via player properties
    if player.supports_sleep_timer:
        print("Device supports sleep timer")
    
    if player.shuffle_supported:
        print("Shuffle is supported for current source")
    
    await player.client.close()
```

## Output Selection (Hardware + Bluetooth)

WiiM devices support multiple audio output modes, and pywiim provides unified output selection that includes both hardware modes and already paired Bluetooth devices.

### Available Outputs

Get all available outputs (hardware modes + paired BT devices):

```python
# List all outputs
outputs = player.available_outputs
# Example (when BT devices are paired): ["Line Out", "Optical Out", "Coax Out", "BT: Sony Speaker", "BT: JBL Headphones"]
# Note: Generic "Bluetooth Out" is removed when specific BT devices are available

# Just get hardware modes
hardware_modes = player.available_output_modes
# Example: ["Line Out", "Optical Out", "Coax Out", "Bluetooth Out"]

# Just get paired Bluetooth output devices
bt_devices = player.bluetooth_output_devices
# Example: [
#     {"name": "Sony Speaker", "mac": "AA:BB:CC:DD:EE:FF", "connected": True},
#     {"name": "JBL Headphones", "mac": "11:22:33:44:55:66", "connected": False}
# ]
```

### Select Output

Use `select_output()` to switch to any output (hardware mode or specific BT device):

```python
# Select hardware output mode
await player.audio.select_output("Optical Out")
await player.audio.select_output("Line Out")

# Select specific Bluetooth device (auto-switches to BT mode and connects)
await player.audio.select_output("BT: Sony Speaker")
await player.audio.select_output("BT: JBL Headphones")

# Check current output
current_mode = player.audio_output_mode  # e.g., "Optical Out"
is_bt_active = player.is_bluetooth_output_active  # True if BT output mode is active
```

### Complete Example

```python
from pywiim import Player, WiiMClient

async def demo_output_selection():
    player = Player(WiiMClient("192.168.1.100"))
    await player.refresh()
    
    # Show all available outputs
    print("Available outputs:")
    for output in player.available_outputs:
        print(f"  - {output}")
    
    # Select Optical output
    await player.audio.select_output("Optical Out")
    print(f"Switched to: {player.audio_output_mode}")
    
    # Show paired Bluetooth devices
    print("\nPaired Bluetooth output devices:")
    for device in player.bluetooth_output_devices:
        status = "🔗 Connected" if device["connected"] else "⊗ Paired"
        print(f"  {status} {device['name']} ({device['mac']})")
    
    # Select specific Bluetooth device
    if player.bluetooth_output_devices:
        first_device = player.bluetooth_output_devices[0]
        await player.audio.select_output(f"BT: {first_device['name']}")
        print(f"Connected to: {first_device['name']}")
```

### Home Assistant Integration

For Home Assistant `select` entity:

```python
class WiiMOutputSelectEntity(SelectEntity):
    """Select entity for output selection."""
    
    @property
    def options(self) -> list[str]:
        """Return available output options.
        
        Available as a property on player: player.available_outputs
        Returns a list of output names (hardware modes + paired BT devices).
        """
        return self.coordinator.data.available_outputs
    
    @property
    def current_option(self) -> str | None:
        """Return current output.
        
        Returns the currently selected output mode, which must match one of the
        options in the available_outputs list. Returns None if output status
        is not available or doesn't match any option.
        """
        player = self.coordinator.data
        
        # Get available options to ensure we return a valid value
        available = player.available_outputs
        if not available:
            return None
        
        # Check if BT output is active and which device is connected
        if player.is_bluetooth_output_active:
            # Find the specific connected BT device from history
            # Note: We only show specific BT devices, not generic "Bluetooth Out"
            for device in player.bluetooth_output_devices:
                if device["connected"]:
                    bt_option = f"BT: {device['name']}"
                    # Ensure this option exists in available_outputs
                    if bt_option in available:
                        return bt_option
        
        # Get current hardware output mode
        current_mode = player.audio_output_mode
        if current_mode and current_mode in available:
            return current_mode
        
        # If current_mode doesn't match, try to find a matching option
        # (handles case where device returns slightly different format)
        if current_mode:
            for option in available:
                if option.lower() == current_mode.lower():
                    return option
        
        # If still no match, return None (will show as "Unknown" in HA)
        return None
    
    async def async_select_option(self, option: str) -> None:
        """Change the selected output."""
        await self.coordinator.data.audio.select_output(option)
        # State updates automatically via callback - no manual refresh needed
```

