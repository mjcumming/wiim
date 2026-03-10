"""WiiM light platform."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import WiiMCoordinator
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM Light platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    player = coordinator.player

    entities: list[LightEntity] = [WiiMLEDLight(coordinator, config_entry)]

    # Display (WiiM Ultra LCD) – on/off + brightness; only when supported
    if getattr(player, "supports_display_config", False):
        entities.append(WiiMDisplayLight(coordinator, config_entry))

    async_add_entities(entities)
    device_name = player.name or config_entry.title or "WiiM Speaker"
    _LOGGER.info(
        "Created light entities for %s: LED%s",
        device_name,
        " + Display" if len(entities) > 1 else "",
    )


class WiiMLEDLight(WiimEntity, LightEntity):
    """Light entity for the speaker front-panel LED (on/off only)."""

    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True
    _attr_assumed_state = True

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialise the LED light entity."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_led"
        self._attr_name = "LED"
        self._is_on: bool | None = None

    @property
    def available(self) -> bool:
        """Return entity availability."""
        try:
            return self.coordinator.last_update_success
        except Exception:
            return False

    @property
    def is_on(self) -> bool | None:  # type: ignore[override]
        """Return LED power state (assumed)."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:  # type: ignore[override]
        """Turn LED on. Brightness is ignored (legacy LED is on/off only)."""
        _ = kwargs.get(ATTR_BRIGHTNESS)  # ignored
        async with self.wiim_command("turn on LED"):
            await self.coordinator.player.set_led(True)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:  # type: ignore[override]
        """Turn LED off."""
        async with self.wiim_command("turn off LED"):
            await self.coordinator.player.set_led(False)
        self._is_on = False
        self.async_write_ha_state()


class WiiMDisplayLight(WiimEntity, LightEntity):
    """Light entity for WiiM Ultra LCD display (on/off + brightness)."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True
    _attr_assumed_state = True  # No read API for display state

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialise the Display light entity."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_display"
        self._attr_name = "Display"
        self._is_on: bool | None = None
        self._brightness: int | None = None  # 0-255

    @property
    def available(self) -> bool:
        """Return entity availability."""
        try:
            return self.coordinator.last_update_success
        except Exception:
            return False

    @property
    def is_on(self) -> bool | None:  # type: ignore[override]
        """Return display power state (assumed)."""
        return self._is_on

    @property
    def brightness(self) -> int | None:  # type: ignore[override]
        """Return display brightness (0-255, assumed)."""
        return self._brightness

    async def async_turn_on(self, **kwargs: Any) -> None:  # type: ignore[override]
        """Turn display on and optionally set brightness."""
        brightness_255: int = int(kwargs.get(ATTR_BRIGHTNESS, 255))
        brightness_pct: int = max(0, min(100, round(brightness_255 * 100 / 255)))

        async with self.wiim_command("turn on display"):
            await self.coordinator.player.set_display_enabled(True)
        if brightness_pct != 100:
            async with self.wiim_command("set display brightness"):
                await self.coordinator.player.set_display_config(
                    auto_sense_enable=0,
                    default_bright=brightness_pct,
                    disable=0,
                )

        self._is_on = True
        self._brightness = brightness_255
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:  # type: ignore[override]
        """Turn display off."""
        async with self.wiim_command("turn off display"):
            await self.coordinator.player.set_display_enabled(False)
        self._is_on = False
        self.async_write_ha_state()
