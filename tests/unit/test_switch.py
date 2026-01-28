"""Unit tests for WiiM Switch Entity - testing subwoofer control."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry

from custom_components.wiim.switch import WiiMSubwooferSwitch, async_setup_entry


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.unique_id = "test-uuid"
    entry.data = {"host": "192.168.1.100"}
    entry.options = {}
    entry.title = "Test WiiM"
    return entry


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {"player": MagicMock()}
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    coordinator.player = MagicMock()
    coordinator.player.name = "Test WiiM"
    coordinator.player.host = "192.168.1.100"
    coordinator.player.supports_subwoofer = True
    coordinator.player.subwoofer_status = {"plugged": True, "status": True, "level": 0}
    coordinator.player.get_subwoofer_status = AsyncMock(return_value={"plugged": True, "status": True, "level": 0})
    coordinator.player.set_subwoofer_enabled = AsyncMock()
    return coordinator


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {"wiim": {"test_entry_id": {"coordinator": MagicMock()}}}
    hass.async_create_task = MagicMock()
    return hass


class TestSubwooferSwitchSetup:
    """Test subwoofer switch setup."""

    @pytest.mark.asyncio
    async def test_setup_creates_entity_when_subwoofer_connected(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test setup creates entity when subwoofer is connected."""
        mock_hass.data["wiim"]["test_entry_id"]["coordinator"] = mock_coordinator
        mock_coordinator.player.supports_subwoofer = True
        mock_coordinator.player.subwoofer_status = {"plugged": True, "status": True}

        entities = []

        def mock_add_entities(new_entities):
            entities.extend(new_entities)

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        assert len(entities) == 1
        assert isinstance(entities[0], WiiMSubwooferSwitch)

    @pytest.mark.asyncio
    async def test_setup_skips_entity_when_no_subwoofer(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test setup skips entity when no subwoofer connected."""
        mock_hass.data["wiim"]["test_entry_id"]["coordinator"] = mock_coordinator
        mock_coordinator.player.supports_subwoofer = True
        mock_coordinator.player.subwoofer_status = {"plugged": False, "status": False}

        entities = []

        def mock_add_entities(new_entities):
            entities.extend(new_entities)

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_setup_skips_entity_when_not_supported(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test setup skips entity when device doesn't support subwoofer."""
        mock_hass.data["wiim"]["test_entry_id"]["coordinator"] = mock_coordinator
        mock_coordinator.player.supports_subwoofer = False

        entities = []

        def mock_add_entities(new_entities):
            entities.extend(new_entities)

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        assert len(entities) == 0


class TestSubwooferSwitchBasic:
    """Test basic subwoofer switch functionality."""

    def test_initialization(self, mock_coordinator, mock_config_entry):
        """Test subwoofer switch initialization."""
        entity = WiiMSubwooferSwitch(mock_coordinator, mock_config_entry)
        assert entity.unique_id == "test-uuid_subwoofer"
        assert entity.name == "Subwoofer"

    def test_icon(self, mock_coordinator, mock_config_entry):
        """Test icon property."""
        entity = WiiMSubwooferSwitch(mock_coordinator, mock_config_entry)
        assert entity.icon == "mdi:speaker"

    def test_has_entity_name(self, mock_coordinator, mock_config_entry):
        """Test has_entity_name property."""
        entity = WiiMSubwooferSwitch(mock_coordinator, mock_config_entry)
        assert entity._attr_has_entity_name is True


class TestSubwooferSwitchState:
    """Test subwoofer switch state."""

    def test_is_on_returns_cached_state(self, mock_coordinator, mock_config_entry):
        """Test is_on returns cached state."""
        entity = WiiMSubwooferSwitch(mock_coordinator, mock_config_entry)
        entity._is_on = True
        assert entity.is_on is True

        entity._is_on = False
        assert entity.is_on is False

    def test_is_on_returns_none_when_not_set(self, mock_coordinator, mock_config_entry):
        """Test is_on returns None when not initialized."""
        entity = WiiMSubwooferSwitch(mock_coordinator, mock_config_entry)
        assert entity.is_on is None

    def test_available_when_state_set(self, mock_coordinator, mock_config_entry):
        """Test available is True when state is set."""
        entity = WiiMSubwooferSwitch(mock_coordinator, mock_config_entry)
        entity._is_on = True
        assert entity.available is True

    def test_unavailable_when_state_none(self, mock_coordinator, mock_config_entry):
        """Test available is False when state is None."""
        entity = WiiMSubwooferSwitch(mock_coordinator, mock_config_entry)
        entity._is_on = None
        assert entity.available is False


class TestSubwooferSwitchControl:
    """Test subwoofer switch control methods."""

    @pytest.mark.asyncio
    async def test_turn_on(self, mock_coordinator, mock_config_entry):
        """Test turn on enables subwoofer."""
        entity = WiiMSubwooferSwitch(mock_coordinator, mock_config_entry)
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on()

        mock_coordinator.player.set_subwoofer_enabled.assert_called_once_with(True)
        assert entity._is_on is True
        entity.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_turn_off(self, mock_coordinator, mock_config_entry):
        """Test turn off disables subwoofer."""
        entity = WiiMSubwooferSwitch(mock_coordinator, mock_config_entry)
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_off()

        mock_coordinator.player.set_subwoofer_enabled.assert_called_once_with(False)
        assert entity._is_on is False
        entity.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_state_fetches_status(self, mock_coordinator, mock_config_entry):
        """Test _update_state fetches subwoofer status."""
        mock_coordinator.player.get_subwoofer_status = AsyncMock(return_value={"plugged": True, "status": True})
        entity = WiiMSubwooferSwitch(mock_coordinator, mock_config_entry)

        await entity._update_state()

        mock_coordinator.player.get_subwoofer_status.assert_called_once()
        assert entity._is_on is True

    @pytest.mark.asyncio
    async def test_update_state_handles_error(self, mock_coordinator, mock_config_entry):
        """Test _update_state handles errors gracefully."""
        mock_coordinator.player.get_subwoofer_status = AsyncMock(side_effect=Exception("Connection error"))
        entity = WiiMSubwooferSwitch(mock_coordinator, mock_config_entry)
        entity._is_on = True  # Set initial state

        await entity._update_state()

        # Should not crash and should not change state on error
        assert entity._is_on is True
