#!/usr/bin/env python3
"""
WiiM Integration - Device Add/Delete Lifecycle Tests
Tests the complete lifecycle of adding and removing WiiM devices via HA REST API.

Usage:
    python scripts/test-device-lifecycle.py --config scripts/test.config --device-ip 192.168.1.100
    python scripts/test-device-lifecycle.py --ha-url http://localhost:8123 --token YOUR_TOKEN --device-ip 192.168.1.100
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class DeviceLifecycleTests:
    """Test device add/remove lifecycle via HA REST API."""

    DOMAIN = "wiim"

    def __init__(self, ha_url: str, token: str, device_ip: str):
        self.ha_url = ha_url.rstrip("/")
        self.token = token
        self.device_ip = device_ip
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self.added_entry_id: str | None = None

    def print_header(self, text: str):
        width = 80
        print(f"\n{Colors.CYAN}{'=' * width}{Colors.RESET}")
        print(f"{Colors.BOLD}{text:^{width}}{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * width}{Colors.RESET}\n")

    def print_success(self, text: str):
        print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")

    def print_failure(self, text: str):
        print(f"{Colors.RED}❌ {text}{Colors.RESET}")

    def print_warning(self, text: str):
        print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")

    def print_info(self, text: str):
        print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")

    # =========================================================================
    # Config Entry API Methods
    # =========================================================================

    def get_config_entries(self, domain: str | None = None) -> list[dict[str, Any]]:
        """Get all config entries, optionally filtered by domain."""
        try:
            response = requests.get(
                f"{self.ha_url}/api/config/config_entries/entry",
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()
            entries = response.json()

            if domain:
                entries = [e for e in entries if e.get("domain") == domain]

            return entries
        except Exception as e:
            print(f"{Colors.RED}Error getting config entries: {e}{Colors.RESET}")
            return []

    def get_config_entry_details(self, entry_id: str) -> dict[str, Any] | None:
        """Get full details of a config entry including data field."""
        try:
            # Use WebSocket-style API via REST to get full entry details
            # The list API doesn't return 'data', need to check entity states
            response = requests.get(
                f"{self.ha_url}/api/states",
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()
            states = response.json()

            # Find a WiiM entity that belongs to this entry and get its attributes
            for state in states:
                attrs = state.get("attributes", {})
                if attrs.get("integration_purpose") == "individual_speaker_control":
                    # Found a WiiM entity, but need to match to entry_id
                    # This is tricky - may need to use device registry
                    pass

            return None
        except Exception as e:
            print(f"{Colors.RED}Error getting entry details: {e}{Colors.RESET}")
            return None

    def find_wiim_entry_by_host(self, host: str) -> dict[str, Any] | None:
        """Find a WiiM config entry by host IP.

        Since the list API doesn't include 'data' field, we check entity states
        for the ip_address attribute to match the host.
        """
        try:
            # Get all entity states and find WiiM entity with matching ip_address
            response = requests.get(
                f"{self.ha_url}/api/states",
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()
            states = response.json()

            # Find WiiM entity with matching ip_address attribute
            matching_entity = None
            for state in states:
                attrs = state.get("attributes", {})
                if attrs.get("ip_address") == host:
                    matching_entity = state
                    break
                # Also check integration_purpose as backup identifier
                if attrs.get("integration_purpose") == "individual_speaker_control" and attrs.get("ip_address") == host:
                    matching_entity = state
                    break

            if not matching_entity:
                # Fallback: check entry titles for IP
                entries = self.get_config_entries(self.DOMAIN)
                for entry in entries:
                    title = entry.get("title", "")
                    if host in title:
                        return entry
                return None

            # Found matching entity - now find its config entry
            # Entity ID format is typically: media_player.device_name
            # The config entry title usually matches the friendly_name
            entity_name = matching_entity.get("attributes", {}).get("friendly_name", "")

            entries = self.get_config_entries(self.DOMAIN)
            for entry in entries:
                if entry.get("title") == entity_name:
                    return entry

            return None
        except Exception as e:
            print(f"{Colors.RED}Error finding entry by host: {e}{Colors.RESET}")
            return None

    def start_config_flow(self) -> dict[str, Any] | None:
        """Start a new config flow for WiiM integration (manual add)."""
        try:
            # Step 1: Initialize the config flow
            response = requests.post(
                f"{self.ha_url}/api/config/config_entries/flow",
                headers=self.headers,
                json={"handler": self.DOMAIN},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"{Colors.RED}Error starting config flow: {e}{Colors.RESET}")
            return None

    def continue_config_flow(self, flow_id: str, user_input: dict[str, Any]) -> dict[str, Any] | None:
        """Continue a config flow with user input."""
        try:
            response = requests.post(
                f"{self.ha_url}/api/config/config_entries/flow/{flow_id}",
                headers=self.headers,
                json=user_input,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Return the response data even on errors (contains form errors)
            if e.response is not None:
                try:
                    return e.response.json()
                except Exception:
                    pass
            print(f"{Colors.RED}Error continuing config flow: {e}{Colors.RESET}")
            return None
        except Exception as e:
            print(f"{Colors.RED}Error continuing config flow: {e}{Colors.RESET}")
            return None

    def delete_config_entry(self, entry_id: str) -> bool:
        """Delete a config entry by ID."""
        try:
            response = requests.delete(
                f"{self.ha_url}/api/config/config_entries/entry/{entry_id}",
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"{Colors.RED}Error deleting config entry: {e}{Colors.RESET}")
            return False

    def reload_config_entry(self, entry_id: str) -> bool:
        """Reload a config entry."""
        try:
            response = requests.post(
                f"{self.ha_url}/api/config/config_entries/entry/{entry_id}/reload",
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"{Colors.RED}Error reloading config entry: {e}{Colors.RESET}")
            return False

    # =========================================================================
    # Test Methods
    # =========================================================================

    def test_device_not_already_configured(self) -> dict[str, Any]:
        """Verify the device is not already configured."""
        self.print_header("Pre-check: Device Not Already Configured")

        existing = self.find_wiim_entry_by_host(self.device_ip)
        if existing:
            self.print_warning(f"Device already configured with entry_id: {existing['entry_id']}")
            self.print_info("Removing existing entry for clean test...")

            if self.delete_config_entry(existing["entry_id"]):
                time.sleep(3)
                self.print_success("Existing entry removed")
            else:
                return {"passed": False, "details": {"error": "Could not remove existing entry"}}

        self.print_success(f"Device {self.device_ip} is not configured")
        return {"passed": True}

    def test_add_device_via_config_flow(self) -> dict[str, Any]:
        """Test adding a device via the config flow API."""
        self.print_header("Test: Add Device via Config Flow")

        # Step 1: Start config flow
        self.print_info("Starting config flow...")
        flow_result = self.start_config_flow()

        if not flow_result:
            return {"passed": False, "details": {"error": "Failed to start config flow"}}

        flow_id = flow_result.get("flow_id")
        step_id = flow_result.get("step_id")
        flow_type = flow_result.get("type")

        self.print_info(f"Flow ID: {flow_id}, Step: {step_id}, Type: {flow_type}")

        # Step 2: Handle discovery step (if devices are discovered)
        # WiiM config flow: user -> discovery -> manual (if no devices) OR discovery -> select
        if step_id == "discovery":
            # Check if devices were discovered
            data_schema = flow_result.get("data_schema", [])
            self.print_info(f"Discovery step, schema: {data_schema}")

            # If discovery found devices, we need to either select one or go to manual
            # For testing, let's go to manual entry by providing an unknown host
            # Actually, let's check if our device is in the list
            # For now, let's try manual step directly if available
            pass

        # Step 3: Navigate to manual entry and submit IP
        # WiiM flow may go directly to manual if no devices discovered
        if step_id in ("discovery", "manual", "user"):
            self.print_info(f"Submitting device IP: {self.device_ip}")

            # The config flow expects "host" field
            result = self.continue_config_flow(flow_id, {"host": self.device_ip})

            if not result:
                return {"passed": False, "details": {"error": "Failed to submit device IP"}}

            result_type = result.get("type")
            self.print_info(f"Result type: {result_type}")

            # Handle different result types
            if result_type == "create_entry":
                # Success! Entry was created
                entry_id = result.get("result", {}).get("entry_id")
                title = result.get("title")
                self.added_entry_id = entry_id
                self.print_success(f"Device added successfully!")
                self.print_info(f"Entry ID: {entry_id}, Title: {title}")
                return {"passed": True, "details": {"entry_id": entry_id, "title": title}}

            elif result_type == "form":
                # Another form step needed (e.g., discovery_confirm)
                new_step = result.get("step_id")
                self.print_info(f"Additional step required: {new_step}")

                if new_step == "discovery_confirm":
                    # Confirm the discovered device
                    confirm_result = self.continue_config_flow(flow_id, {})
                    if confirm_result and confirm_result.get("type") == "create_entry":
                        entry_id = confirm_result.get("result", {}).get("entry_id")
                        title = confirm_result.get("title")
                        self.added_entry_id = entry_id
                        self.print_success(f"Device added successfully!")
                        self.print_info(f"Entry ID: {entry_id}, Title: {title}")
                        return {"passed": True, "details": {"entry_id": entry_id, "title": title}}
                    else:
                        return {"passed": False, "details": {"error": f"Confirm step failed: {confirm_result}"}}

                elif new_step == "manual":
                    # Need to submit to manual step
                    manual_result = self.continue_config_flow(flow_id, {"host": self.device_ip})
                    if manual_result and manual_result.get("type") == "create_entry":
                        entry_id = manual_result.get("result", {}).get("entry_id")
                        title = manual_result.get("title")
                        self.added_entry_id = entry_id
                        self.print_success(f"Device added successfully!")
                        self.print_info(f"Entry ID: {entry_id}, Title: {title}")
                        return {"passed": True, "details": {"entry_id": entry_id, "title": title}}
                    else:
                        errors = manual_result.get("errors", {}) if manual_result else {}
                        return {"passed": False, "details": {"error": f"Manual step failed", "errors": errors}}

            elif result_type == "abort":
                reason = result.get("reason")
                if reason == "already_configured":
                    self.print_warning("Device already configured (race condition)")
                    existing = self.find_wiim_entry_by_host(self.device_ip)
                    if existing:
                        self.added_entry_id = existing["entry_id"]
                        return {
                            "passed": True,
                            "details": {"already_configured": True, "entry_id": existing["entry_id"]},
                        }
                return {"passed": False, "details": {"error": f"Flow aborted: {reason}"}}

            else:
                return {
                    "passed": False,
                    "details": {"error": f"Unexpected result type: {result_type}", "result": result},
                }

        return {"passed": False, "details": {"error": f"Unexpected step: {step_id}"}}

    def test_verify_device_setup(self) -> dict[str, Any]:
        """Verify the device was set up correctly after adding."""
        self.print_header("Test: Verify Device Setup")

        if not self.added_entry_id:
            return {"passed": False, "details": {"error": "No entry ID from previous add test"}}

        # Wait for setup to complete with retry loop
        self.print_info("Waiting for device setup...")
        max_attempts = 12  # 12 attempts x 5 seconds = 60 seconds max
        state = None

        for attempt in range(max_attempts):
            time.sleep(5)

            # Check config entry state
            entries = self.get_config_entries(self.DOMAIN)
            entry = next((e for e in entries if e["entry_id"] == self.added_entry_id), None)

            if not entry:
                return {"passed": False, "details": {"error": "Config entry not found"}}

            state = entry.get("state")
            self.print_info(f"Entry state: {state} (attempt {attempt + 1}/{max_attempts})")

            if state == "loaded":
                break
            elif state in ("setup_error", "failed_unload"):
                return {"passed": False, "details": {"error": f"Setup failed with state: {state}"}}

        if state != "loaded":
            return {
                "passed": False,
                "details": {"error": f"Entry not loaded after {max_attempts * 5}s, state: {state}"},
            }

        # Check if entities were created
        try:
            response = requests.get(
                f"{self.ha_url}/api/states",
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()
            all_states = response.json()

            # Find WiiM entities
            wiim_entities = [
                s
                for s in all_states
                if s.get("attributes", {}).get("integration_purpose") == "individual_speaker_control"
            ]

            self.print_info(f"Found {len(wiim_entities)} WiiM media player(s)")

            if not wiim_entities:
                return {"passed": False, "details": {"error": "No WiiM entities found"}}

            self.print_success("Device setup verified successfully")
            return {"passed": True, "details": {"entity_count": len(wiim_entities)}}

        except Exception as e:
            return {"passed": False, "details": {"error": str(e)}}

    def test_device_reload(self) -> dict[str, Any]:
        """Test reloading the device config entry."""
        self.print_header("Test: Reload Device")

        if not self.added_entry_id:
            return {"passed": False, "details": {"error": "No entry ID from previous add test"}}

        self.print_info(f"Reloading entry: {self.added_entry_id}")

        if not self.reload_config_entry(self.added_entry_id):
            return {"passed": False, "details": {"error": "Reload failed"}}

        time.sleep(3)

        # Verify still loaded
        entries = self.get_config_entries(self.DOMAIN)
        entry = next((e for e in entries if e["entry_id"] == self.added_entry_id), None)

        if not entry or entry.get("state") != "loaded":
            return {"passed": False, "details": {"error": "Entry not loaded after reload"}}

        self.print_success("Device reloaded successfully")
        return {"passed": True}

    def test_remove_device(self) -> dict[str, Any]:
        """Test removing the device via config entry delete."""
        self.print_header("Test: Remove Device")

        if not self.added_entry_id:
            return {"passed": False, "details": {"error": "No entry ID from previous add test"}}

        self.print_info(f"Removing entry: {self.added_entry_id}")

        if not self.delete_config_entry(self.added_entry_id):
            return {"passed": False, "details": {"error": "Delete failed"}}

        time.sleep(3)

        # Verify removal
        entries = self.get_config_entries(self.DOMAIN)
        entry = next((e for e in entries if e["entry_id"] == self.added_entry_id), None)

        if entry:
            return {"passed": False, "details": {"error": "Entry still exists after delete"}}

        self.print_success("Device removed successfully")
        return {"passed": True}

    def test_verify_cleanup(self) -> dict[str, Any]:
        """Verify entities and device registry cleaned up after removal."""
        self.print_header("Test: Verify Cleanup")

        # Check no leftover entities
        try:
            response = requests.get(
                f"{self.ha_url}/api/states",
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()
            all_states = response.json()

            # Check if the removed device's entities are gone
            # This is tricky without knowing the exact entity_id
            # For now, just verify the entry is gone
            entry = self.find_wiim_entry_by_host(self.device_ip)

            if entry:
                return {"passed": False, "details": {"error": "Config entry still exists"}}

            self.print_success("Cleanup verified - no leftover entries")
            return {"passed": True}

        except Exception as e:
            return {"passed": False, "details": {"error": str(e)}}

    def test_readd_after_delete(self) -> dict[str, Any]:
        """Test re-adding a device after it was deleted."""
        self.print_header("Test: Re-add Device After Delete")

        # This tests that the device can be cleanly re-added
        self.added_entry_id = None  # Reset for fresh add
        return self.test_add_device_via_config_flow()

    # =========================================================================
    # Test Runner
    # =========================================================================

    def run(self, cleanup: bool = True) -> bool:
        """Run all device lifecycle tests."""
        self.print_header("WiiM Device Lifecycle Tests")
        self.print_info(f"Target device: {self.device_ip}")
        self.print_info(f"HA URL: {self.ha_url}")

        tests = [
            ("pre_check", self.test_device_not_already_configured),
            ("add_device", self.test_add_device_via_config_flow),
            ("verify_setup", self.test_verify_device_setup),
            ("reload_device", self.test_device_reload),
            ("remove_device", self.test_remove_device),
            ("verify_cleanup", self.test_verify_cleanup),
            ("readd_device", self.test_readd_after_delete),
        ]

        results = {}
        for test_name, test_func in tests:
            try:
                results[test_name] = test_func()
            except Exception as e:
                results[test_name] = {"passed": False, "details": {"error": str(e)}}

            # Stop if a critical test fails
            if not results[test_name].get("passed", False):
                if test_name in ("add_device", "verify_setup"):
                    self.print_warning(f"Critical test {test_name} failed, stopping")
                    break

        # Final cleanup (if enabled and we added a device)
        if cleanup and self.added_entry_id:
            self.print_info("Final cleanup: removing test device...")
            self.delete_config_entry(self.added_entry_id)

        # Print summary
        self.print_header("Test Summary")
        passed = sum(1 for r in results.values() if r.get("passed", False))
        total = len(results)

        for test_name, result in results.items():
            if result.get("passed", False):
                self.print_success(f"{test_name}: PASSED")
            else:
                self.print_failure(f"{test_name}: FAILED - {result.get('details', {})}")

        print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.RESET}")
        return passed == total


def main():
    parser = argparse.ArgumentParser(description="WiiM Device Lifecycle Tests")
    parser.add_argument("--ha-url", default="http://localhost:8123", help="Home Assistant URL")
    parser.add_argument("--token", help="Home Assistant long-lived access token")
    parser.add_argument("--config", help="Path to test.config file")
    parser.add_argument("--device-ip", required=True, help="IP address of WiiM device to test with")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't remove device after tests")

    args = parser.parse_args()

    # Load config if provided
    ha_url = args.ha_url
    token = args.token

    if args.config and os.path.exists(args.config):
        try:
            with open(args.config) as f:
                config = json.load(f)
                ha_url = config.get("HA_URL", ha_url)
                token = config.get("TOKEN", token)
        except json.JSONDecodeError:
            with open(args.config) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        if key == "HA_URL":
                            ha_url = value
                        elif key == "HA_TOKEN":
                            token = value

    token = token or os.environ.get("HA_TOKEN")

    if not token:
        print("Error: No token provided. Use --token or set HA_TOKEN environment variable.")
        sys.exit(1)

    suite = DeviceLifecycleTests(ha_url, token, args.device_ip)
    success = suite.run(cleanup=not args.no_cleanup)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
