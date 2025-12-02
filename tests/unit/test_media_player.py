"""Unit tests for WiiM Media Player - testing volume and core functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry

from custom_components.wiim.const import CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP
from custom_components.wiim.data import Speaker
from custom_components.wiim.media_player import WiiMMediaPlayer


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
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {"player": MagicMock()}
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    coordinator.player = MagicMock()
    coordinator.player.volume_level = 0.5
    coordinator.player.is_muted = False
    coordinator.player.play_state = "play"
    coordinator.player.source = "spotify"
    coordinator.player.is_solo = True
    coordinator.player.is_master = False
    coordinator.player.is_slave = False
    coordinator.player.group = None
    # Make player methods async
    coordinator.player.set_volume = AsyncMock(return_value=True)
    coordinator.player.set_mute = AsyncMock(return_value=True)
    return coordinator


@pytest.fixture
def mock_speaker(mock_coordinator, mock_config_entry):
    """Create a mock speaker."""
    speaker = MagicMock(spec=Speaker)
    speaker.coordinator = mock_coordinator
    speaker.config_entry = mock_config_entry
    speaker.uuid = "test-uuid"
    speaker.name = "Test WiiM"
    speaker.available = True
    return speaker


@pytest.fixture
def media_player(mock_speaker):
    """Create a WiiMMediaPlayer instance."""
    return WiiMMediaPlayer(mock_speaker)


class TestWiiMMediaPlayerVolume:
    """Test volume-related functionality."""

    def test_volume_level_returns_player_volume(self, media_player, mock_coordinator):
        """Test that volume_level returns player's volume_level."""
        mock_coordinator.data["player"].volume_level = 0.75
        assert media_player.volume_level == 0.75

    def test_volume_level_returns_none_when_player_missing(self, media_player, mock_coordinator):
        """Test that volume_level returns None when player is missing."""
        mock_coordinator.data = None
        assert media_player.volume_level is None

    def test_volume_level_for_slave_in_group(self, media_player, mock_coordinator):
        """Test that volume_level works for slaves in a group (Issue #126)."""
        # Setup slave player
        mock_coordinator.data["player"].is_slave = True
        mock_coordinator.data["player"].is_master = False
        mock_coordinator.data["player"].volume_level = 0.3  # Slave has its own volume

        # Volume should still be accessible for slaves
        assert media_player.volume_level == 0.3

    def test_volume_step_reads_from_config_default(self, media_player, mock_speaker):
        """Test that volume_step returns default when not configured (Issue #127)."""
        mock_speaker.config_entry.options = {}
        assert media_player.volume_step == DEFAULT_VOLUME_STEP

    def test_volume_step_reads_from_config_custom(self, media_player, mock_speaker):
        """Test that volume_step reads from config entry options (Issue #127)."""
        mock_speaker.config_entry.options = {CONF_VOLUME_STEP: 0.1}
        assert media_player.volume_step == 0.1

    def test_volume_step_handles_missing_speaker(self, media_player):
        """Test that volume_step handles missing speaker gracefully."""
        media_player.speaker = None
        assert media_player.volume_step == DEFAULT_VOLUME_STEP

    def test_volume_step_handles_missing_config_entry(self, media_player, mock_speaker):
        """Test that volume_step handles missing config_entry gracefully."""
        mock_speaker.config_entry = None
        assert media_player.volume_step == DEFAULT_VOLUME_STEP


class TestWiiMMediaPlayerBasic:
    """Test basic media player functionality."""

    def test_media_player_initialization(self, media_player, mock_speaker):
        """Test media player is initialized correctly."""
        assert media_player.speaker is mock_speaker
        assert media_player.coordinator is mock_speaker.coordinator

    def test_media_player_name(self, media_player, mock_speaker):
        """Test media player name property."""
        assert media_player.name == mock_speaker.name

    def test_media_player_available(self, media_player, mock_speaker):
        """Test media player available property."""
        mock_speaker.available = True
        assert media_player.available is True

    @pytest.mark.asyncio
    async def test_set_volume_level(self, media_player, mock_coordinator):
        """Test setting volume level."""
        await media_player.async_set_volume_level(0.8)
        mock_coordinator.player.set_volume.assert_called_once_with(0.8)
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_mute_volume(self, media_player, mock_coordinator):
        """Test muting volume."""
        await media_player.async_mute_volume(True)
        mock_coordinator.player.set_mute.assert_called_once_with(True)
        # State updates automatically via callback - no manual refresh needed


class TestWiiMMediaPlayerGrouping:
    """Test grouping functionality."""

    def test_volume_level_for_master_in_group(self, media_player, mock_coordinator):
        """Test volume_level for master in group."""
        mock_coordinator.data["player"].is_master = True
        mock_coordinator.data["player"].is_slave = False
        mock_coordinator.data["player"].volume_level = 0.6
        assert media_player.volume_level == 0.6

    def test_volume_level_for_solo_speaker(self, media_player, mock_coordinator):
        """Test volume_level for solo speaker."""
        mock_coordinator.data["player"].is_solo = True
        mock_coordinator.data["player"].volume_level = 0.4
        assert media_player.volume_level == 0.4


class TestWiiMMediaPlayerPlayback:
    """Test playback controls."""

    @pytest.mark.asyncio
    async def test_media_play(self, media_player, mock_coordinator):
        """Test play command."""
        mock_coordinator.player.play = AsyncMock(return_value=True)

        await media_player.async_media_play()

        mock_coordinator.player.play.assert_called_once()
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_media_pause(self, media_player, mock_coordinator):
        """Test pause command."""
        mock_coordinator.player.pause = AsyncMock(return_value=True)

        await media_player.async_media_pause()

        mock_coordinator.player.pause.assert_called_once()
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_media_play_pause(self, media_player, mock_coordinator):
        """Test play/pause toggle."""
        mock_coordinator.player.media_play_pause = AsyncMock(return_value=True)

        await media_player.async_media_play_pause()

        mock_coordinator.player.media_play_pause.assert_called_once()
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_media_stop(self, media_player, mock_coordinator):
        """Test stop command."""
        player = mock_coordinator.data["player"]
        player.stop = AsyncMock(return_value=True)
        player.source = "spotify"  # Not streaming

        await media_player.async_media_stop()

        player.stop.assert_called_once()
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_media_next_track(self, media_player, mock_coordinator):
        """Test next track command."""
        mock_coordinator.player.next_track = AsyncMock(return_value=True)

        await media_player.async_media_next_track()

        mock_coordinator.player.next_track.assert_called_once()
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_media_previous_track(self, media_player, mock_coordinator):
        """Test previous track command."""
        mock_coordinator.player.previous_track = AsyncMock(return_value=True)

        await media_player.async_media_previous_track()

        mock_coordinator.player.previous_track.assert_called_once()
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_media_seek(self, media_player, mock_coordinator):
        """Test seek command."""
        mock_coordinator.player.seek = AsyncMock(return_value=True)
        media_player._attr_media_duration = 180  # 3 minutes

        await media_player.async_media_seek(60.0)

        mock_coordinator.player.seek.assert_called_once_with(60)
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_playback_handles_error(self, media_player, mock_coordinator):
        """Test playback commands handle errors."""
        from pywiim.exceptions import WiiMError

        mock_coordinator.player.play = AsyncMock(side_effect=WiiMError("Playback error"))

        from homeassistant.exceptions import HomeAssistantError

        with pytest.raises(HomeAssistantError, match="Failed to start playback"):
            await media_player.async_media_play()


