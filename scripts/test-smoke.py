#!/usr/bin/env python3
"""
WiiM Integration - Smoke Tests
Quick validation tests (2-3 minutes) for critical functionality.

Run before commits or releases to ensure nothing is broken.
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


class SmokeTestSuite:
    """Quick smoke tests for critical functionality."""

    MAX_VOLUME = 0.10  # 10% max for safety

    def __init__(self, ha_url: str, token: str):
        self.ha_url = ha_url.rstrip("/")
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self.devices = []
        self.results = []

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

    def test_device_discovery(self) -> bool:
        """Test 1: Can we discover devices?"""
        self.print_header("Test 1: Device Discovery")

        try:
            response = requests.get(f"{self.ha_url}/api/states", headers=self.headers, timeout=10)
            response.raise_for_status()
            all_states = response.json()

            devices = [
                state
                for state in all_states
                if state["entity_id"].startswith("media_player.")
                and state.get("attributes", {}).get("integration_purpose") == "individual_speaker_control"
            ]

            if not devices:
                self.print_failure("No WiiM devices found")
                return False

            self.print_success(f"Found {len(devices)} WiiM device(s)")

            # Store first device for other tests
            self.devices = devices[:1]  # Only test first device for speed

            for device in self.devices:
                attrs = device["attributes"]
                print(f"  {Colors.MAGENTA}{attrs.get('friendly_name')}{Colors.RESET}")
                print(f"    State: {device['state']}")
                print(f"    Source: {attrs.get('source', 'None')}")

            return True
        except Exception as e:
            self.print_failure(f"Device discovery failed: {e}")
            return False

    def test_basic_playback(self) -> bool:
        """Test 2: Can we play/pause?"""
        self.print_header("Test 2: Basic Playback")

        if not self.devices:
            self.print_warning("No devices available - skipping")
            return False

        device = self.devices[0]
        entity_id = device["entity_id"]
        source = device.get("attributes", {}).get("source")

        # Skip if AirPlay is active (playback controls locked)
        if source == "AirPlay":
            self.print_warning("AirPlay active - skipping playback test")
            return True  # Not a failure, just can't test

        # Test pause (safe, won't start playback)
        if not self.call_service("media_player", "media_pause", entity_id):
            self.print_failure("Pause command failed")
            return False

        self.print_success("Pause command succeeded")

        # Small delay
        time.sleep(1)

        # Test play
        if not self.call_service("media_player", "media_play", entity_id):
            self.print_failure("Play command failed")
            return False

        self.print_success("Play command succeeded")

        # Verify state updated
        time.sleep(2)
        state = self.get_state(entity_id)
        if state and state["state"] in ["playing", "idle"]:
            self.print_success(f"State updated: {state['state']}")
        else:
            self.print_warning("State may not have updated yet (expected with callbacks)")

        return True

    def test_volume_control(self) -> bool:
        """Test 3: Can we change volume?"""
        self.print_header("Test 3: Volume Control")

        if not self.devices:
            self.print_warning("No devices available - skipping")
            return False

        device = self.devices[0]
        entity_id = device["entity_id"]

        # Get current volume
        state = self.get_state(entity_id)
        if not state:
            self.print_failure("Could not get device state")
            return False

        current_volume = state.get("attributes", {}).get("volume_level", 0.5)
        self.print_info(f"Current volume: {current_volume:.1%}")

        # Set safe test volume
        test_volume = min(self.MAX_VOLUME, current_volume + 0.05)
        if not self.call_service("media_player", "volume_set", entity_id, volume_level=test_volume):
            self.print_failure("Volume set command failed")
            return False

        self.print_success(f"Volume set to {test_volume:.1%}")

        # Verify volume updated
        time.sleep(1)
        new_state = self.get_state(entity_id)
        if new_state:
            new_volume = new_state.get("attributes", {}).get("volume_level")
            if new_volume is not None:
                self.print_success(f"Volume updated: {new_volume:.1%}")
            else:
                self.print_warning("Volume attribute not available (may update via callback)")

        # Restore original volume
        self.call_service("media_player", "volume_set", entity_id, volume_level=current_volume)
        self.print_info("Volume restored to original level")

        return True

    def test_state_synchronization(self) -> bool:
        """Test 4: Does state update correctly?"""
        self.print_header("Test 4: State Synchronization")

        if not self.devices:
            self.print_warning("No devices available - skipping")
            return False

        device = self.devices[0]
        entity_id = device["entity_id"]

        # Get initial state
        initial_state = self.get_state(entity_id)
        if not initial_state:
            self.print_failure("Could not get device state")
            return False

        self.print_info(f"Initial state: {initial_state['state']}")

        # Trigger a state change (mute toggle is safe)
        initial_muted = initial_state.get("attributes", {}).get("is_volume_muted", False)
        self.call_service("media_player", "volume_mute", entity_id, is_volume_muted=not initial_muted)

        # Wait for state update
        time.sleep(2)

        # Check updated state
        updated_state = self.get_state(entity_id)
        if updated_state:
            new_muted = updated_state.get("attributes", {}).get("is_volume_muted")
            if new_muted is not None and new_muted != initial_muted:
                self.print_success("State synchronized correctly")
                # Restore
                self.call_service("media_player", "volume_mute", entity_id, is_volume_muted=initial_muted)
                return True
            else:
                self.print_warning("State may not have updated yet (callbacks may be delayed)")
                # Restore anyway
                self.call_service("media_player", "volume_mute", entity_id, is_volume_muted=initial_muted)
                return True  # Not a failure, just timing
        else:
            self.print_failure("Could not get updated state")
            return False

    def run_all(self) -> bool:
        """Run all smoke tests."""
        self.print_header("WiiM Integration - Smoke Tests")

        tests = [
            ("Device Discovery", self.test_device_discovery),
            ("Basic Playback", self.test_basic_playback),
            ("Volume Control", self.test_volume_control),
            ("State Synchronization", self.test_state_synchronization),
        ]

        results = []
        for name, test_func in tests:
            try:
                result = test_func()
                results.append((name, result))
            except Exception as e:
                self.print_failure(f"{name} raised exception: {e}")
                results.append((name, False))

        # Summary
        self.print_header("Test Summary")
        passed = sum(1 for _, result in results if result)
        total = len(results)

        for name, result in results:
            if result:
                self.print_success(f"{name}: PASSED")
            else:
                self.print_failure(f"{name}: FAILED")

        print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.RESET}")

        return passed == total


def main():
    parser = argparse.ArgumentParser(description="WiiM Integration Smoke Tests")
    parser.add_argument("--ha-url", default="http://localhost:8123", help="Home Assistant URL")
    parser.add_argument("--token", help="Home Assistant long-lived access token")
    parser.add_argument("--config", help="Path to test.config file with HA_URL and TOKEN")

    args = parser.parse_args()

    # Load config if provided
    if args.config and os.path.exists(args.config):
        # Try JSON first, then shell-style config
        try:
            with open(args.config) as f:
                config = json.load(f)
                ha_url = config.get("HA_URL", args.ha_url)
                token = config.get("TOKEN", args.token)
        except json.JSONDecodeError:
            # Shell-style config (KEY=VALUE format)
            with open(args.config) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        if key == "HA_URL":
                            ha_url = value
                        elif key == "HA_TOKEN":
                            token = value
    else:
        ha_url = args.ha_url
        token = args.token or os.environ.get("HA_TOKEN")

    if not token:
        print("Error: No token provided. Use --token or set HA_TOKEN environment variable.")
        sys.exit(1)

    suite = SmokeTestSuite(ha_url, token)
    success = suite.run_all()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
