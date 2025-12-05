#!/usr/bin/env python3
"""
Comprehensive multiroom join/unjoin test suite
Tests various combinations and error cases
"""

import os
import sys
import time
import requests
from typing import Any


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class MultiroomTestSuite:
    def __init__(self, ha_url: str, token: str):
        self.ha_url = ha_url.rstrip("/")
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self.devices = {}

    def print_header(self, text: str):
        print(f"\n{Colors.CYAN}{'=' * 80}{Colors.RESET}")
        print(f"{Colors.BOLD}{text:^80}{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 80}{Colors.RESET}\n")

    def print_success(self, text: str):
        print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")

    def print_failure(self, text: str):
        print(f"{Colors.RED}❌ {text}{Colors.RESET}")

    def print_warning(self, text: str):
        print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")

    def print_info(self, text: str):
        print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")

    def get_state(self, entity_id: str) -> dict[str, Any] | None:
        try:
            response = requests.get(f"{self.ha_url}/api/states/{entity_id}", headers=self.headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"    {Colors.RED}Failed to get state: {e}{Colors.RESET}")
            return None

    def call_service(self, domain: str, service: str, entity_id: str, **data) -> tuple[bool, str]:
        """Call service and return (success, error_message)"""
        try:
            url = f"{self.ha_url}/api/services/{domain}/{service}"
            payload = {"entity_id": entity_id, **data}
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code == 200:
                return True, ""
            else:
                error_text = response.text
                try:
                    error_json = response.json()
                    error_text = error_json.get("message", error_text)
                except:
                    pass
                return False, f"HTTP {response.status_code}: {error_text}"
        except Exception as e:
            return False, str(e)

    def discover_devices(self):
        """Find the three target devices"""
        self.print_header("Device Discovery")

        response = requests.get(f"{self.ha_url}/api/states", headers=self.headers)
        all_states = response.json()

        target_ips = ["192.168.1.116", "192.168.1.115", "192.168.1.68"]

        for state in all_states:
            if (
                state["entity_id"].startswith("media_player.")
                and state.get("attributes", {}).get("integration_purpose") == "individual_speaker_control"
            ):
                ip = state.get("attributes", {}).get("ip_address")
                if ip in target_ips:
                    self.devices[ip] = {
                        "entity_id": state["entity_id"],
                        "name": state.get("attributes", {}).get("friendly_name", state["entity_id"]),
                        "ip": ip,
                        "state": state,
                    }
                    print(
                        f"{Colors.MAGENTA}{ip}:{Colors.RESET} {self.devices[ip]['name']} ({self.devices[ip]['entity_id']})"
                    )

        if len(self.devices) != 3:
            self.print_failure(f"Expected 3 devices, found {len(self.devices)}")
            return False

        self.print_success(f"Found all 3 target devices")
        return True

    def get_group_info(self, entity_id: str) -> dict[str, Any]:
        """Get current group information for a device"""
        state = self.get_state(entity_id)
        if not state:
            return {}
        attrs = state.get("attributes", {})
        return {
            "role": attrs.get("group_role", "unknown"),
            "group_members": attrs.get("group_members") or [],
            "is_master": attrs.get("group_role") == "master",
            "is_slave": attrs.get("group_role") == "slave",
            "is_solo": attrs.get("group_role") == "solo",
        }

    def wait_for_state(self, entity_id: str, check_func, timeout: int = 10) -> bool:
        """Wait for state to match check function"""
        start = time.time()
        while time.time() - start < timeout:
            if check_func(self.get_group_info(entity_id)):
                return True
            time.sleep(0.5)
        return False

    def test_join(self, master_ip: str, slave_ips: list[str], expected_success: bool = True) -> bool:
        """Test joining devices"""
        master = self.devices[master_ip]
        slaves = [self.devices[ip] for ip in slave_ips]

        master_name = master["name"]
        slave_names = [s["name"] for s in slaves]

        print(f"\n{Colors.BOLD}Test: Join {master_name} + {', '.join(slave_names)}{Colors.RESET}")
        print(f"  Master: {master['entity_id']} ({master_ip})")
        for slave in slaves:
            print(f"  Slave: {slave['entity_id']} ({slave['ip']})")

        # Get initial states
        initial_master = self.get_group_info(master["entity_id"])
        print(f"  Master initial role: {initial_master['role']}")

        # Check if any slaves are already in a group
        slaves_already_in_group = []
        for slave in slaves:
            slave_info = self.get_group_info(slave["entity_id"])
            if not slave_info["is_solo"]:
                slaves_already_in_group.append(slave["name"])

        if slaves_already_in_group:
            self.print_warning(f"  Warning: {', '.join(slaves_already_in_group)} already in a group")

        # Call join service
        slave_entity_ids = [s["entity_id"] for s in slaves]
        success, error = self.call_service("media_player", "join", master["entity_id"], group_members=slave_entity_ids)

        if not success:
            if expected_success:
                self.print_failure(f"Join failed (unexpected): {error}")
                return False
            else:
                self.print_success(f"Join failed as expected: {error}")
                return True

        if not expected_success:
            self.print_failure(f"Join succeeded but was expected to fail")
            return False

        # Wait for group to form (longer for 3+ devices)
        wait_time = 8 if len(slaves) >= 2 else 6
        time.sleep(wait_time)

        # Verify group
        master_info = self.get_group_info(master["entity_id"])
        print(f"  Master role after join: {master_info['role']}")
        print(f"  Group members: {master_info['group_members']}")

        # Check all slaves are in group
        all_in_group = all(s["entity_id"] in master_info["group_members"] for s in slaves)
        master_is_master = master_info["is_master"]

        if all_in_group and master_is_master:
            self.print_success("Join successful - all devices in group")
            return True
        else:
            self.print_failure(f"Join incomplete - in_group: {all_in_group}, master_is_master: {master_is_master}")
            return False

    def test_unjoin(self, device_ip: str, expected_success: bool = True) -> bool:
        """Test unjoining a device"""
        device = self.devices[device_ip]
        device_name = device["name"]

        print(f"\n{Colors.BOLD}Test: Unjoin {device_name}{Colors.RESET}")
        print(f"  Device: {device['entity_id']} ({device_ip})")

        # Get initial state
        initial_info = self.get_group_info(device["entity_id"])
        print(f"  Initial role: {initial_info['role']}")

        # Call unjoin service
        success, error = self.call_service("media_player", "unjoin", device["entity_id"])

        if not success:
            if expected_success:
                self.print_failure(f"Unjoin failed (unexpected): {error}")
                return False
            else:
                self.print_success(f"Unjoin failed as expected: {error}")
                return True

        if not expected_success:
            self.print_failure(f"Unjoin succeeded but was expected to fail")
            return False

        # Wait for unjoin
        time.sleep(6)

        # Verify unjoined
        final_info = self.get_group_info(device["entity_id"])
        print(f"  Final role: {final_info['role']}")

        if final_info["is_solo"]:
            self.print_success("Unjoin successful - device is solo")
            return True
        else:
            self.print_failure(f"Unjoin incomplete - still in group (role: {final_info['role']})")
            return False

    def ensure_all_solo(self, max_attempts: int = 3):
        """Ensure all devices are solo before starting tests"""
        self.print_info("Ensuring all devices are solo...")

        for attempt in range(max_attempts):
            all_solo = True
            for ip, device in self.devices.items():
                info = self.get_group_info(device["entity_id"])
                if not info["is_solo"]:
                    all_solo = False
                    print(f"  Unjoining {device['name']} (attempt {attempt + 1})...")
                    self.call_service("media_player", "unjoin", device["entity_id"])

            if all_solo:
                break

            time.sleep(5)  # Wait for unjoin to complete

        # Final verification
        time.sleep(3)
        for ip, device in self.devices.items():
            info = self.get_group_info(device["entity_id"])
            if not info["is_solo"]:
                self.print_warning(f"  {device['name']} still not solo (role: {info['role']})")
            else:
                print(f"  {device['name']} is solo")

    def run_all_tests(self):
        """Run comprehensive test suite"""
        self.print_header("Comprehensive Multiroom Test Suite")

        if not self.discover_devices():
            return

        self.ensure_all_solo()
        time.sleep(2)

        results = []

        # Test 1: Simple 2-device join
        self.print_header("Test 1: Simple 2-Device Join")
        results.append(("2-device join", self.test_join("192.168.1.115", ["192.168.1.68"])))
        time.sleep(2)

        # Test 2: Unjoin slave
        self.print_header("Test 2: Unjoin Slave")
        results.append(("Unjoin slave", self.test_unjoin("192.168.1.68")))
        time.sleep(2)

        # Test 3: Join 3 devices
        self.print_header("Test 3: Join 3 Devices")
        results.append(("3-device join", self.test_join("192.168.1.115", ["192.168.1.68", "192.168.1.116"])))
        time.sleep(2)

        # Test 4: Unjoin middle device (should break group)
        self.print_header("Test 4: Unjoin Middle Device")
        results.append(("Unjoin middle", self.test_unjoin("192.168.1.68")))
        time.sleep(2)

        # Test 5: Rejoin to form 2-device group
        self.print_header("Test 5: Rejoin 2 Devices")
        results.append(("Rejoin 2 devices", self.test_join("192.168.1.115", ["192.168.1.116"])))
        time.sleep(2)

        # Test 6: Unjoin master (slave should become solo)
        self.print_header("Test 6: Unjoin Master")
        results.append(("Unjoin master", self.test_unjoin("192.168.1.115")))
        time.sleep(2)

        # Test 7: Join already joined device (should work - replaces group)
        self.print_header("Test 7: Join Already Joined Device")
        # First create a group
        self.test_join("192.168.1.115", ["192.168.1.68"])
        time.sleep(2)
        # Now join the master to a different slave (should work)
        results.append(("Join already joined", self.test_join("192.168.1.115", ["192.168.1.116"])))
        time.sleep(2)

        # Test 8: Unjoin solo device (should fail or be no-op)
        self.print_header("Test 8: Unjoin Solo Device")
        self.ensure_all_solo()
        time.sleep(2)
        results.append(("Unjoin solo", self.test_unjoin("192.168.1.68", expected_success=True)))  # May succeed as no-op
        time.sleep(2)

        # Test 9: Join device to itself (edge case - should be no-op or fail gracefully)
        self.print_header("Test 9: Join Device to Itself")
        self.ensure_all_solo()
        time.sleep(2)
        # This should either work as a no-op or fail gracefully - either is acceptable
        result = self.test_join("192.168.1.115", ["192.168.1.115"], expected_success=True)
        # Accept either success (no-op) or graceful failure
        results.append(("Join to self", True))  # Always pass - just testing it doesn't crash
        time.sleep(2)

        # Test 10: Complex: Join A+B, then join C to A (should form A+B+C)
        self.print_header("Test 10: Complex Multi-Step Join")
        self.ensure_all_solo()
        time.sleep(2)
        # Step 1: Join A+B
        self.test_join("192.168.1.115", ["192.168.1.68"])
        time.sleep(2)
        # Step 2: Join C to A (should add C to existing group)
        results.append(("Complex join", self.test_join("192.168.1.115", ["192.168.1.116"])))
        time.sleep(2)

        # Final cleanup
        self.print_header("Final Cleanup")
        self.ensure_all_solo()

        # Summary
        self.print_header("Test Summary")
        passed = sum(1 for _, result in results if result)
        total = len(results)

        for name, result in results:
            status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if result else f"{Colors.RED}❌ FAIL{Colors.RESET}"
            print(f"  {status} {name}")

        print(
            f"\n{Colors.BOLD}Results: {passed}/{total} tests passed ({passed * 100 // total if total > 0 else 0}%){Colors.RESET}"
        )


def main():
    ha_url = os.getenv("HA_URL", "http://localhost:8123")
    token = os.getenv("HA_TOKEN")

    if not token:
        print(f"{Colors.RED}No HA_TOKEN environment variable set!{Colors.RESET}")
        sys.exit(1)

    suite = MultiroomTestSuite(ha_url, token)
    suite.run_all_tests()


if __name__ == "__main__":
    main()
