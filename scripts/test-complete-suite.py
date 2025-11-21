#!/usr/bin/env python3
"""
WiiM Integration - Complete Test Suite
Tests ALL features with AirPlay detection and safe volume limits
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
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class WiiMCompleteTestSuite:
    """Complete test suite with AirPlay handling and safe volumes."""

    MAX_VOLUME = 0.10  # 10% maximum for safety

    def __init__(self, ha_url: str, token: str):
        self.ha_url = ha_url.rstrip("/")
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self.devices = []
        self.test_results = {}

    def print_header(self, text: str, char: str = "="):
        width = 80
        print(f"\n{Colors.CYAN}{char * width}{Colors.RESET}")
        print(f"{Colors.BOLD}{text:^{width}}{Colors.RESET}")
        print(f"{Colors.CYAN}{char * width}{Colors.RESET}\n")

    def print_success(self, text: str):
        print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")

    def print_failure(self, text: str):
        print(f"{Colors.RED}❌ {text}{Colors.RESET}")

    def print_warning(self, text: str):
        print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")

    def call_service(self, domain: str, service: str, entity_id: str, **data) -> bool:
        try:
            url = f"{self.ha_url}/api/services/{domain}/{service}"
            payload = {"entity_id": entity_id, **data}
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"    {Colors.RED}Service error: {e}{Colors.RESET}")
            return False

    def get_state(self, entity_id: str) -> dict[str, Any] | None:
        try:
            response = requests.get(f"{self.ha_url}/api/states/{entity_id}", headers=self.headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    def discover_devices(self) -> list[dict]:
        self.print_header("Device Discovery")

        response = requests.get(f"{self.ha_url}/api/states", headers=self.headers)
        all_states = response.json()

        devices = [
            state
            for state in all_states
            if state["entity_id"].startswith("media_player.")
            and state.get("attributes", {}).get("integration_purpose") == "individual_speaker_control"
        ]

        self.print_success(f"Found {len(devices)} WiiM device(s)\n")

        for i, device in enumerate(devices, 1):
            attrs = device["attributes"]
            source = attrs.get("source", "None")
            is_airplay = source == "AirPlay"

            print(f"{Colors.MAGENTA}Device {i}: {attrs.get('friendly_name')}{Colors.RESET}")
            print(f"  State: {device['state']}")
            print(f"  Source: {source} {'🔒 AirPlay Active!' if is_airplay else ''}")
            print()

        self.devices = devices
        return devices

    def test_all_features(self, device: dict) -> list[dict]:
        """Test ALL features on a device."""
        device["entity_id"]
        attrs = device["attributes"]
        device_name = attrs.get("friendly_name")
        source = attrs.get("source")
        is_airplay = source == "AirPlay"
        # Note: is_playing check removed as it was unused

        self.print_header(f"Testing: {device_name}", char="-")

        if device["state"] == "unavailable":
            self.print_warning("Device unavailable - skipping")
            return [{"test": "All", "passed": False, "details": {"error": "Unavailable"}}]

        # AirPlay warning
        if is_airplay:
            self.print_warning("AirPlay is active! Playback controls will be locked.")
            print("    Only hardware controls (volume/mute) will work.")
            print("    To test ALL features, disconnect AirPlay first.\n")

        results = []

        # Always test these (work in any state)
        results.append(self.test_availability(device))
        results.append(self.test_device_info(device))
        results.append(self.test_volume_safe(device))
        results.append(self.test_mute(device))
        results.append(self.test_tts(device))

        # Only test these if not AirPlay
        if not is_airplay:
            results.append(self.test_eq(device))
            results.append(self.test_shuffle(device))
            results.append(self.test_repeat(device))
            results.append(self.test_source(device))
            results.append(self.test_output_mode(device))
        else:
            print(f"{Colors.YELLOW}Skipping EQ/shuffle/repeat/source/output (AirPlay active){Colors.RESET}\n")

        # Summary
        passed = sum(1 for r in results if r["passed"] is True)
        total = sum(1 for r in results if r["passed"] is not None)

        print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.RESET}")

        return results

    def test_availability(self, device: dict) -> dict:
        print(f"\n{Colors.BOLD}✓ Device Availability{Colors.RESET}")
        available = device["state"] != "unavailable"
        if available:
            self.print_success("Available")
        return {"test": "Availability", "passed": available, "details": {}}

    def test_device_info(self, device: dict) -> dict:
        print(f"\n{Colors.BOLD}✓ Device Information{Colors.RESET}")
        attrs = device["attributes"]
        required = ["device_model", "firmware_version", "ip_address", "mac_address"]
        complete = all(attrs.get(k) for k in required)
        if complete:
            self.print_success("Complete")
        return {"test": "Device Info", "passed": complete, "details": {}}

    def test_volume_safe(self, device: dict) -> dict:
        entity_id = device["entity_id"]
        print(f"\n{Colors.BOLD}✓ Volume Control (Safe - Max 10%){Colors.RESET}")

        state = self.get_state(entity_id)
        original = state["attributes"].get("volume_level", 0.5)

        # Safe test: max 10% change, never above 10%
        test_vol = min(0.08, original + 0.05)

        print(f"  Setting {int(test_vol * 100)}% (from {int(original * 100)}%)...")
        self.call_service("media_player", "volume_set", entity_id, volume_level=test_vol)
        time.sleep(4)

        new_state = self.get_state(entity_id)
        new_vol = new_state["attributes"].get("volume_level", 0)
        works = abs(new_vol - test_vol) < 0.05

        # Restore
        self.call_service("media_player", "volume_set", entity_id, volume_level=original)
        time.sleep(2)

        if works:
            self.print_success(f"Works (changed to {int(new_vol * 100)}%)")
        else:
            self.print_failure("Didn't change")

        return {"test": "Volume", "passed": works, "details": {}}

    def test_mute(self, device: dict) -> dict:
        entity_id = device["entity_id"]
        print(f"\n{Colors.BOLD}✓ Mute Control{Colors.RESET}")

        self.call_service("media_player", "volume_mute", entity_id, is_volume_muted=True)
        time.sleep(4)  # Proper wait time

        state = self.get_state(entity_id)
        muted = state["attributes"].get("is_volume_muted", False)

        # Unmute
        self.call_service("media_player", "volume_mute", entity_id, is_volume_muted=False)
        time.sleep(2)

        if muted:
            self.print_success("Works")
        else:
            self.print_failure("Didn't mute")

        return {"test": "Mute", "passed": muted, "details": {}}

    def test_eq(self, device: dict) -> dict:
        entity_id = device["entity_id"]
        print(f"\n{Colors.BOLD}✓ EQ Control{Colors.RESET}")

        state = self.get_state(entity_id)
        current_eq = state["attributes"].get("sound_mode", "Flat")
        test_eq = "Jazz" if current_eq != "Jazz" else "Rock"

        print(f"  {current_eq} → {test_eq}...")
        self.call_service("media_player", "select_sound_mode", entity_id, sound_mode=test_eq)
        time.sleep(5)

        new_state = self.get_state(entity_id)
        new_eq = new_state["attributes"].get("sound_mode")
        works = new_eq == test_eq

        # Restore
        self.call_service("media_player", "select_sound_mode", entity_id, sound_mode=current_eq)
        time.sleep(2)

        if works:
            self.print_success(f"Works (changed to {new_eq})")
        else:
            self.print_failure(f"Didn't change (still {new_eq})")

        return {"test": "EQ", "passed": works, "details": {}}

    def test_shuffle(self, device: dict) -> dict:
        entity_id = device["entity_id"]
        print(f"\n{Colors.BOLD}✓ Shuffle Control{Colors.RESET}")

        state = self.get_state(entity_id)
        current = state["attributes"].get("shuffle", False)
        test_val = not current

        print(f"  {current} → {test_val}...")
        self.call_service("media_player", "shuffle_set", entity_id, shuffle=test_val)
        time.sleep(5)

        new_state = self.get_state(entity_id)
        new_val = new_state["attributes"].get("shuffle", current)
        works = new_val == test_val

        # Restore
        self.call_service("media_player", "shuffle_set", entity_id, shuffle=current)
        time.sleep(2)

        if works:
            self.print_success(f"Works (changed to {new_val})")
        else:
            self.print_failure(f"Didn't change (still {new_val})")

        return {"test": "Shuffle", "passed": works, "details": {}}

    def test_repeat(self, device: dict) -> dict:
        entity_id = device["entity_id"]
        print(f"\n{Colors.BOLD}✓ Repeat Control{Colors.RESET}")

        state = self.get_state(entity_id)
        current = state["attributes"].get("repeat", "off")
        test_val = "one" if current != "one" else "all"

        print(f"  {current} → {test_val}...")
        self.call_service("media_player", "repeat_set", entity_id, repeat=test_val)
        time.sleep(5)

        new_state = self.get_state(entity_id)
        new_val = new_state["attributes"].get("repeat", current)
        works = new_val == test_val

        # Restore
        self.call_service("media_player", "repeat_set", entity_id, repeat=current)
        time.sleep(2)

        if works:
            self.print_success(f"Works (changed to {new_val})")
        else:
            self.print_failure(f"Didn't change (still {new_val})")

        return {"test": "Repeat", "passed": works, "details": {}}

    def test_source(self, device: dict) -> dict:
        entity_id = device["entity_id"]
        print(f"\n{Colors.BOLD}✓ Source Selection{Colors.RESET}")

        state = self.get_state(entity_id)
        sources = state["attributes"].get("source_list", [])
        current = state["attributes"].get("source")

        # Show diagnostic info about sources
        print(f"  Source list from HA: {sources}")
        print(f"  Current source: {current}")

        # Try to get diagnostics to see what pywiim is providing
        try:
            diagnostics_url = f"{self.ha_url}/api/diagnostics/device/{device.get('device_id', '')}"
            diag_response = requests.get(diagnostics_url, headers=self.headers, timeout=5)
            if diag_response.status_code == 200:
                diag_data = diag_response.json()
                source_diag = diag_data.get("source_list_diagnostics", {})
                if source_diag:
                    print(f"  Pywiim available_sources: {source_diag.get('available_sources_from_pywiim')}")
                    print(f"  Pywiim input_list: {source_diag.get('input_list_from_device_info')}")
        except Exception:
            pass  # Diagnostics not available, skip

        if len(sources) < 2:
            self.print_warning("Not enough sources")
            return {"test": "Source", "passed": None, "details": {"skipped": True}}

        test_source = sources[0] if sources[0] != current else sources[1]

        print(f"  {current} → {test_source}...")
        self.call_service("media_player", "select_source", entity_id, source=test_source)
        time.sleep(5)

        new_state = self.get_state(entity_id)
        new_source = new_state["attributes"].get("source")
        works = new_source == test_source

        if works:
            self.print_success(f"Works (switched to {new_source})")
        else:
            self.print_failure(f"Didn't switch (still {new_source})")

        return {"test": "Source", "passed": works, "details": {}}

    def test_output_mode(self, device: dict) -> dict:
        entity_id = device["entity_id"]
        print(f"\n{Colors.BOLD}✓ Audio Output Mode{Colors.RESET}")

        output_entity = f"select.{entity_id.split('.')[-1]}_audio_output_mode"
        state = self.get_state(output_entity)

        if not state:
            self.print_warning("Entity not found")
            return {"test": "Output Mode", "passed": None, "details": {"skipped": True}}

        options = state["attributes"].get("options", [])
        current = state["state"]

        if len(options) < 2:
            return {"test": "Output Mode", "passed": None, "details": {"skipped": True}}

        # Pick non-Bluetooth mode
        test_mode = next((m for m in options if m != current and "BT" not in m), options[0])

        print(f"  {current} → {test_mode}...")
        self.call_service("select", "select_option", output_entity, option=test_mode)
        time.sleep(5)

        new_state = self.get_state(output_entity)
        new_mode = new_state["state"]
        works = new_mode == test_mode

        # Restore
        self.call_service("select", "select_option", output_entity, option=current)
        time.sleep(2)

        if works:
            self.print_success(f"Works (changed to {new_mode})")
        else:
            self.print_failure(f"Didn't change (still {new_mode})")

        return {"test": "Output Mode", "passed": works, "details": {}}

    def test_tts(self, device: dict) -> dict:
        entity_id = device["entity_id"]
        print(f"\n{Colors.BOLD}✓ TTS{Colors.RESET}")

        success = self.call_service(
            "media_player",
            "play_media",
            entity_id,
            media_content_type="music",
            media_content_id="media-source://tts?message=WiiM test complete",
            announce=True,
        )

        if success:
            self.print_success("Service accepted")
            time.sleep(6)  # Let TTS play
            self.call_service("media_player", "media_stop", entity_id)
        else:
            self.print_failure("Service failed")

        return {"test": "TTS", "passed": success, "details": {}}

    def test_multiroom(self, devices: list[dict]) -> dict:
        if len(devices) < 2:
            return {"test": "Multiroom", "passed": None, "details": {"skipped": True}}

        self.print_header("Multiroom Testing", char="-")

        master = devices[0]["entity_id"]
        slave = devices[1]["entity_id"]

        # JOIN
        print(f"{Colors.BOLD}Creating group...{Colors.RESET}")
        self.call_service("media_player", "join", master, group_members=[slave])
        time.sleep(6)

        state = self.get_state(master)
        group_members = state["attributes"].get("group_members", [])
        joined = slave in group_members

        if joined:
            self.print_success("Group formed")

        # UNJOIN
        print(f"\n{Colors.BOLD}Ungrouping...{Colors.RESET}")
        self.call_service("media_player", "unjoin", slave)
        time.sleep(6)

        state = self.get_state(slave)
        role = state["attributes"].get("group_role", "solo")
        unjoined = role == "solo"

        if unjoined:
            self.print_success("Ungrouped")

        return {"test": "Multiroom", "passed": joined and unjoined, "details": {}}

    def run_complete_suite(self):
        """Run complete test suite."""
        self.print_header("WiiM Complete Test Suite")
        print(f"{Colors.CYAN}Safe Mode: Volume limited to {int(self.MAX_VOLUME * 100)}% max{Colors.RESET}")
        print(f"{Colors.CYAN}Proper Timing: 4-6 second waits for state changes{Colors.RESET}\n")

        devices = self.discover_devices()
        if not devices:
            print("No devices found!")
            return

        # Test each device
        for device in devices:
            entity_id = device["entity_id"]
            results = self.test_all_features(device)
            self.test_results[entity_id] = {
                "device_name": device["attributes"].get("friendly_name"),
                "source": device["attributes"].get("source"),
                "tests": results,
            }
            time.sleep(2)

        # Multiroom test
        if len(devices) >= 2:
            multiroom_result = self.test_multiroom(devices)
            self.test_results[devices[0]["entity_id"]]["tests"].append(multiroom_result)

        # Summary
        self.print_summary()

    def print_summary(self):
        self.print_header("Complete Test Suite Summary")

        total_tests = 0
        passed_tests = 0
        airplay_devices = 0

        for _entity_id, data in self.test_results.items():
            device_name = data["device_name"]
            is_airplay = data["source"] == "AirPlay"
            if is_airplay:
                airplay_devices += 1

            tests = data["tests"]
            device_passed = sum(1 for t in tests if t["passed"] is True)
            device_total = sum(1 for t in tests if t["passed"] is not None)

            total_tests += device_total
            passed_tests += device_passed

            color = Colors.GREEN if device_passed == device_total else Colors.YELLOW
            airplay_note = " 🔒 AirPlay" if is_airplay else ""
            print(f"{color}{device_name}: {device_passed}/{device_total} passed{airplay_note}{Colors.RESET}")

        print(f"\n{Colors.BOLD}Overall Results:{Colors.RESET}")
        print(f"  Tests Run:        {total_tests}")
        print(f"  Tests Passed:     {passed_tests}")
        print(f"  Success Rate:     {(passed_tests / total_tests * 100):.1f}%")
        print(f"  AirPlay Devices:  {airplay_devices}/{len(self.test_results)}")

        if airplay_devices > 0:
            print(f"\n{Colors.YELLOW}Note: {airplay_devices} device(s) have AirPlay active.{Colors.RESET}")
            print(f"{Colors.YELLOW}Disconnect AirPlay to test playback controls (EQ/shuffle/repeat).{Colors.RESET}")

        # Save report
        filename = f"wiim_complete_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
                    "airplay_active": airplay_devices,
                    "results": self.test_results,
                },
                f,
                indent=2,
            )

        self.print_success(f"Report saved: {filename}")


def main():
    parser = argparse.ArgumentParser(description="WiiM Complete Test Suite")
    parser.add_argument("ha_url", nargs="?", default="http://localhost:8123")
    parser.add_argument("--token", help="HA token (or set HA_TOKEN)")
    args = parser.parse_args()

    token = args.token or os.getenv("HA_TOKEN")
    if not token:
        print(f"{Colors.RED}No token! Set HA_TOKEN or use --token{Colors.RESET}")
        sys.exit(1)

    suite = WiiMCompleteTestSuite(args.ha_url, token)
    suite.run_complete_suite()


if __name__ == "__main__":
    main()