class TestWiiMMediaPlayerSource:
    """Test source selection."""

    def test_source_returns_current_source(self, media_player, mock_coordinator):
        """Test source property returns current source."""
        mock_coordinator.data["player"].source = "spotify"
        mock_coordinator.data["player"].available_sources = ["Spotify", "Bluetooth"]

        assert media_player.source == "Spotify"  # Capitalized

    def test_source_returns_none_when_no_source(self, media_player, mock_coordinator):
        """Test source returns None when no source set."""
        mock_coordinator.data["player"].source = None
        mock_coordinator.data["player"].available_sources = []

        assert media_player.source is None

    def test_source_list_returns_available_sources(self, media_player, mock_coordinator):
        """Test source_list returns available sources."""
        mock_coordinator.data["player"].available_sources = ["Spotify", "Bluetooth", "Optical"]

        assert media_player.source_list == ["Spotify", "Bluetooth", "Optical"]

    @pytest.mark.asyncio
    async def test_select_source(self, media_player, mock_coordinator, mock_speaker):
        """Test selecting a source."""
        player = mock_coordinator.data["player"]
        player.available_sources = ["Spotify", "Bluetooth"]
        mock_coordinator.player.set_source = AsyncMock(return_value=True)
        mock_speaker.input_list = ["spotify", "bluetooth"]

        await media_player.async_select_source("Spotify")

        # The code maps "Spotify" -> "spotify" via available_sources or input_list
        # It should call with the device source name (from available_sources map)
        mock_coordinator.player.set_source.assert_called_once()
        # Check it was called with a lowercase version
        call_args = mock_coordinator.player.set_source.call_args[0][0]
        assert call_args.lower() == "spotify"
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_select_source_handles_error(self, media_player, mock_coordinator):
        """Test select source handles errors."""
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        mock_coordinator.player.set_source = AsyncMock(side_effect=WiiMError("Source error"))

        with pytest.raises(HomeAssistantError, match="Failed to select source"):
            await media_player.async_select_source("Spotify")


class TestWiiMMediaPlayerMediaInfo:
    """Test media information properties."""

    def test_media_title(self, media_player, mock_coordinator):
        """Test media title property."""
        player = mock_coordinator.data["player"]
        player.media_title = "Test Song"
        player.is_slave = False  # Not a slave, so uses player directly
        player.group = None

        # media_title property uses _get_metadata_player() which returns player
        assert media_player.media_title == "Test Song"

    def test_media_artist(self, media_player, mock_coordinator):
        """Test media artist property."""
        player = mock_coordinator.data["player"]
        player.media_artist = "Test Artist"
        player.is_slave = False
        player.group = None

        assert media_player.media_artist == "Test Artist"

    def test_media_album_name(self, media_player, mock_coordinator):
        """Test media album name property."""
        player = mock_coordinator.data["player"]
        player.media_album = "Test Album"
        player.is_slave = False
        player.group = None

        assert media_player.media_album_name == "Test Album"

    def test_media_image_url(self, media_player, mock_coordinator):
        """Test media image URL property."""
        player = mock_coordinator.data["player"]
        player.media_image_url = "http://example.com/cover.jpg"
        player.is_slave = False
        player.group = None

        # media_image_url property checks player.media_image_url first
        # If it exists, returns it; otherwise returns placeholder
        url = media_player.media_image_url
        assert url is not None
        # Should return the actual URL or a placeholder

    def test_media_duration(self, media_player, mock_coordinator):
        """Test media duration property."""
        player = mock_coordinator.data["player"]
        player.media_duration = 180
        player.play_state = "play"
        player.is_slave = False
        player.group = None

        # Trigger update to set duration
        media_player._update_position_from_coordinator()
        assert media_player.media_duration == 180

    def test_media_position(self, media_player, mock_coordinator):
        """Test media position property."""
        from homeassistant.components.media_player import MediaPlayerState

        player = mock_coordinator.data["player"]
        player.media_position = 60
        player.play_state = "play"  # Need playing state for position
        player.is_slave = False
        player.group = None
        player.media_duration = 180

        # Trigger update to set position
        media_player._update_position_from_coordinator()
        # Position should be set when playing
        assert media_player.media_position == 60
        assert media_player.state == MediaPlayerState.PLAYING


class TestWiiMMediaPlayerErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_set_volume_handles_error(self, media_player, mock_coordinator):
        """Test set volume handles errors."""
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        mock_coordinator.player.set_volume = AsyncMock(side_effect=WiiMError("Volume error"))

        with pytest.raises(HomeAssistantError, match="Failed to set volume"):
            await media_player.async_set_volume_level(0.5)

    @pytest.mark.asyncio
    async def test_mute_handles_error(self, media_player, mock_coordinator):
        """Test mute handles errors."""
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        mock_coordinator.player.set_mute = AsyncMock(side_effect=WiiMError("Mute error"))

        with pytest.raises(HomeAssistantError, match="Failed to"):
            await media_player.async_mute_volume(True)


