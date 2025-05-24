"""Test WiiM media player platform."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.wiim.const import DOMAIN
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import STATE_IDLE, STATE_PLAYING
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .const import MOCK_CONFIG


async def test_media_player_setup(hass, mock_wiim_client, mock_coordinator):
    """Test media player platform setup."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")

    with (
        patch("custom_components.wiim.api.WiiMClient", return_value=mock_wiim_client),
    ):
        # Setup the integration
        from custom_components.wiim import async_setup_entry

        await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()

        # Verify entity was created
        state = hass.states.get("media_player.wiim_192_168_1_100")
        assert state is not None


async def test_media_player_state_playing(hass, mock_wiim_client, mock_coordinator):
    """Test media player state when playing."""
    mock_coordinator.data = {
        "status": {"play_status": "play", "device_name": "WiiM Mini", "volume": 75}
    }

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")

    with patch("custom_components.wiim.api.WiiMClient", return_value=mock_wiim_client):
        from custom_components.wiim import async_setup_entry

        await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()

        state = hass.states.get("media_player.wiim_192_168_1_100")
        assert state.state == STATE_PLAYING


async def test_media_player_state_stopped(hass, mock_wiim_client, mock_coordinator):
    """Test media player state when stopped."""
    mock_coordinator.data = {
        "status": {"play_status": "stop", "device_name": "WiiM Mini", "volume": 50}
    }

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")

    with patch("custom_components.wiim.api.WiiMClient", return_value=mock_wiim_client):
        from custom_components.wiim import async_setup_entry

        await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()

        state = hass.states.get("media_player.wiim_192_168_1_100")
        assert state.state == STATE_IDLE


async def test_media_player_volume_level(hass, mock_wiim_client, mock_coordinator):
    """Test media player volume level property."""
    mock_coordinator.data = {"status": {"volume": 80, "device_name": "WiiM Mini"}}

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")

    with patch("custom_components.wiim.api.WiiMClient", return_value=mock_wiim_client):
        from custom_components.wiim import async_setup_entry

        await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()

        state = hass.states.get("media_player.wiim_192_168_1_100")
        assert float(state.attributes["volume_level"]) == 0.8  # 80% -> 0.8


async def test_media_player_device_info(hass, mock_wiim_client, mock_coordinator):
    """Test media player device info."""
    mock_coordinator.data = {
        "status": {
            "device_name": "WiiM Mini Kitchen",
        }
    }

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")

    with patch("custom_components.wiim.api.WiiMClient", return_value=mock_wiim_client):
        from custom_components.wiim import async_setup_entry

        await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()

        # Get the entity from device registry
        import homeassistant.helpers.device_registry as dr

        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, "192.168.1.100")}
        )
        assert device is not None
        assert device.name == "WiiM Mini Kitchen"
        assert device.manufacturer == "WiiM"
