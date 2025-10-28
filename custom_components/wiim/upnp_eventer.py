"""UPnP event handler for WiiM devices.

Follows Sonos integration pattern for subscription management and auto-renewal.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

from .upnp_client import UpnpClient

_LOGGER = logging.getLogger(__name__)


class UpnpEventer:
    """Manage UPnP event subscriptions and process LastChange notifications.

    Handles GENA (Generic Event Notification Architecture) subscriptions
    for AVTransport and RenderingControl services.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        upnp_client: UpnpClient,
        state_manager: Any,  # WiiMState - will be defined in state.py
        device_uuid: str,
    ) -> None:
        """Initialize UPnP eventer.

        Args:
            hass: Home Assistant instance
            upnp_client: UpnpClient instance for device
            state_manager: State manager for storing device state
            device_uuid: Unique device identifier for dispatcher signals
        """
        self.hass = hass
        self.upnp_client = upnp_client
        self.state_manager = state_manager
        self.device_uuid = device_uuid

        # Subscription tracking
        self._sid_avt: str | None = None  # AVTransport SID
        self._sid_rcs: str | None = None  # RenderingControl SID
        self._sid_avt_expires: int | None = None
        self._sid_rcs_expires: int | None = None

        # Health tracking
        self._push_healthy = False
        self._last_notify_ts: float | None = None
        self._event_count = 0
        self._retry_count = 0
        self._renew_cancel: Any | None = None  # Cancel callable from async_call_later

    async def start(
        self,
        callback_host: str | None = None,
        callback_port: int = 0,
    ) -> None:
        """Start event subscriptions.

        Args:
            callback_host: Host IP for callback URL (auto-detect if None)
            callback_port: Port for callback (0 = ephemeral)
        """
        # DLNA pattern: Notify server setup
        await self.upnp_client.start_notify_server(
            callback_host=callback_host,
            callback_port=callback_port,
        )

        # DLNA pattern: Subscribe to all services using DmrDevice
        def handle_upnp_event(service, state_variables):
            """Handle UPnP events from DmrDevice - calls our handle_notify method."""
            # Convert to our expected format
            variables_dict = {var.name: var.value for var in state_variables}
            _LOGGER.info(
                "🔔 UPnP EVENT CALLBACK FIRED from %s: service=%s, %d variables",
                self.upnp_client.host,
                service.service_id if hasattr(service, "service_id") else "unknown",
                len(variables_dict),
            )
            _LOGGER.debug("Variables: %s", list(variables_dict.keys()))
            # Call our handler
            self.handle_notify(
                service.service_id if hasattr(service, "service_id") else "unknown", None, None, variables_dict
            )

        _LOGGER.info("Subscribing to UPnP services for %s (DLNA pattern)", self.upnp_client.host)
        await self.upnp_client.async_subscribe_services(event_callback=handle_upnp_event)

        self._sid_avt_expires = time.time() + 1800
        self._sid_rcs_expires = time.time() + 1800
        _LOGGER.info("UPnP subscriptions established for %s", self.upnp_client.host)

        # Mark push as healthy
        self._push_healthy = True
        _LOGGER.info(
            "✅ UPnP event subscriptions started successfully for %s (AVTransport & RenderingControl)",
            self.upnp_client.host,
        )

    async def async_unsubscribe(self) -> None:
        """Unsubscribe from all services and stop notify server."""
        # Cancel renewal task
        if self._renew_cancel:
            try:
                self._renew_cancel()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error cancelling renewal: %s", err)
            self._renew_cancel = None

        # Unsubscribe from services
        if self._sid_avt:
            await self.upnp_client.async_unsubscribe("AVTransport", self._sid_avt)
            self._sid_avt = None
        if self._sid_rcs:
            await self.upnp_client.async_unsubscribe("RenderingControl", self._sid_rcs)
            self._sid_rcs = None

        # Stop notify server
        await self.upnp_client.unwind_notify_server()

        self._push_healthy = False
        _LOGGER.info("UPnP event subscriptions stopped for %s", self.upnp_client.host)

    @callback
    def _schedule_auto_renew(self) -> None:
        """Schedule subscription renewal before expiry."""
        # Renew at 28 minutes (120s before 30min expiry)
        self._renew_cancel = async_call_later(self.hass, 1680, self._async_renew_subscriptions)

    async def _async_renew_subscriptions(self, _now: Any) -> None:
        """Renew all active subscriptions."""
        try:
            _LOGGER.debug("Renewing UPnP subscriptions for %s", self.upnp_client.host)

            # Renew AVTransport subscription
            renewal_failed = False
            if self._sid_avt:
                ok_avt = await self.upnp_client.async_renew("AVTransport", self._sid_avt, timeout=1800)
                if not ok_avt:
                    renewal_failed = True

            # Renew RenderingControl subscription
            if self._sid_rcs:
                ok_rcs = await self.upnp_client.async_renew("RenderingControl", self._sid_rcs, timeout=1800)
                if not ok_rcs:
                    renewal_failed = True

            # Check if renewal succeeded
            if renewal_failed:
                self._retry_count += 1
                _LOGGER.warning(
                    "Subscription renewal failed for %s (retry_count=%d)",
                    self.upnp_client.host,
                    self._retry_count,
                )
                self._handle_subscription_failure()
            else:
                # Reset retry count on successful renewal
                self._retry_count = 0
                # Update expiry times
                self._sid_avt_expires = time.time() + 1800
                self._sid_rcs_expires = time.time() + 1800

            # Schedule next renewal
            self._schedule_auto_renew()

        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to renew subscriptions: %s", err)
            self._handle_subscription_failure()

    def _handle_subscription_failure(self) -> None:
        """Handle subscription failures with retry logic."""
        self._retry_count += 1

        if self._retry_count <= 3:
            # Attempt resubscribe
            _LOGGER.debug("Retrying subscription (attempt %d)", self._retry_count)
            # TODO: Implement retry logic
        else:
            # Push path unhealthy, enable polling fallback
            self._push_healthy = False
            _LOGGER.warning(
                "UPnP push unhealthy after %d retries, enabling fallback polling",
                self._retry_count,
            )

    @callback
    def handle_notify(
        self,
        service_type: str,
        _sid: str,  # Unused but part of UPnP protocol
        seq: int,
        variables: dict[str, Any],
    ) -> None:
        """Handle NOTIFY from device with LastChange data.

        Args:
            service_type: Service type ("AVTransport" or "RenderingControl")
            _sid: Subscription SID (unused in handler)
            seq: Event sequence number
            variables: State variables including LastChange
        """
        self._last_notify_ts = time.time()
        self._event_count += 1

        _LOGGER.info(
            "📡 Received UPnP NOTIFY #%d from %s: service=%s, keys=%s",
            self._event_count,
            self.upnp_client.host,
            service_type,
            list(variables.keys()),
        )

        _LOGGER.debug(
            "Full UPnP NOTIFY details from %s: service=%s, seq=%d, vars=%s",
            self.upnp_client.host,
            service_type,
            seq,
            variables,
        )

        # Parse LastChange XML
        if "LastChange" in variables:
            changes = self._parse_last_change(service_type, variables["LastChange"])
        else:
            changes = dict(variables)

        # Apply diff to state (only meaningful changes)
        if self.state_manager.apply_diff(changes):
            # Only trigger update if state actually changed (Sonos pattern)
            # Use underscore for consistency with other signals
            async_dispatcher_send(self.hass, f"wiim_state_updated_{self.device_uuid}")

    def _parse_last_change(
        self,
        service_type: str,
        last_change_xml: str,
    ) -> dict[str, Any]:
        """Parse LastChange XML into state changes.

        Args:
            service_type: Service type ("AVTransport" or "RenderingControl")
            last_change_xml: LastChange XML string

        Returns:
            Dict of state changes mapped to WiiMState attributes
        """
        changes = {}

        try:
            from xml.etree import ElementTree as ET

            root = ET.fromstring(last_change_xml)

            # Parse Event XML structure
            for event in root.findall(".//Event"):
                for instance in event.findall("./InstanceID"):
                    _instance_id = instance.get("val", "0")

                    # Parse AVTransport service variables
                    if service_type == "AVTransport":
                        for var in instance.findall(".//"):
                            var_name = var.tag
                            var_value = var.get("val", "")

                            # Map AVTransport state variables to WiiMState
                            if var_name == "TransportState":
                                # PLAYING, PAUSED_PLAYBACK, STOPPED, etc.
                                changes["play_state"] = var_value.lower().replace("_", " ")
                            elif var_name == "AbsoluteTimePosition":
                                # Parse time position (HH:MM:SS or negative offset)
                                changes["position"] = self._parse_time_position(var_value)
                            elif var_name == "CurrentTrackDuration":
                                changes["duration"] = self._parse_time_position(var_value)

                    # Parse RenderingControl service variables
                    elif service_type == "RenderingControl":
                        for var in instance.findall(".//"):
                            var_name = var.tag
                            var_value = var.get("val", "")

                            if var_name == "Volume":
                                # Convert volume (0-100) to float (0.0-1.0)
                                try:
                                    vol_int = int(var_value)
                                    changes["volume"] = vol_int / 100.0
                                except (ValueError, TypeError):
                                    pass
                            elif var_name == "Mute":
                                changes["muted"] = var_value.lower() == "1"

        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error parsing LastChange XML: %s", err)

        if changes:
            _LOGGER.debug(
                "Parsed LastChange for %s: %s",
                service_type,
                changes,
            )
        else:
            _LOGGER.debug("No valid state changes in LastChange for %s", service_type)

        return changes

    def _parse_time_position(self, time_str: str) -> int | None:
        """Parse time position from UPnP format to seconds.

        Formats: "HH:MM:SS" or "-HH:MM:SS" or seconds as string
        """
        if not time_str or time_str == "NOT_IMPLEMENTED":
            return None

        try:
            # Try simple seconds integer first
            return int(time_str)
        except ValueError:
            pass

        # Parse HH:MM:SS format
        try:
            parts = time_str.split(":")
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                total_seconds = hours * 3600 + minutes * 60 + seconds
                return abs(total_seconds)  # Return absolute value
        except (ValueError, AttributeError):
            pass

        return None

    def healthy(self) -> bool:
        """Check if push path is healthy."""
        if not self._push_healthy:
            return False

        # Check if we've received recent NOTIFYs
        time_since_last = time.time() - (self._last_notify_ts or 0)
        if time_since_last > 240:  # 4 minutes without events
            _LOGGER.warning(
                "No UPnP events for %.0f seconds, marking push unhealthy",
                time_since_last,
            )
            return False

        return True
