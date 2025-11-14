"""Tests for WiiM LMS (Squeezelite) API."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.wiim.api import WiiMClient
from custom_components.wiim.api_base import WiiMError


class TestLMSAPI:
    """Test cases for LMS API functionality."""

    @pytest.mark.asyncio
    async def test_get_squeezelite_state_success(self):
        """Test successful Squeezelite state retrieval."""
        client = WiiMClient("192.168.1.100")

        mock_state = {
            "default_server": "192.168.1.4:3483",
            "state": "connected",
            "discover_list": ["192.168.1.4:3483", "192.168.1.123:3483"],
            "connected_server": "192.168.1.4:3483",
            "auto_connect": 1,
        }

        with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_state) as mock_request:
            result = await client.get_squeezelite_state()
            assert result == mock_state
            mock_request.assert_called_once_with("/httpapi.asp?command=Squeezelite:getState")
            await client.close()

    @pytest.mark.asyncio
    async def test_discover_lms_servers_success(self):
        """Test LMS server discovery."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
            await client.discover_lms_servers()
            mock_request.assert_called_once_with("/httpapi.asp?command=Squeezelite:discover")
            await client.close()

    @pytest.mark.asyncio
    async def test_set_auto_connect_enabled_success(self):
        """Test setting auto-connect enabled."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
            await client.set_auto_connect_enabled(True)
            mock_request.assert_called_once_with("/httpapi.asp?command=Squeezelite:autoConnectEnable:1")
            await client.close()

    @pytest.mark.asyncio
    async def test_set_auto_connect_disabled_success(self):
        """Test setting auto-connect disabled."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
            await client.set_auto_connect_enabled(False)
            mock_request.assert_called_once_with("/httpapi.asp?command=Squeezelite:autoConnectEnable:0")
            await client.close()

    @pytest.mark.asyncio
    async def test_connect_to_lms_server_success(self):
        """Test connecting to LMS server."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
            await client.connect_to_lms_server("192.168.1.123:3483")
            mock_request.assert_called_once_with("/httpapi.asp?command=Squeezelite:connectServer:192.168.1.123:3483")
            await client.close()

    @pytest.mark.asyncio
    async def test_is_auto_connect_enabled(self):
        """Test checking auto-connect status."""
        client = WiiMClient("192.168.1.100")

        # Test enabled
        with patch.object(client, "get_squeezelite_state", new_callable=AsyncMock, return_value={"auto_connect": 1}):
            result = await client.is_auto_connect_enabled()
            assert result is True
            await client.close()

        # Test disabled
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "get_squeezelite_state", new_callable=AsyncMock, return_value={"auto_connect": 0}):
            result = await client.is_auto_connect_enabled()
            assert result is False
            await client.close()

        # Test error
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "get_squeezelite_state", new_callable=AsyncMock, side_effect=WiiMError("API Error")):
            result = await client.is_auto_connect_enabled()
            assert result is False
            await client.close()

    @pytest.mark.asyncio
    async def test_get_connected_server(self):
        """Test getting connected server."""
        client = WiiMClient("192.168.1.100")

        with patch.object(
            client,
            "get_squeezelite_state",
            new_callable=AsyncMock,
            return_value={"connected_server": "192.168.1.4:3483"},
        ):
            result = await client.get_connected_server()
            assert result == "192.168.1.4:3483"
            await client.close()

        # Test no connection
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "get_squeezelite_state", new_callable=AsyncMock, return_value={}):
            result = await client.get_connected_server()
            assert result == ""
            await client.close()

    @pytest.mark.asyncio
    async def test_get_default_server(self):
        """Test getting default server."""
        client = WiiMClient("192.168.1.100")

        with patch.object(
            client, "get_squeezelite_state", new_callable=AsyncMock, return_value={"default_server": "192.168.1.4:3483"}
        ):
            result = await client.get_default_server()
            assert result == "192.168.1.4:3483"
            await client.close()

        # Test no default
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "get_squeezelite_state", new_callable=AsyncMock, return_value={}):
            result = await client.get_default_server()
            assert result == ""
            await client.close()

    @pytest.mark.asyncio
    async def test_get_discovered_servers(self):
        """Test getting discovered servers list."""
        client = WiiMClient("192.168.1.100")

        mock_servers = ["192.168.1.4:3483", "192.168.1.123:3483"]
        with patch.object(
            client, "get_squeezelite_state", new_callable=AsyncMock, return_value={"discover_list": mock_servers}
        ):
            result = await client.get_discovered_servers()
            assert result == mock_servers
            await client.close()

        # Test empty list
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "get_squeezelite_state", new_callable=AsyncMock, return_value={"discover_list": []}):
            result = await client.get_discovered_servers()
            assert result == []
            await client.close()

        # Test missing key
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "get_squeezelite_state", new_callable=AsyncMock, return_value={}):
            result = await client.get_discovered_servers()
            assert result == []
            await client.close()

    @pytest.mark.asyncio
    async def test_get_connection_state(self):
        """Test getting human-readable connection state."""
        client = WiiMClient("192.168.1.100")

        # Test different states
        state_tests = [
            ("discovering", "Searching for servers"),
            ("connected", "Connected"),
            ("disconnected", "Disconnected"),
            ("unknown_state", "unknown_state"),
            ("", "unknown"),
        ]

        for raw_state, expected_state in state_tests:
            with patch.object(
                client, "get_squeezelite_state", new_callable=AsyncMock, return_value={"state": raw_state}
            ):
                result = await client.get_connection_state()
                assert result == expected_state

            await client.close()
            client = WiiMClient("192.168.1.100")

        # Test error
        with patch.object(client, "get_squeezelite_state", new_callable=AsyncMock, side_effect=WiiMError("API Error")):
            result = await client.get_connection_state()
            assert result == "unknown"
            await client.close()

    @pytest.mark.asyncio
    async def test_is_connected_to_lms(self):
        """Test checking LMS connection status."""
        client = WiiMClient("192.168.1.100")

        # Test connected
        with patch.object(client, "get_squeezelite_state", new_callable=AsyncMock, return_value={"state": "connected"}):
            result = await client.is_connected_to_lms()
            assert result is True
            await client.close()

        # Test not connected
        client = WiiMClient("192.168.1.100")
        with patch.object(
            client, "get_squeezelite_state", new_callable=AsyncMock, return_value={"state": "discovering"}
        ):
            result = await client.is_connected_to_lms()
            assert result is False
            await client.close()

        # Test error
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "get_squeezelite_state", new_callable=AsyncMock, side_effect=WiiMError("API Error")):
            result = await client.is_connected_to_lms()
            assert result is False
            await client.close()

    @pytest.mark.asyncio
    async def test_setup_lms_connection(self):
        """Test complete LMS connection setup."""
        client = WiiMClient("192.168.1.100")

        with (
            patch.object(client, "set_auto_connect_enabled", new_callable=AsyncMock) as mock_auto_connect,
            patch.object(client, "connect_to_lms_server", new_callable=AsyncMock) as mock_connect,
        ):
            await client.setup_lms_connection("192.168.1.123:3483", auto_connect=True)

            mock_auto_connect.assert_called_once_with(True)
            mock_connect.assert_called_once_with("192.168.1.123:3483")

            await client.close()

    @pytest.mark.asyncio
    async def test_setup_lms_connection_no_auto_connect(self):
        """Test LMS setup without auto-connect."""
        client = WiiMClient("192.168.1.100")

        with (
            patch.object(client, "set_auto_connect_enabled", new_callable=AsyncMock) as mock_auto_connect,
            patch.object(client, "connect_to_lms_server", new_callable=AsyncMock) as mock_connect,
        ):
            await client.setup_lms_connection("192.168.1.123:3483", auto_connect=False)

            mock_auto_connect.assert_called_once_with(False)
            mock_connect.assert_called_once_with("192.168.1.123:3483")

            await client.close()

    @pytest.mark.asyncio
    async def test_get_lms_status(self):
        """Test comprehensive LMS status."""
        client = WiiMClient("192.168.1.100")

        mock_state = {
            "state": "connected",
            "connected_server": "192.168.1.4:3483",
            "default_server": "192.168.1.4:3483",
            "auto_connect": 1,
            "discover_list": ["192.168.1.4:3483"],
        }

        with (
            patch.object(
                client, "get_squeezelite_state", new_callable=AsyncMock, return_value=mock_state
            ) as mock_state,
            patch.object(client, "get_connection_state", new_callable=AsyncMock, return_value="Connected"),
            patch.object(client, "is_auto_connect_enabled", new_callable=AsyncMock, return_value=True),
            patch.object(client, "get_discovered_servers", new_callable=AsyncMock, return_value=["192.168.1.4:3483"]),
            patch.object(client, "is_connected_to_lms", new_callable=AsyncMock, return_value=True),
        ):
            result = await client.get_lms_status()

            assert result["connection_state"] == "Connected"
            assert result["connected_server"] == "192.168.1.4:3483"
            assert result["default_server"] == "192.168.1.4:3483"
            assert result["auto_connect_enabled"] is True
            assert result["discovered_servers"] == ["192.168.1.4:3483"]
            assert result["is_connected"] is True

            await client.close()

    @pytest.mark.asyncio
    async def test_get_lms_status_error(self):
        """Test LMS status with API errors."""
        client = WiiMClient("192.168.1.100")

        with patch.object(client, "get_squeezelite_state", new_callable=AsyncMock, side_effect=WiiMError("API Error")):
            result = await client.get_lms_status()

            assert result["connection_state"] == "unknown"
            assert result["connected_server"] == ""
            assert result["default_server"] == ""
            assert result["auto_connect_enabled"] is False
            assert result["discovered_servers"] == []
            assert result["is_connected"] is False

            await client.close()

    @pytest.mark.asyncio
    async def test_lms_error_handling(self):
        """Test LMS API error handling."""
        client = WiiMClient("192.168.1.100")

        # Test discovery error
        with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("Discovery Error")):
            with pytest.raises(WiiMError):
                await client.discover_lms_servers()
            await client.close()

        # Test connection error
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("Connection Error")):
            with pytest.raises(WiiMError):
                await client.connect_to_lms_server("192.168.1.123:3483")
            await client.close()

        # Test auto-connect error
        client = WiiMClient("192.168.1.100")
        with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("Auto-connect Error")):
            with pytest.raises(WiiMError):
                await client.set_auto_connect_enabled(True)
            await client.close()
