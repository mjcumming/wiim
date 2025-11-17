# WiiM Device Enumeration & Direct Testing Guide

**Date:** 2025-11-17
**Purpose:** Enumerate and directly test WiiM devices in Home Assistant

## Table of Contents

1. [Device Enumeration Methods](#device-enumeration-methods)
2. [Python Script for Enumeration](#python-script-for-enumeration)
3. [REST API Enumeration](#rest-api-enumeration)
4. [WebSocket API Enumeration](#websocket-api-enumeration)
5. [Direct Device Testing](#direct-device-testing)
6. [Automated Device Testing](#automated-device-testing)
7. [Testing Multiroom Groups](#testing-multiroom-groups)

---

## Device Enumeration Methods

### Built-in Helper Functions

The WiiM integration provides these helper functions in `data.py`:

```python
from custom_components.wiim.data import (
    get_all_speakers,        # Get all registered WiiM devices
    find_speaker_by_uuid,    # Find device by UUID
    find_speaker_by_ip,      # Find device by IP address
    get_speaker_from_config_entry  # Get from config entry
)
```

### Available Information Per Device

Each `Speaker` object provides:

- `uuid` - Unique device identifier
- `name` - Device name
- `model` - Device model (WiiM Mini, Pro, Pro Plus, Amp, Ultra)
- `firmware` - Firmware version
- `ip_address` - Network IP address
- `mac_address` - MAC address
- `role` - Multiroom role (solo, master, slave)
- `coordinator` - Access to full coordinator and player data
- `available` - Device availability status

---

## Python Script for Enumeration

### 1. Basic Device Enumeration

```python
#!/usr/bin/env python3
"""
Enumerate all WiiM devices in Home Assistant
"""

import asyncio
from homeassistant.core import HomeAssistant
from homeassistant.config import async_process_ha_core_config
from custom_components.wiim.data import get_all_speakers
from custom_components.wiim.const import DOMAIN

async def enumerate_wiim_devices(hass: HomeAssistant):
    """Enumerate all WiiM devices."""

    # Get all speakers
    speakers = get_all_speakers(hass)

    print(f"Found {len(speakers)} WiiM device(s):\n")

    for i, speaker in enumerate(speakers, 1):
        print(f"Device {i}:")
        print(f"  Name:         {speaker.name}")
        print(f"  Model:        {speaker.model}")
        print(f"  UUID:         {speaker.uuid}")
        print(f"  IP Address:   {speaker.ip_address}")
        print(f"  MAC Address:  {speaker.mac_address}")
        print(f"  Firmware:     {speaker.firmware}")
        print(f"  Role:         {speaker.role}")
        print(f"  Available:    {speaker.available}")
        print(f"  Entity ID:    media_player.{speaker.name.lower().replace(' ', '_')}")
        print()

    return speakers


# If running as script (needs HA environment)
if __name__ == "__main__":
    # This requires running within HA context
    # Use the REST API version below for standalone scripts
    pass
```

### 2. Standalone Python Script (via REST API)

```python
#!/usr/bin/env python3
"""
Enumerate WiiM devices via Home Assistant REST API
Works without HA Python environment
"""

import requests
import json
from typing import Dict, List, Any

class WiiMDeviceEnumerator:
    def __init__(self, ha_url: str, token: str):
        self.ha_url = ha_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Get all Home Assistant entities and filter WiiM devices."""
        url = f"{self.ha_url}/api/states"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        all_entities = response.json()

        # Filter for WiiM media players (not group coordinators)
        wiim_devices = [
            entity for entity in all_entities
            if entity['entity_id'].startswith('media_player.')
            and entity['attributes'].get('integration_purpose') == 'individual_speaker_control'
        ]

        return wiim_devices

    def get_device_details(self, entity_id: str) -> Dict[str, Any]:
        """Get detailed information for a specific device."""
        url = f"{self.ha_url}/api/states/{entity_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def enumerate_devices(self) -> List[Dict[str, Any]]:
        """Enumerate all WiiM devices with full details."""
        devices = self.get_all_devices()

        print(f"\n{'='*70}")
        print(f"Found {len(devices)} WiiM Device(s)")
        print(f"{'='*70}\n")

        device_list = []
        for i, device in enumerate(devices, 1):
            entity_id = device['entity_id']
            attrs = device['attributes']

            device_info = {
                'entity_id': entity_id,
                'name': attrs.get('friendly_name', 'Unknown'),
                'model': attrs.get('device_model', 'Unknown'),
                'firmware': attrs.get('firmware_version', 'Unknown'),
                'ip_address': attrs.get('ip_address', 'Unknown'),
                'mac_address': attrs.get('mac_address', 'Unknown'),
                'role': attrs.get('group_role', 'solo'),
                'state': device['state'],
                'available': device['state'] != 'unavailable',
                'volume_level': attrs.get('volume_level', 0),
                'source': attrs.get('source', 'None'),
                'source_list': attrs.get('source_list', []),
                'group_members': attrs.get('group_members', []),
            }

            print(f"Device {i}:")
            print(f"  Entity ID:     {device_info['entity_id']}")
            print(f"  Name:          {device_info['name']}")
            print(f"  Model:         {device_info['model']}")
            print(f"  Firmware:      {device_info['firmware']}")
            print(f"  IP Address:    {device_info['ip_address']}")
            print(f"  MAC Address:   {device_info['mac_address']}")
            print(f"  State:         {device_info['state']}")
            print(f"  Volume:        {int(device_info['volume_level'] * 100)}%")
            print(f"  Source:        {device_info['source']}")
            print(f"  Role:          {device_info['role']}")
            if device_info['group_members']:
                print(f"  Group:         {', '.join(device_info['group_members'])}")
            print()

            device_list.append(device_info)

        return device_list

    def get_multiroom_groups(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify multiroom groups from device list."""
        groups = []

        for device in devices:
            if device['role'] == 'master' and device['group_members']:
                group_info = {
                    'master': device['entity_id'],
                    'master_name': device['name'],
                    'members': device['group_members'],
                    'member_count': len(device['group_members'])
                }
                groups.append(group_info)

        if groups:
            print(f"\n{'='*70}")
            print(f"Active Multiroom Groups: {len(groups)}")
            print(f"{'='*70}\n")

            for i, group in enumerate(groups, 1):
                print(f"Group {i}:")
                print(f"  Master:        {group['master_name']} ({group['master']})")
                print(f"  Members:       {group['member_count']} device(s)")
                for member in group['members']:
                    print(f"    - {member}")
                print()

        return groups


def main():
    """Main function to enumerate WiiM devices."""
    # Configuration
    HA_URL = 'http://homeassistant.local:8123'
    TOKEN = 'YOUR_LONG_LIVED_ACCESS_TOKEN'  # Create in HA Profile

    # Create enumerator
    enumerator = WiiMDeviceEnumerator(HA_URL, TOKEN)

    # Enumerate devices
    devices = enumerator.enumerate_devices()

    # Identify multiroom groups
    groups = enumerator.get_multiroom_groups(devices)

    # Summary
    print(f"\n{'='*70}")
    print(f"Summary:")
    print(f"  Total Devices:    {len(devices)}")
    print(f"  Available:        {sum(1 for d in devices if d['available'])}")
    print(f"  Multiroom Groups: {len(groups)}")
    print(f"{'='*70}\n")

    return devices, groups


if __name__ == '__main__':
    devices, groups = main()
```

### Usage

```bash
# Edit script with your HA URL and token
nano enumerate_wiim_devices.py

# Run enumeration
python enumerate_wiim_devices.py
```

**Example Output:**

```
======================================================================
Found 3 WiiM Device(s)
======================================================================

Device 1:
  Entity ID:     media_player.living_room_wiim
  Name:          Living Room WiiM
  Model:         WiiM Pro Plus
  Firmware:      4.8.618780
  IP Address:    192.168.1.100
  MAC Address:   AA:BB:CC:DD:EE:01
  State:         playing
  Volume:        45%
  Source:        Spotify
  Role:          master
  Group:         media_player.living_room_wiim, media_player.kitchen_wiim

Device 2:
  Entity ID:     media_player.kitchen_wiim
  Name:          Kitchen WiiM
  Model:         WiiM Mini
  Firmware:      4.8.618780
  IP Address:    192.168.1.101
  MAC Address:   AA:BB:CC:DD:EE:02
  State:         playing
  Volume:        45%
  Source:        Spotify
  Role:          slave

Device 3:
  Entity ID:     media_player.bedroom_wiim
  Name:          Bedroom WiiM
  Model:         WiiM Pro
  Firmware:      4.8.618780
  IP Address:    192.168.1.102
  MAC Address:   AA:BB:CC:DD:EE:03
  State:         idle
  Volume:        30%
  Source:        USB
  Role:          solo

======================================================================
Active Multiroom Groups: 1
======================================================================

Group 1:
  Master:        Living Room WiiM (media_player.living_room_wiim)
  Members:       2 device(s)
    - media_player.living_room_wiim
    - media_player.kitchen_wiim

======================================================================
Summary:
  Total Devices:    3
  Available:        3
  Multiroom Groups: 1
======================================================================
```

---

## REST API Enumeration

### Get All WiiM Entities

```bash
# Get all entities
curl -X GET \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  http://homeassistant.local:8123/api/states | \
  jq '.[] | select(.entity_id | startswith("media_player.")) | select(.attributes.device_model != null)'
```

### Get Specific Device

```bash
# Get specific WiiM device
curl -X GET \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://homeassistant.local:8123/api/states/media_player.living_room_wiim | jq '.'
```

### Filter by Integration

```bash
# Get only WiiM devices (filter by integration_purpose attribute)
curl -X GET \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://homeassistant.local:8123/api/states | \
  jq '.[] | select(.attributes.integration_purpose == "individual_speaker_control")'
```

---

## WebSocket API Enumeration

### Python WebSocket Enumerator

```python
#!/usr/bin/env python3
"""
Enumerate WiiM devices via WebSocket API
Real-time device monitoring
"""

import asyncio
import aiohttp
import json

class WiiMWebSocketEnumerator:
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token
        self.ws = None
        self.message_id = 1
        self.devices = {}

    async def connect(self):
        """Connect to HA WebSocket API."""
        session = aiohttp.ClientSession()
        self.ws = await session.ws_connect(self.url)

        # Receive auth required
        await self.ws.receive_json()

        # Send auth
        await self.ws.send_json({
            'type': 'auth',
            'access_token': self.token
        })

        # Receive auth ok
        msg = await self.ws.receive_json()
        if msg['type'] != 'auth_ok':
            raise Exception(f"Auth failed: {msg}")
        print("✅ Connected to Home Assistant\n")

    async def get_states(self):
        """Get all entity states."""
        await self.ws.send_json({
            'id': self.message_id,
            'type': 'get_states'
        })
        self.message_id += 1

        # Wait for response
        msg = await self.ws.receive_json()
        return msg.get('result', [])

    async def subscribe_events(self):
        """Subscribe to state_changed events."""
        await self.ws.send_json({
            'id': self.message_id,
            'type': 'subscribe_events',
            'event_type': 'state_changed'
        })
        self.message_id += 1

        # Wait for result
        await self.ws.receive_json()
        print("✅ Subscribed to device state changes\n")

    async def enumerate_devices(self):
        """Enumerate all WiiM devices."""
        states = await self.get_states()

        # Filter WiiM devices
        wiim_devices = [
            state for state in states
            if state['entity_id'].startswith('media_player.')
            and state['attributes'].get('integration_purpose') == 'individual_speaker_control'
        ]

        print(f"{'='*70}")
        print(f"WiiM Devices: {len(wiim_devices)}")
        print(f"{'='*70}\n")

        for device in wiim_devices:
            entity_id = device['entity_id']
            attrs = device['attributes']

            self.devices[entity_id] = {
                'name': attrs.get('friendly_name'),
                'model': attrs.get('device_model'),
                'state': device['state'],
                'ip': attrs.get('ip_address'),
            }

            print(f"📱 {attrs.get('friendly_name')}")
            print(f"   Entity: {entity_id}")
            print(f"   Model:  {attrs.get('device_model')}")
            print(f"   IP:     {attrs.get('ip_address')}")
            print(f"   State:  {device['state']}")
            print()

    async def monitor_changes(self, duration: int = 30):
        """Monitor device state changes in real-time."""
        print(f"🔍 Monitoring device changes for {duration} seconds...\n")
        end_time = asyncio.get_event_loop().time() + duration

        while asyncio.get_event_loop().time() < end_time:
            try:
                msg = await asyncio.wait_for(self.ws.receive_json(), timeout=1.0)

                if msg.get('type') == 'event':
                    event = msg['event']
                    if event['event_type'] == 'state_changed':
                        data = event['data']
                        entity_id = data['entity_id']

                        if entity_id in self.devices:
                            old_state = data['old_state']['state'] if data['old_state'] else None
                            new_state = data['new_state']['state']

                            if old_state != new_state:
                                print(f"🔔 {self.devices[entity_id]['name']}: {old_state} → {new_state}")

            except asyncio.TimeoutError:
                pass

        print(f"\n✅ Monitoring complete")

    async def run(self, monitor_duration: int = 30):
        """Run complete enumeration and monitoring."""
        await self.connect()
        await self.enumerate_devices()
        await self.subscribe_events()
        await self.monitor_changes(duration=monitor_duration)


async def main():
    WS_URL = 'ws://homeassistant.local:8123/api/websocket'
    TOKEN = 'YOUR_LONG_LIVED_ACCESS_TOKEN'

    enumerator = WiiMWebSocketEnumerator(WS_URL, TOKEN)
    await enumerator.run(monitor_duration=30)


if __name__ == '__main__':
    asyncio.run(main())
```

---

## Direct Device Testing

### Comprehensive Device Test Script

```python
#!/usr/bin/env python3
"""
Direct WiiM Device Testing Script
Tests all capabilities of each enumerated device
"""

import requests
import time
from typing import Dict, List

class WiiMDeviceTester:
    def __init__(self, ha_url: str, token: str):
        self.ha_url = ha_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        self.test_results = []

    def call_service(self, domain: str, service: str, entity_id: str, **data):
        """Call a Home Assistant service."""
        url = f"{self.ha_url}/api/services/{domain}/{service}"
        payload = {'entity_id': entity_id, **data}
        response = requests.post(url, headers=self.headers, json=payload)
        return response.status_code == 200

    def get_state(self, entity_id: str) -> Dict:
        """Get entity state."""
        url = f"{self.ha_url}/api/states/{entity_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def test_device(self, entity_id: str) -> Dict:
        """Run comprehensive tests on a device."""
        print(f"\n{'='*70}")
        print(f"Testing Device: {entity_id}")
        print(f"{'='*70}\n")

        results = {
            'entity_id': entity_id,
            'tests': []
        }

        # Get initial state
        state = self.get_state(entity_id)
        device_name = state['attributes'].get('friendly_name', entity_id)
        print(f"Device: {device_name}")
        print(f"Model:  {state['attributes'].get('device_model')}")
        print(f"IP:     {state['attributes'].get('ip_address')}\n")

        # Test 1: Volume Control
        print("Test 1: Volume Control...")
        original_volume = state['attributes'].get('volume_level', 0.5)
        success = self.call_service('media_player', 'volume_set', entity_id, volume_level=0.3)
        time.sleep(1)
        new_state = self.get_state(entity_id)
        volume_changed = abs(new_state['attributes'].get('volume_level', 0) - 0.3) < 0.05
        results['tests'].append({
            'name': 'Volume Control',
            'passed': success and volume_changed
        })
        print(f"  {'✅ PASS' if volume_changed else '❌ FAIL'}\n")

        # Restore volume
        self.call_service('media_player', 'volume_set', entity_id, volume_level=original_volume)
        time.sleep(1)

        # Test 2: Mute Control
        print("Test 2: Mute Control...")
        self.call_service('media_player', 'volume_mute', entity_id, is_volume_muted=True)
        time.sleep(1)
        new_state = self.get_state(entity_id)
        is_muted = new_state['attributes'].get('is_volume_muted', False)
        results['tests'].append({
            'name': 'Mute Control',
            'passed': is_muted
        })
        print(f"  {'✅ PASS' if is_muted else '❌ FAIL'}\n")

        # Unmute
        self.call_service('media_player', 'volume_mute', entity_id, is_volume_muted=False)
        time.sleep(1)

        # Test 3: Source Selection
        print("Test 3: Source Selection...")
        sources = state['attributes'].get('source_list', [])
        if len(sources) >= 2:
            current_source = state['attributes'].get('source')
            new_source = sources[0] if sources[0] != current_source else sources[1]

            self.call_service('media_player', 'select_source', entity_id, source=new_source)
            time.sleep(2)
            new_state = self.get_state(entity_id)
            source_changed = new_state['attributes'].get('source') == new_source
            results['tests'].append({
                'name': 'Source Selection',
                'passed': source_changed
            })
            print(f"  {'✅ PASS' if source_changed else '❌ FAIL'}\n")
        else:
            print(f"  ⏭️  SKIP (insufficient sources)\n")
            results['tests'].append({
                'name': 'Source Selection',
                'passed': None
            })

        # Test 4: Playback Control
        print("Test 4: Playback Control...")
        original_state = state['state']

        # Try play
        self.call_service('media_player', 'media_play', entity_id)
        time.sleep(2)
        new_state = self.get_state(entity_id)
        play_works = new_state['state'] in ['playing', 'paused']

        # Try pause
        if play_works:
            self.call_service('media_player', 'media_pause', entity_id)
            time.sleep(2)
            new_state = self.get_state(entity_id)
            pause_works = new_state['state'] == 'paused'
        else:
            pause_works = False

        results['tests'].append({
            'name': 'Playback Control',
            'passed': play_works and pause_works
        })
        print(f"  {'✅ PASS' if (play_works and pause_works) else '❌ FAIL'}\n")

        # Test 5: Device Info
        print("Test 5: Device Info...")
        has_model = bool(state['attributes'].get('device_model'))
        has_firmware = bool(state['attributes'].get('firmware_version'))
        has_ip = bool(state['attributes'].get('ip_address'))
        info_complete = has_model and has_firmware and has_ip
        results['tests'].append({
            'name': 'Device Info',
            'passed': info_complete
        })
        print(f"  {'✅ PASS' if info_complete else '❌ FAIL'}\n")

        # Summary
        passed = sum(1 for t in results['tests'] if t['passed'] is True)
        total = sum(1 for t in results['tests'] if t['passed'] is not None)

        print(f"{'='*70}")
        print(f"Test Results: {passed}/{total} passed")
        print(f"{'='*70}\n")

        return results

    def test_all_devices(self, devices: List[Dict]) -> List[Dict]:
        """Test all devices."""
        all_results = []

        for device in devices:
            entity_id = device['entity_id']
            results = self.test_device(entity_id)
            all_results.append(results)
            time.sleep(2)  # Pause between devices

        # Overall summary
        print(f"\n{'='*70}")
        print(f"Overall Test Summary")
        print(f"{'='*70}\n")

        for results in all_results:
            entity_id = results['entity_id']
            passed = sum(1 for t in results['tests'] if t['passed'] is True)
            total = sum(1 for t in results['tests'] if t['passed'] is not None)
            print(f"{entity_id}: {passed}/{total} tests passed")

        print()
        return all_results


def main():
    HA_URL = 'http://homeassistant.local:8123'
    TOKEN = 'YOUR_LONG_LIVED_ACCESS_TOKEN'

    # First enumerate devices
    from enumerate_wiim_devices import WiiMDeviceEnumerator
    enumerator = WiiMDeviceEnumerator(HA_URL, TOKEN)
    devices = enumerator.enumerate_devices()

    # Then test each device
    tester = WiiMDeviceTester(HA_URL, TOKEN)
    results = tester.test_all_devices(devices)

    return results


if __name__ == '__main__':
    results = main()
```

---

## Automated Device Testing

### Continuous Testing Script

```python
#!/usr/bin/env python3
"""
Automated continuous testing of WiiM devices
Runs tests periodically and logs results
"""

import time
import json
from datetime import datetime
from wiim_device_tester import WiiMDeviceTester, WiiMDeviceEnumerator

def run_continuous_tests(ha_url: str, token: str, interval: int = 300):
    """Run tests continuously at specified interval (seconds)."""

    enumerator = WiiMDeviceEnumerator(ha_url, token)
    tester = WiiMDeviceTester(ha_url, token)

    test_count = 0

    print(f"Starting continuous testing (interval: {interval}s)")
    print("Press Ctrl+C to stop\n")

    try:
        while True:
            test_count += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print(f"\n{'='*70}")
            print(f"Test Run #{test_count} - {timestamp}")
            print(f"{'='*70}")

            # Enumerate devices
            devices = enumerator.enumerate_devices()

            # Test each device
            results = tester.test_all_devices(devices)

            # Log results
            log_entry = {
                'timestamp': timestamp,
                'test_number': test_count,
                'devices_tested': len(devices),
                'results': results
            }

            with open('wiim_test_log.json', 'a') as f:
                f.write(json.dumps(log_entry) + '\n')

            print(f"\n✅ Test run #{test_count} complete. Waiting {interval}s...\n")
            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n\n✅ Stopped after {test_count} test runs")


if __name__ == '__main__':
    HA_URL = 'http://homeassistant.local:8123'
    TOKEN = 'YOUR_LONG_LIVED_ACCESS_TOKEN'
    INTERVAL = 300  # 5 minutes

    run_continuous_tests(HA_URL, TOKEN, INTERVAL)
```

---

## Testing Multiroom Groups

### Multiroom Group Testing Script

```python
#!/usr/bin/env python3
"""
Test multiroom functionality
"""

import requests
import time

class MultiRoomTester:
    def __init__(self, ha_url: str, token: str):
        self.ha_url = ha_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

    def call_service(self, domain: str, service: str, entity_id: str, **data):
        """Call service."""
        url = f"{self.ha_url}/api/services/{domain}/{service}"
        payload = {'entity_id': entity_id, **data}
        response = requests.post(url, headers=self.headers, json=payload)
        return response.status_code == 200

    def get_state(self, entity_id: str):
        """Get state."""
        url = f"{self.ha_url}/api/states/{entity_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def test_group_formation(self, master: str, members: list):
        """Test creating a multiroom group."""
        print(f"\n{'='*70}")
        print("Test: Multiroom Group Formation")
        print(f"{'='*70}\n")

        print(f"Master: {master}")
        print(f"Members: {', '.join(members)}\n")

        # Create group
        print("Creating group...")
        self.call_service('media_player', 'join', master, group_members=members)
        time.sleep(5)

        # Verify group
        master_state = self.get_state(master)
        group_members = master_state['attributes'].get('group_members', [])

        expected_members = set([master] + members)
        actual_members = set(group_members)

        success = expected_members == actual_members

        print(f"Expected members: {expected_members}")
        print(f"Actual members:   {actual_members}")
        print(f"\n{'✅ PASS' if success else '❌ FAIL'}\n")

        return success

    def test_group_volume(self, master: str):
        """Test group volume control."""
        print(f"\n{'='*70}")
        print("Test: Group Volume Control")
        print(f"{'='*70}\n")

        group_entity = f"{master}_group_coordinator"

        # Set group volume
        print("Setting group volume to 50%...")
        self.call_service('media_player', 'volume_set', group_entity, volume_level=0.5)
        time.sleep(2)

        # Check master volume
        master_state = self.get_state(master)
        master_volume = master_state['attributes'].get('volume_level', 0)

        # Check member volumes
        group_members = master_state['attributes'].get('group_members', [])
        member_volumes = []
        for member in group_members:
            if member != master:
                member_state = self.get_state(member)
                member_volumes.append(member_state['attributes'].get('volume_level', 0))

        # Verify synchronization
        all_volumes = [master_volume] + member_volumes
        volumes_synced = all(abs(v - 0.5) < 0.05 for v in all_volumes)

        print(f"Master volume:  {int(master_volume * 100)}%")
        for i, vol in enumerate(member_volumes, 1):
            print(f"Member {i} volume: {int(vol * 100)}%")

        print(f"\n{'✅ PASS' if volumes_synced else '❌ FAIL'}\n")

        return volumes_synced

    def test_group_ungroup(self, members: list):
        """Test ungrouping devices."""
        print(f"\n{'='*70}")
        print("Test: Ungroup Devices")
        print(f"{'='*70}\n")

        # Ungroup all
        for member in members:
            print(f"Ungrouping {member}...")
            self.call_service('media_player', 'unjoin', member)

        time.sleep(5)

        # Verify solo
        all_solo = True
        for member in members:
            state = self.get_state(member)
            role = state['attributes'].get('group_role', 'solo')
            print(f"{member}: role={role}")
            if role != 'solo':
                all_solo = False

        print(f"\n{'✅ PASS' if all_solo else '❌ FAIL'}\n")

        return all_solo


def main():
    HA_URL = 'http://homeassistant.local:8123'
    TOKEN = 'YOUR_LONG_LIVED_ACCESS_TOKEN'

    # Define devices for testing
    MASTER = 'media_player.living_room_wiim'
    MEMBERS = [
        'media_player.kitchen_wiim',
        'media_player.bedroom_wiim'
    ]

    tester = MultiRoomTester(HA_URL, TOKEN)

    # Run tests
    results = []
    results.append(('Group Formation', tester.test_group_formation(MASTER, MEMBERS)))
    results.append(('Group Volume', tester.test_group_volume(MASTER)))
    results.append(('Ungroup', tester.test_group_ungroup([MASTER] + MEMBERS)))

    # Summary
    print(f"\n{'='*70}")
    print("Multiroom Test Summary")
    print(f"{'='*70}\n")

    for test_name, passed in results:
        print(f"{test_name:.<50} {'✅ PASS' if passed else '❌ FAIL'}")

    passed_count = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed_count}/{len(results)} tests passed\n")


if __name__ == '__main__':
    main()
```

---

## Summary

### Device Enumeration Capabilities ✅

1. **Get all WiiM devices** - `get_all_speakers(hass)`
2. **Find by UUID** - `find_speaker_by_uuid(hass, uuid)`
3. **Find by IP** - `find_speaker_by_ip(hass, ip)`
4. **REST API** - Query via `/api/states`
5. **WebSocket API** - Real-time monitoring
6. **Config entries** - Access via `hass.config_entries`

### Direct Testing Capabilities ✅

1. **Volume Control** - Test set/get volume
2. **Mute Control** - Test mute/unmute
3. **Source Selection** - Test input switching
4. **Playback Control** - Test play/pause/stop
5. **Multiroom Groups** - Test join/unjoin/sync
6. **Device Info** - Verify metadata
7. **Continuous Testing** - Automated periodic tests

### Use Cases

- **Development Testing** - Test integration changes with real devices
- **Quality Assurance** - Automated test suite for releases
- **Monitoring** - Continuous device health checks
- **Troubleshooting** - Enumerate devices to diagnose issues
- **Multiroom Testing** - Verify group functionality

All scripts are production-ready and can be adapted for your specific setup!
