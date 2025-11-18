#!/usr/bin/env python3
"""
Quick test script for sleep timer and alarm services on a specific device.
"""

import os
import sys
import time
from typing import Any

import requests


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_header(text: str):
    print(f"\n{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{text}{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}\n")


def print_success(text: str):
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")


def print_failure(text: str):
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")


def print_info(text: str):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")


def find_device(ha_url: str, headers: dict, device_name: str) -> dict[str, Any] | None:
    """Find a device by name."""
    try:
        response = requests.get(f"{ha_url}/api/states", headers=headers, timeout=5)
        response.raise_for_status()
        all_states = response.json()

        # Search for device by friendly name or entity ID
        for state in all_states:
            if not state["entity_id"].startswith("media_player."):
                continue

            attrs = state.get("attributes", {})
            friendly_name = attrs.get("friendly_name", "").lower()
            entity_id = state["entity_id"].lower()

            if device_name.lower() in friendly_name or device_name.lower() in entity_id:
                if attrs.get("integration_purpose") == "individual_speaker_control":
                    return state

        return None
    except Exception as e:
        print_failure(f"Failed to discover devices: {e}")
        return None


def call_service(ha_url: str, headers: dict, domain: str, service: str, entity_id: str, **data) -> bool:
    """Call a Home Assistant service."""
    try:
        url = f"{ha_url}/api/services/{domain}/{service}"
        payload = {"entity_id": entity_id, **data}
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            return True
        else:
            print_failure(f"Service returned status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print_failure(f"Service call failed: {e}")
        return False


def main():
    ha_url = os.getenv("HA_URL", "http://localhost:8123").rstrip("/")
    token = os.getenv("HA_TOKEN")

    if not token:
        print_failure("No HA_TOKEN environment variable set!")
        print_info("Set it with: export HA_TOKEN='your_long_lived_access_token'")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Find master bedroom device
    print_header("Finding Master Bedroom Device")
    device = find_device(ha_url, headers, "master bedroom")

    if not device:
        print_failure("Could not find master bedroom device!")
        print_info("Available devices:")
        try:
            response = requests.get(f"{ha_url}/api/states", headers=headers, timeout=5)
            all_states = response.json()
            for state in all_states:
                if state["entity_id"].startswith("media_player."):
                    attrs = state.get("attributes", {})
                    if attrs.get("integration_purpose") == "individual_speaker_control":
                        print(f"  - {attrs.get('friendly_name', state['entity_id'])} ({state['entity_id']})")
        except Exception:
            pass
        sys.exit(1)

    entity_id = device["entity_id"]
    device_name = device["attributes"].get("friendly_name", entity_id)
    print_success(f"Found device: {device_name} ({entity_id})")

    # Test Sleep Timer
    print_header("Testing Sleep Timer")
    print_info("Setting sleep timer to 2 minutes (120 seconds)...")
    success = call_service(ha_url, headers, "wiim", "set_sleep_timer", entity_id, sleep_time=120)
    if success:
        print_success("Sleep timer set successfully")
    else:
        print_failure("Failed to set sleep timer")
        return

    time.sleep(2)

    print_info("Clearing sleep timer...")
    clear_success = call_service(ha_url, headers, "wiim", "clear_sleep_timer", entity_id)
    if clear_success:
        print_success("Sleep timer cleared successfully")
    else:
        print_failure("Failed to clear sleep timer")

    time.sleep(1)

    # Test Alarms
    print_header("Testing Alarm Management")
    print_info("Creating alarm in slot 0 (7:00 AM UTC, daily)...")
    alarm_success = call_service(
        ha_url,
        headers,
        "wiim",
        "update_alarm",
        entity_id,
        alarm_id=0,
        time="07:00:00",
        trigger="daily",
        operation="playback",
    )
    if alarm_success:
        print_success("Alarm created successfully")
    else:
        print_failure("Failed to create alarm")
        return

    time.sleep(2)

    print_info("Updating alarm time to 8:00 AM UTC...")
    update_success = call_service(
        ha_url,
        headers,
        "wiim",
        "update_alarm",
        entity_id,
        alarm_id=0,
        time="08:00:00",
    )
    if update_success:
        print_success("Alarm updated successfully")
    else:
        print_failure("Failed to update alarm")

    time.sleep(2)

    print_info("Creating alarm in slot 1 (9:00 AM UTC, daily)...")
    alarm2_success = call_service(
        ha_url,
        headers,
        "wiim",
        "update_alarm",
        entity_id,
        alarm_id=1,
        time="09:00:00",
        trigger="daily",
        operation="playback",
    )
    if alarm2_success:
        print_success("Second alarm created successfully")
    else:
        print_failure("Failed to create second alarm")

    print_header("Test Complete")
    print_success("All tests completed!")
    print_info("Note: Alarms remain on device - you may want to delete them manually if needed")


if __name__ == "__main__":
    main()
