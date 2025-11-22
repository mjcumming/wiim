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

from .data import Speaker, get_speaker_from_config_entry
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
    speaker = get_speaker_from_config_entry(hass, config_entry)
    entry = hass.data["wiim"][config_entry.entry_id]["entry"]

    entities = []
    # Only create maintenance buttons if the option is enabled
    if entry.options.get("enable_maintenance_buttons", False):
        entities.extend(
            [
                WiiMRebootButton(speaker),
                WiiMSyncTimeButton(speaker),
            ]
        )

    async_add_entities(entities)
    _LOGGER.info("Created %d button entities for %s", len(entities), speaker.name)


class WiiMRebootButton(WiimEntity, ButtonEntity):
    """Device reboot button for system maintenance and firmware updates.

    Rebooting the device will apply any downloaded firmware updates.
    Also useful for resolving connectivity issues and refreshing device state.
    """

    _attr_icon = "mdi:restart"
    _attr_has_entity_name = True

    def __init__(self, speaker: Speaker) -> None:
        """Initialize reboot button."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_reboot"
        self._attr_name = "Reboot"

    async def async_press(self) -> None:
        """Execute device reboot command.

        Sends reboot command to the device. If the device has downloaded a firmware
        update, the reboot will trigger the installation process.
        """
        try:
            _LOGGER.info("Initiating reboot for %s", self.speaker.name)
            await self.speaker.coordinator.player.reboot()
            _LOGGER.info("Reboot command sent successfully to %s", self.speaker.name)
            await self._async_execute_command_with_refresh("reboot")

        except Exception as err:
            # Reboot commands often don't return proper responses
            # Log the attempt but don't fail the button press
            _LOGGER.info(
                "Reboot command sent to %s (device may not respond): %s",
                self.speaker.name,
                err,
            )
            # Don't raise - reboot command was sent successfully
            # The device will reboot even if the response parsing fails
            await self._async_execute_command_with_refresh("reboot")


class WiiMSyncTimeButton(WiimEntity, ButtonEntity):
    """Device time synchronization button.

    Synchronizes the device clock with network time for accurate timestamps.
    """

    _attr_icon = "mdi:clock-sync"
    _attr_has_entity_name = True

    def __init__(self, speaker: Speaker) -> None:
        """Initialize time sync button."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_sync_time"
        self._attr_name = "Sync Time"

    async def async_press(self) -> None:
        """Execute time synchronization command.

        Synchronizes the device's internal clock with network time,
        ensuring accurate timestamps for media metadata and logs.
        """
        try:
            _LOGGER.info("Synchronizing time for %s", self.speaker.name)
            await self.speaker.coordinator.player.sync_time()
            await self._async_execute_command_with_refresh("sync_time")

        except Exception as err:
            _LOGGER.error("Failed to sync time for %s: %s", self.speaker.name, err)
            raise
