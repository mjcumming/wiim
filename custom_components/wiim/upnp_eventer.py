"""UPnP event handler for WiiM devices.

Follows Samsung/DLNA pattern using async_upnp_client (DmrDevice pattern).
See: /workspaces/core/homeassistant/components/dlna_dmr/media_player.py
and /workspaces/core/homeassistant/components/samsungtv/media_player.py

Reference implementation: dlna_dmr/media_player.py:388-391
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Any

from async_upnp_client.client import UpnpService, UpnpStateVariable
from async_upnp_client.exceptions import UpnpResponseError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .upnp_client import UpnpClient

_LOGGER = logging.getLogger(__name__)


class UpnpEventer:
    """Manage UPnP event subscriptions and process LastChange notifications.

    Reference pattern: dlna_dmr/media_player.py:388-391
    Uses DmrDevice.async_subscribe_services(auto_resubscribe=True) - handles renewals automatically.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        upnp_client: UpnpClient,
        state_manager: Any,  # WiiMState - will be defined in state.py
        device_uuid: str,
    ) -> None:
        """Initialize UPnP eventer."""
        self.hass = hass
        self.upnp_client = upnp_client
        self.state_manager = state_manager
        self.device_uuid = device_uuid

        # Event statistics (for diagnostics only - no health checking per DLNA DMR pattern)
        self._last_notify_ts: float | None = None
        self._event_count = 0

    async def start(
        self,
        callback_host: str | None = None,
        callback_port: int = 0,
    ) -> None:
        """Start event subscriptions (reference: dlna_dmr/media_player.py:388-391).

        Args:
            callback_host: Host IP for callback URL (auto-detect if None)
            callback_port: Port for callback (0 = ephemeral)
        """
        # Start notify server first (required before subscriptions)
        await self.upnp_client.start_notify_server(
            callback_host=callback_host,
            callback_port=callback_port,
        )

        # Reference pattern: dlna_dmr/media_player.py:388-391
        # ONE LINE: auto_resubscribe=True handles all renewals internally
        subscription_start_time = time.time()
        _LOGGER.info(
            "📨 Subscribing to UPnP services for %s (DmrDevice pattern with auto_resubscribe=True)",
            self.upnp_client.host,
        )

        try:
            # Log callback URL for diagnostics
            callback_url = getattr(self.upnp_client.notify_server, "callback_url", None)
            if callback_url:
                _LOGGER.info(
                    "   → Callback URL: %s (devices will send NOTIFY events to this URL)",
                    callback_url,
                )
                # Validate callback URL reachability
                server_host = getattr(self.upnp_client.notify_server, "host", "unknown")
                if (
                    server_host.startswith("172.")
                    or server_host.startswith("192.168.65")
                    or server_host == "0.0.0.0"
                ):
                    _LOGGER.error(
                        "   ⚠️  CRITICAL: Callback URL uses unreachable IP %s - devices on your LAN cannot reach this!",
                        server_host,
                    )
                    _LOGGER.error(
                        "      UPnP events will not arrive. Configure callback_host in integration options with your host's LAN IP.",
                    )
            else:
                _LOGGER.error(
                    "   ⚠️  CRITICAL: No callback URL available - UPnP events will NOT work!",
                )

            # Reference pattern: Set callback and subscribe - auto_resubscribe handles everything
            self.upnp_client._dmr_device.on_event = self._on_event
            await self.upnp_client._dmr_device.async_subscribe_services(
                auto_resubscribe=True
            )

            subscription_duration = time.time() - subscription_start_time
            _LOGGER.info(
                "✅ UPnP subscriptions established for %s (completed in %.2fs, auto_resubscribe=True handles renewals)",
                self.upnp_client.host,
                subscription_duration,
            )

        except UpnpResponseError as err:
            # Device rejected subscription - this is OK, we'll poll instead (reference pattern)
            subscription_duration = time.time() - subscription_start_time
            _LOGGER.debug(
                "Device rejected subscription for %s (after %.2fs): %r - will use polling",
                self.upnp_client.host,
                subscription_duration,
                err,
            )
            raise
        except Exception as err:  # noqa: BLE001
            subscription_duration = time.time() - subscription_start_time
            _LOGGER.error(
                "❌ Failed to subscribe to UPnP services for %s (after %.2fs): %s",
                self.upnp_client.host,
                subscription_duration,
                err,
            )
            _LOGGER.warning("   → Integration will fall back to HTTP polling")
            raise

    async def async_unsubscribe(self) -> None:
        """Unsubscribe from all services and stop notify server (reference pattern)."""
        if self.upnp_client._dmr_device:
            try:
                self.upnp_client._dmr_device.on_event = None
                await self.upnp_client._dmr_device.async_unsubscribe_services()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error unsubscribing services: %s", err)

        # Stop notify server
        await self.upnp_client.unwind_notify_server()

        _LOGGER.info("UPnP event subscriptions stopped for %s", self.upnp_client.host)

    def _on_event(
        self,
        service: UpnpService,
        state_variables: Sequence[UpnpStateVariable],
    ) -> None:
        """Handle UPnP events from DmrDevice (reference: dlna_dmr/media_player.py:510)."""
        # Handle empty state_variables (resubscription failure indication)
        if not state_variables:
            _LOGGER.debug(
                "Empty state_variables from %s - may indicate resubscription failure",
                self.upnp_client.host,
            )
            return

        # Extract service type from service.service_id
        service_id = service.service_id
        if "AVTransport" in service_id:
            service_type = "AVTransport"
        elif "RenderingControl" in service_id or "Rendering" in service_id:
            service_type = "RenderingControl"
        else:
            _LOGGER.debug("Unknown service type: %s", service_id)
            service_type = "Unknown"

        # Convert state_variables to dict (like original handle_notify received)
        variables_dict = {var.name: var.value for var in state_variables}

        # Track event statistics
        self._last_notify_ts = time.time()
        self._event_count += 1

        _LOGGER.info(
            "📡 Received UPnP NOTIFY #%d from %s: service=%s, variables=%s",
            self._event_count,
            self.upnp_client.host,
            service_type,
            list(variables_dict.keys()),
        )
        # Log all variable values for debugging (especially to see if audio output mode changes are included)
        # Always log LastChange XML to see what variables are available
        if "LastChange" in variables_dict:
            _LOGGER.debug(
                "UPnP event LastChange XML for %s: %s",
                self.upnp_client.host,
                variables_dict.get("LastChange", "")[
                    :500
                ],  # First 500 chars to avoid huge logs
            )

        # Parse LastChange XML (same as original)
        if "LastChange" in variables_dict:
            changes = self._parse_last_change(
                service_type, variables_dict["LastChange"]
            )
        else:
            changes = variables_dict

        # Apply diff to state (same as original)
        if self.state_manager.apply_diff(changes):
            async_dispatcher_send(self.hass, f"wiim_state_updated_{self.device_uuid}")

    def _parse_last_change(
        self,
        service_type: str,
        last_change_xml: str,
    ) -> dict[str, Any]:
        """Parse LastChange XML into state changes."""
        changes = {}

        try:
            from xml.etree import ElementTree as ET

            root = ET.fromstring(last_change_xml)

            # Parse Event XML structure
            for event in root.findall(".//Event"):
                for instance in event.findall("./InstanceID"):
                    _ = instance.get("val", "0")  # Instance ID not currently used

                    # Parse AVTransport service variables
                    if service_type == "AVTransport":
                        for var in list(instance):
                            var_name = var.tag
                            var_value = var.get("val", "")

                            if var_name == "TransportState":
                                changes["play_state"] = var_value.lower().replace(
                                    "_", " "
                                )
                            elif var_name == "AbsoluteTimePosition":
                                changes["position"] = self._parse_time_position(
                                    var_value
                                )
                            elif var_name == "RelativeTimePosition":
                                changes["position"] = self._parse_time_position(
                                    var_value
                                )
                            elif var_name == "CurrentTrackDuration":
                                changes["duration"] = self._parse_time_position(
                                    var_value
                                )

                    # Parse RenderingControl service variables
                    elif service_type == "RenderingControl":
                        for var in list(instance):
                            var_name = var.tag
                            var_value = var.get("val", "")
                            channel = var.get("channel", "")

                            if var_name == "Volume":
                                if channel == "Master" or not channel:
                                    try:
                                        vol_int = int(var_value)
                                        changes["volume"] = vol_int / 100.0
                                    except (ValueError, TypeError):
                                        pass
                            elif var_name == "Mute":
                                if channel == "Master" or not channel:
                                    changes["muted"] = var_value.lower() == "1"
                            # Log any other RenderingControl variables we're not parsing
                            # (might include audio output mode changes)
                            else:
                                _LOGGER.debug(
                                    "Unparsed RenderingControl variable: %s = %s",
                                    var_name,
                                    var_value,
                                )

                    # Log any other variables we encounter (for discovering audio output mode changes)
                    else:
                        _LOGGER.debug(
                            "Unparsed variable in %s service: %s = %s",
                            service_type,
                            var_name,
                            var_value,
                        )

        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error parsing LastChange XML: %s", err)

        if changes:
            _LOGGER.debug("Parsed LastChange for %s: %s", service_type, changes)

        return changes

    def _parse_time_position(self, time_str: str) -> int | None:
        """Parse time position from UPnP format to seconds."""
        if not time_str or time_str == "NOT_IMPLEMENTED":
            return None

        try:
            return int(time_str)
        except ValueError:
            pass

        try:
            parts = time_str.split(":")
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                return abs(hours * 3600 + minutes * 60 + seconds)
        except (ValueError, AttributeError):
            pass

        return None

    def get_subscription_stats(self) -> dict[str, Any]:
        """Get subscription statistics for diagnostics (following DLNA DMR pattern - no health checking)."""
        now = time.time()
        return {
            "total_events": self._event_count,
            "last_notify_ts": self._last_notify_ts,
            "time_since_last": now - self._last_notify_ts
            if self._last_notify_ts is not None
            else None,
        }
