# WiiM Home Assistant Integration – Master Guide (v0.2 consolidated)

_Integrates and harmonizes "WiiM Custom Home Assistant Integration — End‑to‑End Guide + Scaffold for Cursor AI" and "WiiM – Home Assistant Custom Integration (Design v0.2)" to serve as the single source of truth for the project team and any AI coding agents involved._

---

## 1 · Project Charter & Vision

| Item                  | Detail                                                                                                                                                            |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Objective**         | Ship a **dependency‑free HACS custom component** that exposes every WiiM / LinkPlay speaker on the local network as a `media_player` entity in Home Assistant.    |
| **Target HA Version** |  ≥ 2024.12.0 (Python 3.11 baseline)                                                                                                                               |
| **Success Metrics**   | • Entity auto‑discovers and appears in UI• Command latency < 500 ms• Unit‑test coverage > 85 %• ≤ 600 source LOC (excluding tests/docs)• MVP features R1–R6 green |
| **Distribution**      | HACS custom repo `hawiim`, semantic version tags & CHANGELOG                                                                                                      |

### 1.1 MVP Feature Set (v0.1)

| ID     | Requirement                                                         |
| ------ | ------------------------------------------------------------------- |
| **R1** | Core transport – play, pause, stop, next/prev, seek                 |
| **R2** | Volume – set absolute %, configurable step (default 5 %)            |
| **R3** | Preset keys – fire `MCUKeyShortClick:{n}` via `play_preset` service |
| **R4** | Grouping – join / un‑join any LinkPlay master (multi‑room)          |
| **R5** | Polling – user‑set interval (≥ 1 s; default 5 s)                    |
| **R6** | Discovery – Zeroconf `_linkplay._tcp` + manual entry                |

_Stretch Goals (v0.2+):_ snapshot/restore, media browser, fixed‑volume detection, UPnP enrichment, EQ presets, Bluetooth source select, options‑flow extras, eventual core PR.

---

## 2 · High‑Level Architecture & Directory Layout

```text
custom_components/wiim/
├── __init__.py          # setup_entry / unload / reload
├── manifest.json        # no external "requirements"
├── const.py             # literals & defaults (see §3)
├── api.py               # ≤200 LOC async HTTP client (bundles cert)
├── coordinator.py       # DataUpdateCoordinator wrapper
├── media_player.py      # MediaPlayerEntity subclass & media browser
├── snapshot.py          # helper for snapshot/restore (stretch)
├── config_flow.py       # Zeroconf + manual + options UI
├── strings.json         # UI strings for ConfigFlow/OptionsFlow
├── services.yaml        # schemas: play_preset, toggle_power
└── tests/               # pytest‑asyncio unit tests & fixtures
```

### 2.1 Data Flow

1. **Discovery** – `config_flow` detects `_linkplay._tcp` mDNS records whose TXT field `model` starts with `WiiM`.
2. **Client** – `api.WiiMClient` issues HTTPS requests (self‑signed cert pinned in‑file) and falls back to Telnet where required.
3. **Coordinator** – polls `/httpapi.asp?command=getStatusEx` every `poll_interval` seconds.
4. **Entity** – reflects state, exposes HA media‑player services; async methods call client, then refresh coordinator.

---

## 3 · Constants & Supported Features (const.py excerpt)

```python
DOMAIN = "wiim"

# Config keys
CONF_HOST          = "host"
CONF_POLL_INTERVAL = "poll_interval"
CONF_VOLUME_STEP   = "volume_step"

# Defaults
DEFAULT_PORT          = 443   # HTTPS
DEFAULT_TIMEOUT       = 10    # seconds
DEFAULT_POLL_INTERVAL = 5     # seconds
DEFAULT_VOLUME_STEP   = 0.05  # 5 %

# Services / Attributes
SERVICE_PLAY_PRESET  = "play_preset"
SERVICE_TOGGLE_POWER = "toggle_power"
ATTR_PRESET          = "preset"
ATTR_GROUP_MEMBERS   = "group_members"
ATTR_FIRMWARE        = "firmware"
ATTR_FIXED_VOLUME    = "fixed_volume"
```

