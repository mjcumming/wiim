"""WiiM Media Player integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

# Import config_flow to make it available as a module attribute for tests
from . import config_flow  # noqa: F401
from .api import WiiMClient, WiiMConnectionError, WiiMError, WiiMTimeoutError
from .const import (
    CONF_ENABLE_MAINTENANCE_BUTTONS,
    CONF_ENABLE_NETWORK_MONITORING,
    DOMAIN,
    FIXED_POLL_INTERVAL,
)
from .coordinator import WiiMCoordinator
from .data import WiimData, get_or_create_speaker

_LOGGER = logging.getLogger(__name__)

# Core platforms that are always enabled
CORE_PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,  # Always enabled - core functionality
    Platform.SENSOR,  # Always enabled - role sensor is essential for multiroom
    Platform.NUMBER,  # Always enabled - group volume control for multiroom
    Platform.SWITCH,  # Always enabled - group mute control for multiroom
]

# Essential optional platforms based on user configuration
OPTIONAL_PLATFORMS: dict[str, Platform] = {
    CONF_ENABLE_MAINTENANCE_BUTTONS: Platform.BUTTON,
    CONF_ENABLE_NETWORK_MONITORING: Platform.BINARY_SENSOR,
    # Note: EQ controls are now handled within the switch platform conditionally
}


def get_enabled_platforms(entry: ConfigEntry) -> list[Platform]:
    """Get list of platforms that should be enabled based on user options."""
    platforms = CORE_PLATFORMS.copy()

    # Add optional platforms based on user preferences
    for config_key, platform in OPTIONAL_PLATFORMS.items():
        # Maintenance buttons default to True, others default to False
        default_enabled = config_key == CONF_ENABLE_MAINTENANCE_BUTTONS
        if entry.options.get(config_key, default_enabled):
            platforms.append(platform)
            _LOGGER.debug("Enabling platform %s based on option %s", platform, config_key)

    _LOGGER.info(
        "Enabled platforms for %s: %s",
        entry.title or entry.data.get("host", entry.entry_id),
        [p.value for p in platforms],
    )
    return platforms


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WiiM from a config entry."""

    # Create central data registry ONLY if it doesn't exist
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # CRITICAL FIX: Only create WiimData if it doesn't exist
    # This prevents wiping out existing speaker registrations during auto-discovery
    if "data" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["data"] = WiimData(hass)
        _LOGGER.debug("Created new WiimData registry")
    else:
        _LOGGER.debug("Reusing existing WiimData registry with %d speakers", len(hass.data[DOMAIN]["data"].speakers))

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
    )

    _LOGGER.info(
        "WiiM coordinator created for %s with fixed %ds polling interval",
        entry.data["host"],
        FIXED_POLL_INTERVAL,
    )

    # Initial data fetch with proper error handling
    try:
        _LOGGER.info("Starting initial data fetch for %s", entry.data["host"])
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Initial data fetch completed for %s", entry.data["host"])

    except WiiMTimeoutError as err:
        _LOGGER.warning("Timeout fetching initial data from %s, will retry: %s", entry.data["host"], err)
        raise ConfigEntryNotReady(f"Timeout connecting to WiiM device at {entry.data['host']}") from err
    except WiiMConnectionError as err:
        _LOGGER.warning("Connection error fetching initial data from %s, will retry: %s", entry.data["host"], err)
        raise ConfigEntryNotReady(f"Connection error with WiiM device at {entry.data['host']}") from err
    except WiiMError as err:
        _LOGGER.error("API error fetching initial data from %s: %s", entry.data["host"], err)
        raise ConfigEntryNotReady(f"API error with WiiM device at {entry.data['host']}") from err
    except Exception as err:
        _LOGGER.error("Unexpected error fetching initial data from %s: %s", entry.data["host"], err, exc_info=True)
        raise  # Re-raise unexpected errors

    # Use entry.unique_id as the stable device identifier
    # This should be set correctly in config_flow.py from device UUID or MAC
    device_uuid = entry.unique_id
    if not device_uuid:
        _LOGGER.error("No unique_id found in config entry for %s - this should not happen", entry.data["host"])
        # Fallback logic for device_uuid only for logging - not for HA device registry
        status_dict = coordinator.data.get("status", {}) if coordinator.data else {}
        if uuid_from_device := status_dict.get("uuid"):
            device_uuid = uuid_from_device
        elif mac := status_dict.get("MAC"):
            clean_mac = mac.lower().replace(":", "")
            device_uuid = clean_mac
        else:
            # Last resort for logging only - never use for HA registry
            device_uuid = entry.data["host"].replace(".", "_")
            _LOGGER.warning("Using IP-based UUID for logging only: %s", device_uuid)

    speaker = get_or_create_speaker(hass, coordinator, entry)
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
