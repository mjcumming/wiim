"""Squeezelite/LMS (Lyrion Music Server) integration helpers for WiiM HTTP client.

This mixin handles Squeezelite server discovery, connection management, and
configuration. These endpoints are unofficial and may not be available on
all firmware versions or device models.

It assumes the base client provides the `_request` coroutine and logging via
`_log` or `_LOGGER`. No state is stored – all results come from the device each call.
"""

from __future__ import annotations

from typing import Any

from .api_base import WiiMError
from .const import (  # noqa: I001,I202  # Import order matches project style
    API_ENDPOINT_SQUEEZELITE_AUTO_CONNECT,
    API_ENDPOINT_SQUEEZELITE_CONNECT_SERVER,
    API_ENDPOINT_SQUEEZELITE_DISCOVER,
    API_ENDPOINT_SQUEEZELITE_STATE,
)


class LMSAPI:  # mixin – must appear *before* the base client in MRO
    """Squeezelite/LMS server integration helpers."""

    # pylint: disable=no-member

    # ------------------------------------------------------------------
    # LMS server state and discovery
    # ------------------------------------------------------------------

    async def get_squeezelite_state(self) -> dict[str, Any]:  # type: ignore[override]
        """Get current Squeezelite configuration and connection state.

        Returns:
            Dict containing:
            - default_server: LMS instance for auto-connect (e.g., "192.168.1.4:3483")
            - state: Current connection state ("discovering", "connected", etc.)
            - discover_list: List of discovered LMS servers
            - connected_server: Currently connected server (if any)
            - auto_connect: Whether auto-connect is enabled (1/0)
        """
        return await self._request(API_ENDPOINT_SQUEEZELITE_STATE)  # type: ignore[attr-defined]

    async def discover_lms_servers(self) -> None:  # type: ignore[override]
        """Trigger discovery of LMS servers on the network.

        Raises:
            WiiMRequestError: If the discovery request fails
        """
        await self._request(API_ENDPOINT_SQUEEZELITE_DISCOVER)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def set_auto_connect_enabled(self, enabled: bool) -> None:  # type: ignore[override]
        """Enable or disable automatic connection to LMS servers.

        Args:
            enabled: True to enable auto-connect, False to disable

        Raises:
            WiiMRequestError: If the request fails
        """
        value = "1" if enabled else "0"
        await self._request(f"{API_ENDPOINT_SQUEEZELITE_AUTO_CONNECT}{value}")  # type: ignore[attr-defined]

    async def connect_to_lms_server(self, server_address: str) -> None:  # type: ignore[override]
        """Connect to a specific LMS server.

        Args:
            server_address: LMS server IP address (with optional port, e.g., "192.168.1.123:3483")

        Raises:
            WiiMRequestError: If the connection request fails
        """
        await self._request(f"{API_ENDPOINT_SQUEEZELITE_CONNECT_SERVER}{server_address}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    async def is_auto_connect_enabled(self) -> bool:  # type: ignore[override]
        """Check if LMS auto-connect is enabled.

        Returns:
            True if auto-connect is enabled, False otherwise
        """
        try:
            state = await self.get_squeezelite_state()
            return str(state.get("auto_connect", "0")) == "1"
        except WiiMError:
            return False

    async def get_connected_server(self) -> str:  # type: ignore[override]
        """Get currently connected LMS server address.

        Returns:
            Server address (e.g., "192.168.1.4:3483") or empty string if not connected
        """
        try:
            state = await self.get_squeezelite_state()
            return str(state.get("connected_server", ""))
        except WiiMError:
            return ""

    async def get_default_server(self) -> str:  # type: ignore[override]
        """Get default LMS server for auto-connect.

        Returns:
            Default server address or empty string if not set
        """
        try:
            state = await self.get_squeezelite_state()
            return str(state.get("default_server", ""))
        except WiiMError:
            return ""

    async def get_discovered_servers(self) -> list[str]:  # type: ignore[override]
        """Get list of discovered LMS servers.

        Returns:
            List of server addresses (e.g., ["192.168.1.4:3483", "192.168.1.123:3483"])
        """
        try:
            state = await self.get_squeezelite_state()
            discover_list = state.get("discover_list", [])
            return discover_list if isinstance(discover_list, list) else []
        except WiiMError:
            return []

    async def get_connection_state(self) -> str:  # type: ignore[override]
        """Get current LMS connection state as human-readable string.

        Returns:
            State string: "discovering", "connected", "disconnected", or "unknown"
        """
        state_map = {"discovering": "Searching for servers", "connected": "Connected", "disconnected": "Disconnected"}

        try:
            state = await self.get_squeezelite_state()
            raw_state = str(state.get("state", "")).lower()
            return state_map.get(raw_state, raw_state or "unknown")
        except WiiMError:
            return "unknown"

    async def is_connected_to_lms(self) -> bool:  # type: ignore[override]
        """Check if currently connected to an LMS server.

        Returns:
            True if connected, False otherwise
        """
        try:
            state = await self.get_squeezelite_state()
            return str(state.get("state", "")).lower() == "connected"
        except WiiMError:
            return False

    async def setup_lms_connection(self, server_address: str, auto_connect: bool = True) -> None:  # type: ignore[override]
        """Convenience method to set up LMS connection with one call.

        Args:
            server_address: LMS server address to connect to
            auto_connect: Whether to enable auto-connect (default: True)
        """
        # Set auto-connect preference
        await self.set_auto_connect_enabled(auto_connect)

        # Connect to the server
        await self.connect_to_lms_server(server_address)

    async def get_lms_status(self) -> dict[str, Any]:  # type: ignore[override]
        """Get comprehensive LMS integration status.

        Returns:
            Dict containing current LMS status:
            - connection_state: Human-readable connection state
            - connected_server: Currently connected server
            - default_server: Auto-connect server
            - auto_connect_enabled: Whether auto-connect is enabled
            - discovered_servers: List of all discovered servers
            - is_connected: Boolean connection status
        """
        try:
            state = await self.get_squeezelite_state()

            return {
                "connection_state": await self.get_connection_state(),
                "connected_server": str(state.get("connected_server", "")),
                "default_server": str(state.get("default_server", "")),
                "auto_connect_enabled": await self.is_auto_connect_enabled(),
                "discovered_servers": await self.get_discovered_servers(),
                "is_connected": await self.is_connected_to_lms(),
            }
        except WiiMError:
            return {
                "connection_state": "unknown",
                "connected_server": "",
                "default_server": "",
                "auto_connect_enabled": False,
                "discovered_servers": [],
                "is_connected": False,
            }
