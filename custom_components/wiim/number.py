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
from .data import Speaker

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM number entities from a config entry.

    Creates configurable numeric controls for device settings and performance
    optimization. All entities integrate with the Speaker architecture for
    consistent state management.
    """
    speaker: Speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]

    # Only create Volume Step - polling interval is handled in options menu
    entities = [
        WiiMVolumeStepNumber(speaker),
        # Removed WiiMPollingIntervalNumber - redundant with options menu
    ]

    async_add_entities(entities)
    _LOGGER.info("Created %d number entities for %s", len(entities), speaker.name)


class WiiMVolumeStepNumber(WiimEntity, NumberEntity):
    """Volume step size configuration for granular volume control."""

    _attr_icon = "mdi:volume-medium"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1
    _attr_native_max_value = 20
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"

    def __init__(self, speaker: Speaker) -> None:
        """Initialize volume step number entity."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_volume_step"
        self._attr_name = "Volume Step"  # Clean name without device duplication
        self._volume_step = 5  # Default step size

    @property
    def native_value(self) -> int:
        """Return the current volume step size."""
        return self._volume_step

    async def async_set_native_value(self, value: float) -> None:
        """Set the volume step size.

        This setting controls how much the volume changes when using
        volume up/down commands. Smaller values provide finer control,
        larger values provide quicker adjustment.
        """
        step_size = int(value)

        try:
            _LOGGER.info("Setting volume step to %d%% for %s", step_size, self.speaker.name)
            self._volume_step = step_size

            # Notify that the configuration has changed
            self.speaker.coordinator.record_user_command("volume_step_change")

            # Update the entity state
            self.async_write_ha_state()

        except Exception as err:
            _LOGGER.error("Failed to set volume step for %s: %s", self.speaker.name, err)
            raise

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return configuration guidance."""
        return {
            "description": "Volume change amount for up/down commands",
            "recommended_range": "3-10%",
            "current_setting": f"{self._volume_step}%",
        }
