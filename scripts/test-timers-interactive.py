#!/usr/bin/env python3
"""
Interactive test script for sleep timer and alarm services.
Prompts for HA token if not in environment.
"""

import getpass
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


def call_service(ha_url: str, headers: dict, domain: str, service: str, entity_id: str, **data) -> tuple[bool, str]:
    """Call a Home Assistant service."""
    try:
        url = f"{ha_url}/api/services/{domain}/{service}"
        payload = {"entity_id": entity_id, **data}
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            return True, ""
        else:
            error_msg = response.text
            try:
                error_json = response.json()
                error_msg = error_json.get("message", error_msg)
            except Exception:
                pass
            return False, f"Status {response.status_code}: {error_msg}"
    except Exception as e:
        return False, str(e)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test sleep timer and alarms on WiiM device")
    parser.add_argument("--token", help="Home Assistant access token")
    parser.add_argument("--url", default="http://localhost:8123", help="Home Assistant URL")
    parser.add_argument("--device", default="master bedroom", help="Device name to search for")
    args = parser.parse_args()

    ha_url = args.url.rstrip("/")
    token = args.token or os.getenv("HA_TOKEN")

    if not token:
        print_failure("No access token provided!")
        print_info("Usage: python3 test-timers-interactive.py --token YOUR_TOKEN")
        print_info("Or set HA_TOKEN environment variable")
        print_info("You can get a long-lived access token from:")
        print_info("  Home Assistant → Profile → Long-Lived Access Tokens")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Test connection
    print_header("Testing Connection")
    try:
        response = requests.get(f"{ha_url}/api/", headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Connected to Home Assistant (version: {data.get('version', 'Unknown')})")
        else:
            print_failure(f"Connection failed: HTTP {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print_failure(f"Cannot connect to Home Assistant: {e}")
        sys.exit(1)

    # Find device
    print_header(f"Finding Device: {args.device}")
    device = find_device(ha_url, headers, args.device)

    if not device:
        print_failure("Could not find master bedroom device!")
        print_info("Searching for all WiiM devices...")
        try:
            response = requests.get(f"{ha_url}/api/states", headers=headers, timeout=5)
            all_states = response.json()
            wiim_devices = [
                state
                for state in all_states
                if state["entity_id"].startswith("media_player.")
                and state.get("attributes", {}).get("integration_purpose") == "individual_speaker_control"
            ]
            if wiim_devices:
                print_info("Available WiiM devices:")
                for state in wiim_devices:
                    attrs = state.get("attributes", {})
                    print(f"  - {attrs.get('friendly_name', state['entity_id'])} ({state['entity_id']})")
            else:
                print_failure("No WiiM devices found!")
        except Exception as e:
            print_failure(f"Error searching devices: {e}")
        sys.exit(1)

    entity_id = device["entity_id"]
    device_name = device["attributes"].get("friendly_name", entity_id)
    print_success(f"Found device: {device_name} ({entity_id})")

    # Test Sleep Timer
    print_header("Testing Sleep Timer")
    print_info("Setting sleep timer to 2 minutes (120 seconds)...")
    success, error = call_service(ha_url, headers, "wiim", "set_sleep_timer", entity_id, sleep_time=120)
    if success:
        print_success("Sleep timer set successfully")
    else:
        print_failure(f"Failed to set sleep timer: {error}")
        return

    time.sleep(2)

    print_info("Clearing sleep timer...")
    clear_success, clear_error = call_service(ha_url, headers, "wiim", "clear_sleep_timer", entity_id)
    if clear_success:
        print_success("Sleep timer cleared successfully")
    else:
        print_failure(f"Failed to clear sleep timer: {clear_error}")

    time.sleep(1)

    # Test Alarms
    print_header("Testing Alarm Management")
    print_info("Creating alarm in slot 0 (7:00 AM UTC, daily)...")
    alarm_success, alarm_error = call_service(
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
        print_failure(f"Failed to create alarm: {alarm_error}")
        return

    time.sleep(2)

    print_info("Updating alarm time to 8:00 AM UTC...")
    update_success, update_error = call_service(
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
        print_failure(f"Failed to update alarm: {update_error}")

    time.sleep(2)

    print_info("Creating alarm in slot 1 (9:00 AM UTC, daily)...")
    alarm2_success, alarm2_error = call_service(
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
        print_failure(f"Failed to create second alarm: {alarm2_error}")

    print_header("Test Complete")
    print_success("All tests completed!")
    print_info("Note: Alarms remain on device - you may want to delete them manually if needed")


if __name__ == "__main__":
    main()
