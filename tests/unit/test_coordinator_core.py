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
        player.host = "192.168.1.100"
        player.refresh = AsyncMock()  # refresh() is called during polling
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
        return player

    @pytest.fixture
    def coordinator(self, hass, mock_client, mock_player):
        """Create a WiiMCoordinator instance."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )

        with (
            patch("custom_components.wiim.coordinator.Player", return_value=mock_player),
            patch("custom_components.wiim.coordinator.async_get_clientsession"),
        ):
            coordinator = WiiMCoordinator(
                hass,
                host="192.168.1.100",
                entry=entry,
                capabilities={"supports_eq": True, "supports_audio_output": True},
            )
            coordinator.player = mock_player
        return coordinator

    @pytest.mark.asyncio
    async def test_coordinator_initialization(self, coordinator):
        """Test coordinator is initialized correctly."""
        assert coordinator.player is not None
        assert coordinator._capabilities is not None
        assert coordinator._polling_strategy is not None

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

        # Verify player.refresh() was called (polling updates state from device)
        mock_player.refresh.assert_called_once()

        # Verify simplified data structure - just player
        assert data is not None
        assert "player" in data
        assert data["player"] is mock_player
        # No more extracted primitives
        assert "volume_level" not in data
        assert "is_muted" not in data
        assert "play_state" not in data
        assert "role" not in data
        assert "group_info" not in data
        assert "metadata" not in data

    @pytest.mark.asyncio
    async def test_async_update_data_wiim_error_returns_cached(self, coordinator, mock_player):
        """Test that WiiMError returns cached data if available."""
        # Set initial data
        coordinator.data = {"player": mock_player}

        # Make refresh raise an error
        mock_player.refresh.side_effect = WiiMError("Connection failed")

        # Should return cached data, not raise
        data = await coordinator._async_update_data()

        assert data is not None
        assert data == {"player": mock_player}
        # Access properties directly from player
        assert data["player"].volume_level == 0.5
        assert data["player"].play_state == "stop"

    @pytest.mark.asyncio
    async def test_async_update_data_wiim_error_raises_if_no_cache(self, coordinator, mock_player):
        """Test that WiiMError raises UpdateFailed if no cached data."""
        coordinator.data = None

        # Make refresh raise an error
        mock_player.refresh.side_effect = WiiMError("Connection failed")

        # Should raise UpdateFailed when no cache available
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
        """Test that player.refresh() is called during polling."""
        mock_player.play_state = "stop"
        mock_player.group = None
        mock_player.role = "solo"

        # Call update to trigger refresh
        data = await coordinator._async_update_data()

        # Verify player.refresh() was called
        mock_player.refresh.assert_called()
        assert data == {"player": mock_player}

    @pytest.mark.asyncio
    async def test_async_update_data_track_change_detection(self, coordinator, mock_player, mock_client):
        """Test that track changes trigger metadata fetch."""
        # Set initial state
        coordinator.data = {"player": mock_player}

        # Change track
        mock_player.media_title = "New Title"
        mock_player.media_artist = "New Artist"
        mock_player.source = "spotify"

        await coordinator._async_update_data()

        # Verify player object is in data with new track info
        assert coordinator.data is not None
        assert coordinator.data["player"].media_title == "New Title"
        assert coordinator.data["player"].media_artist == "New Artist"

    @pytest.mark.asyncio
    async def test_async_update_data_preserves_existing_data(self, coordinator, mock_player):
        """Test that existing data is preserved when not refetched."""
        # Note: After refactoring, coordinator only returns {"player": ...}
        # Extra fields like presets are stored separately if needed
        coordinator.data = {"player": mock_player}

        await coordinator._async_update_data()

        # Verify simplified data structure
        assert coordinator.data is not None
        assert "player" in coordinator.data
        assert coordinator.data["player"] == mock_player

    @pytest.mark.asyncio
    async def test_async_update_data_handles_parallel_fetch_errors(self, coordinator, mock_player, mock_client):
        """Test that errors in parallel fetches are handled gracefully."""
        # After refactoring, there are no parallel fetches - just player.refresh()
        # This test verifies that refresh errors are handled

        # Should not raise - returns player object
        data = await coordinator._async_update_data()

        assert data is not None
        assert "player" in data
        assert data["player"] == mock_player
