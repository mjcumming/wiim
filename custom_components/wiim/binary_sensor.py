"""WiiM binary sensor platform.

Provides device connectivity monitoring when network monitoring is enabled.
Avoids redundant sensors that duplicate information available elsewhere.
"""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENABLE_NETWORK_MONITORING, DOMAIN
from .data import Speaker
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM binary sensors with smart filtering.

    Only creates connectivity sensors when network monitoring is enabled.
    Avoids redundant sensors that duplicate media_player or role sensor information.
    """
    speaker: Speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    entry = hass.data[DOMAIN][config_entry.entry_id]["entry"]

    entities = []

    # Only create connectivity sensor when network monitoring is enabled
    if entry.options.get(CONF_ENABLE_NETWORK_MONITORING, False):
        entities.append(WiiMConnectivityBinarySensor(speaker))

    async_add_entities(entities)
    _LOGGER.info("Created %d binary sensor entities for %s (filtering applied)", len(entities), speaker.name)


class WiiMConnectivityBinarySensor(WiimEntity, BinarySensorEntity):
    """Device connectivity and health status sensor.

    Only created when network monitoring is enabled.
    Useful for monitoring device availability and network health.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:wifi"

    def __init__(self, speaker: Speaker) -> None:
        """Initialize connected status binary sensor."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_connected"
        self._attr_name = "Connected"  # Generic label
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool:
        """Return true if device is connected and responding."""
        return self.speaker.available

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return connectivity and health diagnostics."""
        attrs = {
            "ip_address": self.speaker.ip,
            "device_uuid": self.speaker.uuid,
        }

        # Add defensive polling info if available
        polling_info = self.speaker.coordinator.data.get("polling", {})
        if polling_info:
            attrs.update(
                {
                    "is_playing": polling_info.get("is_playing"),
                    "polling_interval": polling_info.get("interval"),
                    "api_capabilities": polling_info.get("api_capabilities", {}),
                }
            )

        # Add failure count if available
        if hasattr(self.speaker.coordinator, "_consecutive_failures"):
            attrs["consecutive_failures"] = getattr(self.speaker.coordinator, "_consecutive_failures", 0)

        return attrs
