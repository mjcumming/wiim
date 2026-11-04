"""Select entities for WiiM integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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

    # EQ presets: same list as media_player sound_mode (player.supports_eq / eq_presets)
    if coordinator.player.supports_eq:
        entities.append(WiiMEQPresetSelect(coordinator, config_entry))
        _LOGGER.debug("Creating EQ preset select entity - device supports EQ")
    else:
        _LOGGER.debug("Skipping EQ preset select entity - device does not support EQ")

    if coordinator.player.client.capabilities.get("supports_peq", False):
        try:
            await coordinator.player.initialize_peq_presets()
        except WiiMError as err:
            _LOGGER.warning("Could not read parametric EQ presets for %s: %s", config_entry.title, err)
        # PEQ can be active even when there are no saved presets to load.
        entities.append(WiiMPEQPresetSelect(coordinator, config_entry))

    # DAC filter: pywiim sets supports_digital_filter only when the device returns a list.
    if coordinator.player.supports_digital_filter:
        entities.append(WiiMDACFilterSelect(coordinator, config_entry))
        _LOGGER.debug("Creating DAC filter select entity - device supports digital filter")
    else:
        _LOGGER.debug("Skipping DAC filter select entity - device does not support digital filter")

    # RoomFit: created when the device has saved profiles. An empty list means
    # none are saved yet, so a later first profile needs an integration reload.
    if coordinator.player.room_correction_profiles:
        entities.append(WiiMRoomFitSelect(coordinator, config_entry))
        _LOGGER.debug("Creating RoomFit select entity - device has saved profiles")
    else:
        _LOGGER.debug("Skipping RoomFit select entity - no saved profiles")

    # Output channel: pywiim determines whether the device supports the control.
    if coordinator.player.supports_output_channel:
        entities.append(WiiMChannelSelect(coordinator, config_entry))
        _LOGGER.debug("Creating channel select entity - device supports output channel")
    else:
        _LOGGER.debug("Skipping channel select entity - device does not support output channel")

    async_add_entities(entities)
    device_name = coordinator.player.name or config_entry.title or "WiiM Speaker"
    _LOGGER.debug(
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


class WiiMEQPresetSelect(WiimEntity, SelectEntity):
    """Select entity for EQ preset control.

    Mirrors media player sound mode: ``player.eq_preset`` / ``player.eq_presets``
    and ``player.set_eq_preset()``. Created only when ``player.supports_eq``.
    """

    _attr_icon = "mdi:equalizer"
    _attr_has_entity_name = True

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_eq_preset"
        self._attr_name = "EQ Preset"

    @property
    def options(self) -> list[str]:
        """Return available EQ presets, always including Off."""
        player = self.coordinator.player
        presets = [str(preset) for preset in (player.eq_presets or [])]
        if "Off" not in presets:
            presets.insert(0, "Off")
        current = player.eq_preset
        if current and all(option.casefold() != current.casefold() for option in presets):
            presets.append(current)
        return presets

    @property
    def current_option(self) -> str | None:
        """Return the current EQ preset, or Off when EQ is disabled."""
        options = self.options
        eq_preset = self.coordinator.player.eq_preset
        if not eq_preset:
            return None
        current = str(eq_preset)
        if current in options:
            return current
        for option in options:
            if option.lower() == current.lower():
                return option
        return None

    async def async_select_option(self, option: str) -> None:
        """Apply the selected EQ preset (Off disables EQ)."""
        player = self.coordinator.player
        if option == player.eq_preset and (player.eq_is_custom or option not in (player.eq_presets or [])):
            return
        async with self.wiim_command(f"select EQ preset '{option}'"):
            await player.set_eq_preset(option)


class WiiMPEQPresetSelect(WiimEntity, SelectEntity):
    """Select a saved parametric EQ preset for the current source."""

    _attr_icon = "mdi:equalizer"
    _attr_has_entity_name = True
    _attr_translation_key = "peq_preset"

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_peq_preset"
        self._attr_name = "Parametric EQ Preset"

    @property
    def _off_option(self) -> str:
        """Choose a disable label that does not shadow an existing preset."""
        names = {name.casefold() for name in self.player.peq_presets}
        if self.player.peq_enabled is True and self.player.peq_preset:
            names.add(self.player.peq_preset.casefold())
        if "off" not in names:
            return "Off"
        option = "Off (disable)"
        suffix = 2
        while option.casefold() in names:
            option = f"Off (disable {suffix})"
            suffix += 1
        return option

    @property
    def options(self) -> list[str]:
        """Return the cached preset names supplied by pywiim."""
        player = self.coordinator.player
        presets = [self._off_option, *player.peq_presets]
        current = player.peq_preset
        if player.peq_enabled is True and current and all(option.casefold() != current.casefold() for option in presets):
            presets.append(current)
        return presets

    @property
    def current_option(self) -> str | None:
        """Return the active preset when PEQ is enabled."""
        player = self.coordinator.player
        if player.peq_enabled is False:
            return self._off_option
        if player.peq_enabled is True and player.peq_preset:
            return next((option for option in self.options if option.casefold() == player.peq_preset.casefold()), None)
        return None

    async def async_select_option(self, option: str) -> None:
        """Load a saved preset for this device's current source."""
        player = self.coordinator.player
        if option == player.peq_preset and option not in player.peq_presets:
            return
        async with self.wiim_command(f"select parametric EQ preset '{option}'"):
            if option == self._off_option:
                await player.disable_peq()
            else:
                await player.set_peq_preset(option)


