"""Test coordinator role detection helpers."""

from unittest.mock import MagicMock

import pytest

from custom_components.wiim.coordinator_role import detect_role_from_status_and_slaves
from custom_components.wiim.models import DeviceInfo, PlayerStatus


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for role detection testing."""
    coordinator = MagicMock()
    coordinator.client = MagicMock()
    coordinator.client.host = "192.168.1.100"
    coordinator.get_current_role = MagicMock(return_value="solo")
    return coordinator


@pytest.fixture
def base_status():
    """Create base PlayerStatus for testing."""
    return PlayerStatus.model_validate({"status": "stop", "vol": 50, "mode": "0"})


@pytest.fixture
def base_device_info():
    """Create base DeviceInfo for testing."""
    return DeviceInfo.model_validate({"uuid": "test-device-uuid", "DeviceName": "Test Device", "group": "0"})


async def test_role_detection_solo(mock_coordinator, base_status, base_device_info):
    """Test solo role detection."""
    multiroom = {"slave_count": 0, "slaves": []}

    result = await detect_role_from_status_and_slaves(mock_coordinator, base_status, multiroom, base_device_info)

    assert result == "solo"
    assert mock_coordinator.client._group_master is None
    assert mock_coordinator.client._group_slaves == []


async def test_role_detection_master_with_slaves(mock_coordinator, base_status, base_device_info):
    """Test master role detection when device has slaves."""
    multiroom = {
        "slave_count": 2,
        "slaves": [{"ip": "192.168.1.101", "name": "Slave 1"}, {"ip": "192.168.1.102", "name": "Slave 2"}],
    }

    result = await detect_role_from_status_and_slaves(mock_coordinator, base_status, multiroom, base_device_info)

    assert result == "master"
    assert mock_coordinator.client._group_master == "192.168.1.100"
    assert mock_coordinator.client._group_slaves == ["192.168.1.101", "192.168.1.102"]


async def test_role_detection_slave_with_master_uuid(mock_coordinator, base_status, base_device_info):
    """Test slave role detection with master UUID."""
    base_device_info.group = "1"
    base_device_info.master_uuid = "master-uuid-123"
    base_device_info.master_ip = "192.168.1.200"

    multiroom = {"slave_count": 0, "slaves": []}

    result = await detect_role_from_status_and_slaves(mock_coordinator, base_status, multiroom, base_device_info)

    assert result == "slave"
    assert mock_coordinator.client._group_master == "192.168.1.200"
    assert mock_coordinator.client._group_slaves == []


async def test_role_detection_slave_with_master_ip_only(mock_coordinator, base_status, base_device_info):
    """Test slave role detection with only master IP."""
    base_device_info.group = "1"
    base_device_info.master_ip = "192.168.1.200"

    multiroom = {"slave_count": 0, "slaves": []}

    result = await detect_role_from_status_and_slaves(mock_coordinator, base_status, multiroom, base_device_info)

    assert result == "slave"
    assert mock_coordinator.client._group_master == "192.168.1.200"


async def test_role_detection_group_without_master_info(mock_coordinator, base_status, base_device_info):
    """Test role detection when in group but missing master info."""
    base_device_info.group = "1"
    # No master_uuid or master_ip

    multiroom = {"slave_count": 0, "slaves": []}

    result = await detect_role_from_status_and_slaves(mock_coordinator, base_status, multiroom, base_device_info)

    assert result == "solo"  # Should fallback to solo
    assert mock_coordinator.client._group_master is None
    assert mock_coordinator.client._group_slaves == []


async def test_role_detection_follower_mode_playing(mock_coordinator, base_status, base_device_info):
    """Test role detection for follower mode (mode=99) while playing."""
    base_status.mode = "99"
    base_status.play_state = "play"

    multiroom = {"slave_count": 0, "slaves": []}

    result = await detect_role_from_status_and_slaves(mock_coordinator, base_status, multiroom, base_device_info)

    assert result == "slave"
    assert mock_coordinator.client._group_master is None
    assert mock_coordinator.client._group_slaves == []


async def test_role_detection_follower_mode_not_playing(mock_coordinator, base_status, base_device_info):
    """Test role detection for follower mode (mode=99) while not playing."""
    base_status.mode = "99"
    base_status.play_state = "stop"

    multiroom = {"slave_count": 0, "slaves": []}

    result = await detect_role_from_status_and_slaves(mock_coordinator, base_status, multiroom, base_device_info)

    assert result == "solo"
    assert mock_coordinator.client._group_master is None
    assert mock_coordinator.client._group_slaves == []


async def test_role_detection_status_group_field(mock_coordinator, base_device_info):
    """Test role detection using group field from status instead of device_info."""
    # Status has group field, device_info doesn't
    base_device_info.group = "0"
    status = PlayerStatus.model_validate({"status": "stop", "vol": 50, "group": "1", "master_uuid": "master-uuid-123"})

    multiroom = {"slave_count": 0, "slaves": []}

    result = await detect_role_from_status_and_slaves(mock_coordinator, status, multiroom, base_device_info)

    assert result == "slave"


async def test_role_detection_priority_device_info_over_status(mock_coordinator, base_device_info):
    """Test that device_info group field takes priority over status."""
    base_device_info.group = "1"
    base_device_info.master_uuid = "device-master-uuid"

    status = PlayerStatus.model_validate(
        {
            "status": "stop",
            "vol": 50,
            "group": "0",  # This should be ignored
            "master_uuid": "status-master-uuid",  # This should be ignored
        }
    )

    multiroom = {"slave_count": 0, "slaves": []}

    result = await detect_role_from_status_and_slaves(mock_coordinator, status, multiroom, base_device_info)

    assert result == "slave"
    # Should use device_info master_uuid, not status
    assert mock_coordinator.client._group_master is None  # No master_ip in device_info


async def test_role_detection_malformed_slaves_list(mock_coordinator, base_status, base_device_info):
    """Test role detection with malformed slaves list."""
    multiroom = {
        "slave_count": 2,
        "slaves": [
            {"ip": "192.168.1.101", "name": "Slave 1"},
            {"name": "Slave 2"},  # Missing IP
            "invalid_entry",  # Not a dict
            {"ip": None, "name": "Slave 3"},  # None IP
        ],
    }

    result = await detect_role_from_status_and_slaves(mock_coordinator, base_status, multiroom, base_device_info)

    assert result == "master"
    # Should only include valid IP addresses
    assert mock_coordinator.client._group_slaves == ["192.168.1.101"]


async def test_role_detection_logging_role_changes(mock_coordinator, base_status, base_device_info):
    """Test that role changes are properly logged."""
    # First call - should log new master role
    mock_coordinator.get_current_role.return_value = "solo"

    multiroom = {"slave_count": 1, "slaves": [{"ip": "192.168.1.101", "name": "Slave"}]}

    result = await detect_role_from_status_and_slaves(mock_coordinator, base_status, multiroom, base_device_info)

    assert result == "master"

    # Second call with same role - should not log again
    mock_coordinator.get_current_role.return_value = "master"

    result = await detect_role_from_status_and_slaves(mock_coordinator, base_status, multiroom, base_device_info)

    assert result == "master"
