"""Provide info to system health."""

from __future__ import annotations

from importlib import metadata
from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .data import get_all_coordinators


@callback
def async_register(hass: HomeAssistant, register: system_health.SystemHealthRegistration) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return info for system health."""
    entries = hass.config_entries.async_entries(DOMAIN)
    coordinators = get_all_coordinators(hass)

    # Count reachable devices
    reachable_count = sum(1 for coord in coordinators if coord.last_update_success)

    # Count multiroom groups using player properties
    masters = []
    slaves = []
    for coord in coordinators:
        if coord.data:
            player = coord.data.get("player")
            if player:
                if player.is_master:
                    masters.append(coord)
                elif player.is_slave:
                    slaves.append(coord)

    # Check first device API health (async)
    first_device_health = None
    if coordinators:
        first_coordinator = coordinators[0]
        first_device_health = await _check_device_health(first_coordinator)

    # Get pywiim version
    pywiim_version = "unknown"
    try:
        pywiim_version = metadata.version("pywiim")
    except metadata.PackageNotFoundError:
        pass

    return {
        "configured_devices": len(entries),
        "reachable_devices": f"{reachable_count}/{len(coordinators)}",
        "multiroom_masters": len(masters),
        "multiroom_slaves": len(slaves),
        "first_device_api": first_device_health,  # This will be async
        "integration_version": "2.0.0",  # Your current version
        "pywiim_version": pywiim_version,
    }


async def _check_device_health(coordinator) -> str:
    """Check health of a specific device."""
    try:
        # Quick API test
        await coordinator.player.get_device_info()
        polling_interval = coordinator.update_interval.total_seconds()
        return f"OK (polling: {polling_interval}s)"
    except Exception as err:
        return f"Error: {str(err)[:50]}"
