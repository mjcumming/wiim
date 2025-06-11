# Cursor **Rules & Engineering Guide** – WiiM / LinkPlay HACS Integration

_Treat this as the project’s **constitution**. Read it. Pin it in Cursor. Obey it._

---

## 0  Non‑negotiables (read before you code a single line)

1. **Every file lives inside** `custom_components/wiim/` – this is ★the only★ directory you may touch.
   ✦ *Never* modify `homeassistant/` core folders.
   ✦ *Never* import private HA internals.
2. **Follow this guide line‑by‑line.** Deviations require an Issue + signed‑off design note from the Tech Lead.
3. **If you are confused, STOP** → ask in GitHub Discussion. Guessing = bugs + rework.

---

## 1  Golden Rules

0. **Spec > Ego** – build only what the ticket describes.
1. Home Assistant Dev Guidelines.
2. HACS repo standards & semantic versioning.
3. LinkPlay API is canonical – WiiM quirks wrapped in code, never leak.
4. Small, composable, typed modules (< 200 LOC).
5. All work tracked (Issue → Branch → PR → Review).
6. Fail loudly with actionable log messages.

---

## 2  Mental Checklist before writing code

Ask yourself **every time** you open a ticket:

1. _What user story am I solving?_ (quote the Issue #)
2. _Where does this logic belong?_ (`api.py` ↔ `coordinator.py` ↔ entity/service)
3. _What data do I need from the device?_ (`getStatusEx`, `getPlayerStatus`, etc.)
4. _How will I test success & failure?_ (unit + integration test)
5. _How does this interact with multi‑room state?_
6. _What happens if the device is offline?_ (timeouts, retries)
7. _How will this appear in Home Assistant UI?_ (state, attributes, services)
   If any answer is fuzzy—stop and clarify.

---

## 3  Directory & File Layout

```
custom_components/
  wiim/
    __init__.py          # set up domain, DataUpdateCoordinator
    api.py               # LinkPlayClient + WiiMClient (Strategy)
    coordinator.py       # polls device, caches data
    media_player.py      # MediaPlayerEntity implementation
    services.yaml        # custom HA services
    config_flow.py       # setup & options flow
    volume_helpers.py    # group‑volume helpers
    const.py             # constants
    manifest.json
    strings.json         # translations
    tests/               # pytest unit + integration tests
    docs/                # markdown diagrams, API snapshots
```

> **Rule:** Any new file outside this tree = reject the PR.

---

## 4  Data Model (Pydantic v2)

```python
class PlayerStatus(BaseModel):
    play_state: Literal["play", "pause", "stop"]
    volume: int            # 0–100
    muted: bool
    mode: int              # source ID
    curpos: int            # ms
    totlen: int            # ms
    title: str | None
    artist: str | None
    album: str | None

class DeviceInfo(BaseModel):
    name: str
    uuid: str
    ip: IPvAnyAddress
    model: str
    firmware: str
    wmrm_version: str
    preset_slots: int
    inputs: set[str]       # {"wifi", "bluetooth", ...}
```

All API JSON → these models. No raw dicts past `api.py`.

---

## 5  System Architecture & Flow

```
User → HA Service call
      ↓
media_player.py
      ↓ (delegates)
coordinator.py  ── poll every 5 s ──▶ api.py ──▶ device
      ↑                               ↑
      └──── cached data (PlayerStatus & DeviceInfo)
```

- **Strategy Pattern** – `LinkPlayClient` base; `WiiMClient` overrides endpoints requiring HTTPS or Yamaha path.
- **Group Logic Helper** – `volume_helpers.py`

  ```python
  def set_group_volume(master, members, vol):
      for m in members:
          m.client.set_volume(vol)
  ```

---

## 6  Implementation Playbook

| Step                                      | File     | Code Skeleton |
| ----------------------------------------- | -------- | ------------- |
| Create client                             | `api.py` | \`\`\`python  |
| class LinkPlayClient: # ctor(ip, session) |          |               |

```
async def player_status(self) -> PlayerStatus: ...
async def set_volume(self, vol: int): ...
```

````|
| Coordinator | `coordinator.py` | subclass `DataUpdateCoordinator`; fetch + store `PlayerStatus` every 5 s |
| Entity | `media_player.py` | use coordinator data, implement `async_set_volume_level` etc. |
| Services | `services.yaml` + handler in `__init__.py` | `wiim.play_preset`, `wiim.join_group` |
| Options Flow | `config_flow.py` | HTTPS toggle, polling interval |

---
## 7  Testing Strategy
1. **Unit:** Mock HTTP with `respx`. Use snapshot JSONs for each device model.
2. **Integration:** Use HA test harness. Assert entity state & services.
3. **Group tests:** spin up two mocked devices; test join + kick + computed group volume.
4. Coverage ≥ 90 %.

---
## 8  CI Pipeline (GitHub Actions)
```yaml
jobs:
  lint-test:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.12'}
      - run: pip install -r requirements-dev.txt
      - run: pre-commit run --all-files
      - run: pytest
  release:
    needs: lint-test
    if: startsWith(github.ref, 'refs/tags/')
    uses: hacs/action@v2
````

---

## 9  Contributor PR Checklist (template)

- [ ] Code confined to `custom_components/wiim/`
- [ ] Fulfils Issue #\_\_ ✅
- [ ] Added/updated unit + integration tests
- [ ] passes `pre‑commit` & coverage ≥ 90 %
- [ ] Docs/changelog updated
- [ ] Tested on **real device** (model & firmware listed)

---

## 10  Common Pitfalls

| Symptom                                                                 | Root Cause                  | Fix                                                        |
| ----------------------------------------------------------------------- | --------------------------- | ---------------------------------------------------------- |
| Accidentally imported `homeassistant.components.media_player` internals | Breaking core encapsulation | Refactor to use public helpers only.                       |
| Cursor suggests editing `ha/core`                                       | File outside Wiim dir       | Reject suggestion, remind Cursor of rule #0.               |
| Group slider only moves host                                            | Missing service loop        | Implement `set_group_volume` helper.                       |
| JSON decode error                                                       | Field hex‑encoded           | Use `bytes.fromhex().decode()` to parse `Title`, `Artist`. |

---

## 11  When in doubt

1. Re‑read this file 🤬.
2. Open GitHub Discussion with “QUESTION:” prefix.
3. Wait for sign‑off **before** coding.

---

### End of Rules
