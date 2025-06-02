#!/usr/bin/env python3
"""Quick test script to verify group state."""

import asyncio
import sys
import logging

# Set up basic logging to see debug messages
logging.basicConfig(level=logging.DEBUG)

# Mock test data based on your logs
devices = {
    "192.168.1.68": {"role": "master", "slaves": {"192.168.1.116", "192.168.1.115"}},
    "192.168.1.116": {"role": "slave", "master_ip": "192.168.1.68"},
    "192.168.1.115": {"role": "slave", "master_ip": "192.168.1.68"},
}


def ip_to_entity_id(ip: str) -> str:
    return f"media_player.wiim_{ip.replace('.', '_')}"


def get_group_members_for_device(device_ip: str) -> list[str]:
    """Simulate the device registry logic."""
    device = devices.get(device_ip)
    if not device:
        return []

    if device["role"] == "master":
        # Master + all slaves
        members = [ip_to_entity_id(device_ip)]
        members.extend(ip_to_entity_id(slave_ip) for slave_ip in device["slaves"])
        return members

    elif device["role"] == "slave" and device.get("master_ip"):
        # All devices in the group (master + all slaves)
        master_ip = device["master_ip"]
        master_device = devices.get(master_ip)
        if master_device:
            members = [ip_to_entity_id(master_ip)]
            members.extend(ip_to_entity_id(slave_ip) for slave_ip in master_device["slaves"])
            return members

    return []  # Solo device has no group members


def test_group_members():
    """Test that group members are returned correctly."""
    print("=== Testing Group Members ===")

    for device_ip in devices:
        members = get_group_members_for_device(device_ip)
        print(f"{device_ip} ({devices[device_ip]['role']}): {members}")

    print("\n=== Expected Results ===")
    print("All three devices should return the same list:")
    print("['media_player.wiim_192_168_1_68', 'media_player.wiim_192_168_1_116', 'media_player.wiim_192_168_1_115']")


if __name__ == "__main__":
    test_group_members()
