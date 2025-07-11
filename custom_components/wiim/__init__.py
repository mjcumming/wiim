"""WiiM Media Player integration for Home Assistant."""

# ---------------------------------------------------------------------------
# Test Environment Compatibility Shim
# ---------------------------------------------------------------------------
# When running unit tests outside of Home Assistant, the real "homeassistant"
# package is typically not installed.  Attempting to import it will therefore
# raise a ``ModuleNotFoundError`` long before pytest fixtures have a chance to
# insert the stub package.  To make the component self-contained for testing we
# fall back to the lightweight stubs located under the top-level *stubs/*
# directory whenever the import fails.  This keeps the production codepath
# untouched while allowing `pytest` to execute in a vanilla virtualenv.
#
# ``stubs/homeassistant/__init__.py`` intentionally registers **itself** and
# all of the sub-modules the integration relies on into ``sys.modules``.  Once
# that module has been imported exactly once, subsequent ``import homeassistant``
# statements throughout the codebase succeed transparently.
# ---------------------------------------------------------------------------

from __future__ import annotations

import sys
from pathlib import Path

try:
    import homeassistant  # noqa: F401 – try real package first
except ModuleNotFoundError:  # pragma: no cover – only executed in test env
    # Add <repo-root>/stubs to ``sys.path`` and retry the import.  We cannot
    # rely on relative imports here because the integration may live two or
    # more levels deep inside *custom_components/*.
    repo_root = Path(__file__).resolve().parents[2]
    stubs_path = repo_root / "stubs"
    sys.path.append(str(stubs_path))

    # Import the stub package which will register itself in ``sys.modules``.
    import importlib

    importlib.import_module("homeassistant")

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
)
from .coordinator import WiiMCoordinator
from .data import Speaker

_LOGGER = logging.getLogger(__name__)

# Core platforms that are always enabled
CORE_PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,  # Always enabled - core functionality
    Platform.SENSOR,  # Always enabled - role sensor is essential for multiroom
    Platform.NUMBER,  # Always enabled - group volume control for multiroom
    Platform.SWITCH,  # Always enabled - group mute control for multiroom
    Platform.UPDATE,  # Always enabled - firmware update indicator
    Platform.LIGHT,  # Always enabled - front-panel LED control
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
        # All optional platforms default to disabled unless the user opts in
        default_enabled = False
        if entry.options.get(config_key, default_enabled):
            platforms.append(platform)
            _LOGGER.debug("Enabling platform %s based on option %s", platform, config_key)

    _LOGGER.info(
        "Enabled platforms for %s: %s",
        entry.title or entry.data.get("host", entry.entry_id),
        [p.value for p in platforms],
    )
    return platforms


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options updates by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WiiM from a config entry."""

    # Simplified v2.0.0 architecture: no custom registry, just use HA config entries
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

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

    # ------------------------------------------------------------------
    # Early Speaker creation & registry setup (before first refresh)
    # ------------------------------------------------------------------
    # We need the Speaker object to exist BEFORE the first coordinator
    # refresh because the coordinator callbacks reference it via
    # get_speaker_from_config_entry(). Creating and storing it early
    # prevents transient "Speaker not found" errors at startup.
    # NOTE: async_setup() is *deferred* until after the first refresh so
    # that _populate_device_info() can rely on fresh coordinator data.
    speaker = Speaker(hass, coordinator, entry)

    # Store minimal references immediately so helper look-ups succeed
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "speaker": speaker,
        "entry": entry,  # platform access to options
    }

    # Listen for config entry updates (e.g. options flow) so we can reload
    entry.async_on_unload(entry.add_update_listener(_update_listener))

    _LOGGER.info(
        "WiiM coordinator created for %s with adaptive polling (1s when playing, 5s when idle)",
        entry.data["host"],
    )

    # Initial data fetch with proper error handling
    try:
        _LOGGER.info("Starting initial data fetch for %s", entry.data["host"])
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Initial data fetch completed for %s", entry.data["host"])

        # Complete speaker setup now that we have fresh coordinator data
        await speaker.async_setup(entry)

    except (WiiMTimeoutError, WiiMConnectionError, WiiMError) as err:
        # Cleanup partial registration before signaling retry
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if isinstance(err, WiiMTimeoutError):
            _LOGGER.warning("Timeout fetching initial data from %s, will retry: %s", entry.data["host"], err)
            raise ConfigEntryNotReady(f"Timeout connecting to WiiM device at {entry.data['host']}") from err
        if isinstance(err, WiiMConnectionError):
            _LOGGER.warning("Connection error fetching initial data from %s, will retry: %s", entry.data["host"], err)
            raise ConfigEntryNotReady(f"Connection error with WiiM device at {entry.data['host']}") from err
        _LOGGER.error("API error fetching initial data from %s: %s", entry.data["host"], err)
        raise ConfigEntryNotReady(f"API error with WiiM device at {entry.data['host']}") from err
    except Exception as err:
        # Cleanup on unexpected error and re-raise
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.error("Unexpected error fetching initial data from %s: %s", entry.data["host"], err, exc_info=True)
        raise

    # Get enabled platforms based on user options
    enabled_platforms = get_enabled_platforms(entry)

    # Set up only enabled platforms
    await hass.config_entries.async_forward_entry_setups(entry, enabled_platforms)

    _LOGGER.info(
        "WiiM integration setup complete for %s (UUID: %s) with %d platforms",
        speaker.name,
        entry.unique_id or "unknown",
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


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
