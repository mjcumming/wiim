"""Test enhanced WiiM media commands with media source integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.media_player import MediaType
from homeassistant.exceptions import HomeAssistantError

from custom_components.wiim.media_player_commands import MediaCommandsMixin


@pytest.fixture
def mock_media_player():
    """Create a mock media player with MediaCommandsMixin."""
    player = MediaCommandsMixin()
    player.hass = MagicMock()
    player.controller = MagicMock()
    player.speaker = MagicMock()
    player._optimistic_media_title = None
    player._optimistic_state = None
    player._optimistic_source = None
    player.async_write_ha_state = MagicMock()
    player._async_execute_command_with_immediate_refresh = AsyncMock()
    player._async_lookup_quick_station_title = AsyncMock(return_value=None)
    return player


@pytest.fixture
def mock_resolved_media():
    """Create a mock resolved media item."""
    item = MagicMock()
    item.url = "http://localhost:8123/api/media_source_proxy/file.mp3"
    item.mime_type = "audio/mpeg"
    return item


def test_is_audio_media_source_with_audio_mime_type(mock_media_player):
    """Test audio media source detection with audio MIME type."""
    play_item = MagicMock()
    play_item.mime_type = "audio/mpeg"
    play_item.url = "http://example.com/song.mp3"

    assert mock_media_player._is_audio_media_source(play_item) is True


def test_is_audio_media_source_with_audio_extension(mock_media_player):
    """Test audio media source detection with audio file extension."""
    play_item = MagicMock()
    play_item.mime_type = None
    play_item.url = "http://example.com/song.flac"

    assert mock_media_player._is_audio_media_source(play_item) is True


def test_is_audio_media_source_with_video_mime_type(mock_media_player):
    """Test that video MIME types are rejected."""
    play_item = MagicMock()
    play_item.mime_type = "video/mp4"
    play_item.url = "http://example.com/video.mp4"

    assert mock_media_player._is_audio_media_source(play_item) is False


def test_is_audio_media_source_with_unknown_type(mock_media_player):
    """Test that unknown types are rejected."""
    play_item = MagicMock()
    play_item.mime_type = "application/octet-stream"
    play_item.url = "http://example.com/unknown.bin"

    assert mock_media_player._is_audio_media_source(play_item) is False


def test_is_audio_media_source_all_extensions(mock_media_player):
    """Test all supported audio extensions."""
    extensions = [".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".wma", ".aiff", ".dsd", ".dsf", ".dff"]

    for ext in extensions:
        play_item = MagicMock()
        play_item.mime_type = None
        play_item.url = f"http://example.com/song{ext}"

        assert mock_media_player._is_audio_media_source(play_item) is True, f"Extension {ext} should be supported"


@pytest.mark.asyncio
async def test_play_media_source_success(mock_media_player, mock_resolved_media):
    """Test successful media source resolution and playback."""
    with patch("homeassistant.components.media_source.async_resolve_media") as mock_resolve:
        mock_resolve.return_value = mock_resolved_media

        await mock_media_player.async_play_media("music", "media-source://local_media/song.mp3")

        # Should resolve the media source
        mock_resolve.assert_called_once_with(mock_media_player.hass, "media-source://local_media/song.mp3")

        # Should call controller.play_url with resolved URL
        mock_media_player.controller.play_url.assert_called_once_with(mock_resolved_media.url)

        # Should request immediate refresh
        mock_media_player._async_execute_command_with_immediate_refresh.assert_called_once_with("play_media")


@pytest.mark.asyncio
async def test_play_media_source_resolution_error(mock_media_player):
    """Test handling of media source resolution errors."""
    with patch("homeassistant.components.media_source.async_resolve_media", side_effect=Exception("Resolution failed")):
        with pytest.raises(HomeAssistantError, match="Failed to resolve media source"):
            await mock_media_player.async_play_media("music", "media-source://invalid")


@pytest.mark.asyncio
async def test_play_media_source_unsupported_type(mock_media_player):
    """Test handling of unsupported media types from media source."""
    video_item = MagicMock()
    video_item.url = "http://localhost:8123/api/media_source_proxy/video.mp4"
    video_item.mime_type = "video/mp4"

    with patch("homeassistant.components.media_source.async_resolve_media") as mock_resolve:
        mock_resolve.return_value = video_item

        with pytest.raises(HomeAssistantError, match="Unsupported media type for WiiM"):
            await mock_media_player.async_play_media("music", "media-source://local_media/video.mp4")


@pytest.mark.asyncio
async def test_play_media_regular_url_unchanged(mock_media_player):
    """Test that regular URLs are not processed as media sources."""
    await mock_media_player.async_play_media(MediaType.URL, "http://example.com/stream.mp3")

    # Should not attempt to resolve as media source
    with patch("homeassistant.components.media_source.async_resolve_media") as mock_resolve:
        mock_resolve.assert_not_called()

    # Should play URL directly
    mock_media_player.controller.play_url.assert_called_once_with("http://example.com/stream.mp3")


@pytest.mark.asyncio
async def test_play_media_preset_unchanged(mock_media_player):
    """Test that preset playback is unchanged."""
    mock_media_player.async_play_preset = AsyncMock()

    await mock_media_player.async_play_media("preset", "1")

    # Should call preset playback
    mock_media_player.async_play_preset.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_play_media_source_with_quick_station_title(mock_media_player, mock_resolved_media):
    """Test media source playback with quick station title optimization."""
    # Mock quick station lookup to return a friendly name
    mock_media_player._async_lookup_quick_station_title.return_value = "My Favorite Stream"

    with patch("homeassistant.components.media_source.async_resolve_media") as mock_resolve:
        mock_resolve.return_value = mock_resolved_media

        await mock_media_player.async_play_media("music", "media-source://local_media/favorite.mp3")

        # Should set optimistic media title
        assert mock_media_player._optimistic_media_title == "My Favorite Stream"

        # Should call async_write_ha_state to update UI immediately
        mock_media_player.async_write_ha_state.assert_called()


@pytest.mark.asyncio
async def test_play_media_source_without_quick_station_title(mock_media_player, mock_resolved_media):
    """Test media source playback without quick station title."""
    # Mock quick station lookup to return None
    mock_media_player._async_lookup_quick_station_title.return_value = None

    with patch("homeassistant.components.media_source.async_resolve_media") as mock_resolve:
        mock_resolve.return_value = mock_resolved_media

        await mock_media_player.async_play_media("music", "media-source://local_media/song.mp3")

        # Should clear optimistic media title
        assert mock_media_player._optimistic_media_title is None

        # Should call async_write_ha_state to update UI immediately
        mock_media_player.async_write_ha_state.assert_called()


@pytest.mark.asyncio
async def test_play_media_audio_mime_type_resolution(mock_media_player, mock_resolved_media):
    """Test that audio MIME types are resolved as media sources."""
    with patch("homeassistant.components.media_source.async_resolve_media") as mock_resolve:
        mock_resolve.return_value = mock_resolved_media

        await mock_media_player.async_play_media("audio/mpeg", "media-source://local_media/song.mp3")

        # Should resolve and play
        mock_resolve.assert_called_once()
        mock_media_player.controller.play_url.assert_called_once_with(mock_resolved_media.url)


@pytest.mark.asyncio
async def test_play_media_optimistic_state_updates(mock_media_player, mock_resolved_media):
    """Test that optimistic state is properly updated during media source playback."""
    with patch("homeassistant.components.media_source.async_resolve_media") as mock_resolve:
        mock_resolve.return_value = mock_resolved_media

        await mock_media_player.async_play_media("music", "media-source://local_media/song.mp3")

        # Should set optimistic state to playing
        from homeassistant.components.media_player import MediaPlayerState

        assert mock_media_player._optimistic_state == MediaPlayerState.PLAYING

        # Should clear optimistic source initially (will be set by device response)
        assert mock_media_player._optimistic_source is None

        # Should call async_write_ha_state for immediate UI feedback
        mock_media_player.async_write_ha_state.assert_called()


@pytest.mark.asyncio
async def test_play_media_controller_error_handling(mock_media_player, mock_resolved_media):
    """Test error handling when controller.play_url fails."""
    with patch("homeassistant.components.media_source.async_resolve_media") as mock_resolve:
        mock_resolve.return_value = mock_resolved_media
        mock_media_player.controller.play_url.side_effect = Exception("Playback failed")

        with pytest.raises(Exception, match="Playback failed"):
            await mock_media_player.async_play_media("music", "media-source://local_media/song.mp3")

        # Should still have attempted to resolve
        mock_resolve.assert_called_once()
        mock_media_player.controller.play_url.assert_called_once()


@pytest.mark.asyncio
async def test_play_media_unsupported_media_type_warning(mock_media_player):
    """Test warning for unsupported media types."""
    with patch("custom_components.wiim.media_player_commands._LOGGER") as mock_logger:
        await mock_media_player.async_play_media("unsupported_type", "some_id")

        # Should log warning
        mock_logger.warning.assert_called_with("Unsupported media type: %s", "unsupported_type")
