"""WiiM number platform.

Provides configurable numeric settings that leverage the Speaker architecture
for device configuration and performance tuning.
"""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WiimEntity
from .coordinator import WiiMCoordinator
from .utils import wiim_command

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM number entities from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    entities = []

    # Channel Balance Number Entity
    # WARNING: Uses unofficial API endpoints - may not work on all firmware versions
    entities.append(WiiMChannelBalance(coordinator, config_entry))

    async_add_entities(entities)
    device_name = coordinator.player.name or config_entry.title or "WiiM Speaker"
    _LOGGER.info("Created %d number entities for %s", len(entities), device_name)


class WiiMChannelBalance(WiimEntity, NumberEntity):
    """Number entity for left/right channel balance control.

    WARNING: This uses unofficial API endpoints and may not work on all firmware versions.
    Balance ranges from -1.0 (full left) to 1.0 (full right), 0.0 is center.
    """

    _attr_mode = NumberMode.SLIDER
    _attr_has_entity_name = True
    _attr_native_min_value = -1.0
    _attr_native_max_value = 1.0
    _attr_native_step = 0.1
    _attr_icon = "mdi:sine-wave"

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the channel balance entity."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_channel_balance"
        self._attr_name = "Channel Balance"
        # Track current value optimistically
        self._balance = 0.0

    @property
    def native_value(self) -> float:
        """Return the current channel balance value."""
        return self._balance

    async def async_set_native_value(self, value: float) -> None:
        """Set the channel balance value.

        Args:
            value: Balance value from -1.0 (left) to 1.0 (right), 0.0 is center
        """
        device_name = self.player.name or self._config_entry.title or "WiiM Speaker"
        async with wiim_command(device_name, "set channel balance"):
            _LOGGER.info("Setting channel balance to %s for %s", value, device_name)
            await self.coordinator.player.set_channel_balance(value)

            # Update optimistic state
            self._balance = value
            self.async_write_ha_state()

            _LOGGER.info("Channel balance set successfully for %s", device_name)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return extra state attributes."""
        return {
            "channel_balance": f"{self._balance:.1f}",
            "note": "Balance: -1.0 = full left, 0.0 = center, 1.0 = full right",
            "warning": "Unofficial API endpoint - may not work on all firmware versions",
        }
