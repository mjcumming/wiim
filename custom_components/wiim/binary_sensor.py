"""WiiM binary sensor platform.

BINARY_SENSOR platform provides connectivity monitoring for WiiM devices.
"""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENABLE_NETWORK_MONITORING, DOMAIN
from .coordinator import WiiMCoordinator
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


class WiiMConnectivityBinarySensor(WiimEntity, BinarySensorEntity):
    """Binary sensor for WiiM device connectivity."""

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry):
        """Initialize the connectivity binary sensor."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        self._attr_unique_id = f"{uuid}_connected"
        self._attr_name = "Connected"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_icon = "mdi:wifi"

    @property
    def is_on(self):
        """Return True if the device is connected."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        player = self.coordinator.player
        uuid = self._config_entry.unique_id or player.host
        attrs = {
            "ip_address": player.host,
            "device_uuid": uuid,
        }
        attrs["is_playing"] = player.is_playing
        if self.coordinator.update_interval:
            attrs["polling_interval"] = self.coordinator.update_interval.total_seconds()
        return attrs


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM binary sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    options = config_entry.options or {}
    entities = []

    if options.get(CONF_ENABLE_NETWORK_MONITORING):
        entities.append(WiiMConnectivityBinarySensor(coordinator, config_entry))

    async_add_entities(entities)
    _LOGGER.debug(
        "Created %d binary sensor entities for %s",
        len(entities),
        config_entry.data.get("host"),
    )
