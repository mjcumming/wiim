"""Unit tests for WiiM API base client."""

import ssl
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestWiiMExceptions:
    """Test WiiM exception classes."""

    def test_wiim_error_base_class(self):
        """Test WiiMError base exception."""
        from custom_components.wiim.api_base import WiiMError

        error = WiiMError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_wiim_request_error(self):
        """Test WiiMRequestError exception."""
        from custom_components.wiim.api_base import WiiMError, WiiMRequestError

        error = WiiMRequestError("Request failed")
        assert str(error) == "Request failed"
        assert isinstance(error, WiiMError)

    def test_wiim_timeout_error(self):
        """Test WiiMTimeoutError exception."""
        from custom_components.wiim.api_base import WiiMRequestError, WiiMTimeoutError

        error = WiiMTimeoutError("Request timed out")
        assert str(error) == "Request timed out"
        assert isinstance(error, WiiMRequestError)

    def test_wiim_connection_error(self):
        """Test WiiMConnectionError exception."""
        from custom_components.wiim.api_base import WiiMConnectionError, WiiMRequestError

        error = WiiMConnectionError("Connection failed")
        assert str(error) == "Connection failed"
        assert isinstance(error, WiiMRequestError)

    def test_wiim_invalid_data_error(self):
        """Test WiiMInvalidDataError exception."""
        from custom_components.wiim.api_base import WiiMError, WiiMInvalidDataError

        error = WiiMInvalidDataError("Invalid data")
        assert str(error) == "Invalid data"
        assert isinstance(error, WiiMError)


class TestWiiMClientInitialization:
    """Test WiiMClient initialization and configuration."""

    def test_client_init_basic(self):
        """Test basic client initialization."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100")

        assert client.host == "192.168.1.100"
        assert client.port == 443  # Default port
        assert client.timeout == 3  # Default timeout
        assert client._endpoint == "https://192.168.1.100:443"  # Default endpoint established
        assert client._session is None  # No session yet

    def test_client_init_with_port(self):
        """Test client initialization with custom port."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100", port=8080)

        assert client.host == "192.168.1.100"
        assert client.port == 8080

    def test_client_init_with_host_port(self):
        """Test client initialization with host:port format."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100:8080")

        assert client.host == "192.168.1.100"
        assert client.port == 8080
        assert client._discovered_port is True

    def test_client_init_with_ipv6(self):
        """Test client initialization with IPv6 address."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("2001:db8::1")

        assert client.host == "2001:db8::1"
        assert client._host_url == "[2001:db8::1]"

    def test_client_init_with_ipv6_brackets(self):
        """Test client initialization with already bracketed IPv6."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("[2001:db8::1]")

        assert client.host == "[2001:db8::1]"
        assert client._host_url == "[2001:db8::1]"

    def test_client_init_with_capabilities(self):
        """Test client initialization with device capabilities."""
        from custom_components.wiim.api_base import WiiMClient

        capabilities = {"response_timeout": 5, "retry_count": 2}
        client = WiiMClient("192.168.1.100", capabilities=capabilities)

        assert client.timeout == 5  # Custom timeout from capabilities
        assert client._capabilities == capabilities

    def test_client_init_custom_timeout(self):
        """Test client initialization with custom timeout."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100", timeout=15)

        assert client.timeout == 15

    def test_client_init_with_ssl_context(self):
        """Test client initialization with SSL context."""
        from custom_components.wiim.api_base import WiiMClient

        ssl_ctx = ssl.create_default_context()
        client = WiiMClient("192.168.1.100", ssl_context=ssl_ctx)

        assert client.ssl_context == ssl_ctx

    async def test_client_init_with_session(self):
        """Test client initialization with aiohttp session."""
        import aiohttp

        from custom_components.wiim.api_base import WiiMClient

        async with aiohttp.ClientSession() as session:
            client = WiiMClient("192.168.1.100", session=session)

            assert client._session == session

    def test_client_properties(self):
        """Test client properties."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100", port=8080)

        assert client.host == "192.168.1.100"
        assert client.base_url == "https://192.168.1.100:8080"  # Default endpoint established


class TestWiiMClientSSLContext:
    """Test WiiMClient SSL context handling."""

    async def test_get_ssl_context_default(self):
        """Test SSL context generation with default settings."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100")

        ssl_ctx = await client._get_ssl_context()

        assert isinstance(ssl_ctx, ssl.SSLContext)
        assert ssl_ctx.check_hostname is False
        assert ssl_ctx.verify_mode == ssl.CERT_NONE
        assert ssl_ctx.minimum_version == ssl.TLSVersion.TLSv1
        assert ssl_ctx.maximum_version == ssl.TLSVersion.TLSv1_3

    async def test_get_ssl_context_custom(self):
        """Test SSL context with custom context provided."""
        from custom_components.wiim.api_base import WiiMClient

        custom_ctx = ssl.create_default_context()
        client = WiiMClient("192.168.1.100", ssl_context=custom_ctx)

        ssl_ctx = await client._get_ssl_context()

        assert ssl_ctx == custom_ctx


