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
        from homeassistant.config_entries import ConfigEntry
        from custom_components.wiim.button import WiiMRebootButton

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.name = "Test WiiM"

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-speaker-uuid"
        config_entry.entry_id = "test-entry"

        button = WiiMRebootButton(coordinator, config_entry)

        assert button.coordinator is coordinator
        assert button.unique_id == "test-speaker-uuid_reboot"
        assert button.name == "Reboot"
        assert button.icon == "mdi:restart"

    @pytest.mark.asyncio
    async def test_async_press_reboot_success(self):
        """Test reboot button press with successful API call."""
        from homeassistant.config_entries import ConfigEntry
        from custom_components.wiim.button import WiiMRebootButton

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.name = "Test WiiM"
        coordinator.player.reboot = AsyncMock()

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-speaker-uuid"
        config_entry.entry_id = "test-entry"
        config_entry.title = "Test WiiM"

        button = WiiMRebootButton(coordinator, config_entry)

        await button.async_press()

        coordinator.player.reboot.assert_called_once()
        # No manual refresh - pywiim manages state updates via callbacks

    @pytest.mark.asyncio
    async def test_async_press_reboot_with_error(self):
        """Test reboot button press when API call fails but still succeeds."""
        from homeassistant.config_entries import ConfigEntry
        from custom_components.wiim.button import WiiMRebootButton

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.name = "Test WiiM"
        coordinator.player.reboot = AsyncMock(side_effect=Exception("Connection error"))

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-speaker-uuid"
        config_entry.entry_id = "test-entry"
        config_entry.title = "Test WiiM"

        button = WiiMRebootButton(coordinator, config_entry)

        # Should not raise exception - reboot is considered successful even with errors
        await button.async_press()

        coordinator.player.reboot.assert_called_once()
        # No manual refresh - pywiim manages state updates via callbacks


class TestWiiMSyncTimeButton:
    """Test WiiM Sync Time Button."""

    def test_sync_time_button_creation(self):
        """Test sync time button entity creation."""
        from homeassistant.config_entries import ConfigEntry
        from custom_components.wiim.button import WiiMSyncTimeButton

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.name = "Test WiiM"

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-speaker-uuid"
        config_entry.entry_id = "test-entry"

        button = WiiMSyncTimeButton(coordinator, config_entry)

        assert button.coordinator is coordinator
        assert button.unique_id == "test-speaker-uuid_sync_time"
        assert button.name == "Sync Time"
        assert button.icon == "mdi:clock-sync"

    @pytest.mark.asyncio
    async def test_async_press_sync_time_success(self):
        """Test sync time button press with successful API call."""
        from homeassistant.config_entries import ConfigEntry
        from custom_components.wiim.button import WiiMSyncTimeButton

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.name = "Test WiiM"
        coordinator.player.sync_time = AsyncMock()

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-speaker-uuid"
        config_entry.entry_id = "test-entry"
        config_entry.title = "Test WiiM"

        button = WiiMSyncTimeButton(coordinator, config_entry)

        await button.async_press()

        coordinator.player.sync_time.assert_called_once()
        # No manual refresh - pywiim manages state updates via callbacks

    @pytest.mark.asyncio
    async def test_async_press_sync_time_with_error(self):
        """Test sync time button press when API call fails."""
        from homeassistant.config_entries import ConfigEntry
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError
        from custom_components.wiim.button import WiiMSyncTimeButton

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.name = "Test WiiM"
        coordinator.player.sync_time = AsyncMock(side_effect=WiiMError("Network error"))

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-speaker-uuid"
        config_entry.entry_id = "test-entry"
        config_entry.title = "Test WiiM"

        button = WiiMSyncTimeButton(coordinator, config_entry)

        # Should raise HomeAssistantError for sync time failures (wrapped by wiim_command)
        with pytest.raises(HomeAssistantError):
            await button.async_press()

        coordinator.player.sync_time.assert_called_once()


class TestButtonPlatformSetup:
    """Test button platform setup functionality."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_maintenance_enabled(self):
        """Test button platform setup when maintenance buttons are enabled."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.button import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"
        config_entry.options = {"enable_maintenance_buttons": True}

        # Mock coordinator
        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.name = "Test WiiM"

        # Set up hass.data structure
        hass.data = {DOMAIN: {config_entry.entry_id: {"coordinator": coordinator, "entry": config_entry}}}

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
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.button import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"
        config_entry.options = {"enable_maintenance_buttons": False}

        # Mock coordinator
        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.name = "Test WiiM"

        # Set up hass.data structure
        hass.data = {DOMAIN: {config_entry.entry_id: {"coordinator": coordinator, "entry": config_entry}}}

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
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.button import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"
        config_entry.options = {}

        # Mock coordinator
        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.name = "Test WiiM"

        # Set up hass.data structure
        hass.data = {DOMAIN: {config_entry.entry_id: {"coordinator": coordinator, "entry": config_entry}}}

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
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.button import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"
        config_entry.options = {"enable_maintenance_buttons": True}

        # Mock coordinator
        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.name = "Test WiiM"

        # Set up hass.data structure (direct access pattern)
        hass.data = {DOMAIN: {config_entry.entry_id: {"coordinator": coordinator, "entry": config_entry}}}

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
