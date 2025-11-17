# WiiM Integration - Real-World Automated Testing Guide

**Date:** 2025-11-17
**Integration Version:** 0.2.27
**Purpose:** Comprehensive guide for automated testing of WiiM integration using HA services and interfaces

## Table of Contents

1. [Overview](#overview)
2. [Testing Approaches](#testing-approaches)
3. [Service-Based Testing](#service-based-testing)
4. [Automation Scripts for Testing](#automation-scripts-for-testing)
5. [REST API Testing](#rest-api-testing)
6. [WebSocket API Testing](#websocket-api-testing)
7. [State Monitoring & Validation](#state-monitoring--validation)
8. [Integration Testing Scenarios](#integration-testing-scenarios)
9. [Multiroom Testing](#multiroom-testing)
10. [Continuous Testing Setup](#continuous-testing-setup)

---

## Overview

The WiiM integration exposes rich testing capabilities through:

- **Standard HA Media Player Services** - playback, volume, source selection, grouping
- **Custom WiiM Services** - presets, EQ, URL playback, device management
- **Entity State Monitoring** - real-time validation of device state
- **REST/WebSocket APIs** - programmatic testing interfaces
- **Automation Scripts** - repeatable test scenarios

### Testing Philosophy

```
┌─────────────────────────────────────────────┐
│   Real-World Testing Approaches             │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  1. Service Call Testing            │   │
│  │     - Developer Tools               │   │
│  │     - Automation Scripts            │   │
│  │     - REST API                      │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  2. State Validation                │   │
│  │     - Entity State Monitoring       │   │
│  │     - Attribute Verification        │   │
│  │     - Event Listening               │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  3. Integration Scenarios           │   │
│  │     - Multiroom Grouping            │   │
│  │     - Playback Workflows            │   │
│  │     - Error Recovery                │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

---

## Testing Approaches

### 1. Manual Testing via Developer Tools

**Location:** Settings → Developer Tools → Services

Quick ad-hoc testing of individual services.

### 2. Automation Scripts

**Location:** Configuration → Automations & Scenes → Scripts

Repeatable test scenarios that can be triggered on demand or scheduled.

### 3. REST API

**Endpoint:** `http://<ha-host>:8123/api/services/<domain>/<service>`

Programmatic testing using curl, Python, or any HTTP client.

### 4. WebSocket API

**Endpoint:** `ws://<ha-host>:8123/api/websocket`

Real-time event monitoring and service calls.

### 5. Python Scripts

**Using:** `homeassistant` Python package or REST API

Comprehensive test suites with assertions and validations.

---

## Service-Based Testing

### Available Services

#### Standard Media Player Services

| Service                             | Purpose          | Test Coverage          |
| ----------------------------------- | ---------------- | ---------------------- |
| `media_player.turn_on`              | Power on device  | Basic connectivity     |
| `media_player.turn_off`             | Power off device | Power management       |
| `media_player.media_play`           | Start playback   | Playback control       |
| `media_player.media_pause`          | Pause playback   | Playback control       |
| `media_player.media_stop`           | Stop playback    | Playback control       |
| `media_player.media_next_track`     | Skip to next     | Track navigation       |
| `media_player.media_previous_track` | Skip to previous | Track navigation       |
| `media_player.media_seek`           | Seek position    | Media position control |
| `media_player.volume_set`           | Set volume       | Volume control         |
| `media_player.volume_mute`          | Mute/unmute      | Volume control         |
| `media_player.volume_up`            | Increase volume  | Volume step control    |
| `media_player.volume_down`          | Decrease volume  | Volume step control    |
| `media_player.select_source`        | Change input     | Source selection       |
| `media_player.shuffle_set`          | Toggle shuffle   | Shuffle mode           |
| `media_player.repeat_set`           | Set repeat mode  | Repeat mode            |
| `media_player.play_media`           | Play URL/preset  | Media playback         |
| `media_player.clear_playlist`       | Clear queue      | Queue management       |
| `media_player.join`                 | Join group       | Multiroom grouping     |
| `media_player.unjoin`               | Leave group      | Multiroom grouping     |

#### Custom WiiM Services

| Service                     | Purpose                | Test Coverage        |
| --------------------------- | ---------------------- | -------------------- |
| `wiim.play_preset`          | Play preset 1-20       | Preset functionality |
| `wiim.play_url`             | Play URL directly      | URL playback         |
| `wiim.play_playlist`        | Play M3U playlist      | Playlist support     |
| `wiim.set_eq`               | Configure EQ           | Audio processing     |
| `wiim.play_notification`    | Play notification      | Notification support |
| `wiim.reboot_device`        | Reboot device          | Device management    |
| `wiim.sync_time`            | Sync device time       | Time sync            |
| `wiim.scan_bluetooth`       | Scan Bluetooth         | Bluetooth scanning   |
| `wiim.set_channel_balance`  | Balance L/R channels   | Audio balance        |
| `wiim.set_spdif_delay`      | SPDIF delay            | Audio timing         |
| `wiim.discover_lms_servers` | Find LMS servers       | LMS integration      |
| `wiim.connect_lms_server`   | Connect to LMS         | LMS integration      |
| `wiim.set_auto_connect_lms` | LMS auto-connect       | LMS settings         |
| `wiim.set_touch_buttons`    | Enable/disable buttons | Hardware control     |

### Example Service Call Tests

#### Test 1: Basic Playback Control

```yaml
# File: scripts/test_wiim_playback.yaml
test_wiim_playback:
  alias: "Test WiiM Playback Control"
  icon: mdi:test-tube
  sequence:
    # 1. Play media
    - service: media_player.media_play
      target:
        entity_id: media_player.wiim_living_room

    # 2. Wait and verify state
    - delay: 2
    - condition: state
      entity_id: media_player.wiim_living_room
      state: "playing"

    # 3. Pause
    - service: media_player.media_pause
      target:
        entity_id: media_player.wiim_living_room

    # 4. Verify paused
    - delay: 2
    - condition: state
      entity_id: media_player.wiim_living_room
      state: "paused"

    # 5. Resume
    - service: media_player.media_play
      target:
        entity_id: media_player.wiim_living_room

    # 6. Stop
    - delay: 2
    - service: media_player.media_stop
      target:
        entity_id: media_player.wiim_living_room
```

#### Test 2: Volume Control

```yaml
test_wiim_volume:
  alias: "Test WiiM Volume Control"
  icon: mdi:volume-high
  sequence:
    # Set to 50%
    - service: media_player.volume_set
      target:
        entity_id: media_player.wiim_living_room
      data:
        volume_level: 0.5

    - delay: 1

    # Verify volume
    - condition: template
      value_template: >
        {{ state_attr('media_player.wiim_living_room', 'volume_level') | float == 0.5 }}

    # Test volume up
    - service: media_player.volume_up
      target:
        entity_id: media_player.wiim_living_room

    - delay: 1

    # Test mute
    - service: media_player.volume_mute
      target:
        entity_id: media_player.wiim_living_room
      data:
        is_volume_muted: true

    - delay: 1

    # Verify muted
    - condition: template
      value_template: >
        {{ state_attr('media_player.wiim_living_room', 'is_volume_muted') == true }}

    # Unmute
    - service: media_player.volume_mute
      target:
        entity_id: media_player.wiim_living_room
      data:
        is_volume_muted: false
```

#### Test 3: Source Selection

```yaml
test_wiim_sources:
  alias: "Test WiiM Source Selection"
  icon: mdi:source-branch
  sequence:
    # Get available sources (stored in attributes)
    # Test switching through sources

    # Select USB
    - service: media_player.select_source
      target:
        entity_id: media_player.wiim_living_room
      data:
        source: "USB"

    - delay: 2

    # Verify USB selected
    - condition: template
      value_template: >
        {{ state_attr('media_player.wiim_living_room', 'source') == 'USB' }}

    # Select Bluetooth
    - service: media_player.select_source
      target:
        entity_id: media_player.wiim_living_room
      data:
        source: "Bluetooth"

    - delay: 2

    # Verify Bluetooth selected
    - condition: template
      value_template: >
        {{ state_attr('media_player.wiim_living_room', 'source') == 'Bluetooth' }}
```

#### Test 4: Preset Playback

```yaml
test_wiim_presets:
  alias: "Test WiiM Presets"
  icon: mdi:numeric
  sequence:
    # Play preset 1
    - service: wiim.play_preset
      target:
        entity_id: media_player.wiim_living_room
      data:
        preset: 1

    - delay: 5

    # Verify playing
    - condition: state
      entity_id: media_player.wiim_living_room
      state: "playing"

    # Play preset 2
    - service: wiim.play_preset
      target:
        entity_id: media_player.wiim_living_room
      data:
        preset: 2

    - delay: 5

    # Stop
    - service: media_player.media_stop
      target:
        entity_id: media_player.wiim_living_room
```

#### Test 5: URL Playback

```yaml
test_wiim_url_playback:
  alias: "Test WiiM URL Playback"
  icon: mdi:web
  sequence:
    # Play internet radio stream
    - service: wiim.play_url
      target:
        entity_id: media_player.wiim_living_room
      data:
        url: "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_two"

    - delay: 5

    # Verify playing
    - condition: state
      entity_id: media_player.wiim_living_room
      state: "playing"

    # Stop
    - service: media_player.media_stop
      target:
        entity_id: media_player.wiim_living_room
```

#### Test 6: EQ Configuration

```yaml
test_wiim_eq:
  alias: "Test WiiM EQ"
  icon: mdi:equalizer
  sequence:
    # Set EQ preset
    - service: wiim.set_eq
      target:
        entity_id: media_player.wiim_living_room
      data:
        preset: "rock"

    - delay: 2

    # Verify EQ preset
    - condition: template
      value_template: >
        {{ state_attr('media_player.wiim_living_room', 'sound_mode') == 'Rock' }}

    # Set custom EQ
    - service: wiim.set_eq
      target:
        entity_id: media_player.wiim_living_room
      data:
        preset: "custom"
        custom_values: [-2, 0, 2, 3, 1, 0, 0, -1, 2, 4]

    - delay: 2

    # Reset to flat
    - service: wiim.set_eq
      target:
        entity_id: media_player.wiim_living_room
      data:
        preset: "flat"
```

---

## Automation Scripts for Testing

### Comprehensive Integration Test Suite

```yaml
# File: scripts/test_wiim_comprehensive.yaml
test_wiim_comprehensive:
  alias: "WiiM Comprehensive Test Suite"
  icon: mdi:test-tube-empty
  sequence:
    # Test 1: Device Availability
    - service: system_log.write
      data:
        message: "WiiM Test: Checking device availability"
        level: info

    - condition: template
      value_template: >
        {{ states('media_player.wiim_living_room') != 'unavailable' }}

    # Test 2: Volume Control
    - service: system_log.write
      data:
        message: "WiiM Test: Testing volume control"
        level: info

    - service: media_player.volume_set
      target:
        entity_id: media_player.wiim_living_room
      data:
        volume_level: 0.3

    - delay: 2

    - condition: template
      value_template: >
        {{ (state_attr('media_player.wiim_living_room', 'volume_level') | float - 0.3) | abs < 0.05 }}

    # Test 3: Playback Control
    - service: system_log.write
      data:
        message: "WiiM Test: Testing playback control"
        level: info

    - service: wiim.play_url
      target:
        entity_id: media_player.wiim_living_room
      data:
        url: "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_two"

    - delay: 5

    - condition: state
      entity_id: media_player.wiim_living_room
      state: "playing"

    # Test 4: Pause/Resume
    - service: system_log.write
      data:
        message: "WiiM Test: Testing pause/resume"
        level: info

    - service: media_player.media_pause
      target:
        entity_id: media_player.wiim_living_room

    - delay: 2

    - condition: state
      entity_id: media_player.wiim_living_room
      state: "paused"

    - service: media_player.media_play
      target:
        entity_id: media_player.wiim_living_room

    - delay: 2

    - condition: state
      entity_id: media_player.wiim_living_room
      state: "playing"

    # Test 5: Mute Control
    - service: system_log.write
      data:
        message: "WiiM Test: Testing mute control"
        level: info

    - service: media_player.volume_mute
      target:
        entity_id: media_player.wiim_living_room
      data:
        is_volume_muted: true

    - delay: 1

    - condition: template
      value_template: >
        {{ state_attr('media_player.wiim_living_room', 'is_volume_muted') == true }}

    - service: media_player.volume_mute
      target:
        entity_id: media_player.wiim_living_room
      data:
        is_volume_muted: false

    # Test 6: Stop Playback
    - service: system_log.write
      data:
        message: "WiiM Test: Testing stop"
        level: info

    - service: media_player.media_stop
      target:
        entity_id: media_player.wiim_living_room

    - delay: 2

    - condition: template
      value_template: >
        {{ states('media_player.wiim_living_room') in ['idle', 'off'] }}

    # All tests passed
    - service: system_log.write
      data:
        message: "WiiM Test: All tests passed!"
        level: info

    - service: persistent_notification.create
      data:
        title: "WiiM Test Suite"
        message: "✅ All tests passed successfully!"
```

---

## REST API Testing

### Using curl

#### Get Entity State

```bash
# Get current state
curl -X GET \
  -H "Authorization: Bearer YOUR_LONG_LIVED_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  http://homeassistant.local:8123/api/states/media_player.wiim_living_room
```

#### Call Service

```bash
# Play media
curl -X POST \
  -H "Authorization: Bearer YOUR_LONG_LIVED_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "media_player.wiim_living_room"}' \
  http://homeassistant.local:8123/api/services/media_player/media_play

# Set volume
curl -X POST \
  -H "Authorization: Bearer YOUR_LONG_LIVED_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "media_player.wiim_living_room", "volume_level": 0.5}' \
  http://homeassistant.local:8123/api/services/media_player/volume_set

# Play preset
curl -X POST \
  -H "Authorization: Bearer YOUR_LONG_LIVED_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "media_player.wiim_living_room", "preset": 1}' \
  http://homeassistant.local:8123/api/services/wiim/play_preset
```

### Python Testing Script

```python
#!/usr/bin/env python3
"""
WiiM Integration Real-World Test Script
Tests WiiM integration using Home Assistant REST API
"""

import requests
import time
import json
from typing import Dict, Any

class WiiMTester:
    def __init__(self, ha_url: str, token: str, entity_id: str):
        self.ha_url = ha_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        self.entity_id = entity_id
        self.test_results = []

    def get_state(self) -> Dict[str, Any]:
        """Get current entity state"""
        url = f"{self.ha_url}/api/states/{self.entity_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def call_service(self, domain: str, service: str, **data) -> bool:
        """Call a Home Assistant service"""
        url = f"{self.ha_url}/api/services/{domain}/{service}"
        payload = {'entity_id': self.entity_id, **data}
        response = requests.post(url, headers=self.headers, json=payload)
        return response.status_code == 200

    def wait_for_state(self, expected_state: str, timeout: int = 10) -> bool:
        """Wait for entity to reach expected state"""
        start = time.time()
        while time.time() - start < timeout:
            state = self.get_state()
            if state['state'] == expected_state:
                return True
            time.sleep(0.5)
        return False

    def test_availability(self) -> bool:
        """Test 1: Device Availability"""
        print("Test 1: Device Availability...")
        try:
            state = self.get_state()
            available = state['state'] != 'unavailable'
            self.test_results.append(('Availability', available))
            print(f"  ✅ Device is available" if available else "  ❌ Device unavailable")
            return available
        except Exception as e:
            print(f"  ❌ Error: {e}")
            self.test_results.append(('Availability', False))
            return False

    def test_volume_control(self) -> bool:
        """Test 2: Volume Control"""
        print("Test 2: Volume Control...")
        try:
            # Set volume to 30%
            self.call_service('media_player', 'volume_set', volume_level=0.3)
            time.sleep(2)

            state = self.get_state()
            volume = state['attributes'].get('volume_level', 0)
            success = abs(volume - 0.3) < 0.05

            self.test_results.append(('Volume Control', success))
            print(f"  ✅ Volume control works (set=0.3, got={volume:.2f})" if success
                  else f"  ❌ Volume mismatch (expected 0.3, got {volume:.2f})")
            return success
        except Exception as e:
            print(f"  ❌ Error: {e}")
            self.test_results.append(('Volume Control', False))
            return False

    def test_playback_control(self) -> bool:
        """Test 3: Playback Control"""
        print("Test 3: Playback Control...")
        try:
            # Play
            self.call_service('media_player', 'media_play')
            play_success = self.wait_for_state('playing', timeout=5)

            if not play_success:
                print("  ❌ Failed to start playback")
                self.test_results.append(('Playback Control', False))
                return False

            # Pause
            self.call_service('media_player', 'media_pause')
            pause_success = self.wait_for_state('paused', timeout=5)

            if not pause_success:
                print("  ❌ Failed to pause")
                self.test_results.append(('Playback Control', False))
                return False

            # Resume
            self.call_service('media_player', 'media_play')
            resume_success = self.wait_for_state('playing', timeout=5)

            success = play_success and pause_success and resume_success
            self.test_results.append(('Playback Control', success))
            print(f"  ✅ Playback control works" if success else "  ❌ Playback control failed")
            return success
        except Exception as e:
            print(f"  ❌ Error: {e}")
            self.test_results.append(('Playback Control', False))
            return False

    def test_mute_control(self) -> bool:
        """Test 4: Mute Control"""
        print("Test 4: Mute Control...")
        try:
            # Mute
            self.call_service('media_player', 'volume_mute', is_volume_muted=True)
            time.sleep(2)

            state = self.get_state()
            is_muted = state['attributes'].get('is_volume_muted', False)

            if not is_muted:
                print("  ❌ Failed to mute")
                self.test_results.append(('Mute Control', False))
                return False

            # Unmute
            self.call_service('media_player', 'volume_mute', is_volume_muted=False)
            time.sleep(2)

            state = self.get_state()
            is_unmuted = not state['attributes'].get('is_volume_muted', True)

            success = is_unmuted
            self.test_results.append(('Mute Control', success))
            print(f"  ✅ Mute control works" if success else "  ❌ Mute control failed")
            return success
        except Exception as e:
            print(f"  ❌ Error: {e}")
            self.test_results.append(('Mute Control', False))
            return False

    def test_source_selection(self) -> bool:
        """Test 5: Source Selection"""
        print("Test 5: Source Selection...")
        try:
            state = self.get_state()
            sources = state['attributes'].get('source_list', [])

            if len(sources) < 2:
                print("  ⚠️  Not enough sources to test")
                self.test_results.append(('Source Selection', True))  # Skip but pass
                return True

            # Select first source
            self.call_service('media_player', 'select_source', source=sources[0])
            time.sleep(2)

            state = self.get_state()
            current_source = state['attributes'].get('source')
            success = current_source == sources[0]

            self.test_results.append(('Source Selection', success))
            print(f"  ✅ Source selection works" if success
                  else f"  ❌ Source mismatch (expected {sources[0]}, got {current_source})")
            return success
        except Exception as e:
            print(f"  ❌ Error: {e}")
            self.test_results.append(('Source Selection', False))
            return False

    def test_preset_playback(self) -> bool:
        """Test 6: Preset Playback"""
        print("Test 6: Preset Playback...")
        try:
            # Play preset 1
            self.call_service('wiim', 'play_preset', preset=1)
            time.sleep(5)

            state = self.get_state()
            is_playing = state['state'] == 'playing'

            # Stop
            self.call_service('media_player', 'media_stop')
            time.sleep(2)

            self.test_results.append(('Preset Playback', is_playing))
            print(f"  ✅ Preset playback works" if is_playing
                  else "  ❌ Preset did not start playing")
            return is_playing
        except Exception as e:
            print(f"  ❌ Error: {e}")
            self.test_results.append(('Preset Playback', False))
            return False

    def run_all_tests(self):
        """Run complete test suite"""
        print("=" * 60)
        print("WiiM Integration Real-World Test Suite")
        print("=" * 60)
        print(f"Entity: {self.entity_id}")
        print(f"HA URL: {self.ha_url}")
        print("=" * 60)
        print()

        # Run tests
        self.test_availability()
        print()
        self.test_volume_control()
        print()
        self.test_playback_control()
        print()
        self.test_mute_control()
        print()
        self.test_source_selection()
        print()
        self.test_preset_playback()
        print()

        # Summary
        print("=" * 60)
        print("Test Results Summary")
        print("=" * 60)
        passed = sum(1 for _, result in self.test_results if result)
        total = len(self.test_results)

        for test_name, result in self.test_results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name:.<40} {status}")

        print("=" * 60)
        print(f"Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        print("=" * 60)

        return passed == total


if __name__ == '__main__':
    # Configuration
    HA_URL = 'http://homeassistant.local:8123'
    TOKEN = 'YOUR_LONG_LIVED_ACCESS_TOKEN'
    ENTITY_ID = 'media_player.wiim_living_room'

    # Run tests
    tester = WiiMTester(HA_URL, TOKEN, ENTITY_ID)
    success = tester.run_all_tests()

    exit(0 if success else 1)
```

### Usage

```bash
# Install requests
pip install requests

# Edit script with your credentials
# HA_URL = 'http://homeassistant.local:8123'
# TOKEN = 'YOUR_LONG_LIVED_ACCESS_TOKEN'
# ENTITY_ID = 'media_player.wiim_living_room'

# Run tests
python test_wiim_integration.py
```

---

## WebSocket API Testing

### Python WebSocket Test Script

```python
#!/usr/bin/env python3
"""
WiiM WebSocket API Test Script
Monitors entity states and triggers service calls via WebSocket
"""

import asyncio
import aiohttp
import json

class WiiMWebSocketTester:
    def __init__(self, url: str, token: str, entity_id: str):
        self.url = url
        self.token = token
        self.entity_id = entity_id
        self.message_id = 1
        self.ws = None
        self.state_changes = []

    async def connect(self):
        """Connect to Home Assistant WebSocket API"""
        session = aiohttp.ClientSession()
        self.ws = await session.ws_connect(self.url)

        # Receive auth required
        msg = await self.ws.receive_json()
        print(f"Connected: {msg}")

        # Send auth
        await self.ws.send_json({
            'type': 'auth',
            'access_token': self.token
        })

        # Receive auth ok
        msg = await self.ws.receive_json()
        if msg['type'] != 'auth_ok':
            raise Exception(f"Auth failed: {msg}")
        print("Authenticated")

    async def subscribe_events(self):
        """Subscribe to state_changed events"""
        await self.ws.send_json({
            'id': self.message_id,
            'type': 'subscribe_events',
            'event_type': 'state_changed'
        })
        self.message_id += 1

        # Wait for result
        msg = await self.ws.receive_json()
        print(f"Subscribed to events: {msg}")

    async def call_service(self, domain: str, service: str, **data):
        """Call a service"""
        await self.ws.send_json({
            'id': self.message_id,
            'type': 'call_service',
            'domain': domain,
            'service': service,
            'service_data': {
                'entity_id': self.entity_id,
                **data
            }
        })
        self.message_id += 1

    async def listen_for_changes(self, duration: int = 30):
        """Listen for state changes"""
        print(f"Listening for state changes for {duration} seconds...")
        end_time = asyncio.get_event_loop().time() + duration

        while asyncio.get_event_loop().time() < end_time:
            try:
                msg = await asyncio.wait_for(self.ws.receive_json(), timeout=1.0)

                if msg.get('type') == 'event':
                    event = msg['event']
                    if event['event_type'] == 'state_changed':
                        data = event['data']
                        entity_id = data['entity_id']

                        if entity_id == self.entity_id:
                            old_state = data['old_state']['state'] if data['old_state'] else None
                            new_state = data['new_state']['state']
                            print(f"State changed: {old_state} → {new_state}")
                            self.state_changes.append((old_state, new_state))

            except asyncio.TimeoutError:
                pass

    async def run_test_sequence(self):
        """Run automated test sequence"""
        print("\n=== Starting Test Sequence ===\n")

        # Test 1: Volume
        print("Test: Set volume to 0.3")
        await self.call_service('media_player', 'volume_set', volume_level=0.3)
        await asyncio.sleep(2)

        # Test 2: Play
        print("Test: Start playback")
        await self.call_service('media_player', 'media_play')
        await asyncio.sleep(5)

        # Test 3: Pause
        print("Test: Pause playback")
        await self.call_service('media_player', 'media_pause')
        await asyncio.sleep(2)

        # Test 4: Resume
        print("Test: Resume playback")
        await self.call_service('media_player', 'media_play')
        await asyncio.sleep(2)

        # Test 5: Stop
        print("Test: Stop playback")
        await self.call_service('media_player', 'media_stop')
        await asyncio.sleep(2)

        print("\n=== Test Sequence Complete ===\n")

    async def run(self):
        """Run complete WebSocket test"""
        await self.connect()
        await self.subscribe_events()

        # Create tasks for listening and testing
        listen_task = asyncio.create_task(self.listen_for_changes(duration=30))

        # Wait a bit then run tests
        await asyncio.sleep(2)
        await self.run_test_sequence()

        # Wait for listening to complete
        await listen_task

        # Summary
        print(f"\nCaptured {len(self.state_changes)} state changes:")
        for old, new in self.state_changes:
            print(f"  {old} → {new}")


async def main():
    WS_URL = 'ws://homeassistant.local:8123/api/websocket'
    TOKEN = 'YOUR_LONG_LIVED_ACCESS_TOKEN'
    ENTITY_ID = 'media_player.wiim_living_room'

    tester = WiiMWebSocketTester(WS_URL, TOKEN, ENTITY_ID)
    await tester.run()


if __name__ == '__main__':
    asyncio.run(main())
```

---

## State Monitoring & Validation

### Entity Attributes to Monitor

```yaml
# Key attributes for validation
media_player.wiim_living_room:
  state: playing | paused | idle | off | unavailable
  attributes:
    volume_level: 0.0 - 1.0
    is_volume_muted: true | false
    media_content_type: music
    media_title: "Track title"
    media_artist: "Artist name"
    media_album_name: "Album name"
    media_duration: 180 (seconds)
    media_position: 45 (seconds)
    source: "USB" | "Bluetooth" | "AirPlay" | etc.
    source_list: ["USB", "Bluetooth", "AirPlay", ...]
    sound_mode: "Rock" | "Jazz" | "Flat" | etc.
    sound_mode_list: ["Flat", "Classical", "Jazz", ...]
    shuffle: true | false
    repeat: "off" | "all" | "one"
    group_members: ["media_player.kitchen", ...]
    group_role: "master" | "slave" | "solo"
    device_model: "WiiM Pro Plus"
    firmware_version: "4.8.618780"
    ip_address: "192.168.1.100"
```

### Validation Script

```python
def validate_entity_state(hass, entity_id: str) -> dict:
    """Validate entity state and attributes"""
    state = hass.states.get(entity_id)

    checks = {
        'entity_exists': state is not None,
        'is_available': state.state != 'unavailable' if state else False,
        'has_volume': 'volume_level' in state.attributes if state else False,
        'volume_valid': 0 <= state.attributes.get('volume_level', -1) <= 1 if state else False,
        'has_source': 'source' in state.attributes if state else False,
        'has_source_list': 'source_list' in state.attributes if state else False,
        'has_group_info': 'group_role' in state.attributes if state else False,
    }

    return checks
```

---

## Integration Testing Scenarios

### Scenario 1: End-to-End Playback Workflow

```yaml
test_e2e_playback:
  alias: "E2E: Complete Playback Workflow"
  sequence:
    # 1. Power on
    - service: media_player.turn_on
      target:
        entity_id: media_player.wiim_living_room
    - delay: 2

    # 2. Set volume
    - service: media_player.volume_set
      target:
        entity_id: media_player.wiim_living_room
      data:
        volume_level: 0.4

    # 3. Play URL
    - service: wiim.play_url
      target:
        entity_id: media_player.wiim_living_room
      data:
        url: "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_two"
    - delay: 10

    # 4. Verify playing
    - condition: state
      entity_id: media_player.wiim_living_room
      state: "playing"

    # 5. Adjust volume during playback
    - service: media_player.volume_set
      target:
        entity_id: media_player.wiim_living_room
      data:
        volume_level: 0.6
    - delay: 5

    # 6. Stop
    - service: media_player.media_stop
      target:
        entity_id: media_player.wiim_living_room

    # 7. Verify stopped
    - delay: 2
    - condition: template
      value_template: >
        {{ states('media_player.wiim_living_room') in ['idle', 'off'] }}
```

### Scenario 2: Source Switching

```yaml
test_source_switching:
  alias: "Test: Source Switching Workflow"
  sequence:
    # Switch to USB
    - service: media_player.select_source
      target:
        entity_id: media_player.wiim_living_room
      data:
        source: "USB"
    - delay: 3
    - condition: template
      value_template: >
        {{ state_attr('media_player.wiim_living_room', 'source') == 'USB' }}

    # Switch to Bluetooth
    - service: media_player.select_source
      target:
        entity_id: media_player.wiim_living_room
      data:
        source: "Bluetooth"
    - delay: 3
    - condition: template
      value_template: >
        {{ state_attr('media_player.wiim_living_room', 'source') == 'Bluetooth' }}

    # Switch to Line-In
    - service: media_player.select_source
      target:
        entity_id: media_player.wiim_living_room
      data:
        source: "Line-In"
    - delay: 3
    - condition: template
      value_template: >
        {{ state_attr('media_player.wiim_living_room', 'source') == 'Line-In' }}
```

### Scenario 3: EQ Preset Cycling

```yaml
test_eq_presets:
  alias: "Test: EQ Preset Cycling"
  sequence:
    # Rock
    - service: wiim.set_eq
      target:
        entity_id: media_player.wiim_living_room
      data:
        preset: "rock"
    - delay: 2

    # Jazz
    - service: wiim.set_eq
      target:
        entity_id: media_player.wiim_living_room
      data:
        preset: "jazz"
    - delay: 2

    # Classical
    - service: wiim.set_eq
      target:
        entity_id: media_player.wiim_living_room
      data:
        preset: "classical"
    - delay: 2

    # Reset to Flat
    - service: wiim.set_eq
      target:
        entity_id: media_player.wiim_living_room
      data:
        preset: "flat"
```

---

## Multiroom Testing

### Test Group Formation

```yaml
test_multiroom_grouping:
  alias: "Test: Multiroom Grouping"
  sequence:
    # 1. Verify all speakers are solo
    - condition: template
      value_template: >
        {{ state_attr('media_player.wiim_living_room', 'group_role') == 'solo' }}
    - condition: template
      value_template: >
        {{ state_attr('media_player.wiim_kitchen', 'group_role') == 'solo' }}

    # 2. Create group
    - service: media_player.join
      target:
        entity_id: media_player.wiim_living_room
      data:
        group_members:
          - media_player.wiim_kitchen
          - media_player.wiim_bedroom

    - delay: 5

    # 3. Verify group formed
    - condition: template
      value_template: >
        {{ state_attr('media_player.wiim_living_room', 'group_role') == 'master' }}
    - condition: template
      value_template: >
        {{ state_attr('media_player.wiim_kitchen', 'group_role') == 'slave' }}

    # 4. Play on group
    - service: wiim.play_preset
      target:
        entity_id: media_player.wiim_living_room
      data:
        preset: 1

    - delay: 10

    # 5. Verify all playing
    - condition: state
      entity_id: media_player.wiim_living_room
      state: "playing"
    - condition: state
      entity_id: media_player.wiim_kitchen
      state: "playing"

    # 6. Ungroup
    - service: media_player.unjoin
      target:
        entity_id: media_player.wiim_kitchen

    - delay: 5

    # 7. Verify ungrouped
    - condition: template
      value_template: >
        {{ state_attr('media_player.wiim_kitchen', 'group_role') == 'solo' }}
```

### Test Group Volume Control

```yaml
test_group_volume:
  alias: "Test: Group Volume Control"
  sequence:
    # 1. Create group
    - service: media_player.join
      target:
        entity_id: media_player.wiim_living_room
      data:
        group_members:
          - media_player.wiim_kitchen

    - delay: 5

    # 2. Control via group coordinator entity
    - service: media_player.volume_set
      target:
        entity_id: media_player.wiim_living_room_group_coordinator
      data:
        volume_level: 0.5

    - delay: 2

    # 3. Verify volumes synchronized
    - condition: template
      value_template: >
        {{
          (state_attr('media_player.wiim_living_room', 'volume_level') | float - 0.5) | abs < 0.05
          and
          (state_attr('media_player.wiim_kitchen', 'volume_level') | float - 0.5) | abs < 0.05
        }}

    # 4. Ungroup
    - service: media_player.unjoin
      target:
        entity_id:
          - media_player.wiim_living_room
          - media_player.wiim_kitchen
```

---

## Continuous Testing Setup

### Automated Nightly Tests

```yaml
# File: automations/test_wiim_nightly.yaml
automation:
  - id: wiim_nightly_test
    alias: "WiiM: Nightly Integration Test"
    trigger:
      - platform: time
        at: "03:00:00"
    action:
      # Run comprehensive test suite
      - service: script.test_wiim_comprehensive

      # Check if tests passed by looking for notification
      - wait_template: >
          {{ state_attr('persistent_notification.wiim_test_suite', 'message')
             is not none }}
        timeout: 300

      # Send notification with results
      - service: notify.admin
        data:
          title: "WiiM Nightly Test Results"
          message: >
            {% if '✅' in state_attr('persistent_notification.wiim_test_suite', 'message') %}
              All WiiM integration tests passed!
            {% else %}
              ⚠️ Some WiiM tests failed. Check logs.
            {% endif %}
```

### Health Check Automation

```yaml
automation:
  - id: wiim_health_check
    alias: "WiiM: Hourly Health Check"
    trigger:
      - platform: time_pattern
        minutes: "/60"
    action:
      # Check device availability
      - condition: template
        value_template: >
          {{ states('media_player.wiim_living_room') != 'unavailable' }}

      # Log healthy status
      - service: system_log.write
        data:
          message: "WiiM health check: Device available"
          level: info

      # If unavailable, send alert
      - choose:
          - conditions:
              - condition: template
                value_template: >
                  {{ states('media_player.wiim_living_room') == 'unavailable' }}
            sequence:
              - service: notify.admin
                data:
                  title: "WiiM Device Unavailable"
                  message: "Living room WiiM speaker is not responding"
```

---

## Summary

### Testing Capabilities Matrix

| Test Type              | Method                   | Automation | Continuous |
| ---------------------- | ------------------------ | ---------- | ---------- |
| **Service Calls**      | Developer Tools, Scripts | ✅         | ✅         |
| **State Validation**   | Templates, Scripts       | ✅         | ✅         |
| **Playback Control**   | Services                 | ✅         | ✅         |
| **Volume Control**     | Services                 | ✅         | ✅         |
| **Source Selection**   | Services                 | ✅         | ✅         |
| **Multiroom Grouping** | Services                 | ✅         | ✅         |
| **Preset Playback**    | WiiM Services            | ✅         | ✅         |
| **EQ Control**         | WiiM Services            | ✅         | ✅         |
| **REST API**           | Python, curl             | ✅         | ✅         |
| **WebSocket API**      | Python                   | ✅         | ✅         |

### Key Takeaways

1. **Rich Service Interface** - 30+ services available for comprehensive testing
2. **State Monitoring** - Real-time entity state validation
3. **Multiple APIs** - REST, WebSocket, Python for programmatic access
4. **Automation Scripts** - Repeatable test scenarios
5. **Continuous Testing** - Schedule automated tests
6. **Multiroom Testing** - Group formation and synchronization

### Next Steps

1. Set up long-lived access token for API testing
2. Create test scripts based on your specific use cases
3. Schedule automated nightly tests
4. Monitor test results and device health
5. Extend test coverage as needed

---

## Resources

- **WiiM Integration Docs:** `/docs/user-guide.md`
- **Automation Cookbook:** `/docs/automation-cookbook.md`
- **Services:** `/custom_components/wiim/services.yaml`
- **HA REST API:** https://developers.home-assistant.io/docs/api/rest/
- **HA WebSocket API:** https://developers.home-assistant.io/docs/api/websocket/
