"""Config flow to configure WiiM component.

Restored full functionality with proper device naming and validation.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
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
    CONF_IDLE_UPDATE_RATE,
    CONF_PLAYING_UPDATE_RATE,
    CONF_VOLUME_STEP,
    CONF_VOLUME_STEP_PERCENT,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_and_get_device_name(host: str) -> str:
    """Validate device and get proper device name."""
    client = WiiMClient(host, port=443)
    try:
        # Basic validation
        await client.get_player_status()

        # Get device name from getStatusEx (main status endpoint)
        try:
            status_info = await client.get_status()
            device_name = status_info.get("DeviceName") or status_info.get("device_name")
            if device_name:
                return device_name
        except WiiMError:
            pass

        # Fallback to get_device_info
        try:
            device_info = await client.get_device_info()
            device_name = device_info.get("DeviceName") or device_info.get("device_name")
            if device_name:
                return device_name
        except WiiMError:
            pass

        # Final fallback
        return f"WiiM {host}"

    finally:
        await client.close()


class WiiMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a WiiM config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up instance."""
        self._host: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return WiiMOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if not host:
                errors["base"] = "no_host"
            else:
                try:
                    # Validate and get proper device name
                    device_name = await _validate_and_get_device_name(host)

                    # Set unique ID and check for duplicates
                    unique_id = host
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    _LOGGER.info("Successfully connected to WiiM device '%s' at %s", device_name, host)
                    return self.async_create_entry(title=device_name, data={CONF_HOST: host})

                except ConfigEntryNotReady:
                    _LOGGER.warning("Failed to connect to %s", host)
                    errors["base"] = "cannot_connect"
                except Exception as e:
                    _LOGGER.error("Unexpected error during config for %s: %s", host, e)
                    errors["base"] = "unknown"

        # Show form
        schema = vol.Schema({vol.Required(CONF_HOST, default=""): str})
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )


class WiiMOptionsFlow(config_entries.OptionsFlow):
    """Handle WiiM options."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Init options flow."""
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            # Convert user-friendly names back to internal names
            options_data = {}

            # NEW: Defensive two-state polling configuration
            if CONF_PLAYING_UPDATE_RATE in user_input:
                options_data[CONF_PLAYING_UPDATE_RATE] = user_input[CONF_PLAYING_UPDATE_RATE]

            if CONF_IDLE_UPDATE_RATE in user_input:
                options_data[CONF_IDLE_UPDATE_RATE] = user_input[CONF_IDLE_UPDATE_RATE]

            # Convert volume step from percentage back to decimal
            if CONF_VOLUME_STEP_PERCENT in user_input:
                options_data[CONF_VOLUME_STEP] = user_input[CONF_VOLUME_STEP_PERCENT] / 100.0

            # Map debug logging option
            if CONF_DEBUG_LOGGING in user_input:
                options_data["debug_logging"] = user_input[CONF_DEBUG_LOGGING]

            # Essential entity filtering options only
            if CONF_ENABLE_DIAGNOSTIC_ENTITIES in user_input:
                options_data[CONF_ENABLE_DIAGNOSTIC_ENTITIES] = user_input[CONF_ENABLE_DIAGNOSTIC_ENTITIES]

            if CONF_ENABLE_MAINTENANCE_BUTTONS in user_input:
                options_data[CONF_ENABLE_MAINTENANCE_BUTTONS] = user_input[CONF_ENABLE_MAINTENANCE_BUTTONS]

            return self.async_create_entry(title="", data=options_data)

        # Get current values and convert for display
        current_volume_step = self.entry.options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
        current_debug_logging = self.entry.options.get("debug_logging", False)

        # Defensive two-state polling options (CORE feature we just implemented)
        current_playing_rate = self.entry.options.get(CONF_PLAYING_UPDATE_RATE, 1)
        current_idle_rate = self.entry.options.get(CONF_IDLE_UPDATE_RATE, 5)

        # Essential entity filtering (keep minimal)
        current_maintenance_buttons = self.entry.options.get(CONF_ENABLE_MAINTENANCE_BUTTONS, True)
        current_diagnostic_entities = self.entry.options.get(CONF_ENABLE_DIAGNOSTIC_ENTITIES, False)

        # Convert volume step from decimal to percentage for user display
        volume_step_percent = int(current_volume_step * 100)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_PLAYING_UPDATE_RATE,
                    default=current_playing_rate,
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
                vol.Optional(
                    CONF_IDLE_UPDATE_RATE,
                    default=current_idle_rate,
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
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
