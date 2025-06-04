"""Unit tests for WiiM media player platform."""

import pytest
from unittest.mock import AsyncMock, MagicMock, call, patch
from homeassistant.components.media_player import (
    MediaPlayerState,
    MediaPlayerEntityFeature,
)

# Import fixtures from our WiiM conftest
pytest_plugins = ["tests.conftest_wiim"]


class TestWiiMMediaPlayer:
    """Test WiiM media player entity."""

    @pytest.fixture
    def media_player(self, wiim_speaker):
        """Create a WiiM media player entity."""
        from custom_components.wiim.media_player import WiiMMediaPlayer

        return WiiMMediaPlayer(wiim_speaker)

    def test_media_player_creation(self, media_player, wiim_speaker):
        """Test media player entity creation."""
        assert media_player.speaker is wiim_speaker
        assert media_player.unique_id == "test-speaker-uuid"
        assert media_player.name == "Test WiiM"

    def test_supported_features(self, media_player):
        """Test media player supported features."""
        expected_features = (
            MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.SELECT_SOUND_MODE
            | MediaPlayerEntityFeature.SHUFFLE_SET
            | MediaPlayerEntityFeature.REPEAT_SET
            | MediaPlayerEntityFeature.GROUPING
            | MediaPlayerEntityFeature.PLAY_MEDIA  # Always supported
            # SEEK is conditionally added, don't include in test
        )
        assert media_player.supported_features == expected_features

    def test_state_property(self, media_player, wiim_speaker):
        """Test state property delegation to speaker."""
        # Mock speaker's get_playback_state
        wiim_speaker.get_playback_state = MagicMock(return_value=MediaPlayerState.PLAYING)

        state = media_player.state
        assert state == MediaPlayerState.PLAYING
        wiim_speaker.get_playback_state.assert_called_once()

    def test_volume_level_property(self, media_player, wiim_speaker):
        """Test volume level property delegation."""
        wiim_speaker.get_volume_level = MagicMock(return_value=0.75)

        volume = media_player.volume_level
        assert volume == 0.75
        wiim_speaker.get_volume_level.assert_called_once()

    def test_is_volume_muted(self, media_player):
        """Test volume mute status."""
        # Test muted
        media_player.speaker.coordinator.data["status"]["mute"] = "1"
        assert media_player.is_volume_muted is True

        # Test unmuted
        media_player.speaker.coordinator.data["status"]["mute"] = "0"
        assert media_player.is_volume_muted is False

        # Test no data
        media_player.speaker.coordinator.data = None
        assert media_player.is_volume_muted is None

    def test_media_properties(self, media_player):
        """Test media metadata properties."""
        # Set up test data
        status = media_player.speaker.coordinator.data["status"]
        status.update(
            {
                "title": "Test Song",
                "artist": "Test Artist",
                "album": "Test Album",
                "duration": "240",
                "position": "60",
                "entity_picture": "http://example.com/cover.jpg",
            }
        )

        assert media_player.media_title == "Test Song"
        assert media_player.media_artist == "Test Artist"
        assert media_player.media_album_name == "Test Album"
        assert media_player.media_duration == 240
        assert media_player.media_position == 60
        assert media_player.media_image_url == "http://example.com/cover.jpg"

    def test_source_properties(self, media_player):
        """Test source and source list properties."""
        status = media_player.speaker.coordinator.data["status"]
        # Add mode field for new source detection logic
        status.update(
            {
                "mode": "10",  # WiFi mode
                "source": "wifi",
                "sources": ["wifi", "bluetooth", "line_in"],
            }
        )

        # The new source detection should map mode "10" to "WiFi"
        assert media_player.source == "WiFi"

        # The source_list returns friendly names from SOURCE_MAP, not raw sources
        source_list = media_player.source_list
        assert isinstance(source_list, list)
        assert len(source_list) > 0
        # Should contain WiFi as one of the available sources
        assert "WiFi" in source_list

    def test_group_members_property(self, media_player, wiim_speaker):
        """Test group members property delegation."""
        wiim_speaker.get_group_member_entity_ids = MagicMock(return_value=["media_player.wiim1", "media_player.wiim2"])

        members = media_player.group_members
        assert members == ["media_player.wiim1", "media_player.wiim2"]
        wiim_speaker.get_group_member_entity_ids.assert_called_once()


