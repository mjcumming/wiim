"""Core entity tests for WiiM - testing base entity class."""

from unittest.mock import MagicMock

import pytest
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.wiim.data import Speaker
from custom_components.wiim.entity import WiimEntity


class TestWiimEntity:
    """Test WiimEntity - base entity class."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        from unittest.mock import AsyncMock

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.async_request_refresh = AsyncMock()
        return coordinator

    @pytest.fixture
    def mock_speaker(self, mock_coordinator):
        """Create a mock speaker."""
        speaker = MagicMock(spec=Speaker)
        speaker.coordinator = mock_coordinator
        speaker.device_info = DeviceInfo(
            identifiers={("wiim", "test-uuid")},
            manufacturer="WiiM",
            name="Test WiiM",
            model="WiiM Mini",
        )
        speaker.available = True
        return speaker

    @pytest.fixture
    def entity(self, mock_speaker):
        """Create a WiimEntity instance."""
        return WiimEntity(mock_speaker)

    def test_entity_initialization(self, entity, mock_speaker):
        """Test entity is initialized correctly."""
        assert entity.speaker is mock_speaker
        assert entity.coordinator is mock_speaker.coordinator

    def test_entity_device_info(self, entity, mock_speaker):
        """Test entity device_info property."""
        device_info = entity.device_info
        assert device_info is mock_speaker.device_info
        assert device_info["identifiers"] == {("wiim", "test-uuid")}
        assert device_info["manufacturer"] == "WiiM"

    def test_entity_available(self, entity, mock_speaker):
        """Test entity available property."""
        mock_speaker.available = True
        assert entity.available is True

        mock_speaker.available = False
        assert entity.available is False

    @pytest.mark.asyncio
    async def test_async_execute_command_with_refresh(self, entity, mock_speaker):
        """Test async_execute_command_with_refresh requests refresh."""
        await entity._async_execute_command_with_refresh("test_command")

        mock_speaker.coordinator.async_request_refresh.assert_called_once()
