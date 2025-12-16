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
from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pywiim.discovery import DiscoveredDevice, discover_devices, validate_device

from .const import (
    CONF_ENABLE_MAINTENANCE_BUTTONS,
    CONF_VOLUME_STEP,
    CONF_VOLUME_STEP_PERCENT,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class WiiMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle WiiM config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._discovered_devices: list[DiscoveredDevice] = []
        self.data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> WiiMOptionsFlow:
        """Return the options flow."""
        return WiiMOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:  # type: ignore[override]
        """Handle user-initiated setup - go directly to manual entry for speed.

        Discovery is still triggered via SSDP/Zeroconf handlers when devices broadcast,
        so we skip the slow network scan here and let users enter the IP directly.
        This reduces the "Add Integration" click delay from 5-10 seconds to instant.
        """
        # Skip slow network discovery - go directly to manual IP entry
        # Users can enter their device IP immediately without waiting
        return await self.async_step_manual()

    async def async_step_discovery(self, discovery_info: dict[str, Any] | None = None) -> ConfigFlowResult:  # type: ignore[override]
        """Handle automatic discovery."""
        if not self._discovered_devices:
            # Run discovery
            self._discovered_devices = await self._discover_devices()

        if discovery_info is not None:
            selected = discovery_info[CONF_HOST]

            if selected == "manual_entry":
                return await self.async_step_manual()

            # Find device from discovered list
            device = None
            for dev in self._discovered_devices:
                display_name = f"{dev.name or f'WiiM Device ({dev.ip})'} ({dev.ip})"
                if display_name == selected:
                    device = dev
                    break

            if not device:
                return await self.async_step_manual()

            device_name = device.name or f"WiiM Device ({device.ip})"
            device_uuid = device.uuid or device.ip
            unique_id = device_uuid

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Trigger slave discovery in background
            self.hass.async_create_task(self._discover_slaves(device.ip))

            return self.async_create_entry(title=device_name, data={CONF_HOST: device.ip})

        if self._discovered_devices:
            # Show discovered devices
            options = [f"{dev.name or f'WiiM Device ({dev.ip})'} ({dev.ip})" for dev in self._discovered_devices]
            options.append("Enter IP manually")

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
        """Handle manual IP entry."""
        if user_input is not None:
            host = user_input[CONF_HOST].strip()

            discovered_device = DiscoveredDevice(ip=host)
            validated_device = await validate_device(discovered_device)

            device_name = validated_device.name or f"WiiM Device ({host})"
            device_uuid = validated_device.uuid or host
            unique_id = device_uuid

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Trigger slave discovery in background
            self.hass.async_create_task(self._discover_slaves(host))

            return self.async_create_entry(title=device_name, data={CONF_HOST: host})

        schema = vol.Schema({vol.Required(CONF_HOST, description="IP address of your WiiM device"): str})

        return self.async_show_form(
            step_id="manual",
            data_schema=schema,
            description_placeholders={"example_ip": "192.168.1.100"},
        )

    async def _discover_devices(self) -> list[DiscoveredDevice]:
        """Discover WiiM devices using pywiim's discover_devices."""
        existing_entries = self._async_current_entries()
        known_hosts = {entry.data[CONF_HOST] for entry in existing_entries}
        known_uuids = {entry.unique_id for entry in existing_entries if entry.unique_id}

        devices = await discover_devices(validate=True)
        discovered = []
        for device in devices:
            if not device.ip:
                continue
            if device.ip in known_hosts:
                continue
            unique_id = device.uuid or device.ip
            if unique_id in known_uuids:
                continue
            discovered.append(device)

        return discovered

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """Handle Zeroconf discovery using pywiim's discovery."""
        host = discovery_info.host
        _LOGGER.debug("Zeroconf discovery for host: %s", host)

        # Check if this IP is already configured before validation
        # This prevents already-configured devices from appearing in discovered list
        existing_entries = self._async_current_entries()
        for entry in existing_entries:
            if entry.data.get(CONF_HOST) == host:
                return self.async_abort(reason="already_configured")

        # Validate device to get UUID
        discovered_device = DiscoveredDevice(ip=host)
        validated_device = await validate_device(discovered_device)

        device_name = validated_device.name or f"WiiM Device ({host})"
        device_uuid = validated_device.uuid or host
        unique_id = device_uuid

        # Set unique_id and abort if already configured by UUID
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self.data = {CONF_HOST: host, "name": device_name}
        return await self.async_step_discovery_confirm()

    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> ConfigFlowResult:
        """Handle SSDP discovery using pywiim's discovery."""
        _LOGGER.debug("SSDP discovery from: %s", discovery_info.ssdp_location)

        if not discovery_info.ssdp_location:
            return self.async_abort(reason="no_host")

        host = urlparse(discovery_info.ssdp_location).hostname
        if not host:
            return self.async_abort(reason="no_host")

        # Check if this IP is already configured before validation
        # This prevents already-configured devices from appearing in discovered list
        existing_entries = self._async_current_entries()
        for entry in existing_entries:
            if entry.data.get(CONF_HOST) == host:
                return self.async_abort(reason="already_configured")

        # HTTP validation: Call device HTTP API to confirm it's actually a WiiM/LinkPlay device
        # validate_device makes HTTP calls to the device to verify it responds as a LinkPlay/WiiM device
        discovered_device = DiscoveredDevice(ip=host)
        try:
            validated_device = await validate_device(discovered_device)
        except Exception as err:
            # validate_device failed - device is not a WiiM/LinkPlay device or not reachable
            # Silently abort (following python-linkplay pattern of skipping invalid devices)
            _LOGGER.debug(
                "Device validation failed for %s (not a WiiM/LinkPlay device): %s",
                host,
                err,
            )
            return self.async_abort(reason="not_wiim_device")

        device_name = validated_device.name or f"WiiM Device ({host})"
        device_uuid = validated_device.uuid or host
        unique_id = device_uuid

        # Set unique_id and abort if already configured by UUID
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self.data = {
            CONF_HOST: host,
            "name": device_name,
            "ssdp_info": {"location": discovery_info.ssdp_location} if discovery_info.ssdp_location else {},
        }
        return await self.async_step_discovery_confirm()

    async def async_step_integration_discovery(self, discovery_info: dict[str, Any]) -> ConfigFlowResult:
        """Handle integration discovery using pywiim's discovery."""
        host = discovery_info.get(CONF_HOST)
        device_name = discovery_info.get("device_name", "Unknown Device")
        device_uuid = discovery_info.get("device_uuid")
        discovery_source = discovery_info.get("discovery_source")

        if discovery_source == "missing_device":
            return await self.async_step_missing_device()

        if not host:
            return self.async_abort(reason="no_host")

        # Check if this IP is already configured before validation
        # This prevents already-configured devices from appearing in discovered list
        existing_entries = self._async_current_entries()
        for entry in existing_entries:
            if entry.data.get(CONF_HOST) == host:
                return self.async_abort(reason="already_configured")

        discovered_device = DiscoveredDevice(ip=host)
        validated_device = await validate_device(discovered_device)

        final_name = validated_device.name or device_name
        final_uuid = validated_device.uuid or device_uuid or host
        unique_id = final_uuid

        # Set unique_id and abort if already configured by UUID
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self.data = {CONF_HOST: host, "name": final_name}
        return await self.async_step_discovery_confirm()

    async def async_step_missing_device(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle missing device discovery - user provides IP for known UUID."""
        errors = {}
        device_uuid = self.context.get("unique_id")
        device_name = (self.data or {}).get("device_name", f"Device {device_uuid[:8] if device_uuid else 'Unknown'}...")

        if user_input is not None:
            host = user_input[CONF_HOST].strip()

            discovered_device = DiscoveredDevice(ip=host)
            validated_device = await validate_device(discovered_device)

            if validated_device.uuid != device_uuid:
                errors["base"] = "uuid_mismatch"
                _LOGGER.warning("UUID mismatch: expected %s, got %s", device_uuid, validated_device.uuid)
            else:
                device_name = validated_device.name or f"WiiM Device ({host})"
                await self.async_set_unique_id(device_uuid)
                self._abort_if_unique_id_configured()

                # Trigger slave discovery in background
                self.hass.async_create_task(self._discover_slaves(host))

                return self.async_create_entry(title=device_name, data={CONF_HOST: host})

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
        # Auto-create entry during onboarding or when user confirms
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            # Preserve SSDP info for UPnP subscriptions (Samsung/DLNA pattern)
            entry_data = {CONF_HOST: self.data[CONF_HOST]}
            if "ssdp_info" in self.data:
                entry_data["ssdp_info"] = self.data["ssdp_info"]

            # Trigger slave discovery in background
            self.hass.async_create_task(self._discover_slaves(self.data[CONF_HOST]))

            return self.async_create_entry(
                title=self.data["name"],
                data=entry_data,
            )

        # Show confirmation form only after onboarding is complete
        # Set title placeholders here where the UI actually processes them
        self.context["title_placeholders"] = {"name": self.data["name"]}
        _LOGGER.info(
            "🔍 DISCOVERY CONFIRM set title_placeholders: %s",
            {"name": self.data["name"]},
        )

        description_placeholders = {"name": self.data["name"]}

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=description_placeholders,
        )

    def is_matching(self, other_flow: config_entries.ConfigFlow) -> bool:
        """Check if two flows are matching."""
        return False

    async def _discover_slaves(self, host: str) -> None:
        """Discover and add any slave devices attached to a master.

        When a master device is added, check if it has slaves and automatically
        trigger discovery flows for them (without unjoining the group).
        """
        try:
            from homeassistant.helpers.aiohttp_client import async_get_clientsession
            from pywiim import WiiMClient

            # Create a temporary client to check for slaves
            # Let pywiim probe automatically - we don't have endpoint cached here
            session = async_get_clientsession(self.hass)
            client = WiiMClient(host=host, session=session)

            # Get group info to see if this device is a master with slaves
            group_info = await client.get_device_group_info()

            if not group_info:
                return

            # Check if this is a master with slaves
            # DeviceGroupInfo is a Pydantic model, access attributes directly
            if group_info.role != "master":
                return

            # slave_hosts is a list of IP addresses
            slave_hosts = group_info.slave_hosts or []
            if not slave_hosts:
                return

            _LOGGER.info(
                "Master device at %s has %d slave(s), triggering discovery for them",
                host,
                len(slave_hosts),
            )

            # Check existing entries to avoid re-adding
            existing_entries = self._async_current_entries()
            known_hosts = {entry.data[CONF_HOST] for entry in existing_entries}

            # Trigger discovery for each slave
            for slave_ip in slave_hosts:
                if not slave_ip:
                    continue

                # Skip if already configured
                if slave_ip in known_hosts:
                    _LOGGER.debug("Slave %s already configured, skipping", slave_ip)
                    continue

                _LOGGER.info("Triggering discovery for slave: %s", slave_ip)

                # Trigger integration discovery for this slave
                # Note: We only have IP, UUID/name will be fetched during validation
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                        data={
                            CONF_HOST: slave_ip,
                            "device_name": f"WiiM Device ({slave_ip})",
                            "device_uuid": None,
                        },
                    )
                )

        except Exception as err:
            _LOGGER.debug("Failed to discover slaves for %s: %s", host, err)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reconfiguration initiated by the user."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()

            # Validate device at new IP address
            discovered_device = DiscoveredDevice(ip=host)
            try:
                validated_device = await validate_device(discovered_device)
            except Exception as err:
                _LOGGER.debug("Device validation failed for %s: %s", host, err)
                errors["base"] = "cannot_connect"
            else:
                # Verify it's the same device (same UUID)
                device_uuid = validated_device.uuid or host
                await self.async_set_unique_id(device_uuid)

                # Check if UUID matches the existing entry
                if reconfigure_entry.unique_id and device_uuid != reconfigure_entry.unique_id:
                    errors["base"] = "uuid_mismatch"
                    _LOGGER.warning(
                        "UUID mismatch during reconfiguration: expected %s, got %s",
                        reconfigure_entry.unique_id,
                        device_uuid,
                    )
                else:
                    # Update entry with new IP and reload
                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        data_updates={CONF_HOST: host},
                        reason="reconfigure_successful",
                    )

        # Show form with current IP pre-filled
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=reconfigure_entry.data.get(CONF_HOST),
                    description="IP address of your WiiM device",
                ): str
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "name": reconfigure_entry.title,
                "current_ip": reconfigure_entry.data.get(CONF_HOST, "Unknown"),
            },
        )


class WiiMOptionsFlow(config_entries.OptionsFlow):
    """Handle WiiM options."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle options flow."""
        try:
            if user_input is not None:
                options_data = {}

                # Volume step: convert from percentage (UI) to decimal (internal)
                if CONF_VOLUME_STEP_PERCENT in user_input:
                    options_data[CONF_VOLUME_STEP] = user_input[CONF_VOLUME_STEP_PERCENT] / 100.0

                # Feature toggles
                if CONF_ENABLE_MAINTENANCE_BUTTONS in user_input:
                    options_data[CONF_ENABLE_MAINTENANCE_BUTTONS] = user_input[CONF_ENABLE_MAINTENANCE_BUTTONS]

                return self.async_create_entry(title="", data=options_data)

            # Populate form with current or default values
            # Safely access entry options with fallbacks
            entry_options = getattr(self.entry, "options", {}) or {}
            current_volume_step_decimal = entry_options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
            volume_step_percent = int(current_volume_step_decimal * 100)

            current_maintenance_buttons = entry_options.get(CONF_ENABLE_MAINTENANCE_BUTTONS, False)

            schema = vol.Schema(
                {
                    vol.Optional(CONF_VOLUME_STEP_PERCENT, default=volume_step_percent): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=50)
                    ),
                    vol.Optional(CONF_ENABLE_MAINTENANCE_BUTTONS, default=current_maintenance_buttons): bool,
                }
            )

            return self.async_show_form(step_id="init", data_schema=schema)
        except Exception as err:
            _LOGGER.exception("Error in options flow: %s", err)
            # Return a form with error message
            return self.async_show_form(
                step_id="init",
                errors={"base": "unknown_error"},
                data_schema=vol.Schema({}),
            )
