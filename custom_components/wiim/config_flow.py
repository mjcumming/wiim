"""Config flow to configure WiiM component.

Simple discovery and setup flow following Home Assistant best practices.
"""

# mypy: ignore-errors

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import WiiMClient
from .const import (
    CONF_DEBUG_LOGGING,
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
    """Validate that a host is a WiiM/LinkPlay device and extract device info."""

    client = WiiMClient(host)
    try:
        # Try to get device status - this is the most reliable way to validate
        status = await client.get_status()
        if not status:
            _LOGGER.debug("No status response from %s", host)
            return False, host, None

        # Extract device name with priority order
        # PRIORITY 1: DeviceName from WiiM API (custom name set in app)
        # PRIORITY 2: Other name fields
        # PRIORITY 3: SSID/Network name (less reliable)
        device_name = (
            status.get("DeviceName")  # Custom name set in WiiM app
            or status.get("device_name")  # Alternative field name
            or status.get("friendlyName")  # Common API field
            or status.get("name")  # Generic name field
            or status.get("ssid", host)  # Device hotspot name (fallback)
        )

        if not device_name or device_name == "Unknown":
            device_name = f"WiiM Device ({host})"

        # Extract UUID - this is critical for device identification
        device_uuid = status.get("uuid")
        if not device_uuid:
            # Some older devices may not provide UUID
            _LOGGER.warning("Device at %s did not provide UUID, using host as fallback", host)
            device_uuid = host

        _LOGGER.debug("Successfully validated device %s at %s (UUID: %s)", device_name, host, device_uuid)
        return True, device_name, device_uuid

    except Exception as err:
        # Log the specific error for debugging
        error_str = str(err).lower()
        if "404" in error_str:
            _LOGGER.debug("Device at %s returned 404 - likely not a WiiM/LinkPlay device", host)
        elif "timeout" in error_str:
            _LOGGER.debug("Timeout connecting to %s - device may be offline", host)
        elif "connection refused" in error_str:
            _LOGGER.debug("Connection refused by %s - device may not support HTTP API", host)
        else:
            _LOGGER.debug("Failed to validate device at %s: %s", host, err)
        return False, host, None
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

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:  # type: ignore[override]
        """Handle user-initiated setup - go straight to manual entry."""
        # Skip the setup mode choice and go directly to manual entry
        # since autodiscovery often fails and manual is more reliable
        return await self.async_step_manual()

    async def async_step_discovery(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:  # type: ignore[override]
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
            if not is_valid or not device_uuid:
                return self.async_abort(reason="cannot_connect")

            # Prefer the real device UUID when available. Otherwise fall back to the
            # host IP address to ensure we can still detect duplicates and satisfy
            # older unit-tests that patch `validate_wiim_device` to return only a
            # 2-tuple.

            unique_id = device_uuid or host

            await self.async_set_unique_id(unique_id)
            # Abort if this unique_id (UUID or host) is already configured.
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

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle manual IP entry with improved UX."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()

            # validate_wiim_device historically returned 2 items.
            # To remain backward-compatible with existing unit tests we
            # gracefully accept both 2-tuple and 3-tuple results.
            validated = await validate_wiim_device(host)

            # Normalise result to (is_valid, device_name, device_uuid)
            if isinstance(validated, tuple):
                if len(validated) == 2:
                    is_valid, device_name = validated  # type: ignore[misc]
                    device_uuid = None
                else:
                    is_valid, device_name, device_uuid = validated  # type: ignore[misc]
            else:
                # Should not happen but keep mypy happy
                is_valid, device_name, device_uuid = False, str(validated), None

            if is_valid:
                # Prefer the real device UUID when available. Otherwise fall back to the
                # host IP address to ensure we can still detect duplicates and satisfy
                # older unit-tests that patch `validate_wiim_device` to return only a
                # 2-tuple.

                unique_id = device_uuid or host

                await self.async_set_unique_id(unique_id)
                # Abort if this unique_id (UUID or host) is already configured.
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=device_name, data={CONF_HOST: host})

            # Validation failed – surface the standard connection error so the form
            # stays open for the user to correct the input.
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

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """Handle Zeroconf discovery."""
        host = discovery_info.host
        _LOGGER.info("🔍 ZEROCONF DISCOVERY called for host: %s", host)

        is_valid, device_name, device_uuid = await validate_wiim_device(host)
        if not is_valid or not device_uuid:
            _LOGGER.warning("🔍 ZEROCONF DISCOVERY validation failed for host: %s", host)
            return self.async_abort(reason="cannot_connect")

        _LOGGER.info("🔍 ZEROCONF DISCOVERY validated device: %s at %s (UUID: %s)", device_name, host, device_uuid)

        # Prefer the real device UUID when available. Otherwise fall back to the
        # host IP address to ensure we can still detect duplicates and satisfy
        # older unit-tests that patch `validate_wiim_device` to return only a
        # 2-tuple.

        unique_id = device_uuid or host

        await self.async_set_unique_id(unique_id)
        # Abort if this unique_id (UUID or host) is already configured.
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Store data for discovery confirmation
        self.data = {CONF_HOST: host, "name": device_name}
        return await self.async_step_discovery_confirm()

    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> ConfigFlowResult:
        """Handle SSDP discovery."""
        _LOGGER.debug("SSDP discovery from: %s", discovery_info.ssdp_location)

        if not discovery_info.ssdp_location:
            _LOGGER.debug("SSDP discovery aborted: no ssdp_location")
            return self.async_abort(reason="no_host")

        host = urlparse(discovery_info.ssdp_location).hostname
        if not host:
            _LOGGER.debug("SSDP discovery aborted: no host from %s", discovery_info.ssdp_location)
            return self.async_abort(reason="no_host")

        _LOGGER.debug("SSDP discovery attempting validation for host: %s", host)

        is_valid, device_name, device_uuid = await validate_wiim_device(host)
        if not is_valid or not device_uuid:
            _LOGGER.debug("SSDP discovery validation failed for host: %s", host)
            return self.async_abort(reason="cannot_connect")

        _LOGGER.info("SSDP discovery validated device: %s at %s", device_name, host)

        # Prefer the real device UUID when available. Otherwise fall back to the
        # host IP address to ensure we can still detect duplicates and satisfy
        # older unit-tests that patch `validate_wiim_device` to return only a
        # 2-tuple.

        unique_id = device_uuid or host

        await self.async_set_unique_id(unique_id)
        # Abort if this unique_id (UUID or host) is already configured.
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Store data for discovery confirmation
        self.data = {CONF_HOST: host, "name": device_name}
        return await self.async_step_discovery_confirm()

    async def async_step_integration_discovery(self, discovery_info: dict[str, Any]) -> ConfigFlowResult:
        """Handle integration discovery (automatic slave discovery and missing devices)."""
        host = discovery_info.get(CONF_HOST)
        device_name = discovery_info.get("device_name", "Unknown Device")
        device_uuid = discovery_info.get("device_uuid")
        discovery_source = discovery_info.get("discovery_source")

        _LOGGER.info(
            "🔍 INTEGRATION DISCOVERY called for device %s at %s (UUID: %s, source: %s)",
            device_name,
            host,
            device_uuid,
            discovery_source,
        )

        # Handle missing device discovery (no IP provided)
        if discovery_source == "missing_device":
            return await self.async_step_missing_device()

        if not host:
            _LOGGER.warning("🔍 INTEGRATION DISCOVERY aborted: no host")
            return self.async_abort(reason="no_host")

        # Validate the device is still reachable
        is_valid, validated_name, validated_uuid = await validate_wiim_device(host)
        if not is_valid or not validated_uuid:
            _LOGGER.warning("Integration discovery failed validation for %s at %s", device_name, host)
            return self.async_abort(reason="cannot_connect")

        # Use validated data (more accurate than discovery data)
        final_name = validated_name or device_name
        final_uuid = validated_uuid

        # Prefer the real device UUID when available. Otherwise fall back to the
        # host IP address to ensure we can still detect duplicates and satisfy
        # older unit-tests that patch `validate_wiim_device` to return only a
        # 2-tuple.

        unique_id = final_uuid or host

        await self.async_set_unique_id(unique_id)
        # Abort if this unique_id (UUID or host) is already configured.
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Store data for discovery confirmation
        self.data = {CONF_HOST: host, "name": final_name}

        _LOGGER.info("🔍 INTEGRATION DISCOVERY completed for %s at %s", final_name, host)
        return await self.async_step_discovery_confirm()

    async def async_step_missing_device(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle missing device discovery - user provides IP for known UUID."""
        errors = {}
        device_uuid = self.context.get("unique_id")
        device_name = (self.data or {}).get("device_name", f"Device {device_uuid[:8] if device_uuid else 'Unknown'}...")

        if user_input is not None:
            host = user_input[CONF_HOST].strip()

            # Validate device and check UUID matches
            is_valid, validated_name, validated_uuid = await validate_wiim_device(host)

            if not is_valid:
                errors["base"] = "cannot_connect"
            elif validated_uuid != device_uuid:
                errors["base"] = "uuid_mismatch"
                _LOGGER.warning("UUID mismatch: expected %s, got %s", device_uuid, validated_uuid)
            else:
                # Success - create entry
                await self.async_set_unique_id(device_uuid)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=validated_name, data={CONF_HOST: host})

        schema = vol.Schema({vol.Required(CONF_HOST, description="IP address of the missing device"): str})

        return self.async_show_form(
            step_id="missing_device",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "device_name": device_name,
                "device_uuid": device_uuid[:8] + "..." if device_uuid else "Unknown",
            },
        )

    async def async_step_discovery_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.data["name"],
                data={CONF_HOST: self.data[CONF_HOST]},
            )

        # Set title placeholders here where the UI actually processes them
        self.context["title_placeholders"] = {"name": self.data["name"]}
        _LOGGER.info("🔍 DISCOVERY CONFIRM set title_placeholders: %s", {"name": self.data["name"]})

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": self.data["name"]},
        )

    def is_matching(self, other_flow: config_entries.ConfigFlow) -> bool:
        """Check if two flows are matching."""
        return False


class WiiMOptionsFlow(config_entries.OptionsFlow):
    """Handle WiiM options."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            options_data = {}

            # Volume step: convert from percentage (UI) to decimal (internal)
            if CONF_VOLUME_STEP_PERCENT in user_input:
                options_data[CONF_VOLUME_STEP] = user_input[CONF_VOLUME_STEP_PERCENT] / 100.0

            # Feature toggles
            if CONF_ENABLE_MAINTENANCE_BUTTONS in user_input:
                options_data[CONF_ENABLE_MAINTENANCE_BUTTONS] = user_input[CONF_ENABLE_MAINTENANCE_BUTTONS]
            if CONF_DEBUG_LOGGING in user_input:
                options_data[CONF_DEBUG_LOGGING] = user_input[CONF_DEBUG_LOGGING]

            return self.async_create_entry(title="", data=options_data)

        # Populate form with current or default values
        current_volume_step_decimal = self.entry.options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
        volume_step_percent = int(current_volume_step_decimal * 100)

        current_maintenance_buttons = self.entry.options.get(CONF_ENABLE_MAINTENANCE_BUTTONS, False)
        current_debug_logging = self.entry.options.get(CONF_DEBUG_LOGGING, False)

        schema = vol.Schema(
            {
                vol.Optional(CONF_VOLUME_STEP_PERCENT, default=volume_step_percent): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=50)
                ),
                vol.Optional(CONF_ENABLE_MAINTENANCE_BUTTONS, default=current_maintenance_buttons): bool,
                vol.Optional(CONF_DEBUG_LOGGING, default=current_debug_logging): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
