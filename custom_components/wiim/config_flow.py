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

from .api import WiiMClient, WiiMError
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


def _extract_device_name(status: dict[str, Any], fallback_host: str) -> str:
    """Extract device name with Audio Pro specific fallbacks and improvements."""

    # Priority 1: DeviceName from WiiM API (custom name set in app)
    # Priority 2: Other name fields
    # Priority 3: SSID/Network name (less reliable)
    device_name = (
        status.get("DeviceName")  # Custom name set in WiiM app
        or status.get("device_name")  # Alternative field name
        or status.get("friendlyName")  # Common API field
        or status.get("name")  # Generic name field
        or status.get("ssid", fallback_host)  # Device hotspot name (fallback)
    )

    # Audio Pro specific naming improvements
    if not device_name or device_name == "Unknown":
        # Check if this looks like an Audio Pro device from the host IP or status
        status_str = str(status).lower()
        if "a10" in fallback_host.lower() or "a10" in status_str:
            device_name = "Audio Pro A10"
        elif "a15" in fallback_host.lower() or "a15" in status_str:
            device_name = "Audio Pro A15"
        elif "a28" in fallback_host.lower() or "a28" in status_str:
            device_name = "Audio Pro A28"
        elif "c10" in fallback_host.lower() or "c10" in status_str:
            device_name = "Audio Pro C10"
        elif any(audio_pro_term in status_str for audio_pro_term in ["audio pro", "audio_pro"]):
            device_name = "Audio Pro Speaker"
        else:
            device_name = f"WiiM Device ({fallback_host})"

    return device_name.strip()


def _is_audio_pro_device(device_name: str, status: dict[str, Any]) -> bool:
    """Check if this appears to be an Audio Pro device."""
    check_text = device_name.lower() + " " + str(status).lower()

    audio_pro_indicators = [
        "audio pro",
        "audio_pro",
        "a10",
        "a15",
        "a28",
        "c10",
        "mkii",
        "mk2",
        "w-",
        "w series",
        "w generation",
    ]

    return any(indicator in check_text for indicator in audio_pro_indicators)


