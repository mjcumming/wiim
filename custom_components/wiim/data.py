"""Helper functions for accessing coordinators from config entries."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "get_coordinator_from_entry",
    "find_coordinator_by_uuid",
    "find_coordinator_by_ip",
    "get_all_coordinators",
]


# ===== HELPER FUNCTIONS =====


def get_coordinator_from_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> WiiMCoordinator:
    """Get coordinator from config entry."""
    try:
        return hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    except KeyError as err:
        _LOGGER.error("Coordinator not found for config entry %s: %s", config_entry.entry_id, err)
        raise RuntimeError(f"Coordinator not found for {config_entry.entry_id}") from err


def find_coordinator_by_uuid(hass: HomeAssistant, uuid: str) -> WiiMCoordinator | None:
    """Find coordinator by UUID."""
    if not uuid:
        return None
    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, uuid)
    if entry and entry.entry_id in hass.data.get(DOMAIN, {}):
        return get_coordinator_from_entry(hass, entry)
    return None


def find_coordinator_by_ip(hass: HomeAssistant, ip: str) -> WiiMCoordinator | None:
    """Find coordinator by IP address."""
    if not ip:
        return None

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_HOST) == ip and entry.entry_id in hass.data.get(DOMAIN, {}):
            return get_coordinator_from_entry(hass, entry)
    return None


def get_all_coordinators(hass: HomeAssistant) -> list[WiiMCoordinator]:
    """Get all registered coordinators."""
    coordinators = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id in hass.data.get(DOMAIN, {}):
            coordinators.append(get_coordinator_from_entry(hass, entry))
    return coordinators