class TestWiiMMediaPlayerShuffleRepeat:
    """Test shuffle and repeat functionality."""

    def test_shuffle_supported_returns_true(self, media_player, mock_coordinator):
        """Test shuffle_supported returns True when supported."""
        mock_coordinator.data["player"].shuffle_supported = True
        assert media_player._shuffle_supported() is True

    def test_shuffle_supported_returns_false_when_not_supported(self, media_player, mock_coordinator):
        """Test shuffle_supported returns False when not supported."""
        mock_coordinator.data["player"].shuffle_supported = False
        assert media_player._shuffle_supported() is False

    def test_shuffle_supported_returns_false_when_player_missing(self, media_player):
        """Test shuffle_supported returns False when player is missing."""
        media_player.coordinator.data = None
        assert media_player._shuffle_supported() is False

    def test_next_track_supported_returns_false_when_attribute_missing(self, media_player, mock_coordinator):
        """Test _next_track_supported returns False when attribute is missing."""
        # Remove the attribute to simulate older pywiim versions or unsupported sources
        player = mock_coordinator.data["player"]
        if hasattr(player, "next_track_supported"):
            delattr(player, "next_track_supported")

        assert media_player._next_track_supported() is False

    def test_shuffle_returns_true(self, media_player, mock_coordinator):
        """Test shuffle property returns True when enabled."""
        mock_coordinator.data["player"].shuffle = True
        assert media_player.shuffle is True

    def test_shuffle_returns_false(self, media_player, mock_coordinator):
        """Test shuffle property returns False when disabled."""
        mock_coordinator.data["player"].shuffle = False
        assert media_player.shuffle is False

    def test_shuffle_returns_none_when_player_missing(self, media_player):
        """Test shuffle property returns None when player is missing."""
        media_player.coordinator.data = None
        assert media_player.shuffle is None

    def test_shuffle_handles_string_values(self, media_player, mock_coordinator):
        """Test shuffle property handles string values."""
        mock_coordinator.data["player"].shuffle = "1"
        assert media_player.shuffle is True

        mock_coordinator.data["player"].shuffle = "true"
        assert media_player.shuffle is True

        mock_coordinator.data["player"].shuffle = "off"
        assert media_player.shuffle is False

    @pytest.mark.asyncio
    async def test_set_shuffle_enables(self, media_player, mock_coordinator):
        """Test setting shuffle to True."""
        mock_coordinator.player.set_shuffle = AsyncMock(return_value=True)

        await media_player.async_set_shuffle(True)

        mock_coordinator.player.set_shuffle.assert_called_once_with(True)
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_set_shuffle_disables(self, media_player, mock_coordinator):
        """Test setting shuffle to False."""
        mock_coordinator.player.set_shuffle = AsyncMock(return_value=True)

        await media_player.async_set_shuffle(False)

        mock_coordinator.player.set_shuffle.assert_called_once_with(False)
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_set_shuffle_handles_error(self, media_player, mock_coordinator):
        """Test set_shuffle handles errors."""
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        mock_coordinator.player.set_shuffle = AsyncMock(side_effect=WiiMError("Shuffle error"))

        with pytest.raises(HomeAssistantError, match="Failed to set shuffle"):
            await media_player.async_set_shuffle(True)

    def test_repeat_supported_returns_true(self, media_player, mock_coordinator):
        """Test repeat_supported returns True when supported."""
        mock_coordinator.data["player"].repeat_supported = True
        assert media_player._repeat_supported() is True

    def test_repeat_supported_returns_false_when_not_supported(self, media_player, mock_coordinator):
        """Test repeat_supported returns False when not supported."""
        mock_coordinator.data["player"].repeat_supported = False
        assert media_player._repeat_supported() is False

    def test_repeat_returns_off(self, media_player, mock_coordinator):
        """Test repeat property returns OFF."""
        from homeassistant.components.media_player import RepeatMode

        mock_coordinator.data["player"].repeat = "off"
        assert media_player.repeat == RepeatMode.OFF

    def test_repeat_returns_one(self, media_player, mock_coordinator):
        """Test repeat property returns ONE."""
        from homeassistant.components.media_player import RepeatMode

        mock_coordinator.data["player"].repeat = "1"
        assert media_player.repeat == RepeatMode.ONE

        mock_coordinator.data["player"].repeat = "track"
        assert media_player.repeat == RepeatMode.ONE

    def test_repeat_returns_all(self, media_player, mock_coordinator):
        """Test repeat property returns ALL."""
        from homeassistant.components.media_player import RepeatMode

        mock_coordinator.data["player"].repeat = "all"
        assert media_player.repeat == RepeatMode.ALL

        mock_coordinator.data["player"].repeat = "playlist"
        assert media_player.repeat == RepeatMode.ALL

    def test_repeat_returns_none_when_player_missing(self, media_player):
        """Test repeat property returns None when player is missing."""
        media_player.coordinator.data = None
        assert media_player.repeat is None

    @pytest.mark.asyncio
    async def test_set_repeat_off(self, media_player, mock_coordinator):
        """Test setting repeat to OFF."""
        from homeassistant.components.media_player import RepeatMode

        mock_coordinator.player.set_repeat = AsyncMock(return_value=True)

        await media_player.async_set_repeat(RepeatMode.OFF)

        mock_coordinator.player.set_repeat.assert_called_once_with("off")
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_set_repeat_one(self, media_player, mock_coordinator):
        """Test setting repeat to ONE."""
        from homeassistant.components.media_player import RepeatMode

        mock_coordinator.player.set_repeat = AsyncMock(return_value=True)

        await media_player.async_set_repeat(RepeatMode.ONE)

        mock_coordinator.player.set_repeat.assert_called_once_with("one")
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_set_repeat_all(self, media_player, mock_coordinator):
        """Test setting repeat to ALL."""
        from homeassistant.components.media_player import RepeatMode

        mock_coordinator.player.set_repeat = AsyncMock(return_value=True)

        await media_player.async_set_repeat(RepeatMode.ALL)

        mock_coordinator.player.set_repeat.assert_called_once_with("all")
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_set_repeat_handles_error(self, media_player, mock_coordinator):
        """Test set_repeat handles errors."""
        from homeassistant.components.media_player import RepeatMode
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        mock_coordinator.player.set_repeat = AsyncMock(side_effect=WiiMError("Repeat error"))

        with pytest.raises(HomeAssistantError, match="Failed to set repeat"):
            await media_player.async_set_repeat(RepeatMode.ALL)

    @pytest.mark.asyncio
    async def test_set_repeat_handles_attribute_error(self, media_player, mock_coordinator):
        """Test set_repeat handles AttributeError when method not available."""
        from homeassistant.components.media_player import RepeatMode
        from homeassistant.exceptions import HomeAssistantError

        mock_coordinator.player.set_repeat = AsyncMock(side_effect=AttributeError("Method not found"))

        with pytest.raises(HomeAssistantError, match="not yet supported"):
            await media_player.async_set_repeat(RepeatMode.ALL)


class TestWiiMMediaPlayerSoundMode:
    """Test EQ/sound mode functionality."""

    def test_is_eq_supported_returns_true(self, media_player, mock_coordinator):
        """Test _is_eq_supported returns True when EQ is supported."""
        mock_coordinator.data["player"].supports_eq = True
        assert media_player._is_eq_supported() is True

    def test_is_eq_supported_returns_false_when_not_supported(self, media_player, mock_coordinator):
        """Test _is_eq_supported returns False when EQ is not supported."""
        mock_coordinator.data["player"].supports_eq = False
        assert media_player._is_eq_supported() is False

    def test_is_eq_supported_returns_false_when_capabilities_missing(self, media_player, mock_coordinator):
        """Test _is_eq_supported returns False when player is missing."""
        mock_coordinator.data = None
        assert media_player._is_eq_supported() is False

    def test_sound_mode_returns_current_preset(self, media_player, mock_coordinator):
        """Test sound_mode returns current EQ preset."""
        mock_coordinator.data["player"].supports_eq = True
        mock_coordinator.data["player"].eq_preset = "bass"

        assert media_player.sound_mode == "Bass"

    def test_sound_mode_returns_none_when_not_supported(self, media_player, mock_coordinator):
        """Test sound_mode returns None when EQ is not supported."""
        mock_coordinator.data["player"].supports_eq = False
        assert media_player.sound_mode is None

    def test_sound_mode_returns_none_when_player_missing(self, media_player, mock_coordinator):
        """Test sound_mode returns None when player is missing."""
        mock_coordinator.data["player"].supports_eq = True
        mock_coordinator.data = None
        assert media_player.sound_mode is None

    def test_sound_mode_list_returns_presets(self, media_player, mock_coordinator):
        """Test sound_mode_list returns available EQ presets."""
        mock_coordinator.data["player"].supports_eq = True
        mock_coordinator.data["player"].eq_presets = ["bass", "treble", "flat"]

        assert media_player.sound_mode_list == ["Bass", "Treble", "Flat"]

    def test_sound_mode_list_returns_none_when_not_supported(self, media_player, mock_coordinator):
        """Test sound_mode_list returns None when EQ is not supported."""
        mock_coordinator.data["player"].supports_eq = False
        assert media_player.sound_mode_list is None

    def test_sound_mode_list_returns_none_when_no_presets(self, media_player, mock_coordinator):
        """Test sound_mode_list returns None when no presets available."""
        mock_coordinator.data["player"].supports_eq = True
        mock_coordinator.data["player"].eq_presets = None
        assert media_player.sound_mode_list is None

    @pytest.mark.asyncio
    async def test_select_sound_mode(self, media_player, mock_coordinator):
        """Test selecting a sound mode."""
        mock_coordinator.data["player"].supports_eq = True
        mock_coordinator.player.set_eq_preset = AsyncMock(return_value=True)

        await media_player.async_select_sound_mode("Bass")

        mock_coordinator.player.set_eq_preset.assert_called_once_with("bass")
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_select_sound_mode_handles_not_supported(self, media_player, mock_coordinator):
        """Test select_sound_mode raises error when EQ is not supported."""
        from homeassistant.exceptions import HomeAssistantError

        mock_coordinator.data["player"].supports_eq = False

        with pytest.raises(HomeAssistantError, match="EQ is not supported"):
            await media_player.async_select_sound_mode("Bass")

    @pytest.mark.asyncio
    async def test_select_sound_mode_handles_error(self, media_player, mock_coordinator):
        """Test select_sound_mode handles errors."""
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        mock_coordinator._capabilities = {"supports_eq": True}
        mock_coordinator.player.set_eq_preset = AsyncMock(side_effect=WiiMError("EQ error"))

        with pytest.raises(HomeAssistantError, match="Failed to select sound mode"):
            await media_player.async_select_sound_mode("Bass")


