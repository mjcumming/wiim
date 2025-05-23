"""Diagnostic sensors for WiiM speakers."""

from __future__ import annotations

import logging
from typing import Any, Final

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_GROUP_ROLE,
    DOMAIN,
)
from .coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)

SENSORS: Final = {
    ATTR_GROUP_ROLE: {
        "name": "Group Role",
        "unit": None,
        "device_class": None,
    },
    "ip_address": {
        "name": "IP Address",
        "unit": None,
        "device_class": None,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up diagnostic sensors for a config entry."""
    coordinator: WiiMCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for key in SENSORS:
        entities.append(_WiiMDiagnosticSensor(coordinator, key))

    async_add_entities(entities)


class _WiiMDiagnosticSensor(CoordinatorEntity[WiiMCoordinator], SensorEntity):
    """A single read‐only diagnostic attribute exposed as a sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WiiMCoordinator, attribute: str) -> None:
        super().__init__(coordinator)
        self._attribute = attribute
        meta = SENSORS[attribute]
        self._attr_unique_id = f"{coordinator.client.host}-{attribute}"
        self._attr_name = meta["name"]
        self._attr_native_unit_of_measurement = meta["unit"]
        self._attr_device_class = meta["device_class"]
        status = coordinator.data.get("status", {}) if isinstance(coordinator.data, dict) else {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.host)},
            name=coordinator.friendly_name,
            manufacturer="WiiM",
            model=status.get("hardware") or status.get("project"),
            sw_version=status.get("firmware"),
            connections={("mac", status.get("MAC"))} if status.get("MAC") else set(),
        )

    @property
    def native_value(self) -> Any | None:  # type: ignore[override]
        if self._attribute == ATTR_GROUP_ROLE:
            return self.coordinator.data.get("role")
        if self._attribute == "ip_address":
            return self.coordinator.client.host
        return None