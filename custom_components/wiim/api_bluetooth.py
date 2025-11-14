"""Bluetooth device scanning helpers for WiiM HTTP client.

This mixin handles Bluetooth device discovery and scanning operations.
These endpoints are unofficial and may not be available on all firmware versions.

It assumes the base client provides the `_request` coroutine and logging via
`_log` or `_LOGGER`. No state is stored – all results come from the device each call.
"""

from __future__ import annotations

import logging
from typing import Any

from .api_base import WiiMError
from .const import (
    API_ENDPOINT_CLEAR_BT_DISCOVERY,
    API_ENDPOINT_CONNECT_BT_A2DP,
    API_ENDPOINT_DISCONNECT_BT_A2DP,
    API_ENDPOINT_GET_BT_DISCOVERY_RESULT,
    API_ENDPOINT_GET_BT_HISTORY,
    API_ENDPOINT_GET_BT_PAIR_STATUS,
    API_ENDPOINT_START_BT_DISCOVERY,
)

_LOGGER = logging.getLogger(__name__)


class BluetoothAPI:  # mixin – must appear *before* the base client in MRO
    """Bluetooth device scanning helpers."""

    # pylint: disable=no-member

    # ------------------------------------------------------------------
    # Bluetooth device discovery
    # ------------------------------------------------------------------

    async def start_bluetooth_discovery(self, duration: int = 3) -> None:  # type: ignore[override]
        """Start Bluetooth device discovery scan.

        Args:
            duration: Scan duration in seconds (typically 3-10 seconds)

        Raises:
            WiiMRequestError: If the request fails
        """
        if not 1 <= duration <= 60:  # Reasonable limits
            raise ValueError("Duration must be between 1 and 60 seconds")

        await self._request(f"{API_ENDPOINT_START_BT_DISCOVERY}{duration}")  # type: ignore[attr-defined]

    async def get_bluetooth_discovery_result(self) -> dict[str, Any]:  # type: ignore[override]
        """Get results of the last Bluetooth device discovery scan.

        Returns:
            Dict containing scan results:
            - num: Number of devices found
            - scan_status: Scan status (0=Not started, 1=Initializing, 2=Scanning, 3=Complete, 4=Final Complete)
            - bt_device: Array of discovered devices with name, mac, and rssi
              (normalized from API's 'list' field with 'ad' for MAC address)
        """
        result = await self._request(API_ENDPOINT_GET_BT_DISCOVERY_RESULT)  # type: ignore[attr-defined]

        # Handle case where API returns error string instead of dict
        if isinstance(result, str):
            return {"num": 0, "scan_status": 0, "bt_device": []}

        # Normalize API response: API returns 'list' with 'ad' for MAC, we normalize to 'bt_device' with 'mac'
        if "list" in result and isinstance(result["list"], list):
            normalized_devices = []
            for device in result["list"]:
                # Extract MAC address - API uses 'ad' field
                mac = device.get("ad", "")
                name = device.get("name", "Unknown")

                # Skip devices without MAC address (invalid entries)
                if not mac:
                    _LOGGER.debug("Skipping Bluetooth device without MAC address: %s", device)
                    continue

                normalized_device = {
                    "name": name,
                    "mac": mac.lower(),  # Normalize MAC to lowercase for consistency
                }
                # Add RSSI if present (some devices may have it)
                if "rssi" in device:
                    normalized_device["rssi"] = device["rssi"]
                # Preserve other fields
                if "role" in device:
                    normalized_device["role"] = device["role"]
                normalized_devices.append(normalized_device)

            _LOGGER.debug(
                "Normalized %d Bluetooth devices from API response (num=%s, scan_status=%s)",
                len(normalized_devices),
                result.get("num"),
                result.get("scan_status"),
            )

            # Return normalized format
            return {
                "num": result.get("num", len(normalized_devices)),
                "scan_status": result.get("scan_status", 0),
                "bt_device": normalized_devices,
            }

        # Fallback: if 'bt_device' already exists (backward compatibility)
        return result

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    async def scan_for_bluetooth_devices(self, duration: int = 3) -> list[dict[str, Any]]:  # type: ignore[override]
        """Perform a complete Bluetooth device scan and return results.

        Args:
            duration: Scan duration in seconds

        Returns:
            List of discovered Bluetooth devices, each containing:
            - name: Device name
            - mac: MAC address
            - rssi: Signal strength (negative dBm value)
        """
        # Clear any previous scan results to avoid stale data
        _LOGGER.debug("Clearing previous Bluetooth scan results")
        try:
            await self.clear_bluetooth_discovery_result()
        except WiiMError as err:
            _LOGGER.debug("Failed to clear previous scan results (may not be supported): %s", err)

        # Start the scan
        _LOGGER.info("Starting Bluetooth discovery scan (duration: %d seconds)", duration)
        await self.start_bluetooth_discovery(duration)

        # Wait for scan to complete (with timeout)
        import asyncio

        # Give the device a moment to start the scan
        await asyncio.sleep(0.5)

        # Wait at least the scan duration + buffer time
        max_wait_time = max(duration + 5, 15)  # At least 15 seconds, or duration + 5
        _LOGGER.debug("Waiting up to %d seconds for scan to complete", max_wait_time)

        scan_started = False
        for attempt in range(max_wait_time):
            try:
                result = await self.get_bluetooth_discovery_result()
                scan_status = result.get("scan_status", 0)
                num_devices = result.get("num", 0)

                status_names = {
                    0: "Not started",
                    1: "Initializing",
                    2: "Scanning",
                    3: "Complete",
                    4: "Complete",
                }
                status_name = status_names.get(scan_status, f"Unknown({scan_status})")

                _LOGGER.debug(
                    "Scan status check (attempt %d/%d): status=%s (%d), devices=%d",
                    attempt + 1,
                    max_wait_time,
                    status_name,
                    scan_status,
                    num_devices,
                )

                # Track if we've seen the scan actually start (status 1, 2, 3, or 4)
                # Status 3/4 also indicate scan started (even if from previous scan)
                if scan_status in (1, 2, 3, 4):
                    scan_started = True

                if scan_status in (
                    3,
                    4,
                ):  # Complete (some devices return 3 early, 4 when fully complete)
                    # Status 4 is the final completion status - but wait at least duration seconds to ensure all devices are found
                    if scan_status == 4:
                        # Wait until we've been scanning for at least the duration to ensure all devices are discovered
                        if attempt >= duration:
                            devices = result.get("bt_device", [])
                            device_count = len(devices) if isinstance(devices, list) else 0
                            _LOGGER.info(
                                "✅ Bluetooth scan completed: status=%s (final), found %d devices after %d seconds",
                                status_name,
                                device_count,
                                attempt + 1,
                            )
                            if device_count > 0:
                                _LOGGER.debug(
                                    "Device list: %s",
                                    [f"{d.get('name', 'Unknown')} ({d.get('mac', 'N/A')})" for d in devices],
                                )
                            return devices if isinstance(devices, list) else []
                        else:
                            # Status 4 appeared early - wait a bit more to ensure all devices are found
                            _LOGGER.debug(
                                "Got status=Complete (4) but only %d seconds elapsed (need %d), continuing scan...",
                                attempt + 1,
                                duration,
                            )
                    # Status 3 might be early completion - wait a bit more to see if status 4 appears
                    # But if we've waited long enough (duration), accept status 3
                    elif attempt >= duration:
                        devices = result.get("bt_device", [])
                        device_count = len(devices) if isinstance(devices, list) else 0
                        _LOGGER.info(
                            "✅ Bluetooth scan completed: status=%s (after %d seconds), found %d devices",
                            status_name,
                            attempt + 1,
                            device_count,
                        )
                        if device_count > 0:
                            _LOGGER.debug(
                                "Device list: %s",
                                [f"{d.get('name', 'Unknown')} ({d.get('mac', 'N/A')})" for d in devices],
                            )
                        return devices if isinstance(devices, list) else []
                    else:
                        # Status 3 but scan hasn't been running long enough - wait a bit more for status 4
                        _LOGGER.debug(
                            "Got status=Complete (3) but only %d seconds elapsed, waiting for final status (4)...",
                            attempt + 1,
                        )
                elif scan_status == 0:  # Not started (scan failed)
                    if scan_started:
                        # Scan started but then failed
                        _LOGGER.warning("Bluetooth scan failed: status=Not started (0) after scan had started")
                        return []
                    # Otherwise, scan might not have started yet, continue waiting
            except WiiMError as err:
                _LOGGER.debug("Error checking scan status (attempt %d): %s", attempt + 1, err)

            await asyncio.sleep(1)  # Wait 1 second before checking again

        # Timeout - return empty list
        _LOGGER.warning(
            "Bluetooth scan timed out after %d seconds. No devices found or scan did not complete.",
            max_wait_time,
        )
        return []

    async def is_bluetooth_scan_in_progress(self) -> bool:  # type: ignore[override]
        """Check if a Bluetooth scan is currently in progress.

        Returns:
            True if scan is running (status 1 or 2), False otherwise
        """
        try:
            result = await self.get_bluetooth_discovery_result()
            scan_status = result.get("scan_status", 0)
            return scan_status in (1, 2)  # 1=Initializing, 2=Scanning
        except WiiMError:
            return False

    async def get_bluetooth_device_count(self) -> int:  # type: ignore[override]
        """Get the number of Bluetooth devices found in the last scan.

        Returns:
            Number of devices found, or 0 if no scan performed or failed
        """
        try:
            result = await self.get_bluetooth_discovery_result()
            return int(result.get("num", 0))
        except WiiMError:
            return 0

    async def get_last_bluetooth_scan_status(self) -> str:  # type: ignore[override]
        """Get the status of the last Bluetooth scan as a human-readable string.

        Returns:
            Status string: "Not started", "Initializing", "Scanning", "Complete", or "Unknown"
        """
        status_map = {0: "Not started", 1: "Initializing", 2: "Scanning", 3: "Complete"}

        try:
            result = await self.get_bluetooth_discovery_result()
            scan_status = result.get("scan_status", -1)
            return status_map.get(scan_status, "Unknown")
        except WiiMError:
            return "Unknown"

    # ------------------------------------------------------------------
    # Bluetooth connection and pairing
    # ------------------------------------------------------------------

    async def connect_bluetooth_device(self, mac_address: str) -> None:  # type: ignore[override]
        """Connect to a Bluetooth device by MAC address.

        Args:
            mac_address: MAC address of the Bluetooth device (format: "AA:BB:CC:DD:EE:FF" or "AA-BB-CC-DD-EE-FF")

        Raises:
            WiiMRequestError: If the request fails
            ValueError: If MAC address format is invalid
        """
        # Normalize MAC address format (accept both : and - separators)
        mac_normalized = mac_address.replace("-", ":").upper()

        # Basic validation - should be 6 groups of 2 hex digits separated by colons
        import re

        if not re.match(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", mac_normalized):
            raise ValueError(f"Invalid MAC address format: {mac_address}. Expected format: AA:BB:CC:DD:EE:FF")

        await self._request(f"{API_ENDPOINT_CONNECT_BT_A2DP}{mac_normalized}")  # type: ignore[attr-defined]

    async def disconnect_bluetooth_device(self) -> None:  # type: ignore[override]
        """Disconnect the current Bluetooth connection.

        Raises:
            WiiMRequestError: If the request fails
        """
        await self._request(API_ENDPOINT_DISCONNECT_BT_A2DP)  # type: ignore[attr-defined]

    async def get_bluetooth_pair_status(self) -> dict[str, Any]:  # type: ignore[override]
        """Get Bluetooth pairing status.

        Returns:
            Dict containing pairing status information
        """
        try:
            result = await self._request(API_ENDPOINT_GET_BT_PAIR_STATUS)  # type: ignore[attr-defined]
            return result if isinstance(result, dict) else {}
        except WiiMError:
            return {}

    async def get_bluetooth_history(self) -> list[dict[str, Any]]:  # type: ignore[override]
        """Get Bluetooth connection history (previously paired devices).

        Returns:
            List of paired devices, each containing device information with:
            - name: Device name
            - ad: MAC address (API uses 'ad' not 'mac')
            - ct: Connection type (1=connected, 0=paired but not connected)
            - role: Device role ("Audio Sink" for output, "Audio Source" for input)
        """
        try:
            result = await self._request(API_ENDPOINT_GET_BT_HISTORY)  # type: ignore[attr-defined]
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                # API returns dict with "list" field containing devices
                if "list" in result and isinstance(result["list"], list):
                    return result["list"]
                elif "bt_device" in result and isinstance(result["bt_device"], list):
                    return result["bt_device"]
            return []
        except WiiMError:
            return []

    async def clear_bluetooth_discovery_result(self) -> None:  # type: ignore[override]
        """Clear Bluetooth discovery scan results.

        Raises:
            WiiMRequestError: If the request fails
        """
        await self._request(API_ENDPOINT_CLEAR_BT_DISCOVERY)  # type: ignore[attr-defined]
