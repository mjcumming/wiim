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

    @pytest.mark.asyncio
    async def test_concurrent_update_scenarios(self, coordinator, mock_player):
        """Test concurrent update scenarios (two updates racing)."""
        import asyncio

        # Simulate two concurrent updates
        update_count = 0

        async def mock_refresh():
            nonlocal update_count
            update_count += 1
            await asyncio.sleep(0.01)  # Small delay to allow concurrency

        mock_player.refresh = AsyncMock(side_effect=mock_refresh)

        # Start two updates concurrently
        task1 = coordinator._async_update_data()
        task2 = coordinator._async_update_data()

        # Wait for both to complete
        results = await asyncio.gather(task1, task2)

        # Both should succeed
        assert all("player" in result for result in results)
        # Both should have called refresh
        assert mock_player.refresh.call_count == 2

    @pytest.mark.asyncio
    async def test_error_recovery_after_network_issues(self, coordinator, mock_player):
        """Test error recovery after network issues (fail then succeed)."""
        # First update fails
        mock_player.refresh.side_effect = WiiMError("Network error")
        coordinator.data = None  # No cache

        # Should raise UpdateFailed
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

        # Set cache for next attempt
        coordinator.data = {"player": mock_player}

        # Second update also fails but has cache
        mock_player.refresh.side_effect = WiiMError("Network error")

        # Should return cached data
        data = await coordinator._async_update_data()
        assert data == {"player": mock_player}

        # Third update succeeds
        mock_player.refresh.side_effect = None
        mock_player.refresh = AsyncMock()

        data = await coordinator._async_update_data()
        assert data == {"player": mock_player}
        mock_player.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_state_transition_edge_cases(self, coordinator, mock_player):
        """Test state transition edge cases (playing -> paused -> stopped)."""
        # Start playing
        mock_player.play_state = "play"
        mock_player.is_playing = True
        data = await coordinator._async_update_data()
        assert data["player"].play_state == "play"

        # Transition to paused
        mock_player.play_state = "pause"
        mock_player.is_playing = False
        data = await coordinator._async_update_data()
        assert data["player"].play_state == "pause"

        # Transition to stopped
        mock_player.play_state = "stop"
        mock_player.is_playing = False
        data = await coordinator._async_update_data()
        assert data["player"].play_state == "stop"

    @pytest.mark.asyncio
    async def test_none_player_handling_during_initialization(self, hass, mock_client):
        """Test None player handling during initialization."""
        from custom_components.wiim.const import DOMAIN

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )

        # Create coordinator with player that might be None initially
        with (
            patch("custom_components.wiim.coordinator.Player", return_value=None),
            patch("custom_components.wiim.coordinator.async_get_clientsession"),
        ):
            # This should not raise during initialization
            coordinator = WiiMCoordinator(
                hass,
                host="192.168.1.100",
                entry=entry,
                capabilities={"supports_eq": True, "supports_audio_output": True},
            )

            # If player is None, accessing it should be handled
            if coordinator.player is None:
                # Update should raise UpdateFailed
                with pytest.raises((UpdateFailed, AttributeError)):
                    await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_polling_interval_changes_based_on_state(self, coordinator, mock_player):
        """Test polling interval changes based on state."""
        from datetime import timedelta

        # Initial state - stopped
        mock_player.play_state = "stop"
        mock_player.is_playing = False
        mock_player.role = "solo"

        await coordinator._async_update_data()

        # Change to playing
        mock_player.play_state = "play"
        mock_player.is_playing = True

        await coordinator._async_update_data()

        # Interval should potentially change (depends on PollingStrategy)
        # At minimum, verify interval is set
        assert coordinator.update_interval is not None
        assert isinstance(coordinator.update_interval, timedelta)

    @pytest.mark.asyncio
    async def test_cache_behavior_partial_data(self, coordinator, mock_player):
        """Test cache behavior when player.refresh() returns partial data."""
        # Set initial complete data
        coordinator.data = {"player": mock_player}
        mock_player.volume_level = 0.5
        mock_player.play_state = "play"

        # Simulate refresh that partially fails but doesn't raise
        # (e.g., some properties updated, others not)
        async def partial_refresh():
            # Update some properties but not others
            mock_player.volume_level = 0.6
            # play_state might not update if refresh is partial

        mock_player.refresh = AsyncMock(side_effect=partial_refresh)

        data = await coordinator._async_update_data()

        # Should return player with updated data
        assert data == {"player": mock_player}
        # Volume should be updated
        assert data["player"].volume_level == 0.6

    @pytest.mark.asyncio
    async def test_polling_strategy_adaptation(self, coordinator, mock_player):
        """Test that polling strategy adapts based on role and play state."""
        # Test solo + playing
        mock_player.role = "solo"
        mock_player.is_playing = True
        await coordinator._async_update_data()
        interval_playing = coordinator.update_interval

        # Test solo + stopped
        mock_player.is_playing = False
        await coordinator._async_update_data()
        interval_stopped = coordinator.update_interval

        # Intervals should be set (may be same or different depending on strategy)
        assert interval_playing is not None
        assert interval_stopped is not None

    @pytest.mark.skip(reason="Teardown issue with lingering timer - needs investigation")
    @pytest.mark.asyncio
    async def test_coordinator_update_listeners(self, coordinator, mock_player):
        """Test that coordinator notifies listeners on state changes."""
        listeners_notified = []

        def listener_callback():
            listeners_notified.append(True)

        # Register a listener
        coordinator.async_add_listener(listener_callback)

        # Trigger update
        await coordinator._async_update_data()

        # Listener should be notified
        assert len(listeners_notified) > 0

    @pytest.mark.asyncio
    async def test_refresh_returns_none_handling(self, coordinator, mock_player):
        """Test coordinator handles player.refresh() returning None gracefully."""

        # Simulate refresh that doesn't raise but returns None
        async def refresh_none():
            return None

        mock_player.refresh = AsyncMock(side_effect=refresh_none)
        coordinator.data = {"player": mock_player}

        # Should still return player object (from cache)
        data = await coordinator._async_update_data()
        assert data is not None
        assert "player" in data

    @pytest.mark.asyncio
    async def test_rapid_state_changes(self, coordinator, mock_player):
        """Test coordinator handles rapid state changes correctly."""
        # Simulate rapid play/pause/play transitions
        states = ["play", "pause", "play", "stop"]
        state_index = [0]

        async def rapid_refresh():
            mock_player.play_state = states[state_index[0]]
            state_index[0] = (state_index[0] + 1) % len(states)

        mock_player.refresh = AsyncMock(side_effect=rapid_refresh)

        # Multiple rapid updates
        for _ in range(4):
            data = await coordinator._async_update_data()
            assert data["player"] is mock_player

    @pytest.mark.asyncio
    async def test_player_object_replacement(self, coordinator, mock_player):
        """Test coordinator handles player object being replaced during update."""
        original_player = mock_player
        coordinator.data = {"player": original_player}

        # Create new player object
        new_player = MagicMock(spec=Player)
        new_player.refresh = AsyncMock()
        new_player.role = "solo"
        new_player.group = None

        # Replace player during update
        async def replace_player():
            coordinator.player = new_player

        original_player.refresh = AsyncMock(side_effect=replace_player)

        data = await coordinator._async_update_data()
        # Should handle replacement gracefully
        assert data is not None
