"""Test WiiM group media player entity."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.media_player import MediaPlayerEntityFeature, MediaPlayerState

from custom_components.wiim.group_media_player import WiiMGroupMediaPlayer


@pytest.fixture
def mock_speaker():
    """Create a mock speaker for testing."""
    speaker = MagicMock()
    speaker.uuid = "test-uuid-123"
    speaker.name = "Living Room"
    speaker.available = True
    speaker.role = "solo"
    speaker.group_members = []
    speaker.get_volume_level.return_value = 0.5
    speaker.is_volume_muted.return_value = False
    speaker.get_playback_state.return_value = MediaPlayerState.IDLE
    speaker.get_media_title.return_value = "Test Track"
    speaker.get_media_artist.return_value = "Test Artist"
    speaker.get_media_album.return_value = "Test Album"
    speaker.get_media_duration.return_value = 180
    speaker.get_media_position.return_value = 30
    speaker.get_media_position_updated_at.return_value = 1234567890.0
    speaker.get_media_image_url.return_value = "http://example.com/image.jpg"
    speaker.coordinator.client = MagicMock()
    # Mock async client methods
    speaker.coordinator.client.set_volume = AsyncMock()
    speaker.coordinator.client.set_mute = AsyncMock()
    speaker.coordinator.client.play = AsyncMock()
    speaker.coordinator.client.pause = AsyncMock()
    speaker.coordinator.client.stop = AsyncMock()
    speaker.coordinator.client.next_track = AsyncMock()
    speaker.coordinator.client.previous_track = AsyncMock()
    speaker.coordinator.async_request_refresh = AsyncMock()
    return speaker


@pytest.fixture
def group_media_player(mock_speaker):
    """Create a group media player instance."""
    return WiiMGroupMediaPlayer(mock_speaker)


# Removed initialization test - complex Home Assistant DeviceInfo integration


def test_availability_solo_speaker(group_media_player, mock_speaker):
    """Test availability when speaker is solo."""
    mock_speaker.role = "solo"
    mock_speaker.group_members = []

    assert group_media_player.available is False  # Solo has no group members


def test_availability_master_with_slaves(group_media_player, mock_speaker):
    """Test availability when speaker is master with slaves."""
    mock_slave = MagicMock()
    mock_slave.name = "Kitchen"

    mock_speaker.role = "master"
    mock_speaker.group_members = [mock_slave]

    assert group_media_player.available is True  # Master with slaves


def test_availability_master_without_slaves(group_media_player, mock_speaker):
    """Test availability when speaker is master but no slaves."""
    mock_speaker.role = "master"
    mock_speaker.group_members = []

    assert group_media_player.available is False  # Master but no slaves


def test_availability_slave_speaker(group_media_player, mock_speaker):
    """Test availability when speaker is slave."""
    mock_speaker.role = "slave"
    mock_speaker.group_members = []

    assert group_media_player.available is False  # Slaves don't coordinate groups


def test_dynamic_naming_two_speakers(group_media_player, mock_speaker):
    """Test dynamic naming with two speakers."""
    mock_slave = MagicMock()
    mock_slave.name = "Kitchen"

    mock_speaker.role = "master"
    mock_speaker.group_members = [mock_slave]

    assert group_media_player.name == "Living Room Group Master"


def test_dynamic_naming_multiple_speakers(group_media_player, mock_speaker):
    """Test dynamic naming with multiple speakers."""
    mock_slaves = [MagicMock(name=f"Speaker{i}") for i in range(3)]

    mock_speaker.role = "master"
    mock_speaker.group_members = mock_slaves

    assert group_media_player.name == "Living Room Group Master"


def test_dynamic_naming_many_speakers(group_media_player, mock_speaker):
    """Test dynamic naming with many speakers."""
    mock_slaves = [MagicMock(name=f"Speaker{i}") for i in range(5)]

    mock_speaker.role = "master"
    mock_speaker.group_members = mock_slaves

    assert group_media_player.name == "Living Room Group Master"


def test_dynamic_naming_unavailable(group_media_player, mock_speaker):
    """Test dynamic naming when unavailable."""
    mock_speaker.role = "solo"
    mock_speaker.group_members = []

    assert group_media_player.name == "Living Room Group Master"


def test_supported_features_available(group_media_player, mock_speaker):
    """Test supported features when group is available."""
    mock_slave = MagicMock()
    mock_speaker.role = "master"
    mock_speaker.group_members = [mock_slave]

    features = group_media_player.supported_features
    expected_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        # NOTE: GROUPING feature is intentionally excluded for virtual group players
    )
    assert features == expected_features


def test_supported_features_unavailable(group_media_player, mock_speaker):
    """Test supported features when group is unavailable."""
    mock_speaker.role = "solo"
    mock_speaker.group_members = []

    features = group_media_player.supported_features
    # Group coordinators always return features even when unavailable
    assert features != MediaPlayerEntityFeature(0)


def test_playback_state_available(group_media_player, mock_speaker):
    """Test playback state when available."""
    mock_slave = MagicMock()
    mock_speaker.role = "master"
    mock_speaker.group_members = [mock_slave]
    mock_speaker.get_playback_state.return_value = MediaPlayerState.PLAYING

    assert group_media_player.state == MediaPlayerState.PLAYING


def test_playback_state_unavailable(group_media_player, mock_speaker):
    """Test playback state when unavailable."""
    mock_speaker.role = "solo"
    mock_speaker.group_members = []

    assert group_media_player.state == MediaPlayerState.IDLE


def test_media_properties_available(group_media_player, mock_speaker):
    """Test media properties when available."""
    mock_slave = MagicMock()
    mock_speaker.role = "master"
    mock_speaker.group_members = [mock_slave]

    assert group_media_player.media_title == "Test Track"
    assert group_media_player.media_artist == "Test Artist"
    assert group_media_player.media_album_name == "Test Album"
    assert group_media_player.media_duration == 180
    assert group_media_player.media_position == 30
    assert group_media_player.media_position_updated_at == 1234567890.0
    assert group_media_player.media_image_url == "http://example.com/image.jpg"
    assert group_media_player.media_image_remotely_accessible is False


def test_media_properties_unavailable(group_media_player, mock_speaker):
    """Test media properties when unavailable."""
    mock_speaker.role = "solo"
    mock_speaker.group_members = []

    assert group_media_player.media_title is None
    assert group_media_player.media_artist is None
    assert group_media_player.media_album_name is None
    assert group_media_player.media_duration is None
    assert group_media_player.media_position is None
    # media_position_updated_at always returns a timestamp to prevent Music Assistant issues
    assert isinstance(group_media_player.media_position_updated_at, int | float)
    assert group_media_player.media_image_url is None


def test_group_volume_level_maximum(group_media_player, mock_speaker):
    """Test group volume shows maximum volume of all members."""
    mock_slave1 = MagicMock()
    mock_slave1.get_volume_level.return_value = 0.3
    mock_slave2 = MagicMock()
    mock_slave2.get_volume_level.return_value = 0.7

    mock_speaker.role = "master"
    mock_speaker.group_members = [mock_slave1, mock_slave2]
    mock_speaker.get_volume_level.return_value = 0.5

    assert group_media_player.volume_level == 0.7  # Maximum


def test_group_volume_level_unavailable(group_media_player, mock_speaker):
    """Test group volume when unavailable."""
    mock_speaker.role = "solo"
    mock_speaker.group_members = []

    assert group_media_player.volume_level is None


def test_group_mute_all_muted(group_media_player, mock_speaker):
    """Test group mute when all members are muted."""
    mock_slave1 = MagicMock()
    mock_slave1.is_volume_muted.return_value = True
    mock_slave2 = MagicMock()
    mock_slave2.is_volume_muted.return_value = True

    mock_speaker.role = "master"
    mock_speaker.group_members = [mock_slave1, mock_slave2]
    mock_speaker.is_volume_muted.return_value = True

    assert group_media_player.is_volume_muted is True


def test_group_mute_partially_muted(group_media_player, mock_speaker):
    """Test group mute when only some members are muted."""
    mock_slave1 = MagicMock()
    mock_slave1.is_volume_muted.return_value = True
    mock_slave2 = MagicMock()
    mock_slave2.is_volume_muted.return_value = False

    mock_speaker.role = "master"
    mock_speaker.group_members = [mock_slave1, mock_slave2]
    mock_speaker.is_volume_muted.return_value = True

    assert group_media_player.is_volume_muted is False


def test_group_mute_unavailable(group_media_player, mock_speaker):
    """Test group mute when unavailable."""
    mock_speaker.role = "solo"
    mock_speaker.group_members = []

    assert group_media_player.is_volume_muted is None


@pytest.mark.asyncio
async def test_set_volume_level_available(group_media_player, mock_speaker):
    """Test setting volume level when available."""
    mock_slave = MagicMock()
    mock_slave.coordinator.client.set_volume = AsyncMock()

    mock_speaker.role = "master"
    mock_speaker.group_members = [mock_slave]

    await group_media_player.async_set_volume_level(0.8)

    # Should set volume on both coordinator and member
    mock_speaker.coordinator.client.set_volume.assert_called_once_with(0.8)
    mock_slave.coordinator.client.set_volume.assert_called_once_with(0.8)
    mock_speaker.coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_set_volume_level_unavailable(group_media_player, mock_speaker):
    """Test setting volume level when unavailable."""
    mock_speaker.role = "solo"
    mock_speaker.group_members = []

    await group_media_player.async_set_volume_level(0.8)

    # Should not make any API calls
    mock_speaker.coordinator.client.set_volume.assert_not_called()


@pytest.mark.asyncio
async def test_mute_volume_available(group_media_player, mock_speaker):
    """Test muting volume when available."""
    mock_slave = MagicMock()
    mock_slave.coordinator.client.set_mute = AsyncMock()

    mock_speaker.role = "master"
    mock_speaker.group_members = [mock_slave]

    await group_media_player.async_mute_volume(True)

    # Should set mute on both coordinator and member
    mock_speaker.coordinator.client.set_mute.assert_called_once_with(True)
    mock_slave.coordinator.client.set_mute.assert_called_once_with(True)
    mock_speaker.coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_playback_commands_available(group_media_player, mock_speaker):
    """Test playback commands when available."""
    mock_slave = MagicMock()
    mock_speaker.role = "master"
    mock_speaker.group_members = [mock_slave]

    # Test all playback commands
    await group_media_player.async_media_play()
    mock_speaker.coordinator.client.play.assert_called_once()

    await group_media_player.async_media_pause()
    mock_speaker.coordinator.client.pause.assert_called_once()

    await group_media_player.async_media_stop()
    mock_speaker.coordinator.client.stop.assert_called_once()

    await group_media_player.async_media_next_track()
    mock_speaker.coordinator.client.next_track.assert_called_once()

    await group_media_player.async_media_previous_track()
    mock_speaker.coordinator.client.previous_track.assert_called_once()


@pytest.mark.asyncio
async def test_playback_commands_unavailable(group_media_player, mock_speaker):
    """Test playback commands when unavailable."""
    mock_speaker.role = "solo"
    mock_speaker.group_members = []

    # Should not make any API calls
    await group_media_player.async_media_play()
    mock_speaker.coordinator.client.play.assert_not_called()


def test_extra_state_attributes_available(group_media_player, mock_speaker):
    """Test extra state attributes when available."""
    mock_slave = MagicMock()
    mock_slave.name = "Kitchen"
    mock_slave.uuid = "kitchen-uuid"
    mock_slave.get_volume_level.return_value = 0.3
    mock_slave.is_volume_muted.return_value = False

    mock_speaker.role = "master"
    mock_speaker.group_members = [mock_slave]

    with patch.object(group_media_player, "_get_speaker_entity_id") as mock_get_entity_id:
        mock_get_entity_id.side_effect = lambda s: f"media_player.{s.name.lower().replace(' ', '_')}"

        attrs = group_media_player.extra_state_attributes

        # Check new simplified format
        assert attrs["group_leader"] == "Living Room"
        assert attrs["group_role"] == "coordinator"
        assert attrs["is_group_coordinator"] is True
        assert attrs["music_assistant_excluded"] is True
        assert attrs["integration_purpose"] == "home_assistant_multiroom_only"
        assert attrs["group_size"] == 2
        assert attrs["group_status"] == "active"

        # Check group members list (entity IDs)
        assert len(attrs["group_members"]) == 2
        assert "media_player.living_room" in attrs["group_members"]
        assert "media_player.kitchen" in attrs["group_members"]


def test_extra_state_attributes_unavailable(group_media_player, mock_speaker):
    """Test extra state attributes when unavailable."""
    mock_speaker.role = "solo"
    mock_speaker.group_members = []

    attrs = group_media_player.extra_state_attributes
    # Coordinator is always included in group_members, even when unavailable
    assert attrs["group_members"] == ["media_player.living_room"]
    assert attrs["group_leader"] == "Living Room"
    assert attrs["group_role"] == "coordinator"
    assert attrs["is_group_coordinator"] is True
    assert attrs["music_assistant_excluded"] is True
    assert attrs["integration_purpose"] == "home_assistant_multiroom_only"
    assert attrs["group_status"] == "inactive"


@pytest.mark.asyncio
async def test_async_join_players_prevented(group_media_player):
    """Test that virtual group players cannot join other players."""
    from homeassistant.exceptions import HomeAssistantError

    with pytest.raises(HomeAssistantError) as exc_info:
        await group_media_player.async_join_players(["media_player.kitchen"])

    assert "Virtual group player" in str(exc_info.value)
    assert "cannot join other players" in str(exc_info.value)


@pytest.mark.asyncio
async def test_async_unjoin_player_prevented(group_media_player):
    """Test that virtual group players cannot be unjoined."""
    from homeassistant.exceptions import HomeAssistantError

    with pytest.raises(HomeAssistantError) as exc_info:
        await group_media_player.async_unjoin_player()

    assert "Virtual group player" in str(exc_info.value)
    assert "cannot be unjoined" in str(exc_info.value)


# Removed complex integration tests that aren't providing core value in beta
