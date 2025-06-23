# WiiM Integration – Global Work Plan

This TODO list captures every open work-stream required to reach the **1.1.0** stable release while respecting
Home-Assistant integration guidelines, HACS rules, and our own cursor design guide.

---

## 0  Legend

- **PR-A** / **PR-B** … refer to pull-request sequence on `main`.
- ✅ Done 🟡 In progress ⬜ Pending

---

## 1  Pydantic Roll-out

| Step | Status | Description                                                                                 |
| ---- | ------ | ------------------------------------------------------------------------------------------- |
| 0    | ✅     | `models.py` added, basic `DeviceInfo` & `PlayerStatus` models                         |
| 1    | ✅     | `api.py` attaches `_model` objects; validation failures logged @DEBUG                   |
| 2    | ✅     | **PR-B** – Coordinator stores `status_model` / `device_model` (typed)            |
| 3    | ✅     | Refactor `data.py` & sensors to prefer `*_model` values over raw dicts                  |
| 4    | ✅     | PURGE legacy dict helpers, migrate all call-sites to Pydantic, enable `mypy --strict`     |
| 4a   | ✅     | Stubbed Home-Assistant classes, pydantic plugin configured, mypy strict baseline (0 errors) |
| 5    | 🟡     | Delete `_model` alias once tree compiles *strict* without errors (final cleanup)        |

---

## 2  Coordinator Refactor – *final push* (all files ≤ 300 LOC)

| Step | Status | Description |
|-----:|:------:|-------------|
| 0 | ✅ | `coordinator_polling.py` hosts heavy loop, returns typed `status_model`/`device_model`. |
| 1 | ✅ | **Carve-out helper modules** from `coordinator.py` ① `coordinator_metadata.py` ② `coordinator_eq.py` ③ `coordinator_role.py` ④ `coordinator_multiroom.py`. Only 2-line wrappers stay. |
| 2 | ✅ | Introduce `TrackMetadata`, `EQInfo`, `PollingMetrics` (dataclass) Pydantic models. Helpers return models; polling stores `metadata_model`, `eq_model`, `polling_metrics`. |
| 3 | ✅ | Convert helper implementations from dicts → models. Delete *all* residual `dict.get()` logic on WiiM payloads. |
| 4 | ✅ | Purge legacy keys (`status`, `device_info`) from coordinator `.data` and from tests/fixtures. |
| 5 | ✅ | Enable `ruff-size-check` & `mypy --strict`; ensure `coordinator.py` ↓ 300 LOC, helpers ↓ 300 LOC, polling ↓ 300 LOC. |
| 6 | ✅ | Update docs & ARCHITECTURE diagram to reflect model-only data-flow. |

---

## 3  File-Size Enforcement & CI

✅ Add `ruff-size-check` (soft warn ≥300, fail >400 LOC).
✅ Pre-commit hook for `ruff`, `black`, `mypy`.
✅ CI job for `pytest -n auto`, `mypy --strict`.

---

## 4  Group Media Player Feature

| Task                                                  | Status |
| ----------------------------------------------------- | ------ |
| Extract `group_helpers.py` ✅                       |        |
| Re-implement `group_media_player.py` (≤200 LOC) ⬜ |        |
| Add option flag to Options Flow ⬜                    |        |
| Unit tests for volume/mute delegation ⬜              |        |
| Docs & screenshots ⬜                                 |        |

---

## 5  Documentation

- Update `development/ARCHITECTURE.md` with Pydantic data-flow. ✅
- Add `docs/models.md` with model schemas. ✅
- Expand troubleshooting doc with new typed-validation error messages. ✅

---

## 6  Testing Coverage ≥ 20 %

- Unit tests for `models.py` edge-cases ⬜
- Happy-path & failure tests for `coordinator_polling.async_fetch_data` ⬜
- Tests for `group_helpers` calc & async setters ⬜

---

## 7  Release / Milestones

1.1.0-b1 – all refactors complete, no group player yet.
1.1.0-b2 – group media player behind flag.
1.1.0  – stable, feature flag default on, docs finalised, changelog updated.
