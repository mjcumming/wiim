"""Device Registry for WiiM Integration.

Provides centralized device registration and lookup using MAC addresses as stable identifiers.
Supports multiple entity types per device (individual media player, group master, etc.).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from ..coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)


def normalize_mac(mac: str) -> str:
    """Normalize MAC address to lowercase without separators."""
    if not mac:
        return ""
    return mac.lower().replace(":", "").replace("-", "").replace(" ", "")


def get_mac_from_coordinator(coordinator: WiiMCoordinator) -> str | None:
    """Extract and normalize MAC address from coordinator data."""
    if not coordinator.data or "status" not in coordinator.data:
        return None

    status = coordinator.data["status"]
    mac = status.get("MAC") or status.get("mac")

    if not mac or mac.lower() in ("unknown", "none", "null", ""):
        return None

    return normalize_mac(mac)


def initialize_device_registry(hass: HomeAssistant, domain: str) -> None:
    """Initialize the device registry data structures."""
    hass.data.setdefault(domain, {})
    hass.data[domain].setdefault("_coordinators", {})  # MAC -> coordinator
    hass.data[domain].setdefault("_ip_to_mac", {})  # IP -> MAC
    hass.data[domain].setdefault("_devices", {})  # MAC -> device info
    hass.data[domain].setdefault("_group_entities", {})  # Keep existing structure


def register_coordinator(hass: HomeAssistant, domain: str, coordinator: WiiMCoordinator, entry_id: str) -> bool:
    """Register a coordinator in the device registry.

    Returns True if successfully registered, False if MAC unavailable.
    """
    initialize_device_registry(hass, domain)

    mac = get_mac_from_coordinator(coordinator)
    ip = coordinator.client.host

    if not mac:
        _LOGGER.warning("[WiiM] Device %s has no valid MAC address, using IP-only registration", ip)
        # Still register in legacy structure for backward compatibility
        hass.data[domain][entry_id] = {"coordinator": coordinator}
        return False

    # Register in all lookup structures
    hass.data[domain]["_coordinators"][mac] = coordinator
    hass.data[domain]["_ip_to_mac"][ip] = mac
    hass.data[domain]["_devices"][mac] = {
        "coordinator": coordinator,
        "entry_id": entry_id,
        "ip": ip,
        "mac": mac,
    }

    # Maintain legacy structure for backward compatibility
    hass.data[domain][entry_id] = {"coordinator": coordinator}

    _LOGGER.debug("[WiiM] Registered device: MAC=%s, IP=%s, entry_id=%s", mac, ip, entry_id)
    return True


def unregister_coordinator(hass: HomeAssistant, domain: str, coordinator: WiiMCoordinator, entry_id: str) -> None:
    """Unregister a coordinator from the device registry."""
    if domain not in hass.data:
        return

    mac = get_mac_from_coordinator(coordinator)
    ip = coordinator.client.host

    # Remove from legacy structure
    hass.data[domain].pop(entry_id, None)

    if not mac:
        return

    # Remove from new structures
    hass.data[domain].get("_coordinators", {}).pop(mac, None)
    hass.data[domain].get("_ip_to_mac", {}).pop(ip, None)
    hass.data[domain].get("_devices", {}).pop(mac, None)

    _LOGGER.debug("[WiiM] Unregistered device: MAC=%s, IP=%s, entry_id=%s", mac, ip, entry_id)


def find_coordinator_by_mac(hass: HomeAssistant, domain: str, mac: str) -> WiiMCoordinator | None:
    """Find coordinator by MAC address."""
    if domain not in hass.data:
        return None

    coordinators = hass.data[domain].get("_coordinators", {})
    normalized_mac = normalize_mac(mac)
    return coordinators.get(normalized_mac)


def find_coordinator_by_ip(hass: HomeAssistant, domain: str, ip: str) -> WiiMCoordinator | None:
    """Find coordinator by IP address."""
    if domain not in hass.data:
        return None

    # Try IP cache first
    ip_to_mac = hass.data[domain].get("_ip_to_mac", {})
    if ip in ip_to_mac:
        return find_coordinator_by_mac(hass, domain, ip_to_mac[ip])

    # Fallback: search all coordinators
    coordinators = hass.data[domain].get("_coordinators", {})
    for coord in coordinators.values():
        if hasattr(coord, "client") and coord.client.host == ip:
            # Update cache for future lookups
            mac = get_mac_from_coordinator(coord)
            if mac:
                ip_to_mac[ip] = mac
            return coord

    return None


def get_all_coordinators(hass: HomeAssistant, domain: str) -> list[WiiMCoordinator]:
    """Get all registered coordinators."""
    if domain not in hass.data:
        return []

    # Use MAC-based registry if available
    coordinators = hass.data[domain].get("_coordinators", {})
    if coordinators:
        return list(coordinators.values())

    # Fallback to legacy structure
    result = []
    for entry_data in hass.data[domain].values():
        if isinstance(entry_data, dict) and "coordinator" in entry_data:
            result.append(entry_data["coordinator"])

    return result


def update_ip_cache(hass: HomeAssistant, domain: str) -> None:
    """Update the IP to MAC mapping cache."""
    if domain not in hass.data:
        return

    coordinators = hass.data[domain].get("_coordinators", {})
    ip_to_mac = hass.data[domain].setdefault("_ip_to_mac", {})

    # Clear and rebuild cache
    ip_to_mac.clear()

    for mac, coord in coordinators.items():
        if hasattr(coord, "client"):
            ip_to_mac[coord.client.host] = mac


def get_device_info(hass: HomeAssistant, domain: str, mac_or_ip: str) -> dict[str, Any] | None:
    """Get device information by MAC or IP address."""
    if domain not in hass.data:
        return None

    # Try MAC first
    devices = hass.data[domain].get("_devices", {})
    normalized_mac = normalize_mac(mac_or_ip)

    if normalized_mac in devices:
        return devices[normalized_mac]

    # Try IP lookup
    coord = find_coordinator_by_ip(hass, domain, mac_or_ip)
    if coord:
        mac = get_mac_from_coordinator(coord)
        if mac and mac in devices:
            return devices[mac]

    return None


def register_group_entity(hass: HomeAssistant, domain: str, mac: str, group_entity: Any) -> None:
    """Register a group entity for a device."""
    if domain not in hass.data:
        return

    devices = hass.data[domain].get("_devices", {})
    normalized_mac = normalize_mac(mac)

    if normalized_mac in devices:
        devices[normalized_mac]["group_entity"] = group_entity
        _LOGGER.debug("[WiiM] Registered group entity for device MAC=%s", normalized_mac)


def unregister_group_entity(hass: HomeAssistant, domain: str, mac: str) -> None:
    """Unregister a group entity for a device."""
    if domain not in hass.data:
        return

    devices = hass.data[domain].get("_devices", {})
    normalized_mac = normalize_mac(mac)

    if normalized_mac in devices:
        devices[normalized_mac].pop("group_entity", None)
        _LOGGER.debug("[WiiM] Unregistered group entity for device MAC=%s", normalized_mac)


def get_debug_info(hass: HomeAssistant, domain: str) -> dict[str, Any]:
    """Get debug information about the device registry."""
    if domain not in hass.data:
        return {}

    data = hass.data[domain]

    return {
        "coordinator_count": len(data.get("_coordinators", {})),
        "device_count": len(data.get("_devices", {})),
        "ip_mappings": len(data.get("_ip_to_mac", {})),
        "group_entities": len(data.get("_group_entities", {})),
        "legacy_entries": len([k for k in data.keys() if not k.startswith("_")]),
        "coordinators_by_mac": {
            mac: {
                "ip": coord.client.host if hasattr(coord, "client") else "unknown",
                "has_data": coord.data is not None if hasattr(coord, "data") else False,
                "role": coord.data.get("role", "unknown") if hasattr(coord, "data") and coord.data else "unknown",
            }
            for mac, coord in data.get("_coordinators", {}).items()
        },
        "ip_to_mac_mappings": data.get("_ip_to_mac", {}),
    }
