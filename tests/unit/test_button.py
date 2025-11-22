"""Unit tests for WiiM button platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestButtonConstants:
    """Test button platform constants."""

    async def test_conf_enable_maintenance_buttons(self):
        """Test maintenance buttons configuration constant."""
        from custom_components.wiim.const import CONF_ENABLE_MAINTENANCE_BUTTONS

        assert CONF_ENABLE_MAINTENANCE_BUTTONS == "enable_maintenance_buttons"


class TestWiiMRebootButton:
    """Test WiiM Reboot Button."""

    def test_reboot_button_creation(self):
        """Test reboot button entity creation."""
        from custom_components.wiim.button import WiiMRebootButton

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        button = WiiMRebootButton(speaker)

        assert button.speaker is speaker
        assert button.unique_id == "test-speaker-uuid_reboot"
        assert button.name == "Reboot"
        assert button.icon == "mdi:restart"

    @pytest.mark.asyncio
    async def test_async_press_reboot_success(self):
        """Test reboot button press with successful API call."""
        from custom_components.wiim.button import WiiMRebootButton

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.reboot = AsyncMock()

        button = WiiMRebootButton(speaker)
        button._async_execute_command_with_refresh = AsyncMock()

        await button.async_press()

        speaker.coordinator.player.reboot.assert_called_once()
        button._async_execute_command_with_refresh.assert_called_once_with("reboot")

    @pytest.mark.asyncio
    async def test_async_press_reboot_with_error(self):
        """Test reboot button press when API call fails but still succeeds."""
        from custom_components.wiim.button import WiiMRebootButton

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.reboot = AsyncMock(side_effect=Exception("Connection error"))

        button = WiiMRebootButton(speaker)
        button._async_execute_command_with_refresh = AsyncMock()

        # Should not raise exception - reboot is considered successful even with errors
        await button.async_press()

        speaker.coordinator.player.reboot.assert_called_once()
        button._async_execute_command_with_refresh.assert_called_once_with("reboot")


class TestWiiMSyncTimeButton:
    """Test WiiM Sync Time Button."""

    def test_sync_time_button_creation(self):
        """Test sync time button entity creation."""
        from custom_components.wiim.button import WiiMSyncTimeButton

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"

        button = WiiMSyncTimeButton(speaker)

        assert button.speaker is speaker
        assert button.unique_id == "test-speaker-uuid_sync_time"
        assert button.name == "Sync Time"
        assert button.icon == "mdi:clock-sync"

    @pytest.mark.asyncio
    async def test_async_press_sync_time_success(self):
        """Test sync time button press with successful API call."""
        from custom_components.wiim.button import WiiMSyncTimeButton

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.sync_time = AsyncMock()

        button = WiiMSyncTimeButton(speaker)
        button._async_execute_command_with_refresh = AsyncMock()

        await button.async_press()

        speaker.coordinator.player.sync_time.assert_called_once()
        button._async_execute_command_with_refresh.assert_called_once_with("sync_time")

    @pytest.mark.asyncio
    async def test_async_press_sync_time_with_error(self):
        """Test sync time button press when API call fails."""
        from custom_components.wiim.button import WiiMSyncTimeButton

        speaker = MagicMock()
        speaker.name = "Test WiiM"
        speaker.uuid = "test-speaker-uuid"
        speaker.coordinator = MagicMock()
        speaker.coordinator.player = MagicMock()
        speaker.coordinator.player.sync_time = AsyncMock(side_effect=Exception("Network error"))

        button = WiiMSyncTimeButton(speaker)
        button._async_execute_command_with_refresh = AsyncMock()

        # Should raise exception for sync time failures
        with pytest.raises(Exception, match="Network error"):
            await button.async_press()

        speaker.coordinator.player.sync_time.assert_called_once()
        button._async_execute_command_with_refresh.assert_not_called()


class TestButtonPlatformSetup:
    """Test button platform setup functionality."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_maintenance_enabled(self):
        """Test button platform setup when maintenance buttons are enabled."""
        from custom_components.wiim.button import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        with patch("custom_components.wiim.button.get_speaker_from_config_entry", return_value=speaker):
            # Mock entry data with maintenance buttons enabled
            hass.data = {"wiim": {"test-entry": {"entry": MagicMock(options={"enable_maintenance_buttons": True})}}}

            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create both reboot and sync time buttons
            assert len(entities) == 2

            entity_names = [entity.__class__.__name__ for entity in entities]
            assert "WiiMRebootButton" in entity_names
            assert "WiiMSyncTimeButton" in entity_names

    @pytest.mark.asyncio
    async def test_async_setup_entry_maintenance_disabled(self):
        """Test button platform setup when maintenance buttons are disabled."""
        from custom_components.wiim.button import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        with patch("custom_components.wiim.button.get_speaker_from_config_entry", return_value=speaker):
            # Mock entry data without maintenance buttons enabled
            hass.data = {"wiim": {"test-entry": {"entry": MagicMock(options={"enable_maintenance_buttons": False})}}}

            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create no buttons
            assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_options(self):
        """Test button platform setup with no options configured."""
        from custom_components.wiim.button import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        with patch("custom_components.wiim.button.get_speaker_from_config_entry", return_value=speaker):
            # Mock entry data with no options
            hass.data = {"wiim": {"test-entry": {"entry": MagicMock(options={})}}}

            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create no buttons
            assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_async_setup_entry_direct_data_access(self):
        """Test button platform setup with direct hass.data access pattern."""
        from custom_components.wiim.button import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        # Mock the direct data access pattern used in the code
        with patch("custom_components.wiim.button.get_speaker_from_config_entry", return_value=speaker):
            # Mock entry data with maintenance buttons enabled (direct access)
            hass.data = {
                "wiim": {
                    "test-entry": {"speaker": speaker, "entry": MagicMock(options={"enable_maintenance_buttons": True})}
                }
            }

            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create both button types
            assert len(entities) == 2

            entity_names = [entity.__class__.__name__ for entity in entities]
            assert "WiiMRebootButton" in entity_names
            assert "WiiMSyncTimeButton" in entity_names
