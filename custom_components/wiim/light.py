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

    # Create LED light entity for all devices
    # Device-specific LED commands are handled in the API layer
    entities = [WiiMLEDLight(coordinator, config_entry)]
    async_add_entities(entities)
    device_name = coordinator.player.name or config_entry.title or "WiiM Speaker"
    _LOGGER.info("Created LED light entity for %s", device_name)


class WiiMLEDLight(WiimEntity, LightEntity):
    """Light entity representing the speaker front-panel LED."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_has_entity_name = True  # Use device name in the UI
    _attr_entity_registry_enabled_default = True
    # No GET endpoint exists – operate optimistically.
    _attr_assumed_state = True

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialise the LED light entity."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_led"
        self._attr_name = "LED"
        # Remember best-guess state so the UI has feedback.
        self._is_on: bool | None = None
        self._brightness: int | None = None  # 0-255

    # ------------------------------------------------------------------
    # Entity state helpers
    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        """Return entity availability."""
        # Also check if device supports LED control
        try:
            # This is a simple check - in practice, the entity won't be created for unsupported devices
            return self.coordinator.last_update_success
        except Exception:
            return False

    @property
    def is_on(self) -> bool | None:  # type: ignore[override]
        """Return LED power state (assumed)."""
        return self._is_on

    @property
    def brightness(self) -> int | None:  # type: ignore[override]
        """Return current brightness value (0-255, assumed)."""
        return self._brightness

    # ------------------------------------------------------------------
    # LightEntity API
    # ------------------------------------------------------------------
    async def async_turn_on(self, **kwargs: Any) -> None:  # type: ignore[override]
        """Turn LED on (and optionally set brightness)."""
        # Default to full brightness when no value provided.
        brightness_255: int = int(kwargs.get(ATTR_BRIGHTNESS, 255))
        brightness_pct: int = max(0, min(100, round(brightness_255 * 100 / 255)))

        device_name = self.player.name or self._config_entry.title or "WiiM Speaker"
        _LOGGER.debug(
            "Setting LED on %s to brightness %d%% (raw %d)",
            device_name,
            brightness_pct,
            brightness_255,
        )
        async with self.wiim_command("turn on LED"):
            await self.coordinator.player.set_led(True)
            # Only send brightness command when different from 100 % to
            # avoid unnecessary round-trip on most devices.
            if brightness_pct != 100:
                await self.coordinator.player.set_led_brightness(brightness_pct)

        # Update optimistic local state
        self._is_on = True
        self._brightness = brightness_255
        self.async_write_ha_state()

        # State updates automatically via callback - no manual refresh needed

    async def async_turn_off(self, **kwargs: Any) -> None:  # type: ignore[override]
        """Turn LED off."""
        async with self.wiim_command("turn off LED"):
            await self.coordinator.player.set_led(False)

        # Update optimistic local state
        self._is_on = False
        self.async_write_ha_state()

        # State updates automatically via callback - no manual refresh needed

    async def async_set_brightness(self, brightness: int) -> None:
        """Helper to set brightness directly from service call (0-255)."""
        if brightness < 0 or brightness > 255:
            raise ValueError("Brightness must be between 0 and 255")

        brightness_pct = max(0, min(100, round(brightness * 100 / 255)))
        device_name = self.player.name or self._config_entry.title or "WiiM Speaker"
        _LOGGER.debug("Setting LED brightness for %s: %d%% (raw %d)", device_name, brightness_pct, brightness)

        async with self.wiim_command("set LED brightness"):
            # Ensure LED is on when setting brightness (matches device behaviour)
            await self.coordinator.player.set_led(True)
            await self.coordinator.player.set_led_brightness(brightness_pct)

        self._is_on = True
        self._brightness = brightness
        self.async_write_ha_state()

        # State updates automatically via callback - no manual refresh needed