class TestMediaPlayerControls:
    """Test media player control methods."""

    @pytest.fixture
    def media_player(self, wiim_speaker, hass):
        """Create a WiiM media player entity with proper hass setup."""
        from custom_components.wiim.media_player import WiiMMediaPlayer

        player = WiiMMediaPlayer(wiim_speaker)
        player.hass = hass  # Set hass for async_write_ha_state
        player.entity_id = "media_player.test_wiim"  # Set entity ID
        return player

    @pytest.mark.asyncio
    async def test_async_media_play(self, media_player):
        """Test play command."""
        await media_player.async_media_play()

        media_player.speaker.coordinator.client.play.assert_called_once()
        media_player.speaker.coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_media_pause(self, media_player):
        """Test pause command."""
        await media_player.async_media_pause()

        media_player.speaker.coordinator.client.pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_media_stop(self, media_player):
        """Test stop command."""
        await media_player.async_media_stop()

        media_player.speaker.coordinator.client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_volume_level(self, media_player):
        """Test volume setting."""
        await media_player.async_set_volume_level(0.75)

        # The controller's set_volume method converts to percentage and calls speaker's coordinator client
        media_player.speaker.coordinator.client.set_volume.assert_called_once_with(75)

    @pytest.mark.asyncio
    async def test_async_mute_volume(self, media_player):
        """Test volume muting."""
        await media_player.async_mute_volume(True)

        media_player.speaker.coordinator.client.set_mute.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_async_media_next_track(self, media_player):
        """Test next track command."""
        await media_player.async_media_next_track()

        media_player.speaker.coordinator.client.next_track.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_media_previous_track(self, media_player):
        """Test previous track command."""
        await media_player.async_media_previous_track()

        media_player.speaker.coordinator.client.previous_track.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_media_seek(self, media_player):
        """Test media seeking."""
        await media_player.async_media_seek(120.5)

        media_player.speaker.coordinator.client.seek.assert_called_once_with(120)

    @pytest.mark.asyncio
    async def test_async_select_source(self, media_player):
        """Test source selection."""
        await media_player.async_select_source("bluetooth")

        media_player.speaker.coordinator.client.set_source.assert_called_once_with("bluetooth")


class TestMediaPlayerGrouping:
    """Test media player grouping functionality."""

    @pytest.fixture
    def media_player(self, wiim_speaker):
        """Create a WiiM media player entity."""
        from custom_components.wiim.media_player import WiiMMediaPlayer

        return WiiMMediaPlayer(wiim_speaker)

    @pytest.mark.asyncio
    async def test_async_join(self, media_player, wiim_speaker, wiim_speaker_slave):
        """Test joining speakers to a group."""
        # Mock speaker's resolve and join methods
        wiim_speaker.resolve_entity_ids_to_speakers = MagicMock(return_value=[wiim_speaker_slave])
        wiim_speaker.async_join_group = AsyncMock()

        await media_player.async_join(["media_player.slave"])

        wiim_speaker.resolve_entity_ids_to_speakers.assert_called_once_with(["media_player.slave"])
        wiim_speaker.async_join_group.assert_called_once_with([wiim_speaker_slave])

    @pytest.mark.asyncio
    async def test_async_unjoin(self, media_player, wiim_speaker):
        """Test leaving a group."""
        wiim_speaker.async_leave_group = AsyncMock()

        await media_player.async_unjoin()

        wiim_speaker.async_leave_group.assert_called_once()


class TestMediaPlayerState:
    """Test media player state attributes."""

    @pytest.fixture
    def media_player(self, wiim_speaker):
        """Create a WiiM media player entity."""
        from custom_components.wiim.media_player import WiiMMediaPlayer

        return WiiMMediaPlayer(wiim_speaker)

    def test_extra_state_attributes(self, media_player, wiim_speaker):
        """Test extra state attributes."""
        # Set up test data
        wiim_speaker.role = "master"
        wiim_speaker.group_members = [wiim_speaker, MagicMock()]  # Master + 1 slave

        attrs = media_player.extra_state_attributes

        assert attrs["speaker_uuid"] == "test-speaker-uuid"
        assert attrs["speaker_role"] == "master"
        assert attrs["coordinator_ip"] == "192.168.1.100"
        assert attrs["group_members_count"] == 2

        # Test smart polling attributes
        assert "activity_level" in attrs
        assert "polling_interval" in attrs

    def test_extra_state_attributes_no_data(self, media_player, wiim_speaker):
        """Test extra state attributes when no coordinator data."""
        wiim_speaker.coordinator.data = None

        attrs = media_player.extra_state_attributes
        assert attrs == {}

    def test_available_property(self, media_player, wiim_speaker):
        """Test availability property delegation."""
        wiim_speaker._available = True
        wiim_speaker.coordinator.last_update_success = True
        assert media_player.available is True

        wiim_speaker._available = False
        assert media_player.available is False

    def test_device_info_property(self, media_player, wiim_speaker):
        """Test device info property delegation."""
        mock_device_info = {"test": "device_info"}
        wiim_speaker.device_info = mock_device_info

        assert media_player.device_info == mock_device_info


class TestMediaPlayerSetup:
    """Test media player platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry(self, hass, wiim_config_entry, wiim_speaker):
        """Test platform setup entry point."""
        from custom_components.wiim.media_player import async_setup_entry

        entities = []

        async def mock_add_entities(entity_list):
            entities.extend(entity_list)

        # Mock the get_speaker_from_config_entry function to return our test speaker
        with patch("custom_components.wiim.media_player.get_speaker_from_config_entry", return_value=wiim_speaker):
            await async_setup_entry(hass, wiim_config_entry, mock_add_entities)

        assert len(entities) == 1
        assert entities[0].speaker is wiim_speaker