class WiiMDACFilterSelect(WiimEntity, SelectEntity):
    """Select entity for the DAC digital filter.

    Created only when ``player.supports_digital_filter`` is true. Options and the
    current value come from pywiim's cached list. The filter affects analog Line Out.
    """

    _attr_icon = "mdi:sine-wave"
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "dac_filter"

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_dac_filter"
        self._attr_name = "DAC Filter"

    @property
    def options(self) -> list[str]:
        """Return filter names from the device."""
        return list(self.coordinator.player.digital_filter_types or [])

    @property
    def current_option(self) -> str | None:
        """Return the current filter name when it is one of the options."""
        current = self.coordinator.player.digital_filter
        if current and current in self.options:
            return str(current)
        return None

    async def async_select_option(self, option: str) -> None:
        """Set the DAC filter by the name pywiim cached from the device."""
        async with self.wiim_command(f"select DAC filter '{option}'"):
            await self.coordinator.player.set_digital_filter(option)


class WiiMRoomFitSelect(WiimEntity, SelectEntity):
    """Select entity for a saved RoomFit profile.

    Created only when ``player.room_correction_profiles`` is non-empty. ``Off``
    disables RoomFit. Any other option loads that saved profile.
    """

    _attr_icon = "mdi:chart-bell-curve"
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "room_fit"

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_room_fit"
        self._attr_name = "RoomFit"

    @property
    def options(self) -> list[str]:
        """Return Off plus the saved profile names."""
        return ["Off", *list(self.coordinator.player.room_correction_profiles or [])]

    @property
    def current_option(self) -> str | None:
        """Return Off while RoomFit is disabled, otherwise the selected profile."""
        current = self.coordinator.player.room_correction
        if current and current in self.options:
            return str(current)
        return None

    async def async_select_option(self, option: str) -> None:
        """Load the selected RoomFit profile, or turn RoomFit off."""
        async with self.wiim_command(f"select RoomFit '{option}'"):
            await self.coordinator.player.set_room_correction(option)


# Option label -> pywiim output channel name
CHANNEL_OPTIONS: dict[str, str] = {"Stereo": "stereo", "Left": "left", "Right": "right"}


class WiiMChannelSelect(WiimEntity, SelectEntity):
    """Select entity for the output channel: Stereo, Left or Right.

    Created only when ``player.supports_output_channel`` is true. The current value
    is ``player.output_channel``, refreshed by pywiim for the player's current role.
    Works on a group member too, so two speakers can play left and right of the same stream.
    """

    _attr_icon = "mdi:surround-sound-2-0"
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "output_channel"
    _attr_options = list(CHANNEL_OPTIONS)

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_output_channel"
        self._attr_name = "Channel"

    @property
    def current_option(self) -> str | None:
        """Return Stereo, Left or Right, or None while the channel is unknown."""
        current = self.coordinator.player.output_channel
        for option, name in CHANNEL_OPTIONS.items():
            if name == current:
                return option
        return None

    async def async_select_option(self, option: str) -> None:
        """Set the output channel."""
        async with self.wiim_command(f"select channel '{option}'"):
            await self.coordinator.player.set_output_channel(CHANNEL_OPTIONS[option])
