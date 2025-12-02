"""Select entities for WiiM integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

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

    # Check if device supports audio output mode control using pywiim's capability property
    player = getattr(speaker.coordinator, "player", None)
    if not player:
        # No player available yet, skip select entities
        _LOGGER.debug("Skipping select entities - player not available")
        return

    supports_audio_output = bool(getattr(player, "supports_audio_output", False))
    if supports_audio_output:
        # Audio Output Mode Select
        entities.append(WiiMOutputModeSelect(speaker))
        _LOGGER.debug("Creating audio output select entity - device supports audio output")
    else:
        _LOGGER.debug(
            "Skipping audio output select entity - device does not support audio output (capability=%s)",
            supports_audio_output,
        )

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

        Implementation follows pywiim integration guide pattern:
        https://github.com/mjcumming/pywiim/blob/main/docs/integration/HA_INTEGRATION.md#audio-output-selection
        """
        player = self.coordinator.data.get("player")
        if not player:
            return None

        # Get available options to ensure we return a valid value
        # Per pywiim guide: available_outputs is a property on player
        available = getattr(player, "available_outputs", None)
        if not available:
            # No outputs available (device may not support or data not loaded)
            # pywiim handles fetching automatically via player.refresh()
            return None

        # Check if BT output is active and which device is connected
        # Per pywiim guide: Check is_bluetooth_output_active first
        is_bt_active = getattr(player, "is_bluetooth_output_active", False)
        if is_bt_active:
            # Find the specific connected BT device from bluetooth_output_devices
            # Note: We only show specific BT devices, not generic "Bluetooth Out"
            # (per pywiim guide: "Generic 'Bluetooth Out' is removed when specific BT devices are available")
            bt_devices = getattr(player, "bluetooth_output_devices", [])
            for device in bt_devices:
                if device.get("connected"):
                    bt_option = f"BT: {device['name']}"
                    # Ensure this option exists in available_outputs
                    if bt_option in available:
                        return bt_option

        # Get current hardware output mode
        # Per pywiim guide: Use player.audio_output_mode property
        current_mode = getattr(player, "audio_output_mode", None)
        if current_mode and current_mode in available:
            return current_mode

        # If current_mode doesn't match, try to find a matching option
        # (handles case where device returns slightly different format)
        if current_mode:
            for option in available:
                if option.lower() == current_mode.lower():
                    return option

        # If still no match, log debug to help diagnose (not warning - may be normal during startup)
        _LOGGER.debug(
            "[%s] Current audio output mode '%s' from pywiim doesn't match any option in available_outputs=%s. "
            "This may indicate audio output status hasn't been fetched yet or a format mismatch.",
            self.speaker.name,
            current_mode,
            available,
        )
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected output."""
        player = self.coordinator.data.get("player")
        if not player:
            raise HomeAssistantError("Player is not available")

        try:
            await player.audio.select_output(option)
            # State updates automatically via callback - no manual refresh needed
        except (WiiMConnectionError, WiiMTimeoutError) as err:
            # Connection/timeout errors are transient
            _LOGGER.warning(
                "Connection issue selecting audio output '%s' on %s: %s. The device may be temporarily unreachable.",
                option,
                self.speaker.name,
                err,
            )
            raise HomeAssistantError(
                f"Unable to select audio output '{option}' on {self.speaker.name}: device temporarily unreachable"
            ) from err
        except WiiMError as err:
            # Check if it's a Bluetooth connection error (device returned invalid JSON)
            error_str = str(err).lower()
            if "bluetooth" in error_str or "connectbta2dp" in error_str or "invalid json" in error_str:
                _LOGGER.warning(
                    "Bluetooth connection error selecting audio output '%s' on %s: %s. "
                    "The device may not support this Bluetooth device or it may be out of range.",
                    option,
                    self.speaker.name,
                    err,
                )
                raise HomeAssistantError(
                    f"Failed to connect to Bluetooth device '{option}' on {self.speaker.name}. "
                    "The device may not be available or may not support this Bluetooth connection."
                ) from err
            # Other errors
            _LOGGER.error(
                "Failed to select audio output '%s' on %s: %s",
                option,
                self.speaker.name,
                err,
                exc_info=True,
            )
            raise HomeAssistantError(f"Failed to select audio output '{option}': {err}") from err
