"""Select entities for WiiM integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

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
    """Set up WiiM select entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    entities = []

    # Check if device supports audio output mode control using pywiim's capability property
    if coordinator.player.supports_audio_output:
        # Audio Output Mode Select
        entities.append(WiiMOutputModeSelect(coordinator, config_entry))
        _LOGGER.debug("Creating audio output select entity - device supports audio output")
    else:
        _LOGGER.debug("Skipping audio output select entity - device does not support audio output")

    # Bluetooth device selection is now integrated into Audio Output Mode select
    # No separate Bluetooth device select entity needed

    async_add_entities(entities)
    device_name = coordinator.player.name or config_entry.title or "WiiM Speaker"
    _LOGGER.info(
        "Created %d select entities for %s",
        len(entities),
        device_name,
    )


class WiiMOutputModeSelect(WiimEntity, SelectEntity):
    """Select entity for audio output mode control."""

    _attr_icon = "mdi:audio-video"
    _attr_has_entity_name = True

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_output_mode"
        self._attr_name = "Audio Output Mode"

    @property
    def options(self) -> list[str]:
        """Return available output options from pywiim player.available_outputs."""
        return self.coordinator.player.available_outputs or []

    @property
    def current_option(self) -> str | None:
        """Return current output mode."""
        player = self.coordinator.player
        available = player.available_outputs
        if not available:
            return None

        # Check if BT output is active and which device is connected
        if player.is_bluetooth_output_active:
            for device in player.bluetooth_output_devices:
                if device.get("connected"):
                    bt_option = f"BT: {device['name']}"
                    if bt_option in available:
                        return bt_option

        # Get current hardware output mode
        current_mode = player.audio_output_mode
        if current_mode and current_mode in available:
            return current_mode

        # Handle case-insensitive matching
        if current_mode:
            for option in available:
                if option.lower() == current_mode.lower():
                    return option

        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected output."""
        player = self.coordinator.player
        device_name = self.player.name or self._config_entry.title or "WiiM Speaker"

        # Check if it's a Bluetooth connection error (device returned invalid JSON)
        try:
            async with wiim_command(device_name, f"select audio output '{option}'"):
                await player.select_output(option)  # pywiim v2.1.37+
                # State updates automatically via callback - no manual refresh needed
        except HomeAssistantError:
            # Re-raise HomeAssistantError as-is (already wrapped by wiim_command)
            raise
        except WiiMError as err:
            # Check if it's a Bluetooth connection error (device returned invalid JSON)
            error_str = str(err).lower()
            if "bluetooth" in error_str or "connectbta2dp" in error_str or "invalid json" in error_str:
                _LOGGER.warning(
                    "Bluetooth connection error selecting audio output '%s' on %s: %s. "
                    "The device may not support this Bluetooth device or it may be out of range.",
                    option,
                    device_name,
                    err,
                )
                raise HomeAssistantError(
                    f"Failed to connect to Bluetooth device '{option}' on {device_name}. "
                    "The device may not be available or may not support this Bluetooth connection."
                ) from err
            # Other errors - re-raise as HomeAssistantError
            raise HomeAssistantError(f"Failed to select audio output '{option}': {err}") from err
