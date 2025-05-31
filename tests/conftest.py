"""Global fixtures for WiiM integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .const import MOCK_DEVICE_DATA, MOCK_STATUS_RESPONSE

pytest_plugins = "pytest_homeassistant_custom_component"


# This fixture enables custom integrations in the test environment
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


# This fixture is used to prevent HomeAssistant from attempting to create and dismiss persistent
# notifications. These calls would fail without this fixture since the persistent_notification
# integration is never loaded during a test.
@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with (
        patch("homeassistant.components.persistent_notification.async_create"),
        patch("homeassistant.components.persistent_notification.async_dismiss"),
    ):
        yield


@pytest.fixture(name="mock_wiim_client")
def mock_wiim_client_fixture():
    """Mock WiiM API client."""
    client = MagicMock()
    client.get_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
    client.get_device_info = AsyncMock(return_value=MOCK_DEVICE_DATA)
    client.get_player_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
    client.get_multiroom_info = AsyncMock(return_value={})
    client.get_meta_info = AsyncMock(return_value={})
    client.get_eq_status = AsyncMock(return_value=False)
    client.get_eq = AsyncMock(return_value={})
    client.play = AsyncMock(return_value=True)
    client.pause = AsyncMock(return_value=True)
    client.stop = AsyncMock(return_value=True)
    client.set_volume = AsyncMock(return_value=True)
    client.mute = AsyncMock(return_value=True)
    client.unmute = AsyncMock(return_value=True)
    client.next_track = AsyncMock(return_value=True)
    client.previous_track = AsyncMock(return_value=True)
    client.seek = AsyncMock(return_value=True)
    client.select_preset = AsyncMock(return_value=True)
    client.join_group = AsyncMock(return_value=True)
    client.leave_group = AsyncMock(return_value=True)
    return client


@pytest.fixture(name="mock_coordinator")
def mock_coordinator_fixture():
    """Mock WiiM coordinator."""
    coordinator = MagicMock()
    # Create the proper data structure that matches what the real coordinator returns
    mock_status = MOCK_STATUS_RESPONSE.copy()
    mock_status["volume_level"] = 0.5  # Add parsed volume_level
    mock_status["volume"] = 50  # Add volume as integer

    coordinator.data = {
        "status": mock_status,
        "multiroom": {"slaves": 0},
        "role": "solo",
        "ha_group": {
            "is_leader": False,
            "members": [],
        },
    }
    coordinator.async_request_refresh = AsyncMock()
    coordinator.last_update_success = True
    # Add the client property
    coordinator.client = MagicMock()
    coordinator.client.host = "192.168.1.100"
    coordinator.client._host = "192.168.1.100"
    coordinator.ha_group_members = set()
    return coordinator


# This fixture, when used, will result in calls to get data to return mock data
@pytest.fixture(name="bypass_get_data")
def bypass_get_data_fixture():
    """Skip calls to get data from API."""
    # Create proper mock data with volume_level included and merge device data
    mock_status = MOCK_STATUS_RESPONSE.copy()
    mock_status["volume_level"] = 0.5  # Add parsed volume_level
    mock_status["volume"] = 50  # Add volume as integer

    # Merge device data into status so device info is available
    mock_status.update(MOCK_DEVICE_DATA)

    mock_coordinator_data = {
        "status": mock_status,
        "multiroom": {"slaves": 0},
        "role": "solo",
        "ha_group": {
            "is_leader": False,
            "members": [],
        },
    }

    with (
        patch(
            "custom_components.wiim.api.WiiMClient.get_status",
            return_value=MOCK_STATUS_RESPONSE,
        ),
        patch(
            "custom_components.wiim.api.WiiMClient.get_device_info",
            return_value=MOCK_DEVICE_DATA,
        ),
        patch(
            "custom_components.wiim.api.WiiMClient.get_player_status",
            return_value=MOCK_STATUS_RESPONSE,
        ),
        patch(
            "custom_components.wiim.api.WiiMClient.get_multiroom_info",
            return_value={"slaves": 0},
        ),
        patch(
            "custom_components.wiim.api.WiiMClient.reboot",
            return_value=True,
        ),
        patch(
            "custom_components.wiim.api.WiiMClient.sync_time",
            return_value=True,
        ),
        patch(
            "custom_components.wiim.coordinator.WiiMCoordinator._async_update_data",
            return_value=mock_coordinator_data,
        ),
    ):
        yield


# In this fixture, we are forcing calls to get data to raise an Exception. This is useful
# for exception handling.
@pytest.fixture(name="error_on_get_data")
def error_get_data_fixture():
    """Simulate error when retrieving data from API."""
    with (
        patch(
            "custom_components.wiim.api.WiiMClient.get_status",
            side_effect=Exception,
        ),
        patch(
            "custom_components.wiim.api.WiiMClient.get_device_info",
            side_effect=Exception,
        ),
    ):
        yield
