"""Unit tests for WiiM number platform."""

from unittest.mock import MagicMock, patch

import pytest


class TestNumberPlatformSetup:
    """Test number platform setup functionality."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_currently_empty(self):
        """Test number platform setup when no number entities are implemented."""
        from custom_components.wiim.number import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()

        # Mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        with patch("custom_components.wiim.number.get_speaker_from_config_entry", return_value=speaker):
            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create no number entities (currently empty implementation)
            assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_async_setup_entry_logging(self):
        """Test number platform setup logging."""
        from custom_components.wiim.number import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()

        # Mock speaker
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        with patch("custom_components.wiim.number.get_speaker_from_config_entry", return_value=speaker):
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify no entities created but setup completed successfully
            async_add_entities.assert_called_once_with([])


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
        from custom_components.wiim.number import WiiMChannelBalance
        from unittest.mock import MagicMock

        mock_speaker = MagicMock()
        mock_speaker.uuid = "test-uuid"
        mock_speaker.name = "Test WiiM"

        entity = WiiMChannelBalance(mock_speaker)

        assert entity.unique_id == "test-uuid_channel_balance"
        assert entity.name == "Channel Balance"
        assert entity.native_min_value == -1.0
        assert entity.native_max_value == 1.0
        assert entity.native_step == 0.1
        assert entity.native_value == 0.0

    def test_channel_balance_native_value(self):
        """Test channel balance native_value property."""
        from custom_components.wiim.number import WiiMChannelBalance
        from unittest.mock import MagicMock

        mock_speaker = MagicMock()
        mock_speaker.uuid = "test-uuid"

        entity = WiiMChannelBalance(mock_speaker)
        entity._balance = 0.5

        assert entity.native_value == 0.5

    @pytest.mark.asyncio
    async def test_channel_balance_set_native_value(self):
        """Test setting channel balance value."""
        from custom_components.wiim.number import WiiMChannelBalance
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_speaker = MagicMock()
        mock_speaker.uuid = "test-uuid"
        mock_speaker.name = "Test WiiM"
        mock_speaker.coordinator = MagicMock()
        mock_speaker.coordinator.player = MagicMock()
        mock_speaker.coordinator.player.set_channel_balance = AsyncMock(return_value=True)

        entity = WiiMChannelBalance(mock_speaker)

        with patch.object(entity, "async_write_ha_state"):
            await entity.async_set_native_value(0.3)

        mock_speaker.coordinator.player.set_channel_balance.assert_called_once_with(0.3)
        assert entity._balance == 0.3

    @pytest.mark.asyncio
    async def test_channel_balance_set_native_value_handles_error(self):
        """Test channel balance handles errors when setting value."""
        from custom_components.wiim.number import WiiMChannelBalance
        from unittest.mock import AsyncMock, MagicMock

        mock_speaker = MagicMock()
        mock_speaker.uuid = "test-uuid"
        mock_speaker.name = "Test WiiM"
        mock_speaker.coordinator = MagicMock()
        mock_speaker.coordinator.player = MagicMock()
        mock_speaker.coordinator.player.set_channel_balance = AsyncMock(side_effect=Exception("Error"))

        entity = WiiMChannelBalance(mock_speaker)

        with pytest.raises(Exception, match="Error"):
            await entity.async_set_native_value(0.3)

    def test_channel_balance_extra_state_attributes(self):
        """Test channel balance extra_state_attributes."""
        from custom_components.wiim.number import WiiMChannelBalance
        from unittest.mock import MagicMock

        mock_speaker = MagicMock()
        mock_speaker.uuid = "test-uuid"

        entity = WiiMChannelBalance(mock_speaker)
        entity._balance = -0.5

        attrs = entity.extra_state_attributes

        assert "channel_balance" in attrs
        assert attrs["channel_balance"] == "-0.5"
        assert "note" in attrs
        assert "warning" in attrs
