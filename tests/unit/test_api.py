"""Tests for WiiM API."""

import asyncio
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from custom_components.wiim.api import WiiMClient
from custom_components.wiim.api_base import WiiMError
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
        await client.close()


@pytest.mark.asyncio
async def test_get_device_info_success():
    """Test successful device info retrieval."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method directly (async)
    with patch.object(client, "_request", new_callable=AsyncMock, return_value=MOCK_DEVICE_DATA) as mock_request:
        result = await client.get_device_info()
        assert result == MOCK_DEVICE_DATA
        mock_request.assert_called_once()
        await client.close()


@pytest.mark.asyncio
async def test_play_command():
    """Test play command."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method directly (async)
    with patch.object(client, "_request", new_callable=AsyncMock, return_value={"raw": "OK"}) as mock_request:
        await client.play()  # Should not raise
        mock_request.assert_called_once()
        await client.close()


@pytest.mark.asyncio
async def test_pause_command():
    """Test pause command."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method directly (async)
    with patch.object(client, "_request", new_callable=AsyncMock, return_value={"raw": "OK"}) as mock_request:
        await client.pause()  # Should not raise
        mock_request.assert_called_once()
        await client.close()


@pytest.mark.asyncio
async def test_resume_command():
    """Test resume command."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method directly (async)
    with patch.object(client, "_request", new_callable=AsyncMock, return_value={"raw": "OK"}) as mock_request:
        await client.resume()  # Should not raise
        mock_request.assert_called_once()
        # Verify it calls the correct endpoint
        mock_request.assert_called_with("/httpapi.asp?command=setPlayerCmd:resume")
        await client.close()


@pytest.mark.asyncio
async def test_set_volume_command():
    """Test set volume command."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method directly (async)
    with patch.object(client, "_request", new_callable=AsyncMock, return_value={"raw": "OK"}) as mock_request:
        await client.set_volume(0.75)  # Should not raise
        mock_request.assert_called_once()
        await client.close()


@pytest.mark.asyncio
async def test_set_source_command():
    """Test set source command."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method directly (async)
    with patch.object(client, "_request", new_callable=AsyncMock, return_value={"raw": "OK"}) as mock_request:
        await client.set_source("wifi")  # Should not raise
        mock_request.assert_called_once_with("/httpapi.asp?command=setPlayerCmd:switchmode:wifi")
        await client.close()


@pytest.mark.asyncio
async def test_set_source_different_sources():
    """Test set source command with different source types."""
    client = WiiMClient("192.168.1.100")

    test_sources = ["wifi", "bluetooth", "optical", "line_in", "arc"]

    for source in test_sources:
        # Mock the _request method directly (async)
        with patch.object(client, "_request", new_callable=AsyncMock, return_value={"raw": "OK"}) as mock_request:
            await client.set_source(source)  # Should not raise
            expected_endpoint = f"/httpapi.asp?command=setPlayerCmd:switchmode:{source}"
            mock_request.assert_called_once_with(expected_endpoint)

    await client.close()


