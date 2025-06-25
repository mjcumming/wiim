"""Test enhanced WiiM media browser with HA media source integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.media_player.browse_media import BrowseMedia, MediaClass

from custom_components.wiim.media_player_browser import MediaBrowserMixin


@pytest.fixture
def mock_browser():
    """Create a mock media browser instance."""
    browser = MediaBrowserMixin()
    browser.hass = MagicMock()
    browser.speaker = MagicMock()
    browser.speaker.coordinator = MagicMock()
    browser.speaker.coordinator.data = {"presets": []}
    browser.speaker.coordinator._presets_supported = False  # Default to no presets
    browser.speaker.name = "Test Speaker"
    browser._async_load_quick_stations = AsyncMock(return_value=[])
    return browser


@pytest.fixture
def mock_media_source_root():
    """Create a mock media source root browse result."""
    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="media-source://",
        media_content_type="media_source",
        title="Media Library",
        can_play=False,
        can_expand=True,
        children=[
            BrowseMedia(
                media_class=MediaClass.DIRECTORY,
                media_content_id="media-source://local_media",
                media_content_type="directory",
                title="Local Media",
                can_play=False,
                can_expand=True,
                children=[],
            ),
            BrowseMedia(
                media_class=MediaClass.MUSIC,
                media_content_id="media-source://local_media/music/song1.mp3",
                media_content_type="audio/mpeg",
                title="Song 1",
                can_play=True,
                can_expand=False,
                children=[],
            ),
        ],
    )


def test_is_audio_content_directory(mock_browser):
    """Test that directories are considered audio content for browsing."""
    directory = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="test",
        media_content_type="directory",
        title="Test Directory",
        can_play=False,
        can_expand=True,
        children=[],
    )

    assert mock_browser._is_audio_content(directory) is True


def test_is_audio_content_music_class(mock_browser):
    """Test that music media classes are considered audio content."""
    audio_classes = [
        MediaClass.MUSIC,
        MediaClass.PODCAST,
        MediaClass.ALBUM,
        MediaClass.ARTIST,
        MediaClass.PLAYLIST,
        MediaClass.TRACK,
    ]

    for media_class in audio_classes:
        item = BrowseMedia(
            media_class=media_class,
            media_content_id="test",
            media_content_type="test",
            title="Test",
            can_play=True,
            can_expand=False,
            children=[],
        )
        assert mock_browser._is_audio_content(item) is True


def test_is_audio_content_audio_mime_type(mock_browser):
    """Test that audio MIME types are considered audio content."""
    item = BrowseMedia(
        media_class=MediaClass.GENERIC,
        media_content_id="test.mp3",
        media_content_type="audio/mpeg",
        title="Test Audio",
        can_play=True,
        can_expand=False,
        children=[],
    )

    assert mock_browser._is_audio_content(item) is True


def test_is_audio_content_audio_extensions(mock_browser):
    """Test that audio file extensions are considered audio content."""
    audio_extensions = [".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".wma", ".aiff", ".dsd", ".dsf", ".dff"]

    for ext in audio_extensions:
        item = BrowseMedia(
            media_class=MediaClass.GENERIC,
            media_content_id=f"test{ext}",
            media_content_type="test",
            title="Test Audio",
            can_play=True,
            can_expand=False,
            children=[],
        )
        assert mock_browser._is_audio_content(item) is True


def test_is_audio_content_non_audio(mock_browser):
    """Test that non-audio content is filtered out."""
    item = BrowseMedia(
        media_class=MediaClass.VIDEO,
        media_content_id="test.mp4",
        media_content_type="video/mp4",
        title="Test Video",
        can_play=True,
        can_expand=False,
        children=[],
    )

    assert mock_browser._is_audio_content(item) is False


@pytest.mark.asyncio
async def test_browse_media_root_with_media_sources(mock_browser, mock_media_source_root):
    """Test browsing root level with media sources available."""
    with patch("homeassistant.components.media_source.async_browse_media") as mock_browse:
        mock_browse.return_value = mock_media_source_root

        result = await mock_browser.async_browse_media()

        assert result.title == "Test Speaker"
        assert result.can_expand is True
        assert len(result.children) == 1  # Only Media Library (no presets or quick stations)

        media_library = result.children[0]
        assert media_library.title == "Media Library"
        assert media_library.media_content_id == "media-source://"
        assert media_library.thumbnail == "mdi:folder-music"


@pytest.mark.asyncio
async def test_browse_media_root_no_media_sources(mock_browser):
    """Test browsing root level when media sources are not available."""
    with patch("homeassistant.components.media_source.async_browse_media", side_effect=Exception("No media sources")):
        result = await mock_browser.async_browse_media()

        # Should return empty directory when no content available
        assert result.title == "Test Speaker"
        assert result.can_expand is False
        assert len(result.children) == 0


@pytest.mark.asyncio
async def test_browse_media_source_root(mock_browser, mock_media_source_root):
    """Test browsing media-source:// root."""
    with patch("homeassistant.components.media_source.async_browse_media") as mock_browse:
        mock_browse.return_value = mock_media_source_root

        result = await mock_browser.async_browse_media(media_content_id="media-source://")

        assert result.title == "Media Library"
        assert len(result.children) == 2  # Directory + audio file

        # Check that both directory and audio content are included
        assert result.children[0].title == "Local Media"
        assert result.children[1].title == "Song 1"


