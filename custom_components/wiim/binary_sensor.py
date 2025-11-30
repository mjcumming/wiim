"""WiiM binary sensor platform.

BINARY_SENSOR platform provides connectivity monitoring for WiiM devices.
"""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENABLE_NETWORK_MONITORING

_LOGGER = logging.getLogger(__name__)


class WiiMConnectivityBinarySensor(BinarySensorEntity):
    """Binary sensor for WiiM device connectivity."""

    def __init__(self, speaker):
        """Initialize the connectivity binary sensor."""
        self.speaker = speaker
        self._attr_unique_id = f"{speaker.uuid}_connected"
        self._attr_name = "Connected"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_icon = "mdi:wifi"

    @property
    def is_on(self):
        """Return True if the device is connected."""
        return getattr(self.speaker, "available", False)

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        attrs = {
            "ip_address": getattr(self.speaker, "ip", None),
            "device_uuid": getattr(self.speaker, "uuid", None),
        }
        if hasattr(self.speaker, "coordinator"):
            coordinator = self.speaker.coordinator
            if hasattr(coordinator, "data"):
                player = coordinator.data.get("player")
                if player is not None:
                    attrs["is_playing"] = getattr(player, "play_state", None) == "play"
            if hasattr(coordinator, "update_interval") and coordinator.update_interval:
                attrs["polling_interval"] = getattr(coordinator.update_interval, "seconds", None)
            if hasattr(coordinator, "_consecutive_failures"):
                attrs["consecutive_failures"] = coordinator._consecutive_failures
        return attrs


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM binary sensors."""
    from .data import get_speaker_from_config_entry

    speaker = get_speaker_from_config_entry(hass, config_entry)
    options = config_entry.options or {}
    entities = []

    if options.get(CONF_ENABLE_NETWORK_MONITORING) and speaker:
        entities.append(WiiMConnectivityBinarySensor(speaker))

    async_add_entities(entities)
    _LOGGER.debug(
        "Created %d binary sensor entities for %s",
        len(entities),
        config_entry.data.get("host"),
    )