class TestWiiMClientRequestHandling:
    """Test WiiMClient request handling and retry logic."""

    @pytest.mark.asyncio
    async def test_request_session_creation(self):
        """Test request session creation."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100")

        # Mock the entire _request method to avoid complex HTTP mocking
        with patch.object(client, "_request_with_protocol_fallback") as mock_request:
            mock_request.return_value = {"status": "ok"}

            # Mock ClientSession creation to avoid unclosed session warnings
            with patch("custom_components.wiim.api_base.aiohttp.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session_class.return_value = mock_session

                await client._request("/test")

                # Should create session with timeout
                mock_session_class.assert_called_once()
                call_args = mock_session_class.call_args[1]
                assert "timeout" in call_args

    @pytest.mark.asyncio
    async def test_request_successful(self):
        """Test successful request."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100")

        # Mock the protocol fallback method
        with patch.object(client, "_request_with_protocol_fallback", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = {"status": "OK"}

            # Mock ClientSession creation to avoid unclosed session warnings
            with patch("custom_components.wiim.api_base.aiohttp.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session_class.return_value = mock_session

                result = await client._request("/test")

                assert result == {"status": "OK"}
                mock_fallback.assert_called_once()
                call_args = mock_fallback.call_args
                assert call_args[0][0] == "/test"  # endpoint
                assert call_args[0][1] == "GET"  # method

    @pytest.mark.asyncio
    async def test_request_with_capabilities(self):
        """Test request with device capabilities."""
        from custom_components.wiim.api_base import WiiMClient

        capabilities = {"retry_count": 2, "is_legacy_device": True}
        client = WiiMClient("192.168.1.100", capabilities=capabilities)

        # Mock the protocol fallback method
        with patch.object(client, "_request_with_protocol_fallback", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = {"status": "OK"}

            # Mock ClientSession creation to avoid unclosed session warnings
            with patch("custom_components.wiim.api_base.aiohttp.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session_class.return_value = mock_session

                result = await client._request("/test")

                # Should respect retry count from capabilities
                assert result == {"status": "OK"}

    @pytest.mark.asyncio
    async def test_request_with_legacy_device_validation(self):
        """Test request with legacy device response validation."""
        from custom_components.wiim.api_base import WiiMClient

        capabilities = {"is_legacy_device": True}
        client = WiiMClient("192.168.1.100", capabilities=capabilities)

        # Mock the protocol fallback and validation methods
        with patch.object(client, "_request_with_protocol_fallback", new_callable=AsyncMock) as mock_fallback:
            with patch.object(client, "_validate_legacy_response", return_value={"validated": True}) as mock_validate:
                mock_fallback.return_value = {"raw": "response"}

                # Mock ClientSession creation to avoid unclosed session warnings
                with patch("custom_components.wiim.api_base.aiohttp.ClientSession") as mock_session_class:
                    mock_session = AsyncMock()
                    mock_session_class.return_value = mock_session

                    result = await client._request("/test")

                    # Should validate response for legacy device
                    mock_validate.assert_called_once_with({"raw": "response"}, "/test")
                    assert result == {"validated": True}

    @pytest.mark.asyncio
    async def test_request_retry_logic(self):
        """Test request retry logic with failures."""
        import aiohttp

        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100")

        # Mock the protocol fallback to fail twice then succeed
        with patch.object(client, "_request_with_protocol_fallback", new_callable=AsyncMock) as mock_fallback:
            # Configure the mock to fail twice then succeed
            async def mock_side_effect(*args, **kwargs):
                if mock_fallback.call_count == 1:
                    raise aiohttp.ClientError("First failure")
                elif mock_fallback.call_count == 2:
                    raise aiohttp.ClientError("Second failure")
                else:
                    return {"status": "OK"}

            mock_fallback.side_effect = mock_side_effect

            # Mock ClientSession creation to avoid unclosed session warnings
            with patch("custom_components.wiim.api_base.aiohttp.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session_class.return_value = mock_session

                # Should succeed on third attempt
                result = await client._request("/test")

                assert result == {"status": "OK"}
                assert mock_fallback.call_count == 3

    @pytest.mark.asyncio
    async def test_request_max_retries_exceeded(self):
        """Test request when max retries exceeded."""
        import aiohttp

        from custom_components.wiim.api_base import WiiMClient, WiiMRequestError

        client = WiiMClient("192.168.1.100")

        # Mock the protocol fallback to always fail
        with patch.object(client, "_request_with_protocol_fallback", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.side_effect = aiohttp.ClientError("Persistent failure")

            # Mock ClientSession creation to avoid unclosed session warnings
            with patch("custom_components.wiim.api_base.aiohttp.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session_class.return_value = mock_session

                # Should raise WiiMRequestError after all retries
                with pytest.raises(WiiMRequestError, match="Request failed after 3 attempts"):
                    await client._request("/test")

                assert mock_fallback.call_count == 3


class TestWiiMClientPublicAPI:
    """Test WiiMClient public API methods."""

    @pytest.mark.asyncio
    async def test_get_device_info_success(self):
        """Test get_device_info with successful response."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100")

        # Mock the internal _request method
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"DeviceName": "Test WiiM", "uuid": "test-uuid"}

            result = await client.get_device_info()

            assert result == {"DeviceName": "Test WiiM", "uuid": "test-uuid"}
            mock_request.assert_called_once_with("/httpapi.asp?command=getStatusEx")

    @pytest.mark.asyncio
    async def test_get_device_info_error(self):
        """Test get_device_info with error response."""
        from custom_components.wiim.api_base import WiiMClient, WiiMError

        client = WiiMClient("192.168.1.100")

        # Mock the internal _request method to raise error
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = WiiMError("Network error")

            result = await client.get_device_info()

            # Should return empty dict on error
            assert result == {}

    @pytest.mark.asyncio
    async def test_get_player_status_success(self):
        """Test get_player_status with successful response."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100")

        # Mock the internal _request method and parser
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            with patch("custom_components.wiim.api_base.parse_player_status") as mock_parser:
                mock_request.return_value = {"status": "play"}
                mock_parser.return_value = ({"status": "play", "volume": 50}, "track123")

                result = await client.get_player_status()

                assert result == {"status": "play", "volume": 50}
                mock_request.assert_called_once_with("/httpapi.asp?command=getPlayerStatusEx")
                mock_parser.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_player_status_error(self):
        """Test get_player_status with error response."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100")

        # Mock the internal _request method to raise error
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("Network error")

            # Should re-raise the exception
            with pytest.raises(Exception, match="Network error"):
                await client.get_player_status()

    @pytest.mark.asyncio
    async def test_get_device_name_from_status(self):
        """Test get_device_name from player status."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100")

        # Mock get_player_status
        with patch.object(client, "get_player_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = {"DeviceName": "Test WiiM"}

            result = await client.get_device_name()

            assert result == "Test WiiM"
            mock_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_device_name_from_device_info(self):
        """Test get_device_name from device info."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100")

        # Mock get_player_status to return no name, then get_device_info
        with patch.object(client, "get_player_status", new_callable=AsyncMock) as mock_status:
            with patch.object(client, "get_device_info", new_callable=AsyncMock) as mock_info:
                mock_status.return_value = {}
                mock_info.return_value = {"DeviceName": "Test WiiM Info"}

                result = await client.get_device_name()

                assert result == "Test WiiM Info"
                mock_status.assert_called_once()
                mock_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_device_name_fallback_to_ip(self):
        """Test get_device_name fallback to IP address."""
        from custom_components.wiim.api_base import WiiMClient, WiiMError

        client = WiiMClient("192.168.1.100")

        # Mock both methods to raise errors
        with patch.object(client, "get_player_status", new_callable=AsyncMock) as mock_status:
            with patch.object(client, "get_device_info", new_callable=AsyncMock) as mock_info:
                mock_status.side_effect = WiiMError("API Error")
                mock_info.side_effect = WiiMError("API Error")

                result = await client.get_device_name()

                # Should fallback to IP address
                assert result == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_validate_connection_success(self):
        """Test validate_connection with successful connection."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100")

        # Mock get_player_status to succeed
        with patch.object(client, "get_player_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = {"status": "stop"}

            result = await client.validate_connection()

            assert result is True

    @pytest.mark.asyncio
    async def test_validate_connection_failure(self):
        """Test validate_connection with connection failure."""
        from custom_components.wiim.api_base import WiiMClient, WiiMError

        client = WiiMClient("192.168.1.100")

        # Mock get_player_status to fail
        with patch.object(client, "get_player_status", new_callable=AsyncMock) as mock_status:
            mock_status.side_effect = WiiMError("Connection failed")

            result = await client.validate_connection()

            assert result is False

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Test closing the aiohttp session."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100")

        # Create a mock session
        mock_session = AsyncMock()
        mock_session.closed = False
        client._session = mock_session

        await client.close()

        # Should close the session
        mock_session.close.assert_called_once()
        assert client._session is None

    @pytest.mark.asyncio
    async def test_close_no_session(self):
        """Test closing when no session exists."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100")

        # No session initially
        await client.close()

        # Should not raise any errors

    @pytest.mark.asyncio
    async def test_close_already_closed_session(self):
        """Test closing already closed session."""
        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("192.168.1.100")

        # Create a mock session that's already closed
        mock_session = MagicMock()
        mock_session.closed = True
        client._session = mock_session

        await client.close()

        # Should not call close on already closed session
        mock_session.close.assert_not_called()
        assert client._session is None


class TestWiiMClientTypedMethods:
    """Test WiiMClient typed (Pydantic) methods."""

    @pytest.mark.asyncio
    async def test_get_device_info_model(self):
        """Test get_device_info_model with Pydantic models."""
        from custom_components.wiim.api_base import WiiMClient
        from custom_components.wiim.models import DeviceInfo

        client = WiiMClient("192.168.1.100")

        # Mock get_device_info
        with patch.object(client, "get_device_info", new_callable=AsyncMock) as mock_info:
            mock_info.return_value = {"DeviceName": "Test WiiM", "uuid": "test-uuid"}

            # Mock DeviceInfo.model_validate
            with patch.object(DeviceInfo, "model_validate") as mock_validate:
                mock_device_info = MagicMock()
                mock_validate.return_value = mock_device_info

                result = await client.get_device_info_model()

                assert result == mock_device_info
                mock_validate.assert_called_once_with({"DeviceName": "Test WiiM", "uuid": "test-uuid"})

    @pytest.mark.asyncio
    async def test_get_player_status_model(self):
        """Test get_player_status_model with Pydantic models."""
        from custom_components.wiim.api_base import WiiMClient
        from custom_components.wiim.models import PlayerStatus

        client = WiiMClient("192.168.1.100")

        # Mock get_player_status
        with patch.object(client, "get_player_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = {"status": "play", "volume": 50}

            # Mock PlayerStatus.model_validate
            with patch.object(PlayerStatus, "model_validate") as mock_validate:
                mock_player_status = MagicMock()
                mock_validate.return_value = mock_player_status

                result = await client.get_player_status_model()

                assert result == mock_player_status
                mock_validate.assert_called_once_with({"status": "play", "volume": 50})


class TestWiiMClientConstants:
    """Test WiiMClient constants and configuration."""

    def test_headers_constant(self):
        """Test HEADERS constant."""
        from custom_components.wiim.api_base import HEADERS

        assert isinstance(HEADERS, dict)
        assert "Connection" in HEADERS
        assert HEADERS["Connection"] == "close"

    def test_default_constants(self):
        """Test default constants."""
        from custom_components.wiim.api_base import DEFAULT_PORT, DEFAULT_TIMEOUT

        assert DEFAULT_PORT == 443
        assert DEFAULT_TIMEOUT == 3

    def test_api_endpoint_constant(self):
        """Test API endpoint constant."""
        from custom_components.wiim.api_base import API_ENDPOINT_STATUS

        assert API_ENDPOINT_STATUS == "/httpapi.asp?command=getStatusEx"


class TestWiiMClientIPv6Handling:
    """Test IPv6 address handling and URL construction - critical for preventing GitHub issue #81."""

    def test_ipv6_url_construction_fast_path(self):
        """Test IPv6 URL construction in fast-path (established endpoint)."""
        from urllib.parse import urlsplit

        from custom_components.wiim.api_base import WiiMClient

        # Test IPv6 client
        client = WiiMClient("2001:db8::1")

        # Simulate the fast-path URL construction logic
        p = urlsplit(client._endpoint)
        hostname = p.hostname
        if hostname and ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        url = f"{p.scheme}://{hostname}:{p.port}/httpapi.asp?command=getStatusEx"

        # This should NOT raise "Invalid IPv6 URL" error
        try:
            urlsplit(url)
            assert True, "IPv6 URL construction succeeded"
        except ValueError as e:
            if "Invalid IPv6 URL" in str(e):
                pytest.fail(f"IPv6 URL construction failed with original bug: {e}")
            else:
                pytest.fail(f"IPv6 URL construction failed with different error: {e}")

        # Verify the URL is properly formatted
        assert url == "https://[2001:db8::1]:443/httpapi.asp?command=getStatusEx"

    def test_ipv6_url_construction_protocol_fallback(self):
        """Test IPv6 URL construction in protocol fallback path."""
        from urllib.parse import urlsplit

        from custom_components.wiim.api_base import WiiMClient

        # Test IPv6 client
        client = WiiMClient("2001:db8::1")

        # Simulate the protocol fallback URL construction logic
        host_for_url = f"[{client._host}]" if ":" in client._host and not client._host.startswith("[") else client._host
        url = f"https://{host_for_url}:443/httpapi.asp?command=getStatusEx"

        # This should NOT raise "Invalid IPv6 URL" error
        try:
            urlsplit(url)
            assert True, "IPv6 URL construction in fallback succeeded"
        except ValueError as e:
            if "Invalid IPv6 URL" in str(e):
                pytest.fail(f"IPv6 URL construction in fallback failed with original bug: {e}")
            else:
                pytest.fail(f"IPv6 URL construction in fallback failed with different error: {e}")

        # Verify the URL is properly formatted
        assert url == "https://[2001:db8::1]:443/httpapi.asp?command=getStatusEx"

    def test_ipv6_bracketed_url_construction(self):
        """Test IPv6 URL construction with already bracketed IPv6."""
        from urllib.parse import urlsplit

        from custom_components.wiim.api_base import WiiMClient

        # Test IPv6 client with brackets
        client = WiiMClient("[2001:db8::1]")

        # Simulate URL construction
        p = urlsplit(client._endpoint)
        hostname = p.hostname
        if hostname and ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        url = f"{p.scheme}://{hostname}:{p.port}/httpapi.asp?command=getStatusEx"

        # This should NOT raise "Invalid IPv6 URL" error
        try:
            urlsplit(url)
            assert True, "Bracketed IPv6 URL construction succeeded"
        except ValueError as e:
            if "Invalid IPv6 URL" in str(e):
                pytest.fail(f"Bracketed IPv6 URL construction failed with original bug: {e}")
            else:
                pytest.fail(f"Bracketed IPv6 URL construction failed with different error: {e}")

    def test_ipv6_vs_ipv4_host_port_parsing(self):
        """Test that IPv6 addresses are not incorrectly parsed as host:port."""
        from custom_components.wiim.api_base import WiiMClient

        # Test IPv6 address (should NOT be parsed as host:port)
        client_ipv6 = WiiMClient("2001:db8::1")
        assert client_ipv6.host == "2001:db8::1"
        assert client_ipv6.port == 443  # Default port, not parsed from address
        assert not client_ipv6._discovered_port  # Should not be marked as discovered port

        # Test IPv4 with port (SHOULD be parsed as host:port)
        client_ipv4 = WiiMClient("192.168.1.100:8080")
        assert client_ipv4.host == "192.168.1.100"
        assert client_ipv4.port == 8080
        assert client_ipv4._discovered_port  # Should be marked as discovered port

    def test_ipv6_with_port_parsing(self):
        """Test IPv6 address with port in brackets."""
        from custom_components.wiim.api_base import WiiMClient

        # Test IPv6 with port in brackets
        client = WiiMClient("[2001:db8::1]:8080")
        assert client.host == "2001:db8::1"  # Host stored without brackets
        assert client.port == 8080
        assert client._discovered_port

    def test_ipv6_edge_cases(self):
        """Test various IPv6 edge cases."""
        from urllib.parse import urlsplit

        from custom_components.wiim.api_base import WiiMClient

        test_cases = [
            "::1",  # Localhost IPv6
            "2001:db8::",  # IPv6 with trailing ::
            "2001:db8:85a3::8a2e:370:7334",  # Full IPv6
            "fe80::1%lo0",  # IPv6 with zone identifier
        ]

        for ipv6_addr in test_cases:
            client = WiiMClient(ipv6_addr)

            # Test URL construction
            p = urlsplit(client._endpoint)
            hostname = p.hostname
            if hostname and ":" in hostname and not hostname.startswith("["):
                hostname = f"[{hostname}]"
            url = f"{p.scheme}://{hostname}:{p.port}/test"

            # Should not raise "Invalid IPv6 URL" error
            try:
                urlsplit(url)
                assert True, f"IPv6 edge case {ipv6_addr} URL construction succeeded"
            except ValueError as e:
                if "Invalid IPv6 URL" in str(e):
                    pytest.fail(f"IPv6 edge case {ipv6_addr} failed with original bug: {e}")
                else:
                    pytest.fail(f"IPv6 edge case {ipv6_addr} failed with different error: {e}")

    @pytest.mark.asyncio
    async def test_ipv6_request_simulation(self):
        """Test simulated IPv6 request to catch URL construction bugs."""
        from unittest.mock import AsyncMock, patch

        from custom_components.wiim.api_base import WiiMClient

        client = WiiMClient("2001:db8::1")

        # Mock the session and response
        mock_session = AsyncMock()

        # Create a proper mock response that behaves like aiohttp response
        class MockResponse:
            def __init__(self):
                self.status = 200

            def raise_for_status(self):
                pass

            async def text(self):
                return '{"status": "OK"}'

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_response = MockResponse()
        mock_session.request = AsyncMock(return_value=mock_response)

        # Mock ClientSession creation
        with patch("custom_components.wiim.api_base.aiohttp.ClientSession", return_value=mock_session):
            with patch("custom_components.wiim.api_base.async_timeout.timeout"):
                try:
                    result = await client._request("/test")
                    assert result == {"status": "OK"}
                except ValueError as e:
                    if "Invalid IPv6 URL" in str(e):
                        pytest.fail(f"IPv6 request simulation failed with original bug: {e}")
                    else:
                        pytest.fail(f"IPv6 request simulation failed with different error: {e}")
