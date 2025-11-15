"""Core data/Speaker tests for WiiM - testing Speaker class and helpers."""

from unittest.mock import MagicMock

import pytest
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wiim.const import DOMAIN
from custom_components.wiim.data import (
    Speaker,
    find_speaker_by_ip,
    find_speaker_by_uuid,
    get_all_speakers,
    get_speaker_from_config_entry,
)
from tests.const import MOCK_DEVICE_DATA


class TestSpeaker:
    """Test Speaker class - minimal wrapper around coordinator."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.client = MagicMock()
        coordinator.player.client.host = "192.168.1.100"
        coordinator.player.device_info = MagicMock()
        coordinator.player.device_info.name = "Test WiiM"
        coordinator.player.device_info.model = "WiiM Mini"
        coordinator.player.device_info.firmware = "1.0.0"
        coordinator.player.role = "solo"
        coordinator.player.group = None
        coordinator.last_update_success = True
        coordinator.data = {
            "player": coordinator.player,
        }
        return coordinator

    @pytest.fixture
    def mock_entry(self):
        """Create a mock config entry."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"host": "192.168.1.100"},
            unique_id=MOCK_DEVICE_DATA["uuid"],
            title="Test WiiM",
        )
        return entry

    @pytest.fixture
    def speaker(self, hass, mock_coordinator, mock_entry):
        """Create a Speaker instance."""
        return Speaker(hass, mock_coordinator, mock_entry)

    def test_speaker_initialization(self, speaker, mock_entry):
        """Test speaker is initialized correctly."""
        assert speaker.config_entry is mock_entry
        assert speaker.uuid == MOCK_DEVICE_DATA["uuid"]

    def test_speaker_name_property(self, speaker, mock_coordinator):
        """Test speaker name property."""
        name = speaker.name
        assert name == "Test WiiM"

    def test_speaker_name_fallback(self, speaker, mock_coordinator, mock_entry):
        """Test speaker name falls back to entry title."""
        mock_coordinator.data = None
        name = speaker.name
        assert name == "Test WiiM"  # Falls back to entry title

    def test_speaker_model_property(self, speaker, mock_coordinator):
        """Test speaker model property."""
        model = speaker.model
        assert model == "WiiM Mini"

    def test_speaker_model_fallback(self, speaker, mock_coordinator):
        """Test speaker model falls back to default."""
        mock_coordinator.data = None
        model = speaker.model
        assert model == "WiiM Speaker"

    def test_speaker_firmware_property(self, speaker, mock_coordinator):
        """Test speaker firmware property."""
        firmware = speaker.firmware
        assert firmware == "1.0.0"

    def test_speaker_firmware_none(self, speaker, mock_coordinator):
        """Test speaker firmware returns None when not available."""
        mock_coordinator.data = None
        firmware = speaker.firmware
        assert firmware is None

    def test_speaker_ip_address_property(self, speaker, mock_coordinator):
        """Test speaker IP address property."""
        ip = speaker.ip_address
        assert ip == "192.168.1.100"

    def test_speaker_role_property(self, speaker, mock_coordinator):
        """Test speaker role property."""
        role = speaker.role
        assert role == "solo"

    def test_speaker_role_slave(self, speaker, mock_coordinator):
        """Test speaker role when in group."""
        mock_coordinator.player.group = MagicMock()
        mock_coordinator.player.role = "slave"
        role = speaker.role
        assert role == "slave"

    def test_speaker_available_property(self, speaker, mock_coordinator):
        """Test speaker available property."""
        mock_coordinator.last_update_success = True
        assert speaker.available is True

        mock_coordinator.last_update_success = False
        assert speaker.available is False

    @pytest.mark.asyncio
    async def test_speaker_async_setup(self, speaker, hass, mock_entry):
        """Test speaker async_setup registers device."""
        # Add entry to hass first
        mock_entry.add_to_hass(hass)

        await speaker.async_setup(mock_entry)

        # Verify device was registered
        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, mock_entry.entry_id)
        assert len(devices) >= 1

        device = devices[0]
        assert device.manufacturer == "WiiM"
        assert device.identifiers == {(DOMAIN, MOCK_DEVICE_DATA["uuid"])}


