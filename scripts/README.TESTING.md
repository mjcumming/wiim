# WiiM Test Scripts Guide

**Real-device testing with saved token**

**Canonical instructions (read these first):**

- **[`development/README.md`](../development/README.md)** — `make pre-run`, then start HA with `hass -c /workspaces/core/config` (symlinked `wiim` integration).
- **[`docs/TESTING-CONSOLIDATED.md`](../docs/TESTING-CONSOLIDATED.md)** — full 4-tier strategy; Tier 3 real-device commands (`test-automated.py`, `test-smoke.py`, `test.config`).

This file is a **script-focused companion** (flags, tables, examples). It does not replace those docs.

---

## Dev container (HA + this integration)

Use the **Home Assistant devcontainer** from the **core** repo (`.devcontainer/devcontainer.json` under your HA core checkout). The dev workspace mounts the parent folder as **`/workspaces`**, so both repos are visible (e.g. `/workspaces/core`, `/workspaces/wiim`).

**WiiM in that HA config:** `core`’s dev config already links the integration (no copy step):

```text
/workspaces/core/config/custom_components/wiim  →  /workspaces/wiim/custom_components/wiim
```

**Sanity check before starting HA:**

```bash
source /home/vscode/.local/ha-venv/bin/activate
cd /workspaces/core
hass -c /workspaces/core/config --script check_config
```

Then start HA as in the **Quick Start** section below (`hass -c /workspaces/core/config`, port **8123** per devcontainer port mapping). Edits under `/workspaces/wiim/custom_components/wiim` are picked up on reload or restart.

---

## 🚀 Quick Start

### Prerequisites

1. **Start Home Assistant** (if not already running):

   ```bash
   # Activate venv and start HA
   source /home/vscode/.local/ha-venv/bin/activate
   cd /workspaces/core
   hass -c /workspaces/core/config --open-ui

   # Or run in background:
   cd /workspaces/core && source /home/vscode/.local/ha-venv/bin/activate && \
   nohup hass -c /workspaces/core/config > /tmp/ha_startup.log 2>&1 &

   # Wait for HA to be ready (check returns 200 or 401):
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8123/api/
   ```

2. **Ensure test config exists**: `scripts/test.config` with `HA_URL` and `HA_TOKEN`

### Running Tests

```bash
# Activate venv (required for test scripts)
source /home/vscode/.local/ha-venv/bin/activate

# Run smoke tests (fast validation)
cd /workspaces/wiim
python scripts/test-smoke.py --config scripts/test.config

# Run full automated suite (includes source selection)
python scripts/test-automated.py --config scripts/test.config --mode full

# Run critical tests only (faster, excludes source selection)
python scripts/test-automated.py --config scripts/test.config --mode critical
```

---

## 📁 Configuration

### File: `scripts/test.config`

Contains:

- ✅ Home Assistant URL
- ✅ Access Token
- ✅ Device Information (IPs, MACs, models)

**Security:** Added to `.gitignore` - won't be committed.

---

## 🧪 Test Scripts

### Core Tests

| Script                            | Purpose                         | Duration |
| --------------------------------- | ------------------------------- | -------- |
| `test-smoke.py`                   | Quick validation (4 tests)      | ~2 min   |
| `test-automated.py`               | Full automated suite (9 tests)  | ~5 min   |
| `test-multiroom-comprehensive.py` | Multiroom edge cases (12 tests) | ~10 min  |

### Specialized Tests

| Script                             | Purpose                                |
| ---------------------------------- | -------------------------------------- |
| `test-device-lifecycle.py`         | Device add/remove via HA REST API      |
| `test-timers-quick.py`             | Sleep timer and alarm tests            |
| `test-timers-interactive.py`       | Interactive timer testing              |
| `test-tts-url.py`                  | TTS / URL resolution checks            |
| `test-reboot-one.py`               | Single-device reboot helper            |

---

## 📋 Test Coverage

### ✅ Covered by Automated Suite

- Device discovery
- Playback controls (play/pause/stop/next/prev)
- Volume control (set/mute)
- Source selection
- Multiroom basic
- EQ presets
- Shuffle/repeat
- Output mode

### ✅ Covered by Multiroom Suite

- 2-device join/unjoin
- 3-device join/unjoin
- External/app-style group join via direct device HTTP API command
- Subnet-aware external join sweep (validates both subnet groups without cross-subnet grouping)
- Virtual group entity
- Metadata propagation
- Group controls
- Edge cases (unjoin master, join already joined, etc.)

