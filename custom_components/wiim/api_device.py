"""Device-related helpers for WiiM HTTP client.

Contains only low-level calls for static device information and LED control.
All networking is provided by the base client (`api_base.WiiMClient`).
"""

from __future__ import annotations

from typing import Any

from .const import (
    API_ENDPOINT_FIRMWARE,
    API_ENDPOINT_LED,
    API_ENDPOINT_LED_BRIGHTNESS,
    API_ENDPOINT_MAC,
    API_ENDPOINT_STATUS,
)
from .models import DeviceInfo


class DeviceAPI:  # mixin – must appear *before* the base client in MRO
    """Device-information and LED helpers expected by the integration."""

    # The mixin relies on the base client providing `_request` and `timeout`.

    # ------------------------------------------------------------------
    # Information helpers
    # ------------------------------------------------------------------

    async def get_device_info(self) -> dict[str, Any]:  # type: ignore[override]
        """Return the raw `getStatusEx` JSON payload."""
        return await self._request(API_ENDPOINT_STATUS)  # type: ignore[attr-defined]

    async def get_device_info_model(self) -> DeviceInfo:  # type: ignore[override]
        """Return a pydantic-validated :class:`DeviceInfo`."""
        return DeviceInfo.model_validate(await self.get_device_info())

    async def get_firmware_version(self) -> str:  # type: ignore[override]
        """Return firmware version string (empty on error)."""
        resp = await self._request(API_ENDPOINT_FIRMWARE)  # type: ignore[attr-defined]
        return resp.get("firmware", "") if isinstance(resp, dict) else ""

    async def get_mac_address(self) -> str:  # type: ignore[override]
        """Return MAC address string (empty on error)."""
        resp = await self._request(API_ENDPOINT_MAC)  # type: ignore[attr-defined]
        return resp.get("mac", "") if isinstance(resp, dict) else ""

    # ------------------------------------------------------------------
    # LED helpers
    # ------------------------------------------------------------------

    async def set_led(self, enabled: bool) -> None:  # type: ignore[override]
        """Enable or disable the front LED."""
        await self._request(f"{API_ENDPOINT_LED}{1 if enabled else 0}")  # type: ignore[attr-defined]

    async def set_led_brightness(self, brightness: int) -> None:  # type: ignore[override]
        """Set LED brightness (0–100)."""
        if not 0 <= brightness <= 100:
            raise ValueError("Brightness must be between 0 and 100")
        await self._request(f"{API_ENDPOINT_LED_BRIGHTNESS}{brightness}")  # type: ignore[attr-defined]
