"""WiiM switch platform.

Provides toggle controls for device features like subwoofer output.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up WiiM switch entities from a config entry."""
    coordinator: WiiMCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    player = coordinator.player

    entities: list[SwitchEntity] = []

    # Check if device supports subwoofer control (WiiM Ultra with firmware 5.2+)
    try:
        if player.supports_subwoofer:
            # Check if subwoofer is actually connected via status
            status = player.subwoofer_status
            if status and status.get("plugged"):
                entities.append(WiiMSubwooferSwitch(coordinator, config_entry))
                _LOGGER.debug("Creating subwoofer switch entity - subwoofer connected")
            else:
                _LOGGER.debug("Skipping subwoofer switch entity - no subwoofer connected")
        else:
            _LOGGER.debug("Skipping subwoofer switch entity - device does not support subwoofer")
    except Exception as err:
        _LOGGER.debug("Skipping subwoofer switch entity - error checking support: %s", err)

    async_add_entities(entities)
    device_name = player.name or config_entry.title or "WiiM Speaker"
    _LOGGER.info("Created %d switch entities for %s", len(entities), device_name)


class WiiMSubwooferSwitch(WiimEntity, SwitchEntity):
    """Switch entity for subwoofer enable/disable control."""

    _attr_icon = "mdi:speaker"
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the subwoofer switch entity."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_subwoofer"
        self._attr_name = "Subwoofer"
        # Cache the state locally since we need to fetch it async
        self._is_on: bool | None = None

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        # Fetch initial state
        await self._update_state()

    async def _update_state(self) -> None:
        """Fetch current subwoofer state from device."""
        try:
            # Use async method for fresh data
            status = await self.coordinator.player.get_subwoofer_status()
            if status:
                self._is_on = status.get("status", False)
        except Exception as err:
            _LOGGER.debug("Failed to get subwoofer status: %s", err)

    @property
    def is_on(self) -> bool | None:
        """Return True if subwoofer is enabled."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.coordinator.last_update_success and self._is_on is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable subwoofer output."""
        async with self.wiim_command("enable subwoofer"):
            await self.coordinator.player.set_subwoofer_enabled(True)

        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable subwoofer output."""
        async with self.wiim_command("disable subwoofer"):
            await self.coordinator.player.set_subwoofer_enabled(False)

        self._is_on = False
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from coordinator."""
        # Schedule state update (async operation)
        self.hass.async_create_task(self._update_state())
        super()._handle_coordinator_update()
