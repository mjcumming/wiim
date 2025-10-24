"""Unit tests for WiiM number platform."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


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
            entities = []
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
