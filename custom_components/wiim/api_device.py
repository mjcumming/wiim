"""Device-centric helpers extracted from the monolithic WiiM HTTP client.

In the *first* migration step this mixin is kept intentionally empty and simply
inherits from `api_base.WiiMClient` at runtime via the façade.  Subsequent PRs
will *move* the actual implementations here.
"""

from __future__ import annotations

from typing import Any

from .api_base import _LOGGER, WiiMError
from .const import (
    API_ENDPOINT_FIRMWARE,
    API_ENDPOINT_LED,
    API_ENDPOINT_LED_BRIGHTNESS,
    API_ENDPOINT_MAC,
    API_ENDPOINT_STATUS,
)
from .models import DeviceInfo


class DeviceAPI:  # pylint: disable=too-few-public-methods
    """Device info, firmware and LED helpers."""

    # ------------------------------------------------------------------
    # Device information ------------------------------------------------
    # ------------------------------------------------------------------

    async def get_device_info(self) -> dict[str, Any]:  # type: ignore[override]
        """Return comprehensive device information via getStatusEx."""
        self._logger_debug("=== API get_device_info START for %s ===", self.host)  # type: ignore[attr-defined]
        try:
            self._logger_debug("Calling getStatusEx endpoint for %s", self.host)  # type: ignore[attr-defined]
            device_info = await self._request(API_ENDPOINT_STATUS)  # type: ignore[attr-defined]
            self._logger_debug("Raw getStatusEx response for %s: %s", self.host, device_info)  # type: ignore[attr-defined]
            return device_info
        except Exception as err:  # pylint: disable=broad-except
            self._logger_error("get_device_info failed for %s: %s", self.host, err)  # type: ignore[attr-defined]
            return {}

    async def get_device_info_model(self) -> DeviceInfo:  # type: ignore[override]
        """Return `DeviceInfo` Pydantic model (raises on validation error)."""
        raw = await self.get_device_info()
        return DeviceInfo.model_validate(raw)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Basic identifiers -------------------------------------------------
    # ------------------------------------------------------------------

    async def get_firmware_version(self) -> str:  # type: ignore[override]
        response = await self._request(API_ENDPOINT_FIRMWARE)  # type: ignore[attr-defined]
        return response.get("firmware", "")

    async def get_mac_address(self) -> str:  # type: ignore[override]
        response = await self._request(API_ENDPOINT_MAC)  # type: ignore[attr-defined]
        return response.get("mac", "")

    # ------------------------------------------------------------------
    # LED helpers -------------------------------------------------------
    # ------------------------------------------------------------------

    async def set_led(self, enabled: bool) -> None:  # type: ignore[override]
        await self._request(f"{API_ENDPOINT_LED}{1 if enabled else 0}")  # type: ignore[attr-defined]

    async def set_led_brightness(self, brightness: int) -> None:  # type: ignore[override]
        if not 0 <= brightness <= 100:
            raise ValueError("Brightness must be between 0 and 100")
        await self._request(f"{API_ENDPOINT_LED_BRIGHTNESS}{brightness}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Config-flow convenience -------------------------------------------
    # ------------------------------------------------------------------

    async def get_device_name(self) -> str:  # type: ignore[override]
        """Best-effort friendly name (device-info → status → IP)."""
        try:
            status = await self.get_player_status()  # type: ignore[attr-defined]
            if name := status.get("DeviceName"):
                return name.strip()
            info = await self.get_device_info()
            if name := info.get("DeviceName") or info.get("device_name"):
                return name.strip()
        except WiiMError:  # type: ignore[misc]
            pass
        return self.host  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Helper wrappers to piggy-back on api_base logging -----------------
    # ------------------------------------------------------------------

    def _logger_debug(self, *args, **kwargs):  # internal helper
        _LOGGER.debug(*args, **kwargs)

    def _logger_error(self, *args, **kwargs):
        _LOGGER.error(*args, **kwargs)

    # NOTE: _LOGGER is defined in api_base and accessible through MRO.

    # END DeviceAPI
