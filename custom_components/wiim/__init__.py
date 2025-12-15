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
from urllib.parse import urlparse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from pywiim import WiiMClient
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

# Import config_flow to make it available as a module attribute for tests
from . import config_flow  # noqa: F401
from .const import (
    CONF_ENABLE_MAINTENANCE_BUTTONS,
    DOMAIN,
)
from .coordinator import WiiMCoordinator

_LOGGER = logging.getLogger(__name__)

# Core platforms that are always enabled
CORE_PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,  # Always enabled - core functionality
    Platform.SENSOR,  # Always enabled - role sensor is essential for multiroom
    Platform.NUMBER,  # Always enabled - group volume control for multiroom
    Platform.LIGHT,  # Always enabled - front-panel LED control
    Platform.SELECT,  # Always enabled - audio output mode control and Bluetooth device selection
    Platform.BUTTON,  # Always enabled - Bluetooth scan button (maintenance buttons are optional)
]

# Essential optional platforms based on user configuration
OPTIONAL_PLATFORMS: dict[str, Platform] = {
    CONF_ENABLE_MAINTENANCE_BUTTONS: Platform.BUTTON,  # Note: BUTTON is in CORE but maintenance buttons are optional
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

    # Firmware update install support (pywiim capability detection):
    # Per upstream pywiim API, only WiiM devices support firmware installation via API.
    # Use pywiim's capability flag as the source of truth.
    caps = capabilities or entry.data.get("capabilities") or {}

    supports_firmware_install = caps.get("supports_firmware_install")
    if supports_firmware_install is None:
        # Prefer pywiim's runtime flag if a coordinator/player is available.
        # This avoids relying on stale/incomplete cached capability dicts.
        try:
            coordinator: WiiMCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
            supports_firmware_install = getattr(coordinator.player, "supports_firmware_install", False)
        except Exception:  # noqa: BLE001
            supports_firmware_install = False

    if bool(supports_firmware_install):
        platforms.append(Platform.UPDATE)

    # Add optional platforms based on user preferences
    # Note: BUTTON is in CORE_PLATFORMS (for Bluetooth scan), but maintenance buttons are optional
    for config_key, platform in OPTIONAL_PLATFORMS.items():
        # Skip if platform is already in core platforms
        if platform in platforms:
            _LOGGER.debug("Platform %s already enabled in core, skipping optional check", platform)
            continue
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


async def _register_ha_device(hass: HomeAssistant, coordinator: WiiMCoordinator, entry: ConfigEntry) -> None:
    """Register device in HA registry.

    Device Info display:
    - Hardware: Device firmware version (e.g., "Linkplay 4.8.731953")
    - Software: PyWiiM library version (e.g., "pywiim 2.0.17")
    - Serial Number: Device IP address
    - Connections: Device MAC address
    """
    dev_reg = dr.async_get(hass)
    uuid = entry.unique_id or coordinator.player.host
    identifiers = {(DOMAIN, uuid)}

    # Get pywiim library version
    try:
        import pywiim

        pywiim_version = f"pywiim {getattr(pywiim, '__version__', 'unknown')}"
    except (ImportError, AttributeError):
        pywiim_version = "pywiim unknown"

    # Get device info from player
    player = coordinator.player
    device_name = player.name or entry.title or "WiiM Speaker"
    device_model = player.model or "WiiM Speaker"
    firmware = player.firmware

    # Get MAC address from device_info if available
    mac_address = None
    if player.device_info and hasattr(player.device_info, "mac"):
        mac_address = player.device_info.mac

    # Build connections set with MAC address if available
    connections: set[tuple[str, str]] = set()
    if mac_address:
        connections.add((CONNECTION_NETWORK_MAC, mac_address))

    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=identifiers,
        manufacturer="WiiM",
        name=device_name,
        model=device_model,
        hw_version=firmware,  # Device firmware (LinkPlay)
        sw_version=pywiim_version,  # Integration library version
        serial_number=player.host,  # IP address as serial number
        connections=connections if connections else None,  # MAC address as connection
    )


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the WiiM integration domain."""
    _LOGGER.info("WiiM integration async_setup called")
    # Initialize domain data structure
    hass.data.setdefault(DOMAIN, {})

    # Services are now registered via EntityServiceDescription pattern in media_player.py
    # No need to register here - services are registered when entities are added

    _LOGGER.info("WiiM integration async_setup completed")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WiiM from a config entry."""
    _LOGGER.info("WiiM async_setup_entry called for entry: %s (host: %s)", entry.entry_id, entry.data.get("host"))

    # Initialize domain data structure
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Services are registered via EntityServiceDescription pattern in media_player.py
    # when entities are added to the platform

    # Create client and coordinator with firmware capabilities
    session = async_get_clientsession(hass)

    # Check if we have a cached endpoint from previous discovery (optimized pattern)
    cached_endpoint = entry.data.get("endpoint")
    port = None
    protocol = None
    if cached_endpoint:
        # Parse cached endpoint and extract port/protocol
        parsed = urlparse(cached_endpoint)
        port = parsed.port
        protocol = parsed.scheme
        _LOGGER.debug(
            "Using cached endpoint for %s: %s (protocol=%s, port=%s)",
            entry.data["host"],
            cached_endpoint,
            protocol,
            port,
        )

    # Create client - pywiim handles capability detection
    # Note: We pass Home Assistant's managed session to pywiim, but pywiim may create
    # additional internal sessions for temporary operations (e.g., getting master name)
    # that aren't properly closed. This results in "Unclosed client session" warnings
    # which are harmless but should be fixed in pywiim itself.
    #
    # OPTIMIZATION: Check for cached capabilities first to avoid slow re-probing
    # on every restart. Capabilities are cached after first successful detection.
    cached_capabilities = entry.data.get("capabilities")
    capabilities: dict[str, Any] = {}

    # Capabilities are cached for startup performance, but the cached payload may be
    # from an older pywiim version that did not include newer keys (e.g.
    # `supports_firmware_install`). If the cache looks incomplete, re-detect once.
    if cached_capabilities and "supports_firmware_install" in cached_capabilities:
        # Use cached capabilities - skip slow probing
        capabilities = cached_capabilities
        _LOGGER.debug(
            "Using cached capabilities for %s: %s",
            entry.data["host"],
            capabilities.get("device_type", "Unknown"),
        )
    else:
        # First setup, no cache, or stale cache - need to detect capabilities
        try:
            import time

            start_time = time.monotonic()

            # Use cached endpoint if available, otherwise let pywiim probe automatically
            temp_client_kwargs = {
                "host": entry.data["host"],
                "timeout": entry.data.get("timeout", 10),
                "session": session,
            }
            if port is not None and protocol is not None:
                temp_client_kwargs["port"] = port
                temp_client_kwargs["protocol"] = protocol
            temp_client = WiiMClient(**temp_client_kwargs)
            # Use pywiim's _detect_capabilities() method
            detected = await temp_client._detect_capabilities()

            # Merge any existing cached capabilities (if present) with the newly detected ones.
            # Prefer freshly detected values to avoid stale flags (like firmware install support).
            if cached_capabilities:
                capabilities = {**cached_capabilities, **(detected or {})}
            else:
                capabilities = detected or {}

            elapsed = time.monotonic() - start_time
            _LOGGER.info(
                "Detected device capabilities for %s in %.2fs: %s",
                entry.data["host"],
                elapsed,
                capabilities.get("device_type", "Unknown"),
            )

            # Cache capabilities for faster future startups
            if capabilities:
                _LOGGER.debug("Caching capabilities for %s", entry.data["host"])
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, "capabilities": capabilities},
                )

            # Log audio output capability specifically for debugging
            if capabilities.get("supports_audio_output"):
                _LOGGER.info(
                    "[AUDIO OUTPUT] Device %s supports audio output control",
                    entry.data["host"],
                )
            else:
                _LOGGER.info(
                    "[AUDIO OUTPUT] Device %s does not support audio output control",
                    entry.data["host"],
                )
            # Log EQ capability specifically for debugging
            if capabilities.get("supports_eq"):
                _LOGGER.info(
                    "[EQ] Device %s supports EQ (detected by pywiim capability detection)",
                    entry.data["host"],
                )
            else:
                _LOGGER.info(
                    "[EQ] Device %s - EQ support NOT detected by pywiim capability detection. Full capabilities: %s",
                    entry.data["host"],
                    capabilities,
                )
        except Exception as err:
            # Smart logging escalation for capability detection failures
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

            log_fn(
                "Failed to detect device capabilities for %s (attempt %d): %s",
                entry.data["host"],
                retry_count,
                err,
            )
            # Use empty capabilities - WiiMClient will handle it
            capabilities = {}

    # Coordinator creates client and player internally using HA's shared session
    # Pass port/protocol if we have a cached endpoint, otherwise let pywiim probe
    coordinator = WiiMCoordinator(
        hass,
        host=entry.data["host"],
        entry=entry,
        capabilities=capabilities,
        port=port,
        protocol=protocol,
        timeout=entry.data.get("timeout", 10),
    )

    # Store coordinator and entry directly in hass.data
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
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

        # Ensure cached capabilities include pywiim's firmware install support flag.
        # Our platform enablement uses `supports_firmware_install` to decide whether to
        # expose the `update` platform; older cached capability payloads may lack it.
        supports_firmware_install = bool(getattr(coordinator.player, "supports_firmware_install", False))
        if capabilities.get("supports_firmware_install") != supports_firmware_install:
            capabilities["supports_firmware_install"] = supports_firmware_install
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    "capabilities": {**(entry.data.get("capabilities") or {}), **capabilities},
                },
            )

        # After first successful connection, persist the discovered endpoint (optimized pattern)
        # This avoids probing on every startup for faster initialization
        if not cached_endpoint:
            discovered_endpoint = coordinator.player.client.discovered_endpoint
            if discovered_endpoint:
                _LOGGER.info(
                    "Caching discovered endpoint for %s: %s",
                    entry.data["host"],
                    discovered_endpoint,
                )
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, "endpoint": discovered_endpoint},
                )

        # Update config entry title if we now have the real device name
        # This fixes manual add showing "WiiM Device (IP)" instead of actual name
        player_name = coordinator.player.name
        if player_name and entry.title != player_name:
            # Only update if current title is a generic fallback name
            host = entry.data.get("host", "")
            is_generic_title = entry.title.startswith("WiiM Device") or entry.title == host
            if is_generic_title:
                _LOGGER.info(
                    "Updating config entry title from '%s' to '%s'",
                    entry.title,
                    player_name,
                )
                hass.config_entries.async_update_entry(entry, title=player_name)

        # Register device in HA registry now that we have fresh coordinator data
        _LOGGER.info("Registering device for %s", entry.data["host"])
        try:
            await _register_ha_device(hass, coordinator, entry)
            _LOGGER.info("Device registration completed for %s", entry.data["host"])
        except Exception as setup_err:  # noqa: BLE001
            _LOGGER.error(
                "Device registration failed for %s: %s",
                entry.data["host"],
                setup_err,
                exc_info=True,
            )
            # Re-raise to let outer handler deal with it
            raise

        # Reset retry count on successful setup
        if hasattr(entry, "_setup_retry_count") and entry._setup_retry_count > 0:
            _LOGGER.info(
                "Setup succeeded for %s after %d retries",
                entry.data["host"],
                entry._setup_retry_count,
            )
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
        # Pylint false-positive: `is_wiim_error` is computed above, not constant.
        if is_wiim_error:  # pylint: disable=using-constant-test
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

    device_name = coordinator.player.name or entry.title or "WiiM Speaker"
    _LOGGER.info(
        "WiiM integration setup complete for %s (UUID: %s) with %d platforms",
        device_name,
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
        coordinator = entry_data.get("coordinator")
        if coordinator:
            device_name = coordinator.player.name or entry.title or "WiiM Speaker"
            _LOGGER.info("Unloaded WiiM integration for %s", device_name)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
