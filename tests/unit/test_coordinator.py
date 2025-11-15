"""Test WiiM coordinator with comprehensive coverage of refactored architecture."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pywiim.exceptions import WiiMError

from custom_components.wiim import DOMAIN
from custom_components.wiim.coordinator import WiiMCoordinator
from custom_components.wiim.models import DeviceInfo, PlayerStatus
from tests.const import MOCK_CONFIG, MOCK_DEVICE_DATA, MOCK_STATUS_RESPONSE


async def test_coordinator_initialization(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator initialization."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    assert coordinator.name == "WiiM 192.168.1.100"
    assert coordinator.client == mock_wiim_client
    assert coordinator.client.host == "192.168.1.100"
    assert coordinator._polling_strategy is not None
    assert coordinator._track_detector is not None


async def test_coordinator_update_success(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test successful coordinator update with pywiim client methods."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"
    mock_wiim_client.get_player_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
    mock_wiim_client.get_device_info = AsyncMock(return_value=MOCK_DEVICE_DATA)
    mock_wiim_client.get_multiroom_status = AsyncMock(return_value={})
    mock_wiim_client.get_meta_info = AsyncMock(return_value=None)

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    try:
        await coordinator.async_refresh()

        assert coordinator.last_update_success is True
        assert coordinator.data is not None

        # Verify the data structure
        assert "status_model" in coordinator.data
        assert "device_model" in coordinator.data
        assert "multiroom" in coordinator.data
        assert "role" in coordinator.data

        # Verify models are properly typed
        assert isinstance(coordinator.data["status_model"], PlayerStatus)
        assert isinstance(coordinator.data["device_model"], DeviceInfo)
        assert coordinator.data["role"] == "solo"

        # Verify pywiim client methods were called
        mock_wiim_client.get_player_status.assert_called_once()

    finally:
        await coordinator.async_shutdown()


async def test_coordinator_update_failure(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator update failure with proper error handling."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"
    mock_wiim_client.get_player_status = AsyncMock(side_effect=WiiMError("Connection error"))

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    try:
        await coordinator.async_refresh()
        assert coordinator.last_update_success is False

    finally:
        await coordinator.async_shutdown()


async def test_coordinator_partial_update_failure(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator handling partial update failures."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"
    mock_wiim_client.get_player_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
    # Device info fails, but status succeeds
    mock_wiim_client.get_device_info = AsyncMock(side_effect=WiiMError("Device info failed"))
    mock_wiim_client.get_multiroom_status = AsyncMock(return_value={})
    mock_wiim_client.get_meta_info = AsyncMock(return_value=None)

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    try:
        await coordinator.async_refresh()
        assert coordinator.data is not None
        assert "status_model" in coordinator.data
        # Device model should be None when fetch fails
        assert coordinator.data.get("device_model") is None

    finally:
        await coordinator.async_shutdown()


async def test_coordinator_device_data(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator device data access."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"
    mock_wiim_client.get_player_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
    mock_wiim_client.get_device_info = AsyncMock(return_value=MOCK_DEVICE_DATA)
    mock_wiim_client.get_multiroom_status = AsyncMock(return_value={})
    mock_wiim_client.get_meta_info = AsyncMock(return_value=None)

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    try:
        await coordinator.async_refresh()

        # Test device data is stored correctly
        assert coordinator.data is not None
        assert coordinator.data["device_model"] is not None
        assert coordinator.data["device_model"].uuid == MOCK_DEVICE_DATA["uuid"]
        assert coordinator.data["device_model"].name == MOCK_DEVICE_DATA["DeviceName"]

    finally:
        await coordinator.async_shutdown()


async def test_coordinator_client_access(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator provides access to pywiim client."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    try:
        # Coordinator should provide access to pywiim client for entity control
        assert coordinator.client == mock_wiim_client
        assert coordinator.client.host == "192.168.1.100"

    finally:
        await coordinator.async_shutdown()


async def test_coordinator_role_detection(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator role detection functionality."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"
    mock_wiim_client.get_player_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
    mock_wiim_client.get_device_info = AsyncMock(return_value=MOCK_DEVICE_DATA)
    mock_wiim_client.get_multiroom_status = AsyncMock(return_value={})
    mock_wiim_client.get_meta_info = AsyncMock(return_value=None)

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    try:
        await coordinator.async_refresh()

        # Test role detection - solo device
        assert coordinator.data["role"] == "solo"

    finally:
        await coordinator.async_shutdown()


async def test_coordinator_group_management(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator group management functionality."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"
    mock_wiim_client.get_player_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
    mock_wiim_client.get_device_info = AsyncMock(return_value=MOCK_DEVICE_DATA)
    # Master device with slaves
    mock_wiim_client.get_multiroom_status = AsyncMock(return_value={"slaves": 1, "slave_list": []})
    mock_wiim_client.get_meta_info = AsyncMock(return_value=None)

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    try:
        await coordinator.async_refresh()

        # Test master role detection
        assert coordinator.data["role"] == "master"
        assert coordinator.data["multiroom"].get("slaves") == 1

    finally:
        await coordinator.async_shutdown()


async def test_coordinator_listeners(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator listener functionality."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"
    mock_wiim_client.get_player_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
    mock_wiim_client.get_device_info = AsyncMock(return_value=MOCK_DEVICE_DATA)
    mock_wiim_client.get_multiroom_status = AsyncMock(return_value={})
    mock_wiim_client.get_meta_info = AsyncMock(return_value=None)

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    listener_called = False

    def mock_listener():
        nonlocal listener_called
        listener_called = True

    coordinator.async_add_listener(mock_listener)

    try:
        await coordinator.async_refresh()
        assert listener_called is True

    finally:
        await coordinator.async_shutdown()


async def test_coordinator_error_recovery(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator error recovery."""
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    try:
        # First update fails
        mock_wiim_client.get_player_status = AsyncMock(side_effect=WiiMError("Connection error"))
        await coordinator.async_refresh()
        assert coordinator.last_update_success is False

        # Second update succeeds
        mock_wiim_client.get_player_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
        mock_wiim_client.get_device_info = AsyncMock(return_value=MOCK_DEVICE_DATA)
        mock_wiim_client.get_multiroom_status = AsyncMock(return_value={})
        mock_wiim_client.get_meta_info = AsyncMock(return_value=None)
        await coordinator.async_refresh()
        assert coordinator.last_update_success is True

    finally:
        await coordinator.async_shutdown()


@pytest.mark.skip(reason="Skipped due to HA background thread issue - functionality covered by other tests")
async def test_coordinator_with_integration(hass: HomeAssistant, bypass_get_data) -> None:  # noqa: ARG001
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
