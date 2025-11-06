"""Unit tests for WiiM select platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestWiiMOutputModeSelect:
    """Test WiiM Output Mode Select Entity."""

    async def test_select_creation(self, hass):
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

    def test_current_option_with_device_communication(self, hass):
        """Test current option when device communication is working."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.get_current_output_mode = MagicMock(return_value="speaker")

        select = WiiMOutputModeSelect(speaker)
        assert select.current_option == "speaker"

    def test_current_option_device_communication_fails(self, hass):
        """Test current option when device communication fails."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator._device_info_working = False

        select = WiiMOutputModeSelect(speaker)
        assert select.current_option is None

    def test_current_option_exception_handling(self, hass):
        """Test current option when get_current_output_mode throws exception."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.get_current_output_mode = MagicMock(side_effect=Exception("Connection error"))

        select = WiiMOutputModeSelect(speaker)
        assert select.current_option is None

    def test_options_with_discovered_modes(self, hass):
        """Test options when discovered modes are available."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.get_output_mode_list = MagicMock(return_value=["speaker", "headphones"])
        speaker.get_discovered_output_modes = MagicMock(return_value=["usb"])
        speaker.get_bluetooth_history = MagicMock(return_value=[])

        select = WiiMOutputModeSelect(speaker)
        options = select.options

        # Should combine and deduplicate modes (excluding "Bluetooth Out" - replaced by device-specific options)
        assert "speaker" in options
        assert "headphones" in options
        assert "usb" in options
        # "Bluetooth Out" should be excluded (replaced by device-specific options)
        assert "Bluetooth Out" not in options

    def test_options_with_exception(self, hass):
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

    def test_options_fallback_to_defaults(self, hass):
        """Test options fallback to default modes."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.get_output_mode_list = MagicMock(return_value=[])
        speaker.get_discovered_output_modes = MagicMock(return_value=[])
        speaker.get_bluetooth_history = MagicMock(return_value=[])

        select = WiiMOutputModeSelect(speaker)
        options = select.options

        # When all methods return empty lists, should only have "BT Update Paired Devices" option
        # (since we always include the refresh option)
        assert "BT Update Paired Devices" in options
        # Should not have any device-specific options
        assert not any(opt.startswith("BT Device") and " - " in opt for opt in options)

    @pytest.mark.asyncio
    async def test_async_select_option_success(self, hass):
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
    async def test_async_select_option_error(self, hass):
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

    def test_extra_state_attributes(self, hass):
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
    async def test_async_setup_entry_with_capabilities(self, hass):
        """Test select platform setup when device supports audio output."""
        from custom_components.wiim.select import async_setup_entry

        # Mock dependencies
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
    async def test_async_setup_entry_without_capabilities(self, hass):
        """Test select platform setup when device doesn't support audio output."""
        from custom_components.wiim.select import async_setup_entry

        # Mock dependencies
        config_entry = MagicMock()

        # Mock speaker without capabilities
        speaker = MagicMock()
        speaker.name = "Test WiiM"
        # Create coordinator mock with _capabilities attribute
        coordinator = MagicMock()
        coordinator._capabilities = {"supports_audio_output": False}
        coordinator.client = MagicMock()
        coordinator.client.capabilities = {"supports_audio_output": False}
        speaker.coordinator = coordinator

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
    async def test_async_setup_entry_no_capabilities_available(self, hass):
        """Test select platform setup when capabilities are not available (fallback)."""
        from custom_components.wiim.select import async_setup_entry

        # Mock dependencies
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
    async def test_async_setup_entry_with_capabilities_attribute_check(self, hass):
        """Test select platform setup with hasattr check for capabilities."""
        from custom_components.wiim.select import async_setup_entry

        # Mock dependencies
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


