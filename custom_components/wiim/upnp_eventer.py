"""UPnP event handler for WiiM devices.

Follows Samsung/DLNA pattern using async_upnp_client (DmrDevice pattern).
See: /workspaces/core/homeassistant/components/dlna_dmr/media_player.py
and /workspaces/core/homeassistant/components/samsungtv/media_player.py
"""

from __future__ import annotations

from collections.abc import Sequence
import logging
import time
from typing import Any

from async_upnp_client.client import UpnpService, UpnpStateVariable
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

from .upnp_client import UpnpClient, UpnpError

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
        self._subscription_avt: Any | None = None  # AVTransport subscription object
        self._subscription_rcs: Any | None = None  # RenderingControl subscription object

        # Health tracking
        self._push_healthy = False
        self._last_notify_ts: float | None = None
        self._last_notify_avt: float | None = None  # Last AVTransport NOTIFY timestamp
        self._last_notify_rcs: float | None = None  # Last RenderingControl NOTIFY timestamp
        self._event_count = 0
        self._event_count_avt = 0  # AVTransport event count
        self._event_count_rcs = 0  # RenderingControl event count
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
        # Start notify server first (required before subscriptions)
        await self.upnp_client.start_notify_server(
            callback_host=callback_host,
            callback_port=callback_port,
        )

        # Samsung/DLNA pattern: Subscribe to services individually using DmrDevice pattern
        subscription_start_time = time.time()
        _LOGGER.info(
            "📨 Subscribing to UPnP services for %s (Samsung/DLNA pattern - individual subscriptions)",
            self.upnp_client.host,
        )

        try:
            # Create callback handler following DmrDevice pattern
            # Callback signature: (service: UpnpService, state_variables: Sequence[UpnpStateVariable])
            # See: dlna_dmr/media_player.py:510-511
            def make_service_callback(service_type: str, subscription_sid: str | None):
                """Create a callback function for a specific service type (DmrDevice pattern)."""

                def callback_handler(service: UpnpService, state_variables: Sequence[UpnpStateVariable]) -> None:
                    """Handle UPnP events from service subscription (DmrDevice pattern)."""
                    # Convert state variables to dict format for our handler
                    # Note: service parameter is available if needed (e.g., service.service_id for identification)
                    variables_dict = {var.name: var.value for var in state_variables}

                    _LOGGER.debug(
                        "🔔 UPnP callback received for %s service from %s: %d variables, SID=%s",
                        service_type,
                        self.upnp_client.host,
                        len(variables_dict),
                        subscription_sid or "unknown",
                    )

                    # Call our handler with correct service type and SID
                    self.handle_notify(
                        service_type,
                        subscription_sid or "unknown",
                        0,  # Sequence number - will be updated when we receive actual events
                        variables_dict,
                    )

                return callback_handler

            # Subscribe to AVTransport service
            # MUST set service.on_event BEFORE subscribing (DmrDevice pattern requirement)
            # See: async_upnp_client/profiles/dlna.py async_subscribe_services()
            _LOGGER.info("   → Subscribing to AVTransport service...")
            avt_callback = make_service_callback("AVTransport", None)  # SID not known yet
            self._subscription_avt = await self.upnp_client.async_subscribe(
                service_name="AVTransport",
                timeout=1800,
                sub_callback=avt_callback,  # Set BEFORE subscription (DmrDevice pattern)
            )

            # Capture SID and expiry from subscription response
            if self._subscription_avt:
                self._sid_avt = getattr(self._subscription_avt, "sid", None)
                granted_timeout = getattr(self._subscription_avt, "timeout", 1800)
                self._sid_avt_expires = time.time() + granted_timeout

                # Note: callback is already set on service.on_event via async_subscribe
                # Update callback closure with actual SID for better logging
                # (callback is already registered, just need to track SID)

                _LOGGER.info(
                    "   ✅ AVTransport subscription created: SID=%s, timeout=%d seconds",
                    self._sid_avt,
                    granted_timeout,
                )
            else:
                raise UpnpError("AVTransport subscription returned None")

            # Subscribe to RenderingControl service
            # MUST set service.on_event BEFORE subscribing (DmrDevice pattern requirement)
            _LOGGER.info("   → Subscribing to RenderingControl service...")
            rcs_callback = make_service_callback("RenderingControl", None)  # SID not known yet
            self._subscription_rcs = await self.upnp_client.async_subscribe(
                service_name="RenderingControl",
                timeout=1800,
                sub_callback=rcs_callback,  # Set BEFORE subscription (DmrDevice pattern)
            )

            # Capture SID and expiry from subscription response
            if self._subscription_rcs:
                self._sid_rcs = getattr(self._subscription_rcs, "sid", None)
                granted_timeout = getattr(self._subscription_rcs, "timeout", 1800)
                self._sid_rcs_expires = time.time() + granted_timeout

                # Note: callback is already set on service.on_event via async_subscribe

                _LOGGER.info(
                    "   ✅ RenderingControl subscription created: SID=%s, timeout=%d seconds",
                    self._sid_rcs,
                    granted_timeout,
                )
            else:
                raise UpnpError("RenderingControl subscription returned None")

            subscription_duration = time.time() - subscription_start_time

            _LOGGER.info(
                "✅ UPnP subscriptions established for %s (completed in %.2fs)",
                self.upnp_client.host,
                subscription_duration,
            )
            _LOGGER.info(
                "   → AVTransport: SID=%s, expires in %d seconds",
                self._sid_avt,
                int(self._sid_avt_expires - time.time()) if self._sid_avt_expires else 0,
            )
            _LOGGER.info(
                "   → RenderingControl: SID=%s, expires in %d seconds",
                self._sid_rcs,
                int(self._sid_rcs_expires - time.time()) if self._sid_rcs_expires else 0,
            )

            # Schedule auto-renewal before expiry (renew at 80% of timeout = 24 minutes for 30 min timeout)
            self._schedule_auto_renew()
            _LOGGER.info(
                "   → Auto-renewal scheduled (will renew at 80%% of timeout = ~24 minutes)",
            )

            # Mark push as healthy
            self._push_healthy = True
            _LOGGER.info(
                "✅ UPnP event subscriptions started successfully for %s (AVTransport & RenderingControl)",
                self.upnp_client.host,
            )
            _LOGGER.info(
                "   → Waiting for NOTIFY events from device...",
            )

        except Exception as err:  # noqa: BLE001
            subscription_duration = time.time() - subscription_start_time
            _LOGGER.error(
                "❌ Failed to subscribe to UPnP services for %s (after %.2fs): %s",
                self.upnp_client.host,
                subscription_duration,
                err,
            )
            _LOGGER.warning(
                "   → Integration will fall back to HTTP polling",
            )
            # Clean up partial subscriptions
            if self._subscription_avt and self._sid_avt:
                try:
                    await self.upnp_client.async_unsubscribe("AVTransport", self._sid_avt)
                except Exception:  # noqa: BLE001
                    pass
            if self._subscription_rcs and self._sid_rcs:
                try:
                    await self.upnp_client.async_unsubscribe("RenderingControl", self._sid_rcs)
                except Exception:  # noqa: BLE001
                    pass
            raise

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
        """Schedule subscription renewal before expiry.

        Renews at 80% of the shortest remaining timeout (e.g., 24 minutes for 30-minute timeout).
        """
        # Calculate renewal time based on earliest expiry
        now = time.time()
        earliest_expiry = None

        if self._sid_avt_expires:
            earliest_expiry = self._sid_avt_expires
        if self._sid_rcs_expires:
            if earliest_expiry is None or self._sid_rcs_expires < earliest_expiry:
                earliest_expiry = self._sid_rcs_expires

        if earliest_expiry is None:
            # Default to 30 minutes if no expiry times set
            renewal_delay = 1800 * 0.8  # 80% of 30 minutes = 24 minutes
        else:
            # Renew at 80% of remaining time
            remaining_time = earliest_expiry - now
            renewal_delay = remaining_time * 0.8

        # Ensure minimum delay of 60 seconds (safety check)
        renewal_delay = max(renewal_delay, 60)

        _LOGGER.debug(
            "Scheduling subscription renewal for %s in %.1f seconds (80%% of timeout)",
            self.upnp_client.host,
            renewal_delay,
        )
        self._renew_cancel = async_call_later(self.hass, renewal_delay, self._async_renew_subscriptions)

    async def _async_renew_subscriptions(self, _now: Any) -> None:
        """Renew all active subscriptions."""
        try:
            renewal_start_time = time.time()
            _LOGGER.info("🔄 Starting subscription renewal for %s", self.upnp_client.host)

            # Renew AVTransport subscription
            renewal_failed = False
            avt_renewed = False
            rcs_renewed = False

            if self._sid_avt:
                _LOGGER.debug("   → Renewing AVTransport subscription: SID=%s", self._sid_avt)
                result_avt = await self.upnp_client.async_renew("AVTransport", self._sid_avt, timeout=1800)
                if result_avt:
                    new_sid_avt, granted_timeout_avt = result_avt
                    self._sid_avt = new_sid_avt  # Update SID (may change on renewal)
                    self._sid_avt_expires = time.time() + granted_timeout_avt
                    avt_renewed = True
                else:
                    renewal_failed = True
            else:
                _LOGGER.debug("   → No AVTransport SID to renew")

            # Renew RenderingControl subscription
            if self._sid_rcs:
                _LOGGER.debug("   → Renewing RenderingControl subscription: SID=%s", self._sid_rcs)
                result_rcs = await self.upnp_client.async_renew("RenderingControl", self._sid_rcs, timeout=1800)
                if result_rcs:
                    new_sid_rcs, granted_timeout_rcs = result_rcs
                    self._sid_rcs = new_sid_rcs  # Update SID (may change on renewal)
                    self._sid_rcs_expires = time.time() + granted_timeout_rcs
                    rcs_renewed = True
                else:
                    renewal_failed = True
            else:
                _LOGGER.debug("   → No RenderingControl SID to renew")

            # Check if renewal succeeded
            renewal_duration = time.time() - renewal_start_time

            if renewal_failed:
                self._retry_count += 1
                _LOGGER.warning(
                    "⚠️  Subscription renewal failed for %s (retry_count=%d, duration=%.2fs)",
                    self.upnp_client.host,
                    self._retry_count,
                    renewal_duration,
                )
                _LOGGER.warning(
                    "   → AVTransport: %s, RenderingControl: %s",
                    "renewed" if avt_renewed else "FAILED",
                    "renewed" if rcs_renewed else "FAILED",
                )
                self._handle_subscription_failure()
            else:
                # Reset retry count on successful renewal
                self._retry_count = 0
                _LOGGER.info(
                    "✅ Subscription renewal successful for %s (duration=%.2fs)",
                    self.upnp_client.host,
                    renewal_duration,
                )
                _LOGGER.debug(
                    "   → AVTransport expires: %d seconds, RenderingControl expires: %d seconds",
                    int(self._sid_avt_expires - time.time()) if self._sid_avt_expires else 0,
                    int(self._sid_rcs_expires - time.time()) if self._sid_rcs_expires else 0,
                )
                # Update expiry times (already updated above for successful renewals)
                if self._sid_avt_expires is None:
                    self._sid_avt_expires = time.time() + 1800
                if self._sid_rcs_expires is None:
                    self._sid_rcs_expires = time.time() + 1800

            # Schedule next renewal
            self._schedule_auto_renew()

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("❌ Failed to renew subscriptions for %s: %s", self.upnp_client.host, err)
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
        now = time.time()
        self._last_notify_ts = now
        self._event_count += 1

        # Track per-service statistics
        if service_type == "AVTransport":
            self._last_notify_avt = now
            self._event_count_avt += 1
            service_count = self._event_count_avt
            time_since_last = now - (self._last_notify_avt or 0)
        elif service_type == "RenderingControl":
            self._last_notify_rcs = now
            self._event_count_rcs += 1
            service_count = self._event_count_rcs
            time_since_last = now - (self._last_notify_rcs or 0)
        else:
            service_count = self._event_count
            time_since_last = now - (self._last_notify_ts or 0)

        _LOGGER.info(
            "📡 Received UPnP NOTIFY #%d (%s #%d) from %s: service=%s",
            self._event_count,
            service_type,
            service_count,
            self.upnp_client.host,
            service_type,
        )
        _LOGGER.info(
            "   → Variables: %s",
            list(variables.keys()),
        )

        if time_since_last > 0.1:  # Only log if significant time gap
            _LOGGER.debug(
                "   → Time since last %s event: %.2fs",
                service_type,
                time_since_last,
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
            # Only trigger update if state actually changed
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

    def _map_service_id_to_type(self, service_id: str) -> str:
        """Map service ID to canonical service type name.

        Args:
            service_id: Service ID from UPnP device

        Returns:
            Canonical service type ("AVTransport" or "RenderingControl")
        """
        service_id_lower = service_id.lower()
        if "transport" in service_id_lower:
            return "AVTransport"
        elif "rendering" in service_id_lower or "control" in service_id_lower:
            return "RenderingControl"
        return service_id  # Return as-is if cannot determine

    def healthy(self) -> bool:
        """Check if push path is healthy."""
        if not self._push_healthy:
            return False

        now = time.time()

        # Check if we've received recent NOTIFYs from either service
        time_since_last = now - (self._last_notify_ts or 0)

        # Also check per-service health
        avt_time_since = now - (self._last_notify_avt or 0) if self._last_notify_avt else float("inf")
        rcs_time_since = now - (self._last_notify_rcs or 0) if self._last_notify_rcs else float("inf")

        # Consider unhealthy if no events for 4+ minutes
        if time_since_last > 240:  # 4 minutes without any events
            _LOGGER.warning(
                "⚠️  No UPnP events for %.0f seconds - marking push unhealthy",
                time_since_last,
            )
            _LOGGER.debug(
                "   → AVTransport: last event %.0fs ago (%d events total)",
                avt_time_since if avt_time_since < float("inf") else 0,
                self._event_count_avt,
            )
            _LOGGER.debug(
                "   → RenderingControl: last event %.0fs ago (%d events total)",
                rcs_time_since if rcs_time_since < float("inf") else 0,
                self._event_count_rcs,
            )
            return False

        return True

    def get_subscription_stats(self) -> dict[str, Any]:
        """Get subscription statistics for diagnostics.

        Returns:
            Dictionary with subscription health metrics
        """
        now = time.time()
        return {
            "push_healthy": self._push_healthy,
            "total_events": self._event_count,
            "avt_events": self._event_count_avt,
            "rcs_events": self._event_count_rcs,
            "last_notify_ts": self._last_notify_ts,
            "last_notify_avt": self._last_notify_avt,
            "last_notify_rcs": self._last_notify_rcs,
            "time_since_last": now - (self._last_notify_ts or 0),
            "avt_expires": self._sid_avt_expires,
            "rcs_expires": self._sid_rcs_expires,
            "retry_count": self._retry_count,
        }
