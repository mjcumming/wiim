"""Test coordinator multiroom helpers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.wiim.coordinator_multiroom import resolve_multiroom_source_and_media
from custom_components.wiim.models import PlayerStatus


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for multiroom testing."""
    coordinator = MagicMock()
    coordinator.client = MagicMock()
    coordinator.client.host = "192.168.1.100"
    coordinator.hass = MagicMock()
    coordinator.data = {"status_model": None}
    return coordinator


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    return MagicMock()


async def test_multiroom_not_in_multiroom_mode(mock_coordinator):
    """Test that function returns early when not in multiroom mode."""
    status = PlayerStatus.model_validate({"status": "play", "vol": 50})
    metadata = {"title": "Test Track"}
    role = "solo"

    await resolve_multiroom_source_and_media(mock_coordinator, status, metadata, role)

    # Should return early without any changes
    assert status.source is None  # No source resolution attempted


async def test_multiroom_master_source_resolution(mock_coordinator):
    """Test master source resolution in multiroom mode."""
    status = PlayerStatus.model_validate({"status": "play", "vol": 50, "source": "multiroom"})
    # Set multiroom mode
    status._multiroom_mode = True

    metadata = {"title": "Test Track"}
    role = "master"

    await resolve_multiroom_source_and_media(mock_coordinator, status, metadata, role)

    # Should resolve source from multiroom to actual source
    assert status.source == "network"  # Default fallback


async def test_multiroom_master_source_spotify_detection(mock_coordinator):
    """Test master source detection for Spotify."""
    status = PlayerStatus.model_validate(
        {"status": "play", "vol": 50, "source": "multiroom", "title": "Playing on Spotify"}
    )
    status._multiroom_mode = True

    metadata = {"title": "Playing on Spotify"}
    role = "master"

    await resolve_multiroom_source_and_media(mock_coordinator, status, metadata, role)

    assert status.source == "spotify"


async def test_multiroom_master_source_wifi_with_duration(mock_coordinator):
    """Test master source detection for WiFi with duration."""
    status = PlayerStatus.model_validate(
        {"status": "play", "vol": 50, "source": "multiroom", "title": "Some Track", "duration": 180}
    )
    status._multiroom_mode = True

    metadata = {"title": "Some Track"}
    role = "master"

    await resolve_multiroom_source_and_media(mock_coordinator, status, metadata, role)

    assert status.source == "wifi"


async def test_multiroom_slave_media_mirroring_with_master_ip(mock_coordinator):
    """Test slave media mirroring when master IP is available."""
    status = PlayerStatus.model_validate({"status": "play", "vol": 50, "source": "multiroom"})
    status._multiroom_mode = True

    # Set up coordinator data with master IP
    mock_coordinator.data = {"status_model": PlayerStatus.model_validate({"master_ip": "192.168.1.200"})}

    # Mock finding master speaker
    mock_master_speaker = MagicMock()
    mock_master_speaker.role = "master"
    mock_master_speaker.coordinator.data = {
        "status_model": PlayerStatus.model_validate(
            {
                "title": "Master Track",
                "artist": "Master Artist",
                "source": "spotify",
                "play_state": "play",
                "position": 30,
                "duration": 180,
            }
        ),
        "metadata": {"entity_picture": "http://example.com/master-cover.jpg", "album": "Master Album"},
    }

    metadata = {}
    role = "slave"

    with patch("custom_components.wiim.coordinator_multiroom.find_speaker_by_ip", return_value=mock_master_speaker):
        await resolve_multiroom_source_and_media(mock_coordinator, status, metadata, role)

    # Status should be mirrored from master
    status_dict = status.model_dump(exclude_none=True)
    assert status_dict["title"] == "Master Track"
    assert status_dict["artist"] == "Master Artist"
    assert status_dict["source"] == "spotify"
    assert status_dict["play_state"] == "play"
    assert status_dict["position"] == 30
    assert status_dict["duration"] == 180

    # Metadata should be mirrored
    assert metadata["entity_picture"] == "http://example.com/master-cover.jpg"
    assert metadata["album"] == "Master Album"


async def test_multiroom_slave_fallback_to_group_search(mock_coordinator):
    """Test slave media mirroring with fallback to group member search."""
    status = PlayerStatus.model_validate({"status": "play", "vol": 50, "source": "multiroom"})
    status._multiroom_mode = True

    # No master IP in coordinator data
    mock_coordinator.data = {"status_model": None}

    # Mock master speaker found via group search
    mock_master_speaker = MagicMock()
    mock_master_speaker.role = "master"
    mock_master_speaker.ip_address = "192.168.1.200"
    mock_master_speaker.group_members = [
        MagicMock(ip_address="192.168.1.100"),  # This slave
        MagicMock(ip_address="192.168.1.101"),  # Another slave
    ]
    mock_master_speaker.coordinator.data = {
        "status_model": PlayerStatus.model_validate({"title": "Group Track", "source": "network"}),
        "metadata": {"title": "Group Track"},
    }

    mock_other_speaker = MagicMock()
    mock_other_speaker.role = "solo"

    metadata = {}
    role = "slave"

    with (
        patch("custom_components.wiim.coordinator_multiroom.find_speaker_by_ip", return_value=None),
        patch(
            "custom_components.wiim.coordinator_multiroom.get_all_speakers",
            return_value=[mock_master_speaker, mock_other_speaker],
        ),
    ):
        await resolve_multiroom_source_and_media(mock_coordinator, status, metadata, role)

    # Should mirror from found master
    status_dict = status.model_dump(exclude_none=True)
    assert status_dict["title"] == "Group Track"
    assert status_dict["source"] == "network"