`test-multiroom-comprehensive.py` options:
- `--mode full` (default): full comprehensive flow + external sync checks
- `--mode external`: external/app-style sync checks only (fast regression check)
- `WIIM_TARGET_IPS=ip1,ip2,...`: optionally limit discovery to a subset of devices

### ✅ Covered by Specialized Tests

- Sleep timers
- Alarms
- Device lifecycle (add/remove/reload)

### ✅ Covered by Device Lifecycle Tests

- Config entry add via REST API
- Config entry reload
- Config entry delete
- Cleanup verification
- Re-add after delete

### 🔄 Manual Testing Recommended

- Bluetooth output
- Media browsing
- Announcements/TTS
- URL playback
- Preset playback
- **Channel balance** (`number` entity) — see [Channel balance (live device)](#channel-balance-live-device) below

---

## Channel balance (live device)

The integration exposes **`number.<device_name>_channel_balance`** when **pywiim** detects **`supports_channel_balance`** on that hardware (runtime HTTP probe). It is a normal Home Assistant **Number** (slider, −1…1, step 0.1), same patterns as subwoofer level.

**Prerequisites**

- `pywiim==2.2.1` (or newer per `manifest.json`) on the HA host
- A device/firmware where balance is supported (entity absent = probe false; not a failure)

**1. UI**

1. **Developer tools → States** — search `channel_balance` or filter domain `number`.
2. **Developer tools → Actions** — domain `number`, action `Set value`, entity your `number.*_channel_balance`, value e.g. `0.3`, then back to `0.0`.

**2. REST (same token as `scripts/test.config`)**

```bash
# Set HA_URL / HA_TOKEN from scripts/test.config (do not commit tokens).
source /home/vscode/.local/ha-venv/bin/activate
export HA_URL=http://localhost:8123
export HA_TOKEN=your_long_lived_token

ENTITY_ID=number.living_room_channel_balance   # replace with your entity

curl -sS -X POST "$HA_URL/api/services/number/set_value" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"entity_id\": \"$ENTITY_ID\", \"value\": 0.4}"

curl -sS "$HA_URL/api/states/$ENTITY_ID" -H "Authorization: Bearer $HA_TOKEN" | jq .state,.attributes
```

**3. Automated suites**

Smoke / automated / multiroom scripts in this folder exercise **media player**, volume, grouping, etc. They do **not** yet assert channel balance; add a call to `number.set_value` in a script if you want it in CI-style live runs.

---

## 🔧 Running Tests

**IMPORTANT: Always activate the venv before running tests:**

```bash
source /home/vscode/.local/ha-venv/bin/activate
cd /workspaces/wiim
```

### Smoke Tests (Fast)

```bash
source /home/vscode/.local/ha-venv/bin/activate
cd /workspaces/wiim
python scripts/test-smoke.py --config scripts/test.config
```

### Full Automated Suite

```bash
source /home/vscode/.local/ha-venv/bin/activate
cd /workspaces/wiim
python scripts/test-automated.py --config scripts/test.config --mode full
```

### Critical Path Only

```bash
source /home/vscode/.local/ha-venv/bin/activate
cd /workspaces/wiim
python scripts/test-automated.py --config scripts/test.config --mode critical
```

### Multiroom Tests

```bash
export HA_TOKEN=$(grep HA_TOKEN scripts/test.config | cut -d'=' -f2)
export HA_URL=http://localhost:8123
python scripts/test-multiroom-comprehensive.py
```

### Timer Tests

```bash
python scripts/test-timers-quick.py --entity media_player.outdoor
```

### Device Lifecycle Tests (Add/Remove)

```bash
# Test device add/remove via HA REST API
python scripts/test-device-lifecycle.py --config scripts/test.config --device-ip 192.168.1.100

# Keep device after tests (don't cleanup)
python scripts/test-device-lifecycle.py --config scripts/test.config --device-ip 192.168.1.100 --no-cleanup
```

---

## 📊 Pre-Release Checklist

```bash
# 1. Start Home Assistant (if not running)
source /home/vscode/.local/ha-venv/bin/activate
cd /workspaces/core
hass -c /workspaces/core/config --open-ui
# Wait for HA to be ready (check: curl http://localhost:8123/api/)

# 2. Run all validation
cd /workspaces/wiim
source /home/vscode/.local/ha-venv/bin/activate
make pre-release

# Or manually:
make test                    # Unit tests
make lint                    # Code quality
python scripts/test-smoke.py --config scripts/test.config
python scripts/test-automated.py --config scripts/test.config --mode full
```

---

## 🔌 Device Requirements

### Minimum (Smoke/Automated)

- 1 WiiM device with active source
- Home Assistant running

### Full Testing

- 3 WiiM devices for multiroom
- Active playback source (Spotify, etc.)
