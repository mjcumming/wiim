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
from .const import (
    CONF_ENABLE_DIAGNOSTIC_ENTITIES,
    CONF_ENABLE_MAINTENANCE_BUTTONS,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)
from .coordinator import WiiMCoordinator
from .data import WiimData, get_or_create_speaker

_LOGGER = logging.getLogger(__name__)

# Core platforms that are always enabled
CORE_PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,  # Always enabled - core functionality
    Platform.SENSOR,  # Always enabled - role sensor is essential for multiroom
]

# Essential optional platforms based on user configuration
OPTIONAL_PLATFORMS: dict[str, Platform] = {
    CONF_ENABLE_MAINTENANCE_BUTTONS: Platform.BUTTON,
}


def get_enabled_platforms(entry: ConfigEntry) -> list[Platform]:
    """Get list of platforms that should be enabled based on user options."""
    platforms = CORE_PLATFORMS.copy()

    # Add optional platforms based on user preferences
    for config_key, platform in OPTIONAL_PLATFORMS.items():
        if entry.options.get(
            config_key, config_key == CONF_ENABLE_MAINTENANCE_BUTTONS
        ):  # Maintenance buttons default to True
            platforms.append(platform)
            _LOGGER.debug("Enabling platform %s based on option %s", platform, config_key)

    _LOGGER.info("Enabled platforms for %s: %s", entry.data["host"], [p.value for p in platforms])
    return platforms


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WiiM from a config entry."""

    # Create central data registry
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["data"] = WiimData(hass)

    # Create client and coordinator
    session = async_get_clientsession(hass)
    client = WiiMClient(
        host=entry.data["host"],
        port=entry.data.get("port", 443),
        timeout=entry.data.get("timeout", 10),
        session=session,
    )

    coordinator = WiiMCoordinator(
        hass,
        client,
        entry=entry,
        poll_interval=entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
    )

    # Initial data fetch
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Failed to fetch initial data from %s: %s", entry.data["host"], err)
        raise  # Re-raise to trigger SETUP_RETRY instead of SETUP_ERROR

    # Create/update speaker with clean UUID
    status_dict = coordinator.data.get("status", {}) if coordinator.data else {}

    # Priority order for clean UUID generation:
    # 1. Device UUID (if available)
    # 2. MAC address (clean, no colons)
    # 3. IP address as last resort
    device_uuid = None
    if uuid_from_device := status_dict.get("uuid"):
        device_uuid = uuid_from_device
    elif mac := status_dict.get("MAC"):
        # Use MAC without colons as clean identifier
        clean_mac = mac.lower().replace(":", "")
        device_uuid = clean_mac
    else:
        # Fallback to IP-based UUID (clean format)
        ip_clean = entry.data["host"].replace(".", "_")
        device_uuid = ip_clean

    speaker = get_or_create_speaker(hass, device_uuid, coordinator)
    await speaker.async_setup(entry)

    # Store references for platforms
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "speaker": speaker,
        "entry": entry,  # Store entry for platform access to options
    }

    # Get enabled platforms based on user options
    enabled_platforms = get_enabled_platforms(entry)

    # Set up only enabled platforms
    await hass.config_entries.async_forward_entry_setups(entry, enabled_platforms)

    _LOGGER.info(
        "WiiM integration setup complete for %s (UUID: %s) with %d platforms",
        speaker.name,
        device_uuid,
        len(enabled_platforms),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Get the platforms that were actually set up
    enabled_platforms = get_enabled_platforms(entry)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, enabled_platforms):
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, {})
        speaker = entry_data.get("speaker")
        if speaker:
            _LOGGER.info("Unloaded WiiM integration for %s", speaker.name)
    return unload_ok
