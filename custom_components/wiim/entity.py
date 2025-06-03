"""Base entity class for WiiM integration."""

from __future__ import annotations

import logging

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .data import Speaker, get_wiim_data
from .const import DOMAIN  # Make sure DOMAIN is imported

_LOGGER = logging.getLogger(__name__)


class WiimEntity(CoordinatorEntity):
    """Base class for all WiiM entities (like SonosEntity)."""

    _attr_has_entity_name = True  # Use device name for clean entity IDs

    def __init__(self, speaker: Speaker) -> None:
        """Initialize with speaker reference."""
        # Initialize coordinator entity with speaker's coordinator
        super().__init__(speaker.coordinator)  # Pass the coordinator instance
        self.speaker = speaker
        self._attr_unique_id = self.speaker.uuid  # This is the crucial part
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.speaker.uuid)},
            "name": self.speaker.name,
            "manufacturer": "WiiM",  # Or dynamically if available
            "model": self.speaker.model,
            "sw_version": self.speaker.firmware,
            # "via_device": (DOMAIN, self.speaker.config_entry.entry_id), # If relevant
        }

    async def async_added_to_hass(self) -> None:
        """Set up event listening and entity registration."""
        # Call parent first to register as coordinator listener
        await super().async_added_to_hass()

        # Register in central mapping for O(1) lookups
        data = get_wiim_data(self.hass)
        data.entity_id_mappings[self.entity_id] = self.speaker

        # Listen for speaker state changes (event-driven pattern)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"wiim_state_updated_{self.speaker.uuid}",
                self.async_write_ha_state,
            )
        )

        _LOGGER.debug("Entity %s registered for speaker %s", self.entity_id, self.speaker.uuid)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up entity registration."""
        data = get_wiim_data(self.hass)
        data.entity_id_mappings.pop(self.entity_id, None)
        _LOGGER.debug("Entity %s unregistered", self.entity_id)

    async def _async_execute_command_with_refresh(self, command_type: str) -> None:
        """Execute a command and request a coordinator refresh.

        Args:
            command_type: A string describing the command for logging.
        """
        # The actual command execution is handled by the controller/speaker methods
        # This method's role is to ensure data is refreshed after a command.
        _LOGGER.debug(
            "User command '%s' executed for %s, requesting data refresh",
            command_type,
            self.speaker.name,
        )
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Delegate to speaker (single source of truth)."""
        return self.speaker.device_info

    @property
    def available(self) -> bool:
        """Delegate to speaker."""
        return self.speaker.available


class WiimPollingEntity(WiimEntity):
    """Base class for WiiM entities that require polling (like SonosPollingEntity)."""

    _attr_should_poll = True

    def __init__(self, speaker: Speaker) -> None:
        """Initialize polling entity."""
        super().__init__(speaker)

    async def async_update(self) -> None:
        """Update the entity state by requesting coordinator refresh."""
        if not self.available:
            return

        try:
            # Request fresh data from coordinator
            await self.speaker.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.debug("Polling update failed for %s: %s", self.entity_id, err)
