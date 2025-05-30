"""Test WiiM coordinator."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wiim.const import DOMAIN
from custom_components.wiim.coordinator import WiiMCoordinator

from .const import MOCK_CONFIG, MOCK_DEVICE_DATA, MOCK_STATUS_RESPONSE


async def test_coordinator_initialization(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator initialization."""
    coordinator = WiiMCoordinator(hass, mock_wiim_client, "test_host")

    assert coordinator.name == "WiiM"
    assert coordinator._client == mock_wiim_client
    assert coordinator._host == "test_host"


async def test_coordinator_update_success(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test successful coordinator update."""
    coordinator = WiiMCoordinator(hass, mock_wiim_client, "test_host")

    # Mock successful API calls
    mock_wiim_client.get_status.return_value = MOCK_STATUS_RESPONSE
    mock_wiim_client.get_device_info.return_value = MOCK_DEVICE_DATA

    await coordinator.async_request_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data is not None
    assert "status" in coordinator.data
    assert "device_info" in coordinator.data


async def test_coordinator_update_failure(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator update failure."""
    coordinator = WiiMCoordinator(hass, mock_wiim_client, "test_host")

    # Mock API call failure
    mock_wiim_client.get_status.side_effect = Exception("Connection error")

    with pytest.raises(UpdateFailed):
        await coordinator.async_request_refresh()


async def test_coordinator_partial_update_failure(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator handling partial update failures."""
    coordinator = WiiMCoordinator(hass, mock_wiim_client, "test_host")

    # Mock status success but device info failure
    mock_wiim_client.get_status.return_value = MOCK_STATUS_RESPONSE
    mock_wiim_client.get_device_info.side_effect = Exception("Device info error")

    # Should still succeed if at least status is available
    await coordinator.async_request_refresh()

    # Check that status data is available even if device info failed
    assert coordinator.data is not None
    assert "status" in coordinator.data


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


async def test_coordinator_listeners(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator listener functionality."""
    coordinator = WiiMCoordinator(hass, mock_wiim_client, "test_host")

    # Mock successful API calls
    mock_wiim_client.get_status.return_value = MOCK_STATUS_RESPONSE
    mock_wiim_client.get_device_info.return_value = MOCK_DEVICE_DATA

    # Add a mock listener
    listener_called = False

    def mock_listener():
        nonlocal listener_called
        listener_called = True

    coordinator.async_add_listener(mock_listener)

    # Trigger update
    await coordinator.async_request_refresh()

    # Listener should have been called
    assert listener_called is True


async def test_coordinator_data_structure(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator data structure."""
    coordinator = WiiMCoordinator(hass, mock_wiim_client, "test_host")

    # Mock successful API calls
    mock_wiim_client.get_status.return_value = MOCK_STATUS_RESPONSE
    mock_wiim_client.get_device_info.return_value = MOCK_DEVICE_DATA

    await coordinator.async_request_refresh()

    # Check data structure
    assert coordinator.data is not None
    assert isinstance(coordinator.data, dict)

    # Check expected keys
    expected_keys = ["status", "device_info"]
    for key in expected_keys:
        if key in coordinator.data:
            assert coordinator.data[key] is not None


async def test_coordinator_error_recovery(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator error recovery."""
    coordinator = WiiMCoordinator(hass, mock_wiim_client, "test_host")

    # First update fails
    mock_wiim_client.get_status.side_effect = Exception("Connection error")

    with pytest.raises(UpdateFailed):
        await coordinator.async_request_refresh()

    assert coordinator.last_update_success is False

    # Second update succeeds
    mock_wiim_client.get_status.side_effect = None
    mock_wiim_client.get_status.return_value = MOCK_STATUS_RESPONSE
    mock_wiim_client.get_device_info.return_value = MOCK_DEVICE_DATA

    await coordinator.async_request_refresh()

    assert coordinator.last_update_success is True