async def test_multiroom_slave_no_master_found(mock_coordinator):
    """Test slave behavior when no master is found."""
    status = PlayerStatus.model_validate({"status": "play", "vol": 50, "source": "multiroom"})
    status._multiroom_mode = True

    mock_coordinator.data = {"status_model": None}

    metadata = {}
    role = "slave"

    with (
        patch("custom_components.wiim.coordinator_multiroom.find_speaker_by_ip", return_value=None),
        patch("custom_components.wiim.coordinator_multiroom.get_all_speakers", return_value=[]),
    ):
        await resolve_multiroom_source_and_media(mock_coordinator, status, metadata, role)

    # Should set source to follower when master not found
    status_dict = status.model_dump(exclude_none=True)
    assert status_dict["source"] == "follower"


async def test_multiroom_solo_device_in_multiroom_mode(mock_coordinator):
    """Test solo device behavior when in multiroom mode."""
    status = PlayerStatus.model_validate({"status": "play", "vol": 50, "source": "multiroom"})
    status._multiroom_mode = True

    metadata = {"title": "Solo Track"}
    role = "solo"

    await resolve_multiroom_source_and_media(mock_coordinator, status, metadata, role)

    # Solo device should keep multiroom source
    assert status.source == "multiroom"


async def test_multiroom_master_found_but_not_master_role(mock_coordinator):
    """Test when found speaker is not actually a master."""
    status = PlayerStatus.model_validate({"status": "play", "vol": 50, "source": "multiroom"})
    status._multiroom_mode = True

    mock_coordinator.data = {"status_model": PlayerStatus.model_validate({"master_ip": "192.168.1.200"})}

    # Found speaker is not actually a master
    mock_found_speaker = MagicMock()
    mock_found_speaker.role = "slave"  # Not master!

    metadata = {}
    role = "slave"

    with (
        patch("custom_components.wiim.coordinator_multiroom.find_speaker_by_ip", return_value=mock_found_speaker),
        patch("custom_components.wiim.coordinator_multiroom.get_all_speakers", return_value=[]),
    ):
        await resolve_multiroom_source_and_media(mock_coordinator, status, metadata, role)

    # Should fallback to follower when found speaker is not master
    status_dict = status.model_dump(exclude_none=True)
    assert status_dict["source"] == "follower"


async def test_multiroom_master_data_missing(mock_coordinator):
    """Test slave behavior when master speaker has no data."""
    status = PlayerStatus.model_validate({"status": "play", "vol": 50, "source": "multiroom"})
    status._multiroom_mode = True

    mock_coordinator.data = {"status_model": PlayerStatus.model_validate({"master_ip": "192.168.1.200"})}

    # Master speaker exists but has no coordinator data
    mock_master_speaker = MagicMock()
    mock_master_speaker.role = "master"
    mock_master_speaker.coordinator.data = None  # No data!

    metadata = {}
    role = "slave"

    with patch("custom_components.wiim.coordinator_multiroom.find_speaker_by_ip", return_value=mock_master_speaker):
        await resolve_multiroom_source_and_media(mock_coordinator, status, metadata, role)

    # Should fallback to follower when master has no data
    status_dict = status.model_dump(exclude_none=True)
    assert status_dict["source"] == "follower"


async def test_multiroom_exception_handling(mock_coordinator):
    """Test exception handling in multiroom processing."""
    status = PlayerStatus.model_validate({"status": "play", "vol": 50, "source": "multiroom"})
    status._multiroom_mode = True

    mock_coordinator.data = {"status_model": None}

    # Mock speaker that raises exception when accessing ip_address
    mock_master_speaker = MagicMock()
    mock_master_speaker.role = "master"
    mock_master_speaker.group_members = [MagicMock()]
    mock_master_speaker.group_members[0].ip_address = PropertyError("Access error")

    metadata = {}
    role = "slave"

    with (
        patch("custom_components.wiim.coordinator_multiroom.find_speaker_by_ip", return_value=None),
        patch("custom_components.wiim.coordinator_multiroom.get_all_speakers", return_value=[mock_master_speaker]),
    ):
        await resolve_multiroom_source_and_media(mock_coordinator, status, metadata, role)

    # Should handle exception gracefully and fallback
    status_dict = status.model_dump(exclude_none=True)
    assert status_dict["source"] == "follower"


# Custom exception for testing
class PropertyError(Exception):
    """Exception for testing property access errors."""

    pass
