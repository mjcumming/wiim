"""Unit tests for WiiM data layer components."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.components.media_player import MediaPlayerState
from homeassistant.helpers.device_registry import DeviceInfo

# Import fixtures from our WiiM conftest
pytest_plugins = ["tests.conftest_wiim"]


class TestWiimData:
    """Test WiimData registry functionality."""

    def test_wiim_data_creation(self, hass, wiim_data):
        """Test WiimData instance creation."""
        assert wiim_data.hass is hass
        assert len(wiim_data.speakers) == 0
        assert len(wiim_data.entity_id_mappings) == 0

    def test_speaker_registration(self, wiim_data, wiim_speaker):
        """Test speaker registration in WiimData."""
        # Speaker should be registered in fixture
        assert "test-speaker-uuid" in wiim_data.speakers
        assert wiim_data.speakers["test-speaker-uuid"] is wiim_speaker

    def test_get_speaker_by_uuid(self, wiim_data, wiim_speaker):
        """Test UUID-based speaker lookup."""
        result = wiim_data.get_speaker_by_uuid("test-speaker-uuid")
        assert result is wiim_speaker

        # Test non-existent UUID
        result = wiim_data.get_speaker_by_uuid("non-existent-uuid")
        assert result is None

    def test_get_speaker_by_ip(self, wiim_data, wiim_speaker):
        """Test IP-based speaker lookup."""
        result = wiim_data.get_speaker_by_ip("192.168.1.100")
        assert result is wiim_speaker

        # Test non-existent IP
        result = wiim_data.get_speaker_by_ip("192.168.1.999")
        assert result is None

    def test_get_speaker_by_entity_id(self, wiim_data, wiim_speaker):
        """Test entity ID-based speaker lookup."""
        # Register entity mapping
        entity_id = "media_player.test_wiim"
        wiim_data.entity_id_mappings[entity_id] = wiim_speaker

        result = wiim_data.get_speaker_by_entity_id(entity_id)
        assert result is wiim_speaker

        # Test non-existent entity
        result = wiim_data.get_speaker_by_entity_id("media_player.nonexistent")
        assert result is None


class TestSpeaker:
    """Test Speaker class functionality."""

    def test_speaker_creation(self, hass, wiim_coordinator, wiim_speaker):
        """Test Speaker instance creation."""
        assert wiim_speaker.hass is hass
        assert wiim_speaker.uuid == "test-speaker-uuid"
        assert wiim_speaker.coordinator is wiim_coordinator
        assert wiim_speaker.role == "solo"

    def test_speaker_properties(self, wiim_speaker):
        """Test Speaker property access."""
        assert wiim_speaker.name == "Test WiiM"
        assert wiim_speaker.model == "WiiM Mini"
        assert wiim_speaker.ip_address == "192.168.1.100"
        assert wiim_speaker.available is True

    @pytest.mark.asyncio
    async def test_populate_device_info(self, wiim_speaker):
        """Test device info population."""
        # Test that device properties are populated from coordinator data
        await wiim_speaker._populate_device_info()

        assert wiim_speaker.name == "Test WiiM"
        assert wiim_speaker.model == "WiiM Mini"
        assert wiim_speaker.ip_address == "192.168.1.100"
        assert wiim_speaker.mac_address == "aa:bb:cc:dd:ee:ff"  # Normalized format with colons
        assert wiim_speaker.firmware == "1.0.0"
        assert wiim_speaker.role == "solo"

    def test_get_playback_state(self, wiim_speaker):
        """Test playback state calculation."""
        # Test stopped state
        state = wiim_speaker.get_playback_state()
        assert state == MediaPlayerState.IDLE

        # Test playing state
        wiim_speaker.coordinator.data["status"]["play_status"] = "play"
        state = wiim_speaker.get_playback_state()
        assert state == MediaPlayerState.PLAYING

        # Test paused state
        wiim_speaker.coordinator.data["status"]["play_status"] = "pause"
        state = wiim_speaker.get_playback_state()
        assert state == MediaPlayerState.PAUSED

    def test_get_volume_level(self, wiim_speaker):
        """Test volume level calculation."""
        # Test normal volume
        volume = wiim_speaker.get_volume_level()
        assert volume == 0.5  # 50/100

        # Test no volume data
        del wiim_speaker.coordinator.data["status"]["vol"]
        volume = wiim_speaker.get_volume_level()
        assert volume is None

    def test_is_group_coordinator(self, wiim_speaker):
        """Test group coordinator detection."""
        # Solo speaker should be coordinator
        assert wiim_speaker.is_group_coordinator is True

        # Master should be coordinator
        wiim_speaker.role = "master"
        assert wiim_speaker.is_group_coordinator is True

        # Slave should not be coordinator
        wiim_speaker.role = "slave"
        assert wiim_speaker.is_group_coordinator is False

    def test_update_from_coordinator_data(self, wiim_speaker):
        """Test speaker state update from coordinator."""
        update_data = {
            "status": {
                "DeviceName": "Updated WiiM",
                "project": "WiiM Pro Plus",
                "MAC": "112233445566",  # Valid hex MAC that normalizes to 11:22:33:44:55:66
                "firmware": "2.0.0",
            },
            "role": "master",
        }

        wiim_speaker.update_from_coordinator_data(update_data)

        assert wiim_speaker.name == "Updated WiiM"
        assert wiim_speaker.model == "WiiM Pro Plus"
        assert wiim_speaker.mac_address == "11:22:33:44:55:66"  # Normalized format with colons
        assert wiim_speaker.firmware == "2.0.0"
        assert wiim_speaker.role == "master"

    @pytest.mark.asyncio
    async def test_async_write_entity_states(self, wiim_speaker, mock_wiim_dispatcher):
        """Test entity state notification."""
        wiim_speaker.async_write_entity_states()

        mock_wiim_dispatcher.assert_called_once_with(wiim_speaker.hass, f"wiim_state_updated_{wiim_speaker.uuid}")


class TestSpeakerGroupManagement:
    """Test Speaker group management functionality."""

    @pytest.mark.asyncio
    async def test_resolve_entity_ids_to_speakers(self, wiim_speaker, wiim_speaker_slave, wiim_data):
        """Test entity ID resolution to speakers."""
        # Set up entity mappings
        wiim_data.entity_id_mappings["media_player.test_wiim"] = wiim_speaker
        wiim_data.entity_id_mappings["media_player.test_slave"] = wiim_speaker_slave

        entity_ids = ["media_player.test_wiim", "media_player.test_slave"]
        speakers = wiim_speaker.resolve_entity_ids_to_speakers(entity_ids)

        assert len(speakers) == 2
        assert wiim_speaker in speakers
        assert wiim_speaker_slave in speakers

    @pytest.mark.asyncio
    async def test_async_join_group(self, wiim_speaker, wiim_speaker_slave):
        """Test group joining functionality."""
        # Mock API calls for the join operation
        wiim_speaker.coordinator.client.create_group = AsyncMock()
        wiim_speaker_slave.coordinator.client.join_slave = AsyncMock()

        # Test successful group creation
        await wiim_speaker.async_join_group([wiim_speaker_slave])

        # Verify API calls were made
        wiim_speaker.coordinator.client.create_group.assert_called_once()
        wiim_speaker_slave.coordinator.client.join_slave.assert_called_once_with(wiim_speaker.ip_address)

    @pytest.mark.asyncio
    async def test_async_leave_group_as_slave(self, wiim_speaker, wiim_speaker_slave):
        """Test leaving group as a slave."""
        # Set up group relationship
        wiim_speaker.role = "master"
        wiim_speaker_slave.role = "slave"
        wiim_speaker_slave.coordinator_speaker = wiim_speaker
        wiim_speaker.group_members = [wiim_speaker, wiim_speaker_slave]

        # Mock API calls
        wiim_speaker.coordinator.client.kick_slave = AsyncMock()

        await wiim_speaker_slave.async_leave_group()

        # Verify API call to master
        wiim_speaker.coordinator.client.kick_slave.assert_called_once_with(wiim_speaker_slave.ip_address)

    @pytest.mark.asyncio
    async def test_async_leave_group_as_master(self, wiim_speaker, wiim_speaker_slave):
        """Test leaving group as a master (disbands group)."""
        # Set up group relationship
        wiim_speaker.role = "master"
        wiim_speaker_slave.role = "slave"
        wiim_speaker.group_members = [wiim_speaker, wiim_speaker_slave]

        # Mock API calls
        wiim_speaker.coordinator.client.leave_group = AsyncMock()

        await wiim_speaker.async_leave_group()

        # Verify ungroup command
        wiim_speaker.coordinator.client.leave_group.assert_called_once()

    def test_get_group_member_entity_ids(self, wiim_speaker, wiim_speaker_slave, wiim_data):
        """Test getting group member entity IDs."""
        # Set up group and entity mappings
        wiim_speaker.role = "master"  # Must be master to have group members
        wiim_speaker.group_members = [wiim_speaker, wiim_speaker_slave]

        # Set up bidirectional entity mappings
        wiim_data.register_entity("media_player.test_wiim", wiim_speaker)
        wiim_data.register_entity("media_player.test_slave", wiim_speaker_slave)

        entity_ids = wiim_speaker.get_group_member_entity_ids()

        assert len(entity_ids) == 2
        assert "media_player.test_wiim" in entity_ids
        assert "media_player.test_slave" in entity_ids
        assert entity_ids[0] == "media_player.test_wiim"  # Master first


class TestHelperFunctions:
    """Test helper functions in data module."""

    def test_get_wiim_data(self, hass, wiim_data):
        """Test get_wiim_data helper function."""
        from custom_components.wiim.data import get_wiim_data
        from custom_components.wiim.const import DOMAIN

        # Set up hass.data structure that get_wiim_data expects
        hass.data = {DOMAIN: {"data": wiim_data}}

        # Should return existing data
        result = get_wiim_data(hass)
        assert result is wiim_data

    def test_get_or_create_speaker(self, hass, wiim_data, wiim_coordinator):
        """Test get_or_create_speaker helper function."""
        from custom_components.wiim.data import get_or_create_speaker
        from custom_components.wiim.const import DOMAIN
        from homeassistant.config_entries import ConfigEntry

        # Set up hass.data structure that get_wiim_data expects
        hass.data = {DOMAIN: {"data": wiim_data}}

        # Create a mock config entry
        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "new-uuid"
        config_entry.data = {"host": "192.168.1.200"}
        config_entry.options = {}
        config_entry.title = "New Speaker"

        # Create new speaker
        speaker = get_or_create_speaker(hass, wiim_coordinator, config_entry)
        assert speaker.uuid == "new-uuid"
        assert "new-uuid" in wiim_data.speakers

        # Get existing speaker
        same_speaker = get_or_create_speaker(hass, wiim_coordinator, config_entry)
        assert same_speaker is speaker
