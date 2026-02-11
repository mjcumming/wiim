#!/usr/bin/env python3
"""One-off: discover one WiiM device and call reboot_device (real-world test for issue #179)."""

import os
import sys
from pathlib import Path

import requests

# Same config loading as test-automated.py
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "test.config"
HA_URL = os.environ.get("HA_URL", "http://localhost:8123")
TOKEN = os.environ.get("HA_TOKEN")

if CONFIG_PATH.exists():
    with open(CONFIG_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key == "HA_URL":
                    HA_URL = value.strip()
                elif key == "HA_TOKEN":
                    TOKEN = value.strip()

if not TOKEN:
    print("Error: No HA_TOKEN in test.config or HA_TOKEN env")
    sys.exit(1)

HA_URL = HA_URL.rstrip("/")
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# Discover WiiM media_player entities
try:
    r = requests.get(f"{HA_URL}/api/states", headers=headers, timeout=10)
    r.raise_for_status()
except Exception as e:
    print(f"Failed to get states: {e}")
    sys.exit(1)

devices = [
    s
    for s in r.json()
    if s["entity_id"].startswith("media_player.")
    and s.get("attributes", {}).get("integration_purpose") == "individual_speaker_control"
]

if not devices:
    print("No WiiM media_player devices found.")
    sys.exit(1)

entity_id = devices[0]["entity_id"]
friendly = devices[0].get("attributes", {}).get("friendly_name", entity_id)
print(f"Calling reboot_device on: {entity_id} ({friendly})")

try:
    resp = requests.post(
        f"{HA_URL}/api/services/wiim/reboot_device",
        headers=headers,
        json={"entity_id": entity_id},
        timeout=15,
    )
    if resp.status_code == 200:
        print("Reboot service returned 200 OK (restart sent; device may not respond).")
    else:
        print(f"Service returned {resp.status_code}: {resp.text[:300]}")
except Exception as e:
    print(f"Request error: {e}")
    sys.exit(1)
