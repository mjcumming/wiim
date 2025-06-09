"""Tests for WiiM API."""

import asyncio
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from custom_components.wiim.api import WiiMClient

from tests.const import MOCK_DEVICE_DATA, MOCK_STATUS_RESPONSE


@pytest.mark.asyncio
async def test_wiim_client_init():
    """Test WiiM client initialization."""
    client = WiiMClient("192.168.1.100")

    assert client.host == "192.168.1.100"
    assert client.port == 443  # Default HTTPS port


@pytest.mark.asyncio
async def test_get_status_success():
    """Test successful status retrieval."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method directly (async)
    with patch.object(client, "_request", new_callable=AsyncMock, return_value=MOCK_STATUS_RESPONSE) as mock_request:
        result = await client.get_player_status()
        assert "play_status" in result
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_get_device_info_success():
    """Test successful device info retrieval."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method directly (async)
    with patch.object(client, "_request", new_callable=AsyncMock, return_value=MOCK_DEVICE_DATA) as mock_request:
        result = await client.get_device_info()
        assert result == MOCK_DEVICE_DATA
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_play_command():
    """Test play command."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method directly (async)
    with patch.object(client, "_request", new_callable=AsyncMock, return_value={"raw": "OK"}) as mock_request:
        await client.play()  # Should not raise
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_pause_command():
    """Test pause command."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method directly (async)
    with patch.object(client, "_request", new_callable=AsyncMock, return_value={"raw": "OK"}) as mock_request:
        await client.pause()  # Should not raise
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_set_volume_command():
    """Test set volume command."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method directly (async)
    with patch.object(client, "_request", new_callable=AsyncMock, return_value={"raw": "OK"}) as mock_request:
        await client.set_volume(0.75)  # Should not raise
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_connection_error_handling():
    """Test connection error handling."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method to raise an exception (async)
    with patch.object(client, "_request", new_callable=AsyncMock, side_effect=aiohttp.ClientError("Connection failed")):
        with pytest.raises(aiohttp.ClientError):
            await client.get_player_status()


@pytest.mark.asyncio
async def test_timeout_error_handling():
    """Test timeout error handling."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method to raise a timeout (async)
    with patch.object(client, "_request", new_callable=AsyncMock, side_effect=asyncio.TimeoutError()):
        with pytest.raises(asyncio.TimeoutError):
            await client.get_player_status()
