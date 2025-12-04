"""WiiM number platform.

Provides configurable numeric settings that leverage the Speaker architecture
for device configuration and performance tuning.
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
    """Set up WiiM number entities from a config entry."""
    # Currently no number entities are exposed in the UI
    # Channel balance is available as a service/action only
    entities = []
    async_add_entities(entities)
