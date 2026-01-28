"""Unit tests for WiiM Data - testing coordinator helper functions."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.wiim.const import DOMAIN
from custom_components.wiim.data import (
    find_coordinator_by_ip,
    find_coordinator_by_uuid,
    get_all_coordinators,
    get_all_players,
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

    def test_find_coordinator_by_uuid(self, hass: HomeAssistant, mock_config_entry, mock_coordinator):
        """Test find_coordinator_by_uuid helper function."""
        # Register coordinator
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }

        # Mock config entry lookup
        with patch.object(hass.config_entries, "async_entry_for_domain_unique_id", return_value=mock_config_entry):
            found_coordinator = find_coordinator_by_uuid(hass, "test-uuid")

            assert found_coordinator == mock_coordinator

    def test_find_coordinator_by_uuid_returns_none_when_empty(self, hass: HomeAssistant):
        """Test find_coordinator_by_uuid returns None for empty UUID."""
        assert find_coordinator_by_uuid(hass, "") is None
        assert find_coordinator_by_uuid(hass, None) is None

    def test_find_coordinator_by_uuid_returns_none_when_not_found(self, hass: HomeAssistant):
        """Test find_coordinator_by_uuid returns None when not found."""
        with patch.object(hass.config_entries, "async_entry_for_domain_unique_id", return_value=None):
            assert find_coordinator_by_uuid(hass, "unknown-uuid") is None

    def test_find_coordinator_by_ip(self, hass: HomeAssistant, mock_config_entry, mock_coordinator):
        """Test find_coordinator_by_ip helper function."""
        # Register coordinator
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }

        # Mock config entries
        with patch.object(hass.config_entries, "async_entries", return_value=[mock_config_entry]):
            found_coordinator = find_coordinator_by_ip(hass, "192.168.1.100")

            assert found_coordinator == mock_coordinator

    def test_find_coordinator_by_ip_returns_none_when_empty(self, hass: HomeAssistant):
        """Test find_coordinator_by_ip returns None for empty IP."""
        assert find_coordinator_by_ip(hass, "") is None
        assert find_coordinator_by_ip(hass, None) is None

    def test_find_coordinator_by_ip_returns_none_when_not_found(self, hass: HomeAssistant, mock_config_entry):
        """Test find_coordinator_by_ip returns None when IP not found."""
        mock_config_entry.data = {"host": "192.168.1.200"}  # Different IP

        with patch.object(hass.config_entries, "async_entries", return_value=[mock_config_entry]):
            assert find_coordinator_by_ip(hass, "192.168.1.100") is None

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

    def test_get_all_players(self, hass: HomeAssistant, mock_config_entry, mock_coordinator):
        """Test get_all_players returns all Player objects."""
        # Register coordinator
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }

        # Mock config entries
        with patch.object(hass.config_entries, "async_entries", return_value=[mock_config_entry]):
            players = get_all_players(hass)

            assert len(players) == 1
            assert players[0] == mock_coordinator.player

    def test_get_all_players_multiple_coordinators(self, hass: HomeAssistant):
        """Test get_all_players returns players from multiple coordinators."""
        # Create two mock coordinators with different players
        mock_coordinator1 = MagicMock()
        mock_coordinator1.player = MagicMock()
        mock_coordinator1.player.host = "192.168.1.100"

        mock_coordinator2 = MagicMock()
        mock_coordinator2.player = MagicMock()
        mock_coordinator2.player.host = "192.168.1.101"

        mock_entry1 = MagicMock()
        mock_entry1.entry_id = "entry1"
        mock_entry1.data = {"host": "192.168.1.100"}

        mock_entry2 = MagicMock()
        mock_entry2.entry_id = "entry2"
        mock_entry2.data = {"host": "192.168.1.101"}

        # Register both coordinators
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN]["entry1"] = {"coordinator": mock_coordinator1}
        hass.data[DOMAIN]["entry2"] = {"coordinator": mock_coordinator2}

        with patch.object(hass.config_entries, "async_entries", return_value=[mock_entry1, mock_entry2]):
            players = get_all_players(hass)

            assert len(players) == 2
            assert mock_coordinator1.player in players
            assert mock_coordinator2.player in players

    def test_get_all_players_skips_none_player(self, hass: HomeAssistant, mock_config_entry):
        """Test get_all_players skips coordinators with None player."""
        mock_coordinator = MagicMock()
        mock_coordinator.player = None  # Player not yet initialized

        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
            "coordinator": mock_coordinator,
            "entry": mock_config_entry,
        }

        with patch.object(hass.config_entries, "async_entries", return_value=[mock_config_entry]):
            players = get_all_players(hass)

            assert len(players) == 0

    def test_get_all_players_empty_domain(self, hass: HomeAssistant):
        """Test get_all_players returns empty list when no coordinators."""
        hass.data.setdefault(DOMAIN, {})

        with patch.object(hass.config_entries, "async_entries", return_value=[]):
            players = get_all_players(hass)

            assert players == []
