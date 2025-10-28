"""UPnP client for WiiM/Linkplay devices.

Follows DLNA/DMR and Sonos integration patterns from core Home Assistant.
"""

from __future__ import annotations

import logging
from typing import Any

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpSessionRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpError

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
            # Session requester with SSL disabled for self-signed certs (DLNA/DMR pattern)
            requester = AiohttpSessionRequester(self.session, with_sleep=True, timeout=10)

            # Create UPnP device from description.xml using factory (DLNA/DMR pattern)
            factory = UpnpFactory(requester, non_strict=True)
            self._device = await factory.async_create_device(self.description_url)

            # Get AVTransport service
            self._av_transport_service = self._device.service("urn:schemas-upnp-org:service:AVTransport:1")

            # Get RenderingControl service
            self._rendering_control_service = self._device.service("urn:schemas-upnp-org:service:RenderingControl:1")

            _LOGGER.info(
                "UPnP client initialized for %s: AVTransport=%s, RenderingControl=%s",
                self.host,
                self._av_transport_service is not None,
                self._rendering_control_service is not None,
            )

        except Exception as err:
            _LOGGER.warning("Failed to initialize UPnP client for %s: %s", self.host, err)
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
        # Create notify server (DLNA/DMR pattern)
        requester = AiohttpSessionRequester(self.session, with_sleep=True, timeout=10)
        source_ip = "0.0.0.0" if callback_port == 0 else callback_host or "0.0.0.0"

        self._notify_server = AiohttpNotifyServer(
            requester=requester,
            source=(source_ip, callback_port),
            loop=None,  # Use default event loop
        )

        await self._notify_server.async_start_server()

        _LOGGER.info(
            "Notify server started on %s:%d",
            self._notify_server.host,
            self._notify_server.port,
        )

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
        """Subscribe to UPnP service events (Sonos pattern).

        Args:
            service_name: Name of service ("AVTransport" or "RenderingControl")
            timeout: Subscription timeout in seconds
            sub_callback: Callback function for events (Sonos pattern)
            renew_fail_callback: Callback function when renewal fails (Sonos pattern)

        Returns:
            Subscription object (for storing and managing callback)
        """
        service = getattr(self, f"_{service_name.lower().replace(' ', '_')}_service")
        if not service:
            raise UpnpError(f"Service {service_name} not available")

        if not self._notify_server:
            raise UpnpError("Notify server not started")

        callback_url = f"http://{self._notify_server.host}:{self._notify_server.port}/notify"

        # Sonos pattern: use auto_renew=True and manage callbacks
        subscription = await service.subscribe(
            auto_renew=True,
            requested_timeout=timeout,
            event_callback_url=callback_url,
        )

        # Set callbacks (Sonos pattern from lines 423-424)
        if sub_callback:
            subscription.callback = sub_callback
        if renew_fail_callback:
            subscription.auto_renew_fail = renew_fail_callback

        _LOGGER.info(
            "Subscribed to %s on %s: SID=%s, expires=%d seconds (auto_renew=True)",
            service_name,
            self.host,
            subscription.sid,
            timeout,
        )

        return subscription

    async def async_renew(
        self,
        service_name: str,
        sid: str,
        timeout: int = 1800,
    ) -> bool:
        """Renew UPnP service subscription.

        Args:
            service_name: Name of service ("AVTransport" or "RenderingControl")
            sid: Subscription SID to renew
            timeout: New subscription timeout in seconds

        Returns:
            True if renewal successful, False otherwise
        """
        service = getattr(self, f"_{service_name.lower().replace(' ', '_')}_service")
        if not service:
            _LOGGER.warning("Service %s not available for renewal", service_name)
            return False

        try:
            await service.async_resubscribe(sid=sid, timeout=timeout)
            _LOGGER.debug(
                "Renewed subscription to %s on %s: SID=%s, expires=%d seconds",
                service_name,
                self.host,
                sid,
                timeout,
            )
            return True
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Failed to renew subscription to %s on %s (SID=%s): %s",
                service_name,
                self.host,
                sid,
                err,
            )
            return False

    async def async_unsubscribe(
        self,
        service_name: str,
        sid: str,
    ) -> None:
        """Unsubscribe from UPnP service.

        Args:
            service_name: Name of service ("AVTransport" or "RenderingControl")
            sid: Subscription SID to unsubscribe
        """
        service = getattr(self, f"_{service_name.lower().replace(' ', '_')}_service")
        if not service:
            _LOGGER.warning("Service %s not available for unsubscribe", service_name)
            return

        try:
            await service.async_unsubscribe(sid=sid)
            _LOGGER.debug("Unsubscribed from %s on %s: SID=%s", service_name, self.host, sid)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error unsubscribing from %s on %s: %s", service_name, self.host, err)

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