@pytest.mark.asyncio
async def test_connection_error_handling():
    """Test connection error handling."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method to raise an exception (async)
    with patch.object(client, "_request", new_callable=AsyncMock, side_effect=aiohttp.ClientError("Connection failed")):
        with pytest.raises(aiohttp.ClientError):
            await client.get_player_status()
        await client.close()


@pytest.mark.asyncio
async def test_timeout_error_handling():
    """Test timeout error handling."""
    client = WiiMClient("192.168.1.100")

    # Mock the _request method to raise a timeout (async)
    with patch.object(client, "_request", new_callable=AsyncMock, side_effect=TimeoutError()):
        with pytest.raises(asyncio.TimeoutError):
            await client.get_player_status()
        await client.close()


# ===== UNOFFICIAL API TESTS =====


@pytest.mark.asyncio
async def test_bluetooth_api_integration():
    """Test that Bluetooth API methods are available and working."""
    client = WiiMClient("192.168.1.100")

    # Test that Bluetooth methods exist
    assert hasattr(client, "start_bluetooth_discovery")
    assert hasattr(client, "get_bluetooth_discovery_result")
    assert hasattr(client, "scan_for_bluetooth_devices")

    # Mock the _request method
    with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
        await client.start_bluetooth_discovery(3)
        mock_request.assert_called_once_with("/httpapi.asp?command=startbtdiscovery:3")

    await client.close()


@pytest.mark.asyncio
async def test_audio_settings_api_integration():
    """Test that Audio Settings API methods are available and working."""
    client = WiiMClient("192.168.1.100")

    # Test that Audio Settings methods exist
    assert hasattr(client, "get_spdif_sample_rate")
    assert hasattr(client, "set_spdif_switch_delay")
    assert hasattr(client, "get_channel_balance")
    assert hasattr(client, "set_channel_balance")

    # Test SPDIF sample rate
    with patch.object(client, "_request", new_callable=AsyncMock, return_value="48000") as mock_request:
        result = await client.get_spdif_sample_rate()
        assert result == "48000"
        mock_request.assert_called_once_with("/httpapi.asp?command=getSpdifOutSampleRate")

    # Test channel balance
    with patch.object(client, "_request", new_callable=AsyncMock, return_value="0.5") as mock_request:
        result = await client.get_channel_balance()
        assert result == 0.5
        mock_request.assert_called_once_with("/httpapi.asp?command=getChannelBalance")

    await client.close()


@pytest.mark.asyncio
async def test_lms_api_integration():
    """Test that LMS API methods are available and working."""
    client = WiiMClient("192.168.1.100")

    # Test that LMS methods exist
    assert hasattr(client, "get_squeezelite_state")
    assert hasattr(client, "discover_lms_servers")
    assert hasattr(client, "connect_to_lms_server")
    assert hasattr(client, "set_auto_connect_enabled")

    # Test LMS state
    mock_state = {"state": "connected", "connected_server": "192.168.1.4:3483"}
    with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_state) as mock_request:
        result = await client.get_squeezelite_state()
        assert result == mock_state
        mock_request.assert_called_once_with("/httpapi.asp?command=Squeezelite:getState")

    # Test LMS discovery
    with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
        await client.discover_lms_servers()
        mock_request.assert_called_once_with("/httpapi.asp?command=Squeezelite:discover")

    await client.close()


@pytest.mark.asyncio
async def test_misc_api_integration():
    """Test that Miscellaneous API methods are available and working."""
    client = WiiMClient("192.168.1.100")

    # Test that Misc methods exist
    assert hasattr(client, "set_buttons_enabled")
    assert hasattr(client, "set_led_switch")
    assert hasattr(client, "enable_touch_buttons")
    assert hasattr(client, "disable_touch_buttons")

    # Test button control
    with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
        await client.set_buttons_enabled(False)
        mock_request.assert_called_once_with("/httpapi.asp?command=Button_Enable_SET:0")

    # Test LED control
    with patch.object(client, "_request", new_callable=AsyncMock, return_value="OK") as mock_request:
        await client.set_led_switch(True)
        mock_request.assert_called_once_with("/httpapi.asp?command=LED_SWITCH_SET:1")

    await client.close()


@pytest.mark.asyncio
async def test_unofficial_api_error_handling():
    """Test error handling for unofficial API methods."""
    client = WiiMClient("192.168.1.100")

    # Test Bluetooth API error
    with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("Bluetooth Error")):
        with pytest.raises(WiiMError):
            await client.start_bluetooth_discovery(3)
        await client.close()

    # Test Audio Settings API error
    client = WiiMClient("192.168.1.100")
    with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("Audio Error")):
        with pytest.raises(WiiMError):
            await client.set_channel_balance(0.5)
        await client.close()

    # Test LMS API error
    client = WiiMClient("192.168.1.100")
    with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("LMS Error")):
        with pytest.raises(WiiMError):
            await client.discover_lms_servers()
        await client.close()

    # Test Misc API error
    client = WiiMClient("192.168.1.100")
    with patch.object(client, "_request", new_callable=AsyncMock, side_effect=WiiMError("Misc Error")):
        with pytest.raises(WiiMError):
            await client.set_buttons_enabled(True)
        await client.close()


@pytest.mark.asyncio
async def test_all_unofficial_api_methods_available():
    """Test that all unofficial API methods are properly accessible."""
    client = WiiMClient("192.168.1.100")

    # Bluetooth API methods
    bluetooth_methods = [
        "start_bluetooth_discovery",
        "get_bluetooth_discovery_result",
        "scan_for_bluetooth_devices",
        "is_bluetooth_scan_in_progress",
        "get_bluetooth_device_count",
        "get_last_bluetooth_scan_status",
    ]

    # Audio Settings API methods
    audio_methods = [
        "get_spdif_sample_rate",
        "set_spdif_switch_delay",
        "get_channel_balance",
        "set_channel_balance",
        "center_channel_balance",
        "get_spdif_sample_rate_int",
        "is_spdif_output_active",
        "get_audio_settings_status",
    ]

    # LMS API methods
    lms_methods = [
        "get_squeezelite_state",
        "discover_lms_servers",
        "set_auto_connect_enabled",
        "connect_to_lms_server",
        "is_auto_connect_enabled",
        "get_connected_server",
        "get_default_server",
        "get_discovered_servers",
        "get_connection_state",
        "is_connected_to_lms",
        "setup_lms_connection",
        "get_lms_status",
    ]

    # Misc API methods
    misc_methods = [
        "set_buttons_enabled",
        "enable_touch_buttons",
        "disable_touch_buttons",
        "set_led_switch",
        "are_touch_buttons_enabled",
        "get_device_capabilities",
        "test_misc_functionality",
    ]

    # Verify all methods exist
    all_expected_methods = bluetooth_methods + audio_methods + lms_methods + misc_methods

    for method_name in all_expected_methods:
        assert hasattr(client, method_name), f"Method {method_name} not found in WiiMClient"

    await client.close()


@pytest.mark.asyncio
async def test_client_capabilities_property():
    """Test that client properly exposes capabilities property."""
    # Test with no capabilities
    client = WiiMClient("192.168.1.100")
    assert hasattr(client, "capabilities")
    assert client.capabilities == {}
    await client.close()

    # Test with custom capabilities
    test_capabilities = {
        "supports_audio_output": True,
        "is_wiim_device": True,
        "firmware_version": "4.8.731953",
    }
    client = WiiMClient("192.168.1.100", capabilities=test_capabilities)
    assert client.capabilities == test_capabilities
    assert client.capabilities.get("supports_audio_output") is True
    assert client.capabilities.get("is_wiim_device") is True
    await client.close()
