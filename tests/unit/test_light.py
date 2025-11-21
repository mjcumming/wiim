"""Unit tests for WiiM light platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestWiiMLEDLight:
    """Test WiiM LED Light Entity."""

    async def test_light_creation(self):
        """Test LED light entity creation."""
        from custom_components.wiim.light import WiiMLEDLight

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        light = WiiMLEDLight(speaker)

        assert light.speaker is speaker
        assert light.unique_id == "test-speaker-uuid_led"
        assert light.name == "LED"
        assert light.supported_color_modes == {"brightness"}
        assert light.assumed_state is True  # Optimistic operation

    def test_light_availability(self):
        """Test light availability based on speaker availability."""
        from custom_components.wiim.light import WiiMLEDLight

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.available = True

        light = WiiMLEDLight(speaker)
        assert light.available is True

        # Test unavailable speaker
        speaker.available = False
        assert light.available is False

    def test_light_availability_with_exception(self):
        """Test light availability when coordinator has update failure."""
        from custom_components.wiim.light import WiiMLEDLight

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        # Mock coordinator with failed update
        coordinator = MagicMock()
        coordinator.last_update_success = False
        speaker.coordinator = coordinator

        light = WiiMLEDLight(speaker)
        # The light should be available by default (CoordinatorEntity behavior)
        # This test mainly verifies the entity can be created with failed coordinator
        assert hasattr(light, "available")

    def test_light_is_on_initial_state(self):
        """Test light initial state (assumed)."""
        from custom_components.wiim.light import WiiMLEDLight

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        light = WiiMLEDLight(speaker)
        # Initial state should be None (unknown)
        assert light.is_on is None
        assert light.brightness is None

    def test_light_is_on_after_turn_on(self):
        """Test light state after turning on."""
        from custom_components.wiim.light import WiiMLEDLight

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        light = WiiMLEDLight(speaker)
        light._is_on = True
        light._brightness = 255

        assert light.is_on is True
        assert light.brightness == 255

    def test_light_is_on_after_turn_off(self):
        """Test light state after turning off."""
        from custom_components.wiim.light import WiiMLEDLight

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        light = WiiMLEDLight(speaker)
        light._is_on = False

        assert light.is_on is False

    @pytest.mark.asyncio
    async def test_async_turn_on_full_brightness(self):
        """Test turning on light with full brightness."""
        from custom_components.wiim.light import WiiMLEDLight

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.set_led = AsyncMock()

        light = WiiMLEDLight(speaker)
        light._async_execute_command_with_refresh = AsyncMock()

        # Mock async_write_ha_state to avoid HA context requirement
        with patch.object(light, "async_write_ha_state") as mock_write_state:
            await light.async_turn_on()

            speaker.coordinator.player.set_led.assert_called_once_with(True)
            light._async_execute_command_with_refresh.assert_called_once_with("led_on")
            mock_write_state.assert_called_once()
            assert light._is_on is True
            assert light._brightness == 255

    @pytest.mark.asyncio
    async def test_async_turn_on_with_brightness(self):
        """Test turning on light with custom brightness."""
        from custom_components.wiim.light import WiiMLEDLight

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.set_led = AsyncMock()
        speaker.coordinator.player.set_led_brightness = AsyncMock()

        light = WiiMLEDLight(speaker)
        light._async_execute_command_with_refresh = AsyncMock()

        # Mock async_write_ha_state to avoid HA context requirement
        with patch.object(light, "async_write_ha_state") as mock_write_state:
            # Test with 50% brightness (128/255 ≈ 0.5)
            await light.async_turn_on(brightness=128)

            speaker.coordinator.player.set_led.assert_called_once_with(True)
            speaker.coordinator.player.set_led_brightness.assert_called_once_with(50)  # 128/255 * 100
            light._async_execute_command_with_refresh.assert_called_once_with("led_on")
            mock_write_state.assert_called_once()
            assert light._is_on is True
            assert light._brightness == 128

    @pytest.mark.asyncio
    async def test_async_turn_off(self):
        """Test turning off the light."""
        from custom_components.wiim.light import WiiMLEDLight

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.set_led = AsyncMock()

        light = WiiMLEDLight(speaker)
        light._async_execute_command_with_refresh = AsyncMock()

        # Mock async_write_ha_state to avoid HA context requirement
        with patch.object(light, "async_write_ha_state") as mock_write_state:
            await light.async_turn_off()

            speaker.coordinator.player.set_led.assert_called_once_with(False)
            light._async_execute_command_with_refresh.assert_called_once_with("led_off")
            mock_write_state.assert_called_once()
            assert light._is_on is False

    @pytest.mark.asyncio
    async def test_async_turn_on_error(self):
        """Test turning on light with API error."""
        from custom_components.wiim.light import WiiMLEDLight

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.set_led = AsyncMock(side_effect=Exception("API Error"))

        light = WiiMLEDLight(speaker)
        light._async_execute_command_with_refresh = AsyncMock()

        with pytest.raises(Exception, match="API Error"):
            await light.async_turn_on()

        # State should not be updated on error
        assert light._is_on is None
        assert light._brightness is None

    @pytest.mark.asyncio
    async def test_async_turn_off_error(self):
        """Test turning off light with API error."""
        from custom_components.wiim.light import WiiMLEDLight

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.set_led = AsyncMock(side_effect=Exception("API Error"))

        light = WiiMLEDLight(speaker)
        light._async_execute_command_with_refresh = AsyncMock()

        with pytest.raises(Exception, match="API Error"):
            await light.async_turn_off()

        # State should not be updated on error
        assert light._is_on is None

    @pytest.mark.asyncio
    async def test_async_set_brightness_invalid_values(self):
        """Test setting brightness with invalid values."""
        from custom_components.wiim.light import WiiMLEDLight

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        light = WiiMLEDLight(speaker)

        # Test values outside 0-255 range
        with pytest.raises(ValueError, match="Brightness must be between 0 and 255"):
            await light.async_set_brightness(-1)

        with pytest.raises(ValueError, match="Brightness must be between 0 and 255"):
            await light.async_set_brightness(256)

    @pytest.mark.asyncio
    async def test_async_set_brightness_valid_values(self):
        """Test setting brightness with valid values."""
        from custom_components.wiim.light import WiiMLEDLight

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.set_led = AsyncMock()
        speaker.coordinator.player.set_led_brightness = AsyncMock()

        light = WiiMLEDLight(speaker)
        light._async_execute_command_with_refresh = AsyncMock()

        # Mock async_write_ha_state to avoid HA context requirement
        with patch.object(light, "async_write_ha_state") as mock_write_state:
            # Test 50% brightness
            await light.async_set_brightness(128)

            speaker.coordinator.player.set_led.assert_called_once_with(True)
            speaker.coordinator.player.set_led_brightness.assert_called_once_with(50)  # 128/255 * 100
            light._async_execute_command_with_refresh.assert_called_once_with("led_brightness")
            mock_write_state.assert_called_once()
            assert light._is_on is True
            assert light._brightness == 128

    @pytest.mark.asyncio
    async def test_async_set_brightness_zero(self):
        """Test setting brightness to zero (off)."""
        from custom_components.wiim.light import WiiMLEDLight

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.set_led = AsyncMock()
        speaker.coordinator.player.set_led_brightness = AsyncMock()

        light = WiiMLEDLight(speaker)
        light._async_execute_command_with_refresh = AsyncMock()

        # Mock async_write_ha_state to avoid HA context requirement
        with patch.object(light, "async_write_ha_state") as mock_write_state:
            await light.async_set_brightness(0)

            speaker.coordinator.player.set_led.assert_called_once_with(True)
            speaker.coordinator.player.set_led_brightness.assert_called_once_with(0)
            light._async_execute_command_with_refresh.assert_called_once_with("led_brightness")
            mock_write_state.assert_called_once()
            assert light._is_on is True
            assert light._brightness == 0


class TestLightPlatformSetup:
    """Test light platform setup functionality."""

    @pytest.mark.asyncio
    async def test_async_setup_entry(self):
        """Test light platform setup."""
        from custom_components.wiim.light import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()

        # Mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        with patch("custom_components.wiim.light.get_speaker_from_config_entry", return_value=speaker):
            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create exactly one LED light entity
            assert len(entities) == 1
            assert entities[0].__class__.__name__ == "WiiMLEDLight"
