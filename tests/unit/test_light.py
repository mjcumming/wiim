"""Unit tests for WiiM Light Entity - testing LED control functionality."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode
from homeassistant.config_entries import ConfigEntry

from custom_components.wiim.data import Speaker
from custom_components.wiim.light import WiiMLEDLight


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
    coordinator.player.set_led_brightness = AsyncMock(return_value=True)
    return coordinator


@pytest.fixture
def mock_speaker(mock_coordinator, mock_config_entry):
    """Create a mock speaker."""
    speaker = MagicMock(spec=Speaker)
    speaker.coordinator = mock_coordinator
    speaker.config_entry = mock_config_entry
    speaker.uuid = "test-uuid"
    speaker.name = "Test WiiM"
    speaker.available = True
    speaker.model = "WiiM Mini"
    speaker.firmware = "1.0.0"
    speaker.role = "solo"
    speaker.ip_address = "192.168.1.100"
    speaker.mac_address = "AA:BB:CC:DD:EE:FF"
    speaker.input_list = ["spotify", "bluetooth"]
    speaker.device_model = None
    return speaker


class TestWiiMLEDLightBasic:
    """Test basic LED light functionality."""

    def test_initialization(self, mock_speaker):
        """Test LED light initialization."""
        entity = WiiMLEDLight(mock_speaker)
        assert entity.unique_id == "test-uuid_led"
        assert entity.name == "LED"
        assert entity.speaker == mock_speaker

    def test_supported_color_modes(self, mock_speaker):
        """Test supported color modes."""
        entity = WiiMLEDLight(mock_speaker)
        assert entity.supported_color_modes == {ColorMode.BRIGHTNESS}

    def test_has_entity_name(self, mock_speaker):
        """Test has_entity_name property."""
        entity = WiiMLEDLight(mock_speaker)
        assert entity._attr_has_entity_name is True

    def test_assumed_state(self, mock_speaker):
        """Test assumed_state property."""
        entity = WiiMLEDLight(mock_speaker)
        assert entity._attr_assumed_state is True

    def test_available_mirrors_speaker(self, mock_speaker):
        """Test availability mirrors speaker availability."""
        mock_speaker.available = True
        entity = WiiMLEDLight(mock_speaker)
        assert entity.available is True

        mock_speaker.available = False
        entity = WiiMLEDLight(mock_speaker)
        assert entity.available is False

    def test_is_on_initial_state(self, mock_speaker):
        """Test initial is_on state."""
        entity = WiiMLEDLight(mock_speaker)
        assert entity.is_on is None  # Optimistic state starts as None

    def test_brightness_initial_state(self, mock_speaker):
        """Test initial brightness state."""
        entity = WiiMLEDLight(mock_speaker)
        assert entity.brightness is None  # Optimistic state starts as None


class TestWiiMLEDLightTurnOn:
    """Test LED turn on functionality."""

    async def test_turn_on_default_brightness(self, mock_speaker, mock_coordinator):
        """Test turn on with default brightness (100%)."""
        entity = WiiMLEDLight(mock_speaker)
        # Mock the async_write_ha_state method
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on()

        # Should set LED on and brightness to 100%
        mock_coordinator.player.set_led.assert_called_once_with(True)
        # Brightness 100% should not call set_led_brightness (optimization)
        mock_coordinator.player.set_led_brightness.assert_not_called()

        # Optimistic state should be updated
        assert entity.is_on is True
        assert entity.brightness == 255
        # Should call async_request_refresh via _async_execute_command_with_refresh
        mock_coordinator.async_request_refresh.assert_called_once()

    async def test_turn_on_with_brightness(self, mock_speaker, mock_coordinator):
        """Test turn on with specific brightness."""
        entity = WiiMLEDLight(mock_speaker)
        entity.async_write_ha_state = MagicMock()

        # Brightness 128 (50%)
        await entity.async_turn_on(**{ATTR_BRIGHTNESS: 128})

        # Should set LED on and brightness to 50%
        mock_coordinator.player.set_led.assert_called_once_with(True)
        mock_coordinator.player.set_led_brightness.assert_called_once_with(50)

        # Optimistic state should be updated
        assert entity.is_on is True
        assert entity.brightness == 128
        mock_coordinator.async_request_refresh.assert_called_once()

    async def test_turn_on_brightness_conversion(self, mock_speaker, mock_coordinator):
        """Test brightness conversion from 0-255 to 0-100%."""
        entity = WiiMLEDLight(mock_speaker)
        entity.async_write_ha_state = MagicMock()

        # Test various brightness values
        test_cases = [
            (0, 0),  # 0% brightness
            (64, 25),  # 25% brightness
            (128, 50),  # 50% brightness
            (192, 75),  # 75% brightness
            (255, 100),  # 100% brightness
        ]

        for brightness_255, expected_pct in test_cases:
            mock_coordinator.player.set_led.reset_mock()
            mock_coordinator.player.set_led_brightness.reset_mock()
            mock_coordinator.async_request_refresh.reset_mock()

            await entity.async_turn_on(**{ATTR_BRIGHTNESS: brightness_255})

            if expected_pct != 100:
                mock_coordinator.player.set_led_brightness.assert_called_once_with(expected_pct)
            else:
                # 100% should not call set_led_brightness
                mock_coordinator.player.set_led_brightness.assert_not_called()
            mock_coordinator.async_request_refresh.assert_called_once()

    async def test_turn_on_handles_error(self, mock_speaker, mock_coordinator):
        """Test turn on handles errors."""
        mock_coordinator.player.set_led.side_effect = Exception("LED error")

        entity = WiiMLEDLight(mock_speaker)

        with pytest.raises(Exception, match="LED error"):
            await entity.async_turn_on()

        # Optimistic state should not be updated on error
        assert entity.is_on is None


class TestWiiMLEDLightTurnOff:
    """Test LED turn off functionality."""

    async def test_turn_off(self, mock_speaker, mock_coordinator):
        """Test turn off LED."""
        entity = WiiMLEDLight(mock_speaker)
        entity.async_write_ha_state = MagicMock()

        # First turn on
        await entity.async_turn_on()
        assert entity.is_on is True
        mock_coordinator.async_request_refresh.reset_mock()

        # Then turn off
        await entity.async_turn_off()

        mock_coordinator.player.set_led.assert_called_with(False)

        # Optimistic state should be updated
        assert entity.is_on is False
        mock_coordinator.async_request_refresh.assert_called_once()

    async def test_turn_off_handles_error(self, mock_speaker, mock_coordinator):
        """Test turn off handles errors."""
        mock_coordinator.player.set_led.side_effect = Exception("LED error")

        entity = WiiMLEDLight(mock_speaker)

        with pytest.raises(Exception, match="LED error"):
            await entity.async_turn_off()


class TestWiiMLEDLightSetBrightness:
    """Test LED brightness control."""

    async def test_set_brightness(self, mock_speaker, mock_coordinator):
        """Test setting brightness directly."""
        entity = WiiMLEDLight(mock_speaker)
        entity.async_write_ha_state = MagicMock()

        await entity.async_set_brightness(128)

        # Should set LED on first, then brightness
        mock_coordinator.player.set_led.assert_called_once_with(True)
        mock_coordinator.player.set_led_brightness.assert_called_once_with(50)

        # Optimistic state should be updated
        assert entity.is_on is True
        assert entity.brightness == 128
        mock_coordinator.async_request_refresh.assert_called_once()

    async def test_set_brightness_validation(self, mock_speaker):
        """Test brightness validation."""
        entity = WiiMLEDLight(mock_speaker)

        # Test invalid values
        with pytest.raises(ValueError, match="Brightness must be between 0 and 255"):
            await entity.async_set_brightness(-1)

        with pytest.raises(ValueError, match="Brightness must be between 0 and 255"):
            await entity.async_set_brightness(256)

    async def test_set_brightness_handles_error(self, mock_speaker, mock_coordinator):
        """Test set brightness handles errors."""
        mock_coordinator.player.set_led.side_effect = Exception("LED error")

        entity = WiiMLEDLight(mock_speaker)

        with pytest.raises(Exception, match="LED error"):
            await entity.async_set_brightness(128)


class TestWiiMLEDLightStateUpdates:
    """Test LED optimistic state updates."""

    async def test_state_update_on_turn_on(self, mock_speaker, mock_coordinator):
        """Test state update when turning on."""
        entity = WiiMLEDLight(mock_speaker)
        entity.async_write_ha_state = MagicMock()

        # Initially None
        assert entity.is_on is None
        assert entity.brightness is None

        # Turn on
        await entity.async_turn_on()

        # Should be updated
        assert entity.is_on is True
        assert entity.brightness == 255

    async def test_state_update_on_turn_off(self, mock_speaker, mock_coordinator):
        """Test state update when turning off."""
        entity = WiiMLEDLight(mock_speaker)
        entity.async_write_ha_state = MagicMock()

        # Turn on first
        await entity.async_turn_on()
        assert entity.is_on is True
        mock_coordinator.async_request_refresh.reset_mock()

        # Turn off
        await entity.async_turn_off()

        # Should be updated
        assert entity.is_on is False
        # Brightness should remain (optimistic state)
        assert entity.brightness == 255

    async def test_state_update_on_brightness_change(self, mock_speaker, mock_coordinator):
        """Test state update when changing brightness."""
        entity = WiiMLEDLight(mock_speaker)
        entity.async_write_ha_state = MagicMock()

        # Turn on
        await entity.async_turn_on()
        assert entity.brightness == 255
        mock_coordinator.async_request_refresh.reset_mock()

        # Change brightness
        await entity.async_set_brightness(128)

        # Should be updated
        assert entity.brightness == 128
        assert entity.is_on is True
