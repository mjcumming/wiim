"""Select entities for WiiM integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pywiim.exceptions import WiiMError

from .const import DOMAIN
from .coordinator import WiiMCoordinator
from .entity import WiimEntity

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

        # Get current hardware output mode
        current_mode = player.audio_output_mode

        # Check if Bluetooth output is active
        # audio_output_mode returns "Bluetooth Out" when BT is active,
        # but available_outputs has "BT: DeviceName" format
        if current_mode and current_mode.lower() in ("bluetooth out", "bt"):
            # Find which BT device is connected
            for device in player.bluetooth_output_devices or []:
                if device.get("connected"):
                    bt_option = f"BT: {device['name']}"
                    if bt_option in available:
                        return bt_option

        # Direct match
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
            async with self.wiim_command(f"select audio output '{option}'"):
                # Use pywiim's unified output selection API (hardware modes + BT devices)
                await player.audio.select_output(option)
                # State updates automatically via callback - no manual refresh needed
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
