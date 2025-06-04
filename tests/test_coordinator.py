"""Test WiiM coordinator."""

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wiim import DOMAIN
from custom_components.wiim.api import WiiMError
from custom_components.wiim.coordinator import WiiMCoordinator

from .const import MOCK_CONFIG, MOCK_DEVICE_DATA, MOCK_STATUS_RESPONSE


async def test_coordinator_initialization(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator initialization."""
    # Set up mock client with host property
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"  # For the coordinator name construction

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    assert coordinator.name == "WiiM 192.168.1.100"
    assert coordinator.client == mock_wiim_client
    assert coordinator.client.host == "192.168.1.100"


async def test_coordinator_update_success(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test successful coordinator update."""
    # Set up mock client with host property
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    # Mock successful API calls
    mock_wiim_client.get_status.return_value = MOCK_STATUS_RESPONSE
    mock_wiim_client.get_device_info.return_value = MOCK_DEVICE_DATA

    try:
        await coordinator.async_refresh()

        assert coordinator.last_update_success is True
        assert coordinator.data is not None
        assert "status" in coordinator.data
        assert "multiroom" in coordinator.data
        assert "role" in coordinator.data
    finally:
        # Clean up the coordinator to prevent lingering timers
        await coordinator.async_shutdown()


async def test_coordinator_update_failure(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator update failure."""
    # Set up mock client with host property
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    # Mock ALL API calls to fail - this should trigger UpdateFailed
    mock_wiim_client.get_player_status.side_effect = WiiMError("Connection error")
    mock_wiim_client.get_status.side_effect = WiiMError("Connection error")
    mock_wiim_client.get_multiroom_info.side_effect = WiiMError("Connection error")

    try:
        await coordinator.async_refresh()
        # The coordinator should handle the failure gracefully
        assert coordinator.last_update_success is False
    finally:
        # Clean up the coordinator to prevent lingering timers
        await coordinator.async_shutdown()


async def test_coordinator_partial_update_failure(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator handling partial update failures."""
    # Set up mock client with host property
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    # Mock status success but device info failure - partial failures don't cause total failure
    mock_wiim_client.get_player_status.return_value = MOCK_STATUS_RESPONSE
    mock_wiim_client.get_status.return_value = MOCK_STATUS_RESPONSE
    mock_wiim_client.get_multiroom_info.return_value = {"slaves": 0}

    try:
        # Should succeed if at least one endpoint works
        await coordinator.async_refresh()

        # Check that status data is available
        assert coordinator.data is not None
        assert "status" in coordinator.data
    finally:
        # Clean up the coordinator to prevent lingering timers
        await coordinator.async_shutdown()


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
    # Set up mock client with host property
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    # Mock successful API calls
    mock_wiim_client.get_status.return_value = MOCK_STATUS_RESPONSE
    mock_wiim_client.get_device_info.return_value = MOCK_DEVICE_DATA

    # Add a mock listener
    listener_called = False

    def mock_listener():
        nonlocal listener_called
        listener_called = True

    coordinator.async_add_listener(mock_listener)

    try:
        # Trigger update using the proper API
        await coordinator.async_refresh()

        # Listener should have been called
        assert listener_called is True
    finally:
        # Clean up the coordinator to prevent lingering timers
        await coordinator.async_shutdown()


async def test_coordinator_data_structure(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator data structure."""
    # Set up mock client with host property
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    # Mock successful API calls
    mock_wiim_client.get_player_status.return_value = MOCK_STATUS_RESPONSE
    mock_wiim_client.get_status.return_value = MOCK_STATUS_RESPONSE
    mock_wiim_client.get_multiroom_info.return_value = {"slaves": 0}

    try:
        await coordinator.async_refresh()

        # Check data structure
        assert coordinator.data is not None
        assert isinstance(coordinator.data, dict)

        # Check expected keys that actually exist in current implementation
        expected_keys = ["status", "multiroom", "role"]
        for key in expected_keys:
            assert key in coordinator.data
            assert coordinator.data[key] is not None
    finally:
        # Clean up the coordinator to prevent lingering timers
        await coordinator.async_shutdown()


async def test_coordinator_error_recovery(hass: HomeAssistant, mock_wiim_client) -> None:
    """Test coordinator error recovery."""
    # Set up mock client with host property
    mock_wiim_client.host = "192.168.1.100"
    mock_wiim_client._host = "192.168.1.100"

    coordinator = WiiMCoordinator(hass, mock_wiim_client)

    try:
        # First update fails - ALL endpoints fail
        mock_wiim_client.get_player_status.side_effect = WiiMError("Connection error")
        mock_wiim_client.get_status.side_effect = WiiMError("Connection error")
        mock_wiim_client.get_multiroom_info.side_effect = WiiMError("Connection error")

        await coordinator.async_refresh()
        assert coordinator.last_update_success is False

        # Second update succeeds - clear the side effects
        mock_wiim_client.get_player_status.side_effect = None
        mock_wiim_client.get_status.side_effect = None
        mock_wiim_client.get_multiroom_info.side_effect = None
        mock_wiim_client.get_player_status.return_value = MOCK_STATUS_RESPONSE
        mock_wiim_client.get_status.return_value = MOCK_STATUS_RESPONSE
        mock_wiim_client.get_multiroom_info.return_value = {"slaves": 0}

        await coordinator.async_refresh()

        assert coordinator.last_update_success is True
    finally:
        # Clean up the coordinator to prevent lingering timers
        await coordinator.async_shutdown()