_Supported HA features: PLAY, PAUSE, VOLUME_SET, JOIN, UNJOIN._

---

## 4 · HTTP Client (`api.py`)

- **Certificate pinning** – embeds the WiiM CA cert to satisfy HTTPS on port 443.
- **Async‑only** – all I/O awaited; sync Telnet fallback wrapped in `run_in_executor`.
- **Concurrency** – single in‑flight request protected by `asyncio.Lock`.
- **Key methods**:

  - `get_status()` – returns parsed JSON dict (`play_status`, `play_mode`, `volume`, …).
  - `play() / pause() / stop()` – `setPlayerCmd:play/pause/stop`.
  - `set_volume(pct)` – `setPlayerCmd:vol:{pct}`.
  - `select_preset(n)` – `MCUKeyShortClick:{n}`.
  - `join(master_ip)` / `unjoin()` – `setMultiroom:Slave|Exit`.

---

## 5 · Coordinator (`coordinator.py`)

- Sub‑class of `DataUpdateCoordinator`.
- Owns `client` & updates `data` every `poll_interval` seconds.
- Marks entity unavailable after ≥ 3 consecutive failures or timeout.

---

## 6 · MediaPlayer Entity (`media_player.py`)

- Maps status JSON → `MediaPlayerState` & attributes.
- Exposes `async_media_play`, `async_media_pause`, `async_volume_set`, `async_join`, `async_unjoin`.
- Optional **Media Browser** panel (v0.2) listing presets & favourite web‑radio streams.
- Handles **snapshot/restore** for TTS (stretch).

---

## 7 · Config Flow & Options Flow

1. **Config Flow**

   - Zeroconf path – auto‑populates host/IP; validates by calling `client.get_status()`.
   - Manual path – user enters IP; same validation.

2. **Options Flow** (v0.2)

   - Adjust polling interval (1‑60 s).
   - Set default volume step (1‑10 %).

---

## 8 · Coding Rules & Quality Gates

