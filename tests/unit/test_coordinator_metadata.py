"""Test coordinator metadata helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.wiim.api import WiiMError
from custom_components.wiim.coordinator_metadata import get_track_metadata_defensive
from custom_components.wiim.models import PlayerStatus, TrackMetadata


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for metadata testing."""
    coordinator = MagicMock()
    coordinator.client = MagicMock()
    coordinator.client.host = "192.168.1.100"
    coordinator._metadata_supported = None  # Not yet tested
    coordinator._last_artwork_url = None
    return coordinator


@pytest.fixture
def basic_status():
    """Create basic PlayerStatus for testing."""
    return PlayerStatus.model_validate(
        {"status": "play", "vol": 50, "Title": "Test Track", "Artist": "Test Artist", "Album": "Test Album"}
    )


async def test_metadata_not_supported_fallback(mock_coordinator, basic_status):
    """Test metadata fallback when getMetaInfo is not supported."""
    mock_coordinator._metadata_supported = False

    result = await get_track_metadata_defensive(mock_coordinator, basic_status)

    assert isinstance(result, TrackMetadata)
    assert result.title == "Test Track"
    assert result.artist == "Test Artist"
    assert result.album == "Test Album"


async def test_metadata_success_first_time(mock_coordinator, basic_status):
    """Test successful metadata retrieval on first attempt."""
    mock_coordinator._metadata_supported = None  # First time
    mock_coordinator.client.get_meta_info = AsyncMock(
        return_value={
            "metaData": {
                "title": "Enhanced Track",
                "artist": "Enhanced Artist",
                "album": "Enhanced Album",
                "cover_url": "http://example.com/cover.jpg",
            }
        }
    )

    result = await get_track_metadata_defensive(mock_coordinator, basic_status)

    assert isinstance(result, TrackMetadata)
    assert result.title == "Enhanced Track"
    assert result.artist == "Enhanced Artist"
    assert result.album == "Enhanced Album"
    assert result.cover_url == "http://example.com/cover.jpg"
    assert mock_coordinator._metadata_supported is True


async def test_metadata_success_already_supported(mock_coordinator, basic_status):
    """Test metadata when already known to be supported."""
    mock_coordinator._metadata_supported = True
    mock_coordinator.client.get_meta_info = AsyncMock(
        return_value={
            "metaData": {
                "title": "Rich Track Info",
                "artist": "Rich Artist Info",
                "albumart": "http://example.com/rich.jpg",
            }
        }
    )

    result = await get_track_metadata_defensive(mock_coordinator, basic_status)

    assert isinstance(result, TrackMetadata)
    assert result.title == "Rich Track Info"
    assert result.artist == "Rich Artist Info"
    assert result.entity_picture == "http://example.com/rich.jpg"


async def test_metadata_wiim_error_first_time(mock_coordinator, basic_status):
    """Test metadata when WiiMError occurs on first attempt."""
    mock_coordinator._metadata_supported = None  # First time
    mock_coordinator.client.get_meta_info = AsyncMock(side_effect=WiiMError("Not supported"))

    result = await get_track_metadata_defensive(mock_coordinator, basic_status)

    assert isinstance(result, TrackMetadata)
    # Should fallback to basic metadata
    assert result.title == "Test Track"
    assert result.artist == "Test Artist"
    assert result.album == "Test Album"
    assert mock_coordinator._metadata_supported is False


async def test_metadata_empty_response(mock_coordinator, basic_status):
    """Test metadata when getMetaInfo returns empty response."""
    mock_coordinator._metadata_supported = True
    mock_coordinator.client.get_meta_info = AsyncMock(return_value={})

    result = await get_track_metadata_defensive(mock_coordinator, basic_status)

    assert isinstance(result, TrackMetadata)
    # Should fallback to basic metadata
    assert result.title == "Test Track"
    assert result.artist == "Test Artist"
    assert result.album == "Test Album"


async def test_metadata_artwork_field_variations(mock_coordinator, basic_status):
    """Test metadata with different artwork field names."""
    mock_coordinator._metadata_supported = True

    artwork_fields = [
        ("cover", "http://example.com/cover1.jpg"),
        ("cover_url", "http://example.com/cover2.jpg"),
        ("albumart", "http://example.com/cover3.jpg"),
        ("albumArtURI", "http://example.com/cover4.jpg"),
        ("art_url", "http://example.com/cover5.jpg"),
        ("thumbnail", "http://example.com/cover6.jpg"),
        ("image", "http://example.com/cover7.jpg"),
        ("coverart", "http://example.com/cover8.jpg"),
        ("artworkUrl", "http://example.com/cover9.jpg"),
    ]

    for field_name, artwork_url in artwork_fields:
        mock_coordinator.client.get_meta_info = AsyncMock(
            return_value={"metaData": {"title": "Test Track", field_name: artwork_url}}
        )

        result = await get_track_metadata_defensive(mock_coordinator, basic_status)

        assert isinstance(result, TrackMetadata)
        assert result.entity_picture == artwork_url
        assert result.cover_url == artwork_url


