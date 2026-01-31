"""Helper functions for accessing coordinators from config entries."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "get_coordinator_from_entry",
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


def get_all_coordinators(hass: HomeAssistant) -> list[WiiMCoordinator]:
    """Get all registered coordinators."""
    coordinators = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id in hass.data.get(DOMAIN, {}):
            coordinators.append(get_coordinator_from_entry(hass, entry))
    return coordinators
