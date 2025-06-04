"""WiiM number platform.

Provides configurable numeric settings that leverage the Speaker architecture
for device configuration and performance tuning.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import get_speaker_from_config_entry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM number entities from a config entry.

    Currently no number entities are created - volume step is handled
    in the device configuration menu only to avoid duplication.
    """
    speaker = get_speaker_from_config_entry(hass, config_entry)

    # NO entities created - volume step is config-only
    entities = []

    async_add_entities(entities)
    _LOGGER.info("Number platform setup complete for %s (no entities - config-only)", speaker.name)
