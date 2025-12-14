"""WiiM update platform.

Exposes device firmware update availability via Home Assistant's `update` domain.

pywiim provides firmware update support via Player properties/methods:
- `player.firmware_update_available`: update downloaded & ready (bool)
- `player.latest_firmware_version`: latest available version string (str | None)
- `player.supports_firmware_install`: whether install via API is supported (bool; WiiM only)
- `await player.install_firmware_update()`: start installation (WiiM only)

This integration stays thin: we only expose pywiim's state and call its APIs.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import WiiMCoordinator
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM firmware update entity from a config entry."""
    coordinator: WiiMCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([WiiMFirmwareUpdateEntity(coordinator, config_entry)])
    device_name = coordinator.player.name or config_entry.title or "WiiM Speaker"
    _LOGGER.debug("Created firmware update entity for %s", device_name)


class WiiMFirmwareUpdateEntity(WiimEntity, UpdateEntity):
    """Firmware update availability for a WiiM device."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_icon = "mdi:update"

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize firmware update entity."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_firmware_update"
        self._attr_name = "Firmware Update"

    @property
    def installed_version(self) -> str | None:  # type: ignore[override]
        """Return the currently installed firmware string."""
        firmware = getattr(self.player, "firmware", None)
        if firmware is None:
            return None
        fw = str(firmware).strip()
        if fw in {"", "0", "-", "unknown"}:
            return None
        return fw

    @property
    def latest_version(self) -> str | None:  # type: ignore[override]
        """Return the latest available firmware version (if known)."""
        latest = getattr(self.player, "latest_firmware_version", None)
        if latest is None:
            return None
        latest_str = str(latest).strip()
        if latest_str in {"", "0", "-", "unknown"}:
            return None
        return latest_str

    @property
    def update_available(self) -> bool:  # type: ignore[override]
        """Return True if an update is available and ready (per pywiim)."""
        return bool(getattr(self.player, "firmware_update_available", False))

    @property
    def release_notes(self) -> str | None:  # type: ignore[override]
        """Return release notes for the latest version (not provided by device)."""
        return None

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:  # type: ignore[override]
        """Install the update.

        Uses pywiim's firmware update API (WiiM devices only).
        """
        if not self.update_available:
            raise HomeAssistantError("No firmware update is ready to install.")

        device_name = self.player.name or self._config_entry.title or "WiiM Speaker"
        try:
            if not getattr(self.player, "supports_firmware_install", False):
                raise HomeAssistantError("Firmware installation via API is not supported on this device.")

            _LOGGER.info("Starting firmware installation for %s", device_name)
            await self.player.install_firmware_update()
            _LOGGER.info("Firmware installation started for %s", device_name)
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Failed to start firmware update install: {err}") from err

    # Some HA type-checkers/pylint versions expect a synchronous `install` method.
    # Provide it as a thin wrapper to satisfy tooling without changing behavior.
    def install(self, version: str | None, backup: bool, **kwargs: Any) -> None:  # type: ignore[override]
        """Sync wrapper for firmware installation (not supported)."""
        raise HomeAssistantError("Firmware installation must be triggered from Home Assistant asynchronously.")