class TestWiiMMediaPlayerPlayMedia:
    """Test play_media functionality."""

    @pytest.mark.asyncio
    async def test_play_media_url(self, media_player, mock_coordinator):
        """Test playing a URL."""
        mock_coordinator.player.play_url = AsyncMock(return_value=True)
        media_player.hass = MagicMock()

        await media_player.async_play_media("music", "http://example.com/song.mp3")

        mock_coordinator.player.play_url.assert_called_once_with("http://example.com/song.mp3")
        # pywiim now tracks the URL via play_url() - state updates automatically via callback

    @pytest.mark.asyncio
    async def test_play_media_preset(self, media_player, mock_coordinator):
        """Test playing a preset."""
        mock_coordinator.player.play_preset = AsyncMock(return_value=True)
        media_player.hass = MagicMock()

        await media_player.async_play_media("preset", "1")

        mock_coordinator.player.play_preset.assert_called_once_with(1)
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_play_media_announce(self, media_player, mock_coordinator):
        """Test playing an announcement."""
        from homeassistant.components.media_player import ATTR_MEDIA_ANNOUNCE

        mock_coordinator.player.play_notification = AsyncMock(return_value=True)
        media_player.hass = MagicMock()
        media_player.entity_id = "media_player.test"

        await media_player.async_play_media("music", "http://example.com/announce.mp3", **{ATTR_MEDIA_ANNOUNCE: True})

        mock_coordinator.player.play_notification.assert_called_once_with("http://example.com/announce.mp3")
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_play_media_handles_empty_media_id(self, media_player):
        """Test play_media raises error for empty media_id."""
        from homeassistant.exceptions import HomeAssistantError

        with pytest.raises(HomeAssistantError, match="media_id cannot be empty"):
            await media_player.async_play_media("music", "")

    @pytest.mark.asyncio
    async def test_play_media_handles_error(self, media_player, mock_coordinator):
        """Test play_media handles errors."""
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        mock_coordinator.player.play_url = AsyncMock(side_effect=WiiMError("Play error"))
        media_player.hass = MagicMock()

        with pytest.raises(HomeAssistantError, match="Failed to play media"):
            await media_player.async_play_media("music", "http://example.com/song.mp3")


class TestWiiMMediaPlayerMediaContent:
    """Test media content properties."""

    def test_media_content_type(self, media_player):
        """Test media_content_type returns MUSIC."""
        from homeassistant.components.media_player import MediaType

        assert media_player.media_content_type == MediaType.MUSIC

    def test_media_content_id_returns_url_when_playing(self, media_player, mock_coordinator):
        """Test media_content_id returns URL from pywiim when playing."""
        from homeassistant.components.media_player import MediaPlayerState

        player = mock_coordinator.data["player"]
        player.play_state = "play"
        player.is_slave = False
        player.group = None
        player.media_content_id = "http://example.com/song.mp3"
        media_player._attr_state = MediaPlayerState.PLAYING

        assert media_player.media_content_id == "http://example.com/song.mp3"

    def test_media_content_id_returns_none_when_idle(self, media_player, mock_coordinator):
        """Test media_content_id returns None when idle (regardless of pywiim value)."""
        from homeassistant.components.media_player import MediaPlayerState

        player = mock_coordinator.data["player"]
        player.media_content_id = "http://example.com/song.mp3"
        media_player._attr_state = MediaPlayerState.IDLE

        # Should return None when idle even if pywiim has a URL
        assert media_player.media_content_id is None

    def test_media_content_id_returns_none_for_non_url_sources(self, media_player, mock_coordinator):
        """Test media_content_id returns None for non-URL sources (Spotify, etc.)."""
        from homeassistant.components.media_player import MediaPlayerState

        player = mock_coordinator.data["player"]
        player.play_state = "play"
        player.is_slave = False
        player.group = None
        player.media_content_id = None  # pywiim returns None for non-URL sources
        media_player._attr_state = MediaPlayerState.PLAYING

        assert media_player.media_content_id is None


class TestWiiMMediaPlayerJoinUnjoin:
    """Test join/unjoin functionality."""

    def test_join_players_raises_not_implemented(self, media_player):
        """Test join_players raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Use async_join_players"):
            media_player.join_players([])

    def test_unjoin_player_raises_not_implemented(self, media_player):
        """Test unjoin_player raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Use async_unjoin_player"):
            media_player.unjoin_player()

    @pytest.mark.asyncio
    async def test_async_unjoin_player(self, media_player, mock_coordinator):
        """Test async_unjoin_player leaves group."""
        player = mock_coordinator.data["player"]
        player.leave_group = AsyncMock(return_value=True)
        player.group = MagicMock()
        media_player.hass = MagicMock()

        await media_player.async_unjoin_player()

        player.leave_group.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_unjoin_player_handles_error(self, media_player, mock_coordinator):
        """Test async_unjoin_player handles errors."""
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        player = mock_coordinator.data["player"]
        player.leave_group = AsyncMock(side_effect=WiiMError("Leave error"))
        player.group = MagicMock()
        media_player.hass = MagicMock()

        with pytest.raises(HomeAssistantError, match="Failed to leave group"):
            await media_player.async_unjoin_player()

    def test_group_members_returns_none_when_no_group(self, media_player, mock_coordinator):
        """Test group_members returns None when not in a group."""
        mock_coordinator.data["player"].group = None
        assert media_player.group_members is None

    def test_group_members_returns_entity_ids(self, media_player, mock_coordinator):
        """Test group_members returns entity IDs."""

        # Mock entity registry
        mock_registry = MagicMock()
        mock_registry.async_get_entity_id.side_effect = lambda platform, domain, uuid: {
            ("media_player", "wiim", "uuid1"): "media_player.wiim_1",
            ("media_player", "wiim", "uuid2"): "media_player.wiim_2",
        }.get((platform, domain, uuid))

        # Mock group with players
        mock_group = MagicMock()
        mock_player1 = MagicMock()
        mock_player1.uuid = "uuid1"  # Direct uuid attribute
        mock_player2 = MagicMock()
        mock_player2.uuid = "uuid2"  # Direct uuid attribute
        mock_group.all_players = [mock_player1, mock_player2]

        player = mock_coordinator.data["player"]
        player.group = mock_group
        player.is_solo = False  # Not solo, so in a group
        media_player.hass = MagicMock()

        with patch("custom_components.wiim.media_player.er.async_get", return_value=mock_registry):
            members = media_player.group_members
            assert members is not None
            assert len(members) == 2


