"""Select entities for WiiM integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
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
    """Set up WiiM select entities."""
    speaker = get_speaker_from_config_entry(hass, config_entry)

    entities = []

    # Determine capabilities safely. Prefer client.capabilities if it is a dict,
    # otherwise use coordinator._capabilities if it is a dict. Avoid treating
    # MagicMock attributes as truthy capability containers.
    capabilities = None

    client = getattr(speaker.coordinator, "client", None)
    client_capabilities = getattr(client, "capabilities", None)
    if isinstance(client_capabilities, dict):
        capabilities = client_capabilities
    else:
        coordinator_capabilities = getattr(speaker.coordinator, "_capabilities", None)
        if isinstance(coordinator_capabilities, dict):
            capabilities = coordinator_capabilities

    if isinstance(capabilities, dict):
        supports_audio_output = bool(capabilities.get("supports_audio_output", False))
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
        if capabilities is None:
            return []

    # Bluetooth device selection is now integrated into Audio Output Mode select
    # No separate Bluetooth device select entity needed

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
    def options(self) -> list[str]:
        """Return available output options.

        Available as a property on player: player.available_outputs
        Returns a list of output names (hardware modes + paired BT devices).
        Returns empty list if device doesn't support audio output or data not yet loaded.
        """
        player = self.coordinator.data.get("player")
        if not player:
            return []

        # Access as a property on player (not a method)
        # available_outputs is a property on player, not player.audio
        # Returns None if not supported/not loaded, or empty list if supported but no outputs
        available_outputs = getattr(player, "available_outputs", None)
        if available_outputs is None:
            # Device may not support audio output or data not yet loaded
            # pywiim handles fetching automatically via player.refresh()
            return []

        # Return the list (may be empty if device supports audio output but has no outputs configured)
        return available_outputs

    @property
    def current_option(self) -> str | None:
        """Return current output.

        Returns the currently selected output mode, which must match one of the
        options in the available_outputs list. Returns None if output status
        is not available or doesn't match any option.
        """
        player = self.coordinator.data.get("player")
        if not player:
            return None

        # Get available options to ensure we return a valid value
        available = player.available_outputs
        if not available:
            # No outputs available (device may not support or data not loaded)
            # pywiim handles fetching automatically via player.refresh()
            return None

        # Check if BT output is active and which device is connected
        if player.is_bluetooth_output_active:
            for device in player.bluetooth_output_devices:
                if device.get("connected"):
                    bt_option = f"BT: {device['name']}"
                    # Ensure this option exists in available_outputs
                    if bt_option in available:
                        return bt_option
            # Fall back to generic "Bluetooth Out" if no specific device found
            if "Bluetooth Out" in available:
                return "Bluetooth Out"

        # Get current hardware output mode
        current_mode = player.audio_output_mode
        if current_mode and current_mode in available:
            return current_mode

        # If current_mode doesn't match, try to find a matching option
        # (handles case where device returns slightly different format)
        if current_mode:
            for option in available:
                if option.lower() == current_mode.lower():
                    return option

        # If still no match, return None (will show as "Unknown" in HA)
        # pywiim handles fetching automatically - no manual refresh needed
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected output."""
        player = self.coordinator.data.get("player")
        if not player:
            return
        await player.audio.select_output(option)
        # State updates automatically via callback - no manual refresh needed
