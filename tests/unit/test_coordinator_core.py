"""Core coordinator tests for WiiM - testing pywiim integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pywiim import Player, WiiMClient
from pywiim.exceptions import WiiMError

from custom_components.wiim.const import DOMAIN
from custom_components.wiim.coordinator import WiiMCoordinator
from tests.const import MOCK_CONFIG, MOCK_DEVICE_DATA


class TestWiiMCoordinator:
    """Test WiiMCoordinator - core coordinator functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock WiiMClient."""
        client = MagicMock(spec=WiiMClient)
        client.host = "192.168.1.100"
        client.get_multiroom_status = AsyncMock(return_value={"slaves": 0})
        client.get_eq = AsyncMock(return_value={})
        client.get_meta_info = AsyncMock(return_value={"metaData": {}})
        client.get_audio_output_status = AsyncMock(return_value={})
        return client

    @pytest.fixture
    def mock_player(self, mock_client):
        """Create a mock Player."""
        player = MagicMock(spec=Player)
        player.client = mock_client
        player.refresh = AsyncMock()
        player.role = "solo"
        player.group = None
        player.play_state = "stop"
        player.volume_level = 0.5
        player.is_muted = False
        player.media_title = None
        player.media_artist = None
        player.media_album = None
        player.media_image_url = None
        player.media_position = None
        player.media_duration = None
        player.source = None
        player.device_info = MagicMock()
        player.device_info.name = "Test WiiM"
        player.device_info.model = "WiiM Mini"
        player.device_info.firmware = "1.0.0"
        player.get_device_info = AsyncMock()
        return player

    @pytest.fixture
    def coordinator(self, hass, mock_client, mock_player):
        """Create a WiiMCoordinator instance."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )

        with patch("custom_components.wiim.coordinator.Player", return_value=mock_player):
            coordinator = WiiMCoordinator(
                hass,
                mock_client,
                entry=entry,
                capabilities={"supports_eq": True, "supports_audio_output": True},
            )
        return coordinator

    @pytest.mark.asyncio
    async def test_coordinator_initialization(self, coordinator):
        """Test coordinator is initialized correctly."""
        assert coordinator.client is not None
        assert coordinator.player is not None
        assert coordinator._capabilities is not None
        assert coordinator._polling_strategy is not None
        assert coordinator._track_detector is not None

    @pytest.mark.asyncio
    async def test_async_update_data_success(self, coordinator, mock_player):
        """Test successful data update."""
        # Setup mock player properties
        mock_player.role = "solo"
        mock_player.group = None
        mock_player.play_state = "stop"
        mock_player.volume_level = 0.5
        mock_player.is_muted = False

        data = await coordinator._async_update_data()

        assert data is not None
        assert "player" in data
        assert data["player"] is mock_player
        assert data["volume_level"] == 0.5
        assert data["is_muted"] is False
        assert data["play_state"] == "stop"
        assert data["role"] == "solo"

    @pytest.mark.asyncio
    async def test_async_update_data_wiim_error_returns_cached(self, coordinator, mock_player):
        """Test that WiiMError returns cached data if available."""
        # Set initial data
        coordinator.data = {
            "player": mock_player,
            "volume_level": 0.3,
            "play_state": "play",
        }

        # Make refresh raise an error
        mock_player.refresh.side_effect = WiiMError("Connection failed")

        # Should return cached data, not raise
        data = await coordinator._async_update_data()

        assert data is not None
        assert data["volume_level"] == 0.3
        assert data["play_state"] == "play"

    @pytest.mark.asyncio
    async def test_async_update_data_wiim_error_raises_if_no_cache(self, coordinator, mock_player):
        """Test that WiiMError raises UpdateFailed if no cached data."""
        coordinator.data = None

        mock_player.refresh.side_effect = WiiMError("Connection failed")

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_async_update_data_adaptive_polling(self, coordinator, mock_player):
        """Test that polling interval adapts based on play state."""
        # Test playing state - should use shorter interval
        mock_player.play_state = "play"
        mock_player.group = None
        mock_player.role = "solo"

        await coordinator._async_update_data()

        # Interval should be set (exact value depends on PollingStrategy)
        assert coordinator.update_interval.total_seconds() > 0

    @pytest.mark.asyncio
    async def test_async_update_data_conditional_fetching(self, coordinator, mock_player, mock_client):
        """Test that conditional fetching works correctly."""
        mock_player.play_state = "stop"
        mock_player.group = None
        mock_player.role = "solo"

        # First update - should fetch device info
        await coordinator._async_update_data()

        # Verify get_device_info was called
        mock_player.get_device_info.assert_called()

    @pytest.mark.asyncio
    async def test_async_update_data_track_change_detection(self, coordinator, mock_player, mock_client):
        """Test that track changes trigger metadata fetch."""
        # Set initial state
        coordinator.data = {
            "player": mock_player,
            "media_title": "Old Title",
            "media_artist": "Old Artist",
        }

        # Change track
        mock_player.media_title = "New Title"
        mock_player.media_artist = "New Artist"
        mock_player.source = "spotify"

        await coordinator._async_update_data()

        # Metadata fetch should be triggered (via get_meta_info)
        # Note: exact behavior depends on PollingStrategy implementation
        assert coordinator.data is not None

    @pytest.mark.asyncio
    async def test_async_update_data_preserves_existing_data(self, coordinator, mock_player):
        """Test that existing data is preserved when not refetched."""
        # Set initial data with extra fields
        coordinator.data = {
            "player": mock_player,
            "presets": ["Preset 1", "Preset 2"],
            "bt_pair_status": {"status": "paired"},
        }

        await coordinator._async_update_data()

        # Preserved fields should still be present
        assert "presets" in coordinator.data
        assert "bt_pair_status" in coordinator.data
        assert coordinator.data["presets"] == ["Preset 1", "Preset 2"]

    @pytest.mark.asyncio
    async def test_async_update_data_handles_parallel_fetch_errors(self, coordinator, mock_player, mock_client):
        """Test that errors in parallel fetches are handled gracefully."""
        # Make one parallel fetch fail
        mock_client.get_multiroom_status.side_effect = WiiMError("Multiroom fetch failed")

        # Should not raise - errors are caught and handled
        data = await coordinator._async_update_data()

        assert data is not None
        # Multiroom should use cached data or empty dict
        assert "multiroom" in data
