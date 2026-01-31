"""Unit tests for WiiM Data - testing coordinator helper functions."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.wiim.const import DOMAIN
from custom_components.wiim.data import (
    get_all_coordinators,
    get_coordinator_from_entry,
)


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
    coordinator.player = MagicMock()
    coordinator.player.host = "192.168.1.100"
    coordinator.player.volume_level = 0.5
    return coordinator


class TestGetCoordinatorFromEntry:
    """Test get_coordinator_from_entry helper function."""

    def test_get_coordinator_from_entry(self, hass: HomeAssistant, mock_config_entry, mock_coordinator):
        """Test getting coordinator from config entry."""
        # Register coordinator in hass.data
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }

        # Get coordinator
        retrieved_coordinator = get_coordinator_from_entry(hass, mock_config_entry)

        assert retrieved_coordinator == mock_coordinator

    def test_get_coordinator_from_entry_not_found(self, hass: HomeAssistant, mock_config_entry):
        """Test getting coordinator when not found."""
        # Initialize hass.data structure but don't add coordinator
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][mock_config_entry.entry_id] = {}  # Empty dict, no coordinator key

        # Should raise RuntimeError when coordinator not found
        with pytest.raises(RuntimeError, match="Coordinator not found"):
            get_coordinator_from_entry(hass, mock_config_entry)


class TestDataHelperFunctions:
    """Test data helper functions."""

    def test_get_all_coordinators(self, hass: HomeAssistant, mock_config_entry, mock_coordinator):
        """Test get_all_coordinators helper function."""
        # Register coordinator
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }

        # Mock config entries
        with patch.object(hass.config_entries, "async_entries", return_value=[mock_config_entry]):
            coordinators = get_all_coordinators(hass)

            assert len(coordinators) == 1
            assert coordinators[0] == mock_coordinator

    def test_get_all_coordinators_handles_missing_entry(self, hass: HomeAssistant, mock_config_entry):
        """Test get_all_coordinators handles missing entry gracefully."""
        # Entry exists but not in hass.data
        hass.data.setdefault(DOMAIN, {})

        with patch.object(hass.config_entries, "async_entries", return_value=[mock_config_entry]):
            # Should handle KeyError gracefully
            coordinators = get_all_coordinators(hass)
            # Should return empty list or handle error
            assert isinstance(coordinators, list)