@pytest.mark.asyncio
async def test_browse_media_source_with_filtering(mock_browser):
    """Test browsing media source with audio content filtering."""
    mixed_content = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="media-source://mixed",
        media_content_type="directory",
        title="Mixed Content",
        can_play=False,
        can_expand=True,
        children=[
            BrowseMedia(
                media_class=MediaClass.MUSIC,
                media_content_id="song.mp3",
                media_content_type="audio/mpeg",
                title="Audio File",
                can_play=True,
                can_expand=False,
                children=[],
            ),
            BrowseMedia(
                media_class=MediaClass.VIDEO,
                media_content_id="video.mp4",
                media_content_type="video/mp4",
                title="Video File",
                can_play=True,
                can_expand=False,
                children=[],
            ),
            BrowseMedia(
                media_class=MediaClass.DIRECTORY,
                media_content_id="subfolder",
                media_content_type="directory",
                title="Subfolder",
                can_play=False,
                can_expand=True,
                children=[],
            ),
        ],
    )

    with patch("homeassistant.components.media_source.async_browse_media") as mock_browse:
        mock_browse.return_value = mixed_content

        result = await mock_browser.async_browse_media(media_content_id="media-source://mixed")

        # Should only include audio file and directory, not video
        assert len(result.children) == 2
        assert result.children[0].title == "Audio File"
        assert result.children[1].title == "Subfolder"


@pytest.mark.asyncio
async def test_browse_media_source_error(mock_browser):
    """Test handling of media source browsing errors."""
    from homeassistant.components.media_player.browse_media import BrowseError

    with patch("homeassistant.components.media_source.async_browse_media", side_effect=Exception("Browse failed")):
        with pytest.raises(BrowseError, match="Failed to browse media source"):
            await mock_browser.async_browse_media(media_content_id="media-source://invalid")


@pytest.mark.asyncio
async def test_browse_media_source_specific_path(mock_browser):
    """Test browsing a specific media source path."""
    subfolder_content = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="media-source://local_media/music",
        media_content_type="directory",
        title="Music",
        can_play=False,
        can_expand=True,
        children=[
            BrowseMedia(
                media_class=MediaClass.MUSIC,
                media_content_id="media-source://local_media/music/album1/track1.flac",
                media_content_type="audio/flac",
                title="Track 1",
                can_play=True,
                can_expand=False,
                children=[],
            ),
        ],
    )

    with patch("homeassistant.components.media_source.async_browse_media") as mock_browse:
        mock_browse.return_value = subfolder_content

        result = await mock_browser.async_browse_media(media_content_id="media-source://local_media/music")

        assert result.title == "Music"
        assert len(result.children) == 1
        assert result.children[0].title == "Track 1"
        assert result.children[0].media_content_type == "audio/flac"


