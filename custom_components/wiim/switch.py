"""WiiM switch platform.

Provides toggle controls for device features like subwoofer output and 12V trigger.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import WiiMCoordinator
from .entity import WiimEntity
from .utils import coerce_on_off, first_status_field, status_field, status_truthy

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM switch entities from a config entry."""
    coordinator: WiiMCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    player = coordinator.player

    entities: list[SwitchEntity] = []

    # 12V trigger output (WiiM Ultra / Pro / Pro Plus) - pywiim 2.1.89+
    try:
        if getattr(player, "supports_trigger_out", False):
            entities.append(WiiMTriggerOutSwitch(coordinator, config_entry))
            _LOGGER.debug("Creating 12V trigger switch entity")
    except Exception as err:
        _LOGGER.debug("Skipping 12V trigger switch entity - error checking support: %s", err)

    # Check if device supports subwoofer control (WiiM Ultra with firmware 5.2+)
    try:
        if player.supports_subwoofer:
            # Check if subwoofer is actually connected via status
            status = player.subwoofer_status
            if status_truthy(status_field(status, "plugged")):
                entities.append(WiiMSubwooferSwitch(coordinator, config_entry))
                _LOGGER.debug("Creating subwoofer switch entity - subwoofer connected")
            else:
                _LOGGER.debug("Skipping subwoofer switch entity - no subwoofer connected")
        else:
            _LOGGER.debug("Skipping subwoofer switch entity - device does not support subwoofer")
    except Exception as err:
        _LOGGER.debug("Skipping subwoofer switch entity - error checking support: %s", err)

    async_add_entities(entities)
    device_name = player.name or config_entry.title or "WiiM Speaker"
    _LOGGER.info("Created %d switch entities for %s", len(entities), device_name)


class WiiMTriggerOutSwitch(WiimEntity, SwitchEntity):
    """Switch entity for 12V trigger output (WiiM Ultra / Pro / Pro Plus)."""

    _attr_icon = "mdi:flash"
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the 12V trigger switch entity."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_trigger_out"
        self._attr_name = "12V trigger"
        self._is_on: bool | None = None

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        await self._update_state()

    async def _update_state(self) -> None:
        """Fetch current 12V trigger state from device."""
        try:
            status = await self.coordinator.player.client.get_trigger_out_status()
            raw_state: Any
            if isinstance(status, dict):
                raw_state = status.get("status", status.get("on"))
            else:
                raw_state = status

            if raw_state is None:
                raw_state = getattr(self.coordinator.player, "trigger_out_on", None)

            self._is_on = coerce_on_off(raw_state)
            _LOGGER.debug("12V trigger status raw=%r parsed=%r", raw_state, self._is_on)
        except Exception as err:
            _LOGGER.debug("Failed to get 12V trigger status: %s", err)
        finally:
            # This method runs from async tasks on coordinator updates; publish the
            # updated local state so entity availability/state is refreshed.
            if self.hass is not None:
                self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return True if 12V trigger output is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.coordinator.last_update_success and self._is_on is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn 12V trigger output on."""
        async with self.wiim_command("12V trigger on"):
            await self.coordinator.player.client.set_trigger_out(True)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn 12V trigger output off."""
        async with self.wiim_command("12V trigger off"):
            await self.coordinator.player.client.set_trigger_out(False)
        self._is_on = False
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from coordinator."""
        # _update_state() writes HA state when the async fetch completes.
        # Avoid immediate super() write with stale local cache.
        self.hass.async_create_task(self._update_state())


class WiiMSubwooferSwitch(WiimEntity, SwitchEntity):
    """Switch entity for subwoofer enable/disable control."""

    _attr_icon = "mdi:speaker"
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the subwoofer switch entity."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_subwoofer"
        self._attr_name = "Subwoofer"
        # Cache the state locally since we need to fetch it async
        self._is_on: bool | None = None

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        # Fetch initial state
        await self._update_state()

    async def _update_state(self) -> None:
        """Fetch current subwoofer state from device."""
        try:
            # Use async method for fresh data
            status = await self.coordinator.player.get_subwoofer_status()
            raw_state = first_status_field(status, ("status", "enabled", "on", "is_on", "state"))

            # Fallback to cached status if async payload doesn't include on/off field
            if raw_state is None:
                cached_status = getattr(self.coordinator.player, "subwoofer_status", None)
                raw_state = first_status_field(cached_status, ("status", "enabled", "on", "is_on", "state"))

            self._is_on = coerce_on_off(raw_state)
            _LOGGER.debug("Subwoofer status raw=%r parsed=%r", raw_state, self._is_on)
        except Exception as err:
            _LOGGER.debug("Failed to get subwoofer status: %s", err)
        finally:
            if self.hass is not None:
                self.async_write_ha_state()

    async def _set_subwoofer_enabled(self, enabled: bool) -> None:
        """Set subwoofer enabled state with pywiim API compatibility fallbacks."""
        player = self.coordinator.player

        # Preferred high-level API
        setter = getattr(player, "set_subwoofer_enabled", None)
        if callable(setter):
            await setter(enabled)
            return

        client = getattr(player, "client", None)
        if client is not None:
            # pywiim client-level alias (if available)
            client_setter = getattr(client, "set_subwoofer_enabled", None)
            if callable(client_setter):
                await client_setter(enabled)
                return

            # Legacy/alternate API naming
            status_setter = getattr(client, "set_subwoofer_status", None)
            if callable(status_setter):
                await status_setter(1 if enabled else 0)
                return

        raise RuntimeError("No supported pywiim subwoofer enable method found")

    @property
    def is_on(self) -> bool | None:
        """Return True if subwoofer is enabled."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.coordinator.last_update_success and self._is_on is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable subwoofer output."""
        async with self.wiim_command("enable subwoofer"):
            await self._set_subwoofer_enabled(True)
        await self._update_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable subwoofer output."""
        async with self.wiim_command("disable subwoofer"):
            await self._set_subwoofer_enabled(False)
        await self._update_state()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from coordinator."""
        # _update_state() writes HA state when the async fetch completes.
        # Avoid immediate super() write with stale local cache.
        self.hass.async_create_task(self._update_state())
