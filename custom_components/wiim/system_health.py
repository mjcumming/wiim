"""Provide info to system health."""

from __future__ import annotations

from importlib import metadata
from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .data import get_all_speakers


@callback
def async_register(hass: HomeAssistant, register: system_health.SystemHealthRegistration) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return info for system health."""
    entries = hass.config_entries.async_entries(DOMAIN)
    speakers = get_all_speakers(hass)

    # Count reachable devices
    reachable_count = sum(1 for speaker in speakers if speaker.available)

    # Count multiroom groups
    masters = [s for s in speakers if s.role == "master"]
    slaves = [s for s in speakers if s.role == "slave"]

    # Check first device API health (async)
    first_device_health = None
    if speakers:
        first_speaker = speakers[0]
        first_device_health = await _check_device_health(first_speaker)

    # Get pywiim version
    pywiim_version = "unknown"
    try:
        pywiim_version = metadata.version("pywiim")
    except metadata.PackageNotFoundError:
        pass

    return {
        "configured_devices": len(entries),
        "reachable_devices": f"{reachable_count}/{len(speakers)}",
        "multiroom_masters": len(masters),
        "multiroom_slaves": len(slaves),
        "first_device_api": first_device_health,  # This will be async
        "integration_version": "2.0.0",  # Your current version
        "pywiim_version": pywiim_version,
    }


async def _check_device_health(speaker) -> str:
    """Check health of a specific device."""
    try:
        # Quick API test
        await speaker.coordinator.player.get_device_info()
        polling_interval = speaker.coordinator.update_interval.total_seconds()
        return f"OK (polling: {polling_interval}s)"
    except Exception as err:
        return f"Error: {str(err)[:50]}"