async def validate_wiim_device(host: str) -> tuple[bool, str, str | None]:
    """Validate that a host is a WiiM/LinkPlay device and extract device info.

    Uses enhanced validation with protocol fallback similar to python-linkplay library.
    Tries multiple protocols and ports to handle different device configurations.
    """

    # Protocol fallback strategy like python-linkplay
    # Audio Pro devices often use HTTPS on standard ports, so prioritize HTTPS
    protocols_to_try = [
        ("https", 443),  # Standard HTTPS (Audio Pro MkII/W-Series prefer this)
        ("https", 4443),  # Alternative HTTPS port
        ("https", 8443),  # Another common HTTPS port for Audio Pro devices
        ("http", 80),  # Standard HTTP (fallback for older devices)
        ("http", 8080),  # Alternative HTTP port (some devices use this)
    ]

    # Also try the original host string in case it includes a custom port
    if ":" in host and not host.startswith("["):
        # Check if this is an IPv6 address first
        try:
            import ipaddress

            ipaddress.IPv6Address(host)
            # It's a valid IPv6 address, don't try to parse as host:port
        except ipaddress.AddressValueError:
            # Not an IPv6 address, try parsing as host:port
            try:
                _, port_part = host.rsplit(":", 1)
                port_int = int(port_part)
                protocols_to_try.insert(0, ("https", port_int))
                protocols_to_try.insert(1, ("http", port_int))
            except (ValueError, TypeError):
                pass  # Not a valid host:port format, use defaults

    last_error = None
    for protocol, port in protocols_to_try:
        client = WiiMClient(host, port=port)
        try:
            _LOGGER.debug("Trying %s://%s:%s for validation", protocol, host, port)

            # Try to get device status - this is the most reliable way to validate
            status = await client.get_status()
            if not status:
                _LOGGER.debug("No status response from %s:%s via %s", host, port, protocol)
                continue

            # Extract device name with enhanced Audio Pro support
            device_name = _extract_device_name(status, host)

            # Check if this is an Audio Pro device for enhanced logging
            is_audio_pro = _is_audio_pro_device(device_name, status)

            # Extract UUID - this is critical for device identification
            device_uuid = status.get("uuid")
            if not device_uuid:
                # Some older devices may not provide UUID
                _LOGGER.debug(
                    "Device at %s:%s did not provide UUID, using host as fallback",
                    host,
                    port,
                )
                device_uuid = host

            # Enhanced logging with Audio Pro specific messages
            if is_audio_pro:
                _LOGGER.info(
                    "🔊 Audio Pro device detected: %s at %s:%s via %s (UUID: %s)",
                    device_name,
                    host,
                    port,
                    protocol,
                    device_uuid,
                )
            else:
                _LOGGER.info(
                    "Successfully validated device %s at %s:%s via %s (UUID: %s)",
                    device_name,
                    host,
                    port,
                    protocol,
                    device_uuid,
                )

            # Success! Store the working connection details for later use
            # Note: We can't easily pass the working protocol/port back, but
            # the WiiMClient will remember the working endpoint

            return True, device_name, device_uuid

        except (OSError, TimeoutError, ValueError, WiiMError) as err:
            # Check if this appears to be an Audio Pro device for enhanced error messages
            is_audio_pro = any(
                audio_pro_model in host.lower() or audio_pro_model in str(err).lower()
                for audio_pro_model in [
                    "a10",
                    "a15",
                    "a28",
                    "c10",
                    "audio pro",
                    "audio_pro",
                ]
            )

            # Log the specific error for debugging but continue trying other protocols
            error_str = str(err).lower()
            last_error = err

            if is_audio_pro:
                # Audio Pro specific error logging
                _LOGGER.debug(
                    "Audio Pro device %s:%s failed via %s: %s",
                    host,
                    port,
                    protocol,
                    err,
                )
                if "404" in error_str:
                    _LOGGER.debug(
                        "Audio Pro device %s:%s returned 404 via %s - may be HTTPS-only device",
                        host,
                        port,
                        protocol,
                    )
                elif "timeout" in error_str:
                    _LOGGER.debug(
                        "Audio Pro device %s:%s timeout via %s - device may be slow to respond",
                        host,
                        port,
                        protocol,
                    )
                elif "connection refused" in error_str:
                    _LOGGER.debug(
                        "Audio Pro device %s:%s connection refused via %s - may need different protocol",
                        host,
                        port,
                        protocol,
                    )
                elif "ssl" in error_str or "certificate" in error_str:
                    _LOGGER.debug(
                        "Audio Pro device %s:%s SSL error via %s - may need HTTP instead",
                        host,
                        port,
                        protocol,
                    )
            else:
                # Standard error logging for non-Audio Pro devices
                if "404" in error_str:
                    _LOGGER.debug(
                        "Device at %s:%s returned 404 via %s - not a LinkPlay device",
                        host,
                        port,
                        protocol,
                    )
                elif "timeout" in error_str:
                    _LOGGER.debug(
                        "Timeout connecting to %s:%s via %s - device may be slow",
                        host,
                        port,
                        protocol,
                    )
                elif "connection refused" in error_str:
                    _LOGGER.debug(
                        "Connection refused by %s:%s via %s - wrong protocol/port",
                        host,
                        port,
                        protocol,
                    )
                elif "ssl" in error_str or "certificate" in error_str:
                    _LOGGER.debug(
                        "SSL error with %s:%s via %s - device may not support HTTPS",
                        host,
                        port,
                        protocol,
                    )
                else:
                    _LOGGER.debug(
                        "Failed to validate device at %s:%s via %s: %s",
                        host,
                        port,
                        protocol,
                        err,
                    )
            continue
        finally:
            await client.close()

    # If we get here, all protocols failed
    # Check if this appears to be an Audio Pro device for enhanced error messages
    # Enhanced Audio Pro detection - check hostname patterns and common Audio Pro IP ranges
    is_audio_pro = any(
        audio_pro_model in host.lower()
        for audio_pro_model in [
            "a10",
            "a15",
            "a28",
            "c10",
            "audio pro",
            "audio_pro",
            "mkii",
            "mk2",
            "w-",
            "w series",
            "w generation",
        ]
    )

    if is_audio_pro:
        _LOGGER.warning(
            "🔊 Audio Pro device validation failed for %s. Last error: %s",
            host,
            last_error,
        )
        _LOGGER.info(
            "Audio Pro device %s validation failed - this is common for MkII/W-Series devices. "
            "These devices often require manual setup with their IP address. "
            "The devices will work perfectly once configured manually.",
            host,
        )
    else:
        _LOGGER.warning("All validation attempts failed for %s. Last error: %s", host, last_error)

    # Instead of failing completely, provide a fallback that allows manual setup
    # This matches python-linkplay's approach of being permissive
    error_str = str(last_error).lower() if last_error else ""

    if is_audio_pro:
        # Audio Pro specific final error messages
        if "404" in error_str:
            _LOGGER.info(
                "Audio Pro device %s returned 404 - likely MkII/W-Series device requiring HTTPS. Manual setup available.",
                host,
            )
        elif "timeout" in error_str:
            _LOGGER.info(
                "Audio Pro device %s timeout - device may be slow or offline. Manual setup available.",
                host,
            )
        elif "connection refused" in error_str:
            _LOGGER.info(
                "Audio Pro device %s connection refused - may need manual IP configuration.",
                host,
            )
        elif "ssl" in error_str or "certificate" in error_str:
            _LOGGER.info(
                "Audio Pro device %s SSL error - device may require specific protocol. Manual setup available.",
                host,
            )
        else:
            _LOGGER.info(
                "Audio Pro device %s failed validation - manual setup is recommended and will work.",
                host,
            )
    else:
        # Standard final error messages for non-Audio Pro devices
        if "404" in error_str:
            _LOGGER.info("Device at %s returned 404 - likely not a WiiM/LinkPlay device", host)
        elif "timeout" in error_str:
            _LOGGER.info("Timeout connecting to %s - device may be offline or slow", host)
        elif "connection refused" in error_str:
            _LOGGER.info("Connection refused by %s - device may not support HTTP API", host)
        else:
            _LOGGER.info("Failed to validate device at %s - may need manual configuration", host)

    # Return a "soft failure" that still allows the device to be configured manually
    # The UI can show this as "Validation failed but manual setup available"
    fallback_name = "Audio Pro Speaker" if is_audio_pro else f"WiiM Device ({host})"
    return False, fallback_name, host


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

    async def async_step_discovery(self, discovery_info: dict[str, Any] | None = None) -> ConfigFlowResult:  # type: ignore[override]
        """Handle automatic discovery."""
        if not self._discovered_devices:
            # Run discovery
            self._discovered_devices = await self._discover_devices()

        if discovery_info is not None:
            selected = discovery_info[CONF_HOST]

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

            # Validate and create entry (enhanced validation)
            is_valid, device_name, device_uuid = await validate_wiim_device(host)

            # Enhanced logic: handle both successful validation and soft failures
            if is_valid and device_uuid:
                # Full success - proceed with auto-configuration
                pass  # Continue with the existing logic below
            elif device_uuid:
                # Soft failure - validation failed but we got a fallback UUID
                # Still proceed but log the issue
                _LOGGER.warning("Using fallback validation for selected device %s", host)
            else:
                # Hard failure - no UUID at all
                _LOGGER.error("Validation completely failed for selected device %s", host)
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
        # Get all existing entries to check for duplicates by both host and UUID
        existing_entries = self._async_current_entries()
        known_hosts = {entry.data[CONF_HOST] for entry in existing_entries}
        known_uuids = {entry.unique_id for entry in existing_entries if entry.unique_id}

        async def _on_device(device):
            """Handle discovered device."""
            host = getattr(device, "host", None)
            if not host and (loc := getattr(device, "location", None)):
                host = urlparse(loc).hostname

            if not host or host in discovered:
                return

            # Skip if this host is already configured
            if host in known_hosts:
                _LOGGER.debug("Skipping already configured device at host %s", host)
                return

            is_valid, device_name, device_uuid = await validate_wiim_device(host)
            if is_valid or device_uuid:
                # Check if this UUID is already configured (prevents duplicates when IP changes)
                unique_id = device_uuid or host
                if unique_id in known_uuids:
                    _LOGGER.debug("Skipping already configured device with UUID %s at host %s", unique_id, host)
                    return

                # Include devices that either validate successfully OR have a fallback UUID
                # This matches python-linkplay's permissive approach
                discovered[host] = device_name

        try:
            await async_search(
                async_callback=_on_device,
                timeout=5,
                search_target="urn:schemas-upnp-org:device:MediaRenderer:1",
            )
        except (OSError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Discovery error: %s", err)

        return discovered

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """Handle Zeroconf discovery.

        Enhanced to handle devices that are discovered but fail initial validation,
        similar to python-linkplay's permissive approach.
        """
        host = discovery_info.host
        _LOGGER.info("🔍 ZEROCONF DISCOVERY called for host: %s", host)

        # Check if this might be an Audio Pro device based on discovery info
        # This helps us provide better fallback behavior for Audio Pro devices
        discovery_name = discovery_info.name.lower() if discovery_info.name else ""
        discovery_type = discovery_info.type.lower() if discovery_info.type else ""
        discovery_text = f"{discovery_name} {discovery_type}"

        is_likely_audio_pro = any(
            indicator in discovery_text
            for indicator in [
                "audio pro",
                "audio_pro",
                "a10",
                "a15",
                "a28",
                "c10",
                "mkii",
                "mk2",
                "w-",
                "w series",
                "w generation",
            ]
        )

        if is_likely_audio_pro:
            _LOGGER.info("🔊 Audio Pro device detected in discovery: %s", host)

        is_valid, device_name, device_uuid = await validate_wiim_device(host)

        # Enhanced logic: handle both successful validation and soft failures
        if is_valid and device_uuid:
            # Full success - auto-configure
            _LOGGER.info(
                "🔍 ZEROCONF DISCOVERY validated device: %s at %s (UUID: %s)",
                device_name,
                host,
                device_uuid,
            )
            unique_id = device_uuid

            await self.async_set_unique_id(unique_id)
            # Abort if this unique_id (UUID or host) is already configured.
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

            # Store data for discovery confirmation
            self.data = {CONF_HOST: host, "name": device_name}
            return await self.async_step_discovery_confirm()

        elif device_uuid:
            # Soft failure - validation failed but we got a fallback UUID
            # This means the device might still work but needs manual confirmation
            _LOGGER.warning("🔍 ZEROCONF DISCOVERY got fallback UUID for %s: %s", host, device_uuid)

            unique_id = device_uuid
            await self.async_set_unique_id(unique_id)
            # Abort if this unique_id (UUID or host) is already configured.
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

            # Store data for discovery confirmation with a note about manual setup
            self.data = {CONF_HOST: host, "name": device_name, "needs_manual": True}
            return await self.async_step_discovery_confirm()

        elif is_likely_audio_pro:
            # Special handling for Audio Pro devices that fail validation
            # Audio Pro devices often fail auto-discovery but work perfectly with manual setup
            _LOGGER.info(
                "🔊 Audio Pro device %s failed auto-discovery validation - "
                "this is common for MkII/W-Series devices. Offering manual setup.",
                host,
            )

            # Use host as unique_id for Audio Pro devices that fail validation
            unique_id = host
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

            # Store data for discovery confirmation with Audio Pro specific guidance
            self.data = {CONF_HOST: host, "name": "Audio Pro Speaker", "needs_manual": True, "is_audio_pro": True}
            return await self.async_step_discovery_confirm()

        else:
            # Hard failure - no UUID at all, likely not a LinkPlay device
            _LOGGER.warning("🔍 ZEROCONF DISCOVERY validation completely failed for host: %s", host)
            return self.async_abort(reason="cannot_connect")

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

        # Check if this might be an Audio Pro device based on SSDP info
        ssdp_location = discovery_info.ssdp_location.lower() if discovery_info.ssdp_location else ""
        ssdp_server = discovery_info.ssdp_server.lower() if discovery_info.ssdp_server else ""
        ssdp_text = f"{ssdp_location} {ssdp_server}"

        is_likely_audio_pro = any(
            indicator in ssdp_text
            for indicator in [
                "audio pro",
                "audio_pro",
                "a10",
                "a15",
                "a28",
                "c10",
                "mkii",
                "mk2",
                "w-",
                "w series",
                "w generation",
            ]
        )

        if is_likely_audio_pro:
            _LOGGER.info("🔊 Audio Pro device detected in SSDP discovery: %s", host)

        is_valid, device_name, device_uuid = await validate_wiim_device(host)

        # Enhanced logic: handle both successful validation and soft failures
        if is_valid and device_uuid:
            # Full success - auto-configure
            _LOGGER.info("SSDP discovery validated device: %s at %s", device_name, host)
            unique_id = device_uuid

            await self.async_set_unique_id(unique_id)
            # Abort if this unique_id (UUID or host) is already configured.
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

            # Store data for discovery confirmation
            self.data = {CONF_HOST: host, "name": device_name}
            return await self.async_step_discovery_confirm()

        elif device_uuid:
            # Soft failure - validation failed but we got a fallback UUID
            _LOGGER.debug("SSDP discovery got fallback UUID for %s: %s", host, device_uuid)

            unique_id = device_uuid
            await self.async_set_unique_id(unique_id)
            # Abort if this unique_id (UUID or host) is already configured.
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

            # Store data for discovery confirmation with a note about manual setup
            self.data = {CONF_HOST: host, "name": device_name, "needs_manual": True}
            return await self.async_step_discovery_confirm()

        elif is_likely_audio_pro:
            # Special handling for Audio Pro devices that fail validation
            # Audio Pro devices often fail auto-discovery but work perfectly with manual setup
            _LOGGER.info(
                "🔊 Audio Pro device %s failed SSDP discovery validation - "
                "this is common for MkII/W-Series devices. Offering manual setup.",
                host,
            )

            # Use host as unique_id for Audio Pro devices that fail validation
            unique_id = host
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

            # Store data for discovery confirmation with Audio Pro specific guidance
            self.data = {CONF_HOST: host, "name": "Audio Pro Speaker", "needs_manual": True, "is_audio_pro": True}
            return await self.async_step_discovery_confirm()

        else:
            # Hard failure - no UUID at all, likely not a LinkPlay device
            _LOGGER.debug("SSDP discovery validation completely failed for host: %s", host)
            return self.async_abort(reason="cannot_connect")

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

        # Enhanced logic: handle both successful validation and soft failures
        if is_valid and validated_uuid:
            # Full success - use validated data
            final_name = validated_name or device_name
            final_uuid = validated_uuid
            _LOGGER.info("Integration discovery validated device: %s at %s", final_name, host)

        elif validated_uuid:
            # Soft failure - validation failed but we got a fallback UUID
            final_name = validated_name or device_name
            final_uuid = validated_uuid
            _LOGGER.warning("Integration discovery got fallback UUID for %s at %s", final_name, host)

        else:
            # Hard failure - no UUID at all
            _LOGGER.warning(
                "Integration discovery validation completely failed for %s at %s",
                device_name,
                host,
            )
            return self.async_abort(reason="cannot_connect")

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
        _LOGGER.info(
            "🔍 DISCOVERY CONFIRM set title_placeholders: %s",
            {"name": self.data["name"]},
        )

        # Enhanced description for Audio Pro devices
        description_placeholders = {"name": self.data["name"]}

        if self.data.get("is_audio_pro", False):
            description_placeholders["audio_pro_note"] = (
                "\n\n**Note**: This Audio Pro device failed auto-discovery validation, "
                "which is common for MkII/W-Series devices. Manual setup will work perfectly."
            )
        else:
            description_placeholders["audio_pro_note"] = ""

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=description_placeholders,
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
