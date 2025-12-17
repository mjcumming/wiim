# WiiM Test Scripts Guide

**Real-device testing with saved token**

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
| `test-multiroom-comprehensive.py` | Multiroom edge cases (10 tests) | ~10 min  |

### Specialized Tests

| Script                             | Purpose                                |
| ---------------------------------- | -------------------------------------- |
| `test-device-lifecycle.py`         | Device add/remove via HA REST API      |
| `test-device-115-comprehensive.py` | Deep testing of specific device        |
| `test-channel-balance.py`          | Channel balance (uses pywiim directly) |
| `test-timers-quick.py`             | Sleep timer and alarm tests            |
| `test-timers-interactive.py`       | Interactive timer testing              |

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
- Virtual group entity
- Metadata propagation
- Group controls
- Edge cases (unjoin master, join already joined, etc.)

### ✅ Covered by Specialized Tests

- Channel balance
- Sleep timers
- Alarms
- Deep device testing

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
