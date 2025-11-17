#!/usr/bin/env python3
"""
WiiM Integration - Advanced Features Test Suite
Tests multiroom, EQ, output selection, TTS, and more!
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import requests


# Import Colors from basic test script
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class WiiMAdvancedTestSuite:
    """Advanced features test suite for WiiM devices."""

    def __init__(self, ha_url: str, token: str):
        self.ha_url = ha_url.rstrip("/")
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self.devices = []
        self.test_results = []

    def print_header(self, text: str, char: str = "="):
        """Print formatted header."""
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

    def print_info(self, text: str):
        print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")

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

    def get_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity state."""
        try:
            url = f"{self.ha_url}/api/states/{entity_id}"
            response = requests.get(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"    {Colors.RED}Failed to get state: {e}{Colors.RESET}")
            return None

    def discover_devices(self) -> List[Dict[str, Any]]:
        """Discover WiiM devices."""
        self.print_header("Device Discovery")

        response = requests.get(f"{self.ha_url}/api/states", headers=self.headers)
        all_states = response.json()

        wiim_devices = [
            state
            for state in all_states
            if state["entity_id"].startswith("media_player.")
            and state.get("attributes", {}).get("integration_purpose") == "individual_speaker_control"
        ]

        self.print_success(f"Found {len(wiim_devices)} WiiM device(s)\n")
        self.devices = wiim_devices
        return wiim_devices

    def test_eq_control(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Test EQ preset selection."""
        entity_id = device["entity_id"]
        attrs = device.get("attributes", {})

        print(f"\n{Colors.BOLD}Test: EQ Control{Colors.RESET}")

        sound_modes = attrs.get("sound_mode_list", [])
        current_mode = attrs.get("sound_mode", "Flat")

        if not sound_modes or len(sound_modes) < 2:
            self.print_warning("Not enough EQ presets (skipping)")
            return {"test": "EQ Control", "passed": None, "details": {"skipped": True}}

        print(f"  Available EQ presets: {len(sound_modes)}")
        print(f"  Current: {current_mode}")

        # Pick different EQ preset
        test_eq = "Jazz" if current_mode != "Jazz" else "Rock"
        print(f"  Switching to: {test_eq}")

        # Call service
        success = self.call_service("media_player", "select_sound_mode", entity_id, sound_mode=test_eq)
        time.sleep(4)  # Wait for state update

        # Verify
        new_state = self.get_state(entity_id)
        new_mode = new_state.get("attributes", {}).get("sound_mode")
        eq_changed = new_mode == test_eq

        print(f"  New EQ: {new_mode}")

        # Restore original
        if current_mode:
            self.call_service("media_player", "select_sound_mode", entity_id, sound_mode=current_mode)
            time.sleep(2)

        result = {
            "test": "EQ Control",
            "passed": eq_changed,
            "details": {
                "original": current_mode,
                "test_eq": test_eq,
                "actual": new_mode,
                "available_presets": len(sound_modes),
            },
        }

        if eq_changed:
            self.print_success(f"EQ control works ({len(sound_modes)} presets available)")
        else:
            self.print_failure(f"EQ didn't change (expected {test_eq}, got {new_mode})")

        return result

    def test_shuffle_repeat(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Test shuffle and repeat control."""
        entity_id = device["entity_id"]
        attrs = device.get("attributes", {})

        print(f"\n{Colors.BOLD}Test: Shuffle & Repeat Control{Colors.RESET}")

        original_shuffle = attrs.get("shuffle", False)
        original_repeat = attrs.get("repeat", "off")

        print(f"  Original shuffle: {original_shuffle}")
        print(f"  Original repeat: {original_repeat}")

        # Test shuffle
        print("  Setting shuffle: ON")
        shuffle_success = self.call_service("media_player", "shuffle_set", entity_id, shuffle=True)
        time.sleep(4)

        state = self.get_state(entity_id)
        new_shuffle = state.get("attributes", {}).get("shuffle", False)
        shuffle_works = new_shuffle == True

        print(f"  New shuffle: {new_shuffle}")

        # Test repeat
        print("  Setting repeat: one")
        repeat_success = self.call_service("media_player", "repeat_set", entity_id, repeat="one")
        time.sleep(4)

        state = self.get_state(entity_id)
        new_repeat = state.get("attributes", {}).get("repeat", "off")
        repeat_works = new_repeat == "one"

        print(f"  New repeat: {new_repeat}")

        # Restore
        self.call_service("media_player", "shuffle_set", entity_id, shuffle=original_shuffle)
        self.call_service("media_player", "repeat_set", entity_id, repeat=original_repeat)

        result = {
            "test": "Shuffle & Repeat",
            "passed": shuffle_works and repeat_works,
            "details": {"shuffle_works": shuffle_works, "repeat_works": repeat_works},
        }

        if shuffle_works and repeat_works:
            self.print_success("Shuffle & Repeat control works")
        else:
            self.print_failure(f"Shuffle: {shuffle_works}, Repeat: {repeat_works}")

        return result

    def test_multiroom_grouping(self, devices: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Test multiroom join/unjoin."""
        print(f"\n{Colors.BOLD}Test: Multiroom Grouping{Colors.RESET}")

        if len(devices) < 2:
            self.print_warning("Need at least 2 devices for multiroom testing (skipping)")
            return {"test": "Multiroom Grouping", "passed": None, "details": {"skipped": True}}

        master = devices[0]["entity_id"]
        slave = devices[1]["entity_id"]

        master_name = devices[0]["attributes"].get("friendly_name")
        slave_name = devices[1]["attributes"].get("friendly_name")

        print(f"  Master: {master_name}")
        print(f"  Slave: {slave_name}")

        # Test JOIN
        print("\n  Creating group...")
        join_success = self.call_service("media_player", "join", master, group_members=[slave])
        time.sleep(6)  # Group formation takes longer

        # Verify group
        master_state = self.get_state(master)
        group_members = master_state.get("attributes", {}).get("group_members", [])
        group_formed = slave in group_members

        print(f"  Group members: {group_members}")

        if group_formed:
            self.print_success("Group formation works")
        else:
            self.print_warning("Group not formed")

        # Test UNJOIN
        print("\n  Ungrouping...")
        unjoin_success = self.call_service("media_player", "unjoin", slave)
        time.sleep(6)

        # Verify ungrouped
        slave_state = self.get_state(slave)
        role = slave_state.get("attributes", {}).get("group_role", "solo")
        ungrouped = role == "solo"

        print(f"  Slave role after unjoin: {role}")

        if ungrouped:
            self.print_success("Ungroup works")
        else:
            self.print_warning("Device still in group")

        result = {
            "test": "Multiroom Grouping",
            "passed": group_formed and ungrouped,
            "details": {
                "master": master_name,
                "slave": slave_name,
                "group_formed": group_formed,
                "ungrouped": ungrouped,
            },
        }

        return result

    def test_tts(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Test TTS (Text-to-Speech) functionality."""
        entity_id = device["entity_id"]

        print(f"\n{Colors.BOLD}Test: TTS (Text-to-Speech){Colors.RESET}")

        # Store original volume
        state = self.get_state(entity_id)
        original_volume = state.get("attributes", {}).get("volume_level", 0.3)

        # Play TTS announcement
        print("  Playing TTS announcement...")
        tts_message = "This is a test of the WiiM text to speech system"

        success = self.call_service(
            "media_player",
            "play_media",
            entity_id,
            media_content_type="music",
            media_content_id=f"media-source://tts?message={tts_message}",
            announce=True,
        )

        if not success:
            self.print_failure("TTS service call failed")
            return {"test": "TTS", "passed": False, "details": {"error": "Service call failed"}}

        time.sleep(3)

        # Check if device is playing
        new_state = self.get_state(entity_id)
        is_playing = new_state.get("state") == "playing"

        result = {
            "test": "TTS",
            "passed": success and is_playing,
            "details": {"service_accepted": success, "playback_started": is_playing, "message": tts_message},
        }

        if success:
            self.print_success("TTS announcement sent")
            if is_playing:
                print("    Device is playing TTS")
            else:
                print("    Device accepted but playback status unclear")
        else:
            self.print_failure("TTS failed")

        # Wait for TTS to complete
        time.sleep(5)

        # Stop to end TTS
        self.call_service("media_player", "media_stop", entity_id)

        return result

    def test_preset_playback(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Test preset playback."""
        entity_id = device["entity_id"]

        print(f"\n{Colors.BOLD}Test: Preset Playback{Colors.RESET}")

        print("  Playing preset #1...")
        success = self.call_service("wiim", "play_preset", entity_id, preset=1)

        if not success:
            return {"test": "Preset Playback", "passed": False, "details": {"error": "Service call failed"}}

        time.sleep(6)  # Presets take time to load

        # Check if playing
        state = self.get_state(entity_id)
        is_playing = state.get("state") == "playing"

        print(f"  State after preset: {state.get('state')}")

        # Stop playback
        if is_playing:
            self.call_service("media_player", "media_stop", entity_id)
            time.sleep(2)

        result = {
            "test": "Preset Playback",
            "passed": is_playing,
            "details": {"preset": 1, "playback_started": is_playing},
        }

        if is_playing:
            self.print_success("Preset playback works")
        else:
            self.print_warning("Preset didn't start playing (may not be configured)")

        return result

    def test_audio_output_mode(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Test audio output mode selection."""
        entity_id = device["entity_id"]
        device_name = device["attributes"].get("friendly_name")

        print(f"\n{Colors.BOLD}Test: Audio Output Mode{Colors.RESET}")

        # Check for output mode select entity
        output_entity = f"{entity_id}_audio_output_mode"

        # Try to get the select entity state
        select_state = self.get_state(output_entity)

        if not select_state:
            self.print_warning("Audio output mode select entity not found (skipping)")
            return {"test": "Audio Output Mode", "passed": None, "details": {"skipped": True}}

        options = select_state.get("attributes", {}).get("options", [])
        current = select_state.get("state")

        print(f"  Available modes: {options}")
        print(f"  Current mode: {current}")

        if len(options) < 2:
            self.print_warning("Not enough output modes to test")
            return {"test": "Audio Output Mode", "passed": None, "details": {"skipped": True}}

        # Pick different mode
        test_mode = options[0] if options[0] != current else options[1]
        print(f"  Switching to: {test_mode}")

        # Call service
        success = self.call_service("select", "select_option", output_entity, option=test_mode)
        time.sleep(4)

        # Verify
        new_state = self.get_state(output_entity)
        new_mode = new_state.get("state")
        mode_changed = new_mode == test_mode

        print(f"  New mode: {new_mode}")

        # Restore
        if current:
            self.call_service("select", "select_option", output_entity, option=current)
            time.sleep(2)

        result = {
            "test": "Audio Output Mode",
            "passed": mode_changed,
            "details": {"original": current, "test_mode": test_mode, "actual": new_mode, "available_modes": options},
        }

        if mode_changed:
            self.print_success("Audio output mode selection works")
        else:
            self.print_failure(f"Mode didn't change (expected {test_mode}, got {new_mode})")

        return result

    def test_url_playback(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Test URL playback."""
        entity_id = device["entity_id"]

        print(f"\n{Colors.BOLD}Test: URL Playback{Colors.RESET}")

        # Play internet radio
        test_url = "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_two"
        print(f"  Playing: BBC Radio 2")

        success = self.call_service("wiim", "play_url", entity_id, url=test_url)
        time.sleep(6)  # URL loading takes time

        # Check if playing
        state = self.get_state(entity_id)
        is_playing = state.get("state") == "playing"
        media_title = state.get("attributes", {}).get("media_title", "None")

        print(f"  State: {state.get('state')}")
        print(f"  Media title: {media_title}")

        # Stop playback
        if is_playing:
            self.call_service("media_player", "media_stop", entity_id)
            time.sleep(2)

        result = {
            "test": "URL Playback",
            "passed": is_playing,
            "details": {"url": test_url, "playback_started": is_playing, "media_title": media_title},
        }

        if is_playing:
            self.print_success("URL playback works")
        else:
            self.print_warning("URL didn't start playing (check network/stream)")

        return result

    def run_advanced_tests(self):
        """Run all advanced feature tests."""
        self.print_header("WiiM Advanced Features Test Suite")

        # Discover devices
        devices = self.discover_devices()
        if not devices:
            print("No devices found!")
            return

        all_results = {}

        # Test each device
        for device in devices:
            entity_id = device["entity_id"]
            device_name = device["attributes"].get("friendly_name")

            self.print_header(f"Testing: {device_name}", char="-")

            results = []
            results.append(self.test_eq_control(device))
            results.append(self.test_shuffle_repeat(device))
            results.append(self.test_preset_playback(device))
            results.append(self.test_url_playback(device))
            results.append(self.test_audio_output_mode(device))

            # Summary for this device
            passed = sum(1 for r in results if r["passed"] is True)
            total = sum(1 for r in results if r["passed"] is not None)

            print(f"\n{Colors.BOLD}Device Test Summary: {passed}/{total} tests passed{Colors.RESET}")

            all_results[entity_id] = {"device_name": device_name, "tests": results}

            time.sleep(2)

        # Multiroom test (requires multiple devices)
        if len(devices) >= 2:
            self.print_header("Multiroom Testing", char="-")
            multiroom_result = self.test_multiroom_grouping(devices)
            # Add to first device results
            first_device = devices[0]["entity_id"]
            all_results[first_device]["tests"].append(multiroom_result)

        # TTS test (on first device)
        if devices:
            first_device_data = devices[0]
            self.print_header(f"TTS Testing: {first_device_data['attributes'].get('friendly_name')}", char="-")
            tts_result = self.test_tts(first_device_data)
            first_device = first_device_data["entity_id"]
            all_results[first_device]["tests"].append(tts_result)

        # Overall summary
        self.print_header("Advanced Test Suite Summary")

        total_tests = 0
        passed_tests = 0

        for entity_id, data in all_results.items():
            device_name = data["device_name"]
            tests = data["tests"]
            device_passed = sum(1 for t in tests if t["passed"] is True)
            device_total = sum(1 for t in tests if t["passed"] is not None)

            total_tests += device_total
            passed_tests += device_passed

            color = Colors.GREEN if device_passed == device_total else Colors.YELLOW
            print(f"{color}{device_name}: {device_passed}/{device_total} tests passed{Colors.RESET}")

        print(f"\n{Colors.BOLD}Overall Results:{Colors.RESET}")
        print(f"  Tests Run:        {total_tests}")
        print(f"  Tests Passed:     {passed_tests}")
        print(f"  Success Rate:     {(passed_tests / total_tests * 100):.1f}%")

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"wiim_advanced_test_report_{timestamp}.json"

        report = {
            "timestamp": datetime.now().isoformat(),
            "test_type": "advanced_features",
            "devices_tested": len(devices),
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
            "results": all_results,
        }

        with open(filename, "w") as f:
            json.dump(report, f, indent=2)

        self.print_success(f"Test report saved to: {filename}")

        return report


def main():
    parser = argparse.ArgumentParser(description="WiiM Advanced Features Test Suite")
    parser.add_argument("ha_url", nargs="?", default="http://localhost:8123")
    parser.add_argument("--token", help="HA access token (or set HA_TOKEN env var)")

    args = parser.parse_args()

    token = args.token or os.getenv("HA_TOKEN")
    if not token:
        print(f"{Colors.RED}❌ No access token provided!{Colors.RESET}")
        sys.exit(1)

    suite = WiiMAdvancedTestSuite(args.ha_url, token)
    suite.run_advanced_tests()


if __name__ == "__main__":
    main()
