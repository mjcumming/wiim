"""Config flow to configure WiiM component.

Simple discovery and setup flow following Home Assistant best practices.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import WiiMClient
from .const import (
    CONF_DEBUG_LOGGING,
    CONF_ENABLE_DIAGNOSTIC_ENTITIES,
    CONF_ENABLE_MAINTENANCE_BUTTONS,
    CONF_VOLUME_STEP,
    CONF_VOLUME_STEP_PERCENT,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)

# --- Discovery imports ---
try:
    from async_upnp_client.search import async_search
except ImportError:
    async_search = None

import zeroconf

_LOGGER = logging.getLogger(__name__)


async def validate_wiim_device(host: str) -> tuple[bool, str]:
    """Validate device and get name.

    Returns:
        Tuple of (is_valid, device_name)
    """
    client = WiiMClient(host)
    try:
        if not await client.validate_connection():
            return False, host

        device_name = await client.get_device_name()
        return True, device_name
    finally:
        await client.close()


class WiiMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle WiiM config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._discovered_devices: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> WiiMOptionsFlow:
        """Return the options flow."""
        return WiiMOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle user-initiated setup."""
        if user_input is not None:
            if user_input.get("setup_mode") == "manual":
                return await self.async_step_manual()
            else:
                return await self.async_step_discovery()

        # Show setup method choice
        schema = vol.Schema(
            {
                vol.Required("setup_mode", default="discovery"): vol.In(
                    {"discovery": "Automatic discovery", "manual": "Manual IP entry"}
                )
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_discovery(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle automatic discovery."""
        if not self._discovered_devices:
            # Run discovery
            self._discovered_devices = await self._discover_devices()

        if user_input is not None:
            selected = user_input[CONF_HOST]

            if selected == "manual_entry":
                return await self.async_step_manual()

            # Find the actual host from our options
            host = None
            for device_host, device_name in self._discovered_devices.items():
                if f"{device_name} ({device_host})" == selected:
                    host = device_host
                    break

            if not host:
                return await self.async_step_manual()

            # Validate and create entry
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            is_valid, device_name = await validate_wiim_device(host)
            if not is_valid:
                return self.async_abort(reason="cannot_connect")

            return self.async_create_entry(title=device_name, data={CONF_HOST: host})

        if self._discovered_devices:
            # Show discovered devices
            options = [f"{name} ({host})" for host, name in self._discovered_devices.items()]
            options.append("Enter IP manually")

            option_map = {}
            for host, name in self._discovered_devices.items():
                option_map[f"{name} ({host})"] = host
            option_map["Enter IP manually"] = "manual_entry"

            schema = vol.Schema({vol.Required(CONF_HOST): vol.In(options)})

            return self.async_show_form(
                step_id="discovery",
                data_schema=schema,
                description_placeholders={"count": str(len(self._discovered_devices))},
            )
        else:
            # No devices found
            return await self.async_step_manual()

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle manual IP entry."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            is_valid, device_name = await validate_wiim_device(host)
            if is_valid:
                return self.async_create_entry(title=device_name, data={CONF_HOST: host})
            else:
                errors["base"] = "cannot_connect"

        schema = vol.Schema({vol.Required(CONF_HOST): str})
        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors)

    async def _discover_devices(self) -> dict[str, str]:
        """Discover WiiM devices via UPnP."""
        if not async_search:
            return {}

        discovered = {}
        known_hosts = {entry.data[CONF_HOST] for entry in self._async_current_entries()}

        async def _on_device(device):
            """Handle discovered device."""
            host = getattr(device, "host", None)
            if not host and (loc := getattr(device, "location", None)):
                host = urlparse(loc).hostname

            if not host or host in discovered or host in known_hosts:
                return

            is_valid, device_name = await validate_wiim_device(host)
            if is_valid:
                discovered[host] = device_name

        try:
            await async_search(
                async_callback=_on_device, timeout=5, search_target="urn:schemas-upnp-org:device:MediaRenderer:1"
            )
        except Exception as err:
            _LOGGER.debug("Discovery error: %s", err)

        return discovered

    async def async_step_zeroconf(self, discovery_info: zeroconf.ZeroconfServiceInfo) -> FlowResult:
        """Handle Zeroconf discovery."""
        host = discovery_info.host

        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        is_valid, device_name = await validate_wiim_device(host)
        if not is_valid:
            return self.async_abort(reason="cannot_connect")

        self.context["title_placeholders"] = {"name": device_name, "host": host}
        return await self.async_step_confirm()

    async def async_step_ssdp(self, discovery_info: dict[str, Any]) -> FlowResult:
        """Handle SSDP discovery."""
        host = None
        for key in ["_host", "ssdp_location", "LOCATION", "location"]:
            if val := discovery_info.ssdp_headers.get(key):
                if key == "_host":
                    host = val
                else:
                    host = urlparse(val).hostname
                break

        if not host:
            return self.async_abort(reason="no_host")

        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()

        is_valid, device_name = await validate_wiim_device(host)
        if not is_valid:
            return self.async_abort(reason="cannot_connect")

        self.context["title_placeholders"] = {"name": device_name, "host": host}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            placeholders = self.context.get("title_placeholders", {})
            return self.async_create_entry(
                title=placeholders.get("name", f"WiiM {placeholders.get('host', '')}"),
                data={CONF_HOST: placeholders.get("host")},
            )

        return self.async_show_form(step_id="confirm")


class WiiMOptionsFlow(config_entries.OptionsFlow):
    """Handle WiiM options."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            options_data = {}

            # Volume step: convert from percentage (UI) to decimal (internal)
            if CONF_VOLUME_STEP_PERCENT in user_input:
                options_data[CONF_VOLUME_STEP] = user_input[CONF_VOLUME_STEP_PERCENT] / 100.0

            # Feature toggles
            if CONF_ENABLE_MAINTENANCE_BUTTONS in user_input:
                options_data[CONF_ENABLE_MAINTENANCE_BUTTONS] = user_input[CONF_ENABLE_MAINTENANCE_BUTTONS]
            if CONF_ENABLE_DIAGNOSTIC_ENTITIES in user_input:
                options_data[CONF_ENABLE_DIAGNOSTIC_ENTITIES] = user_input[CONF_ENABLE_DIAGNOSTIC_ENTITIES]
            if CONF_DEBUG_LOGGING in user_input:
                options_data[CONF_DEBUG_LOGGING] = user_input[CONF_DEBUG_LOGGING]

            return self.async_create_entry(title="", data=options_data)

        # Populate form with current or default values
        current_volume_step_decimal = self.entry.options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
        volume_step_percent = int(current_volume_step_decimal * 100)

        current_maintenance_buttons = self.entry.options.get(CONF_ENABLE_MAINTENANCE_BUTTONS, True)
        current_diagnostic_entities = self.entry.options.get(CONF_ENABLE_DIAGNOSTIC_ENTITIES, False)
        current_debug_logging = self.entry.options.get(CONF_DEBUG_LOGGING, False)

        schema = vol.Schema(
            {
                vol.Optional(CONF_VOLUME_STEP_PERCENT, default=volume_step_percent): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=50)
                ),
                vol.Optional(CONF_ENABLE_MAINTENANCE_BUTTONS, default=current_maintenance_buttons): bool,
                vol.Optional(CONF_ENABLE_DIAGNOSTIC_ENTITIES, default=current_diagnostic_entities): bool,
                vol.Optional(CONF_DEBUG_LOGGING, default=current_debug_logging): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
