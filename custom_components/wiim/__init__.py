"""WiiM Media Player integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

# Import config_flow to make it available as a module attribute for tests
from . import config_flow  # noqa: F401
from .api import WiiMClient
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN
from .coordinator import WiiMCoordinator
from .device_registry import get_device_registry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WiiM from a config entry."""
    client = WiiMClient(
        host=entry.data["host"],
        port=entry.data.get("port", 80),
        timeout=entry.data.get("timeout", 10),
        max_volume=entry.data.get("max_volume", 100),
        https=entry.data.get("https", False),
    )

    coordinator = WiiMCoordinator(
        hass,
        client,
        poll_interval=entry.data.get("poll_interval", 10),
    )

    # Register device in the device registry
    device_registry = get_device_registry(hass)
    device_registry.register_device(coordinator)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Failed to fetch initial data from %s: %s", entry.data["host"], err)
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Unregister device from the device registry
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, {})
        if coordinator := entry_data.get("coordinator"):
            device_registry = get_device_registry(hass)
            device_registry.unregister_device(coordinator.client.host)
    return unload_ok
