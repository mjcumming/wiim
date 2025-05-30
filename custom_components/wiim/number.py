"""Number entities to adjust polling interval and volume step per WiiM device."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_POLL_INTERVAL,
    CONF_VOLUME_STEP,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)
from .coordinator import WiiMCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities for a config entry."""
    coordinator: WiiMCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[NumberEntity] = [
        _PollIntervalNumber(coordinator, entry),
        _VolumeStepNumber(coordinator, entry),
    ]
    async_add_entities(entities)


class _BaseWiiMNumber(CoordinatorEntity[WiiMCoordinator], NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: WiiMCoordinator, entry: ConfigEntry, key: str, name: str):
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_unique_id = f"{coordinator.client.host}-{key}"
        self._attr_name = name
        status = coordinator.data.get("status", {}) if isinstance(coordinator.data, dict) else {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.host)},
            name=coordinator.friendly_name,
            manufacturer="WiiM",
            model=status.get("project") or status.get("hardware"),
            sw_version=status.get("firmware"),
            connections={("mac", status.get("MAC"))} if status.get("MAC") else set(),
        )

    def _save(self, value):
        # Update config_entry.options atomically
        options = dict(self._entry.options)
        options[self._key] = value
        self.hass.config_entries.async_update_entry(self._entry, options=options)


class _PollIntervalNumber(_BaseWiiMNumber):
    _attr_native_min_value = 1
    _attr_native_max_value = 60
    _attr_native_step = 1
    _attr_unit_of_measurement = "s"

    def __init__(self, coordinator: WiiMCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry, CONF_POLL_INTERVAL, "Polling Interval")

    @property
    def native_value(self):
        return self._entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

    async def async_set_native_value(self, value):
        # Update coordinator interval immediately
        value = int(value)
        self.coordinator.update_interval = timedelta(seconds=value)
        self.coordinator._base_poll_interval = value
        self._save(value)
        # Restart the coordinator's polling loop
        await self.coordinator.async_stop()
        await self.coordinator.async_start()
        await self.coordinator.async_refresh()


class _VolumeStepNumber(_BaseWiiMNumber):
    _attr_native_min_value = 1
    _attr_native_max_value = 50
    _attr_native_step = 1
    _attr_unit_of_measurement = "%"

    def __init__(self, coordinator: WiiMCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry, CONF_VOLUME_STEP, "Volume Step")

    @property
    def native_value(self):
        # Convert from internal decimal (0.01-0.5) to percentage (1-50%)
        decimal_value = self._entry.options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
        return int(decimal_value * 100)

    async def async_set_native_value(self, value):
        # Convert from percentage (1-50%) to internal decimal (0.01-0.5)
        decimal_value = float(value) / 100.0
        self._save(decimal_value)
