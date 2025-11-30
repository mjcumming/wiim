"""WiiM switch platform.

SWITCH platform is in CORE_PLATFORMS but currently no switches are created.
This file is kept for future switch entities if needed.
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
    """Set up WiiM switches.

    Currently no switches are created. SWITCH platform is in CORE_PLATFORMS
    for potential future use (e.g., group mute control).
    """
    # No entities to create at this time
    async_add_entities([])
    _LOGGER.debug("No switch entities created for %s", config_entry.data.get("host"))
