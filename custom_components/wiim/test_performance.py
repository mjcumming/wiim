#!/usr/bin/env python3
"""Test script to verify the new device registry performance."""

import asyncio
import time
from unittest.mock import MagicMock


# Mock HomeAssistant for testing
class MockHass:
    def __init__(self):
        self.data = {}


async def test_device_registry():
    """Test the new device registry."""
    from .device_registry import WiiMDeviceRegistry

    hass = MockHass()
    registry = WiiMDeviceRegistry(hass)

    # Create mock coordinators
    mock_coordinators = []
    for i in range(5):
        coord = MagicMock()
        coord.client.host = f"192.168.1.{100 + i}"
        coord.data = {"status": {"uuid": f"uuid-{i}"}}
        mock_coordinators.append(coord)
        registry.register_device(coord)

    print("✅ Registered 5 devices")

    # Test role changes - simulate device becoming slave
    start_time = time.time()

    # Device 1 becomes slave of device 0
    status = {"group": "1", "master_uuid": "uuid-0"}

    changes = await registry.handle_role_change("192.168.1.101", "solo", "slave", status)

    end_time = time.time()
    print(f"✅ Role change took {(end_time - start_time) * 1000:.2f}ms")
    print(f"✅ Changes made: {changes}")

    # Test group member lookup (should be O(1))
    start_time = time.time()

    for _ in range(1000):
        members = registry.get_group_members_for_device("192.168.1.100")
        leader = registry.get_group_leader_for_device("192.168.1.101")

    end_time = time.time()
    print(f"✅ 1000 group lookups took {(end_time - start_time) * 1000:.2f}ms")
    print(f"   Average: {(end_time - start_time) * 1000000 / 1000:.2f}μs per lookup")

    # Show final state
    print("\n📊 Final device states:")
    for ip, device in registry.devices.items():
        print(f"  {ip}: role={device.role}, master={device.master_ip}, slaves={device.slaves}")


if __name__ == "__main__":
    asyncio.run(test_device_registry())
