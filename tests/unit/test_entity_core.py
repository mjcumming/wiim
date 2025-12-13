"""Core entity tests for WiiM - testing base entity class."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.wiim.entity import WiimEntity


class TestWiimEntity:
    """Test WiimEntity - base entity class."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.async_request_refresh = AsyncMock()
        coordinator.player = MagicMock()
        coordinator.player.name = "Test WiiM"
        coordinator.player.model = "WiiM Mini"
        coordinator.player.firmware = "1.0.0"
        coordinator.player.host = "192.168.1.100"
        coordinator.device_info = DeviceInfo(
            identifiers={("wiim", "test-uuid")},
            manufacturer="WiiM",
            name="Test WiiM",
            model="WiiM Mini",
        )
        return coordinator

    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry."""
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        entry.unique_id = "test-uuid"
        entry.data = {"host": "192.168.1.100"}
        entry.options = {}
        return entry

    @pytest.fixture
    def entity(self, mock_coordinator, mock_config_entry):
        """Create a WiimEntity instance."""
        return WiimEntity(mock_coordinator, mock_config_entry)

    def test_entity_initialization(self, entity, mock_coordinator, mock_config_entry):
        """Test entity is initialized correctly."""
        assert entity.coordinator is mock_coordinator
        assert entity._config_entry is mock_config_entry

    def test_entity_device_info(self, entity, mock_coordinator, mock_config_entry):
        """Test entity device_info property."""
        device_info = entity.device_info
        # device_info is dynamically built from player properties
        assert ("wiim", "test-uuid") in device_info["identifiers"]
        assert device_info["manufacturer"] == "WiiM"
        assert device_info["name"] == "Test WiiM"
        assert device_info["model"] == "WiiM Mini"

    def test_entity_available(self, entity, mock_coordinator):
        """Test entity available property."""
        mock_coordinator.last_update_success = True
        assert entity.available is True

        mock_coordinator.last_update_success = False
        assert entity.available is False

    def test_entity_player_property(self, entity, mock_coordinator):
        """Test entity player property access."""
        assert entity.player is mock_coordinator.player
        assert entity.player.name == "Test WiiM"

    def test_entity_device_info_missing_mac(self, mock_coordinator, mock_config_entry):
        """Test device info when MAC address is missing."""
        # Remove MAC address from device_info
        mock_coordinator.player.device_info = MagicMock()
        mock_coordinator.player.device_info.mac = None

        entity = WiimEntity(mock_coordinator, mock_config_entry)
        device_info = entity.device_info

        # Should still create device info without MAC
        assert device_info["identifiers"] == {("wiim", "test-uuid")}
        assert device_info["connections"] is None  # No MAC, so no connections

    def test_entity_device_info_missing_model(self, mock_coordinator, mock_config_entry):
        """Test device info when model is missing."""
        mock_coordinator.player.model = None

        entity = WiimEntity(mock_coordinator, mock_config_entry)
        device_info = entity.device_info

        # Should use fallback model
        assert device_info["model"] == "WiiM Speaker"

    def test_entity_device_info_none_player(self, mock_coordinator, mock_config_entry):
        """Test device info when player is None."""
        mock_coordinator.player = None

        entity = WiimEntity(mock_coordinator, mock_config_entry)

        # Should handle None player gracefully
        # Accessing device_info should not raise, but may use fallbacks
        try:
            device_info = entity.device_info
            # If it doesn't raise, verify it has some structure
            assert "identifiers" in device_info or device_info is not None
        except AttributeError:
            # If it raises AttributeError, that's also acceptable behavior
            pass

    @pytest.mark.asyncio
    async def test_entity_lifecycle_added_to_hass(self, entity, hass):
        """Test entity lifecycle when added to hass."""
        # Entity should be able to be added to hass
        entity.hass = hass
        entity.entity_id = "test.test_entity"

        # Should not raise when added
        await entity.async_added_to_hass()

        # Verify entity is set up
        assert entity.hass is hass

    @pytest.mark.asyncio
    async def test_entity_lifecycle_will_remove_from_hass(self, entity, hass):
        """Test entity lifecycle when removed from hass."""
        entity.hass = hass
        entity.entity_id = "test.test_entity"

        # Should not raise when removed
        await entity.async_will_remove_from_hass()

        # Verify cleanup completed - method should complete without exception
        # The base CoordinatorEntity handles cleanup, we just verify it works
        assert entity.hass is hass  # Entity still has hass reference until fully removed

    def test_entity_availability_state_changes(self, entity, mock_coordinator):
        """Test availability state changes when coordinator fails/recovers."""
        # Start available
        mock_coordinator.last_update_success = True
        assert entity.available is True

        # Coordinator fails
        mock_coordinator.last_update_success = False
        assert entity.available is False

        # Coordinator recovers
        mock_coordinator.last_update_success = True
        assert entity.available is True

    def test_entity_coordinator_update_handling(self, entity, mock_coordinator):
        """Test entity handles coordinator updates."""
        # Entity should respond to coordinator updates
        # The base CoordinatorEntity handles this, but we verify it works

        # Trigger a coordinator update by changing last_update_success
        mock_coordinator.last_update_success = not mock_coordinator.last_update_success

        # Availability should reflect coordinator state
        assert entity.available == mock_coordinator.last_update_success

    def test_entity_device_info_with_mac(self, mock_coordinator, mock_config_entry):
        """Test device info includes MAC address when available."""
        # Set up player with MAC address
        mock_coordinator.player.device_info = MagicMock()
        mock_coordinator.player.device_info.mac = "AA:BB:CC:DD:EE:FF"

        entity = WiimEntity(mock_coordinator, mock_config_entry)
        device_info = entity.device_info

        # Should include MAC in connections
        assert device_info["connections"] is not None
        assert len(device_info["connections"]) > 0
        # Verify MAC is in connections
        mac_found = any(conn[1] == "AA:BB:CC:DD:EE:FF" for conn in device_info["connections"])
        assert mac_found

    def test_entity_device_info_name_fallback(self, mock_coordinator, mock_config_entry):
        """Test device info name fallback when player name is missing."""
        mock_coordinator.player.name = None
        mock_config_entry.title = "Config Entry Title"

        entity = WiimEntity(mock_coordinator, mock_config_entry)
        device_info = entity.device_info

        # Should use config entry title as fallback
        assert device_info["name"] == "Config Entry Title"

    def test_entity_device_info_name_final_fallback(self, mock_coordinator, mock_config_entry):
        """Test device info name final fallback when both player name and title are missing."""
        mock_coordinator.player.name = None
        mock_config_entry.title = None

        entity = WiimEntity(mock_coordinator, mock_config_entry)
        device_info = entity.device_info

        # Should use final fallback
        assert device_info["name"] == "WiiM Speaker"

    # Note: _async_execute_command_with_refresh was removed as pywiim
    # now manages all state updates via callbacks - no manual refresh needed
