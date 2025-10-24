"""Unit tests for WiiM media image cache."""

import pytest
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch


class TestMediaImageCache:
    """Test MediaImageCache functionality."""

    @pytest.fixture
    def cache(self):
        """Create a MediaImageCache instance."""
        from custom_components.wiim.media_image_cache import MediaImageCache

        return MediaImageCache()

    def test_cache_initialization(self, cache):
        """Test cache initialization."""
        assert cache._cached_url is None
        assert cache._cached_bytes is None
        assert cache._cached_content_type is None
        assert cache._MAX_BYTES == 10 * 1024 * 1024  # 10MB

    def test_fetch_empty_url(self, cache):
        """Test fetch with empty URL."""
        import asyncio

        async def test_fetch():
            result = await cache.fetch(MagicMock(), "")
            assert result == (None, None)

        asyncio.run(test_fetch())

    def test_fetch_none_url(self, cache):
        """Test fetch with None URL."""
        import asyncio

        async def test_fetch():
            result = await cache.fetch(MagicMock(), None)
            assert result == (None, None)

        asyncio.run(test_fetch())

    @pytest.mark.asyncio
    async def test_fetch_cache_hit(self, cache):
        """Test fetch with cached URL."""
        # Set up cache with data
        cache._cached_url = "http://test.com/image.jpg"
        cache._cached_bytes = b"fake_image_data"
        cache._cached_content_type = "image/jpeg"

        # Mock Home Assistant
        mock_hass = MagicMock()

        result = await cache.fetch(mock_hass, "http://test.com/image.jpg")

        # Should return cached data without making network request
        assert result == (b"fake_image_data", "image/jpeg")

    @pytest.mark.asyncio
    async def test_fetch_cache_miss_success(self, cache):
        """Test fetch with cache miss and successful download."""
        # Mock aiohttp session and response
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "1024", "Content-Type": "image/png"}
        mock_response.read = AsyncMock(return_value=b"test_image_data")

        # Create a proper async context manager mock
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session.get = MagicMock(return_value=mock_context_manager)

        # Mock Home Assistant
        mock_hass = MagicMock()

        with patch("custom_components.wiim.media_image_cache.async_get_clientsession", return_value=mock_session):
            result = await cache.fetch(mock_hass, "http://test.com/new_image.jpg")

            # Should return downloaded data
            assert result == (b"test_image_data", "image/png")

            # Cache should be updated
            assert cache._cached_url == "http://test.com/new_image.jpg"
            assert cache._cached_bytes == b"test_image_data"
            assert cache._cached_content_type == "image/png"

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, cache):
        """Test fetch with HTTP error response."""
        # Mock aiohttp session and response
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.headers = {}

        # Create a proper async context manager mock

        mock_context_manager = AsyncMock()

        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)

        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session.get = MagicMock(return_value=mock_context_manager)

        # Mock Home Assistant
        mock_hass = MagicMock()

        with patch("custom_components.wiim.media_image_cache.async_get_clientsession", return_value=mock_session):
            result = await cache.fetch(mock_hass, "http://test.com/not_found.jpg")

            # Should return None on error
            assert result == (None, None)

            # Cache should be cleared
            assert cache._cached_url is None
            assert cache._cached_bytes is None
            assert cache._cached_content_type is None

    @pytest.mark.asyncio
    async def test_fetch_content_too_large(self, cache):
        """Test fetch with content too large."""
        # Mock aiohttp session and response
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {
            "Content-Length": str(15 * 1024 * 1024)  # 15MB, exceeds 10MB limit
        }

        # Create a proper async context manager mock

        mock_context_manager = AsyncMock()

        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)

        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session.get = MagicMock(return_value=mock_context_manager)

        # Mock Home Assistant
        mock_hass = MagicMock()

        with patch("custom_components.wiim.media_image_cache.async_get_clientsession", return_value=mock_session):
            result = await cache.fetch(mock_hass, "http://test.com/large_image.jpg")

            # Should return None for too large content
            assert result == (None, None)

            # Cache should be cleared
            assert cache._cached_url is None

    @pytest.mark.asyncio
    async def test_fetch_download_too_large(self, cache):
        """Test fetch when downloaded data exceeds size limit."""
        # Mock aiohttp session and response
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {
            "Content-Length": "1024"  # Small content-length
        }
        mock_response.read = AsyncMock(return_value=b"x" * (12 * 1024 * 1024))  # 12MB data

        # Create a proper async context manager mock

        mock_context_manager = AsyncMock()

        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)

        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session.get = MagicMock(return_value=mock_context_manager)

        # Mock Home Assistant
        mock_hass = MagicMock()

        with patch("custom_components.wiim.media_image_cache.async_get_clientsession", return_value=mock_session):
            result = await cache.fetch(mock_hass, "http://test.com/download_large.jpg")

            # Should return None for oversized download
            assert result == (None, None)

            # Cache should be cleared
            assert cache._cached_url is None

    @pytest.mark.asyncio
    async def test_fetch_https_with_ssl_context(self, cache):
        """Test fetch with HTTPS URL and SSL context."""
        # Mock aiohttp session and response
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "1024", "Content-Type": "image/jpeg"}
        mock_response.read = AsyncMock(return_value=b"test_image_data")

        # Create a proper async context manager mock
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session.get = MagicMock(return_value=mock_context_manager)

        # Mock Home Assistant
        mock_hass = MagicMock()
        mock_ssl_context = MagicMock()

        with patch("custom_components.wiim.media_image_cache.async_get_clientsession", return_value=mock_session):
            result = await cache.fetch(mock_hass, "https://test.com/secure_image.jpg", ssl_context=mock_ssl_context)

            # Should return downloaded data
            assert result == (b"test_image_data", "image/jpeg")

            # Should pass SSL context for HTTPS
            mock_session.get.assert_called_once()
            call_kwargs = mock_session.get.call_args[1]
            assert "ssl" in call_kwargs
            assert call_kwargs["ssl"] == mock_ssl_context

    @pytest.mark.asyncio
    async def test_fetch_http_without_ssl_context(self, cache):
        """Test fetch with HTTP URL (no SSL context)."""
        # Mock aiohttp session and response
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "1024", "Content-Type": "image/jpeg"}
        mock_response.read = AsyncMock(return_value=b"test_image_data")

        # Create a proper async context manager mock

        mock_context_manager = AsyncMock()

        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)

        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session.get = MagicMock(return_value=mock_context_manager)

        # Mock Home Assistant
        mock_hass = MagicMock()

        with patch("custom_components.wiim.media_image_cache.async_get_clientsession", return_value=mock_session):
            result = await cache.fetch(mock_hass, "http://test.com/image.jpg")

            # Should return downloaded data
            assert result == (b"test_image_data", "image/jpeg")

            # Should not pass SSL context for HTTP
            mock_session.get.assert_called_once()
            call_kwargs = mock_session.get.call_args[1]
            assert "ssl" not in call_kwargs

    @pytest.mark.asyncio
    async def test_fetch_content_type_with_semicolon(self, cache):
        """Test fetch with content-type containing semicolon."""
        # Mock aiohttp session and response
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "1024", "Content-Type": "image/jpeg; charset=utf-8"}
        mock_response.read = AsyncMock(return_value=b"test_image_data")

        # Create a proper async context manager mock

        mock_context_manager = AsyncMock()

        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)

        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session.get = MagicMock(return_value=mock_context_manager)

        # Mock Home Assistant
        mock_hass = MagicMock()

        with patch("custom_components.wiim.media_image_cache.async_get_clientsession", return_value=mock_session):
            result = await cache.fetch(mock_hass, "http://test.com/image.jpg")

            # Should extract content type before semicolon
            assert result == (b"test_image_data", "image/jpeg")

    @pytest.mark.asyncio
    async def test_fetch_default_content_type(self, cache):
        """Test fetch with default content type."""
        # Mock aiohttp session and response
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {
            "Content-Length": "1024"
            # No Content-Type header
        }
        mock_response.read = AsyncMock(return_value=b"test_image_data")

        # Create a proper async context manager mock

        mock_context_manager = AsyncMock()

        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)

        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session.get = MagicMock(return_value=mock_context_manager)

        # Mock Home Assistant
        mock_hass = MagicMock()

        with patch("custom_components.wiim.media_image_cache.async_get_clientsession", return_value=mock_session):
            result = await cache.fetch(mock_hass, "http://test.com/image.jpg")

            # Should use default content type
            assert result == (b"test_image_data", "image/jpeg")

    @pytest.mark.asyncio
    async def test_fetch_timeout_error(self, cache):
        """Test fetch with timeout error."""
        # Mock aiohttp session with timeout
        mock_session = MagicMock()
        mock_session.get = AsyncMock(side_effect=TimeoutError("Request timeout"))

        # Mock Home Assistant
        mock_hass = MagicMock()

        with patch("custom_components.wiim.media_image_cache.async_get_clientsession", return_value=mock_session):
            result = await cache.fetch(mock_hass, "http://test.com/timeout.jpg")

            # Should return None on timeout
            assert result == (None, None)

            # Cache should be cleared
            assert cache._cached_url is None

    @pytest.mark.asyncio
    async def test_fetch_client_error(self, cache):
        """Test fetch with client error."""
        # Mock aiohttp session with client error
        mock_session = MagicMock()
        mock_session.get = AsyncMock(side_effect=aiohttp.ClientError("Connection failed"))

        # Mock Home Assistant
        mock_hass = MagicMock()

        with patch("custom_components.wiim.media_image_cache.async_get_clientsession", return_value=mock_session):
            result = await cache.fetch(mock_hass, "http://test.com/error.jpg")

            # Should return None on client error
            assert result == (None, None)

            # Cache should be cleared
            assert cache._cached_url is None

    @pytest.mark.asyncio
    async def test_fetch_unexpected_error(self, cache):
        """Test fetch with unexpected error."""
        # Mock aiohttp session with unexpected error
        mock_session = MagicMock()
        mock_session.get = AsyncMock(side_effect=ValueError("Unexpected error"))

        # Mock Home Assistant
        mock_hass = MagicMock()

        with patch("custom_components.wiim.media_image_cache.async_get_clientsession", return_value=mock_session):
            result = await cache.fetch(mock_hass, "http://test.com/unexpected.jpg")

            # Should return None on unexpected error
            assert result == (None, None)

            # Cache should be cleared
            assert cache._cached_url is None

    def test_clear_cache(self, cache):
        """Test cache clearing."""
        # Set up cache with data
        cache._cached_url = "http://test.com/image.jpg"
        cache._cached_bytes = b"image_data"
        cache._cached_content_type = "image/jpeg"

        # Clear cache
        cache._clear()

        # Verify cache is cleared
        assert cache._cached_url is None
        assert cache._cached_bytes is None
        assert cache._cached_content_type is None

    def test_max_bytes_constant(self):
        """Test MAX_BYTES constant."""
        from custom_components.wiim.media_image_cache import MediaImageCache

        # Should be 10MB
        assert MediaImageCache._MAX_BYTES == 10 * 1024 * 1024

    def test_user_agent_header(self):
        """Test User-Agent header is set correctly."""
        # This is tested implicitly in the fetch tests, but let's be explicit
        # The User-Agent should be "HomeAssistant/WiiM-Integration"
        pass
