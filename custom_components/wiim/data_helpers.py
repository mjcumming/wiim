"""Speaker lookup and config entry helper functions.

Extracted from data.py as part of Phase 2 refactor to create focused,
maintainable modules under 300 LOC each.

This module contains:
- Speaker lookup functions (UUID, IP, all speakers)
- Config entry helper functions
- IP update logic

All functions follow the simplified architecture using HA config entries
as source of truth without complex registries.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN

if TYPE_CHECKING:
    from .data import Speaker

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "get_speaker_from_config_entry",
    "find_speaker_by_uuid",
    "find_speaker_by_ip",
    "get_all_speakers",
    "update_speaker_ip",
]


def get_speaker_from_config_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> Speaker:
    """Get speaker from config entry - standard HA pattern.

    Args:
        hass: Home Assistant instance
        config_entry: Configuration entry for the speaker

    Returns:
        Speaker instance for the config entry

    Raises:
        RuntimeError: If speaker not found for config entry
    """
    try:
        return cast("Speaker", hass.data[DOMAIN][config_entry.entry_id]["speaker"])
    except KeyError as err:
        _LOGGER.error("Speaker not found for config entry %s: %s", config_entry.entry_id, err)
        raise RuntimeError(f"Speaker not found for {config_entry.entry_id}") from err


def find_speaker_by_uuid(hass: HomeAssistant, uuid: str) -> Speaker | None:
    """Find speaker by UUID using config entry iteration.

    Uses HA's built-in config entry system for efficient UUID lookup.

    Args:
        hass: Home Assistant instance
        uuid: Speaker UUID to search for

    Returns:
        Speaker instance if found, None otherwise
    """
    if not uuid:
        return None

    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, uuid)
    if entry and entry.entry_id in hass.data.get(DOMAIN, {}):
        return get_speaker_from_config_entry(hass, entry)
    return None


def find_speaker_by_ip(hass: HomeAssistant, ip: str) -> Speaker | None:
    """Find speaker by IP address using config entry iteration.

    Iterates through config entries to find matching IP address.
    Used for group member resolution and device discovery.

    Args:
        hass: Home Assistant instance
        ip: IP address to search for

    Returns:
        Speaker instance if found, None otherwise
    """
    if not ip:
        return None

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_HOST) == ip and entry.entry_id in hass.data.get(DOMAIN, {}):
            return get_speaker_from_config_entry(hass, entry)
    return None


def get_all_speakers(hass: HomeAssistant) -> list[Speaker]:
    """Get all registered speakers.

    Returns all speakers from config entries that have been successfully
    initialized in hass.data[DOMAIN].

    Args:
        hass: Home Assistant instance

    Returns:
        List of all registered Speaker instances
    """
    speakers = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id in hass.data.get(DOMAIN, {}):
            speakers.append(get_speaker_from_config_entry(hass, entry))
    return speakers


def update_speaker_ip(hass: HomeAssistant, speaker: Speaker, new_ip: str) -> None:
    """Update speaker IP address through config entry system.

    Updates both the config entry data and the speaker object when
    a device's IP address changes (e.g., DHCP reassignment).

    Args:
        hass: Home Assistant instance
        speaker: Speaker instance to update
        new_ip: New IP address for the speaker
    """
    if speaker.ip_address == new_ip:
        return

    _LOGGER.info("Updating speaker %s IP: %s -> %s", speaker.name, speaker.ip_address, new_ip)

    # Update config entry
    hass.config_entries.async_update_entry(speaker.config_entry, data={**speaker.config_entry.data, CONF_HOST: new_ip})

    # Update speaker object
    speaker.ip_address = new_ip
