"""WiiM button platform.

Provides useful device maintenance buttons. All buttons are optional and only
created when maintenance buttons are enabled in options.
"""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    """Set up WiiM maintenance buttons from a config entry.

    Only creates useful maintenance buttons that users actually need.
    All buttons are optional and controlled by user preferences.
    """
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    entry = hass.data[DOMAIN][config_entry.entry_id]["entry"]

    entities = []
    # Only create maintenance buttons if the option is enabled
    if entry.options.get("enable_maintenance_buttons", False):
        entities.extend(
            [
                WiiMRebootButton(coordinator, config_entry),
                WiiMSyncTimeButton(coordinator, config_entry),
            ]
        )

    async_add_entities(entities)
    device_name = coordinator.player.name or config_entry.title or "WiiM Speaker"
    _LOGGER.info("Created %d button entities for %s", len(entities), device_name)


class WiiMRebootButton(WiimEntity, ButtonEntity):
    """Device reboot button for system maintenance and firmware updates.

    Rebooting the device will apply any downloaded firmware updates.
    Also useful for resolving connectivity issues and refreshing device state.
    """

    _attr_icon = "mdi:restart"
    _attr_has_entity_name = True

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize reboot button."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_reboot"
        self._attr_name = "Reboot"

    async def async_press(self) -> None:
        """Execute device reboot command.

        Sends reboot command to the device. If the device has downloaded a firmware
        update, the reboot will trigger the installation process.
        """
        device_name = self.player.name or self._config_entry.title or "WiiM Speaker"
        try:
            _LOGGER.info("Initiating reboot for %s", device_name)
            await self.coordinator.player.reboot()
            _LOGGER.info("Reboot command sent successfully to %s", device_name)
            # State updates automatically via callback - no manual refresh needed

        except Exception as err:
            # Reboot commands often don't return proper responses
            # Log the attempt but don't fail the button press
            _LOGGER.info(
                "Reboot command sent to %s (device may not respond): %s",
                device_name,
                err,
            )
            # Don't raise - reboot command was sent successfully
            # The device will reboot even if the response parsing fails
            # State updates automatically via callback - no manual refresh needed


class WiiMSyncTimeButton(WiimEntity, ButtonEntity):
    """Device time synchronization button.

    Synchronizes the device clock with network time for accurate timestamps.
    """

    _attr_icon = "mdi:clock-sync"
    _attr_has_entity_name = True

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize time sync button."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_sync_time"
        self._attr_name = "Sync Time"

    async def async_press(self) -> None:
        """Execute time synchronization command.

        Synchronizes the device's internal clock with network time,
        ensuring accurate timestamps for media metadata and logs.
        """
        async with self.wiim_command("sync time"):
            _LOGGER.info("Synchronizing time for %s", self.name)
            await self.coordinator.player.sync_time()
            # State updates automatically via callback - no manual refresh needed
