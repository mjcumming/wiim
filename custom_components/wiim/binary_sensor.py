"""WiiM binary sensor platform.

BINARY_SENSOR platform is optional and currently no binary sensors are created.
This file is kept for potential future binary sensor entities.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM binary sensors.

    Currently no binary sensors are created.
    """
    # No entities to create at this time
    async_add_entities([])
    _LOGGER.debug("No binary sensor entities created for %s", config_entry.data.get("host"))
