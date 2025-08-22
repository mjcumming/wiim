"""Device-related helpers for WiiM HTTP client.

Contains only low-level calls for static device information and LED control.
All networking is provided by the base client (`api_base.WiiMClient`).
"""

from __future__ import annotations

from typing import Any

from .const import (
    API_ENDPOINT_ARYLIC_LED,
    API_ENDPOINT_ARYLIC_LED_BRIGHTNESS,
    API_ENDPOINT_FIRMWARE,
    API_ENDPOINT_LED,
    API_ENDPOINT_LED_BRIGHTNESS,
    API_ENDPOINT_MAC,
    API_ENDPOINT_STATUS,
)
from .firmware_capabilities import get_led_command_format
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
        """Enable or disable the front LED with device-specific commands."""
        try:
            # Get device info to determine LED command format
            device_info = await self.get_device_info_model()
            led_format = get_led_command_format(device_info)

            if led_format == "arylic":
                # Arylic devices use MCU+PAS+RAKOIT:LED commands
                # LED:1 = on, LED:0 = off
                # Note: These commands are experimental based on user research
                try:
                    await self._request(f"{API_ENDPOINT_ARYLIC_LED}{1 if enabled else 0}")  # type: ignore[attr-defined]
                except Exception as arylic_err:
                    # Fallback: try standard commands in case Arylic supports them
                    import logging

                    _logger = logging.getLogger(__name__)
                    _logger.debug("Arylic LED command failed, trying standard: %s", arylic_err)
                    try:
                        await self._request(f"{API_ENDPOINT_LED}{1 if enabled else 0}")  # type: ignore[attr-defined]
                    except Exception as std_err:
                        _logger.debug("Standard LED command also failed: %s", std_err)
                        raise arylic_err from std_err  # Re-raise original error
            else:
                # Standard LinkPlay LED command
                await self._request(f"{API_ENDPOINT_LED}{1 if enabled else 0}")  # type: ignore[attr-defined]

        except Exception as err:
            # Log but don't fail - LED control is optional
            import logging

            _logger = logging.getLogger(__name__)
            _logger.debug("LED control not supported or failed for device: %s", err)

    async def set_led_brightness(self, brightness: int) -> None:  # type: ignore[override]
        """Set LED brightness (0–100) with device-specific commands."""
        if not 0 <= brightness <= 100:
            raise ValueError("Brightness must be between 0 and 100")

        try:
            # Get device info to determine LED command format
            device_info = await self.get_device_info_model()
            led_format = get_led_command_format(device_info)

            if led_format == "arylic":
                # Arylic devices use MCU+PAS+RAKOIT:LEDBRIGHTNESS commands
                # Brightness: 0-100 percentage
                # Note: These commands are experimental based on user research
                try:
                    await self._request(f"{API_ENDPOINT_ARYLIC_LED_BRIGHTNESS}{brightness}")  # type: ignore[attr-defined]
                except Exception as arylic_err:
                    # Fallback: try standard commands in case Arylic supports them
                    import logging

                    _logger = logging.getLogger(__name__)
                    _logger.debug("Arylic LED brightness command failed, trying standard: %s", arylic_err)
                    try:
                        await self._request(f"{API_ENDPOINT_LED_BRIGHTNESS}{brightness}")  # type: ignore[attr-defined]
                    except Exception as std_err:
                        _logger.debug("Standard LED brightness command also failed: %s", std_err)
                        raise arylic_err from std_err  # Re-raise original error
            else:
                # Standard LinkPlay brightness command
                await self._request(f"{API_ENDPOINT_LED_BRIGHTNESS}{brightness}")  # type: ignore[attr-defined]

        except Exception as err:
            # Log but don't fail - LED control is optional
            import logging

            _logger = logging.getLogger(__name__)
            _logger.debug("LED brightness control not supported or failed for device: %s", err)
