"""Unit tests for WiiM Light platform – LED (on/off) and Display entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_COLOR_MODE, ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.wiim.const import DOMAIN
from custom_components.wiim.light import (
    WiiMDisplayLight,
    WiiMLEDLight,
    async_setup_entry,
)


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.unique_id = "test-uuid"
    entry.data = {"host": "192.168.1.100"}
    entry.options = {}
    return entry


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {"player": MagicMock()}
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    coordinator.player = MagicMock()
    coordinator.player.set_led = AsyncMock(return_value=True)
    coordinator.player.set_display_enabled = AsyncMock(return_value=True)
    coordinator.player.set_display_config = AsyncMock(return_value=True)
    return coordinator


@pytest.fixture
def mock_coordinator_setup(mock_coordinator, mock_config_entry):
    """Set up mock_coordinator with player properties."""
    mock_coordinator.player.name = "Test WiiM"
    mock_coordinator.player.model = "WiiM Mini"
    mock_coordinator.player.firmware = "1.0.0"
    mock_coordinator.player.host = "192.168.1.100"
    mock_coordinator.player.device_info = MagicMock()
    mock_coordinator.player.device_info.mac = "AA:BB:CC:DD:EE:FF"
    mock_coordinator.player.input_list = ["spotify", "bluetooth"]
    mock_coordinator.player.supports_display_config = False
    return mock_coordinator, mock_config_entry


# ----- WiiMLEDLight (on/off only) -----


class TestWiiMLEDLightBasic:
    """Test basic LED light functionality (on/off only)."""

    def test_initialization(self, mock_coordinator_setup):
        """Test LED light initialization."""
        mock_coordinator, mock_config_entry = mock_coordinator_setup
        entity = WiiMLEDLight(mock_coordinator, mock_config_entry)
        assert entity.unique_id == "test-uuid_led"
        assert entity.name == "LED"
        assert entity.coordinator == mock_coordinator

    def test_supported_color_modes_onoff(self, mock_coordinator_setup):
        """Test LED supports on/off only."""
        mock_coordinator, mock_config_entry = mock_coordinator_setup
        entity = WiiMLEDLight(mock_coordinator, mock_config_entry)
        assert entity.supported_color_modes == {ColorMode.ONOFF}

    def test_color_mode_reported(self, mock_coordinator_setup):
        """Test entity reports color_mode (required by HA 2025.3+)."""
        mock_coordinator, mock_config_entry = mock_coordinator_setup
        entity = WiiMLEDLight(mock_coordinator, mock_config_entry)
        assert entity.color_mode == ColorMode.ONOFF

    def test_has_entity_name(self, mock_coordinator_setup):
        """Test has_entity_name property."""
        mock_coordinator, mock_config_entry = mock_coordinator_setup
        entity = WiiMLEDLight(mock_coordinator, mock_config_entry)
        assert entity._attr_has_entity_name is True

    def test_assumed_state(self, mock_coordinator_setup):
        """Test assumed_state property."""
        mock_coordinator, mock_config_entry = mock_coordinator_setup
        entity = WiiMLEDLight(mock_coordinator, mock_config_entry)
        assert entity._attr_assumed_state is True

    def test_available_mirrors_coordinator(self, mock_coordinator_setup):
        """Test availability mirrors coordinator last_update_success."""
        mock_coordinator, mock_config_entry = mock_coordinator_setup
        mock_coordinator.last_update_success = True
        entity = WiiMLEDLight(mock_coordinator, mock_config_entry)
        assert entity.available is True

        mock_coordinator.last_update_success = False
        entity = WiiMLEDLight(mock_coordinator, mock_config_entry)
        assert entity.available is False

    def test_is_on_initial_state(self, mock_coordinator_setup):
        """Test initial is_on state."""
        mock_coordinator, mock_config_entry = mock_coordinator_setup
        entity = WiiMLEDLight(mock_coordinator, mock_config_entry)
        assert entity.is_on is None

    def test_state_attributes_include_color_mode_when_on(self, mock_coordinator_setup):
        """Test HA state attributes render LED color mode without errors."""
        mock_coordinator, mock_config_entry = mock_coordinator_setup
        entity = WiiMLEDLight(mock_coordinator, mock_config_entry)
        entity._is_on = True

        assert entity.state_attributes[ATTR_COLOR_MODE] == ColorMode.ONOFF


class TestWiiMLEDLightTurnOnOff:
    """Test LED turn on/off (no brightness)."""

    async def test_turn_on_calls_set_led_true_only(self, mock_coordinator_setup, mock_coordinator):
        """Test turn on only calls set_led(True); no brightness."""
        mock_coordinator, mock_config_entry = mock_coordinator_setup
        entity = WiiMLEDLight(mock_coordinator, mock_config_entry)
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on()

        mock_coordinator.player.set_led.assert_called_once_with(True)
        assert entity.is_on is True

    async def test_turn_on_ignores_brightness_kwarg(self, mock_coordinator_setup, mock_coordinator):
        """Test turn on with brightness kwarg still only calls set_led(True)."""
        mock_coordinator, mock_config_entry = mock_coordinator_setup
        entity = WiiMLEDLight(mock_coordinator, mock_config_entry)
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on(**{ATTR_BRIGHTNESS: 128})

        mock_coordinator.player.set_led.assert_called_once_with(True)
        assert entity.is_on is True

    async def test_turn_off(self, mock_coordinator_setup, mock_coordinator):
        """Test turn off LED."""
        mock_coordinator, mock_config_entry = mock_coordinator_setup
        entity = WiiMLEDLight(mock_coordinator, mock_config_entry)
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on()
        mock_coordinator.player.reset_mock()

        await entity.async_turn_off()

        mock_coordinator.player.set_led.assert_called_once_with(False)
        assert entity.is_on is False

    async def test_turn_on_handles_error(self, mock_coordinator_setup, mock_coordinator):
        """Test turn on handles errors."""
        mock_coordinator, mock_config_entry = mock_coordinator_setup
        mock_coordinator.player.set_led.side_effect = Exception("LED error")

        entity = WiiMLEDLight(mock_coordinator, mock_config_entry)

        with pytest.raises(Exception, match="LED error"):
            await entity.async_turn_on()

        assert entity.is_on is None

    async def test_turn_off_handles_error(self, mock_coordinator_setup, mock_coordinator):
        """Test turn off handles errors."""
        mock_coordinator, mock_config_entry = mock_coordinator_setup
        mock_coordinator.player.set_led.side_effect = Exception("LED error")

        entity = WiiMLEDLight(mock_coordinator, mock_config_entry)

        with pytest.raises(Exception, match="LED error"):
            await entity.async_turn_off()


# ----- WiiMDisplayLight -----


@pytest.fixture
def mock_coordinator_with_display(mock_coordinator, mock_config_entry):
    """Coordinator with supports_display_config True (WiiM Ultra)."""
    mock_coordinator.player.name = "WiiM Ultra"
    mock_coordinator.player.model = "WiiM Ultra"
    mock_coordinator.player.host = "192.168.1.101"
    mock_coordinator.player.supports_display_config = True
    mock_coordinator.player.device_info = MagicMock()
    mock_coordinator.player.device_info.mac = "AA:BB:CC:DD:EE:FF"
    mock_config_entry.unique_id = "ultra-uuid"
    return mock_coordinator, mock_config_entry


class TestWiiMDisplayLightBasic:
    """Test Display light entity (WiiM Ultra)."""

    def test_initialization(self, mock_coordinator_with_display):
        """Test Display light initialization."""
        mock_coordinator, mock_config_entry = mock_coordinator_with_display
        entity = WiiMDisplayLight(mock_coordinator, mock_config_entry)
        assert entity.unique_id == "ultra-uuid_display"
        assert entity.name == "Display"

    def test_supported_color_modes_brightness(self, mock_coordinator_with_display):
        """Test Display supports brightness."""
        mock_coordinator, mock_config_entry = mock_coordinator_with_display
        entity = WiiMDisplayLight(mock_coordinator, mock_config_entry)
        assert entity.supported_color_modes == {ColorMode.BRIGHTNESS}
        assert entity.color_mode == ColorMode.BRIGHTNESS

    def test_initial_state(self, mock_coordinator_with_display):
        """Test initial display state."""
        mock_coordinator, mock_config_entry = mock_coordinator_with_display
        entity = WiiMDisplayLight(mock_coordinator, mock_config_entry)
        assert entity.is_on is None
        assert entity.brightness is None

    def test_state_attributes_include_color_mode_when_on(self, mock_coordinator_with_display):
        """Test HA state attributes render display color mode without errors."""
        mock_coordinator, mock_config_entry = mock_coordinator_with_display
        entity = WiiMDisplayLight(mock_coordinator, mock_config_entry)
        entity._is_on = True
        entity._brightness = 255

        assert entity.state_attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS


class TestWiiMDisplayLightTurnOnOff:
    """Test Display turn on/off and brightness."""

    async def test_turn_on_enables_display(self, mock_coordinator_with_display, mock_coordinator):
        """Test turn on calls set_display_enabled(True)."""
        mock_coordinator, mock_config_entry = mock_coordinator_with_display
        entity = WiiMDisplayLight(mock_coordinator, mock_config_entry)
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on()

        mock_coordinator.player.set_display_enabled.assert_called_once_with(True)
        mock_coordinator.player.set_display_config.assert_not_called()
        assert entity.is_on is True
        assert entity.brightness == 255

    async def test_turn_on_with_brightness(self, mock_coordinator_with_display, mock_coordinator):
        """Test turn on with brightness calls set_display_config."""
        mock_coordinator, mock_config_entry = mock_coordinator_with_display
        entity = WiiMDisplayLight(mock_coordinator, mock_config_entry)
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on(**{ATTR_BRIGHTNESS: 128})

        mock_coordinator.player.set_display_enabled.assert_called_once_with(True)
        mock_coordinator.player.set_display_config.assert_called_once()
        call_kw = mock_coordinator.player.set_display_config.call_args[1]
        assert call_kw["default_bright"] == 50
        assert call_kw["disable"] == 0
        assert entity.brightness == 128

    async def test_turn_off(self, mock_coordinator_with_display, mock_coordinator):
        """Test turn off display."""
        mock_coordinator, mock_config_entry = mock_coordinator_with_display
        entity = WiiMDisplayLight(mock_coordinator, mock_config_entry)
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on()
        mock_coordinator.player.reset_mock()

        await entity.async_turn_off()

        mock_coordinator.player.set_display_enabled.assert_called_once_with(False)
        assert entity.is_on is False


# ----- async_setup_entry -----


class TestLightSetupEntry:
    """Test light platform async_setup_entry."""

    async def test_setup_adds_only_led_when_no_display_support(
        self, mock_coordinator_setup, mock_config_entry
    ):
        """Test only LED entity is added when supports_display_config is False."""
        mock_coordinator, _ = mock_coordinator_setup
        mock_coordinator.player.supports_display_config = False
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator}}}
        add_entities = MagicMock()

        await async_setup_entry(hass, mock_config_entry, add_entities)

        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], WiiMLEDLight)

    async def test_setup_adds_led_and_display_when_display_supported(
        self, mock_coordinator_setup, mock_config_entry
    ):
        """Test LED and Display entities added when supports_display_config is True."""
        mock_coordinator, _ = mock_coordinator_setup
        mock_coordinator.player.supports_display_config = True
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator}}}
        add_entities = MagicMock()

        await async_setup_entry(hass, mock_config_entry, add_entities)

        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        assert len(entities) == 2
        assert isinstance(entities[0], WiiMLEDLight)
        assert isinstance(entities[1], WiiMDisplayLight)
