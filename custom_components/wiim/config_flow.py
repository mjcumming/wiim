from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
import logging
import asyncio

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import WiiMClient, WiiMError
from .const import (
    CONF_POLL_INTERVAL,
    CONF_VOLUME_STEP,
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

async def _async_validate_host(host: str) -> None:
    """Validate we can talk to the WiiM device and always close the session."""
    client = WiiMClient(host)
    max_retries = 3
    retry_delay = 1  # seconds

    for attempt in range(max_retries):
        try:
            await client.get_status()
            return
        except WiiMError as err:
            if attempt == max_retries - 1:
                raise
            _LOGGER.debug("Attempt %d failed to validate WiiM device at %s: %s", attempt + 1, host, err)
            await asyncio.sleep(retry_delay)
        finally:
            # Ensure the underlying aiohttp session is closed even on failure
            await client.close()


class WiiMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a WiiM config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up instance."""
        self._host: str | None = None
        self._discovered_hosts: dict[str, str] = {}

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
        """Handle the initial step (manual or UPnP discovery), use device name from API, and filter duplicates."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                client = WiiMClient(host)
                info = await client.get_player_status()
                # Use host/IP as unique_id to guarantee one entry per device
                unique_id = host
                # If device is in a group, ungroup it
                if info.get("role") == "slave" or info.get("group") == "1":
                    try:
                        await client.leave_group()
                    except Exception:
                        pass
                    info = await client.get_player_status()
                device_name = info.get("device_name") or info.get("DeviceName") or host
                model = info.get("device_model") or info.get("hardware") or ""
                firmware = info.get("firmware") or ""
                await client.close()
                # Ensure no duplicate by checking configured entries **and**
                # flows that are half-way through (scenario: two discoveries
                # fire at the same time).
                known_ids = {entry.unique_id for entry in self._async_current_entries()}
                in_progress_ids = {
                    flow["context"].get("unique_id")
                    for flow in self.hass.config_entries.flow.async_progress()
                    if flow["handler"] == DOMAIN
                }
                if unique_id in (known_ids | in_progress_ids):
                    return self.async_abort(reason="already_configured")
                await self.async_set_unique_id(unique_id)
                existing_entry = self._async_current_entries()
                for entry in existing_entry:
                    if entry.unique_id == unique_id:
                        if entry.data.get(CONF_HOST) != host:
                            _LOGGER.debug("[WiiM] Updating host for %s: %s -> %s", unique_id, entry.data.get(CONF_HOST), host)
                            self.hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_HOST: host})
                        self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device_name, data={CONF_HOST: host}
                )
            except WiiMError:
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.error("[WiiM] Error during config flow: %s", e)
                errors["base"] = "unknown"
        if async_search is not None:
            return await self.async_step_upnp()
        schema = vol.Schema({vol.Required(CONF_HOST): str})
        # Try to show placeholders if we have info
        placeholders = {}
        if 'device_name' in locals():
            placeholders = {
                "device_name": device_name,
                "host": host,
                "model": model,
                "firmware": firmware,
            }
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors, description_placeholders=placeholders)

    async def async_step_upnp(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Discover WiiM/LinkPlay devices via UPnP/SSDP."""
        errors: dict[str, str] = {}
        if not self._discovered_hosts:
            # Perform UPnP discovery.  Returns dict{host: friendly_name}
            self._discovered_hosts = await self._discover_upnp_hosts()
        if user_input is not None:
            selected = user_input[CONF_HOST]
            if hasattr(self, "_options_map") and selected in self._options_map:  # type: ignore[attr-defined]
                host = self._options_map[selected]  # type: ignore[attr-defined]
            else:
                host = selected
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()
            try:
                await _async_validate_host(host)
            except WiiMError:
                errors["base"] = "cannot_connect"
            else:
                # Fetch device name for nicer entry title
                device_name = host
                client = None
                try:
                    client = WiiMClient(host)
                    info = await client.get_player_status()
                    device_name = info.get("device_name") or info.get("DeviceName") or host
                except Exception:
                    pass
                finally:
                    if client is not None:
                        try:
                            await client.close()
                        except Exception:
                            pass
                return self.async_create_entry(
                    title=device_name,
                    data={CONF_HOST: host},
                )
        if self._discovered_hosts:
            # Build a label→host map so the dropdown shows nice names
            options_map = {
                f"{name} ({host})": host for host, name in self._discovered_hosts.items()
            }
            self._options_map = options_map  # type: ignore[attr-defined]
            schema = vol.Schema({vol.Required(CONF_HOST): vol.In(list(options_map.keys()))})
            # Try to show placeholders for the first discovered device
            first_host = next(iter(self._discovered_hosts), None)
            placeholders = {}
            if first_host:
                try:
                    client = WiiMClient(first_host)
                    info = await client.get_player_status()
                    device_name = info.get("device_name") or info.get("DeviceName") or first_host
                    model = info.get("device_model") or info.get("hardware") or ""
                    firmware = info.get("firmware") or ""
                    await client.close()
                    placeholders = {
                        "device_name": device_name,
                        "host": first_host,
                        "model": model,
                        "firmware": firmware,
                    }
                except Exception:
                    pass
            return self.async_show_form(
                step_id="upnp",
                data_schema=schema,
                errors=errors,
                description_placeholders=placeholders,
            )
        # If no devices found, fall back to manual
        schema = vol.Schema({vol.Required(CONF_HOST): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def _discover_upnp_hosts(self) -> dict[str, str]:
        """Discover devices and return mapping of host→friendly name."""
        if async_search is None:
            return {}

        discovered: dict[str, str] = {}
        known_ids = {entry.unique_id for entry in self._async_current_entries()}
        in_progress_ids = {flow['context'].get('unique_id') for flow in self.hass.config_entries.flow.async_progress() if flow['handler'] == DOMAIN}
        all_known = known_ids | in_progress_ids

        async def _on_ssdp_device(device):
            """Callback fired for every SSDP/UPnP response.

            We immediately open a TCP connection to the reported host and run
            `get_player_status` to obtain the device name and confirm it is in
            fact a WiiM/LinkPlay speaker.  Early filtering avoids showing
            random DLNA renderers in the dropdown.
            """
            host: str | None = getattr(device, "host", None)
            if host is None and (loc := getattr(device, "location", None)):
                host = urlparse(loc).hostname
            if not host or host in discovered:
                return
            try:
                client = WiiMClient(host)
                info = await client.get_player_status()
                # Use host/IP as unique_id to guarantee one entry per device
                unique_id = host
                await client.close()
                if unique_id in all_known:
                    return
            except Exception:
                return
            discovered[host] = info.get("device_name") or host

        try:
            await async_search(
                async_callback=_on_ssdp_device,
                timeout=5,
                search_target="urn:schemas-upnp-org:device:MediaRenderer:1",
                mx=2,
            )
        except TypeError:
            await async_search(
                async_callback=_on_ssdp_device,
                timeout=5,
                search_target="urn:schemas-upnp-org:device:MediaRenderer:1",
            )
        return discovered

    async def async_step_zeroconf(self, discovery_info: zeroconf.ZeroconfServiceInfo) -> FlowResult:
        """Handle Zeroconf discovery, filter duplicates, and use device name from API."""
        host = discovery_info.host
        # ────────────────────────────────────────────────────────────────────
        # Zeroconf advertisement – map to (host, name) and re-use same
        # validation logic.  All the duplicate checks mirror the manual &
        # UPnP paths so behaviour stays consistent across discovery methods.
        # Get device host
        # Ignore advertised UUID/MAC; rely on host to enforce uniqueness
        unique_id = host
        # Filter out already-configured or in-progress
        known_ids = {entry.unique_id for entry in self._async_current_entries()}
        in_progress_ids = {flow['context'].get('unique_id') for flow in self.hass.config_entries.flow.async_progress() if flow['handler'] == DOMAIN}
        if unique_id in (known_ids | in_progress_ids):
            return self.async_abort(reason="already_configured")
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        try:
            client = WiiMClient(host)
            info = await client.get_player_status()
            # If device is in a group, ungroup it to enumerate all devices
            if info.get("role") == "slave" or info.get("group") == "1":
                try:
                    await client.leave_group()
                except Exception:
                    pass
                info = await client.get_player_status()
            device_name = info.get("device_name") or info.get("DeviceName") or host
            await client.close()
        except WiiMError as err:
            _LOGGER.error("Failed to validate WiiM device at %s from Zeroconf: %s", host, err)
            return self.async_abort(reason="cannot_connect")
        except Exception as e:
            _LOGGER.error("Unknown error validating WiiM device at %s from Zeroconf: %s", host, e, exc_info=True)
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
            device_name = self.context.get("title_placeholders", {}).get("name") or f"WiiM {self._host}"
            return self.async_create_entry(
                title=device_name,
                data={CONF_HOST: self._host},
            )

        return self.async_show_form(step_id="confirm")

    # -----------------------------------------------------
    # SSDP discovery (native HA flow) ---------------------
    # -----------------------------------------------------

    async def async_step_ssdp(self, discovery_info: dict[str, Any]) -> FlowResult:
        """Handle SSDP discovery from Home Assistant core, filter duplicates, and use device name from API."""
        # ------------------------------------------------------------------
        # HA-native SSDP discovery (same flow object as UPnP search) --------
        # ------------------------------------------------------------------
        # The SSDP payload differs slightly, hence a bespoke parser that tries
        # multiple header names to extract the host/IP.
        # Get device host
        host = discovery_info.ssdp_headers.get("_host")
        if not host:
            if loc := discovery_info.ssdp_headers.get("ssdp_location"):
                host = urlparse(loc).hostname
            elif loc := discovery_info.ssdp_location:
                host = urlparse(loc).hostname
            elif "LOCATION" in discovery_info.ssdp_headers:
                host = urlparse(discovery_info.ssdp_headers["LOCATION"]).hostname
            elif "location" in discovery_info.ssdp_headers:
                host = urlparse(discovery_info.ssdp_headers["location"]).hostname
        if not host:
            return self.async_abort(reason="no_host")
        # Fetch unique_id and filter
        try:
            client = WiiMClient(host)
            info = await client.get_player_status()
            # Use host/IP as unique_id to guarantee one entry per device
            unique_id = host
            # If device is in a group, ungroup it
            if info.get("role") == "slave" or info.get("group") == "1":
                try:
                    await client.leave_group()
                except Exception:
                    pass
                info = await client.get_player_status()
            device_name = info.get("device_name") or info.get("DeviceName") or host
            await client.close()
        except Exception:
            return self.async_abort(reason="cannot_connect")
        known_ids = {entry.unique_id for entry in self._async_current_entries()}
        in_progress_ids = {flow['context'].get('unique_id') for flow in self.hass.config_entries.flow.async_progress() if flow['handler'] == DOMAIN}
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
            # Set logger level based on debug_logging option
            debug_logging = user_input.get("debug_logging", False)
            await self.hass.services.async_call(
                "logger",
                "set_level",
                {"custom_components.wiim": "debug" if debug_logging else "info"},
                blocking=True,
            )
            return self.async_create_entry(title="Options", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=self.entry.options.get(
                        CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Optional(
                    CONF_VOLUME_STEP,
                    default=self.entry.options.get(
                        CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.5)),
                vol.Optional(
                    "debug_logging",
                    default=self.entry.options.get("debug_logging", False),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
