#!/usr/bin/env python3
"""
WiiM Integration - Real Device Test Suite
Tests actual WiiM devices in a running Home Assistant instance
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any

import requests


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class WiiMRealDeviceTestSuite:
    """Automated test suite for real WiiM devices."""

    def __init__(self, ha_url: str, token: str | None = None):
        self.ha_url = ha_url.rstrip("/")
        self.token = token or os.getenv("HA_TOKEN")

        if not self.token:
            print(f"{Colors.RED}❌ No access token provided!{Colors.RESET}")
            print(f"{Colors.YELLOW}Set HA_TOKEN environment variable or use --token{Colors.RESET}")
            sys.exit(1)

        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        self.devices = []
        self.test_results = []
        self.start_time = None

    def print_header(self, text: str, char: str = "="):
        """Print formatted header."""
        width = 80
        print(f"\n{Colors.CYAN}{char * width}{Colors.RESET}")
        print(f"{Colors.BOLD}{text:^{width}}{Colors.RESET}")
        print(f"{Colors.CYAN}{char * width}{Colors.RESET}\n")

    def print_success(self, text: str):
        """Print success message."""
        print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")

    def print_failure(self, text: str):
        """Print failure message."""
        print(f"{Colors.RED}❌ {text}{Colors.RESET}")

    def print_info(self, text: str):
        """Print info message."""
        print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")

    def print_warning(self, text: str):
        """Print warning message."""
        print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")

    def check_connection(self) -> bool:
        """Check connection to Home Assistant."""
        self.print_info("Checking Home Assistant connection...")

        try:
            response = requests.get(f"{self.ha_url}/api/", headers=self.headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.print_success("Connected to Home Assistant")
                self.print_info(f"Version: {data.get('version', 'Unknown')}")
                return True
            else:
                self.print_failure(f"Connection failed: HTTP {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            self.print_failure(f"Cannot connect to {self.ha_url}")
            return False
        except Exception as e:
            self.print_failure(f"Connection error: {e}")
            return False

    def discover_devices(self) -> list[dict[str, Any]]:
        """Discover all WiiM devices."""
        self.print_header("Device Discovery")
        self.print_info("Searching for WiiM devices...")

        try:
            response = requests.get(f"{self.ha_url}/api/states", headers=self.headers)
            response.raise_for_status()
            all_states = response.json()

            # Filter for WiiM media players (not group coordinators)
            wiim_devices = [
                state
                for state in all_states
                if state["entity_id"].startswith("media_player.")
                and state.get("attributes", {}).get("integration_purpose") == "individual_speaker_control"
            ]

            self.devices = wiim_devices

            if not wiim_devices:
                self.print_warning("No WiiM devices found!")
                self.print_info("Make sure WiiM integration is set up in Home Assistant")
                return []

            self.print_success(f"Found {len(wiim_devices)} WiiM device(s)\n")

            for i, device in enumerate(wiim_devices, 1):
                attrs = device.get("attributes", {})
                print(f"{Colors.MAGENTA}Device {i}:{Colors.RESET}")
                print(f"  Entity ID:    {device['entity_id']}")
                print(f"  Name:         {attrs.get('friendly_name', 'Unknown')}")
                print(f"  Model:        {attrs.get('device_model', 'Unknown')}")
                print(f"  Firmware:     {attrs.get('firmware_version', 'Unknown')}")
                print(f"  IP Address:   {attrs.get('ip_address', 'Unknown')}")
                print(f"  State:        {device['state']}")
                print(f"  Available:    {device['state'] != 'unavailable'}")
                print()

            return wiim_devices

        except Exception as e:
            self.print_failure(f"Device discovery failed: {e}")
            return []

    def call_service(self, domain: str, service: str, entity_id: str, **data) -> bool:
        """Call a Home Assistant service."""
        try:
            url = f"{self.ha_url}/api/services/{domain}/{service}"
            payload = {"entity_id": entity_id, **data}
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"    {Colors.RED}Service call failed: {e}{Colors.RESET}")
            return False

    def get_state(self, entity_id: str) -> dict[str, Any] | None:
        """Get entity state."""
        try:
            url = f"{self.ha_url}/api/states/{entity_id}"
            response = requests.get(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"    {Colors.RED}Failed to get state: {e}{Colors.RESET}")
            return None

    def wait_for_state(self, entity_id: str, expected_state: str, timeout: int = 10) -> bool:
        """Wait for entity to reach expected state."""
        start = time.time()
        while time.time() - start < timeout:
            state = self.get_state(entity_id)
            if state and state["state"] == expected_state:
                return True
            time.sleep(0.5)
        return False

    def test_device_availability(self, device: dict[str, Any]) -> dict[str, Any]:
        """Test if device is available."""
        device["entity_id"]
        device.get("attributes", {})

        print(f"\n{Colors.BOLD}Test: Device Availability{Colors.RESET}")

        available = device["state"] != "unavailable"

        result = {
            "test": "Device Availability",
            "passed": available,
            "details": {"state": device["state"], "available": available},
        }

        if available:
            self.print_success("Device is available")
        else:
            self.print_failure("Device is unavailable")

        return result

    def test_volume_control(self, device: dict[str, Any]) -> dict[str, Any]:
        """Test volume control."""
        entity_id = device["entity_id"]

        print(f"\n{Colors.BOLD}Test: Volume Control{Colors.RESET}")

        # Get original volume
        state = self.get_state(entity_id)
        if not state:
            return {"test": "Volume Control", "passed": False, "details": {"error": "Could not get state"}}

        original_volume = state.get("attributes", {}).get("volume_level", 0.5)
        print(f"  Original volume: {int(original_volume * 100)}%")

        # Set test volume
        test_volume = 0.35
        print(f"  Setting volume to {int(test_volume * 100)}%...")
        success = self.call_service("media_player", "volume_set", entity_id, volume_level=test_volume)

        if not success:
            return {"test": "Volume Control", "passed": False, "details": {"error": "Service call failed"}}

        time.sleep(2)

        # Verify volume changed
        new_state = self.get_state(entity_id)
        new_volume = new_state.get("attributes", {}).get("volume_level", 0)
        volume_changed = abs(new_volume - test_volume) < 0.05

        print(f"  New volume: {int(new_volume * 100)}%")

        # Restore original volume
        self.call_service("media_player", "volume_set", entity_id, volume_level=original_volume)
        time.sleep(1)

        result = {
            "test": "Volume Control",
            "passed": volume_changed,
            "details": {
                "original_volume": original_volume,
                "test_volume": test_volume,
                "actual_volume": new_volume,
                "tolerance": 0.05,
            },
        }

        if volume_changed:
            self.print_success("Volume control works")
        else:
            self.print_failure(f"Volume mismatch (expected {test_volume:.2f}, got {new_volume:.2f})")

        return result

    def test_mute_control(self, device: dict[str, Any]) -> dict[str, Any]:
        """Test mute control."""
        entity_id = device["entity_id"]

        print(f"\n{Colors.BOLD}Test: Mute Control{Colors.RESET}")

        # Mute
        print("  Muting device...")
        self.call_service("media_player", "volume_mute", entity_id, is_volume_muted=True)
        time.sleep(2)

        # Check if muted
        state = self.get_state(entity_id)
        is_muted = state.get("attributes", {}).get("is_volume_muted", False)

        # Unmute
        self.call_service("media_player", "volume_mute", entity_id, is_volume_muted=False)
        time.sleep(1)

        result = {"test": "Mute Control", "passed": is_muted, "details": {"muted": is_muted}}

        if is_muted:
            self.print_success("Mute control works")
        else:
            self.print_failure("Device did not mute")

        return result

    def test_source_selection(self, device: dict[str, Any]) -> dict[str, Any]:
        """Test source selection."""
        entity_id = device["entity_id"]
        attrs = device.get("attributes", {})

        print(f"\n{Colors.BOLD}Test: Source Selection{Colors.RESET}")

        sources = attrs.get("source_list", [])
        current_source = attrs.get("source")

        print(f"  Available sources: {', '.join(sources)}")
        print(f"  Current source: {current_source}")

        if len(sources) < 2:
            self.print_warning("Not enough sources to test (skipping)")
            return {"test": "Source Selection", "passed": None, "details": {"skipped": True}}

        # Pick different source
        test_source = sources[0] if sources[0] != current_source else sources[1]
        print(f"  Switching to: {test_source}")

        self.call_service("media_player", "select_source", entity_id, source=test_source)
        time.sleep(2)

        # Verify source changed
        new_state = self.get_state(entity_id)
        new_source = new_state.get("attributes", {}).get("source")
        source_changed = new_source == test_source

        print(f"  New source: {new_source}")

        # Restore original source
        if current_source:
            self.call_service("media_player", "select_source", entity_id, source=current_source)
            time.sleep(1)

        result = {
            "test": "Source Selection",
            "passed": source_changed,
            "details": {"test_source": test_source, "actual_source": new_source},
        }

        if source_changed:
            self.print_success("Source selection works")
        else:
            self.print_failure(f"Source did not change (expected {test_source}, got {new_source})")

        return result

    def test_device_info(self, device: dict[str, Any]) -> dict[str, Any]:
        """Test device information completeness."""
        attrs = device.get("attributes", {})

        print(f"\n{Colors.BOLD}Test: Device Information{Colors.RESET}")

        required_attrs = {
            "device_model": attrs.get("device_model"),
            "firmware_version": attrs.get("firmware_version"),
            "ip_address": attrs.get("ip_address"),
            "mac_address": attrs.get("mac_address"),
        }

        missing = [k for k, v in required_attrs.items() if not v]
        complete = len(missing) == 0

        for key, value in required_attrs.items():
            status = "✓" if value else "✗"
            print(f"  {status} {key}: {value or 'Missing'}")

        result = {
            "test": "Device Information",
            "passed": complete,
            "details": {"attributes": required_attrs, "missing": missing},
        }

        if complete:
            self.print_success("All device information present")
        else:
            self.print_failure(f"Missing attributes: {', '.join(missing)}")

        return result

    def test_device(self, device: dict[str, Any]) -> list[dict[str, Any]]:
        """Run all tests on a device."""
        entity_id = device["entity_id"]
        attrs = device.get("attributes", {})
        device_name = attrs.get("friendly_name", entity_id)

        self.print_header(f"Testing: {device_name}", char="-")

        results = []

        # Skip if device is unavailable
        if device["state"] == "unavailable":
            self.print_warning(f"Device {device_name} is unavailable - skipping tests")
            return [{"test": "All Tests", "passed": False, "details": {"error": "Device unavailable"}}]

        # Run tests
        results.append(self.test_device_availability(device))
        results.append(self.test_device_info(device))
        results.append(self.test_volume_control(device))
        results.append(self.test_mute_control(device))
        results.append(self.test_source_selection(device))

        # Summary for this device
        passed = sum(1 for r in results if r["passed"] is True)
        total = sum(1 for r in results if r["passed"] is not None)

        print(f"\n{Colors.BOLD}Device Test Summary:{Colors.RESET}")
        print(f"  {passed}/{total} tests passed")

        return results

    def run_all_tests(self) -> dict[str, Any]:
        """Run complete test suite."""
        self.start_time = datetime.now()

        self.print_header("WiiM Real Device Test Suite")
        print(f"{Colors.CYAN}Home Assistant: {self.ha_url}{Colors.RESET}")
        print(f"{Colors.CYAN}Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}{Colors.RESET}\n")

        # Check connection
        if not self.check_connection():
            return {"error": "Connection failed"}

        # Discover devices
        devices = self.discover_devices()
        if not devices:
            return {"error": "No devices found"}

        # Test each device
        all_results = {}
        for device in devices:
            entity_id = device["entity_id"]
            results = self.test_device(device)
            all_results[entity_id] = {
                "device_name": device.get("attributes", {}).get("friendly_name"),
                "model": device.get("attributes", {}).get("device_model"),
                "tests": results,
            }
            time.sleep(2)  # Pause between devices

        # Overall summary
        self.print_header("Test Suite Summary")

        total_devices = len(devices)
        total_tests = 0
        passed_tests = 0

        for _entity_id, data in all_results.items():
            device_name = data["device_name"]
            tests = data["tests"]
            device_passed = sum(1 for t in tests if t["passed"] is True)
            device_total = sum(1 for t in tests if t["passed"] is not None)

            total_tests += device_total
            passed_tests += device_passed

            status = f"{device_passed}/{device_total}"
            color = Colors.GREEN if device_passed == device_total else Colors.YELLOW
            print(f"{color}{device_name}: {status} tests passed{Colors.RESET}")

        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        print(f"\n{Colors.BOLD}Overall Results:{Colors.RESET}")
        print(f"  Devices Tested:   {total_devices}")
        print(f"  Total Tests:      {total_tests}")
        print(f"  Tests Passed:     {passed_tests}")
        print(f"  Success Rate:     {(passed_tests / total_tests * 100):.1f}%")
        print(f"  Duration:         {duration:.1f}s")

        # Save results to file
        report = {
            "timestamp": self.start_time.isoformat(),
            "ha_url": self.ha_url,
            "devices_tested": total_devices,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
            "duration_seconds": duration,
            "results": all_results,
        }

        filename = f"wiim_test_report_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(report, f, indent=2)

        self.print_success(f"Test report saved to: {filename}")

        return report


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WiiM Integration - Real Device Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with environment variable token
  export HA_TOKEN="your_token_here"
  python test-real-devices.py http://homeassistant.local:8123

  # Test with command line token
  python test-real-devices.py http://homeassistant.local:8123 --token YOUR_TOKEN

  # Test local HA instance
  python test-real-devices.py http://localhost:8123 --token YOUR_TOKEN
        """,
    )

    parser.add_argument(
        "ha_url",
        nargs="?",
        default="http://homeassistant.local:8123",
        help="Home Assistant URL (default: http://homeassistant.local:8123)",
    )
    parser.add_argument("--token", help="Home Assistant long-lived access token (or set HA_TOKEN env var)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Create and run test suite
    suite = WiiMRealDeviceTestSuite(args.ha_url, args.token)

    try:
        report = suite.run_all_tests()

        # Exit with appropriate code
        if "error" in report:
            sys.exit(1)
        elif report.get("success_rate", 0) == 1.0:
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Test suite interrupted by user{Colors.RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {e}{Colors.RESET}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
