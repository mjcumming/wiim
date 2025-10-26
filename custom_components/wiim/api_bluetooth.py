"""Bluetooth device scanning helpers for WiiM HTTP client.

This mixin handles Bluetooth device discovery and scanning operations.
These endpoints are unofficial and may not be available on all firmware versions.

It assumes the base client provides the `_request` coroutine and logging via
`_log` or `_LOGGER`. No state is stored – all results come from the device each call.
"""

from __future__ import annotations

from typing import Any

from .api_base import WiiMError
from .const import (
    API_ENDPOINT_GET_BT_DISCOVERY_RESULT,
    API_ENDPOINT_START_BT_DISCOVERY,
)


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
            - scan_status: Scan status (0=Not started, 1=Initializing, 2=Scanning, 3=Complete)
            - bt_device: Array of discovered devices with name, mac, and rssi
        """
        result = await self._request(API_ENDPOINT_GET_BT_DISCOVERY_RESULT)  # type: ignore[attr-defined]

        # Handle case where API returns error string instead of dict
        if isinstance(result, str):
            return {"num": 0, "scan_status": 0, "bt_device": []}

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
        # Start the scan
        await self.start_bluetooth_discovery(duration)

        # Wait for scan to complete (with timeout)
        import asyncio

        max_wait_time = max(duration + 5, 15)  # At least 15 seconds, or duration + 5

        for _ in range(max_wait_time):
            try:
                result = await self.get_bluetooth_discovery_result()
                scan_status = result.get("scan_status", 0)

                if scan_status == 3:  # Complete
                    devices = result.get("bt_device", [])
                    return devices if isinstance(devices, list) else []
                elif scan_status == 0:  # Not started (scan failed)
                    return []
            except WiiMError:
                pass

            await asyncio.sleep(1)  # Wait 1 second before checking again

        # Timeout - return empty list
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
