"""Miscellaneous device control helpers for WiiM HTTP client.

This mixin handles various device controls including button controls and
other miscellaneous operations. These endpoints are unofficial and may not
be available on all firmware versions.

Note: LED controls are already implemented in the DeviceAPI mixin with
device-specific command detection.

It assumes the base client provides the `_request` coroutine and logging via
`_log` or `_LOGGER`. No state is stored – all results come from the device each call.
"""

from __future__ import annotations

from typing import Any

from .api_base import WiiMError
from .const import (
    API_ENDPOINT_SET_BUTTONS,
)


class MiscAPI:  # mixin – must appear *before* the base client in MRO
    """Miscellaneous device control helpers (buttons, etc.)."""

    # pylint: disable=no-member

    # ------------------------------------------------------------------
    # Touch button controls
    # ------------------------------------------------------------------

    async def set_buttons_enabled(self, enabled: bool) -> None:  # type: ignore[override]
        """Enable or disable touch button controls on the device.

        Args:
            enabled: True to enable touch buttons, False to disable

        Raises:
            WiiMRequestError: If the request fails

        Note:
            This controls the physical touch buttons on the device itself,
            not Home Assistant button entities.
        """
        value = "1" if enabled else "0"
        await self._request(f"{API_ENDPOINT_SET_BUTTONS}{value}")  # type: ignore[attr-defined]

    async def enable_touch_buttons(self) -> None:  # type: ignore[override]
        """Enable touch button controls on the device."""
        await self.set_buttons_enabled(True)

    async def disable_touch_buttons(self) -> None:  # type: ignore[override]
        """Disable touch button controls on the device."""
        await self.set_buttons_enabled(False)

    # ------------------------------------------------------------------
    # Alternative LED control (if needed)
    # ------------------------------------------------------------------

    async def set_led_switch(self, enabled: bool) -> None:  # type: ignore[override]
        """Alternative LED control method using LED_SWITCH_SET command.

        This is an alternative to the device-specific LED commands already
        implemented in the DeviceAPI mixin. Use only if the standard LED
        commands don't work on your device.

        Args:
            enabled: True to enable LED, False to disable

        Raises:
            WiiMRequestError: If the request fails
        """
        # Import here to avoid circular imports
        from .const import API_ENDPOINT_SET_LED

        value = "1" if enabled else "0"
        await self._request(f"{API_ENDPOINT_SET_LED}{value}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Status and information helpers
    # ------------------------------------------------------------------

    async def get_device_capabilities(self) -> dict[str, Any]:  # type: ignore[override]
        """Get comprehensive device capabilities including unofficial endpoints.

        Returns:
            Dict containing capability flags for various features
        """
        capabilities = {
            "touch_buttons": False,
            "alternative_led": False,
            "network_config": False,
            "bluetooth_scanning": False,
            "audio_settings": False,
            "lms_integration": False,
        }

        # Test each capability by attempting to use it
        # Note: This is a best-effort check and may produce log warnings

        # Check touch buttons (this one should work if endpoint exists)
        try:
            await self.set_buttons_enabled(True)
            capabilities["touch_buttons"] = True
        except WiiMError:
            pass

        # Check alternative LED control
        try:
            await self.set_led_switch(True)
            capabilities["alternative_led"] = True
        except WiiMError:
            pass

        return capabilities

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    async def are_touch_buttons_enabled(self) -> bool:  # type: ignore[override]
        """Check if touch buttons are currently enabled.

        Returns:
            True if buttons are enabled, False otherwise.
            Note: This is a guess since the API doesn't provide readback.
            Always returns True unless the endpoint fails completely.
        """
        try:
            # Try to enable buttons - if it succeeds, assume they're supported
            await self.enable_touch_buttons()
            return True
        except WiiMError:
            return False

    async def test_misc_functionality(self) -> dict[str, bool]:  # type: ignore[override]
        """Test all miscellaneous functionality and report what's available.

        Returns:
            Dict with availability status for each feature
        """
        results = {}

        # Test touch button control
        try:
            await self.set_buttons_enabled(True)
            results["touch_buttons"] = True
        except WiiMError:
            results["touch_buttons"] = False

        # Test alternative LED control
        try:
            await self.set_led_switch(True)
            results["alternative_led"] = True
        except WiiMError:
            results["alternative_led"] = False

        return results
