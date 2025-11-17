# Quick Start: Real Device Testing

**Ready to test your actual WiiM devices?** Follow these 3 simple steps!

## ✅ Prerequisites

- ✅ Home Assistant running at `http://homeassistant.local:8123` (confirmed!)
- ✅ WiiM integration installed
- ✅ At least one WiiM device configured
- ⚠️ **Need:** Long-lived access token (get in step 1)

---

## 🚀 Quick Start (3 Steps)

### Step 1: Get Your Access Token (2 minutes)

1. Open Home Assistant in your browser
2. Click your profile (bottom left)
3. Scroll to **"Long-Lived Access Tokens"**
4. Click **"Create Token"**
5. Give it a name: "WiiM Testing"
6. **Copy the token** (you won't see it again!)

Example token format:

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJmNGQ...
```

### Step 2: Run the Test Suite (30 seconds)

```bash
# Set your token (replace with your actual token)
export HA_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Run tests
cd /workspaces/wiim
python scripts/test-real-devices.py http://homeassistant.local:8123
```

### Step 3: Review Results

The script will:

1. ✅ Connect to Home Assistant
2. ✅ Discover all WiiM devices
3. ✅ Test each device automatically
4. ✅ Show colored pass/fail results
5. ✅ Save detailed JSON report

**That's it!** 🎉

---

## 📊 What Gets Tested

For **each WiiM device**, the suite automatically tests:

| Test                    | What It Checks           | Duration |
| ----------------------- | ------------------------ | -------- |
| **Device Availability** | Is device online?        | < 1s     |
| **Device Information**  | Model, firmware, IP, MAC | < 1s     |
| **Volume Control**      | Can set volume to 35%?   | ~3s      |
| **Mute Control**        | Can mute/unmute?         | ~3s      |
| **Source Selection**    | Can switch inputs?       | ~3s      |

**Total per device:** ~10 seconds

---

## 🎨 Example Output

```bash
$ python scripts/test-real-devices.py http://homeassistant.local:8123

================================================================================
                      WiiM Real Device Test Suite
================================================================================

ℹ️  Checking Home Assistant connection...
✅ Connected to Home Assistant
ℹ️  Version: 2025.11.2

================================================================================
                            Device Discovery
================================================================================

✅ Found 2 WiiM device(s)

Device 1:
  Entity ID:    media_player.living_room_wiim
  Name:         Living Room WiiM
  Model:        WiiM Pro Plus
  IP Address:   192.168.1.100
  State:        playing

Device 2:
  Entity ID:    media_player.kitchen_wiim
  Name:         Kitchen WiiM
  Model:        WiiM Mini
  IP Address:   192.168.1.101
  State:        idle

--------------------------------------------------------------------------------
                    Testing: Living Room WiiM
--------------------------------------------------------------------------------

Test: Device Availability
✅ Device is available

Test: Device Information
  ✓ device_model: WiiM Pro Plus
  ✓ firmware_version: 4.8.618780
  ✓ ip_address: 192.168.1.100
  ✓ mac_address: AA:BB:CC:DD:EE:01
✅ All device information present

Test: Volume Control
  Original volume: 45%
  Setting volume to 35%...
  New volume: 35%
✅ Volume control works

Test: Mute Control
  Muting device...
✅ Mute control works

Test: Source Selection
  Available sources: USB, Bluetooth, Spotify
  Current source: Spotify
  Switching to: USB
  New source: USB
✅ Source selection works

Device Test Summary:
  5/5 tests passed

[... Kitchen WiiM tests ...]

================================================================================
                         Test Suite Summary
================================================================================

Living Room WiiM: 5/5 tests passed
Kitchen WiiM: 5/5 tests passed

Overall Results:
  Devices Tested:   2
  Total Tests:      10
  Tests Passed:     10
  Success Rate:     100.0%
  Duration:         22.5s

✅ Test report saved to: wiim_test_report_20251117_160530.json
```

---

## 📄 Test Report

Check the generated JSON report:

```bash
# View latest report
cat wiim_test_report_*.json | jq '.'

# Quick summary
jq '.success_rate, .duration_seconds' wiim_test_report_*.json
```

**Report includes:**

- ✅ Timestamp
- ✅ All devices tested
- ✅ Individual test results
- ✅ Pass/fail details
- ✅ Duration metrics

---

## 🔄 Automated Testing

### Run Every Hour

```bash
# Add to crontab
export EDITOR=nano
crontab -e

# Add this line:
0 * * * * cd /workspaces/wiim && HA_TOKEN='YOUR_TOKEN' python scripts/test-real-devices.py http://homeassistant.local:8123 >> /tmp/wiim-tests.log 2>&1
```

### Monitor Results

```bash
# Watch logs
tail -f /tmp/wiim-tests.log

# Check test history
ls -lh wiim_test_report_*.json

# Success rate trend
jq '.success_rate' wiim_test_report_*.json | \
  awk '{sum+=$1; count++} END {print "Average success rate:", (sum/count)*100 "%"}'
```

---

## 🔧 Troubleshooting

### Problem: "No access token provided"

**Solution:** Set the token:

```bash
export HA_TOKEN="your_token_here"
# Or use --token flag
python scripts/test-real-devices.py http://homeassistant.local:8123 --token YOUR_TOKEN
```

### Problem: "Cannot connect to Home Assistant"

**Solution:** Check HA is running:

```bash
curl http://homeassistant.local:8123/api/
# Should return: {"message":"API running."}
```

### Problem: "No WiiM devices found"

**Solution:**

1. Verify WiiM integration is installed
2. Check devices are configured (Settings → Devices & Services → WiiM)
3. Ensure devices are powered on

### Problem: "Some tests failed"

**Normal!** This might happen if:

- Device is playing music (volume test might not work)
- Device only has one source (source test skipped)
- Network latency (increase wait times)

Check the JSON report for details on what failed.

---

## 🎯 Advanced Usage

### Test Specific Device

Modify `discover_devices()` in the script:

```python
# Only test Living Room
wiim_devices = [
    state for state in all_states
    if state['entity_id'] == 'media_player.living_room_wiim'
]
```

### Test Only Available Devices

```python
# Skip unavailable devices (already built-in!)
wiim_devices = [
    state for state in all_states
    if state['state'] != 'unavailable'
]
```

### Add Custom Test

```python
def test_preset_playback(self, device: Dict[str, Any]) -> Dict[str, Any]:
    """Test preset playback."""
    entity_id = device['entity_id']

    print(f"\n{Colors.BOLD}Test: Preset Playback{Colors.RESET}")

    # Play preset 1
    self.call_service('wiim', 'play_preset', entity_id, preset=1)
    time.sleep(5)

    state = self.get_state(entity_id)
    is_playing = state['state'] == 'playing'

    if is_playing:
        self.print_success("Preset playback works")
    else:
        self.print_failure("Preset did not play")

    return {
        'test': 'Preset Playback',
        'passed': is_playing,
        'details': {'preset': 1, 'state': state['state']}
    }

# Add to test_device() method:
results.append(self.test_preset_playback(device))
```

---

## 📈 CI/CD Integration

### GitHub Actions

```yaml
name: Daily WiiM Tests

on:
  schedule:
    - cron: "0 8 * * *" # 8 AM daily
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install dependencies
        run: pip install requests

      - name: Run tests
        env:
          HA_TOKEN: ${{ secrets.HA_TOKEN }}
        run: |
          python scripts/test-real-devices.py \
            http://homeassistant.local:8123

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-report
          path: wiim_test_report_*.json
```

### Jenkins

```groovy
pipeline {
    agent any
    triggers {
        cron('0 */6 * * *')  // Every 6 hours
    }
    environment {
        HA_TOKEN = credentials('ha-token')
    }
    stages {
        stage('Test') {
            steps {
                sh '''
                    python scripts/test-real-devices.py \
                        http://homeassistant.local:8123
                '''
            }
        }
    }
    post {
        always {
            archiveArtifacts 'wiim_test_report_*.json'
        }
    }
}
```

---

## 🎓 Best Practices

1. **Run tests during low-usage times** - Tests change volume/source
2. **Keep token secure** - Use environment variables, not hardcoded
3. **Monitor success rate trends** - Declining success = issues
4. **Save test reports** - Useful for debugging
5. **Test after updates** - Verify integration still works

---

## 📚 Related Documentation

- **[Device Enumeration Guide](DEVICE.ENUMERATION.AND.TESTING.md)** - Detailed enumeration methods
- **[Real-World Testing Guide](REAL.WORLD.TESTING.md)** - Service examples and manual testing
- **[Automated Test Results](AUTOMATED.TEST.RESULTS.md)** - Unit test results

---

## ✅ Summary

**What you have:**

- ✅ Production-ready test script
- ✅ Tests 5 key functions per device
- ✅ Colored output with clear results
- ✅ JSON reports for analysis
- ✅ CI/CD integration support
- ✅ Runs in ~10 seconds per device

**Ready to run!** Just need your access token.

```bash
# That's all you need!
export HA_TOKEN="your_token"
python scripts/test-real-devices.py http://homeassistant.local:8123
```

🎉 **Happy Testing!**
