"""Integration tests for WiiM group management."""

import pytest
from unittest.mock import AsyncMock, MagicMock

# Import fixtures from our WiiM conftest
pytest_plugins = ["tests.conftest_wiim"]


class TestGroupManagementWorkflow:
    """Test complete group management workflows."""

    @pytest.fixture
    def group_setup(self, wiim_data, wiim_speaker, wiim_speaker_slave):
        """Set up speakers for group testing."""
        # Add both speakers to the data registry
        wiim_data.speakers[wiim_speaker.uuid] = wiim_speaker
        wiim_data.speakers[wiim_speaker_slave.uuid] = wiim_speaker_slave

        # Set up entity mappings
        wiim_data.entity_id_mappings["media_player.master"] = wiim_speaker
        wiim_data.entity_id_mappings["media_player.slave"] = wiim_speaker_slave

        return {"master": wiim_speaker, "slave": wiim_speaker_slave, "data": wiim_data}

    @pytest.mark.asyncio
    async def test_complete_group_join_workflow(self, group_setup, mock_wiim_dispatcher):
        """Test the complete workflow of joining speakers into a group."""
        master = group_setup["master"]
        slave = group_setup["slave"]

        # Mock API responses
        slave.coordinator.client.send_command = AsyncMock()
        master.coordinator.async_request_refresh = AsyncMock()
        slave.coordinator.async_request_refresh = AsyncMock()

        # Execute group join
        await master.async_join_group([slave])

        # Verify API call was made to slave
        slave.coordinator.client.send_command.assert_called_once_with(
            f"ConnectMasterAp:JoinGroupMaster:{master.ip}:wifi0.0.0.0"
        )

        # Verify state changes
        assert master.role == "master"
        assert slave.role == "slave"
        assert slave.coordinator_speaker is master

        # Verify group membership
        assert len(master.group_members) == 2
        assert master.group_members[0] is master  # Master comes first
        assert slave in master.group_members

        # Verify coordinators were refreshed
        master.coordinator.async_request_refresh.assert_called()
        slave.coordinator.async_request_refresh.assert_called()

        # Verify entity state updates were dispatched
        assert mock_wiim_dispatcher.call_count >= 2  # At least master and slave

    @pytest.mark.asyncio
    async def test_group_leave_as_slave(self, group_setup, mock_wiim_dispatcher):
        """Test slave leaving a group."""
        master = group_setup["master"]
        slave = group_setup["slave"]

        # Set up existing group
        master.role = "master"
        slave.role = "slave"
        slave.coordinator_speaker = master
        master.group_members = [master, slave]
        slave.group_members = [master, slave]

        # Mock API calls
        master.coordinator.client.send_command = AsyncMock()

        # Execute leave
        await slave.async_leave_group()

        # Verify SlaveKickout command was sent to master
        master.coordinator.client.send_command.assert_called_once_with(f"multiroom:SlaveKickout:{slave.ip}")

        # Verify state changes
        assert slave.role == "solo"
        assert slave.coordinator_speaker is None
        assert slave not in master.group_members
        assert len(slave.group_members) == 0

    @pytest.mark.asyncio
    async def test_group_disband_as_master(self, group_setup, mock_wiim_dispatcher):
        """Test master disbanding the entire group."""
        master = group_setup["master"]
        slave = group_setup["slave"]

        # Set up existing group
        master.role = "master"
        slave.role = "slave"
        master.group_members = [master, slave]
        slave.group_members = [master, slave]

        # Mock API calls
        master.coordinator.client.send_command = AsyncMock()

        # Execute disband
        await master.async_leave_group()

        # Verify Ungroup command was sent
        master.coordinator.client.send_command.assert_called_once_with("multiroom:Ungroup")

        # Verify all speakers returned to solo
        assert master.role == "solo"
        assert slave.role == "solo"
        assert len(master.group_members) == 0
        assert len(slave.group_members) == 0

    @pytest.mark.asyncio
    async def test_entity_id_resolution(self, group_setup):
        """Test entity ID to speaker resolution."""
        master = group_setup["master"]
        data = group_setup["data"]

        # Test successful resolution
        entity_ids = ["media_player.master", "media_player.slave"]
        speakers = master.resolve_entity_ids_to_speakers(entity_ids)

        assert len(speakers) == 2
        assert data.speakers["test-speaker-uuid"] in speakers
        assert data.speakers["test-slave-uuid"] in speakers

        # Test partial resolution (some IDs not found)
        entity_ids = ["media_player.master", "media_player.nonexistent"]
        speakers = master.resolve_entity_ids_to_speakers(entity_ids)

        assert len(speakers) == 1
        assert data.speakers["test-speaker-uuid"] in speakers

    def test_group_member_entity_ids_ordering(self, group_setup):
        """Test that group member entity IDs are returned with master first."""
        master = group_setup["master"]
        slave = group_setup["slave"]
        data = group_setup["data"]

        # Set up group
        master.group_members = [master, slave]

        entity_ids = master.get_group_member_entity_ids()

        assert len(entity_ids) == 2
        assert entity_ids[0] == "media_player.master"  # Master first
        assert entity_ids[1] == "media_player.slave"


