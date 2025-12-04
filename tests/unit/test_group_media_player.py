"""Unit tests for WiiM Group Media Player - testing group coordination functionality."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.components.media_player import MediaPlayerEntityFeature, MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

from custom_components.wiim.const import CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP
from custom_components.wiim.group_media_player import WiiMGroupMediaPlayer


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.unique_id = "test-uuid"
    entry.data = {"host": "192.168.1.100"}
    entry.options = {}
    return entry


@pytest.fixture
def mock_master_player():
    """Create a mock master player with group."""
    player = MagicMock()
    player.host = "192.168.1.100"
    player.volume_level = 0.5
    player.is_muted = False
    player.play_state = "play"
    player.source = "spotify"
    player.role = "master"
    player.is_master = True
    player.is_slave = False
    player.is_solo = False

    # Group properties
    player.group = MagicMock()
    player.group.volume_level = 0.6  # MAX of all devices
    player.group.is_muted = False  # ALL muted
    player.group.all_players = [player]  # Will be expanded in group tests

    # Media properties
    player.media_title = "Test Song"
    player.media_artist = "Test Artist"
    player.media_album = "Test Album"
    player.media_duration = 180
    player.media_position = 60
    player.media_image_url = "http://example.com/cover.jpg"
    player.media_content_id = None  # URL if playing URL-based media

    # Methods
    player.set_volume = AsyncMock(return_value=True)
    player.set_mute = AsyncMock(return_value=True)
    player.play = AsyncMock(return_value=True)
    player.pause = AsyncMock(return_value=True)
    player.stop = AsyncMock(return_value=True)
    player.next_track = AsyncMock(return_value=True)
    player.previous_track = AsyncMock(return_value=True)

    return player


@pytest.fixture
def mock_group_coordinator(mock_master_player):
    """Create a mock coordinator with group."""
    coordinator = MagicMock()
    coordinator.data = {"player": mock_master_player}
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    coordinator.player = mock_master_player
    return coordinator


@pytest.fixture
def mock_group_coordinator_setup(mock_group_coordinator, mock_config_entry):
    """Set up mock_group_coordinator with player properties."""
    # Set up player properties
    mock_group_coordinator.player.name = "Test WiiM"
    mock_group_coordinator.player.model = "WiiM Mini"
    mock_group_coordinator.player.firmware = "1.0.0"
    mock_group_coordinator.player.host = "192.168.1.100"
    mock_group_coordinator.player.device_info = MagicMock()
    mock_group_coordinator.player.device_info.mac = "AA:BB:CC:DD:EE:FF"
    mock_group_coordinator.player.input_list = ["spotify", "bluetooth"]

    # Return as a simple object for easier access
    class CoordinatorSetup:
        def __init__(self, coordinator, config_entry):
            self.coordinator = coordinator
            self.config_entry = config_entry

    return CoordinatorSetup(mock_group_coordinator, mock_config_entry)


@pytest.fixture
def group_media_player(mock_group_coordinator, mock_config_entry):
    """Create a WiiMGroupMediaPlayer instance using the new pattern."""
    # Set up player properties
    mock_group_coordinator.player.name = "Test WiiM"
    mock_group_coordinator.player.model = "WiiM Mini"
    mock_group_coordinator.player.firmware = "1.0.0"
    mock_group_coordinator.player.host = "192.168.1.100"
    mock_group_coordinator.player.device_info = MagicMock()
    mock_group_coordinator.player.device_info.mac = "AA:BB:CC:DD:EE:FF"
    mock_group_coordinator.player.input_list = ["spotify", "bluetooth"]
    return WiiMGroupMediaPlayer(mock_group_coordinator, mock_config_entry)


class TestWiiMGroupMediaPlayerBasic:
    """Test basic group media player functionality."""

    def test_initialization(self, mock_group_coordinator_setup):
        """Test group media player initialization."""
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.unique_id == "test-uuid_group_coordinator"
        assert entity.coordinator == mock_group_coordinator_setup.coordinator
        assert entity._config_entry == mock_group_coordinator_setup.config_entry

    def test_name_property(self, mock_group_coordinator_setup):
        """Test dynamic name property."""
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        # When available and master
        assert entity.name == "Test WiiM Group Master"

        # When not available (coordinator unavailable means group entity is unavailable)
        mock_group_coordinator_setup.coordinator.last_update_success = False
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.name == "Test WiiM"

    def test_available_when_master_with_slaves(self, mock_group_coordinator_setup, mock_master_player):
        """Test availability when master has slaves."""
        # Setup: master with slaves
        mock_master_player.is_master = True
        mock_master_player.group.all_players = [mock_master_player, MagicMock()]  # 2 players = has slaves

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.available is True

    def test_not_available_when_solo(self, mock_group_coordinator_setup, mock_master_player):
        """Test not available when solo."""
        mock_master_player.is_master = False
        mock_master_player.is_solo = True
        mock_master_player.group.all_players = [mock_master_player]  # Only 1 player = solo

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.available is False

    def test_not_available_when_slave(self, mock_group_coordinator_setup, mock_master_player):
        """Test not available when slave."""
        mock_master_player.is_master = False
        mock_master_player.is_slave = True
        mock_master_player.group = None

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.available is False


class TestWiiMGroupMediaPlayerVolume:
    """Test group volume functionality."""

    def test_volume_level_returns_group_max(self, mock_group_coordinator_setup, mock_master_player):
        """Test volume level returns MAX of all devices in group."""
        # Setup: group with different volumes
        mock_master_player.volume_level = 0.5
        mock_master_player.group.volume_level = 0.6  # MAX

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.volume_level == 0.6

    def test_volume_level_returns_none_when_unavailable(self, mock_group_coordinator_setup):
        """Test volume level returns None when unavailable."""
        mock_group_coordinator_setup.coordinator.last_update_success = False

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.volume_level is None

    def test_volume_step_reads_from_config(self, mock_group_coordinator_setup):
        """Test volume step reads from config entry options."""
        mock_group_coordinator_setup.config_entry.options = {CONF_VOLUME_STEP: 0.10}  # Stored as decimal (10% = 0.10)

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.volume_step == 0.10  # 10% = 0.10

    def test_volume_step_defaults_when_not_configured(self, mock_group_coordinator_setup):
        """Test volume step defaults when not configured."""
        mock_config_entry.options = {}

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.volume_step == DEFAULT_VOLUME_STEP

    async def test_set_volume_level(self, mock_group_coordinator_setup, mock_master_player):
        """Test setting group volume level."""
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        # Mock group.set_volume_all method
        mock_master_player.group.set_volume_all = AsyncMock(return_value=True)

        await entity.async_set_volume_level(0.75)

        # Should call set_volume_all on group
        mock_master_player.group.set_volume_all.assert_called_once_with(0.75)
        # No manual refresh - pywiim manages state updates via callbacks

    async def test_set_volume_level_handles_error(self, mock_group_coordinator_setup, mock_master_player):
        """Test set volume level handles errors."""
        mock_master_player.group.set_volume_all = AsyncMock(side_effect=WiiMError("Volume error"))

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        with pytest.raises(HomeAssistantError, match="Failed to set group volume"):
            await entity.async_set_volume_level(0.75)


class TestWiiMGroupMediaPlayerMute:
    """Test group mute functionality."""

    def test_is_volume_muted_returns_true_when_all_muted(self, mock_group_coordinator_setup, mock_master_player):
        """Test is_volume_muted returns True when ALL devices are muted."""
        mock_master_player.group.is_muted = True  # ALL muted

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.is_volume_muted is True

    def test_is_volume_muted_returns_false_when_any_unmuted(self, mock_group_coordinator_setup, mock_master_player):
        """Test is_volume_muted returns False when any device is unmuted."""
        mock_master_player.group.is_muted = False  # Not all muted

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.is_volume_muted is False

    async def test_mute_volume(self, mock_group_coordinator_setup, mock_master_player):
        """Test muting group volume."""
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        # Mock group.mute_all method
        mock_master_player.group.mute_all = AsyncMock(return_value=True)

        await entity.async_mute_volume(True)

        mock_master_player.group.mute_all.assert_called_once_with(True)
        # No manual refresh - pywiim manages state updates via callbacks

    async def test_unmute_volume(self, mock_group_coordinator_setup, mock_master_player):
        """Test unmuting group volume."""
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        # Mock group.mute_all method
        mock_master_player.group.mute_all = AsyncMock(return_value=True)

        await entity.async_mute_volume(False)

        mock_master_player.group.mute_all.assert_called_once_with(False)
        # No manual refresh - pywiim manages state updates via callbacks


class TestWiiMGroupMediaPlayerPlayback:
    """Test group playback controls."""

    async def test_media_play(self, mock_group_coordinator_setup, mock_master_player):
        """Test play command."""
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        await entity.async_media_play()

        mock_master_player.play.assert_called_once()
        # No manual refresh - pywiim manages state updates via callbacks

    async def test_media_pause(self, mock_group_coordinator_setup, mock_master_player):
        """Test pause command."""
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        await entity.async_media_pause()

        mock_master_player.pause.assert_called_once()
        # No manual refresh - pywiim manages state updates via callbacks

    async def test_media_stop(self, mock_group_coordinator_setup, mock_master_player):
        """Test stop command."""
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        await entity.async_media_stop()

        mock_master_player.stop.assert_called_once()
        # No manual refresh - pywiim manages state updates via callbacks

    async def test_media_next_track(self, mock_group_coordinator_setup, mock_master_player):
        """Test next track command."""
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        await entity.async_media_next_track()

        mock_master_player.next_track.assert_called_once()
        # No manual refresh - pywiim manages state updates via callbacks

    async def test_media_previous_track(self, mock_group_coordinator_setup, mock_master_player):
        """Test previous track command."""
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        await entity.async_media_previous_track()

        mock_master_player.previous_track.assert_called_once()
        # No manual refresh - pywiim manages state updates via callbacks

    async def test_playback_handles_connection_error(self, mock_group_coordinator_setup, mock_master_player):
        """Test playback commands handle connection errors gracefully."""

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        mock_group_coordinator_setup.coordinator.player.play = AsyncMock(
            side_effect=WiiMConnectionError("Connection lost")
        )

        # Playback methods raise generic HomeAssistantError (not "temporarily unreachable" like volume/mute)
        with pytest.raises(HomeAssistantError, match="Failed to play"):
            await entity.async_media_play()

    async def test_playback_handles_timeout_error(self, mock_group_coordinator_setup, mock_master_player):
        """Test playback commands handle timeout errors gracefully."""

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        mock_group_coordinator_setup.coordinator.player.play = AsyncMock(side_effect=WiiMTimeoutError("Timeout"))

        # Playback methods raise generic HomeAssistantError (not "temporarily unreachable" like volume/mute)
        with pytest.raises(HomeAssistantError, match="Failed to play"):
            await entity.async_media_play()

    async def test_playback_handles_other_errors(self, mock_group_coordinator_setup, mock_master_player):
        """Test playback commands handle other errors."""
        mock_master_player.play.side_effect = WiiMError("Playback error")

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        with pytest.raises(HomeAssistantError, match="Failed to"):
            await entity.async_media_play()


class TestWiiMGroupMediaPlayerState:
    """Test group media player state using pywiim v2.1.37+ state properties."""

    def test_state_playing(self, mock_group_coordinator_setup, mock_master_player):
        """Test state when playing."""
        mock_master_player.is_playing = True
        mock_master_player.is_paused = False
        mock_master_player.is_buffering = False

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.state == MediaPlayerState.PLAYING

    def test_state_paused(self, mock_group_coordinator_setup, mock_master_player):
        """Test state when paused."""
        mock_master_player.is_playing = False
        mock_master_player.is_paused = True
        mock_master_player.is_buffering = False

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.state == MediaPlayerState.PAUSED

    def test_state_idle(self, mock_group_coordinator_setup, mock_master_player):
        """Test state when idle."""
        mock_master_player.is_playing = False
        mock_master_player.is_paused = False
        mock_master_player.is_buffering = False

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.state == MediaPlayerState.IDLE

    def test_state_none_when_unavailable(self, mock_group_coordinator_setup):
        """Test state is None when unavailable."""
        mock_group_coordinator_setup.coordinator.last_update_success = False

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.state is None


class TestWiiMGroupMediaPlayerMediaInfo:
    """Test group media player media information."""

    def test_media_title(self, mock_group_coordinator_setup, mock_master_player):
        """Test media title from master."""
        mock_master_player.media_title = "Test Song"

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.media_title == "Test Song"

    def test_media_artist(self, mock_group_coordinator_setup, mock_master_player):
        """Test media artist from master."""
        mock_master_player.media_artist = "Test Artist"

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.media_artist == "Test Artist"

    def test_media_album_name(self, mock_group_coordinator_setup, mock_master_player):
        """Test media album name from master."""
        mock_master_player.media_album = "Test Album"

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.media_album_name == "Test Album"

    def test_media_image_url(self, mock_group_coordinator_setup, mock_master_player):
        """Test media image URL from master."""
        mock_master_player.media_image_url = "http://example.com/cover.jpg"

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.media_image_url == "http://example.com/cover.jpg"

    def test_media_duration(self, mock_group_coordinator_setup, mock_master_player):
        """Test media duration from master."""
        mock_master_player.media_duration = 180
        mock_master_player.play_state = "play"  # Need playing state for duration

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        # Trigger update to set duration
        entity._update_position_from_coordinator()
        assert entity.media_duration == 180

    def test_media_position(self, mock_group_coordinator_setup, mock_master_player):
        """Test media position from master."""
        mock_master_player.media_position = 60
        mock_master_player.play_state = "play"  # Need playing state for position

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        # Trigger update to set position
        entity._update_position_from_coordinator()
        assert entity.media_position == 60


class TestWiiMGroupMediaPlayerShuffleRepeat:
    """Test group shuffle and repeat functionality."""

    def test_shuffle_supported_returns_true(self, mock_group_coordinator_setup, mock_master_player):
        """Test shuffle_supported returns True when supported."""
        mock_master_player.shuffle_supported = True
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity._shuffle_supported() is True

    def test_shuffle_supported_returns_false_when_not_supported(self, mock_group_coordinator_setup, mock_master_player):
        """Test shuffle_supported returns False when not supported."""
        mock_master_player.shuffle_supported = False
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity._shuffle_supported() is False

    def test_shuffle_returns_true(self, mock_group_coordinator_setup, mock_master_player):
        """Test shuffle property returns True when enabled."""
        mock_master_player.shuffle = True
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.shuffle is True

    def test_shuffle_returns_false(self, mock_group_coordinator_setup, mock_master_player):
        """Test shuffle property returns False when disabled."""
        mock_master_player.shuffle = False
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.shuffle is False

    def test_shuffle_returns_none_when_player_missing(self, mock_group_coordinator_setup):
        """Test shuffle property returns None when unavailable."""
        mock_group_coordinator_setup.coordinator.last_update_success = False
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.shuffle is None

    @pytest.mark.asyncio
    async def test_set_shuffle_enables(self, mock_group_coordinator_setup, mock_master_player):
        """Test setting shuffle to True."""
        mock_master_player.set_shuffle = AsyncMock(return_value=True)
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        await entity.async_set_shuffle(True)

        mock_master_player.set_shuffle.assert_called_once_with(True)
        # No manual refresh - pywiim manages state updates via callbacks

    @pytest.mark.asyncio
    async def test_set_shuffle_handles_error(self, mock_group_coordinator_setup, mock_master_player):
        """Test set_shuffle handles errors."""
        mock_master_player.set_shuffle = AsyncMock(side_effect=WiiMError("Shuffle error"))
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        with pytest.raises(HomeAssistantError, match="Failed to set shuffle"):
            await entity.async_set_shuffle(True)

    def test_repeat_supported_returns_true(self, mock_group_coordinator_setup, mock_master_player):
        """Test repeat_supported returns True when supported."""
        mock_master_player.repeat_supported = True
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity._repeat_supported() is True

    def test_repeat_returns_off(self, mock_group_coordinator_setup, mock_master_player):
        """Test repeat property returns OFF."""
        from homeassistant.components.media_player import RepeatMode

        mock_master_player.repeat = "off"
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.repeat == RepeatMode.OFF

    def test_repeat_returns_one(self, mock_group_coordinator_setup, mock_master_player):
        """Test repeat property returns ONE."""
        from homeassistant.components.media_player import RepeatMode

        mock_master_player.repeat = "1"
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.repeat == RepeatMode.ONE

    def test_repeat_returns_all(self, mock_group_coordinator_setup, mock_master_player):
        """Test repeat property returns ALL."""
        from homeassistant.components.media_player import RepeatMode

        mock_master_player.repeat = "all"
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.repeat == RepeatMode.ALL

    @pytest.mark.asyncio
    async def test_set_repeat_all(self, mock_group_coordinator_setup, mock_master_player):
        """Test setting repeat to ALL."""
        from homeassistant.components.media_player import RepeatMode

        mock_master_player.set_repeat = AsyncMock(return_value=True)
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        await entity.async_set_repeat(RepeatMode.ALL)

        mock_master_player.set_repeat.assert_called_once_with("all")
        # No manual refresh - pywiim manages state updates via callbacks

    @pytest.mark.asyncio
    async def test_set_repeat_handles_error(self, mock_group_coordinator_setup, mock_master_player):
        """Test set_repeat handles errors."""
        from homeassistant.components.media_player import RepeatMode

        mock_master_player.set_repeat = AsyncMock(side_effect=WiiMError("Repeat error"))
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        with pytest.raises(HomeAssistantError, match="Failed to set repeat"):
            await entity.async_set_repeat(RepeatMode.ALL)


class TestWiiMGroupMediaPlayerPlayMedia:
    """Test group play_media functionality."""

    @pytest.mark.asyncio
    async def test_play_media_delegates_to_master(self, mock_group_coordinator_setup, mock_master_player):
        """Test play_media delegates to master player."""
        mock_master_player.play_url = AsyncMock(return_value=True)
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        await entity.async_play_media("music", "http://example.com/song.mp3")

        mock_master_player.play_url.assert_called_once_with("http://example.com/song.mp3")
        # No manual refresh - pywiim manages state updates via callbacks

    @pytest.mark.asyncio
    async def test_play_media_handles_error(self, mock_group_coordinator_setup, mock_master_player):
        """Test play_media handles errors."""
        mock_master_player.play_url = AsyncMock(side_effect=WiiMError("Play error"))
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        with pytest.raises(HomeAssistantError, match="Failed to play media"):
            await entity.async_play_media("music", "http://example.com/song.mp3")


class TestWiiMGroupMediaPlayerMediaContent:
    """Test group media content properties."""

    def test_media_content_type(self, mock_group_coordinator_setup):
        """Test media_content_type returns MUSIC."""
        from homeassistant.components.media_player import MediaType

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.media_content_type == MediaType.MUSIC

    def test_media_content_id_returns_url_when_playing(self, mock_group_coordinator_setup, mock_master_player):
        """Test media_content_id returns URL from pywiim when playing."""
        from homeassistant.components.media_player import MediaPlayerState

        mock_master_player.media_content_id = "http://example.com/song.mp3"
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        entity._attr_state = MediaPlayerState.PLAYING

        assert entity.media_content_id == "http://example.com/song.mp3"

    def test_media_content_id_returns_none_when_idle(self, mock_group_coordinator_setup, mock_master_player):
        """Test media_content_id returns None when idle (regardless of pywiim value)."""
        from homeassistant.components.media_player import MediaPlayerState

        mock_master_player.media_content_id = "http://example.com/song.mp3"
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        entity._attr_state = MediaPlayerState.IDLE

        # Should return None when idle even if pywiim has a URL
        assert entity.media_content_id is None


class TestWiiMGroupMediaPlayerImageHandling:
    """Test group media player image handling."""

    def test_media_image_url_returns_none_when_unavailable(self, mock_group_coordinator_setup):
        """Test media_image_url returns None when unavailable."""
        mock_group_coordinator_setup.coordinator.last_update_success = False
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        assert entity.media_image_url is None

    def test_media_image_url_returns_placeholder_when_no_url(self, mock_group_coordinator_setup, mock_master_player):
        """Test media_image_url returns placeholder when player has no URL."""
        mock_master_player.media_image_url = None
        mock_master_player.media_title = "Test Song"
        mock_master_player.media_artist = "Test Artist"
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        url = entity.media_image_url
        assert url is not None
        assert url.startswith("wiim://group-cover-art/")

    def test_media_image_remotely_accessible(self, mock_group_coordinator_setup):
        """Test media_image_remotely_accessible returns False."""
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        assert entity.media_image_remotely_accessible is False

    @pytest.mark.asyncio
    async def test_get_media_image_returns_cover_art(self, mock_group_coordinator_setup, mock_master_player):
        """Test async_get_media_image returns cover art."""
        mock_master_player.fetch_cover_art = AsyncMock(return_value=(b"image_data", "image/jpeg"))

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        result = await entity.async_get_media_image()

        assert result == (b"image_data", "image/jpeg")
        mock_master_player.fetch_cover_art.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_media_image_returns_none_when_unavailable(self, mock_group_coordinator_setup):
        """Test async_get_media_image returns None when unavailable."""
        mock_group_coordinator_setup.coordinator.last_update_success = False
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        result = await entity.async_get_media_image()
        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_get_media_image_handles_missing_fetch_method(self, mock_group_coordinator_setup, mock_master_player):
        """Test async_get_media_image handles missing fetch_cover_art method."""
        # Don't set fetch_cover_art attribute
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        result = await entity.async_get_media_image()
        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_get_media_image_handles_exception(self, mock_group_coordinator_setup, mock_master_player):
        """Test async_get_media_image handles exceptions gracefully."""
        mock_master_player.fetch_cover_art = AsyncMock(side_effect=Exception("Error"))

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        result = await entity.async_get_media_image()

        assert result == (None, None)


class TestWiiMGroupMediaPlayerExtraState:
    """Test group media player extra state attributes."""

    def test_extra_state_attributes_when_available(self, mock_group_coordinator_setup, mock_master_player):
        """Test extra_state_attributes when available."""
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        attrs = entity.extra_state_attributes

        assert attrs["group_leader"] == "Test WiiM"
        assert attrs["group_status"] == "active"

    def test_extra_state_attributes_when_unavailable(self, mock_group_coordinator_setup):
        """Test extra_state_attributes when unavailable."""
        mock_group_coordinator_setup.coordinator.last_update_success = False
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        attrs = entity.extra_state_attributes

        assert attrs["group_leader"] == "Test WiiM"
        assert attrs["group_status"] == "inactive"


class TestWiiMGroupMediaPlayerSupportedFeatures:
    """Test group media player supported features."""

    def test_supported_features_when_unavailable(self, mock_group_coordinator_setup):
        """Test supported_features returns basic features when unavailable."""
        mock_group_coordinator_setup.coordinator.last_update_success = False
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        features = entity.supported_features

        assert MediaPlayerEntityFeature.VOLUME_SET in features
        assert MediaPlayerEntityFeature.VOLUME_MUTE in features
        assert MediaPlayerEntityFeature.VOLUME_STEP in features
        # Should not have playback features when unavailable
        assert MediaPlayerEntityFeature.PLAY not in features

    def test_supported_features_with_supports_next_track(self, mock_group_coordinator_setup, mock_master_player):
        """Test supported_features includes NEXT_TRACK and PREVIOUS_TRACK when supported."""
        mock_master_player.supports_next_track = True
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        features = entity.supported_features

        assert MediaPlayerEntityFeature.NEXT_TRACK in features
        assert MediaPlayerEntityFeature.PREVIOUS_TRACK in features

    def test_supported_features_without_supports_next_track(self, mock_group_coordinator_setup, mock_master_player):
        """Test supported_features excludes NEXT_TRACK and PREVIOUS_TRACK when not supported."""
        mock_master_player.supports_next_track = False
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        features = entity.supported_features

        assert MediaPlayerEntityFeature.NEXT_TRACK not in features
        assert MediaPlayerEntityFeature.PREVIOUS_TRACK not in features

    def test_next_track_supported_returns_true(self, mock_group_coordinator_setup, mock_master_player):
        """Test _next_track_supported returns True when supported."""
        mock_master_player.supports_next_track = True
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        assert entity._next_track_supported() is True

    def test_next_track_supported_returns_false_when_not_supported(
        self, mock_group_coordinator_setup, mock_master_player
    ):
        """Test _next_track_supported returns False when not supported."""
        mock_master_player.supports_next_track = False
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        assert entity._next_track_supported() is False

    def test_next_track_supported_returns_false_when_unavailable(self, mock_group_coordinator_setup):
        """Test _next_track_supported returns False when entity is unavailable."""
        mock_group_coordinator_setup.coordinator.last_update_success = False
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        assert entity._next_track_supported() is False

    # Note: Removed test_next_track_supported_returns_false_when_player_missing
    # The coordinator.player is always available after setup (pywiim guarantees this)


class TestWiiMGroupMediaPlayerStateEdgeCases:
    """Test group media player state edge cases with pywiim v2.1.37+ state properties."""

    def test_state_derives_playing_from_is_playing(self, mock_group_coordinator_setup, mock_master_player):
        """Test state derives PLAYING when is_playing is True."""
        from homeassistant.components.media_player import MediaPlayerState

        mock_master_player.is_playing = True
        mock_master_player.is_paused = False
        mock_master_player.is_buffering = False
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        entity._attr_state = None

        assert entity.state == MediaPlayerState.PLAYING

    def test_state_derives_buffering_from_is_buffering(self, mock_group_coordinator_setup, mock_master_player):
        """Test state derives BUFFERING when is_buffering is True."""
        from homeassistant.components.media_player import MediaPlayerState

        mock_master_player.is_playing = False
        mock_master_player.is_paused = False
        mock_master_player.is_buffering = True
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        entity._attr_state = None

        assert entity.state == MediaPlayerState.BUFFERING

    def test_state_uses_attr_state_when_set(self, mock_group_coordinator_setup):
        """Test state uses _attr_state when set."""
        from homeassistant.components.media_player import MediaPlayerState

        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        entity._attr_state = MediaPlayerState.PAUSED

        assert entity.state == MediaPlayerState.PAUSED

    def test_state_returns_none_when_unavailable(self, mock_group_coordinator_setup):
        """Test state returns None when unavailable."""
        mock_group_coordinator_setup.coordinator.last_update_success = False
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )
        entity._attr_state = None

        assert entity.state is None


class TestWiiMGroupMediaPlayerUpdatePosition:
    """Test group media player position update."""

    def test_update_position_handles_missing_player(self, mock_group_coordinator_setup):
        """Test _update_position_from_coordinator handles missing player (unavailable)."""
        mock_group_coordinator_setup.coordinator.last_update_success = False
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        entity._update_position_from_coordinator()

        assert entity._attr_media_position is None
        assert entity._attr_media_duration is None
        assert entity._attr_state is None


class TestWiiMGroupMediaPlayerHandleUpdate:
    """Test group media player coordinator update handling."""

    def test_handle_coordinator_update_updates_position(self, mock_group_coordinator_setup, mock_master_player):
        """Test _handle_coordinator_update updates position from coordinator."""
        mock_master_player.play_state = "play"
        mock_master_player.media_position = 60
        mock_master_player.media_duration = 180
        entity = WiiMGroupMediaPlayer(
            mock_group_coordinator_setup.coordinator, mock_group_coordinator_setup.config_entry
        )

        with patch.object(entity, "async_write_ha_state"):
            entity._handle_coordinator_update()

        assert entity._attr_media_position == 60
        assert entity._attr_media_duration == 180
