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
    _LOGGER.info("Created %d maintenance button entities for %s", len(entities), speaker.name)


class WiiMRebootButton(WiimEntity, ButtonEntity):
    """Device reboot button for system maintenance.

    Useful for resolving connectivity issues or applying firmware updates.
    """

    _attr_icon = "mdi:restart"

    def __init__(self, speaker: Speaker) -> None:
        """Initialize reboot button."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_reboot"
        self._attr_name = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self.speaker.name} Reboot"  # Display name includes action

    async def async_press(self) -> None:
        """Execute device reboot command.

        Sends reboot command to the device and requests status refresh
        to monitor the reboot process.
        """
        try:
            _LOGGER.info("Initiating reboot for %s", self.speaker.name)
            await self.speaker.coordinator.client.reboot()
            await self._async_execute_command_with_refresh("reboot")

        except Exception as err:
            _LOGGER.error("Failed to reboot %s: %s", self.speaker.name, err)
            raise


class WiiMSyncTimeButton(WiimEntity, ButtonEntity):
    """Device time synchronization button.

    Synchronizes the device clock with network time for accurate timestamps.
    """

    _attr_icon = "mdi:clock-sync"

    def __init__(self, speaker: Speaker) -> None:
        """Initialize time sync button."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_sync_time"
        self._attr_name = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self.speaker.name} Sync Time"  # Display name includes action

    async def async_press(self) -> None:
        """Execute time synchronization command.

        Synchronizes the device's internal clock with network time,
        ensuring accurate timestamps for media metadata and logs.
        """
        try:
            _LOGGER.info("Synchronizing time for %s", self.speaker.name)
            await self.speaker.coordinator.client.sync_time()
            await self._async_execute_command_with_refresh("sync_time")

        except Exception as err:
            _LOGGER.error("Failed to sync time for %s: %s", self.speaker.name, err)
            raise
