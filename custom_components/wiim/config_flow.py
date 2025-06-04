"""Config flow for the WiiM integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from aiohttp.client_exceptions import ClientError
from homeassistant import config_entries
from homeassistant.components import ssdp, zeroconf
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryNotReady

from .api import WiiMClient, WiiMError
from .const import (
    CONF_DEBUG_LOGGING,
    CONF_ENABLE_DIAGNOSTIC_ENTITIES,
    CONF_ENABLE_MAINTENANCE_BUTTONS,
    CONF_VOLUME_STEP,
    CONF_VOLUME_STEP_PERCENT,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_and_get_device_details(host: str) -> tuple[str, str]:
    """Validate connectivity and retrieve the device name and UUID.

    Connects to the WiiM device, fetches its details using getStatusEx, and extracts
    the device name and a stable unique identifier (UUID).

    Args:
        host: The hostname or IP address of the WiiM device.

    Returns:
        A tuple containing the device name and the device UUID.

    Raises:
        ConfigEntryNotReady: If connection to the device fails.
        WiiMError: For other API-related errors.
    """
    # Use shorter timeout for discovery to avoid blocking the UI
    client = WiiMClient(host, timeout=5.0)
    try:
        _LOGGER.debug("Validating WiiM device at %s", host)

        # Use getStatusEx which returns comprehensive device info including UUID
        device_details = await client.get_status()  # This calls getStatusEx endpoint
        _LOGGER.debug("Device validation response for %s: %s", host, device_details)

        # Extract the actual UUID - this should be a proper UUID from the device
        device_uuid = device_details.get("uuid")
        if not device_uuid:
            # Fallback to MAC if UUID not available
            mac_address = device_details.get("MAC") or device_details.get("mac_address")
            if mac_address:
                device_uuid = mac_address.lower().replace(":", "")
                _LOGGER.info("UUID not found, using MAC address %s as unique ID for %s", device_uuid, host)
            else:
                # Last resort - use a combination of host and device name
                device_name_raw = device_details.get("DeviceName") or device_details.get("device_name")
                if device_name_raw:
                    import hashlib

                    device_uuid = hashlib.md5(f"{host}_{device_name_raw}".encode()).hexdigest()[:12]
                    _LOGGER.warning("No UUID or MAC found, generated fallback ID %s for %s", device_uuid, host)
                else:
                    raise WiiMError(f"Could not retrieve UUID, MAC address, or device name for {host}")

        # Extract device name - this will be cleaned up by the Speaker class later
        device_name = device_details.get("DeviceName") or device_details.get("device_name") or f"WiiM {host}"

        _LOGGER.info(
            "Retrieved device info from getStatusEx: Name='%s', UUID='%s', Host='%s'", device_name, device_uuid, host
        )
        return device_name, device_uuid

    except WiiMError as err:
        _LOGGER.warning("API error while validating WiiM device at %s: %s", host, err)
        raise ConfigEntryNotReady(f"API error connecting to WiiM device at {host}: {err}") from err
    except ClientError as err:
        _LOGGER.warning("Connection error while validating WiiM device at %s: %s", host, err)
        raise ConfigEntryNotReady(f"Cannot connect to WiiM device at {host}: {err}") from err
    except Exception as err:
        _LOGGER.warning("Unexpected error while validating WiiM device at %s: %s", host, err)
        raise ConfigEntryNotReady(f"Unexpected error connecting to WiiM device at {host}: {err}") from err
    finally:
        await client.close()


class WiiMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Manages the configuration flow for setting up a new WiiM device."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the WiiM config flow."""
        self._host: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> WiiMOptionsFlow:
        """Get the options flow for this handler."""
        return WiiMOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step of the user configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if not host:
                errors["base"] = "no_host"  # Use a translation key
            else:
                try:
                    # Validate connectivity and get a descriptive device name and UUID
                    device_name, device_uuid = await _validate_and_get_device_details(host)

                    await self.async_set_unique_id(device_uuid)
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: host},
                        reload_on_update=True,  # Reload if host changed for existing UUID
                    )

                    _LOGGER.info(
                        "Successfully identified WiiM device '%s' (UUID: %s) at %s",
                        device_name,
                        device_uuid,
                        host,
                    )
                    return self.async_create_entry(
                        title=device_name,
                        data={CONF_HOST: host, "uuid": device_uuid},  # Store UUID in entry data too
                    )

                except ConfigEntryNotReady:
                    _LOGGER.warning("Connection to WiiM device at %s failed during setup", host)
                    errors["base"] = "cannot_connect"  # Use a translation key
                except WiiMError as err:  # Catch specific WiiMErrors if _validate raises them directly
                    _LOGGER.warning("API error configuring WiiM device at %s: %s", host, err)
                    errors["base"] = "cannot_connect"  # Or a more specific error key
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected error configuring WiiM device at %s", host)
                    errors["base"] = "unknown"  # Use a translation key
        # Show the form to the user
        schema = vol.Schema({vol.Required(CONF_HOST, default=self._host or ""): str})
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle a flow initialized by SSDP discovery."""
        _LOGGER.info("🔍 SSDP discovery triggered for WiiM integration")
        _LOGGER.debug("SSDP discovery received: %s", discovery_info)
        _LOGGER.debug("SSDP location: %s", getattr(discovery_info, "ssdp_location", "N/A"))
        _LOGGER.debug("SSDP USN: %s", getattr(discovery_info, "ssdp_usn", "N/A"))
        _LOGGER.debug("SSDP ST: %s", getattr(discovery_info, "ssdp_st", "N/A"))
        _LOGGER.debug("SSDP upnp data: %s", getattr(discovery_info, "upnp", {}))

        # Extract host from the SSDP location URL
        host = None
        if discovery_info.ssdp_location:
            from urllib.parse import urlparse

            parsed = urlparse(discovery_info.ssdp_location)
            if parsed.hostname:
                host = parsed.hostname
                # WiiM devices typically use HTTPS (443) or HTTP (80)
                # Don't append port 80 as it's default for HTTP
                if parsed.port and parsed.port not in (80, 443):
                    host = f"{host}:{parsed.port}"

        if not host:
            _LOGGER.warning("❌ No valid host found in SSDP discovery info: %s", discovery_info.ssdp_location)
            return self.async_abort(reason="no_host")

        self._host = host
        _LOGGER.info("✅ Discovered WiiM device via SSDP at %s (from location: %s)", host, discovery_info.ssdp_location)

        try:
            # Validate the device and get details
            _LOGGER.debug("🔗 Attempting to validate discovered device at %s", host)
            device_name, device_uuid = await _validate_and_get_device_details(host)

            await self.async_set_unique_id(device_uuid)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: host},
                reload_on_update=True,
            )

            # Show confirmation form to user
            self.context["title_placeholders"] = {"name": device_name}
            _LOGGER.info("🎉 SSDP discovery successful for %s (%s)", device_name, host)
            return await self.async_step_discovery_confirm()

        except (ConfigEntryNotReady, WiiMError) as err:
            _LOGGER.warning("❌ Failed to validate SSDP discovered device at %s: %s", host, err)
            return self.async_abort(reason="cannot_connect")

    async def async_step_zeroconf(self, discovery_info: zeroconf.ZeroconfServiceInfo) -> FlowResult:
        """Handle a flow initialized by Zeroconf discovery."""
        _LOGGER.info("🔍 Zeroconf discovery triggered for WiiM integration")
        _LOGGER.debug("Zeroconf discovery received: %s", discovery_info)
        _LOGGER.debug("Zeroconf host: %s", getattr(discovery_info, "host", "N/A"))
        _LOGGER.debug("Zeroconf port: %s", getattr(discovery_info, "port", "N/A"))
        _LOGGER.debug("Zeroconf type: %s", getattr(discovery_info, "type", "N/A"))
        _LOGGER.debug("Zeroconf name: %s", getattr(discovery_info, "name", "N/A"))
        _LOGGER.debug("Zeroconf properties: %s", getattr(discovery_info, "properties", {}))

        # Extract host from the discovery info
        host = discovery_info.host
        if not host:
            _LOGGER.warning("❌ No host found in Zeroconf discovery info")
            return self.async_abort(reason="no_host")

        # WiiM devices typically use HTTPS (443) or HTTP (80)
        # Only append port if it's not the default HTTP/HTTPS ports
        if discovery_info.port and discovery_info.port not in (80, 443):
            host = f"{host}:{discovery_info.port}"

        self._host = host
        _LOGGER.info("✅ Discovered WiiM device via Zeroconf at %s (port: %s)", host, discovery_info.port)

        try:
            # Validate the device and get details
            _LOGGER.debug("🔗 Attempting to validate discovered device at %s", host)
            device_name, device_uuid = await _validate_and_get_device_details(host)

            await self.async_set_unique_id(device_uuid)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: host},
                reload_on_update=True,
            )

            # Show confirmation form to user
            self.context["title_placeholders"] = {"name": device_name}
            _LOGGER.info("🎉 Zeroconf discovery successful for %s (%s)", device_name, host)
            return await self.async_step_discovery_confirm()

        except (ConfigEntryNotReady, WiiMError) as err:
            _LOGGER.warning("❌ Failed to validate Zeroconf discovered device at %s: %s", host, err)
            return self.async_abort(reason="cannot_connect")

    async def async_step_discovery_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle user confirmation of discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Re-validate to get fresh device details
                device_name, device_uuid = await _validate_and_get_device_details(self._host)

                _LOGGER.info(
                    "Confirmed setup of discovered WiiM device '%s' (UUID: %s) at %s",
                    device_name,
                    device_uuid,
                    self._host,
                )
                return self.async_create_entry(
                    title=device_name,
                    data={CONF_HOST: self._host, "uuid": device_uuid},
                )

            except ConfigEntryNotReady:
                _LOGGER.warning("Connection to discovered WiiM device at %s failed during confirmation", self._host)
                errors["base"] = "cannot_connect"
            except WiiMError as err:
                _LOGGER.warning("API error confirming discovered WiiM device at %s: %s", self._host, err)
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error confirming discovered WiiM device at %s", self._host)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": self._host},
            errors=errors,
        )


class WiiMOptionsFlow(config_entries.OptionsFlow):
    """Manages the options flow for an existing WiiM configuration entry."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize the WiiM options flow."""
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options for the WiiM integration."""
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
        # Convert volume step from decimal (internal) to percentage (UI)
        volume_step_percent = int(current_volume_step_decimal * 100)

        current_maintenance_buttons = self.entry.options.get(
            CONF_ENABLE_MAINTENANCE_BUTTONS,
            True,  # Default enabled
        )
        current_diagnostic_entities = self.entry.options.get(
            CONF_ENABLE_DIAGNOSTIC_ENTITIES,
            False,  # Default disabled
        )
        current_debug_logging = self.entry.options.get(CONF_DEBUG_LOGGING, False)  # Default disabled

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_VOLUME_STEP_PERCENT,
                    default=volume_step_percent,
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
                vol.Optional(
                    CONF_ENABLE_MAINTENANCE_BUTTONS,
                    default=current_maintenance_buttons,
                ): bool,
                vol.Optional(
                    CONF_ENABLE_DIAGNOSTIC_ENTITIES,
                    default=current_diagnostic_entities,
                ): bool,
                vol.Optional(
                    CONF_DEBUG_LOGGING,
                    default=current_debug_logging,
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
