"""UPnP client for WiiM/Linkplay devices.

Follows Samsung/DLNA pattern using async_upnp_client (DmrDevice pattern).
See: /workspaces/core/homeassistant/components/dlna_dmr/media_player.py
and /workspaces/core/homeassistant/components/samsungtv/media_player.py
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import ssl
from typing import Any

from aiohttp import ClientError, ClientSession, TCPConnector
from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpSessionRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpError, UpnpResponseError
from async_upnp_client.profiles.dlna import DmrDevice
from async_upnp_client.utils import async_get_local_ip

_LOGGER = logging.getLogger(__name__)


class UpnpClient:
    """UPnP client wrapper for WiiM devices using async-upnp-client.

    Provides SOAP action calls and service discovery for AVTransport
    and RenderingControl services.
    """

    def __init__(
        self,
        host: str,
        description_url: str,
        session: Any,
    ) -> None:
        """Initialize UPnP client.

        Args:
            host: Device hostname or IP
            description_url: URL to device description.xml
            session: aiohttp session for HTTP requests
        """
        self.host = host
        self.description_url = description_url
        self.session = session
        self._device = None
        self._dmr_device = None  # DmrDevice wrapper for subscriptions (DLNA pattern)
        self._av_transport_service = None
        self._rendering_control_service = None
        self._notify_server = None

    @classmethod
    async def create(
        cls,
        host: str,
        description_url: str,
        session: Any,
    ) -> UpnpClient:
        """Create and initialize UPnP client from description URL.

        Args:
            host: Device hostname or IP
            description_url: URL to device description.xml
            session: aiohttp session for HTTP requests

        Returns:
            Initialized UpnpClient instance
        """
        client = cls(host, description_url, session)
        await client._initialize()
        return client

    async def _initialize(self) -> None:
        """Initialize UPnP device and services."""
        try:
            # Handle both HTTP and HTTPS description URLs
            if self.description_url.startswith("https://"):
                _LOGGER.info("Using HTTPS for UPnP description (self-signed cert support enabled)")
                # HTTPS with self-signed cert support
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                ssl_context.set_ciphers("ALL:@SECLEVEL=0")
                connector = TCPConnector(ssl=ssl_context)
            else:
                _LOGGER.info("Using HTTP for UPnP description (no SSL needed)")
                # HTTP - no SSL needed
                connector = TCPConnector(ssl=False)

            session = ClientSession(connector=connector)
            # DLNA pattern: with_sleep=True adds retry logic, timeout ensures we don't hang
            requester = AiohttpSessionRequester(session, with_sleep=True, timeout=10)

            # Create UPnP device from description.xml using factory (DLNA/DMR pattern)
            _LOGGER.info("Fetching UPnP device description from: %s", self.description_url)
            factory = UpnpFactory(requester, non_strict=True)

            # Add explicit timeout wrapper (5 seconds for description.xml fetch)
            try:
                async with asyncio.timeout(5):
                    self._device = await factory.async_create_device(self.description_url)
            except TimeoutError as timeout_err:
                _LOGGER.error(
                    "❌ Timeout fetching UPnP description from %s after 5 seconds - device may not support UPnP properly",
                    self.description_url,
                )
                raise UpnpError(f"Timeout fetching UPnP description: {timeout_err}") from timeout_err

            _LOGGER.info(
                "✅ Successfully fetched and parsed UPnP device description for %s",
                self.host,
            )

            # Get AVTransport service
            self._av_transport_service = self._device.service("urn:schemas-upnp-org:service:AVTransport:1")

            # Get RenderingControl service
            self._rendering_control_service = self._device.service("urn:schemas-upnp-org:service:RenderingControl:1")

            if not self._av_transport_service:
                _LOGGER.warning(
                    "⚠️  Device %s does not advertise AVTransport service - UPnP eventing may not work",
                    self.host,
                )
            if not self._rendering_control_service:
                _LOGGER.warning(
                    "⚠️  Device %s does not advertise RenderingControl service - UPnP volume events may not work",
                    self.host,
                )

            _LOGGER.info(
                "✅ UPnP client initialized for %s: AVTransport=%s, RenderingControl=%s",
                self.host,
                self._av_transport_service is not None,
                self._rendering_control_service is not None,
            )

        except TimeoutError as err:
            _LOGGER.error(
                "❌ Timeout initializing UPnP client for %s after 5 seconds",
                self.host,
            )
            raise UpnpError(f"Timeout creating UPnP device: {err}") from err
        except ClientError as err:
            _LOGGER.error(
                "❌ Network error initializing UPnP client for %s: %s",
                self.host,
                err,
            )
            raise UpnpError(f"Network error creating UPnP device: {err}") from err
        except Exception as err:
            _LOGGER.error(
                "❌ Failed to initialize UPnP client for %s: %s (type: %s)",
                self.host,
                err,
                type(err).__name__,
            )
            raise UpnpError(f"Failed to create UPnP device: {err}") from err

    async def start_notify_server(
        self,
        callback_host: str | None = None,
        callback_port: int = 0,
    ) -> AiohttpNotifyServer:
        """Start the NOTIFY server for receiving event notifications.

        Args:
            callback_host: Host IP for callback URL (auto-detect if None)
            callback_port: Port for callback (0 = ephemeral)

        Returns:
            Started AiohttpNotifyServer instance
        """
        # Create notify server (DLNA/DMR pattern) with SSL disabled for self-signed certs
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        ssl_context.set_ciphers("ALL:@SECLEVEL=0")

        connector = TCPConnector(ssl=ssl_context)
        session = ClientSession(connector=connector)
        requester = AiohttpSessionRequester(session, with_sleep=True, timeout=10)

        # DLNA pattern: Get the correct local IP for callback URL (handles Docker/WSL networking)
        # In WSL2, async_get_local_ip returns the WSL NAT IP which devices can't reach.
        # We need to allow the caller to pass in the correct host IP via callback_host parameter.

        if callback_host:
            # Use explicit host if provided (allows workaround for Docker/WSL)
            event_ip = callback_host
            _LOGGER.info("Using explicit host IP for UPnP callback: %s", event_ip)
        else:
            # Try to auto-detect
            try:
                _, event_ip = await async_get_local_ip(f"http://{self.host}:49152", asyncio.get_event_loop())
                _LOGGER.info("Detected local IP for UPnP callback: %s", event_ip)
                # Warn if we're in a container network that might not be reachable
                if event_ip.startswith("172.") or event_ip.startswith("192.168.65"):
                    _LOGGER.warning(
                        "⚠️  Detected container/WSL IP %s - devices on your LAN may not be able to reach this for UPnP events. "
                        "Solutions: 1) Use 'network_mode: host' in Docker, 2) Add '--network=host' to devcontainer.json runArgs, "
                        "or 3) Pass the host's LAN IP via callback_host parameter.",
                        event_ip,
                    )
            except Exception as err:
                _LOGGER.warning("Could not detect local IP for UPnP callback: %s", err)
                event_ip = "0.0.0.0"

        source_ip = event_ip if callback_port == 0 else callback_host or event_ip

        self._notify_server = AiohttpNotifyServer(
            requester=requester,
            source=(source_ip, callback_port),
            loop=None,  # Use default event loop
        )

        await self._notify_server.async_start_server()

        # Get server info from the notify server instance
        server_host = getattr(self._notify_server, "host", "unknown")
        server_port = getattr(self._notify_server, "port", "unknown")
        callback_url = getattr(self._notify_server, "callback_url", None)

        # Enhanced callback URL logging with validation
        if callback_url:
            _LOGGER.info(
                "✅ Notify server started on %s:%s",
                server_host,
                server_port,
            )
            _LOGGER.info(
                "📡 UPnP callback URL: %s (this URL will be sent to devices in SUBSCRIBE requests)",
                callback_url,
            )

            # Detect and warn about unreachable container/WSL IPs
            is_unreachable = False
            unreachable_reason = None

            if server_host.startswith("172."):
                is_unreachable = True
                unreachable_reason = "Docker bridge network IP (172.x.x.x)"
            elif server_host.startswith("192.168.65"):
                is_unreachable = True
                unreachable_reason = "WSL2 NAT network IP (192.168.65.x)"
            elif server_host == "0.0.0.0":
                is_unreachable = True
                unreachable_reason = "wildcard binding (0.0.0.0) - devices cannot reach this"

            if is_unreachable:
                _LOGGER.error(
                    "⚠️  CRITICAL: Callback URL is using %s - devices on your LAN CANNOT reach this for UPnP events!",
                    unreachable_reason,
                )
                _LOGGER.error(
                    "   ➤ Solutions:",
                )
                _LOGGER.error(
                    "      1. Use 'network_mode: host' in docker-compose.yml",
                )
                _LOGGER.error(
                    "      2. Add '--network=host' to devcontainer.json runArgs",
                )
                _LOGGER.error(
                    "      3. Configure callback_host in integration options with your host's LAN IP",
                )
                _LOGGER.error(
                    "      4. Use port forwarding to map callback port to host",
                )
                _LOGGER.error(
                    "   Integration will fall back to HTTP polling, but real-time events will not work.",
                )
            else:
                _LOGGER.info(
                    "✓ Callback URL appears reachable (not a container/WSL IP)",
                )
        else:
            _LOGGER.error("⚠️  CRITICAL: No callback_url from notify server - UPnP events will NOT work!")
            _LOGGER.error(
                "   This is likely a networking issue - devices cannot send NOTIFY events to the container",
            )
            _LOGGER.error(
                "   Check Docker networking configuration (use --network=host or configure port forwarding)",
            )

        # Create DmrDevice wrapper (DLNA pattern from Samsung/DLNA integrations)
        # This provides async_subscribe_services() method
        self._dmr_device = DmrDevice(self._device, self._notify_server.event_handler)
        _LOGGER.info("DmrDevice wrapper created for %s", self.host)

        return self._notify_server

    async def unwind_notify_server(self) -> None:
        """Stop and clean up the NOTIFY server."""
        if self._notify_server:
            try:
                await self._notify_server.async_stop_server()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error stopping notify server for %s: %s", self.host, err)
            finally:
                self._notify_server = None
                _LOGGER.debug("Notify server stopped for %s", self.host)

    @property
    def av_transport(self) -> Any:
        """Get AVTransport service."""
        return self._av_transport_service

    @property
    def rendering_control(self) -> Any:
        """Get RenderingControl service."""
        return self._rendering_control_service

    @property
    def notify_server(self) -> AiohttpNotifyServer:
        """Get notify server instance."""
        return self._notify_server

    async def async_subscribe(
        self,
        service_name: str,
        timeout: int = 1800,
        sub_callback: Any = None,
        renew_fail_callback: Any = None,
    ) -> Any:
        """Subscribe to UPnP service events (Samsung/DLNA pattern).

        Uses event_handler.async_subscribe() like DmrDevice does.
        See: async_upnp_client/profiles/dlna.py async_subscribe_services()

        Args:
            service_name: Name of service ("AVTransport" or "RenderingControl")
            timeout: Subscription timeout in seconds
            sub_callback: Callback function for events (signature: (service, state_variables))
            renew_fail_callback: Unused (renewal handled separately)

        Returns:
            Subscription object (for storing and managing callback)
        """
        # Map service name to attribute name
        service_attr_map = {
            "avtransport": "_av_transport_service",
            "renderingcontrol": "_rendering_control_service",
        }
        service_attr = service_attr_map.get(service_name.lower())
        if not service_attr:
            raise UpnpError(f"Service {service_name} not available")

        service = getattr(self, service_attr)
        if not service:
            raise UpnpError(f"Service {service_name} not initialized")

        if not self._notify_server:
            raise UpnpError("Notify server not started")

        # Get notify server host/port using getattr to handle attribute access
        server_host = getattr(self._notify_server, "host", "localhost")
        server_port = getattr(self._notify_server, "port", 8000)

        callback_url = f"http://{server_host}:{server_port}/notify"

        # Log the subscription request with callback URL
        _LOGGER.info(
            "📨 Subscribing to %s service on %s",
            service_name,
            self.host,
        )
        _LOGGER.debug(
            "   → Using callback URL: %s (devices will send NOTIFY events to this URL)",
            callback_url,
        )
        _LOGGER.debug("   → Requested timeout: %d seconds", timeout)

        # Following DmrDevice pattern from dlna_dmr/samsungtv integrations:
        # 1. Set service.on_event callback BEFORE subscribing
        # 2. Call event_handler.async_subscribe(service, timeout=...) which returns (sid, timeout_timedelta)
        # See: /workspaces/core/homeassistant/components/dlna_dmr/media_player.py:391
        # and async_upnp_client/profiles/dlna.py async_subscribe_services()
        event_handler = self._notify_server.event_handler

        # Set callback on service (DmrDevice pattern: service.on_event is called by event_handler)
        if sub_callback:
            service.on_event = sub_callback

        # Subscribe - returns (sid, timeout_timedelta) tuple
        # event_handler.async_subscribe() expects timeout as timedelta, not int
        timeout_delta = timedelta(seconds=timeout)
        sid, timeout_timedelta = await event_handler.async_subscribe(
            service,
            timeout=timeout_delta,
        )

        # Convert timedelta to seconds
        granted_timeout = int(timeout_timedelta.total_seconds())

        # Create subscription wrapper for tracking SID and timeout
        class SubscriptionWrapper:
            """Wrapper for subscription info (Samsung/DLNA pattern compatibility)."""

            def __init__(self, sid: str, timeout: int, service_obj: Any):
                self.sid = sid
                self.timeout = timeout
                self.service = service_obj

            @property
            def callback(self):
                return getattr(self.service, "on_event", None)

            @callback.setter
            def callback(self, value):
                # Update service.on_event (DmrDevice pattern)
                self.service.on_event = value

        subscription = SubscriptionWrapper(sid, granted_timeout, service)

        _LOGGER.info(
            "✅ Successfully subscribed to %s on %s",
            service_name,
            self.host,
        )
        _LOGGER.info(
            "   → SID: %s",
            sid,
        )
        _LOGGER.info(
            "   → Timeout: %d seconds (requested %d, granted %d)",
            granted_timeout,
            timeout,
            granted_timeout,
        )
        _LOGGER.info(
            "   → Callback URL: %s",
            callback_url,
        )

        return subscription

    async def async_subscribe_services(
        self,
        event_callback: Any = None,
    ) -> None:
        """Subscribe to UPnP services (DLNA pattern).

        This follows the Samsung/DLNA pattern using DmrDevice.async_subscribe_services().

        Args:
            event_callback: Callback function for events (called with service and state_variables)
        """
        if not self._dmr_device:
            raise UpnpError("DmrDevice not initialized - call start_notify_server() first")

        try:
            # Set event callback
            if event_callback:
                self._dmr_device.on_event = event_callback

            # Subscribe to all services (DLNA pattern)
            _LOGGER.info("📨 Subscribing to all UPnP services using DmrDevice pattern for %s", self.host)
            callback_url = getattr(self._notify_server, "callback_url", "unknown")
            _LOGGER.debug("   → Using callback URL: %s", callback_url)

            await self._dmr_device.async_subscribe_services(auto_resubscribe=True)
            _LOGGER.info("✅ Successfully subscribed to UPnP services for %s (DLNA/DmrDevice pattern)", self.host)
            _LOGGER.debug(
                "   → Devices will send NOTIFY events to: %s",
                callback_url,
            )

        except UpnpResponseError as err:
            # Device rejected subscription - this is OK, we'll poll instead
            _LOGGER.debug("Device rejected subscription for %s: %r", self.host, err)
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Error subscribing to services for %s: %s", self.host, err)
            raise UpnpError(f"Failed to subscribe to services: {err}") from err

    async def async_renew(
        self,
        service_name: str,
        sid: str,
        timeout: int = 1800,
    ) -> tuple[str, int] | None:
        """Renew UPnP service subscription (Samsung/DLNA pattern).

        Uses event_handler.async_resubscribe() like DmrDevice does.
        See: async_upnp_client/profiles/dlna.py _async_resubscribe_services()

        Args:
            service_name: Name of service ("AVTransport" or "RenderingControl")
            sid: Subscription SID to renew
            timeout: New subscription timeout in seconds

        Returns:
            Tuple of (new_sid, timeout_timedelta) if successful, None otherwise
        """
        if not self._notify_server:
            _LOGGER.warning("Notify server not available for renewal")
            return False

        event_handler = self._notify_server.event_handler

        try:
            _LOGGER.debug(
                "🔄 Renewing subscription to %s on %s: SID=%s, timeout=%d seconds",
                service_name,
                self.host,
                sid,
                timeout,
            )
            # DmrDevice pattern: event_handler.async_resubscribe() returns (new_sid, timeout_timedelta)
            # event_handler.async_resubscribe() expects timeout as timedelta, not int
            timeout_delta = timedelta(seconds=timeout)
            new_sid, timeout_timedelta = await event_handler.async_resubscribe(
                sid,
                timeout=timeout_delta,
            )
            granted_timeout = int(timeout_timedelta.total_seconds())
            _LOGGER.info(
                "✅ Successfully renewed subscription to %s on %s: SID=%s->%s, expires=%d seconds",
                service_name,
                self.host,
                sid,
                new_sid,
                granted_timeout,
            )
            return (new_sid, granted_timeout)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "❌ Failed to renew subscription to %s on %s (SID=%s): %s",
                service_name,
                self.host,
                sid,
                err,
            )
            return None

    async def async_unsubscribe(
        self,
        service_name: str,
        sid: str,
    ) -> None:
        """Unsubscribe from UPnP service (Samsung/DLNA pattern).

        Uses event_handler.async_unsubscribe() like DmrDevice does.
        See: async_upnp_client/profiles/dlna.py async_unsubscribe_services()

        Args:
            service_name: Name of service ("AVTransport" or "RenderingControl")
            sid: Subscription SID to unsubscribe
        """
        if not self._notify_server:
            _LOGGER.warning("Notify server not available for unsubscribe")
            return

        event_handler = self._notify_server.event_handler

        try:
            _LOGGER.debug("Unsubscribing from %s on %s: SID=%s", service_name, self.host, sid)
            # DmrDevice pattern: event_handler.async_unsubscribe()
            await event_handler.async_unsubscribe(sid)
            _LOGGER.info("✅ Unsubscribed from %s on %s: SID=%s", service_name, self.host, sid)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("⚠️  Error unsubscribing from %s on %s (SID=%s): %s", service_name, self.host, sid, err)

    async def async_call_action(
        self,
        service_name: str,
        action: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call UPnP service action.

        Args:
            service_name: Name of service ("AVTransport" or "RenderingControl")
            action: Action name (e.g., "Play", "Pause", "SetVolume")
            arguments: Action arguments

        Returns:
            Action response as dict
        """
        service = getattr(self, f"_{service_name.lower().replace(' ', '_')}_service")
        if not service:
            raise UpnpError(f"Service {service_name} not available")

        action_obj = service.action(action)
        if not action_obj:
            raise UpnpError(f"Action {action} not found in {service_name}")

        result = await action_obj.async_call(**arguments or {})

        return result
