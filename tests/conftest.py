"""Global fixtures for WiiM integration."""
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from .const import MOCK_DEVICE_DATA
from .const import MOCK_STATUS_RESPONSE

pytest_plugins = "pytest_homeassistant_custom_component"


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
    coordinator.data = {
        "status": MOCK_STATUS_RESPONSE,
        "device_info": MOCK_DEVICE_DATA,
    }
    coordinator.async_request_refresh = AsyncMock()
    coordinator.last_update_success = True
    return coordinator


# This fixture, when used, will result in calls to get data to return mock data
@pytest.fixture(name="bypass_get_data")
def bypass_get_data_fixture():
    """Skip calls to get data from API."""
    with (
        patch(
            "custom_components.wiim.api.WiiMClient.get_status",
            return_value=MOCK_STATUS_RESPONSE,
        ),
        patch(
            "custom_components.wiim.api.WiiMClient.get_device_info",
            return_value=MOCK_DEVICE_DATA,
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
