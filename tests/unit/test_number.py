"""Unit tests for WiiM number platform - testing subwoofer level control."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry

from custom_components.wiim.number import WiiMSubwooferLevelNumber, async_setup_entry


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
    coordinator.player.subwoofer_status = {"plugged": True, "status": True, "level": 5}
    coordinator.player.get_subwoofer_status = AsyncMock(return_value={"plugged": True, "status": True, "level": 5})
    coordinator.player.set_subwoofer_level = AsyncMock()
    return coordinator


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {"wiim": {"test_entry_id": {"coordinator": MagicMock()}}}
    hass.async_create_task = MagicMock()
    return hass


class TestSubwooferLevelSetup:
    """Test subwoofer level number setup."""

    @pytest.mark.asyncio
    async def test_setup_creates_entity_when_subwoofer_connected(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test setup creates entity when subwoofer is connected."""
        mock_hass.data["wiim"]["test_entry_id"]["coordinator"] = mock_coordinator
        mock_coordinator.player.supports_subwoofer = True
        mock_coordinator.player.subwoofer_status = {"plugged": True, "status": True, "level": 5}

        entities = []

        def mock_add_entities(new_entities):
            entities.extend(new_entities)

        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

        assert len(entities) == 1
        assert isinstance(entities[0], WiiMSubwooferLevelNumber)

    @pytest.mark.asyncio
    async def test_setup_skips_entity_when_no_subwoofer(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test setup skips entity when no subwoofer connected."""
        mock_hass.data["wiim"]["test_entry_id"]["coordinator"] = mock_coordinator
        mock_coordinator.player.supports_subwoofer = True
        mock_coordinator.player.subwoofer_status = {"plugged": False, "status": False, "level": 0}

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


class TestSubwooferLevelBasic:
    """Test basic subwoofer level number functionality."""

    def test_initialization(self, mock_coordinator, mock_config_entry):
        """Test subwoofer level number initialization."""
        entity = WiiMSubwooferLevelNumber(mock_coordinator, mock_config_entry)
        assert entity.unique_id == "test-uuid_subwoofer_level"
        assert entity.name == "Subwoofer Level"

    def test_icon(self, mock_coordinator, mock_config_entry):
        """Test icon property."""
        entity = WiiMSubwooferLevelNumber(mock_coordinator, mock_config_entry)
        assert entity.icon == "mdi:speaker-wireless"

    def test_has_entity_name(self, mock_coordinator, mock_config_entry):
        """Test has_entity_name property."""
        entity = WiiMSubwooferLevelNumber(mock_coordinator, mock_config_entry)
        assert entity._attr_has_entity_name is True

    def test_min_max_step_values(self, mock_coordinator, mock_config_entry):
        """Test min, max, and step values."""
        entity = WiiMSubwooferLevelNumber(mock_coordinator, mock_config_entry)
        assert entity.native_min_value == -15.0
        assert entity.native_max_value == 15.0
        assert entity.native_step == 1.0


class TestSubwooferLevelState:
    """Test subwoofer level number state."""

    def test_native_value_returns_cached_value(self, mock_coordinator, mock_config_entry):
        """Test native_value returns cached value."""
        entity = WiiMSubwooferLevelNumber(mock_coordinator, mock_config_entry)
        entity._value = 5.0
        assert entity.native_value == 5.0

        entity._value = -10.0
        assert entity.native_value == -10.0

    def test_native_value_returns_none_when_not_set(self, mock_coordinator, mock_config_entry):
        """Test native_value returns None when not initialized."""
        entity = WiiMSubwooferLevelNumber(mock_coordinator, mock_config_entry)
        assert entity.native_value is None

    def test_available_when_value_set(self, mock_coordinator, mock_config_entry):
        """Test available is True when value is set."""
        entity = WiiMSubwooferLevelNumber(mock_coordinator, mock_config_entry)
        entity._value = 0.0
        assert entity.available is True

    def test_unavailable_when_value_none(self, mock_coordinator, mock_config_entry):
        """Test available is False when value is None."""
        entity = WiiMSubwooferLevelNumber(mock_coordinator, mock_config_entry)
        entity._value = None
        assert entity.available is False


class TestSubwooferLevelControl:
    """Test subwoofer level number control methods."""

    @pytest.mark.asyncio
    async def test_set_native_value(self, mock_coordinator, mock_config_entry):
        """Test set_native_value sets subwoofer level."""
        entity = WiiMSubwooferLevelNumber(mock_coordinator, mock_config_entry)
        entity.async_write_ha_state = MagicMock()

        await entity.async_set_native_value(10.0)

        mock_coordinator.player.set_subwoofer_level.assert_called_once_with(10)
        assert entity._value == 10.0
        entity.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_native_value_negative(self, mock_coordinator, mock_config_entry):
        """Test set_native_value handles negative values."""
        entity = WiiMSubwooferLevelNumber(mock_coordinator, mock_config_entry)
        entity.async_write_ha_state = MagicMock()

        await entity.async_set_native_value(-5.0)

        mock_coordinator.player.set_subwoofer_level.assert_called_once_with(-5)
        assert entity._value == -5.0

    @pytest.mark.asyncio
    async def test_update_state_fetches_status(self, mock_coordinator, mock_config_entry):
        """Test _update_state fetches subwoofer status."""
        mock_coordinator.player.get_subwoofer_status = AsyncMock(
            return_value={"plugged": True, "status": True, "level": 7}
        )
        entity = WiiMSubwooferLevelNumber(mock_coordinator, mock_config_entry)

        await entity._update_state()

        mock_coordinator.player.get_subwoofer_status.assert_called_once()
        assert entity._value == 7.0

    @pytest.mark.asyncio
    async def test_update_state_handles_error(self, mock_coordinator, mock_config_entry):
        """Test _update_state handles errors gracefully."""
        mock_coordinator.player.get_subwoofer_status = AsyncMock(side_effect=Exception("Connection error"))
        entity = WiiMSubwooferLevelNumber(mock_coordinator, mock_config_entry)
        entity._value = 3.0  # Set initial value

        await entity._update_state()

        # Should not crash and should not change value on error
        assert entity._value == 3.0


class TestNumberPlatformConstants:
    """Test number platform constants and configuration."""

    def test_number_platform_import(self):
        """Test that number platform can be imported."""
        from custom_components.wiim import number

        # Should be able to import the module
        assert hasattr(number, "async_setup_entry")
        assert callable(number.async_setup_entry)
        assert hasattr(number, "WiiMSubwooferLevelNumber")