| Topic         | Rule                                                             |
| ------------- | ---------------------------------------------------------------- |
| External Deps | **None.** Everything vendored / stdlib‑only.                     |
| File Size     | ≤ 150 LOC per file (excluding blanks/docstrings).                |
| Lint          | [ruff](https://github.com/astral-sh/ruff) (full HA profile).     |
| Format        | black (line length 120).                                         |
| Tests         | pytest‑asyncio + `aresponses` for HTTP mocking; coverage > 85 %. |
| CI            | GitHub Actions: ruff → pytest → hassfest.                        |

---

## 9 · AI‑Driven Workflow (Cursor / Copilot)

> **Tip:** Keep this guide open in a pinned tab so the AI agent always has context.

### 9.1 Prompt Playbook

| Context File              | Example Prompt                                                                                                                        | Expected Output                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `api.py` (cursor at TODO) | "Implement `WiiMClient.get_status` following the HTTP API PDF. Use `aiohttp`, return parsed JSON."                                    | Full async method with SSL ctx & error handling. |
| `media_player.py`         | "Write a `WiiMMediaPlayer` subclass of `MediaPlayerEntity` that maps play/pause/volume to `WiiMClient`. Use `DataUpdateCoordinator`." | Complete entity with `supported_features`.       |
| …                         | …                                                                                                                                     | …                                                |

### 9.2 Task Sequence (import into ChatGPT Projects)

1. **Bootstrap **`\*\* – literals & defaults (§3).
2. **Generate **`** skeleton** – include cert & stubs.
3. **Implement client methods** – `_get`, `get_status`, transport cmds.
4. **Coordinator** – polling logic.
5. **MediaPlayer entity** – state mapping & services.
6. **Config Flow** – Zeroconf + manual.
7. **Unit tests** – `tests/` folder.
8. **CI workflow** – `.github/workflows/ci.yml`.
9. **Multi‑room helper** – join/unjoin services.
10. **Options Flow** – polling interval, volume step.
11. **Smoke Test** – manual HA container run.
12. **Release v0.1.0** – bump version & tag.

_(Full task definitions with acceptance criteria are copied verbatim from Section 9 of the original End‑to‑End Guide.)_

---

## 10 · Implementation Checklist

- ***

## 11 · Roadmap

| Version       | Features                                                           |
| ------------- | ------------------------------------------------------------------ |
| **0.1 (MVP)** | R1‑R6 + fixed‑volume detection + basic snapshot/restore            |
| **0.2**       | UPnP metadata enrichment, media position tracking, LED dimming cmd |
| **0.3**       | EQ presets, Bluetooth source select, TTS cutoff fix, core PR       |

---

## 12 · References & Resources

- **python‑linkplay** (Velleman fork): [https://github.com/velman/python-linkplay](https://github.com/velman/python-linkplay)
- **HA Core LinkPlay integration** (upstream patterns): [https://github.com/home-assistant/core/tree/dev/homeassistant/components/linkplay](https://github.com/home-assistant/core/tree/dev/homeassistant/components/linkplay)
- **WiiM HTTP API PDF** (command list): [https://www.wiimhome.com/pdf/HTTP%20API%20for%20WiiM%20Products.pdf](https://www.wiimhome.com/pdf/HTTP%20API%20for%20WiiM%20Products.pdf)
- **HA Developer Docs** – UpdateCoordinator, ConfigFlow patterns: [https://developers.home-assistant.io/](https://developers.home-assistant.io/)
- **LinkPlay Telnet command list** (legacy reference).

---

© 2025 WiiM Custom Integration Project – Consolidated Guide

## 13 · Multi-room Design (2025-05)

This section formalises how the custom integration handles LinkPlay/WiiM multi-room (a.k.a. "multi-zone") playback.

### 13.1 Device roles

| Role   | Detection logic                                                                    | Behaviour                                     |
| ------ | ---------------------------------------------------------------------------------- | --------------------------------------------- |
| master | `type = 0` in `getPlayerStatusEx` **and** `slaves > 0` in `multiroom:getSlaveList` | Streams its own source and forwards to guests |
| guest  | `type = 1` **or** `master_uuid` present                                            | Receives audio from master                    |
| solo   | neither of the above                                                               | Stand-alone speaker                           |

### 13.2 Polled endpoints

1. `getPlayerStatusEx` → rich playback / volume / mute / EQ / position.
2. `multiroom:getSlaveList` → list of guests (if we are master) or empty list.
   - Fallback: `getMultiroomInfoEx` or the embedded `multiroom` block in `getStatusEx`.

### 13.3 Parsing slave list

```json
{
  "slaves": 2,
  "slave_list": [
    {
      "name": "Kitchen",
      "uuid": "…",
      "ip": "192.168.1.21",
      "volume": 55,
      "mute": 0,
      "channel": 0
    },
    {
      "name": "Bathroom",
      "uuid": "…",
      "ip": "192.168.1.22",
      "volume": 50,
      "mute": 1,
      "channel": 0
    }
  ]
}
```

Field mapping:

| Raw key                 | Canonical key            | Notes                    |
| ----------------------- | ------------------------ | ------------------------ |
| `slaves`                | `slave_count`            | `int`                    |
| `slave_list[*].ip`      | `slaves[*].ip`           |                          |
| `slave_list[*].uuid`    | `slaves[*].uuid`         |                          |
| `slave_list[*].name`    | `slaves[*].name`         | UTF-8 (hex-decode)       |
| `slave_list[*].volume`  | `slaves[*].volume_level` | 0-100 → 0-1              |
| `slave_list[*].mute`    | `slaves[*].mute`         | bool                     |
| `slave_list[*].channel` | `slaves[*].channel`      | 0 = stereo, 1 = L, 2 = R |

### 13.4 HA entity model additions

- **Sensor** `<entity>_group_role` — value: `master`, `guest`, `solo`.
- **Media-player attributes**
  - `group_role`, `slave_count`, `slave_ips`, `master_ip`.
- **Services / UI**
  - `media_player.join` (existing HA service) wired to `join_group()`.
  - `media_player.unjoin` wired to `leave_group()` / `disband_group()` depending on role.

### 13.5 Group control HTTP commands

| Action                 | HTTP command                     |
| ---------------------- | -------------------------------- |
| Create group           | `setMultiroom:Master`            |
| Join as guest          | `setMultiroom:Slave:<master_ip>` |
| Leave group (guest)    | `setMultiroom:Exit`              |
| Disband group (master) | `setMultiroom:Delete`            |

### 13.6 Implementation work-plan (v0.3)

| Step | Task                                                                                                                 | Files             |
| ---- | -------------------------------------------------------------------------------------------------------------------- | ----------------- |
| 1    | Add constants for `multiroom:getSlaveList` & `setMultiroom:*`                                                        | `const.py`        |
| 2    | Implement `WiiMClient` helpers: `get_multiroom_slaves`, `create_group`, `join_group`, `leave_group`, `disband_group` | `api.py`          |
| 3    | Build `_parse_slave_list()` and enhance `_parse_player_status()`                                                     | `api.py`          |
| 4    | Update `WiiMCoordinator` to `asyncio.gather` status + slaves and derive `role`                                       | `coordinator.py`  |
| 5    | Add `GroupRoleSensor`                                                                                                | `sensor.py`       |
| 6    | Extend `WiiMMediaPlayer` attributes and grouping methods                                                             | `media_player.py` |
| 7    | Unit tests covering parsing & role detection                                                                         | `tests/`          |
| 8    | Guide & CHANGELOG update                                                                                             | `wiim_guide.md`   |

### 13.7 Implementation Phases for Grouping (2025-05)

#### Phase 1: Foundation & Home Assistant Compliance

- **Why:** Home Assistant core requires both asynchronous and synchronous join/unjoin methods for full compatibility with the `media_player.join` and `media_player.unjoin` services. Even if your integration is fully async, the core will call the synchronous methods unless they are implemented or explicitly marked as async-only.

- **What to do:**

  - Implement the following in your `MediaPlayerEntity` subclass:

    ```python
    def join_players(self, group_members: list[str]) -> None:
        """Synchronous join for HA compatibility."""
        self.hass.async_create_task(self.async_join(group_members))

    def unjoin_player(self) -> None:
        """Synchronous unjoin for HA compatibility."""
        self.hass.async_create_task(self.async_unjoin())
    ```

  - These methods act as wrappers, scheduling the async versions on the event loop.
  - This pattern is used by official integrations (Sonos, Linkplay, Yamaha MusicCast) and is required for the built-in grouping services to work.

- **Checklist:**

  - [x] `MediaPlayerEntityFeature.GROUPING` is set in `_attr_supported_features`.
  - [x] `async_join` and `async_unjoin` are implemented for device-specific logic.
  - [x] `join_players` and `unjoin_player` are implemented as wrappers.

- **Next:** After this phase, grouping services should no longer raise `NotImplementedError` and will be routed to your entity correctly by Home Assistant.

#### Phase 2: Device API Integration and State Management

- **Why:** Home Assistant entity IDs must be mapped to device-specific identifiers (e.g., IP, MAC, UUID) for group operations. Robust API calls, state refresh, and error handling are essential for reliable grouping.

- **What to do:**

  - Implement a helper to map entity_id to device ID (host/IP) using the coordinator or entity registry.
  - In `async_join` and `async_unjoin`, use this mapping to call the correct device API endpoints for group management (create, join, leave).
  - After any group operation, call `await self.coordinator.async_request_refresh()` to update all entities promptly.
  - Use try/except blocks for all API calls, log errors, and raise `HomeAssistantError` for user-facing issues.
  - Add debug logging for all group operations and state changes.

- **Checklist:**

  - [x] Entity ID to device ID mapping helper implemented.
  - [x] API calls for group management use correct device IDs.
  - [x] Coordinator refresh after group changes.
  - [x] Error handling and debug logging in group operations.

- **Next:** After this phase, group operations will reliably update device and Home Assistant state, and errors will be visible in logs for troubleshooting.

#### Phase 3: Discovery, Config Flow, and State Sync

- **Why:** Reliable device discovery, unique identification, and robust state synchronization are essential for a seamless user experience and accurate group management in Home Assistant.

- **What to do:**

  - Ensure Zeroconf/SSDP discovery is declared in `manifest.json` and implemented in `config_flow.py`.
  - In the config flow, always set a unique ID for each device (preferably MAC or UUID, not just host/IP).
  - Use `self._abort_if_unique_id_configured()` to prevent duplicates and update the config entry if a device is rediscovered with a new IP.
  - On Home Assistant startup, ensure the coordinator polls all devices and updates group state, even for externally grouped devices.
  - After any group operation, force a coordinator refresh for all involved entities.
  - Handle device removal, IP changes, and network issues gracefully, updating group state and marking devices unavailable as needed.
  - Provide clear error messages and a user-friendly setup experience in the config flow.
  - Add debug logging for discovery, config flow steps, and state sync events.

- **Checklist:**

  - [x] Zeroconf/SSDP discovery in manifest.json and config_flow.py
  - [x] Unique ID set for each device (MAC/UUID preferred)
  - [x] Duplicate device handling and config entry updates
  - [x] Coordinator fetches and syncs full group topology
  - [x] Immediate refresh after group changes and on startup
  - [x] Graceful handling of device/network changes
  - [x] Clear error messages and user-friendly config flow
  - [x] Debug logging for discovery and state sync

- **Next:** After this phase, device setup, group management, and state accuracy will be robust, even in dynamic network environments or after Home Assistant restarts.

#### Phase 4: Frontend, User Experience, Documentation, and Advanced Troubleshooting

- **Why:** A seamless UI, clear documentation, and robust diagnostics are essential for user satisfaction and effective support.

- **What to do:**

  - Ensure the default Lovelace media-control card and popular custom cards (e.g., mini-media-player) display and control grouping as expected.
  - Verify that `group_members` and group leader are accurately reflected in the UI, and that group volume/playback controls work for grouped entities.
  - Update user documentation to cover:
    - How to set up and use grouping
    - Supported features and limitations
    - Troubleshooting common issues (UI, network, device state)
  - Update developer documentation with code structure, key methods, and extension points.
  - Add advanced debug logging for all group operations, service calls, and state changes.
  - Test edge cases: device offline, network interruptions, mixed firmware, etc.
  - Provide a FAQ and support instructions for users.

- **Checklist:**

  - [x] UI grouping button appears and works
  - [x] Custom cards tested and documented
  - [x] Group state and controls accurate in UI
  - [x] User and developer documentation updated
  - [x] Debug logging for all group operations
  - [x] Edge cases and real-world scenarios tested
  - [x] FAQ and support instructions provided

- **Sample FAQ:**

  - **Q:** The grouping button does not appear in the UI.
    - **A:** Ensure at least two WiiM devices are set up, both support grouping, and are online. Check that `group_members` is populated in Developer Tools → States.
  - **Q:** Group state is not updating after join/unjoin.
    - **A:** Check logs for errors, ensure coordinator refresh is triggered after group operations, and verify network connectivity.
  - **Q:** Grouping fails with an error.
    - **A:** Enable debug logging, reproduce the issue, and check Home Assistant logs for detailed error messages. Report issues with logs attached.

- **Next:** After this phase, the integration will provide a robust, user-friendly, and supportable grouping experience, with clear diagnostics and documentation for both users and developers.
