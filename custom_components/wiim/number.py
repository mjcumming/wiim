"""WiiM number platform.

Provides configurable numeric settings for device configuration.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSoundPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import WiiMCoordinator
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


def _status_field(status: Any, field: str, default: Any = None) -> Any:
    """Read status field from either dict-like or object-like payload."""
    if status is None:
        return default
    if isinstance(status, Mapping):
        return status.get(field, default)
    return getattr(status, field, default)


def _status_truthy(value: Any) -> bool:
    """Interpret common status payloads while preserving fallback truthiness."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "on", "yes", "enabled"}:
            return True
        if normalized in {"0", "false", "off", "no", "disabled"}:
            return False
    return bool(value)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM number entities from a config entry."""
    coordinator: WiiMCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    player = coordinator.player

    entities: list[NumberEntity] = []

    # Check if device supports subwoofer control (WiiM Ultra with firmware 5.2+)
    try:
        if player.supports_subwoofer:
            # Check if subwoofer is actually connected via status
            status = player.subwoofer_status
            if _status_truthy(_status_field(status, "plugged")):
                entities.append(WiiMSubwooferLevelNumber(coordinator, config_entry))
                _LOGGER.debug("Creating subwoofer level number entity - subwoofer connected")
            else:
                _LOGGER.debug("Skipping subwoofer level entity - no subwoofer connected")
        else:
            _LOGGER.debug("Skipping subwoofer level entity - device does not support subwoofer")
    except Exception as err:
        _LOGGER.debug("Skipping subwoofer level entity - error checking support: %s", err)

    async_add_entities(entities)
    device_name = player.name or config_entry.title or "WiiM Speaker"
    _LOGGER.info("Created %d number entities for %s", len(entities), device_name)


class WiiMSubwooferLevelNumber(WiimEntity, NumberEntity):
    """Number entity for subwoofer level adjustment (-15 to +15 dB)."""

    _attr_icon = "mdi:speaker-wireless"
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = -15.0
    _attr_native_max_value = 15.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = UnitOfSoundPressure.DECIBEL

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the subwoofer level number entity."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_subwoofer_level"
        self._attr_name = "Subwoofer Level"
        # Cache the value locally since we need to fetch it async
        self._value: float | None = None

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        # Fetch initial state
        await self._update_state()

    async def _update_state(self) -> None:
        """Fetch current subwoofer level from device."""
        try:
            # Use async method for fresh data
            status = await self.coordinator.player.get_subwoofer_status()
            if status:
                level = _status_field(status, "level")
                if level is not None:
                    self._value = float(level)
        except Exception as err:
            _LOGGER.debug("Failed to get subwoofer status: %s", err)
        finally:
            if self.hass is not None:
                self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        """Return the current subwoofer level."""
        return self._value

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.coordinator.last_update_success and self._value is not None

    async def async_set_native_value(self, value: float) -> None:
        """Set the subwoofer level."""
        level = int(value)
        async with self.wiim_command(f"set subwoofer level to {level} dB"):
            await self.coordinator.player.set_subwoofer_level(level)

        self._value = float(level)
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from coordinator."""
        # _update_state writes entity state once the async read completes.
        self.hass.async_create_task(self._update_state())
