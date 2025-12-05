# WiiM Test Scripts Guide

**Real-device testing with saved token**

---

## 🚀 Quick Start

```bash
# Load saved token (once per session)
source scripts/load-test-env.sh

# Run smoke tests (fast validation)
python scripts/test-smoke.py --config scripts/test.config

# Run full automated suite
python scripts/test-automated.py --config scripts/test.config --mode full
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

### 🔄 Manual Testing Recommended

- Bluetooth output
- Media browsing
- Announcements/TTS
- URL playback
- Preset playback

---

## 🔧 Running Tests

### Smoke Tests (Fast)

```bash
python scripts/test-smoke.py --config scripts/test.config
```

### Full Automated Suite

```bash
python scripts/test-automated.py --config scripts/test.config --mode full
```

### Critical Path Only

```bash
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

---

## 📊 Pre-Release Checklist

```bash
# Run all validation
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
