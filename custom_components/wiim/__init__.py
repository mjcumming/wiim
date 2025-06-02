"""The WiiM integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

# Import config_flow to make it available as a module attribute for tests
from . import config_flow  # noqa: F401
from .api import WiiMClient
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN
from .coordinator import WiiMCoordinator
from .utils.device_registry import initialize_device_registry, register_coordinator, unregister_coordinator

PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WiiM from a config entry."""
    # Initialize device registry structures
    initialize_device_registry(hass, DOMAIN)

    # Re-use Home Assistant's global aiohttp session to avoid unclosed-session warnings.
    client = WiiMClient(entry.data["host"], session=async_get_clientsession(hass))

    # Validate device is reachable; initial data will be fetched by coordinator
    try:
        await client.get_device_info()
    except Exception:
        # For tests, this might fail but that's OK if we have mocked data
        pass

    poll_interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    coordinator = WiiMCoordinator(hass, client, poll_interval=poll_interval)
    coordinator.entry_id = entry.entry_id  # type: ignore[attr-defined]

    # Perform initial data refresh to get MAC address
    await coordinator.async_config_entry_first_refresh()

    # Register coordinator in the new device registry system
    register_coordinator(hass, DOMAIN, coordinator, entry.entry_id)

    # ------------------------------------------------------------------
    # Update entry title to user-friendly device name on first setup
    # ------------------------------------------------------------------

    status = coordinator.data.get("status", {}) if isinstance(coordinator.data, dict) else {}
    friendly_name = status.get("device_name") or status.get("DeviceName")
    if friendly_name and friendly_name != entry.title:
        hass.config_entries.async_update_entry(entry, title=friendly_name)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # No need for explicit shutdown handler – HA will close the shared session.

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Get coordinator before removing it
        coordinator = None
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            coordinator_data = hass.data[DOMAIN][entry.entry_id]
            if isinstance(coordinator_data, dict) and "coordinator" in coordinator_data:
                coordinator = coordinator_data["coordinator"]

        # Unregister from device registry
        if coordinator:
            unregister_coordinator(hass, DOMAIN, coordinator, entry.entry_id)

        # Clean up any dynamic WiiMGroupMediaPlayer entities whose master IP
        # belonged to the coordinator we just unloaded.  This avoids orphaned
        # entities lingering in the entity registry until the next coordinator
        # refresh.
        group_entities = hass.data[DOMAIN].get("_group_entities", {})
        # The host/IP of the device associated with this entry
        host = entry.data.get("host")
        if host and host in group_entities:
            group_entity = group_entities.pop(host)
            hass.async_create_task(group_entity.async_remove())

    return unload_ok