@pytest.mark.asyncio
async def test_browse_media_with_presets_and_quick_stations(mock_browser):
    """Test browsing root with all content types available."""
    # Enable presets support
    mock_browser.speaker.coordinator._presets_supported = True

    # Set up presets
    mock_browser.speaker.coordinator.data = {
        "presets": [
            {"name": "Preset 1", "number": 1, "url": "http://example.com/stream1"},
        ]
    }

    # Set up quick stations
    mock_browser._async_load_quick_stations.return_value = [
        {"name": "Station 1", "url": "http://example.com/station1"},
    ]

    # Mock media sources available
    with patch("homeassistant.components.media_source.async_browse_media") as mock_browse:
        mock_browse.return_value = BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id="media-source://",
            media_content_type="media_source",
            title="Media Library",
            can_play=False,
            can_expand=True,
            children=[MagicMock()],  # At least one child
        )

        result = await mock_browser.async_browse_media()

        assert result.title == "Test Speaker"
        assert len(result.children) == 3  # Media Library + Presets + Quick Stations

        # Check order and content
        assert result.children[0].title == "Media Library"
        assert result.children[0].thumbnail == "mdi:folder-music"

        assert result.children[1].title == "Presets"
        assert result.children[1].thumbnail == "mdi:star"

        assert result.children[2].title == "Quick Stations"
        assert result.children[2].thumbnail == "mdi:radio"


@pytest.mark.asyncio
async def test_browse_media_unknown_content_id(mock_browser):
    """Test handling of unknown media content IDs."""
    from homeassistant.components.media_player.browse_media import BrowseError

    with pytest.raises(BrowseError, match="Unknown media_content_id"):
        await mock_browser.async_browse_media(media_content_id="unknown_id")


@pytest.mark.asyncio
async def test_browse_presets_shelf(mock_browser):
    """Test browsing the presets shelf."""
    # Enable presets support
    mock_browser.speaker.coordinator._presets_supported = True

    mock_browser.speaker.coordinator.data = {
        "presets": [
            {"name": "Jazz Radio", "number": 1, "url": "http://jazz.example.com", "picurl": "http://jazz.jpg"},
            {"name": "Rock FM", "number": 2, "url": "http://rock.example.com"},
        ]
    }

    result = await mock_browser.async_browse_media(media_content_id="presets")

    assert result.title == "Presets"
    assert len(result.children) == 2

    assert result.children[0].title == "Jazz Radio"
    assert result.children[0].media_content_id == "1"
    assert result.children[0].media_content_type == "preset"
    assert result.children[0].thumbnail == "http://jazz.jpg"

    assert result.children[1].title == "Rock FM"
    assert result.children[1].media_content_id == "2"
    assert result.children[1].media_content_type == "preset"


@pytest.mark.asyncio
async def test_browse_quick_stations_shelf(mock_browser):
    """Test browsing the quick stations shelf."""
    mock_browser._async_load_quick_stations.return_value = [
        {"name": "Classical Stream", "url": "http://classical.example.com"},
        {"name": "News Radio", "url": "http://news.example.com"},
    ]

    result = await mock_browser.async_browse_media(media_content_id="quick")

    assert result.title == "Quick Stations"
    assert len(result.children) == 2

    assert result.children[0].title == "Classical Stream"
    assert result.children[0].media_content_id == "http://classical.example.com"
    assert result.children[0].media_content_type == "url"

    assert result.children[1].title == "News Radio"
    assert result.children[1].media_content_id == "http://news.example.com"
    assert result.children[1].media_content_type == "url"
