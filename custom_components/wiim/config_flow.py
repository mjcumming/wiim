"""Config flow for the WiiM integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from aiohttp.client_exceptions import ClientError
from homeassistant import config_entries
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
    client = WiiMClient(host)
    try:
        # Use getStatusEx which returns comprehensive device info including UUID
        device_details = await client.get_status()  # This calls getStatusEx endpoint

        # Extract the actual UUID - this should be a proper UUID from the device
        device_uuid = device_details.get("uuid")
        if not device_uuid:
            # Fallback to MAC if UUID not available
            mac_address = device_details.get("MAC") or device_details.get("mac_address")
            if mac_address:
                device_uuid = mac_address.lower().replace(":", "")
                _LOGGER.info("UUID not found, using MAC address %s as unique ID for %s", device_uuid, host)
            else:
                raise WiiMError(f"Could not retrieve UUID or MAC address for {host}")

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
                except Exception as e:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected error configuring WiiM device at %s", host)
                    errors["base"] = "unknown"  # Use a translation key
        # Show the form to the user
        schema = vol.Schema({vol.Required(CONF_HOST, default=self._host or ""): str})
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
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