class TestWiiMMediaPlayerTimers:
    """Test sleep timer and alarm functionality."""

    @pytest.mark.asyncio
    async def test_set_sleep_timer(self, media_player, mock_coordinator):
        """Test setting sleep timer."""
        mock_coordinator.player.set_sleep_timer = AsyncMock(return_value=True)

        await media_player.set_sleep_timer(60)

        mock_coordinator.player.set_sleep_timer.assert_called_once_with(60)

    @pytest.mark.asyncio
    async def test_set_sleep_timer_handles_error(self, media_player, mock_coordinator):
        """Test set_sleep_timer handles errors."""
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        mock_coordinator.player.set_sleep_timer = AsyncMock(side_effect=WiiMError("Timer error"))

        with pytest.raises(HomeAssistantError, match="Failed to set sleep timer"):
            await media_player.set_sleep_timer(60)

    @pytest.mark.asyncio
    async def test_clear_sleep_timer(self, media_player, mock_coordinator):
        """Test clearing sleep timer."""
        mock_coordinator.player.cancel_sleep_timer = AsyncMock(return_value=True)

        await media_player.clear_sleep_timer()

        mock_coordinator.player.cancel_sleep_timer.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_sleep_timer_handles_error(self, media_player, mock_coordinator):
        """Test clear_sleep_timer handles errors."""
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        mock_coordinator.player.cancel_sleep_timer = AsyncMock(side_effect=WiiMError("Cancel error"))

        with pytest.raises(HomeAssistantError, match="Failed to clear sleep timer"):
            await media_player.clear_sleep_timer()

    @pytest.mark.asyncio
    async def test_set_alarm_daily(self, media_player, mock_coordinator):
        """Test setting a daily alarm."""

        mock_coordinator.player.get_alarm = AsyncMock(return_value=None)
        mock_coordinator.player.set_alarm = AsyncMock(return_value=True)

        with patch("custom_components.wiim.media_player.ALARM_TRIGGER_DAILY", 1, create=True):
            with patch("custom_components.wiim.media_player.ALARM_OP_PLAYBACK", 1, create=True):
                # Mock the import in the function
                with patch("pywiim.ALARM_TRIGGER_DAILY", 1):
                    with patch("pywiim.ALARM_OP_PLAYBACK", 1):
                        await media_player.set_alarm(0, time="070000", trigger="daily", operation="playback")

        mock_coordinator.player.set_alarm.assert_called_once()
        call_kwargs = mock_coordinator.player.set_alarm.call_args[1]
        assert call_kwargs["alarm_id"] == 0
        assert call_kwargs["time"] == "070000"
        assert call_kwargs["trigger"] == 1
        assert call_kwargs["operation"] == 1

    @pytest.mark.asyncio
    async def test_set_alarm_handles_error(self, media_player, mock_coordinator):
        """Test set_alarm handles errors."""
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        mock_coordinator.player.get_alarm = AsyncMock(return_value=None)
        mock_coordinator.player.set_alarm = AsyncMock(side_effect=WiiMError("Alarm error"))

        with patch("pywiim.ALARM_TRIGGER_DAILY", 1):
            with patch("pywiim.ALARM_OP_PLAYBACK", 1):
                with pytest.raises(HomeAssistantError, match="Failed to set alarm"):
                    await media_player.set_alarm(0, time="070000", trigger="daily", operation="playback")

    @pytest.mark.asyncio
    async def test_set_alarm_handles_invalid_time(self, media_player, mock_coordinator):
        """Test set_alarm handles invalid time format."""
        from homeassistant.exceptions import HomeAssistantError

        with patch("pywiim.ALARM_TRIGGER_DAILY", 1):
            with patch("pywiim.ALARM_OP_PLAYBACK", 1):
                with pytest.raises(HomeAssistantError, match="Invalid time format"):
                    await media_player.set_alarm(0, time="invalid", trigger="daily", operation="playback")


class TestWiiMMediaPlayerExtraState:
    """Test extra state attributes."""

    def test_extra_state_attributes(self, media_player, mock_speaker, mock_coordinator):
        """Test extra_state_attributes returns correct values."""
        mock_speaker.model = "WiiM Mini"
        mock_speaker.firmware = "1.0.0"
        mock_speaker.ip_address = "192.168.1.100"
        mock_speaker.mac_address = "AA:BB:CC:DD:EE:FF"
        mock_speaker.role = "master"
        mock_coordinator.data["player"].is_master = True

        attrs = media_player.extra_state_attributes

        assert attrs["device_model"] == "WiiM Mini"
        assert attrs["firmware_version"] == "1.0.0"
        assert attrs["ip_address"] == "192.168.1.100"
        assert attrs["mac_address"] == "AA:BB:CC:DD:EE:FF"
        assert attrs["group_role"] == "master"
        assert attrs["is_group_coordinator"] is True
        assert attrs["music_assistant_compatible"] is True
        assert attrs["integration_purpose"] == "individual_speaker_control"


class TestWiiMMediaPlayerHelperFunctions:
    """Test helper functions."""

    def test_is_connection_error_detects_connection_error(self):
        """Test _is_connection_error detects WiiMConnectionError."""
        from pywiim.exceptions import WiiMConnectionError

        from custom_components.wiim.media_player import _is_connection_error

        assert _is_connection_error(WiiMConnectionError("Connection lost")) is True

    def test_is_connection_error_detects_timeout_error(self):
        """Test _is_connection_error detects WiiMTimeoutError."""
        from pywiim.exceptions import WiiMTimeoutError

        from custom_components.wiim.media_player import _is_connection_error

        assert _is_connection_error(WiiMTimeoutError("Timeout")) is True

    def test_is_connection_error_detects_timeout_in_chain(self):
        """Test _is_connection_error detects TimeoutError in exception chain."""
        from custom_components.wiim.media_player import _is_connection_error

        err = Exception("Wrapper")
        err.__cause__ = TimeoutError("Timeout")
        assert _is_connection_error(err) is True

    def test_capitalize_source_name(self):
        """Test _capitalize_source_name handles special cases."""
        from custom_components.wiim.media_player import _capitalize_source_name

        assert _capitalize_source_name("amazon") == "Amazon"
        assert _capitalize_source_name("usb") == "USB"
        assert _capitalize_source_name("bluetooth") == "Bluetooth"
        assert _capitalize_source_name("airplay") == "AirPlay"
        assert _capitalize_source_name("spotify") == "Spotify"
        assert _capitalize_source_name("unknown") == "Unknown"

    def test_media_source_filter(self):
        """Test media_source_filter filters audio content."""
        from homeassistant.components.media_player import BrowseMedia, MediaType

        from custom_components.wiim.media_player import media_source_filter

        audio_item = MagicMock(spec=BrowseMedia)
        audio_item.media_content_type = "audio/mpeg"
        assert media_source_filter(audio_item) is True

        video_item = MagicMock(spec=BrowseMedia)
        video_item.media_content_type = "video/mp4"
        assert media_source_filter(video_item) is False

        dlna_item = MagicMock(spec=BrowseMedia)
        dlna_item.media_content_type = MediaType.CHANNEL
        assert media_source_filter(dlna_item) is True


