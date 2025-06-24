"""Test adaptive polling functionality."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.wiim.coordinator_polling import (
    FAST_POLL_INTERVAL,
    NORMAL_POLL_INTERVAL,
    _determine_adaptive_interval,
)
from custom_components.wiim.models import PlayerStatus


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for adaptive polling testing."""
    coordinator = MagicMock()
    coordinator.client = MagicMock()
    coordinator.client.host = "192.168.1.100"
    coordinator.hass = MagicMock()
    coordinator.entry = MagicMock()
    return coordinator


def test_adaptive_polling_playing_device():
    """Test that adaptive polling returns 1 second when device is playing."""
    mock_coordinator = MagicMock()
    status_model = PlayerStatus.model_validate({"status": "play", "play_state": "play", "vol": 50})
    role = "solo"

    interval = _determine_adaptive_interval(mock_coordinator, status_model, role)

    assert interval == FAST_POLL_INTERVAL  # 1 second


def test_adaptive_polling_idle_device():
    """Test that adaptive polling returns 5 seconds when device is idle."""
    mock_coordinator = MagicMock()
    status_model = PlayerStatus.model_validate({"status": "stop", "play_state": "stop", "vol": 50})
    role = "solo"

    interval = _determine_adaptive_interval(mock_coordinator, status_model, role)

    assert interval == NORMAL_POLL_INTERVAL  # 5 seconds


def test_adaptive_polling_master_with_playing_slave():
    """Test that a master uses fast polling when a slave is playing."""
    # Mock the data helpers import and speaker registry
    with patch("custom_components.wiim.coordinator_polling.get_speaker_from_config_entry") as mock_get_speaker:
        mock_coordinator = MagicMock()
        mock_coordinator.hass = MagicMock()
        mock_coordinator.entry = MagicMock()

        # Create mock slave speaker that is playing
        mock_slave = MagicMock()
        mock_slave.name = "Kitchen Speaker"
        mock_slave.get_playback_state.return_value = "playing"

        # Create mock master speaker
        mock_master_speaker = MagicMock()
        mock_master_speaker.group_members = [mock_slave]

        mock_get_speaker.return_value = mock_master_speaker

        # Master status shows idle, but slave is playing
        status_model = PlayerStatus.model_validate({"status": "stop", "play_state": "stop", "vol": 50})
        role = "master"

        interval = _determine_adaptive_interval(mock_coordinator, status_model, role)

        assert interval == FAST_POLL_INTERVAL  # 1 second due to playing slave


def test_adaptive_polling_master_with_idle_slaves():
    """Test that a master uses normal polling when all slaves are idle."""
    with patch("custom_components.wiim.coordinator_polling.get_speaker_from_config_entry") as mock_get_speaker:
        mock_coordinator = MagicMock()
        mock_coordinator.hass = MagicMock()
        mock_coordinator.entry = MagicMock()

        # Create mock slave speaker that is idle
        mock_slave = MagicMock()
        mock_slave.name = "Kitchen Speaker"
        mock_slave.get_playback_state.return_value = "idle"

        # Create mock master speaker
        mock_master_speaker = MagicMock()
        mock_master_speaker.group_members = [mock_slave]

        mock_get_speaker.return_value = mock_master_speaker

        # Master status shows idle, and slave is also idle
        status_model = PlayerStatus.model_validate({"status": "stop", "play_state": "stop", "vol": 50})
        role = "master"

        interval = _determine_adaptive_interval(mock_coordinator, status_model, role)

        assert interval == NORMAL_POLL_INTERVAL  # 5 seconds - all idle


def test_adaptive_polling_exception_handling():
    """Test that adaptive polling gracefully handles exceptions when checking group members."""
    with patch(
        "custom_components.wiim.coordinator_polling.get_speaker_from_config_entry",
        side_effect=Exception("Registry error"),
    ):
        mock_coordinator = MagicMock()
        mock_coordinator.hass = MagicMock()
        mock_coordinator.entry = MagicMock()

        # Master status shows idle
        status_model = PlayerStatus.model_validate({"status": "stop", "play_state": "stop", "vol": 50})
        role = "master"

        interval = _determine_adaptive_interval(mock_coordinator, status_model, role)

        # Should fallback to normal polling when exception occurs
        assert interval == NORMAL_POLL_INTERVAL  # 5 seconds
