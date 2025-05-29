"""Config flow to configure WiiM component.

This module implements a simplified discovery flow optimized for Home Assistant:
- Factory pattern for device validation with retry logic
- Prioritized discovery methods: UPnP > Zeroconf > Manual entry
- Automatic device ungrouping during setup for clean HA integration
- Simplified validation and error handling
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
import logging
import asyncio
from enum import Enum

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryNotReady

from .api import WiiMClient, WiiMError
from .const import (
    CONF_POLL_INTERVAL,
    CONF_VOLUME_STEP,
    CONF_STATUS_UPDATE_INTERVAL,
    CONF_VOLUME_STEP_PERCENT,
    CONF_ENABLE_GROUP_ENTITY,
    CONF_DEBUG_LOGGING,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)

# --- UPnP/SSDP discovery imports ---
try:
    from async_upnp_client.search import async_search
except ImportError:
    async_search = None

import zeroconf

_LOGGER = logging.getLogger(__name__)


class DiscoveryState(Enum):
    """Discovery state enumeration."""

    DISCOVERING = "discovering"
    VALIDATING = "validating"
    READY = "ready"
    FAILED = "failed"


async def wiim_factory_client(host: str, max_retries: int = 3) -> WiiMClient:
    """Factory to create and validate WiiM client with retry logic.

    Creates a client that will auto-detect the correct protocol (HTTPS/HTTP)
    and port on first connection attempt.
    """
    # Use default HTTPS port 443, client will auto-detect correct protocol
    client = WiiMClient(host, port=443)  # Start with HTTPS default
    retry_delay = 1  # seconds

    for attempt in range(max_retries):
        try:
            # Validate device responds and get basic info
            # This will trigger protocol auto-detection
            await client.get_player_status()
            _LOGGER.debug(
                "Successfully connected to WiiM device at %s using %s",
                host,
                client._endpoint,
            )
            # Don't close here - return the working client
            return client
        except WiiMError as err:
            if attempt == max_retries - 1:
                await client.close()
                # Provide more specific error message for SSL failures
                if "ssl" in str(err).lower() or "handshake" in str(err).lower():
                    raise ConfigEntryNotReady(
                        f"SSL/TLS connection failed to WiiM device at {host}. "
                        f"Device may not support HTTPS or uses incompatible SSL configuration."
                    ) from err
                else:
                    raise ConfigEntryNotReady(
                        f"Failed to connect to WiiM device at {host} after {max_retries} attempts"
                    ) from err
            _LOGGER.debug(
                "Attempt %d failed to validate WiiM device at %s: %s",
                attempt + 1,
                host,
                err,
            )
            await asyncio.sleep(retry_delay)
        except Exception as err:
            await client.close()
            raise ConfigEntryNotReady(
                f"Unexpected error connecting to WiiM device at {host}"
            ) from err

    # This should never be reached, but just in case
    await client.close()
    raise ConfigEntryNotReady(f"Failed to validate WiiM device at {host}")


async def _async_validate_host(host: str) -> None:
    """Validate we can talk to the WiiM device and always close the session."""
    client = await wiim_factory_client(host)
    try:
        # Client is already validated by wiim_factory_client
        pass
    finally:
        await client.close()


class WiiMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a WiiM config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up instance."""
        self._host: str | None = None
        self._discovered_hosts: dict[str, str] = {}
        self._options_map: dict[str, str] = {}  # Initialize to prevent linter error

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "WiiMOptionsFlow":
        """Return the options flow."""
        return WiiMOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - prioritize discovery methods."""
        errors: dict[str, str] = {}

        # If user provided manual input, validate it
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                client = await wiim_factory_client(host)
                try:
                    info = await client.get_player_status()
                    info = await self._ensure_solo(client, info)

                    # Use host/IP as unique_id to guarantee one entry per device
                    unique_id = host
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    device_name = (
                        info.get("device_name") or info.get("DeviceName") or host
                    )
                finally:
                    await client.close()

                return self.async_create_entry(
                    title=device_name, data={CONF_HOST: host}
                )
            except ConfigEntryNotReady:
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.error("[WiiM] Error during manual config: %s", e)
                errors["base"] = "unknown"

        # Try discovery methods in priority order: Zeroconf > UPnP > Manual
        if async_search is not None and not user_input:
            # UPnP discovery available, try it first
            return await self.async_step_upnp()

        # Fall back to manual entry
        schema = vol.Schema({vol.Required(CONF_HOST): str})
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_upnp(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Discover WiiM/LinkPlay devices via UPnP/SSDP."""
        errors: dict[str, str] = {}

        if not self._discovered_hosts:
            # Perform UPnP discovery
            self._discovered_hosts = await self._discover_upnp_hosts()

        if user_input is not None:
            selected = user_input[CONF_HOST]
            host = self._options_map.get(selected, selected)

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            try:
                client = await wiim_factory_client(host)
                try:
                    info = await client.get_player_status()
                    info = await self._ensure_solo(client, info)
                    device_name = (
                        info.get("device_name") or info.get("DeviceName") or host
                    )
                finally:
                    await client.close()

                return self.async_create_entry(
                    title=device_name,
                    data={CONF_HOST: host},
                )
            except ConfigEntryNotReady:
                errors["base"] = "cannot_connect"

        if self._discovered_hosts:
            # Build options for dropdown
            options_map = {
                f"{name} ({host})": host
                for host, name in self._discovered_hosts.items()
            }
            self._options_map = options_map
            schema = vol.Schema(
                {vol.Required(CONF_HOST): vol.In(list(options_map.keys()))}
            )
            return self.async_show_form(
                step_id="upnp",
                data_schema=schema,
                errors=errors,
            )

        # No devices found, fall back to manual
        schema = vol.Schema({vol.Required(CONF_HOST): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def _discover_upnp_hosts(self) -> dict[str, str]:
        """Discover devices and return mapping of host→friendly name."""
        if async_search is None:
            return {}

        discovered: dict[str, str] = {}
        known_ids = {entry.unique_id for entry in self._async_current_entries()}
        in_progress_ids = {
            flow["context"].get("unique_id")
            for flow in self.hass.config_entries.flow.async_progress()
            if flow["handler"] == DOMAIN
        }
        all_known = known_ids | in_progress_ids

        async def _on_ssdp_device(device):
            """Callback for SSDP/UPnP responses - validate WiiM devices."""
            host: str | None = getattr(device, "host", None)
            if host is None and (loc := getattr(device, "location", None)):
                host = urlparse(loc).hostname
            if not host or host in discovered or host in all_known:
                return

            try:
                # Quick validation - just check if device responds
                client = await wiim_factory_client(host)
                try:
                    info = await client.get_player_status()
                    info = await self._ensure_solo(client, info)
                    device_name = (
                        info.get("device_name") or info.get("DeviceName") or host
                    )
                    discovered[host] = device_name
                finally:
                    await client.close()
            except (ConfigEntryNotReady, Exception):
                # Device not reachable or not a WiiM device
                return

        try:
            await async_search(
                async_callback=_on_ssdp_device,
                timeout=5,
                search_target="urn:schemas-upnp-org:device:MediaRenderer:1",
                mx=2,
            )
        except TypeError:
            # Fallback for older versions without mx parameter
            await async_search(
                async_callback=_on_ssdp_device,
                timeout=5,
                search_target="urn:schemas-upnp-org:device:MediaRenderer:1",
            )
        return discovered

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle Zeroconf discovery with simplified validation."""
        host = discovery_info.host
        unique_id = host

        # Check for duplicates
        known_ids = {entry.unique_id for entry in self._async_current_entries()}
        in_progress_ids = {
            flow["context"].get("unique_id")
            for flow in self.hass.config_entries.flow.async_progress()
            if flow["handler"] == DOMAIN
        }
        if unique_id in (known_ids | in_progress_ids):
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        try:
            client = await wiim_factory_client(host)
            try:
                info = await client.get_player_status()
                info = await self._ensure_solo(client, info)
                device_name = info.get("device_name") or info.get("DeviceName") or host
            finally:
                await client.close()
        except ConfigEntryNotReady as err:
            # Specific error handling for SSL/connection issues
            if "ssl" in str(err).lower() or "handshake" in str(err).lower():
                _LOGGER.debug(
                    "SSL/TLS handshake failed for WiiM device at %s from Zeroconf. "
                    "This is normal for devices that only support HTTP: %s",
                    host,
                    err,
                )
            else:
                _LOGGER.debug(
                    "Failed to validate WiiM device at %s from Zeroconf: %s", host, err
                )
            return self.async_abort(reason="cannot_connect")
        except Exception as e:
            _LOGGER.debug(
                "Unexpected error validating WiiM device at %s from Zeroconf: %s",
                host,
                e,
            )
            return self.async_abort(reason="unknown_error_validation")

        self.context["configuration_in_progress"] = True
        self._host = host
        self.context["title_placeholders"] = {"name": device_name, "host": host}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            device_name = (
                self.context.get("title_placeholders", {}).get("name")
                or f"WiiM {self._host}"
            )
            return self.async_create_entry(
                title=device_name,
                data={CONF_HOST: self._host},
            )

        return self.async_show_form(step_id="confirm")

    # -----------------------------------------------------
    # SSDP discovery (native HA flow) ---------------------
    # -----------------------------------------------------

    async def async_step_ssdp(self, discovery_info: dict[str, Any]) -> FlowResult:
        """Handle SSDP discovery from Home Assistant core."""
        # Extract host from SSDP headers
        host = discovery_info.ssdp_headers.get("_host")
        if not host:
            for location_key in ["ssdp_location", "LOCATION", "location"]:
                if loc := discovery_info.ssdp_headers.get(location_key):
                    host = urlparse(loc).hostname
                    break
            else:
                # Try the discovery_info.ssdp_location attribute
                if hasattr(discovery_info, "ssdp_location"):
                    host = urlparse(discovery_info.ssdp_location).hostname

        if not host:
            return self.async_abort(reason="no_host")

        # Validate device and get info
        try:
            client = await wiim_factory_client(host)
            try:
                info = await client.get_player_status()
                info = await self._ensure_solo(client, info)
                unique_id = host
                device_name = info.get("device_name") or info.get("DeviceName") or host
            finally:
                await client.close()
        except (ConfigEntryNotReady, Exception):
            return self.async_abort(reason="cannot_connect")

        # Check for duplicates
        known_ids = {entry.unique_id for entry in self._async_current_entries()}
        in_progress_ids = {
            flow["context"].get("unique_id")
            for flow in self.hass.config_entries.flow.async_progress()
            if flow["handler"] == DOMAIN
        }
        if unique_id in (known_ids | in_progress_ids):
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        self._host = host
        self.context["title_placeholders"] = {"name": device_name, "host": host}
        return await self.async_step_confirm()

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Handle import from YAML or programmatic flow."""
        return await self.async_step_user(import_config)

    async def _ensure_solo(
        self, client: "WiiMClient", info: dict[str, Any]
    ) -> dict[str, Any]:
        """If the speaker is in a multi-room group, leave or disband it.

        We leave groups when the device is **slave** and delete the whole
        group when it is **master** with at least one slave.  Returns an
        updated status dict after the operation (may be unchanged when the
        device was already solo).
        """

        # If device is a slave → leave group
        if info.get("role") == "slave" or str(info.get("group")) == "1":
            try:
                await client.leave_group()
            except Exception:
                pass
            return await client.get_player_status()

        # If device is master with slaves → disband group
        multi = info.get("multiroom", {})
        has_slaves = bool(multi.get("slave_list")) or multi.get("slaves", 0)
        if has_slaves:
            try:
                await client.delete_group()
            except Exception:
                pass
            return await client.get_player_status()

        return info


class WiiMOptionsFlow(config_entries.OptionsFlow):
    """Handle WiiM options."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Init options flow."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:  # noqa: D401
        """Handle options flow."""
        if user_input is not None:
            # Convert user-friendly names back to internal names
            options_data = {}

            # Map user-friendly field names to internal names
            if CONF_STATUS_UPDATE_INTERVAL in user_input:
                options_data[CONF_POLL_INTERVAL] = user_input[
                    CONF_STATUS_UPDATE_INTERVAL
                ]

            # Convert volume step from percentage back to decimal
            if CONF_VOLUME_STEP_PERCENT in user_input:
                options_data[CONF_VOLUME_STEP] = (
                    user_input[CONF_VOLUME_STEP_PERCENT] / 100.0
                )

            # Map group entity option (keep existing internal key for compatibility)
            if CONF_ENABLE_GROUP_ENTITY in user_input:
                options_data["own_group_entity"] = user_input[CONF_ENABLE_GROUP_ENTITY]

            # Map debug logging option (keep existing internal key for compatibility)
            if CONF_DEBUG_LOGGING in user_input:
                options_data["debug_logging"] = user_input[CONF_DEBUG_LOGGING]
                # Set logger level based on debug_logging option
                await self.hass.services.async_call(
                    "logger",
                    "set_level",
                    {
                        "custom_components.wiim": "debug"
                        if user_input[CONF_DEBUG_LOGGING]
                        else "info"
                    },
                    blocking=True,
                )

            return self.async_create_entry(title="", data=options_data)

        # Get current values and convert for display
        current_poll_interval = self.entry.options.get(
            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
        )
        current_volume_step = self.entry.options.get(
            CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP
        )
        current_debug_logging = self.entry.options.get("debug_logging", False)
        current_group_entity = self.entry.options.get("own_group_entity", False)

        # Convert volume step from decimal to percentage for user display
        volume_step_percent = int(current_volume_step * 100)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_STATUS_UPDATE_INTERVAL,
                    default=current_poll_interval,
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Optional(
                    CONF_VOLUME_STEP_PERCENT,
                    default=volume_step_percent,
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
                vol.Optional(
                    CONF_ENABLE_GROUP_ENTITY,
                    default=current_group_entity,
                ): bool,
                vol.Optional(
                    CONF_DEBUG_LOGGING,
                    default=current_debug_logging,
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