class TestWiiMOutputModeSelectBluetoothIntegration:
    """Test Bluetooth device integration in Audio Output Mode select."""

    def test_options_includes_bluetooth_devices_from_history(self, hass):
        """Test that options include Bluetooth devices from history."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.get_output_mode_list = MagicMock(return_value=["Line Out", "Optical Out"])
        speaker.get_discovered_output_modes = MagicMock(return_value=[])
        speaker.get_bluetooth_history = MagicMock(
            return_value=[
                {"name": "TOZO-T6", "ad": "19:12:25:08:0f:b7", "ct": 0, "role": "Audio Sink"},
                {"name": "DELL27KITCHEN", "ad": "ac:5a:fc:02:2c:a8", "ct": 0, "role": "Audio Source"},
            ]
        )

        select = WiiMOutputModeSelect(speaker)
        options = select.options

        # Should include standard modes and BT devices
        assert "Line Out" in options
        assert "Optical Out" in options
        assert "BT Device 1 - TOZO-T6" in options
        assert "BT Device 2 - DELL27KITCHEN" in options
        # Should NOT include "BT Scan" (disabled by default)
        assert "BT Scan" not in options
        # Should NOT include "Bluetooth Out" (replaced by device-specific options)
        assert "Bluetooth Out" not in options

    def test_options_no_bluetooth_devices(self, hass):
        """Test options when no Bluetooth devices are paired."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.get_output_mode_list = MagicMock(return_value=["Line Out", "Optical Out"])
        speaker.get_discovered_output_modes = MagicMock(return_value=[])
        speaker.get_bluetooth_history = MagicMock(return_value=[])

        select = WiiMOutputModeSelect(speaker)
        options = select.options

        # Should only include standard modes
        assert "Line Out" in options
        assert "Optical Out" in options
        # Should not have any BT device options
        assert not any(opt.startswith("BT Device") for opt in options)

    def test_current_option_bluetooth_device(self, hass):
        """Test current_option shows Bluetooth device when BT output is active."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.get_current_output_mode = MagicMock(return_value="Bluetooth Out")
        speaker.is_bluetooth_output_active = MagicMock(return_value=True)
        speaker.get_connected_bluetooth_device = MagicMock(
            return_value={"name": "TOZO-T6", "ad": "19:12:25:08:0f:b7", "mac": "19:12:25:08:0f:b7"}
        )
        speaker.get_bluetooth_history = MagicMock(
            return_value=[
                {"name": "TOZO-T6", "ad": "19:12:25:08:0f:b7", "ct": 1, "role": "Audio Sink"},
                {"name": "DELL27KITCHEN", "ad": "ac:5a:fc:02:2c:a8", "ct": 0, "role": "Audio Source"},
            ]
        )

        select = WiiMOutputModeSelect(speaker)
        current = select.current_option

        # Should show BT device format instead of just "Bluetooth Out"
        assert current == "BT Device 1 - TOZO-T6"

    def test_current_option_regular_mode(self, hass):
        """Test current_option shows regular mode when not Bluetooth."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.get_current_output_mode = MagicMock(return_value="Line Out")
        speaker.is_bluetooth_output_active = MagicMock(return_value=False)

        select = WiiMOutputModeSelect(speaker)
        current = select.current_option

        assert current == "Line Out"

    @pytest.mark.asyncio
    async def test_async_select_option_bluetooth_device(self, hass):
        """Test selecting a Bluetooth device option."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        coordinator = MagicMock()
        coordinator.client = AsyncMock()
        coordinator.client.connect_bluetooth_device = AsyncMock()
        coordinator.async_request_refresh = AsyncMock()
        speaker.coordinator = coordinator

        speaker.get_bluetooth_history = MagicMock(
            return_value=[
                {"name": "TOZO-T6", "ad": "19:12:25:08:0f:b7", "ct": 0, "role": "Audio Sink"},
            ]
        )

        # Mock the media controller
        with patch("custom_components.wiim.media_controller.MediaPlayerController") as mock_controller_class:
            mock_controller = AsyncMock()
            mock_controller_class.return_value = mock_controller

            select = WiiMOutputModeSelect(speaker)
            # Ensure coordinator is accessible
            select.coordinator = coordinator
            await select.async_select_option("BT Device 1 - TOZO-T6")

            # Should connect to Bluetooth device
            coordinator.client.connect_bluetooth_device.assert_called_once_with("19:12:25:08:0f:b7")
            # Should set output mode to Bluetooth
            mock_controller.select_output_mode.assert_called_once_with("Bluetooth Out")
            # Should refresh coordinator
            coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_select_option_bluetooth_device_not_found(self, hass):
        """Test selecting a Bluetooth device that doesn't exist in history."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        coordinator = MagicMock()
        speaker.coordinator = coordinator
        speaker.get_bluetooth_history = MagicMock(return_value=[])
        speaker.get_current_output_mode = MagicMock(return_value="Line Out")

        select = WiiMOutputModeSelect(speaker)
        # Ensure coordinator is accessible from select entity
        select.coordinator = coordinator

        # Should raise ValueError when device not found
        with pytest.raises(ValueError, match="Bluetooth device.*not found in history"):
            await select.async_select_option("BT Device 1 - Unknown Device")

    @pytest.mark.asyncio
    async def test_async_select_option_regular_mode(self, hass):
        """Test selecting a regular output mode (non-Bluetooth)."""
        from custom_components.wiim.select import WiiMOutputModeSelect

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        # Regular mode doesn't need coordinator, but set it up to avoid errors
        coordinator = MagicMock()
        speaker.coordinator = coordinator

        # Mock the media controller
        with patch("custom_components.wiim.media_controller.MediaPlayerController") as mock_controller_class:
            mock_controller = AsyncMock()
            mock_controller_class.return_value = mock_controller

            select = WiiMOutputModeSelect(speaker)
            await select.async_select_option("Line Out")

            # Should call select_output_mode with regular mode
            mock_controller.select_output_mode.assert_called_once_with("Line Out")
