"""Select entities for WiiM integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# from .const import DOMAIN
from .data import Speaker, get_speaker_from_config_entry
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM select entities."""
    speaker = get_speaker_from_config_entry(hass, config_entry)

    entities = []

    # Check if device supports audio output before creating select entity
    # Access capabilities from coordinator where they're properly stored
    capabilities = getattr(speaker.coordinator, "_capabilities", {})
    if capabilities:
        supports_audio_output = capabilities.get("supports_audio_output", True)  # Keep original default
        if supports_audio_output:
            # Audio Output Mode Select
            entities.append(WiiMOutputModeSelect(speaker))
            _LOGGER.debug("Creating audio output select entity - device supports audio output")
        else:
            _LOGGER.debug(
                "Skipping audio output select entity - device does not support audio output (capability=%s)",
                supports_audio_output,
            )
    else:
        # Fallback: create entity if capabilities not available (assume supported for backwards compatibility)
        _LOGGER.warning(
            "Capabilities not available for %s - creating audio output select entity as fallback", speaker.name
        )
        entities.append(WiiMOutputModeSelect(speaker))

    async_add_entities(entities)
    _LOGGER.info(
        "Created %d select entities for %s",
        len(entities),
        speaker.name,
    )


class WiiMOutputModeSelect(WiimEntity, SelectEntity):
    """Select entity for audio output mode control."""

    _attr_icon = "mdi:audio-video"
    _attr_has_entity_name = True

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_output_mode"
        self._attr_name = "Audio Output Mode"

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        try:
            # Check if core device communication is working
            if (
                hasattr(self.speaker.coordinator, "_device_info_working")
                and not self.speaker.coordinator._device_info_working
            ):
                # Device communication is failing - return None to show as unavailable
                # This indicates a device connectivity issue rather than audio output issue
                return None

            return self.speaker.get_current_output_mode()
        except Exception:
            # Return None if we can't determine the current option
            # This will show as "unknown" in the UI instead of "unavailable"
            _LOGGER.debug("Could not determine current audio output mode for %s", self.speaker.name)
            return None

    @property
    def options(self) -> list[str]:
        """Return a list of available options."""
        try:
            # Get standard selectable modes
            standard_modes = self.speaker.get_output_mode_list()

            # Get any discovered modes from the device
            discovered_modes = self.speaker.get_discovered_output_modes()

            # Combine and deduplicate
            all_modes = list(set(standard_modes + discovered_modes))

            # Sort for consistent ordering
            return sorted(all_modes)
        except Exception:
            # If we can't determine available options, return basic modes
            # This prevents the entity from becoming unavailable
            _LOGGER.debug("Could not determine audio output options for %s, using defaults", self.speaker.name)
            from .const import SELECTABLE_OUTPUT_MODES

            return SELECTABLE_OUTPUT_MODES.copy()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        _LOGGER.info("WiiM Output Mode Select: User selected '%s'", option)
        try:
            # Get the controller and call the output mode selection method
            from .media_controller import MediaPlayerController

            controller = MediaPlayerController(self.speaker)
            _LOGGER.info("WiiM Output Mode Select: Calling select_output_mode('%s')", option)
            await controller.select_output_mode(option)
            _LOGGER.info("WiiM Output Mode Select: Successfully set output mode to '%s'", option)
        except Exception as err:
            _LOGGER.warning("WiiM Output Mode Select: Failed to select output mode '%s': %s", option, err)
            # Don't re-raise the exception - let Home Assistant handle it
            # This prevents the entity from becoming unavailable

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "bluetooth_output_active": self.speaker.is_bluetooth_output_active(),
            "audio_cast_active": self.speaker.is_audio_cast_active(),
            "discovered_modes": self.speaker.get_discovered_output_modes(),
        }
