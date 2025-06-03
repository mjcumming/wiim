"""Test defensive two-state polling implementation."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import timedelta

from custom_components.wiim.coordinator import WiiMCoordinator
from custom_components.wiim.api import WiiMClient
from custom_components.wiim.const import CONF_PLAYING_UPDATE_RATE, CONF_IDLE_UPDATE_RATE


@pytest.fixture
def mock_client():
    """Create a mock WiiM client."""
    client = AsyncMock(spec=WiiMClient)
    client.host = "192.168.1.100"
    client.get_player_status.return_value = {
        "play_status": "idle",
        "volume": 50,
        "title": "Test Track",
        "artist": "Test Artist",
    }
    client.get_status.return_value = {"device_name": "Test Speaker"}
    client.get_multiroom_info.return_value = {"slaves": 0}
    client.get_meta_info.return_value = {}
    client.get_eq_status.return_value = False
    return client


@pytest.fixture
def mock_entry():
    """Create a mock config entry with defensive polling options."""
    entry = AsyncMock()
    entry.options = {
        CONF_PLAYING_UPDATE_RATE: 1,  # 1 second when playing
        CONF_IDLE_UPDATE_RATE: 5,  # 5 seconds when idle
    }
    return entry


async def test_defensive_polling_idle_state(hass, mock_client, mock_entry):
    """Test that defensive polling uses slow interval when idle."""
    coordinator = WiiMCoordinator(
        hass=hass,
        client=mock_client,
        entry=mock_entry,
        poll_interval=5,
    )

    # Mock idle state
    mock_client.get_player_status.return_value = {"play_status": "idle"}

    # Perform update and get returned data
    data = await coordinator._async_update_data()

    # Should use idle interval (5 seconds)
    assert coordinator.update_interval == timedelta(seconds=5)
    assert data["polling"]["is_playing"] is False
    assert data["polling"]["interval"] == 5


async def test_defensive_polling_playing_state(hass, mock_client, mock_entry):
    """Test that defensive polling uses fast interval when playing."""
    coordinator = WiiMCoordinator(
        hass=hass,
        client=mock_client,
        entry=mock_entry,
        poll_interval=5,
    )

    # Mock playing state
    mock_client.get_player_status.return_value = {"play_status": "play"}

    # Perform update and get returned data
    data = await coordinator._async_update_data()

    # Should use playing interval (1 second)
    assert coordinator.update_interval == timedelta(seconds=1)
    assert data["polling"]["is_playing"] is True
    assert data["polling"]["interval"] == 1


async def test_api_capability_probing(hass, mock_client, mock_entry):
    """Test that API capabilities are probed and remembered."""
    coordinator = WiiMCoordinator(
        hass=hass,
        client=mock_client,
        entry=mock_entry,
        poll_interval=5,
    )

    # First update - capabilities unknown
    assert coordinator._statusex_supported is None
    assert coordinator._metadata_supported is None
    assert coordinator._eq_supported is None

    # Mock getStatusEx working
    data = await coordinator._async_update_data()

    # Capabilities should be determined
    capabilities = data["polling"]["api_capabilities"]
    assert "statusex_supported" in capabilities
    assert "metadata_supported" in capabilities
    assert "eq_supported" in capabilities


async def test_graceful_api_failures(hass, mock_client, mock_entry):
    """Test that API failures are handled gracefully."""
    coordinator = WiiMCoordinator(
        hass=hass,
        client=mock_client,
        entry=mock_entry,
        poll_interval=5,
    )

    # Mock getMetaInfo failing
    from custom_components.wiim.api import WiiMError

    mock_client.get_meta_info.side_effect = WiiMError("Not supported")

    # Should not crash
    await coordinator._async_update_data()

    # Should mark metadata as unsupported
    assert coordinator._metadata_supported is False


async def test_user_command_triggers_immediate_refresh(hass, mock_client, mock_entry):
    """Test that user commands trigger immediate polling refresh."""
    coordinator = WiiMCoordinator(
        hass=hass,
        client=mock_client,
        entry=mock_entry,
        poll_interval=5,
    )

    # Set longer interval
    coordinator.update_interval = timedelta(seconds=30)

    # Record user command
    coordinator.record_user_command("play")

    # Should force immediate polling
    assert coordinator.update_interval == timedelta(seconds=1)


async def test_device_info_update_throttling(hass, mock_client, mock_entry):
    """Test that device info updates are throttled properly."""
    coordinator = WiiMCoordinator(
        hass=hass,
        client=mock_client,
        entry=mock_entry,
        poll_interval=5,
    )

    # First update should fetch device info
    assert coordinator._should_update_device_info() is True

    # Immediate second check should be throttled
    assert coordinator._should_update_device_info() is False


async def test_track_change_detection(hass, mock_client, mock_entry):
    """Test that track changes are detected properly."""
    coordinator = WiiMCoordinator(
        hass=hass,
        client=mock_client,
        entry=mock_entry,
        poll_interval=5,
    )

    # First status
    status1 = {"title": "Track 1", "artist": "Artist 1"}
    assert coordinator._track_changed(status1) is True

    # Same track
    status2 = {"title": "Track 1", "artist": "Artist 1"}
    assert coordinator._track_changed(status2) is False

    # Different track
    status3 = {"title": "Track 2", "artist": "Artist 1"}
    assert coordinator._track_changed(status3) is True


async def test_backoff_on_failures(hass, mock_client, mock_entry):
    """Test that consecutive failures trigger backoff."""
    coordinator = WiiMCoordinator(
        hass=hass,
        client=mock_client,
        entry=mock_entry,
        poll_interval=5,
    )

    # Mock failures
    from custom_components.wiim.api import WiiMError

    mock_client.get_player_status.side_effect = WiiMError("Connection failed")

    # Multiple failures should trigger backoff
    coordinator._consecutive_failures = 3

    try:
        await coordinator._async_update_data()
    except Exception:
        pass

    # Should have longer interval due to backoff
    assert coordinator.update_interval.total_seconds() > 5
