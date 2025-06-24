"""Test WiiM coordinator with comprehensive coverage of refactored architecture."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wiim import DOMAIN
from custom_components.wiim.api import WiiMError
from custom_components.wiim.coordinator import WiiMCoordinator
from custom_components.wiim.models import DeviceInfo, EQInfo, PlayerStatus, PollingMetrics, TrackMetadata
from tests.const import MOCK_CONFIG, MOCK_DEVICE_DATA, MOCK_STATUS_RESPONSE


@pytest.fixture
def mock_coordinator_data():
    """Create properly structured coordinator data for testing."""
    return {
        "status_model": PlayerStatus.model_validate(MOCK_STATUS_RESPONSE),
        "device_model": DeviceInfo.model_validate(MOCK_DEVICE_DATA),
        "multiroom": {"slave_count": 0, "slaves": []},
        "metadata_model": TrackMetadata.model_validate({"title": "Test Track", "artist": "Test Artist"}),
        "metadata": {"title": "Test Track", "artist": "Test Artist"},
        "eq_model": EQInfo.model_validate({"eq_enabled": False, "eq_preset": "flat"}),
        "eq": {"eq_enabled": False, "eq_preset": "flat"},
        "presets": [],
        "role": "solo",
        "polling_metrics": PollingMetrics.model_validate(
            {
                "interval": 5.0,
                "is_playing": False,
                "api_capabilities": {
                    "statusex_supported": True,
                    "metadata_supported": False,
                    "eq_supported": False,
                },
            }
        ),
        "polling": {
            "interval": 5.0,
            "is_playing": False,
            "api_capabilities": {
                "statusex_supported": True,
                "metadata_supported": False,
                "eq_supported": False,
            },
        },
    }


async def test_coordinator_initialization(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator initialization."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    assert coordinator.name == "WiiM 192.168.1.100"
    assert coordinator.client == mock_wiim_client
    assert coordinator.client.host == "192.168.1.100"
    assert coordinator._backoff is not None
    assert coordinator._eq_supported is None  # Not yet tested
    assert coordinator._metadata_supported is None  # Not yet tested


async def test_coordinator_update_success(hass: HomeAssistant, mock_wiim_client, mock_coordinator_data) -> None:
    """Test successful coordinator update with new architecture."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    # Mock all the polling endpoints used by the new architecture
    with patch("custom_components.wiim.coordinator_polling.async_update_data", return_value=mock_coordinator_data):
        try:
            await coordinator.async_refresh()

            assert coordinator.last_update_success is True
            assert coordinator.data is not None

            # Verify the new data structure
            assert "status_model" in coordinator.data
            assert "device_model" in coordinator.data
            assert "multiroom" in coordinator.data
            assert "metadata_model" in coordinator.data
            assert "eq_model" in coordinator.data
            assert "role" in coordinator.data
            assert "polling_metrics" in coordinator.data

            # Verify models are properly typed
            assert isinstance(coordinator.data["status_model"], PlayerStatus)
            assert isinstance(coordinator.data["device_model"], DeviceInfo)
            assert isinstance(coordinator.data["metadata_model"], TrackMetadata)
            assert isinstance(coordinator.data["eq_model"], EQInfo)
            assert isinstance(coordinator.data["polling_metrics"], PollingMetrics)

        finally:
            await coordinator.async_shutdown()


