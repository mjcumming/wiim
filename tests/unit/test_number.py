"""Unit tests for WiiM number platform."""

from unittest.mock import MagicMock, patch

import pytest


class TestNumberPlatformSetup:
    """Test number platform setup functionality."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_currently_empty(self):
        """Test number platform setup creates channel balance entity."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.number import WiiMChannelBalance, async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

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

        # Should create 1 number entity (channel balance)
        assert len(entities) == 1
        assert isinstance(entities[0], WiiMChannelBalance)

    @pytest.mark.asyncio
    async def test_async_setup_entry_logging(self):
        """Test number platform setup logging."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.number import WiiMChannelBalance, async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock coordinator
        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.name = "Test WiiM"

        # Set up hass.data structure
        hass.data = {DOMAIN: {config_entry.entry_id: {"coordinator": coordinator, "entry": config_entry}}}

        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        # Verify 1 entity created (channel balance)
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], WiiMChannelBalance)


class TestNumberPlatformConstants:
    """Test number platform constants and configuration."""

    def test_number_platform_import(self):
        """Test that number platform can be imported."""
        from custom_components.wiim import number

        # Should be able to import the module
        assert hasattr(number, "async_setup_entry")
        assert callable(number.async_setup_entry)

    def test_number_platform_ready_for_future_entities(self):
        """Test that number platform is prepared for future number entities."""
        from custom_components.wiim.number import async_setup_entry

        # The setup function exists and is callable
        assert callable(async_setup_entry)

        # The function should handle the case where no entities are created
        # (group volume control is mentioned in comments but not implemented yet)
        pass


class TestWiiMChannelBalance:
    """Test WiiMChannelBalance number entity (even though currently disabled)."""

    def test_channel_balance_initialization(self):
        """Test channel balance entity initialization."""
        from homeassistant.config_entries import ConfigEntry

        from custom_components.wiim.number import WiiMChannelBalance

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.name = "Test WiiM"

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-uuid"
        config_entry.entry_id = "test-entry"

        entity = WiiMChannelBalance(coordinator, config_entry)

        assert entity.unique_id == "test-uuid_channel_balance"
        assert entity.name == "Channel Balance"
        assert entity.native_min_value == -1.0
        assert entity.native_max_value == 1.0
        assert entity.native_step == 0.1
        assert entity.native_value == 0.0

    def test_channel_balance_native_value(self):
        """Test channel balance native_value property."""
        from homeassistant.config_entries import ConfigEntry

        from custom_components.wiim.number import WiiMChannelBalance

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-uuid"
        config_entry.entry_id = "test-entry"

        entity = WiiMChannelBalance(coordinator, config_entry)
        entity._balance = 0.5

        assert entity.native_value == 0.5

    @pytest.mark.asyncio
    async def test_channel_balance_set_native_value(self):
        """Test setting channel balance value."""
        from unittest.mock import AsyncMock

        from homeassistant.config_entries import ConfigEntry

        from custom_components.wiim.number import WiiMChannelBalance

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.name = "Test WiiM"
        coordinator.player.set_channel_balance = AsyncMock(return_value=True)

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-uuid"
        config_entry.entry_id = "test-entry"
        config_entry.title = "Test WiiM"

        entity = WiiMChannelBalance(coordinator, config_entry)

        with patch.object(entity, "async_write_ha_state"):
            await entity.async_set_native_value(0.3)

        coordinator.player.set_channel_balance.assert_called_once_with(0.3)
        assert entity._balance == 0.3

    @pytest.mark.asyncio
    async def test_channel_balance_set_native_value_handles_error(self):
        """Test channel balance handles errors when setting value."""
        from unittest.mock import AsyncMock

        from homeassistant.config_entries import ConfigEntry
        from homeassistant.exceptions import HomeAssistantError
        from pywiim.exceptions import WiiMError

        from custom_components.wiim.number import WiiMChannelBalance

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.name = "Test WiiM"
        coordinator.player.set_channel_balance = AsyncMock(side_effect=WiiMError("Error"))

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-uuid"
        config_entry.entry_id = "test-entry"
        config_entry.title = "Test WiiM"

        entity = WiiMChannelBalance(coordinator, config_entry)

        with pytest.raises(HomeAssistantError):
            await entity.async_set_native_value(0.3)

    def test_channel_balance_extra_state_attributes(self):
        """Test channel balance extra_state_attributes."""
        from homeassistant.config_entries import ConfigEntry

        from custom_components.wiim.number import WiiMChannelBalance

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"

        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.unique_id = "test-uuid"
        config_entry.entry_id = "test-entry"

        entity = WiiMChannelBalance(coordinator, config_entry)
        entity._balance = -0.5

        attrs = entity.extra_state_attributes

        assert "channel_balance" in attrs
        assert attrs["channel_balance"] == "-0.5"
        assert "note" in attrs
        assert "warning" in attrs