class TestGroupErrorHandling:
    """Test error handling in group operations."""

    @pytest.fixture
    def group_setup(self, wiim_data, wiim_speaker, wiim_speaker_slave):
        """Set up speakers for error testing."""
        wiim_data.speakers[wiim_speaker.uuid] = wiim_speaker
        wiim_data.speakers[wiim_speaker_slave.uuid] = wiim_speaker_slave
        wiim_data.entity_id_mappings["media_player.master"] = wiim_speaker
        wiim_data.entity_id_mappings["media_player.slave"] = wiim_speaker_slave

        return {"master": wiim_speaker, "slave": wiim_speaker_slave}

    @pytest.mark.asyncio
    async def test_group_join_api_failure(self, group_setup):
        """Test group join when API call fails."""
        master = group_setup["master"]
        slave = group_setup["slave"]

        # Mock API failure
        from custom_components.wiim.api import WiiMError

        slave.coordinator.client.send_command = AsyncMock(side_effect=WiiMError("Connection failed"))

        # Should raise the API error
        with pytest.raises(WiiMError):
            await master.async_join_group([slave])

        # Verify roles weren't changed on failure
        assert master.role == "solo"
        assert slave.role == "solo"

    @pytest.mark.asyncio
    async def test_group_leave_api_failure(self, group_setup):
        """Test group leave when API call fails."""
        master = group_setup["master"]
        slave = group_setup["slave"]

        # Set up existing group
        master.role = "master"
        slave.role = "slave"
        slave.coordinator_speaker = master

        # Mock API failure
        from custom_components.wiim.api import WiiMError

        master.coordinator.client.send_command = AsyncMock(side_effect=WiiMError("Connection failed"))

        # Should raise the API error
        with pytest.raises(WiiMError):
            await slave.async_leave_group()

        # State should remain unchanged on failure
        assert slave.role == "slave"
        assert slave.coordinator_speaker is master

    def test_resolve_nonexistent_entities(self, group_setup):
        """Test resolving entity IDs that don't exist."""
        master = group_setup["master"]

        # All nonexistent entities
        entity_ids = ["media_player.ghost1", "media_player.ghost2"]
        speakers = master.resolve_entity_ids_to_speakers(entity_ids)

        assert len(speakers) == 0

    def test_get_group_member_entity_ids_no_mappings(self, group_setup):
        """Test getting entity IDs when no entity mappings exist."""
        master = group_setup["master"]
        slave = group_setup["slave"]

        # Set up group but clear entity mappings
        master.group_members = [master, slave]
        wiim_data = master.hass.data["wiim"]["data"]
        wiim_data.entity_id_mappings.clear()

        entity_ids = master.get_group_member_entity_ids()
        assert len(entity_ids) == 0


class TestGroupStateConsistency:
    """Test group state consistency across operations."""

    @pytest.fixture
    def three_speaker_setup(self, wiim_data, wiim_speaker):
        """Set up three speakers for complex group testing."""
        from custom_components.wiim.data import Speaker

        # Create second slave
        slave2_coordinator = MagicMock()
        slave2_coordinator.client = AsyncMock()
        slave2_coordinator.client.host = "192.168.1.102"
        slave2_coordinator.data = {"status": {"uuid": "slave2-uuid"}, "multiroom": {}}
        slave2_coordinator.async_request_refresh = AsyncMock()

        slave2 = Speaker(wiim_speaker.hass, "slave2-uuid", slave2_coordinator)
        slave2.ip = "192.168.1.102"
        slave2.name = "Slave 2"
        slave2.role = "solo"

        # Add all speakers to registry
        wiim_data.speakers[wiim_speaker.uuid] = wiim_speaker
        wiim_data.speakers["test-slave-uuid"] = wiim_speaker  # Reuse for simplicity
        wiim_data.speakers["slave2-uuid"] = slave2

        return {
            "master": wiim_speaker,
            "slave1": wiim_speaker,  # Reusing fixture
            "slave2": slave2,
        }

    @pytest.mark.asyncio
    async def test_complex_group_formation(self, three_speaker_setup):
        """Test forming a group with multiple slaves."""
        master = three_speaker_setup["master"]
        slave1 = three_speaker_setup["slave1"]
        slave2 = three_speaker_setup["slave2"]

        # Mock API calls
        slave1.coordinator.client.send_command = AsyncMock()
        slave2.coordinator.client.send_command = AsyncMock()

        # Join both slaves
        await master.async_join_group([slave1, slave2])

        # Verify all roles are correct
        assert master.role == "master"
        assert slave1.role == "slave"
        assert slave2.role == "slave"

        # Verify group membership is consistent
        expected_members = [master, slave1, slave2]
        assert len(master.group_members) == 3
        assert all(speaker in master.group_members for speaker in expected_members)

        # Verify slaves know about the group
        assert slave1.coordinator_speaker is master
        assert slave2.coordinator_speaker is master

    @pytest.mark.asyncio
    async def test_partial_group_leave(self, three_speaker_setup):
        """Test one slave leaving a multi-member group."""
        master = three_speaker_setup["master"]
        slave1 = three_speaker_setup["slave1"]
        slave2 = three_speaker_setup["slave2"]

        # Set up existing 3-member group
        master.role = "master"
        slave1.role = "slave"
        slave2.role = "slave"
        master.group_members = [master, slave1, slave2]
        slave1.coordinator_speaker = master
        slave2.coordinator_speaker = master

        # Mock API calls
        master.coordinator.client.send_command = AsyncMock()

        # One slave leaves
        await slave1.async_leave_group()

        # Verify group state
        assert master.role == "master"  # Still master
        assert slave1.role == "solo"  # Left group
        assert slave2.role == "slave"  # Still in group

        # Verify membership updated
        assert slave1 not in master.group_members
        assert slave2 in master.group_members
        assert len(master.group_members) == 2  # Master + slave2
