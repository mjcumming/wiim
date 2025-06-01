"""Entity resolution utilities for WiiM integration.

Functions for mapping entity IDs to coordinators and IP addresses.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant

from ..const import DOMAIN

if TYPE_CHECKING:
    from ..coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)


def find_coordinator(hass: HomeAssistant, entity_id: str) -> WiiMCoordinator | None:
    """Return coordinator for the given entity ID."""
    _LOGGER.debug("[WiiM] find_coordinator: Looking up coordinator for entity_id=%s", entity_id)

    # Method 1: Check all available coordinators and see if any match the entity_id pattern
    coordinators = []
    for entry_id, entry_data in hass.data[DOMAIN].items():
        if isinstance(entry_data, dict) and "coordinator" in entry_data:
            coord = entry_data["coordinator"]
            if hasattr(coord, "client"):
                coordinators.append(coord)

    _LOGGER.debug(
        "[WiiM] find_coordinator: Found %d coordinators: %s",
        len(coordinators),
        [coord.client.host for coord in coordinators],
    )

    # Method 2: Try direct entity registry lookup
    try:
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        ent_entry = ent_reg.async_get(entity_id)

        if ent_entry and ent_entry.platform == DOMAIN:
            _LOGGER.debug("[WiiM] find_coordinator: Found registry entry with unique_id=%s", ent_entry.unique_id)

            # Try to match coordinator by unique_id or host IP
            for coord in coordinators:
                # Try matching by host IP
                if coord.client.host == ent_entry.unique_id:
                    _LOGGER.debug("[WiiM] find_coordinator: Matched by host IP")
                    return coord

                # Try matching by formatted IP (unique_id might be formatted)
                formatted_host = f"wiim_{coord.client.host.replace('.', '_')}"
                if formatted_host == ent_entry.unique_id:
                    _LOGGER.debug("[WiiM] find_coordinator: Matched by formatted host")
                    return coord

                # Try matching by device UUID if available
                if coord.data and coord.data.get("status"):
                    device_uuid = coord.data["status"].get("uuid") or coord.data["status"].get("device_id")
                    if device_uuid:
                        uuid_based_unique_id = f"wiim_{device_uuid}"
                        if uuid_based_unique_id == ent_entry.unique_id:
                            _LOGGER.debug("[WiiM] find_coordinator: Matched by UUID")
                            return coord
    except Exception as err:
        _LOGGER.debug("[WiiM] find_coordinator: Entity registry lookup failed: %s", err)

    # Method 3: Try pattern-based matching for common entity_id formats
    # Extract potential device identifier from entity_id (remove media_player. prefix)
    if entity_id.startswith("media_player."):
        device_part = entity_id[13:]  # Remove "media_player." prefix

        for coord in coordinators:
            if not coord.data or not coord.data.get("status"):
                continue

            status = coord.data["status"]
            device_name = status.get("DeviceName") or status.get("device_name") or ""

            # Try exact match with device name (converted to entity format)
            normalized_device_name = device_name.lower().replace(" ", "_").replace("-", "_")
            if normalized_device_name == device_part:
                _LOGGER.debug("[WiiM] find_coordinator: Matched by device name pattern")
                return coord

            # Try matching with formatted host
            formatted_host = f"wiim_{coord.client.host.replace('.', '_')}"
            if formatted_host == entity_id:
                _LOGGER.debug("[WiiM] find_coordinator: Matched by formatted host pattern")
                return coord

    _LOGGER.debug(
        "[WiiM] find_coordinator: No coordinator found for entity_id=%s. Available coordinators: %s",
        entity_id,
        [
            f"{coord.client.host}({coord.data.get('status', {}).get('DeviceName', 'Unknown') if coord.data else 'No data'})"
            for coord in coordinators
        ],
    )
    return None


def entity_id_to_host(hass: HomeAssistant, entity_id: str) -> str | None:
    """Map HA entity_id to device IP address (host). Returns None if not found."""
    _LOGGER.debug("[WiiM] entity_id_to_host() called with entity_id=%s", entity_id)

    # First try: Direct IP-based mapping (legacy scheme)
    for coord in _get_all_coordinators(hass):
        expected = f"media_player.wiim_{coord.client.host.replace('.', '_')}"
        if expected == entity_id:
            _LOGGER.debug("entity_id_to_host: Direct match found for host=%s", coord.client.host)
            return coord.client.host

    # Second try: Entity registry lookup
    try:
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        ent_entry = ent_reg.async_get(entity_id)

        if ent_entry and ent_entry.unique_id:
            unique = ent_entry.unique_id
            _LOGGER.debug("entity_id_to_host: Registry lookup found unique_id=%s", unique)

            # Try to match by unique_id (which should be the host IP)
            for coord in _get_all_coordinators(hass):
                if coord.client.host == unique:
                    _LOGGER.debug("entity_id_to_host: Match found via unique_id for host=%s", coord.client.host)
                    return coord.client.host

            # Try to match by device name
            device_name = ent_entry.name or ent_entry.original_name
            if device_name:
                for coord in _get_all_coordinators(hass):
                    status = coord.data.get("status", {}) if coord.data else {}
                    device_name_from_status = status.get("DeviceName") or status.get("device_name")
                    if device_name_from_status and device_name_from_status.lower() == device_name.lower():
                        _LOGGER.debug("entity_id_to_host: Match found via device name for host=%s", coord.client.host)
                        return coord.client.host
    except Exception as reg_err:
        _LOGGER.debug("entity_id_to_host: Entity registry lookup failed: %s", reg_err)

    # Third try: Use the find_coordinator function and extract host from it
    coord = find_coordinator(hass, entity_id)
    if coord and hasattr(coord, "client"):
        _LOGGER.debug("entity_id_to_host: Match found via find_coordinator for host=%s", coord.client.host)
        return coord.client.host

    _LOGGER.warning("entity_id_to_host: No match found for entity_id=%s", entity_id)
    return None


def _get_all_coordinators(hass: HomeAssistant) -> list:
    """Get all WiiM coordinators from hass.data."""
    coordinators = []
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if isinstance(entry_data, dict) and "coordinator" in entry_data:
            coord = entry_data["coordinator"]
            if hasattr(coord, "client"):
                coordinators.append(coord)
    return coordinators