class TestWiiMMediaPlayerSourceEdgeCases:
    """Test source selection edge cases."""

    def test_source_uses_input_list_fallback(self, media_player, mock_coordinator, mock_speaker):
        """Test source property falls back to input_list when available_sources doesn't match."""
        player = mock_coordinator.data["player"]
        player.source = "bluetooth"  # Lowercase from device
        player.available_sources = ["Spotify"]  # Doesn't include bluetooth
        mock_speaker.input_list = ["bluetooth", "optical"]

        # Should find it in input_list
        assert media_player.source == "Bluetooth"

    def test_source_returns_none_when_no_match(self, media_player, mock_coordinator, mock_speaker):
        """Test source returns None when source doesn't match any available source."""
        player = mock_coordinator.data["player"]
        player.source = "unknown_source"
        player.available_sources = ["Spotify"]
        mock_speaker.input_list = ["bluetooth"]

        assert media_player.source is None

    def test_source_list_falls_back_to_input_list(self, media_player, mock_coordinator, mock_speaker):
        """Test source_list falls back to input_list when available_sources is None."""
        player = mock_coordinator.data["player"]
        player.available_sources = None
        mock_speaker.input_list = ["bluetooth", "optical"]

        assert media_player.source_list == ["Bluetooth", "Optical"]

    def test_source_list_returns_empty_when_no_sources(self, media_player, mock_coordinator, mock_speaker):
        """Test source_list returns empty list when no sources available."""
        player = mock_coordinator.data["player"]
        player.available_sources = None
        mock_speaker.input_list = None

        assert media_player.source_list == []

    @pytest.mark.asyncio
    async def test_select_source_uses_fallback_to_lowercase(self, media_player, mock_coordinator, mock_speaker):
        """Test select_source uses lowercase fallback when not found."""
        player = mock_coordinator.data["player"]
        player.available_sources = None
        mock_speaker.input_list = ["bluetooth"]
        mock_coordinator.player.set_source = AsyncMock(return_value=True)

        await media_player.async_select_source("UnknownSource")

        # Should use lowercase version as final fallback
        mock_coordinator.player.set_source.assert_called_once_with("unknownsource")


class TestWiiMMediaPlayerClearPlaylist:
    """Test clear playlist functionality."""

    @pytest.mark.asyncio
    async def test_clear_playlist(self, media_player, mock_coordinator):
        """Test clearing playlist."""
        mock_coordinator.player.clear_playlist = AsyncMock(return_value=True)

        await media_player.async_clear_playlist()

        mock_coordinator.player.clear_playlist.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_playlist_handles_error(self, media_player, mock_coordinator):
        """Test clear_playlist handles errors."""
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        mock_coordinator.player.clear_playlist = AsyncMock(side_effect=WiiMError("Clear error"))

        with pytest.raises(HomeAssistantError, match="Failed to clear playlist"):
            await media_player.async_clear_playlist()


class TestWiiMMediaPlayerGetMediaImage:
    """Test async_get_media_image functionality."""

    @pytest.mark.asyncio
    async def test_get_media_image_returns_cover_art(self, media_player, mock_coordinator):
        """Test async_get_media_image returns cover art when available."""
        player = mock_coordinator.data["player"]
        player.media_image_url = "http://example.com/cover.jpg"
        player.fetch_cover_art = AsyncMock(return_value=(b"image_data", "image/jpeg"))
        player.is_slave = False
        player.group = None
        media_player.hass = MagicMock()

        result = await media_player.async_get_media_image()

        assert result == (b"image_data", "image/jpeg")
        player.fetch_cover_art.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_media_image_returns_none_when_no_player(self, media_player):
        """Test async_get_media_image returns None when player is missing."""
        media_player.coordinator.data = None
        media_player.hass = MagicMock()

        result = await media_player.async_get_media_image()

        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_get_media_image_handles_missing_fetch_method(self, media_player, mock_coordinator):
        """Test async_get_media_image handles missing fetch_cover_art method."""
        player = mock_coordinator.data["player"]
        player.media_image_url = "http://example.com/cover.jpg"
        # Don't set fetch_cover_art attribute
        player.is_slave = False
        player.group = None
        media_player.hass = MagicMock()

        result = await media_player.async_get_media_image()

        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_get_media_image_handles_empty_result(self, media_player, mock_coordinator):
        """Test async_get_media_image handles empty result."""
        player = mock_coordinator.data["player"]
        player.fetch_cover_art = AsyncMock(return_value=(b"", "image/jpeg"))
        player.is_slave = False
        player.group = None
        media_player.hass = MagicMock()

        result = await media_player.async_get_media_image()

        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_get_media_image_handles_wiiM_error(self, media_player, mock_coordinator):
        """Test async_get_media_image handles WiiMError gracefully."""
        from pywiim.exceptions import WiiMError

        player = mock_coordinator.data["player"]
        player.fetch_cover_art = AsyncMock(side_effect=WiiMError("Cover art error"))
        player.is_slave = False
        player.group = None
        media_player.hass = MagicMock()

        result = await media_player.async_get_media_image()

        # Should return None, None on error (logged but not raised)
        assert result == (None, None)


