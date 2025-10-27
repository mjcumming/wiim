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
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service import async_register_admin_service

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
    Platform.SELECT,  # Always enabled - audio output mode control
]

# Essential optional platforms based on user configuration
OPTIONAL_PLATFORMS: dict[str, Platform] = {
    CONF_ENABLE_MAINTENANCE_BUTTONS: Platform.BUTTON,
    CONF_ENABLE_NETWORK_MONITORING: Platform.BINARY_SENSOR,
    # Note: EQ controls are now handled within the switch platform conditionally
}


def get_enabled_platforms(
    hass: HomeAssistant, entry: ConfigEntry, capabilities: dict[str, Any] | None = None
) -> list[Platform]:
    """Get list of platforms that should be enabled based on user options and device capabilities.

    Args:
        hass: Home Assistant instance
        entry: Config entry
        capabilities: Device capabilities dict (if not provided, will try to get from coordinator)
    """
    platforms = CORE_PLATFORMS.copy()

    # Remove SELECT platform from core list (we'll add it conditionally based on capabilities)
    if Platform.SELECT in platforms:
        platforms.remove(Platform.SELECT)

    # Conditionally add SELECT platform based on device audio output capabilities
    if capabilities is None:
        # Try to get capabilities from coordinator (fallback for reload/update scenarios)
        if entry.entry_id in hass.data.get(DOMAIN, {}):
            coordinator_data = hass.data[DOMAIN][entry.entry_id]
            if "coordinator" in coordinator_data:
                coordinator = coordinator_data["coordinator"]
                # Capabilities are stored in coordinator but not in client
                capabilities = getattr(coordinator, "_capabilities", {})

                # Fallback: check client capabilities for backward compatibility
                if not capabilities and hasattr(coordinator, "client") and hasattr(coordinator.client, "capabilities"):
                    capabilities = coordinator.client.capabilities

    if capabilities:
        supports_audio_output = capabilities.get("supports_audio_output", True)  # Keep original default
        _LOGGER.debug(
            "Audio output capability check for %s: supports_audio_output=%s",
            entry.data.get("host"),
            supports_audio_output,
        )
        if supports_audio_output:
            platforms.append(Platform.SELECT)
            _LOGGER.info("Enabling SELECT platform - device supports audio output control")
        else:
            _LOGGER.info("Skipping SELECT platform - device does not support audio output control")
    else:
        _LOGGER.warning("Capabilities not available for %s - skipping SELECT platform", entry.data.get("host"))

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


async def _reboot_device_service(hass: HomeAssistant, call):
    """Handle reboot_device service call."""
    entity_id = call.data.get("entity_id")
    if not entity_id:
        _LOGGER.error("entity_id is required for reboot_device service")
        return

    # Find the entity and call its reboot method
    entity = hass.states.get(entity_id)
    if not entity:
        _LOGGER.error("Entity %s not found", entity_id)
        return

    if entity.domain != "media_player":
        _LOGGER.error("Entity %s is not a media_player", entity_id)
        return

    # Get the speaker from the entity's device
    device_registry = hass.helpers.device_registry.async_get(hass)
    entity_registry = hass.helpers.entity_registry.async_get(hass)

    entity_entry = entity_registry.async_get(entity_id)
    if not entity_entry or not entity_entry.device_id:
        _LOGGER.error("Entity %s has no device", entity_id)
        return

    device_entry = device_registry.async_get(entity_entry.device_id)
    if not device_entry:
        _LOGGER.error("Device for entity %s not found", entity_id)
        return

    # Find the config entry for this device
    for config_entry_id in device_entry.config_entries:
        if config_entry_id in hass.data.get(DOMAIN, {}):
            entry_data = hass.data[DOMAIN][config_entry_id]
            speaker = entry_data.get("speaker")
            if speaker:
                try:
                    await speaker.coordinator.client.reboot()
                    _LOGGER.info("Reboot command sent successfully to %s", speaker.name)
                except Exception as err:
                    _LOGGER.info(
                        "Reboot command sent to %s (device may not respond): %s",
                        speaker.name,
                        err,
                    )
                return

    _LOGGER.error("No WiiM device found for entity %s", entity_id)


