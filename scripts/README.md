# WiiM Integration Test Scripts

## Real Device Testing

### test-real-devices.py

Automated test suite for testing real WiiM devices in a running Home Assistant instance.

#### Features

- ✅ Discovers all WiiM devices automatically
- ✅ Tests volume control
- ✅ Tests mute/unmute
- ✅ Tests source selection
- ✅ Tests device information
- ✅ Colored output with pass/fail indicators
- ✅ Generates JSON test reports
- ✅ Exit codes for CI/CD integration

#### Usage

##### 1. Get Access Token

Create a long-lived access token in Home Assistant:

1. Go to your Home Assistant profile
2. Scroll to "Long-Lived Access Tokens"
3. Click "Create Token"
4. Copy the token

##### 2. Run Tests

**Option A: Using environment variable (recommended)**

```bash
export HA_TOKEN="your_long_lived_access_token_here"
python scripts/test-real-devices.py http://homeassistant.local:8123
```

**Option B: Using command line**

```bash
python scripts/test-real-devices.py http://homeassistant.local:8123 --token YOUR_TOKEN
```

**Option C: Test local instance**

```bash
python scripts/test-real-devices.py http://localhost:8123 --token YOUR_TOKEN
```

#### Example Output

```
================================================================================
                      WiiM Real Device Test Suite
================================================================================

Home Assistant: http://homeassistant.local:8123
Start Time: 2025-11-17 15:30:00

ℹ️  Checking Home Assistant connection...
✅ Connected to Home Assistant
ℹ️  Version: 2025.11.2

================================================================================
                            Device Discovery
================================================================================

ℹ️  Searching for WiiM devices...
✅ Found 3 WiiM device(s)

Device 1:
  Entity ID:    media_player.living_room_wiim
  Name:         Living Room WiiM
  Model:        WiiM Pro Plus
  Firmware:     4.8.618780
  IP Address:   192.168.1.100
  State:        playing
  Available:    True

Device 2:
  Entity ID:    media_player.kitchen_wiim
  Name:         Kitchen WiiM
  Model:        WiiM Mini
  Firmware:     4.8.618780
  IP Address:   192.168.1.101
  State:        idle
  Available:    True

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
  Available sources: USB, Bluetooth, AirPlay, Spotify
  Current source: Spotify
  Switching to: USB
  New source: USB
✅ Source selection works

Device Test Summary:
  5/5 tests passed

================================================================================
                         Test Suite Summary
================================================================================

Living Room WiiM: 5/5 tests passed
Kitchen WiiM: 5/5 tests passed
Bedroom WiiM: 5/5 tests passed

Overall Results:
  Devices Tested:   3
  Total Tests:      15
  Tests Passed:     15
  Success Rate:     100.0%
  Duration:         45.2s

✅ Test report saved to: wiim_test_report_20251117_153045.json
```

#### Test Report

The script generates a JSON report with detailed results:

```json
{
  "timestamp": "2025-11-17T15:30:00",
  "ha_url": "http://homeassistant.local:8123",
  "devices_tested": 3,
  "total_tests": 15,
  "passed_tests": 15,
  "success_rate": 1.0,
  "duration_seconds": 45.2,
  "results": {
    "media_player.living_room_wiim": {
      "device_name": "Living Room WiiM",
      "model": "WiiM Pro Plus",
      "tests": [
        {
          "test": "Device Availability",
          "passed": true,
          "details": { "state": "playing", "available": true }
        },
        {
          "test": "Volume Control",
          "passed": true,
          "details": {
            "original_volume": 0.45,
            "test_volume": 0.35,
            "actual_volume": 0.35,
            "tolerance": 0.05
          }
        }
      ]
    }
  }
}
```

#### CI/CD Integration

The script uses exit codes for automation:

- `0` - All tests passed (100% success rate)
- `1` - Some tests failed or errors occurred
- `130` - Interrupted by user (Ctrl+C)

**GitHub Actions Example:**

```yaml
name: Test WiiM Integration

on:
  schedule:
    - cron: "0 */6 * * *" # Every 6 hours
  workflow_dispatch:

jobs:
  test-real-devices:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install dependencies
        run: pip install requests

      - name: Run device tests
        env:
          HA_TOKEN: ${{ secrets.HA_TOKEN }}
        run: |
          python scripts/test-real-devices.py \
            http://homeassistant.local:8123

      - name: Upload test report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-report
          path: wiim_test_report_*.json
```

#### Continuous Testing

**Run tests every hour:**

```bash
# Create cron job
(crontab -l 2>/dev/null; echo "0 * * * * cd /workspaces/wiim && HA_TOKEN='YOUR_TOKEN' python scripts/test-real-devices.py http://homeassistant.local:8123 >> /var/log/wiim-tests.log 2>&1") | crontab -
```

**Or use systemd timer:**

```ini
# /etc/systemd/system/wiim-test.service
[Unit]
Description=WiiM Device Test Suite

[Service]
Type=oneshot
Environment="HA_TOKEN=your_token_here"
ExecStart=/usr/bin/python3 /workspaces/wiim/scripts/test-real-devices.py http://homeassistant.local:8123
```

```ini
# /etc/systemd/system/wiim-test.timer
[Unit]
Description=Run WiiM tests hourly

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

Enable:

```bash
sudo systemctl enable --now wiim-test.timer
```

#### Troubleshooting

**No devices found:**

- Verify WiiM integration is configured in HA
- Check that devices are powered on and connected
- Verify network connectivity

**Authentication error:**

- Verify your access token is valid
- Check token hasn't expired
- Ensure token has admin permissions

**Connection timeout:**

- Check Home Assistant is running
- Verify firewall allows connections
- Test with `curl -H "Authorization: Bearer TOKEN" http://homeassistant.local:8123/api/`

#### Advanced Usage

**Test specific device types:**

Modify the `discover_devices()` method to filter:

```python
# Only test WiiM Pro Plus devices
wiim_devices = [
    state for state in all_states
    if state.get('attributes', {}).get('device_model') == 'WiiM Pro Plus'
]
```

**Add custom tests:**

Extend the `WiiMRealDeviceTestSuite` class:

```python
def test_preset_playback(self, device: Dict[str, Any]) -> Dict[str, Any]:
    """Test preset playback."""
    entity_id = device['entity_id']

    # Play preset 1
    self.call_service('wiim', 'play_preset', entity_id, preset=1)
    time.sleep(3)

    state = self.get_state(entity_id)
    is_playing = state['state'] == 'playing'

    return {
        'test': 'Preset Playback',
        'passed': is_playing,
        'details': {'preset': 1, 'state': state['state']}
    }
```

#### Performance Testing

Monitor test duration over time to detect performance degradation:

```bash
# Extract duration from reports
jq '.duration_seconds' wiim_test_report_*.json | \
  awk '{sum+=$1; n++} END {print "Avg:", sum/n, "s"}'
```

## Other Scripts

(Add documentation for other scripts here)