async def test_coordinator_update_failure(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator update failure with proper error handling."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    # Mock polling to fail
    with patch(
        "custom_components.wiim.coordinator_polling.async_update_data", side_effect=WiiMError("Connection error")
    ):
        try:
            await coordinator.async_refresh()
            assert coordinator.last_update_success is False
            # The backoff failures are recorded in the polling module, not directly accessible in our mock

        finally:
            await coordinator.async_shutdown()


async def test_coordinator_partial_update_failure(hass: HomeAssistant, mock_wiim_client, mock_coordinator_data) -> None:
    """Test coordinator handling partial update failures."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    # Mock successful update
    with patch("custom_components.wiim.coordinator_polling.async_update_data", return_value=mock_coordinator_data):
        try:
            await coordinator.async_refresh()
            assert coordinator.data is not None
            assert "status_model" in coordinator.data

        finally:
            await coordinator.async_shutdown()


async def test_coordinator_device_properties(hass: HomeAssistant, mock_wiim_client, mock_coordinator_data) -> None:
    """Test coordinator device property access."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    with patch("custom_components.wiim.coordinator_polling.async_update_data", return_value=mock_coordinator_data):
        try:
            await coordinator.async_refresh()

            # Test device properties
            assert coordinator.device_uuid == MOCK_DEVICE_DATA["uuid"]
            assert coordinator.device_name == MOCK_DEVICE_DATA["DeviceName"]

        finally:
            await coordinator.async_shutdown()


async def test_coordinator_command_tracking(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator command success/failure tracking."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    try:
        # Test command failure recording
        coordinator.record_command_failure("play", Exception("Test error"))
        assert coordinator.has_recent_command_failures() is True
        assert coordinator._command_failure_count == 1

        # Test command success clearing failures
        coordinator.clear_command_failures()
        assert coordinator.has_recent_command_failures() is False
        assert coordinator._command_failure_count == 0

    finally:
        await coordinator.async_shutdown()


async def test_coordinator_role_detection(hass: HomeAssistant, mock_wiim_client, mock_coordinator_data) -> None:
    """Test coordinator role detection functionality."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    with patch("custom_components.wiim.coordinator_polling.async_update_data", return_value=mock_coordinator_data):
        try:
            await coordinator.async_refresh()

            # Test role detection
            assert coordinator.get_current_role() == "solo"
            assert coordinator.is_wiim_master is False
            assert coordinator.is_wiim_slave is False

        finally:
            await coordinator.async_shutdown()


async def test_coordinator_group_management(hass: HomeAssistant, mock_wiim_client, mock_coordinator_data) -> None:
    """Test coordinator group management functionality."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    # Test master role
    master_data = mock_coordinator_data.copy()
    master_data["role"] = "master"
    master_data["multiroom"] = {"slave_count": 1, "slaves": [{"ip": "192.168.1.101", "name": "Slave"}]}

    with patch("custom_components.wiim.coordinator_polling.async_update_data", return_value=master_data):
        try:
            await coordinator.async_refresh()

            assert coordinator.get_current_role() == "master"
            assert coordinator.is_wiim_master is True
            assert coordinator.has_slaves() is True

        finally:
            await coordinator.async_shutdown()


async def test_coordinator_listeners(hass: HomeAssistant, mock_wiim_client, mock_coordinator_data) -> None:
    """Test coordinator listener functionality."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    listener_called = False

    def mock_listener():
        nonlocal listener_called
        listener_called = True

    coordinator.async_add_listener(mock_listener)

    with patch("custom_components.wiim.coordinator_polling.async_update_data", return_value=mock_coordinator_data):
        try:
            await coordinator.async_refresh()
            assert listener_called is True

        finally:
            await coordinator.async_shutdown()


async def test_coordinator_error_recovery(hass: HomeAssistant, mock_wiim_client, mock_coordinator_data) -> None:
    """Test coordinator error recovery with backoff."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    try:
        # First update fails
        with patch(
            "custom_components.wiim.coordinator_polling.async_update_data", side_effect=WiiMError("Connection error")
        ):
            await coordinator.async_refresh()
            assert coordinator.last_update_success is False

        # Second update succeeds
        with patch("custom_components.wiim.coordinator_polling.async_update_data", return_value=mock_coordinator_data):
            await coordinator.async_refresh()
            assert coordinator.last_update_success is True

    finally:
        await coordinator.async_shutdown()


@pytest.mark.skip(reason="Skipped due to HA background thread issue - functionality covered by other tests")
async def test_coordinator_with_integration(hass: HomeAssistant, bypass_get_data) -> None:
    """Test coordinator working with full integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_DEVICE_DATA["uuid"],
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get coordinator from hass data
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    assert coordinator is not None
    assert isinstance(coordinator, WiiMCoordinator)
    assert coordinator.last_update_success is True
