# WiiM / LinkPlay Home Assistant Integration – Architecture Guide

> **Audience**: Home-Assistant developers & maintainers of this custom component.
> **Goal**: Provide a single, accurate reference for understanding, extending and debugging the integration.

---

## 1. Overview

The WiiM / LinkPlay integration adds first-class support for WiiM-powered speakers to Home Assistant (HA). The component focuses on **clean architecture & maintainability** while exposing the full feature-set of the underlying devices:

• Media playback & transport control
• Multi-room (master/slave) grouping
• Equaliser presets & custom bands
• Source switching
• Device maintenance (reboot, time-sync)

Key design themes:

1. **Separation of Concerns** – each file owns a single responsibility.
2. **UUID-based registry** – a central device registry keyed by immutable hardware UUIDs with O(1) look-ups for IP, MAC **and** entity-id.
3. **Smart polling** – dynamic intervals (1 s → 120 s) driven by activity heuristics to cut API traffic by up to 90 %.
4. **Service delegation** – user-facing services implemented in small, testable helper classes instead of monolithic entity methods.

---

## 2. Repository Layout

```
custom_components/wiim/
├── __init__.py            # entry-point & platform setup
├── api.py                 # async HTTP client (controls the device)
├── coordinator.py         # DataUpdateCoordinator + smart polling glue
├── smart_polling.py       # *isolated* polling logic & prediction
├── device_registry.py     # global UUID registry & group tracking
├── media_player.py        # core entity (~1 700 LOC – slated for trim)
├── group_media_player.py  # virtual master entity
├── button.py / number.py / sensor.py / switch.py / binary_sensor.py
├── services/              # service helper modules (clean delegation)
└── utils/                 # misc helpers shared across modules
```

---

## 3. Core Components

### 3.1 Device Registry (`device_registry.py`)

- Single source of truth – all state in one `dict[str, DeviceState]` keyed by device **UUID**.
- Fast lookup indexes: `_ip_to_uuid`, `_mac_to_uuid`, `_entity_to_uuid`.
- Tracks roles (`solo`, `master`, `slave`, `virtual_master`) and relationships.
- Exposes helper methods: `find_device*`, `get_group_members_for_device`, `handle_role_change`, etc.
- Virtual master entities are registered here → UI & services never need to guess.

### 3.2 Coordinator & Smart Polling

- `coordinator.py` holds a `WiiMCoordinator` (`DataUpdateCoordinator`).
- Delegates interval decisions to `SmartPollingManager` in `smart_polling.py`.
- Activity tiers:
  - Active Playback – 1 s
  - Recent Activity – 5 s
  - Background Idle – 30 s
  - Deep Sleep – 120 s
- Playback position prediction avoids frequent `getPlayerStatus` calls during long tracks.

### 3.3 HTTP Client (`api.py`)

- Full async LinkPlay client (≈1 100 LOC).
- Auto-detects HTTP/HTTPS, permissive SSL for self-signed certs, tries multiple ports (443/4443/80).
- Implements every command used by the integration plus fall-backs.
- **NB:** Detailed protocol reference lives in the manufacturer's documentation – **omitted here by intention**.

### 3.4 Media Entities

- **Physical player** – `WiiMMediaPlayer` (implements HA `MediaPlayerEntity`). Responsible **only** for UI-facing features; heavy lifting is pushed down to coordinator, registry or service helpers.
- **Virtual master** – `WiiMGroupMediaPlayer` represents the group leader and surfaces group-wide state.
- Supported entities today:
  - `media_player` (physical + virtual)
  - `sensor` – Group Role, IP Address
  - `button` – Reboot, Sync Time
  - `number` – Polling Interval, Volume Step _(Volume Step planned for removal – see Roadmap)_
  - `switch` / `binary_sensor` – small demo entities

### 3.5 Service Delegation

- `services/` package holds stateless helpers (`WiiMMediaServices`, `WiiMGroupServices`, …).
- `media_player.py` merely validates input & calls helpers → keeps entity lean.

---

## 4. Group Management Workflow

1. HA `media_player.join` triggers `async_join` on the target master.
2. Entity IDs are resolved → coordinators via **device registry** (works with name-based, IP-based or MAC-based IDs).
3. `_create_wiim_multiroom_group` runs device-level API calls (`ConnectMasterAp:*` or legacy commands).
4. Registry updates roles/relationships; coordinator refresh cascades to all members via `_refresh_group_coordinately`.
5. UI updates instantly; virtual master is filtered from join targets to avoid recursive groups.

---

## 5. State-Refresh & Error Handling

- `_standardized_refresh` wrapper enforces consistent request→refresh→verify pattern.
- Batch-refreshes: master first → 100 ms delay → parallel slave refresh.
- Role-change detection (`handle_role_change`) reconciles mismatches every 3rd polling cycle.

---

## 6. Quality, Testing & CI

- Unit tests live under `tests/`. Current coverage ~32 %.
- `Makefile` targets (`make dev-check`, `make check-all`) reproduce CI locally.
- Python **3.13+** is mandatory to match HA 2024.12 requirements.
- One open failure (`test_device_creation` expects name `WiiM`) – tracked in Roadmap.

---

## 7. Maintenance Tips