class TestWiiMMediaPlayerPlayMediaEdgeCases:
    """Test play_media edge cases."""

    @pytest.mark.asyncio
    async def test_play_media_with_enqueue_add(self, media_player, mock_coordinator):
        """Test play_media with enqueue=ADD."""
        from homeassistant.components.media_player import ATTR_MEDIA_ENQUEUE, MediaPlayerEnqueue

        mock_coordinator.player.add_to_queue = AsyncMock(return_value=True)
        mock_coordinator.player._upnp_client = MagicMock()  # Queue support
        media_player.hass = MagicMock()

        await media_player.async_play_media(
            "music", "http://example.com/song.mp3", **{ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.ADD}
        )

        mock_coordinator.player.add_to_queue.assert_called_once_with("http://example.com/song.mp3")

    @pytest.mark.asyncio
    async def test_play_media_with_enqueue_next(self, media_player, mock_coordinator):
        """Test play_media with enqueue=NEXT."""
        from homeassistant.components.media_player import ATTR_MEDIA_ENQUEUE, MediaPlayerEnqueue

        mock_coordinator.player.insert_next = AsyncMock(return_value=True)
        mock_coordinator.player._upnp_client = MagicMock()
        media_player.hass = MagicMock()

        await media_player.async_play_media(
            "music", "http://example.com/song.mp3", **{ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.NEXT}
        )

        mock_coordinator.player.insert_next.assert_called_once_with("http://example.com/song.mp3")

    @pytest.mark.asyncio
    async def test_play_media_with_enqueue_play(self, media_player, mock_coordinator):
        """Test play_media with enqueue=PLAY."""
        from homeassistant.components.media_player import ATTR_MEDIA_ENQUEUE, MediaPlayerEnqueue

        mock_coordinator.player.play_url = AsyncMock(return_value=True)
        mock_coordinator.player._upnp_client = MagicMock()
        media_player.hass = MagicMock()

        await media_player.async_play_media(
            "music", "http://example.com/song.mp3", **{ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.PLAY}
        )

        mock_coordinator.player.play_url.assert_called_once_with("http://example.com/song.mp3")
        # pywiim now tracks the URL via play_url() - state updates automatically via callback

    @pytest.mark.asyncio
    async def test_play_media_announce_with_media_source(self, media_player, mock_coordinator):
        """Test play_media announcement with media source ID."""
        from homeassistant.components import media_source
        from homeassistant.components.media_player import ATTR_MEDIA_ANNOUNCE

        mock_coordinator.player.play_notification = AsyncMock(return_value=True)
        media_player.hass = MagicMock()
        media_player.entity_id = "media_player.test"

        mock_sourced_media = MagicMock()
        mock_sourced_media.url = "http://example.com/announce.mp3"

        with patch.object(media_source, "is_media_source_id", return_value=True):
            with patch.object(media_source, "async_resolve_media", return_value=mock_sourced_media):
                with patch(
                    "custom_components.wiim.media_player.async_process_play_media_url",
                    return_value="http://example.com/announce.mp3",
                ):
                    await media_player.async_play_media("music", "media-source://test", **{ATTR_MEDIA_ANNOUNCE: True})

        mock_coordinator.player.play_notification.assert_called_once_with("http://example.com/announce.mp3")

    @pytest.mark.asyncio
    async def test_play_media_handles_add_to_queue_error(self, media_player, mock_coordinator):
        """Test play_media handles add_to_queue error."""
        from homeassistant.components.media_player import ATTR_MEDIA_ENQUEUE, MediaPlayerEnqueue
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        mock_coordinator.player.add_to_queue = AsyncMock(side_effect=WiiMError("Queue error"))
        mock_coordinator.player._upnp_client = MagicMock()
        media_player.hass = MagicMock()

        with pytest.raises(HomeAssistantError, match="Failed to add media to queue"):
            await media_player.async_play_media(
                "music", "http://example.com/song.mp3", **{ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.ADD}
            )


class TestWiiMMediaPlayerGroupMembersEdgeCases:
    """Test group_members edge cases."""

    def test_group_members_returns_none_when_solo(self, media_player, mock_coordinator):
        """Test group_members returns None when player is solo."""
        player = mock_coordinator.data["player"]
        player.is_solo = True
        player.group = None

        assert media_player.group_members is None

    def test_group_members_returns_none_when_group_is_none(self, media_player, mock_coordinator):
        """Test group_members returns None when group is None."""
        player = mock_coordinator.data["player"]
        player.is_solo = False
        player.group = None

        assert media_player.group_members is None

    def test_group_members_handles_missing_uuid(self, media_player, mock_coordinator):
        """Test group_members handles players without uuid."""

        mock_registry = MagicMock()
        mock_registry.async_get_entity_id.return_value = None

        mock_group = MagicMock()
        mock_player = MagicMock()
        mock_player.uuid = None
        mock_player.mac = None  # No uuid or mac
        mock_group.all_players = [mock_player]

        player = mock_coordinator.data["player"]
        player.group = mock_group
        player.is_solo = False
        media_player.hass = MagicMock()

        with patch("custom_components.wiim.media_player.er.async_get", return_value=mock_registry):
            members = media_player.group_members
            assert members is None  # No valid entity IDs found


class TestWiiMMediaPlayerStateDerivation:
    """Test state derivation edge cases."""

    def test_state_derives_playing_from_play(self, media_player, mock_coordinator):
        """Test state derives PLAYING from 'play'."""
        from homeassistant.components.media_player import MediaPlayerState

        player = mock_coordinator.data["player"]
        player.play_state = "play"
        media_player._attr_state = None

        assert media_player.state == MediaPlayerState.PLAYING

    def test_state_derives_playing_from_playing(self, media_player, mock_coordinator):
        """Test state derives PLAYING from 'playing'."""
        from homeassistant.components.media_player import MediaPlayerState

        player = mock_coordinator.data["player"]
        player.play_state = "playing"
        media_player._attr_state = None

        assert media_player.state == MediaPlayerState.PLAYING

    def test_state_derives_playing_from_load(self, media_player, mock_coordinator):
        """Test state derives PLAYING from 'load'."""
        from homeassistant.components.media_player import MediaPlayerState

        player = mock_coordinator.data["player"]
        player.play_state = "load"
        media_player._attr_state = None

        assert media_player.state == MediaPlayerState.PLAYING

    def test_state_derives_idle_when_no_play_state(self, media_player, mock_coordinator):
        """Test state derives IDLE when play_state is None."""
        from homeassistant.components.media_player import MediaPlayerState

        player = mock_coordinator.data["player"]
        player.play_state = None
        media_player._attr_state = None

        assert media_player.state == MediaPlayerState.IDLE

    def test_state_returns_none_when_unavailable(self, media_player):
        """Test state returns None when unavailable."""
        media_player.coordinator.data = None
        media_player._attr_state = None

        assert media_player.state is None

    def test_state_uses_attr_state_when_set(self, media_player):
        """Test state uses _attr_state when set."""
        from homeassistant.components.media_player import MediaPlayerState

        media_player._attr_state = MediaPlayerState.PAUSED

        assert media_player.state == MediaPlayerState.PAUSED


class TestWiiMMediaPlayerUpdatePosition:
    """Test _update_position_from_coordinator edge cases."""

    def test_update_position_handles_missing_player(self, media_player):
        """Test _update_position_from_coordinator handles missing player."""
        media_player.coordinator.data = None

        # Should not raise
        media_player._update_position_from_coordinator()

        assert media_player._attr_media_position is None
        assert media_player._attr_media_duration is None

    def test_update_position_handles_slave_with_group(self, media_player, mock_coordinator):
        """Test _update_position_from_coordinator handles slave with group."""
        from homeassistant.components.media_player import MediaPlayerState

        player = mock_coordinator.data["player"]
        player.is_slave = True
        player.group = MagicMock()
        master = MagicMock()
        master.media_position = 120
        master.media_duration = 240
        master.play_state = "play"
        player.group.master = master

        media_player._update_position_from_coordinator()

        assert media_player._attr_media_position == 120
        assert media_player._attr_media_duration == 240
        assert media_player._attr_state == MediaPlayerState.PLAYING


