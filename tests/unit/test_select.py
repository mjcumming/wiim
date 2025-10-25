"""Unit tests for WiiM select platform."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestWiiMOutputModeSelect:
    """Test WiiM Output Mode Select Entity."""

    async def test_select_creation(self):
        """Test select entity creation."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        select = WiiMOutputModeSelect(speaker)

        assert select.speaker is speaker
        assert select.unique_id == "test-speaker-uuid_output_mode"
        assert select.name == "Audio Output Mode"
        assert select.icon == "mdi:audio-video"

    def test_current_option_with_device_communication(self):
        """Test current option when device communication is working."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.get_current_output_mode = MagicMock(return_value="speaker")

        select = WiiMOutputModeSelect(speaker)
        assert select.current_option == "speaker"

    def test_current_option_device_communication_fails(self):
        """Test current option when device communication fails."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator._device_info_working = False

        select = WiiMOutputModeSelect(speaker)
        assert select.current_option is None

    def test_current_option_exception_handling(self):
        """Test current option when get_current_output_mode throws exception."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.get_current_output_mode = MagicMock(side_effect=Exception("Connection error"))

        select = WiiMOutputModeSelect(speaker)
        assert select.current_option is None

    def test_options_with_discovered_modes(self):
        """Test options when discovered modes are available."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.get_output_mode_list = MagicMock(return_value=["speaker", "headphones"])
        speaker.get_discovered_output_modes = MagicMock(return_value=["bluetooth", "usb"])

        select = WiiMOutputModeSelect(speaker)
        options = select.options

        # Should combine and deduplicate modes
        assert len(options) == 4
        assert "speaker" in options
        assert "headphones" in options
        assert "bluetooth" in options
        assert "usb" in options

    def test_options_with_exception(self):
        """Test options when methods throw exceptions."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.get_output_mode_list = MagicMock(side_effect=Exception("API Error"))
        speaker.get_discovered_output_modes = MagicMock(side_effect=Exception("API Error"))

        select = WiiMOutputModeSelect(speaker)
        options = select.options

        # Should return default modes when exceptions occur
        assert len(options) > 0
        assert "Line Out" in options or "Bluetooth Out" in options

    def test_options_fallback_to_defaults(self):
        """Test options fallback to default modes."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.get_output_mode_list = MagicMock(return_value=[])
        speaker.get_discovered_output_modes = MagicMock(return_value=[])

        select = WiiMOutputModeSelect(speaker)
        options = select.options

        # When both methods return empty lists, the result should be an empty sorted list
        assert options == []

    @pytest.mark.asyncio
    async def test_async_select_option_success(self):
        """Test selecting option successfully."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        # Mock the media controller
        with patch("custom_components.wiim.media_controller.MediaPlayerController") as mock_controller_class:
            mock_controller = AsyncMock()
            mock_controller_class.return_value = mock_controller

            select = WiiMOutputModeSelect(speaker)
            await select.async_select_option("bluetooth")

            mock_controller_class.assert_called_once_with(speaker)
            mock_controller.select_output_mode.assert_called_once_with("bluetooth")

    @pytest.mark.asyncio
    async def test_async_select_option_error(self):
        """Test selecting option with error."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        # Mock the media controller to raise an exception
        with patch("custom_components.wiim.media_controller.MediaPlayerController") as mock_controller_class:
            mock_controller = AsyncMock()
            mock_controller.select_output_mode = AsyncMock(side_effect=Exception("API Error"))
            mock_controller_class.return_value = mock_controller

            select = WiiMOutputModeSelect(speaker)

            # Should not raise exception - let Home Assistant handle it
            await select.async_select_option("bluetooth")

            mock_controller_class.assert_called_once_with(speaker)
            mock_controller.select_output_mode.assert_called_once_with("bluetooth")

    def test_extra_state_attributes(self):
        """Test extra state attributes."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.is_bluetooth_output_active = MagicMock(return_value=True)
        speaker.is_audio_cast_active = MagicMock(return_value=False)
        speaker.get_discovered_output_modes = MagicMock(return_value=["usb", "hdmi"])

        select = WiiMOutputModeSelect(speaker)
        attrs = select.extra_state_attributes

        assert attrs["bluetooth_output_active"] is True
        assert attrs["audio_cast_active"] is False
        assert attrs["discovered_modes"] == ["usb", "hdmi"]


class TestSelectPlatformSetup:
    """Test select platform setup functionality."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_capabilities(self):
        """Test select platform setup when device supports audio output."""
        from custom_components.wiim.select import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()

        # Mock speaker with capabilities
        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.coordinator = MagicMock()
        speaker.coordinator.client = MagicMock()
        speaker.coordinator.client.capabilities = {"supports_audio_output": True}

        with patch("custom_components.wiim.select.get_speaker_from_config_entry", return_value=speaker):
            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create output mode select
            assert len(entities) == 1
            assert entities[0].__class__.__name__ == "WiiMOutputModeSelect"

    @pytest.mark.asyncio
    async def test_async_setup_entry_without_capabilities(self):
        """Test select platform setup when device doesn't support audio output."""
        from custom_components.wiim.select import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()

        # Mock speaker without capabilities
        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.coordinator = MagicMock()
        speaker.coordinator.client = MagicMock()
        speaker.coordinator.client.capabilities = {"supports_audio_output": False}

        with patch("custom_components.wiim.select.get_speaker_from_config_entry", return_value=speaker):
            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create no select entities
            assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_capabilities_available(self):
        """Test select platform setup when capabilities are not available (fallback)."""
        from custom_components.wiim.select import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()

        # Mock speaker without capabilities attribute (fallback case)
        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.coordinator = MagicMock()
        speaker.coordinator.client = MagicMock()
        # No capabilities attribute - should create entity as fallback

        with patch("custom_components.wiim.select.get_speaker_from_config_entry", return_value=speaker):
            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create select entity as fallback
            assert len(entities) == 1
            assert entities[0].__class__.__name__ == "WiiMOutputModeSelect"

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_capabilities_attribute_check(self):
        """Test select platform setup with hasattr check for capabilities."""
        from custom_components.wiim.select import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()

        # Mock speaker with capabilities (using hasattr check)
        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.coordinator = MagicMock()
        speaker.coordinator.client = MagicMock()
        # hasattr(speaker.coordinator.client, "capabilities") should return True
        speaker.coordinator.client.capabilities = {"supports_audio_output": True}

        with patch("custom_components.wiim.select.get_speaker_from_config_entry", return_value=speaker):
            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create select entity when capabilities support audio output
            assert len(entities) == 1
            assert entities[0].__class__.__name__ == "WiiMOutputModeSelect"