- **Adding a new feature** – decide which layer owns it (service, coordinator, registry).
- **Debugging group issues** – always start with `device_registry.get_group_members_for_device(...)`.
- **Smart polling diagnostics** – call `media_player.*.get_smart_polling_diagnostics` service.

---

## 8. Roadmap (excerpt)

See `wiim/ROADMAP.md` for the complete list, but high-priority items include:

- Trim `media_player.py` below 800 LOC.
- Remove `Volume Step` number entity (fixed step of 5 %).
- Add Firmware Update sensor.
- Finish test suite for Smart Polling & Group flows (>90 % coverage target).

---

## 9. Document History

| Version | Date       | Notes                                                         |
| ------- | ---------- | ------------------------------------------------------------- |
| 1.0     | 2025-06-03 | Initial consolidation of legacy design docs into single guide |

## 10. References

For detailed protocol specifications and the upstream reference implementation, consult:

- LinkPlay/Arylic HTTP API documentation – <https://developer.arylic.com/httpapi/#http-api>
- WiiM Mini HTTP API – <https://www.wiimhome.com/pdf/HTTP%20API%20for%20WiiM%20Mini.pdf>
- WiiM Products HTTP API – <https://www.wiimhome.com/pdf/HTTP%20API%20for%20WiiM%20Products.pdf>
- Up-stream Python reference client (`python-linkplay`) – <https://github.com/Velleman/python-linkplay>

These documents form the canonical source for low-level command formats, endpoint semantics, and edge-case behaviour that this integration builds upon.

## 11. Strategic Refactor (2025-06) - CORRECTED PLAN

The integration is being migrated to a **Sonos-style** architecture based on comprehensive analysis of Home Assistant's premier audio integration. The work is split into nine incremental phases with corrected priorities and dependencies.

### **🎯 Sonos Alignment Analysis**

After thorough examination of the Sonos integration patterns, key architectural gaps were identified:

| **Component**        | **Current WiiM**     | **Target (Sonos-style)**                 | **Status**   |
| -------------------- | -------------------- | ---------------------------------------- | ------------ |
| **Data Layer**       | Basic `data.py`      | Rich `Speaker` class like `SonosSpeaker` | 🔄 Phase 1   |
| **Entity Base**      | Old `WiiMEntity`     | Event-driven `WiimEntity`                | ❌ Phase 2   |
| **Media Player**     | 1,762 lines          | ~400 lines (like Sonos)                  | ❌ Phase 3   |
| **Device Registry**  | 25KB custom registry | HA registry only                         | ❌ Phase 4   |
| **Event System**     | None                 | Dispatcher-based                         | ❌ Phase 1-2 |
| **Group Management** | Scattered logic      | Centralized in `Speaker`                 | ❌ Phase 3   |

### **Phase Overview**

| Phase | Deliverable                                                       | Status         | Dependencies |
| ----- | ----------------------------------------------------------------- | -------------- | ------------ |
| 0     | Foundation & cleanup, feature branch                              | ✅ done        | None         |
| 1     | Rich `Speaker` class with event dispatching (like `SonosSpeaker`) | 🔄 in-progress | Phase 0      |
| 2     | New `WiimEntity` base class (like `SonosEntity`)                  | ⏳             | Phase 1      |
| 3     | Media player refactor: 1,762 → ~400 lines                         | ⏳             | Phase 2      |
| 4     | Delete custom `device_registry.py`, use HA registry only          | ⏳             | Phase 1      |
| 5     | Group pattern: virtual master uses same identifiers (Sonos style) | ⏳             | Phase 3      |
| 6     | Smart-polling isolation (pure functions)                          | ⏳             | Phase 1      |
| 7     | Comprehensive testing: 90% coverage                               | ⏳             | Phase 1-6    |
| 8     | Updated documentation & developer guides                          | ⏳             | Phase 7      |
| 9     | Final cleanup, deprecation warnings, version 1.0.0                | ⏳             | Phase 8      |

### **Key Corrections from Original Plan**

1. **Phase 1 Priority**: Must complete rich `Speaker` class before entity refactor
2. **Event System**: Critical missing piece - dispatcher-based communication
3. **Device Registry Elimination**: 25KB custom registry conflicts with HA patterns
4. **Group Management**: Must be centralized in `Speaker` class, not scattered
5. **Media Player Size**: Target ~400 lines (matching Sonos), not 800

### **Critical Success Factors**

- ✅ **Zero user impact** - maintain all existing functionality
- ✅ **Event-driven architecture** - implement dispatcher pattern like Sonos
- ✅ **Single device registration path** - eliminate custom registry conflicts
- ✅ **Rich Speaker business logic** - move intelligence from entities to Speaker
- ✅ **Clean separation** - entities become thin wrappers over Speaker

### **References**

- **Sonos Integration Analysis** - [REFACTOR_PLAN_v2.md](docs/REFACTOR_PLAN_v2.md)
- **Home Assistant Device Registry** - <https://developers.home-assistant.io/docs/device_registry_index>
- **Event Dispatcher Pattern** - <https://developers.home-assistant.io/docs/integration_listen_events/>

Each phase is released as an **independent PR** to make code-review manageable and to avoid large, risky drops. See `docs/REFACTOR_PLAN_v2.md` for the complete corrected implementation plan with Sonos pattern alignment.
