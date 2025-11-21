"""WiiM switch platform.

Provides audio feature toggles when EQ controls are enabled.
Only creates switches for user-facing audio features.
"""

from __future__ import annotations

import logging
from typing import Any

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

    Creates EQ switch when EQ controls are enabled.
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
        self._attr_name = "Equalizer"  # Generic label
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool | None:
        """Return true if equalizer is enabled."""
        if not self.speaker.coordinator.data:
            return None

        eq_info = self.speaker.coordinator.data.get("eq", {})
        return bool(eq_info.get("enabled", False))

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the equalizer.

        Activates the device's built-in equalizer system, allowing audio
        enhancement through preset or custom EQ curves.
        """
        try:
            _LOGGER.info("Enabling equalizer for %s", self.speaker.name)
            await self.speaker.coordinator.player.set_eq_enabled(True)

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
            await self.speaker.coordinator.player.set_eq_enabled(False)

        except Exception as err:
            _LOGGER.error("Failed to disable equalizer for %s: %s", self.speaker.name, err)
            raise

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return equalizer-related information.

        pywiim provides:
        - player.eq_presets: list of available presets (cached from refresh())
        - player.eq_preset: current preset
        - capabilities["supports_eq"]: whether device supports EQ
        """
        if not self.speaker.coordinator.data:
            return {"eq_supported": False, "current_preset": None, "available_presets": []}

        player = self.speaker.coordinator.data.get("player")
        capabilities = (
            self.speaker.coordinator._capabilities if hasattr(self.speaker.coordinator, "_capabilities") else {}
        )

        # Get presets and current preset from Player object
        available_presets = []
        current_preset = None
        if player:
            available_presets = getattr(player, "eq_presets", []) or []
            current_preset = getattr(player, "eq_preset", None)

        return {
            "eq_supported": capabilities.get("supports_eq", False),
            "current_preset": current_preset,
            "available_presets": available_presets,
        }