async def _sync_time_service(hass: HomeAssistant, call):
    """Handle sync_time service call."""
    entity_id = call.data.get("entity_id")
    if not entity_id:
        _LOGGER.error("entity_id is required for sync_time service")
        return

    # Find the entity and call its sync_time method
    entity = hass.states.get(entity_id)
    if not entity:
        _LOGGER.error("Entity %s not found", entity_id)
        return

    if entity.domain != "media_player":
        _LOGGER.error("Entity %s is not a media_player", entity_id)
        return

    # Get the speaker from the entity's device
    device_registry = hass.helpers.device_registry.async_get(hass)
    entity_registry = hass.helpers.entity_registry.async_get(hass)

    entity_entry = entity_registry.async_get(entity_id)
    if not entity_entry or not entity_entry.device_id:
        _LOGGER.error("Entity %s has no device", entity_id)
        return

    device_entry = device_registry.async_get(entity_entry.device_id)
    if not device_entry:
        _LOGGER.error("Device for entity %s not found", entity_id)
        return

    # Find the config entry for this device
    for config_entry_id in device_entry.config_entries:
        if config_entry_id in hass.data.get(DOMAIN, {}):
            entry_data = hass.data[DOMAIN][config_entry_id]
            speaker = entry_data.get("speaker")
            if speaker:
                try:
                    await speaker.coordinator.client.sync_time()
                    _LOGGER.info("Time sync command sent successfully to %s", speaker.name)
                except Exception as err:
                    _LOGGER.error("Failed to sync time for %s: %s", speaker.name, err)
                    raise
                return

    _LOGGER.error("No WiiM device found for entity %s", entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WiiM from a config entry."""

    # Register global services if this is the first entry
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

        # Register global services
        async_register_admin_service(
            hass,
            DOMAIN,
            "reboot_device",
            _reboot_device_service,
        )
        async_register_admin_service(
            hass,
            DOMAIN,
            "sync_time",
            _sync_time_service,
        )

    # Simplified v2.0.0 architecture: no custom registry, just use HA config entries
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Create client and coordinator with firmware capabilities
    session = async_get_clientsession(hass)

    # Detect device capabilities first
    from .firmware_capabilities import detect_device_capabilities

    # Create temporary client for capability detection
    # Use Audio Pro MkII-compatible settings speculatively to handle devices
    # that require client cert + port 4443 before we can detect capabilities
    temp_capabilities = {
        "protocol_priority": ["https", "http"],
        "preferred_ports": [4443, 8443, 443],  # Try Audio Pro MkII ports first
    }
    temp_client = WiiMClient(
        host=entry.data["host"],
        port=entry.data.get("port", 443),
        timeout=entry.data.get("timeout", 10),
        session=session,
        capabilities=temp_capabilities,
    )

    # Detect capabilities
    try:
        device_info = await temp_client.get_device_info_model()
        capabilities = detect_device_capabilities(device_info)
        _LOGGER.info(
            "Detected device capabilities for %s: %s",
            entry.data["host"],
            capabilities.get("device_type", "Unknown"),
        )
        # Log audio output capability specifically for debugging
        if capabilities.get("supports_audio_output"):
            _LOGGER.info("[AUDIO OUTPUT] Device %s supports audio output control", entry.data["host"])
        else:
            _LOGGER.info(
                "[AUDIO OUTPUT] Device %s does not support audio output control (is_wiim=%s, is_legacy=%s)",
                entry.data["host"],
                capabilities.get("is_wiim_device", False),
                capabilities.get("is_legacy_device", False),
            )
    except Exception as err:
        # Smart logging escalation for capability detection failures too
        retry_count = getattr(entry, "_capability_detection_retry_count", 0)
        retry_count += 1
        entry._capability_detection_retry_count = retry_count

        # Escalate logging based on retry count
        if retry_count <= 2:
            log_fn = _LOGGER.warning
        elif retry_count <= 4:
            log_fn = _LOGGER.debug
        else:
            log_fn = _LOGGER.error

        log_fn("Failed to detect device capabilities for %s (attempt %d): %s", entry.data["host"], retry_count, err)
        capabilities = {}

    # Create client with capabilities
    client = WiiMClient(
        host=entry.data["host"],
        port=entry.data.get("port", 443),
        timeout=entry.data.get("timeout", 10),
        session=session,
        capabilities=capabilities,
    )

    coordinator = WiiMCoordinator(
        hass,
        client,
        entry=entry,
        capabilities=capabilities,
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

        # Reset retry count on successful setup
        if hasattr(entry, "_setup_retry_count") and entry._setup_retry_count > 0:
            _LOGGER.info("Setup succeeded for %s after %d retries", entry.data["host"], entry._setup_retry_count)
            entry._setup_retry_count = 0

    except (WiiMTimeoutError, WiiMConnectionError, WiiMError) as err:
        # Cleanup partial registration before signaling retry
        hass.data[DOMAIN].pop(entry.entry_id, None)

        # Smart logging escalation to reduce noise for persistent failures
        # Track retry count across attempts (stored in config entry runtime data)
        retry_count = getattr(entry, "_setup_retry_count", 0)
        retry_count += 1
        entry._setup_retry_count = retry_count

        # Escalate logging based on retry count to reduce noise
        if retry_count <= 2:
            log_fn = _LOGGER.warning  # First couple attempts - normal to see
        elif retry_count <= 4:
            log_fn = _LOGGER.debug  # Middle attempts - reduce noise
        else:
            log_fn = _LOGGER.error  # Many attempts - device likely offline

        if isinstance(err, WiiMTimeoutError):
            log_fn(
                "Timeout fetching initial data from %s (attempt %d), will retry: %s",
                entry.data["host"],
                retry_count,
                err,
            )
            raise ConfigEntryNotReady(f"Timeout connecting to WiiM device at {entry.data['host']}") from err
        if isinstance(err, WiiMConnectionError):
            log_fn(
                "Connection error fetching initial data from %s (attempt %d), will retry: %s",
                entry.data["host"],
                retry_count,
                err,
            )
            raise ConfigEntryNotReady(f"Connection error with WiiM device at {entry.data['host']}") from err
        _LOGGER.error("API error fetching initial data from %s: %s", entry.data["host"], err)
        raise ConfigEntryNotReady(f"API error with WiiM device at {entry.data['host']}") from err
    except Exception as err:
        # Cleanup on unexpected error and re-raise
        hass.data[DOMAIN].pop(entry.entry_id, None)

        # Check if this is a wrapped WiiM exception (e.g., UpdateFailed from coordinator)
        underlying_err = err.__cause__ if hasattr(err, "__cause__") and err.__cause__ else None
        is_wiim_error = isinstance(err, (WiiMTimeoutError, WiiMConnectionError, WiiMError)) or isinstance(
            underlying_err, (WiiMTimeoutError, WiiMConnectionError, WiiMError)
        )

        # Smart logging escalation for unexpected errors too
        retry_count = getattr(entry, "_setup_retry_count", 0)
        retry_count += 1
        entry._setup_retry_count = retry_count

        # Escalate logging based on retry count
        if retry_count <= 2:
            log_fn = _LOGGER.warning
        elif retry_count <= 4:
            log_fn = _LOGGER.debug
        else:
            log_fn = _LOGGER.error

        # Use appropriate message based on error type
        if is_wiim_error:
            err_to_log = underlying_err if underlying_err else err
            if isinstance(err_to_log, WiiMConnectionError):
                log_fn(
                    "Connection error fetching initial data from %s (attempt %d), will retry: %s",
                    entry.data["host"],
                    retry_count,
                    err,
                )
                raise ConfigEntryNotReady(f"Connection error with WiiM device at {entry.data['host']}") from err
            elif isinstance(err_to_log, WiiMTimeoutError):
                log_fn(
                    "Timeout fetching initial data from %s (attempt %d), will retry: %s",
                    entry.data["host"],
                    retry_count,
                    err,
                )
                raise ConfigEntryNotReady(f"Timeout connecting to WiiM device at {entry.data['host']}") from err

        log_fn(
            "Unexpected error fetching initial data from %s (attempt %d): %s",
            entry.data["host"],
            retry_count,
            err,
            exc_info=True,
        )
        raise

    # Get enabled platforms based on user options and device capabilities
    enabled_platforms = get_enabled_platforms(hass, entry, capabilities)

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
    enabled_platforms = get_enabled_platforms(hass, entry)

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
