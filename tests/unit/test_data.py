"""Unit tests for WiiM Data - testing Speaker class functionality."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.wiim.const import DOMAIN
from custom_components.wiim.data import Speaker, get_speaker_from_config_entry


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


class TestSpeaker:
    """Test Speaker class functionality."""

    def test_speaker_initialization(self, hass: HomeAssistant, mock_coordinator, mock_config_entry):
        """Test Speaker initialization."""
        speaker = Speaker(hass, mock_coordinator, mock_config_entry)

        assert speaker.coordinator == mock_coordinator
        assert speaker.config_entry == mock_config_entry
        assert speaker.hass == hass

    def test_speaker_uuid(self, hass: HomeAssistant, mock_coordinator, mock_config_entry):
        """Test Speaker uuid property."""
        mock_config_entry.unique_id = "test-uuid-123"
        speaker = Speaker(hass, mock_coordinator, mock_config_entry)

        assert speaker.uuid == "test-uuid-123"

    def test_speaker_name(self, hass: HomeAssistant, mock_coordinator, mock_config_entry):
        """Test Speaker name property."""
        # Set up device_info with name
        device_info = MagicMock()
        device_info.name = "Test WiiM"
        mock_coordinator.data["player"].device_info = device_info
        speaker = Speaker(hass, mock_coordinator, mock_config_entry)

        assert speaker.name == "Test WiiM"

    def test_speaker_available(self, hass: HomeAssistant, mock_coordinator, mock_config_entry):
        """Test Speaker available property."""
        mock_coordinator.last_update_success = True
        speaker = Speaker(hass, mock_coordinator, mock_config_entry)

        assert speaker.available is True

        mock_coordinator.last_update_success = False
        assert speaker.available is False

    def test_speaker_ip_address(self, hass: HomeAssistant, mock_coordinator, mock_config_entry):
        """Test Speaker ip_address property."""
        mock_coordinator.player.host = "192.168.1.100"
        speaker = Speaker(hass, mock_coordinator, mock_config_entry)

        assert speaker.ip_address == "192.168.1.100"

    def test_speaker_device_info(self, hass: HomeAssistant, mock_coordinator, mock_config_entry):
        """Test Speaker device_info property."""
        # Set up device_info in player
        device_info = MagicMock()
        device_info.name = "Test WiiM"
        device_info.model = "WiiM Pro"
        mock_coordinator.data["player"].device_info = device_info

        speaker = Speaker(hass, mock_coordinator, mock_config_entry)
        # device_info is set during async_setup, but we can check it's accessible
        assert speaker.device_model == device_info


class TestGetSpeakerFromConfigEntry:
    """Test get_speaker_from_config_entry helper function."""

    def test_get_speaker_from_config_entry(self, hass: HomeAssistant, mock_config_entry, mock_coordinator):
        """Test getting speaker from config entry."""
        # Register speaker in hass.data
        speaker = Speaker(hass, mock_coordinator, mock_config_entry)
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {"speaker": speaker}

        # Get speaker
        retrieved_speaker = get_speaker_from_config_entry(hass, mock_config_entry)

        assert retrieved_speaker == speaker

    def test_get_speaker_from_config_entry_not_found(self, hass: HomeAssistant, mock_config_entry):
        """Test getting speaker when not found."""
        # Initialize hass.data structure but don't add speaker
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][mock_config_entry.entry_id] = {}  # Empty dict, no speaker key

        # Should raise RuntimeError when speaker not found
        with pytest.raises(RuntimeError, match="Speaker not found"):
            get_speaker_from_config_entry(hass, mock_config_entry)


class TestDataHelperFunctions:
    """Test data helper functions."""

    def test_find_speaker_by_uuid(self, hass: HomeAssistant, mock_config_entry, mock_coordinator):
        """Test find_speaker_by_uuid helper function."""
        from custom_components.wiim.data import find_speaker_by_uuid

        # Register speaker
        speaker = Speaker(hass, mock_coordinator, mock_config_entry)
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {"speaker": speaker}

        # Mock config entry lookup
        with patch.object(hass.config_entries, "async_entry_for_domain_unique_id", return_value=mock_config_entry):
            found_speaker = find_speaker_by_uuid(hass, "test-uuid")

            assert found_speaker == speaker

    def test_find_speaker_by_uuid_returns_none_when_empty(self, hass: HomeAssistant):
        """Test find_speaker_by_uuid returns None for empty UUID."""
        from custom_components.wiim.data import find_speaker_by_uuid

        assert find_speaker_by_uuid(hass, "") is None
        assert find_speaker_by_uuid(hass, None) is None

    def test_find_speaker_by_uuid_returns_none_when_not_found(self, hass: HomeAssistant):
        """Test find_speaker_by_uuid returns None when not found."""
        from custom_components.wiim.data import find_speaker_by_uuid

        with patch.object(hass.config_entries, "async_entry_for_domain_unique_id", return_value=None):
            assert find_speaker_by_uuid(hass, "unknown-uuid") is None

    def test_find_speaker_by_ip(self, hass: HomeAssistant, mock_config_entry, mock_coordinator):
        """Test find_speaker_by_ip helper function."""
        from custom_components.wiim.data import find_speaker_by_ip

        # Register speaker
        speaker = Speaker(hass, mock_coordinator, mock_config_entry)
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {"speaker": speaker}

        # Mock config entries
        with patch.object(hass.config_entries, "async_entries", return_value=[mock_config_entry]):
            found_speaker = find_speaker_by_ip(hass, "192.168.1.100")

            assert found_speaker == speaker

    def test_find_speaker_by_ip_returns_none_when_empty(self, hass: HomeAssistant):
        """Test find_speaker_by_ip returns None for empty IP."""
        from custom_components.wiim.data import find_speaker_by_ip

        assert find_speaker_by_ip(hass, "") is None
        assert find_speaker_by_ip(hass, None) is None

    def test_find_speaker_by_ip_returns_none_when_not_found(self, hass: HomeAssistant, mock_config_entry):
        """Test find_speaker_by_ip returns None when IP not found."""
        from custom_components.wiim.data import find_speaker_by_ip

        mock_config_entry.data = {"host": "192.168.1.200"}  # Different IP

        with patch.object(hass.config_entries, "async_entries", return_value=[mock_config_entry]):
            assert find_speaker_by_ip(hass, "192.168.1.100") is None

    def test_get_all_speakers(self, hass: HomeAssistant, mock_config_entry, mock_coordinator):
        """Test get_all_speakers helper function."""
        from custom_components.wiim.data import get_all_speakers

        # Register speaker
        speaker = Speaker(hass, mock_coordinator, mock_config_entry)
        hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {"speaker": speaker}

        # Mock config entries
        with patch.object(hass.config_entries, "async_entries", return_value=[mock_config_entry]):
            speakers = get_all_speakers(hass)

            assert len(speakers) == 1
            assert speakers[0] == speaker

    def test_get_all_speakers_handles_missing_entry(self, hass: HomeAssistant, mock_config_entry):
        """Test get_all_speakers handles missing entry gracefully."""
        from custom_components.wiim.data import get_all_speakers

        # Entry exists but not in hass.data
        hass.data.setdefault(DOMAIN, {})

        with patch.object(hass.config_entries, "async_entries", return_value=[mock_config_entry]):
            # Should handle KeyError gracefully
            speakers = get_all_speakers(hass)
            # Should return empty list or handle error
            assert isinstance(speakers, list)