class TestWiiMMediaPlayerServiceHandlers:
    """Test service handler methods."""

    @pytest.mark.asyncio
    async def test_async_play_url(self, media_player, mock_coordinator):
        """Test async_play_url service handler."""
        from homeassistant.components.media_player import MediaType

        mock_coordinator.player.play_url = AsyncMock(return_value=True)
        media_player.hass = MagicMock()
        media_player.async_play_media = AsyncMock()

        await media_player.async_play_url("http://example.com/song.mp3")

        # Should call async_play_media with MediaType.MUSIC
        media_player.async_play_media.assert_called_once_with(MediaType.MUSIC, "http://example.com/song.mp3")

    @pytest.mark.asyncio
    async def test_async_play_preset(self, media_player, mock_coordinator):
        """Test async_play_preset service handler."""
        mock_coordinator.player.play_preset = AsyncMock(return_value=True)
        media_player.hass = MagicMock()
        media_player.async_play_media = AsyncMock()

        await media_player.async_play_preset(5)

        # Should call async_play_media with preset type
        media_player.async_play_media.assert_called_once_with("preset", "5")

    @pytest.mark.asyncio
    async def test_async_play_playlist(self, media_player, mock_coordinator):
        """Test async_play_playlist service handler."""
        from homeassistant.components.media_player import MediaType

        mock_coordinator.player.play_url = AsyncMock(return_value=True)
        media_player.hass = MagicMock()
        media_player.async_play_media = AsyncMock()

        await media_player.async_play_playlist("http://example.com/playlist.m3u")

        # Should call async_play_media with MediaType.PLAYLIST
        media_player.async_play_media.assert_called_once_with(MediaType.PLAYLIST, "http://example.com/playlist.m3u")

    @pytest.mark.asyncio
    async def test_async_set_eq_preset(self, media_player, mock_coordinator):
        """Test async_set_eq service handler with preset."""
        mock_coordinator.player.set_eq_preset = AsyncMock(return_value=True)
        mock_coordinator.data["player"].supports_eq = True

        await media_player.async_set_eq("rock")

        mock_coordinator.player.set_eq_preset.assert_called_once_with("rock")
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_async_set_eq_custom_list(self, media_player, mock_coordinator):
        """Test async_set_eq service handler with custom values as list."""
        mock_coordinator.player.set_eq_custom = AsyncMock(return_value=True)
        mock_coordinator.data["player"].supports_eq = True

        custom_values = [-2, 0, 2, 3, 1, 0, 0, -1, 2, 4]
        await media_player.async_set_eq("custom", custom_values)

        mock_coordinator.player.set_eq_custom.assert_called_once_with(custom_values)
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_async_set_eq_custom_dict(self, media_player, mock_coordinator):
        """Test async_set_eq service handler with custom values as dict."""
        mock_coordinator.player.set_eq_custom = AsyncMock(return_value=True)
        mock_coordinator.data["player"].supports_eq = True

        custom_values = {"0": -2, "1": 0, "2": 2, "3": 3, "4": 1, "5": 0, "6": 0, "7": -1, "8": 2, "9": 4}
        await media_player.async_set_eq("custom", custom_values)

        # Should convert dict to list
        expected_list = [-2, 0, 2, 3, 1, 0, 0, -1, 2, 4]
        mock_coordinator.player.set_eq_custom.assert_called_once_with(expected_list)
        # State updates automatically via callback - no manual refresh needed

    @pytest.mark.asyncio
    async def test_async_set_eq_requires_custom_values(self, media_player, mock_coordinator):
        """Test async_set_eq requires custom_values when preset is custom."""
        from homeassistant.exceptions import HomeAssistantError

        mock_coordinator.data["player"].supports_eq = True

        with pytest.raises(HomeAssistantError, match="custom_values is required"):
            await media_player.async_set_eq("custom", None)

    @pytest.mark.asyncio
    async def test_async_set_eq_not_supported(self, media_player, mock_coordinator):
        """Test async_set_eq raises error when EQ not supported."""
        from homeassistant.exceptions import HomeAssistantError

        mock_coordinator.data["player"].supports_eq = False

        with pytest.raises(HomeAssistantError, match="EQ is not supported"):
            await media_player.async_set_eq("rock")

    @pytest.mark.asyncio
    async def test_async_set_eq_handles_error(self, media_player, mock_coordinator):
        """Test async_set_eq handles WiiMError."""
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        mock_coordinator.player.set_eq_preset = AsyncMock(side_effect=WiiMError("EQ error"))
        mock_coordinator.data["player"].supports_eq = True

        with pytest.raises(HomeAssistantError, match="Failed to set EQ"):
            await media_player.async_set_eq("rock")

    @pytest.mark.asyncio
    async def test_async_play_notification(self, media_player, mock_coordinator):
        """Test async_play_notification service handler."""
        from homeassistant.components.media_player import ATTR_MEDIA_ANNOUNCE, MediaType

        mock_coordinator.player.play_notification = AsyncMock(return_value=True)
        media_player.hass = MagicMock()
        media_player.async_play_media = AsyncMock()

        await media_player.async_play_notification("http://example.com/notification.mp3")

        # Should call async_play_media with announce=True
        media_player.async_play_media.assert_called_once_with(
            MediaType.MUSIC, "http://example.com/notification.mp3", announce=True
        )

    @pytest.mark.asyncio
    async def test_async_play_queue_no_upnp(self, media_player, mock_coordinator):
        """Test async_play_queue raises error when UPnP not available."""
        from homeassistant.exceptions import HomeAssistantError

        # No queue support
        mock_coordinator.data["player"].supports_queue_add = False

        with pytest.raises(HomeAssistantError, match="Queue playback not available"):
            await media_player.async_play_queue(0)

    @pytest.mark.asyncio
    async def test_async_play_queue_success(self, media_player, mock_coordinator):
        """Test async_play_queue calls pywiim method successfully."""
        from unittest.mock import AsyncMock

        mock_coordinator.data["player"].supports_queue_add = True
        mock_coordinator.player.play_queue = AsyncMock(return_value=None)

        await media_player.async_play_queue(5)

        mock_coordinator.player.play_queue.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_async_remove_from_queue_no_upnp(self, media_player, mock_coordinator):
        """Test async_remove_from_queue raises error when UPnP not available."""
        from homeassistant.exceptions import HomeAssistantError

        mock_coordinator.data["player"].supports_queue_add = False

        with pytest.raises(HomeAssistantError, match="Queue management not available"):
            await media_player.async_remove_from_queue(0)

    @pytest.mark.asyncio
    async def test_async_remove_from_queue_success(self, media_player, mock_coordinator):
        """Test async_remove_from_queue calls pywiim method successfully."""
        from unittest.mock import AsyncMock

        mock_coordinator.data["player"].supports_queue_add = True
        mock_coordinator.player.remove_from_queue = AsyncMock(return_value=None)

        await media_player.async_remove_from_queue(3)

        mock_coordinator.player.remove_from_queue.assert_called_once_with(3)

    @pytest.mark.asyncio
    async def test_async_get_queue_no_upnp(self, media_player, mock_coordinator):
        """Test async_get_queue raises error when UPnP not available."""
        from homeassistant.exceptions import HomeAssistantError

        mock_coordinator.data["player"].supports_queue_browse = False

        with pytest.raises(HomeAssistantError, match="Queue browsing not available"):
            await media_player.async_get_queue()

    @pytest.mark.asyncio
    async def test_async_get_queue_success(self, media_player, mock_coordinator):
        """Test async_get_queue returns queue contents."""
        from unittest.mock import AsyncMock

        mock_coordinator.data["player"].supports_queue_browse = True
        mock_queue = [
            {
                "media_content_id": "http://example.com/song1.mp3",
                "title": "Song 1",
                "artist": "Artist 1",
                "album": "Album 1",
                "duration": 240,
                "position": 0,
            },
            {
                "media_content_id": "http://example.com/song2.mp3",
                "title": "Song 2",
                "artist": "Artist 2",
                "album": "Album 2",
                "duration": 180,
                "position": 1,
            },
        ]
        mock_coordinator.player.get_queue = AsyncMock(return_value=mock_queue)

        result = await media_player.async_get_queue()

        assert result == {"queue": mock_queue}
        mock_coordinator.player.get_queue.assert_called_once()
