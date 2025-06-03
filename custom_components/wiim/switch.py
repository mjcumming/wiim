"""WiiM switch platform.

Provides audio feature toggles when EQ controls are enabled.
Only creates switches for user-facing audio features.
"""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENABLE_EQ_CONTROLS, DOMAIN
from .data import Speaker, get_speaker_from_config_entry
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM switches with filtering.

    Only creates audio feature switches when EQ controls are enabled.
    Avoids internal functionality switches that users don't need.
    """
    speaker = get_speaker_from_config_entry(hass, config_entry)
    entry = hass.data[DOMAIN][config_entry.entry_id]["entry"]

    entities = []

    # Only create equalizer switch when EQ controls are enabled
    if entry.options.get(CONF_ENABLE_EQ_CONTROLS, False):
        entities.append(WiiMEqualizerSwitch(speaker))

    async_add_entities(entities)
    _LOGGER.info("Created %d switch entities for %s (filtering applied)", len(entities), speaker.name)


class WiiMEqualizerSwitch(WiimEntity, SwitchEntity):
    """Equalizer enable/disable switch for audio enhancement control.

    Only created when EQ controls are enabled.
    Allows users to toggle the device's built-in equalizer system.
    """

    _attr_icon = "mdi:equalizer"

    def __init__(self, speaker: Speaker) -> None:
        """Initialize equalizer switch."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_equalizer"
        self._attr_name = "Equalizer"  # Clean name without device duplication

    @property
    def is_on(self) -> bool | None:
        """Return true if equalizer is enabled."""
        if not self.speaker.coordinator.data:
            return None

        status = self.speaker.coordinator.data.get("status", {})
        return status.get("eq_enabled", False)

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the equalizer.

        Activates the device's built-in equalizer system, allowing audio
        enhancement through preset or custom EQ curves.
        """
        try:
            _LOGGER.info("Enabling equalizer for %s", self.speaker.name)
            await self.speaker.coordinator.client.set_eq_enabled(True)
            await self._async_execute_command_with_refresh("equalizer_on")

        except Exception as err:
            _LOGGER.error("Failed to enable equalizer for %s: %s", self.speaker.name, err)
            raise

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the equalizer.

        Deactivates the device's equalizer system, returning to flat
        frequency response for unprocessed audio output.
        """
        try:
            _LOGGER.info("Disabling equalizer for %s", self.speaker.name)
            await self.speaker.coordinator.client.set_eq_enabled(False)
            await self._async_execute_command_with_refresh("equalizer_off")

        except Exception as err:
            _LOGGER.error("Failed to disable equalizer for %s: %s", self.speaker.name, err)
            raise

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return equalizer-related information."""
        if not self.speaker.coordinator.data:
            return {}

        status = self.speaker.coordinator.data.get("status", {})
        attrs = {
            "eq_supported": getattr(self.speaker.coordinator, "eq_supported", False),
        }

        # Add current EQ preset if available
        if eq_preset := status.get("eq_preset"):
            attrs["current_preset"] = eq_preset

        # Add available presets if available
        if hasattr(self.speaker.coordinator, "eq_presets") and self.speaker.coordinator.eq_presets:
            attrs["available_presets"] = self.speaker.coordinator.eq_presets

        return attrs
