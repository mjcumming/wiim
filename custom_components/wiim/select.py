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
        """Return available output options."""
        player = self.coordinator.data.get("player")
        if not player:
            return []

        # Always filter out generic "Bluetooth Out"
        # pywiim's player.available_outputs already handles refreshing the BT list
        # when requested, so we just present what the API gives us (minus the generic option)
        return [opt for opt in player.available_outputs if opt != "Bluetooth Out"]

    @property
    def current_option(self) -> str | None:
        """Return current output."""
        player = self.coordinator.data.get("player")
        if not player:
            return None

        # Check if BT output is active and which device is connected
        if player.is_bluetooth_output_active:
            for device in player.bluetooth_output_devices:
                if device.get("connected"):
                    return f"BT: {device['name']}"
            return "Bluetooth Out"

        # Hardware output (auto-detects Headphone Out on Ultra)
        return player.audio_output_mode

    async def async_select_option(self, option: str) -> None:
        """Change the selected output."""
        player = self.coordinator.data.get("player")
        if player:
            await player.audio.select_output(option)
            # State updates via callback automatically
