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

from .data import Speaker, get_speaker_from_config_entry
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM number entities from a config entry."""
    speaker = get_speaker_from_config_entry(hass, config_entry)

    entities = []

    # Channel Balance Number Entity
    # WARNING: This uses unofficial API endpoints and may not work on all firmware versions
    # TODO: Enable when ready for production use
    # entities.append(WiiMChannelBalance(speaker))

    async_add_entities(entities)
    _LOGGER.info("Created %d number entities for %s", len(entities), speaker.name)


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

    def __init__(self, speaker: Speaker) -> None:
        """Initialize the channel balance entity."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_channel_balance"
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
        try:
            _LOGGER.info("Setting channel balance to %s for %s", value, self.speaker.name)
            await self.speaker.coordinator.player.client.set_channel_balance(value)

            # Update optimistic state
            self._balance = value
            self.async_write_ha_state()

            _LOGGER.info("Channel balance set successfully for %s", self.speaker.name)
        except Exception as err:
            _LOGGER.error("Failed to set channel balance for %s: %s", self.speaker.name, err)
            raise

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return extra state attributes."""
        return {
            "channel_balance": f"{self._balance:.1f}",
            "note": "Balance: -1.0 = full left, 0.0 = center, 1.0 = full right",
            "warning": "Unofficial API endpoint - may not work on all firmware versions",
        }
