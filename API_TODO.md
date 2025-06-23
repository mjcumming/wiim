# WiiM API Client Refactor Plan

> NOTE: Home-Assistant custom integrations cannot include arbitrary sub-packages when published via HACS/ZIP – therefore the refactor keeps a **flat module layout** (multiple `api_*.py` files in `custom_components/wiim/`).

---

## 1. Objectives

1. Separation of Concerns – split the monolithic `api.py` into focused, <300-LOC modules.
2. Pydantic Everywhere – all structured payloads returned/accepted as models.
3. Centralised Session & Transport logic – one place to handle probing, ssl, retries.
4. Consistent Logging & Error types.
5. Unit-testable, incremental, no breaking public import (`WiiMClient` remains).

---

## 2. Target Module Layout (flat)

```
custom_components/wiim/
├── api_base.py      # networking, _request(), exceptions, BaseClient
├── api_device.py    # device info, firmware, LED
├── api_playback.py  # play/pause/seek/volume/shuffle/repeat
├── api_group.py     # multi-room helpers
├── api_eq.py        # EQ presets & custom bands
├── api_preset.py    # preset list & play_preset
├── api_diag.py      # diagnostics: reboot, sync_time, meta info, raw send
└── api.py           # façade composing mixins, keeps public import stable
```

*All file sizes must obey the 300-LOC soft limit (size-check CI).*
The existing `models.py` (Pydantic) stays unchanged in the same directory.

---

## 3. Incremental Migration Steps

| PR | Scope               | Key Tasks                                                                                                                           |
| -- | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| ✅ | Groundwork          | `api_base.py` created, legacy moved; `api.py` façade in place                                                                  |
| ✅ | Device              | • Move `get_device_info`, `get_mac_address`, `get_firmware_version`, LED helpers. `<br>`• Return `DeviceInfo` model.    |
| ✅ | Playback            | • Extract play/pause/stop/next/prev/seek, volume, mute, repeat, shuffle helpers.`<br>`• Purge raw-dict fallbacks.               |
| ✅ | EQ & Preset         | • Move EQ endpoints to `api_eq.py`, convert to `EQInfo` model. `<br>`• Move preset list & play_preset to `api_preset.py`. |
| ✅ | Group & Diagnostics | • Extract multi-room helpers to `api_group.py`. `<br>`• Extract reboot, sync_time, meta_info, raw command to `api_diag.py`. |
| ✅ | Cleanup             | • Delete legacy code from monolithic `api.py` leaving only façade + `DeprecationWarning` for direct use.                      |

Each PR must keep **CI green** (pytest + mypy strict + ruff size-check).

---

## 4. CI / Quality Guard-rails

1. Temporary `# pragma: allow-long-file` for `api_base.py` until shrunk ≤300 LOC.
2. Update `ruff-size-check` exclude list only if pragma'd.
3. Enable `mypy --strict` on new modules immediately.

---

## 5. Testing Strategy

• Use `aresponses` or mocked `aiohttp` to unit-test each module in isolation.
• Focus: endpoint construction, model validation, error surfacing.
• Maintain existing higher-level integration tests unchanged.

---

## 6. Documentation Tasks

• Add an "API Client Architecture" subsection to `development/ARCHITECTURE.md`.
• Extend `docs/models.md` with new `EQInfo`, `GroupInfo` schemas once added.

---

## 7. Roll-out Philosophy

Small, reviewable PRs (<400 LOC diff) aligning with our "one-step-at-a-time" refactor principle, ensuring no external breakage while improving maintainability.

---

*Created by the Cursor AI assistant on request of the maintainer – feel free to amend.*
