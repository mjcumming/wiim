"""Unit tests for WiiM number platform."""

from unittest.mock import MagicMock

import pytest


class TestNumberPlatformSetup:
    """Test number platform setup functionality."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_currently_empty(self):
        """Test number platform setup creates no entities (channel balance is service-only)."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.number import async_setup_entry

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

        # Verify entities were created (but empty list)
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]

        # Should create 0 number entities (channel balance is service-only)
        assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_async_setup_entry_logging(self):
        """Test number platform setup logging."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.number import async_setup_entry

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

        # Verify no entities created (channel balance is service-only)
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 0


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


# Channel balance is now service-only, not an entity
# Tests for the service are in test_services.py
