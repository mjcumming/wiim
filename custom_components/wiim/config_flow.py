"""Config flow to configure WiiM component.

Simple discovery and setup flow following Home Assistant best practices.
"""
# type: ignore

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

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
    async_search = None  # type: ignore[assignment]

_LOGGER = logging.getLogger(__name__)


async def validate_wiim_device(host: str) -> tuple[bool, str, str | None]:
    """Validate device and get info.

    Returns:
        Tuple of (is_valid, device_name, device_uuid)
    """
    client = WiiMClient(host)
    try:
        if not await client.validate_connection():
            return False, host, None

        device_name = await client.get_device_name()

        # Get device UUID from status (like LinkPlay does)
        device_uuid = None
        try:
            status = await client.get_player_status()
            if uuid := status.get("uuid"):
                device_uuid = uuid
            elif mac := status.get("MAC"):
                # Use MAC as backup UUID (normalized)
                device_uuid = mac.lower().replace(":", "")
        except Exception:
            _LOGGER.debug("Could not get device UUID for %s", host)

        return True, device_name, device_uuid
    finally:
        await client.close()


class WiiMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle WiiM config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._discovered_devices: dict[str, str] = {}
        self.data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> WiiMOptionsFlow:
        """Return the options flow."""
        return WiiMOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:  # type: ignore[override]
        """Handle user-initiated setup - go straight to manual entry."""
        # Skip the setup mode choice and go directly to manual entry
        # since autodiscovery often fails and manual is more reliable
        return await self.async_step_manual()

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
            is_valid, device_name, device_uuid = await validate_wiim_device(host)
            if not is_valid:
                return self.async_abort(reason="cannot_connect")

            # Use device UUID if available, otherwise fall back to host
            unique_id = device_uuid or host
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

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
        """Handle manual IP entry with improved UX."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()

            is_valid, device_name, device_uuid = await validate_wiim_device(host)
            if is_valid:
                # Use device UUID if available, otherwise fall back to host
                unique_id = device_uuid or host
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=device_name, data={CONF_HOST: host})
            else:
                errors["base"] = "cannot_connect"

        schema = vol.Schema({vol.Required(CONF_HOST, description="IP address of your WiiM device"): str})

        return self.async_show_form(
            step_id="manual",
            data_schema=schema,
            errors=errors,
            description_placeholders={"example_ip": "192.168.1.100"},
        )

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

            is_valid, device_name, _ = await validate_wiim_device(host)
            if is_valid:
                discovered[host] = device_name

        try:
            await async_search(
                async_callback=_on_device, timeout=5, search_target="urn:schemas-upnp-org:device:MediaRenderer:1"
            )
        except Exception as err:
            _LOGGER.debug("Discovery error: %s", err)

        return discovered

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> FlowResult:
        """Handle Zeroconf discovery."""
        host = discovery_info.host
        _LOGGER.warning("🔍 ZEROCONF DISCOVERY called for host: %s", host)

        is_valid, device_name, device_uuid = await validate_wiim_device(host)
        if not is_valid:
            _LOGGER.warning("🔍 ZEROCONF DISCOVERY validation failed for host: %s", host)
            return self.async_abort(reason="cannot_connect")

        _LOGGER.warning("🔍 ZEROCONF DISCOVERY validated device: %s at %s (UUID: %s)", device_name, host, device_uuid)

        # Use device UUID if available, otherwise fall back to host
        unique_id = device_uuid or host
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Store data for discovery confirmation
        self.data = {CONF_HOST: host, "name": device_name}
        return await self.async_step_discovery_confirm()

    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> FlowResult:
        """Handle SSDP discovery."""
        _LOGGER.warning("🔍 SSDP DISCOVERY called with: %s", discovery_info.ssdp_location)

        if not discovery_info.ssdp_location:
            _LOGGER.warning("🔍 SSDP DISCOVERY aborted: no ssdp_location")
            return self.async_abort(reason="no_host")

        host = urlparse(discovery_info.ssdp_location).hostname
        if not host:
            _LOGGER.warning("🔍 SSDP DISCOVERY aborted: no host from %s", discovery_info.ssdp_location)
            return self.async_abort(reason="no_host")

        _LOGGER.warning("🔍 SSDP DISCOVERY extracted host: %s", host)

        is_valid, device_name, device_uuid = await validate_wiim_device(host)
        if not is_valid:
            _LOGGER.warning("🔍 SSDP DISCOVERY validation failed for host: %s", host)
            return self.async_abort(reason="cannot_connect")

        _LOGGER.warning("🔍 SSDP DISCOVERY validated device: %s at %s (UUID: %s)", device_name, host, device_uuid)

        # Use device UUID if available, otherwise fall back to host
        unique_id = device_uuid or host
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Store data for discovery confirmation
        self.data = {CONF_HOST: host, "name": device_name}
        return await self.async_step_discovery_confirm()

    async def async_step_integration_discovery(self, discovery_info: dict[str, Any]) -> FlowResult:
        """Handle integration discovery (automatic slave discovery)."""
        host = discovery_info.get(CONF_HOST)
        device_name = discovery_info.get("device_name", "Unknown Device")
        device_uuid = discovery_info.get("device_uuid")

        _LOGGER.warning("🔍 INTEGRATION DISCOVERY called for device %s at %s (UUID: %s)", device_name, host, device_uuid)

        if not host:
            _LOGGER.warning("🔍 INTEGRATION DISCOVERY aborted: no host")
            return self.async_abort(reason="no_host")

        # Validate the device is still reachable
        is_valid, validated_name, validated_uuid = await validate_wiim_device(host)
        if not is_valid:
            _LOGGER.warning("Integration discovery failed validation for %s at %s", device_name, host)
            return self.async_abort(reason="cannot_connect")

        # Use validated data (more accurate than discovery data)
        final_name = validated_name or device_name
        final_uuid = validated_uuid or device_uuid or host

        await self.async_set_unique_id(final_uuid)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Store data for discovery confirmation
        self.data = {CONF_HOST: host, "name": final_name}

        _LOGGER.warning("🔍 INTEGRATION DISCOVERY completed for %s at %s", final_name, host)
        _LOGGER.info("Integration discovery completed for %s at %s", final_name, host)
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.data["name"],
                data={CONF_HOST: self.data[CONF_HOST]},
            )

        # Set title placeholders here where the UI actually processes them
        self.context["title_placeholders"] = {"name": self.data["name"]}
        _LOGGER.warning("🔍 DISCOVERY CONFIRM set title_placeholders: %s", {"name": self.data["name"]})

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": self.data["name"]},
        )


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