async def test_metadata_artwork_from_status_fallback(mock_coordinator):
    """Test artwork extraction from status when metadata has none."""
    mock_coordinator._metadata_supported = True
    mock_coordinator.client.get_meta_info = AsyncMock(
        return_value={
            "metaData": {
                "title": "Test Track"
                # No artwork in metadata
            }
        }
    )

    status = PlayerStatus.model_validate(
        {"status": "play", "Title": "Test Track", "cover_url": "http://example.com/status-cover.jpg"}
    )

    result = await get_track_metadata_defensive(mock_coordinator, status)

    assert isinstance(result, TrackMetadata)
    assert result.entity_picture == "http://example.com/status-cover.jpg"
    assert result.cover_url == "http://example.com/status-cover.jpg"


async def test_metadata_artwork_filtering_unknown(mock_coordinator, basic_status):
    """Test that 'un_known' artwork URLs are filtered out."""
    mock_coordinator._metadata_supported = True
    mock_coordinator.client.get_meta_info = AsyncMock(
        return_value={
            "metaData": {
                "title": "Test Track",
                "cover": "un_known",  # Should be filtered
                "cover_url": "http://example.com/real-cover.jpg",  # Should be used
            }
        }
    )

    result = await get_track_metadata_defensive(mock_coordinator, basic_status)

    assert isinstance(result, TrackMetadata)
    assert result.entity_picture == "http://example.com/real-cover.jpg"
    assert result.cover_url == "http://example.com/real-cover.jpg"


async def test_metadata_artwork_logging_changes(mock_coordinator, basic_status):
    """Test artwork change logging."""
    mock_coordinator._metadata_supported = True
    mock_coordinator._last_artwork_url = None

    # First call with artwork
    mock_coordinator.client.get_meta_info = AsyncMock(
        return_value={"metaData": {"title": "Test Track", "cover": "http://example.com/cover1.jpg"}}
    )

    result = await get_track_metadata_defensive(mock_coordinator, basic_status)
    assert result.entity_picture == "http://example.com/cover1.jpg"
    assert mock_coordinator._last_artwork_url == "http://example.com/cover1.jpg"

    # Second call with same artwork (should not log)
    result = await get_track_metadata_defensive(mock_coordinator, basic_status)
    assert result.entity_picture == "http://example.com/cover1.jpg"

    # Third call with different artwork (should log change)
    mock_coordinator.client.get_meta_info = AsyncMock(
        return_value={"metaData": {"title": "Test Track", "cover": "http://example.com/cover2.jpg"}}
    )

    result = await get_track_metadata_defensive(mock_coordinator, basic_status)
    assert result.entity_picture == "http://example.com/cover2.jpg"
    assert mock_coordinator._last_artwork_url == "http://example.com/cover2.jpg"


async def test_metadata_basic_extraction_no_metadata_support(mock_coordinator):
    """Test basic metadata extraction when metadata endpoint not supported."""
    mock_coordinator._metadata_supported = False

    status = PlayerStatus.model_validate(
        {
            "status": "play",
            "Title": "Basic Track",
            "Artist": "Basic Artist",
            "Album": "Basic Album",
            "albumart": "http://example.com/basic-cover.jpg",
        }
    )

    result = await get_track_metadata_defensive(mock_coordinator, status)

    assert isinstance(result, TrackMetadata)
    assert result.title == "Basic Track"
    assert result.artist == "Basic Artist"
    assert result.album == "Basic Album"
    assert result.entity_picture == "http://example.com/basic-cover.jpg"
    assert result.cover_url == "http://example.com/basic-cover.jpg"


async def test_metadata_missing_fields_handling(mock_coordinator, basic_status):
    """Test metadata handling when some fields are missing."""
    mock_coordinator._metadata_supported = True
    mock_coordinator.client.get_meta_info = AsyncMock(
        return_value={
            "metaData": {
                "title": "Only Title"
                # Missing artist and album
            }
        }
    )

    result = await get_track_metadata_defensive(mock_coordinator, basic_status)

    assert isinstance(result, TrackMetadata)
    assert result.title == "Only Title"
    # Should fallback to status for missing fields
    assert result.artist == "Test Artist"
    assert result.album == "Test Album"


async def test_metadata_artwork_removal_logging(mock_coordinator, basic_status):
    """Test artwork removal logging."""
    mock_coordinator._metadata_supported = True
    mock_coordinator._last_artwork_url = "http://example.com/previous.jpg"

    # Call with no artwork
    mock_coordinator.client.get_meta_info = AsyncMock(
        return_value={
            "metaData": {
                "title": "Test Track"
                # No artwork fields
            }
        }
    )

    result = await get_track_metadata_defensive(mock_coordinator, basic_status)

    assert isinstance(result, TrackMetadata)
    assert result.entity_picture is None
    assert result.cover_url is None
    assert mock_coordinator._last_artwork_url is None