class TestSpeakerHelpers:
    """Test helper functions for finding speakers."""

    @pytest.fixture
    def setup_speakers(self, hass):
        """Set up test speakers in hass.data."""
        entry1 = MockConfigEntry(
            domain=DOMAIN,
            data={"host": "192.168.1.100"},
            unique_id="uuid-1",
            entry_id="entry-1",
        )
        entry1.add_to_hass(hass)

        entry2 = MockConfigEntry(
            domain=DOMAIN,
            data={"host": "192.168.1.101"},
            unique_id="uuid-2",
            entry_id="entry-2",
        )
        entry2.add_to_hass(hass)

        # Create mock speakers
        speaker1 = MagicMock()
        speaker1.uuid = "uuid-1"
        speaker1.ip_address = "192.168.1.100"

        speaker2 = MagicMock()
        speaker2.uuid = "uuid-2"
        speaker2.ip_address = "192.168.1.101"

        hass.data[DOMAIN] = {
            "entry-1": {"speaker": speaker1},
            "entry-2": {"speaker": speaker2},
        }

        return {"entry1": entry1, "entry2": entry2, "speaker1": speaker1, "speaker2": speaker2}

    def test_get_speaker_from_config_entry(self, hass, setup_speakers):
        """Test get_speaker_from_config_entry."""
        speaker = get_speaker_from_config_entry(hass, setup_speakers["entry1"])
        assert speaker is setup_speakers["speaker1"]

    def test_get_speaker_from_config_entry_not_found(self, hass):
        """Test get_speaker_from_config_entry raises when not found."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"host": "192.168.1.200"},
            unique_id="uuid-unknown",
            entry_id="entry-unknown",
        )
        entry.add_to_hass(hass)

        with pytest.raises(RuntimeError, match="Speaker not found"):
            get_speaker_from_config_entry(hass, entry)

    def test_find_speaker_by_uuid(self, hass, setup_speakers):
        """Test find_speaker_by_uuid."""
        speaker = find_speaker_by_uuid(hass, "uuid-1")
        assert speaker is setup_speakers["speaker1"]

        speaker = find_speaker_by_uuid(hass, "uuid-2")
        assert speaker is setup_speakers["speaker2"]

    def test_find_speaker_by_uuid_not_found(self, hass, setup_speakers):
        """Test find_speaker_by_uuid returns None when not found."""
        speaker = find_speaker_by_uuid(hass, "uuid-unknown")
        assert speaker is None

    def test_find_speaker_by_uuid_empty(self, hass):
        """Test find_speaker_by_uuid returns None for empty UUID."""
        speaker = find_speaker_by_uuid(hass, "")
        assert speaker is None

    def test_find_speaker_by_ip(self, hass, setup_speakers):
        """Test find_speaker_by_ip."""
        speaker = find_speaker_by_ip(hass, "192.168.1.100")
        assert speaker is setup_speakers["speaker1"]

        speaker = find_speaker_by_ip(hass, "192.168.1.101")
        assert speaker is setup_speakers["speaker2"]

    def test_find_speaker_by_ip_not_found(self, hass, setup_speakers):
        """Test find_speaker_by_ip returns None when not found."""
        speaker = find_speaker_by_ip(hass, "192.168.1.200")
        assert speaker is None

    def test_find_speaker_by_ip_empty(self, hass):
        """Test find_speaker_by_ip returns None for empty IP."""
        speaker = find_speaker_by_ip(hass, "")
        assert speaker is None

    def test_get_all_speakers(self, hass, setup_speakers):
        """Test get_all_speakers returns all speakers."""
        speakers = get_all_speakers(hass)
        assert len(speakers) == 2
        assert setup_speakers["speaker1"] in speakers
        assert setup_speakers["speaker2"] in speakers

    def test_get_all_speakers_empty(self, hass):
        """Test get_all_speakers returns empty list when no speakers."""
        hass.data[DOMAIN] = {}
        speakers = get_all_speakers(hass)
        assert speakers == []
