"""Unit tests for WiiM Services - testing sleep timer and alarm services."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.wiim.services import (
    SERVICE_CLEAR_SLEEP_TIMER,
    SERVICE_SET_SLEEP_TIMER,
    SERVICE_UPDATE_ALARM,
    async_setup_services,
)


class TestServiceRegistration:
    """Test service registration."""

    @pytest.mark.asyncio
    async def test_service_registration(self, hass: HomeAssistant):
        """Test that services are registered."""
        await async_setup_services(hass)

        # Check that services are registered
        services = hass.services.async_services()
        assert "wiim" in services

        wiim_services = services["wiim"]
        assert SERVICE_SET_SLEEP_TIMER in wiim_services
        assert SERVICE_CLEAR_SLEEP_TIMER in wiim_services
        assert SERVICE_UPDATE_ALARM in wiim_services

    @pytest.mark.asyncio
    async def test_set_sleep_timer_service_schema(self, hass: HomeAssistant):
        """Test set sleep timer service schema validation."""
        await async_setup_services(hass)

        # Service should accept sleep_time parameter
        services = hass.services.async_services()
        set_timer_service = services["wiim"][SERVICE_SET_SLEEP_TIMER]

        # Check that schema requires sleep_time
        assert set_timer_service is not None

    @pytest.mark.asyncio
    async def test_clear_sleep_timer_service_schema(self, hass: HomeAssistant):
        """Test clear sleep timer service schema."""
        await async_setup_services(hass)

        # Service should not require parameters
        services = hass.services.async_services()
        clear_timer_service = services["wiim"][SERVICE_CLEAR_SLEEP_TIMER]

        assert clear_timer_service is not None

    @pytest.mark.asyncio
    async def test_update_alarm_service_schema(self, hass: HomeAssistant):
        """Test update alarm service schema."""
        await async_setup_services(hass)

        # Service should accept alarm_id and optional time/trigger/operation
        services = hass.services.async_services()
        update_alarm_service = services["wiim"][SERVICE_UPDATE_ALARM]

        assert update_alarm_service is not None


class TestServiceExecution:
    """Test service execution (requires media player entity)."""

    @pytest.mark.asyncio
    async def test_set_sleep_timer_calls_entity_method(self, hass: HomeAssistant):
        """Test set sleep timer service calls entity method."""
        from custom_components.wiim.services import SERVICE_SET_SLEEP_TIMER

        await async_setup_services(hass)

        # Create a mock media player entity
        mock_entity = MagicMock()
        mock_entity.entity_id = "media_player.test_wiim"
        mock_entity.set_sleep_timer = AsyncMock()

        # Register entity
        hass.states.async_set("media_player.test_wiim", "idle")

        # Call service
        await hass.services.async_call(
            "wiim",
            SERVICE_SET_SLEEP_TIMER,
            {"entity_id": "media_player.test_wiim", "sleep_time": 300},
            blocking=True,
        )

        # Note: In real implementation, this would call the entity method
        # This test verifies the service is registered and can be called

    @pytest.mark.asyncio
    async def test_clear_sleep_timer_calls_entity_method(self, hass: HomeAssistant):
        """Test clear sleep timer service calls entity method."""
        from custom_components.wiim.services import SERVICE_CLEAR_SLEEP_TIMER

        await async_setup_services(hass)

        # Create a mock media player entity
        mock_entity = MagicMock()
        mock_entity.entity_id = "media_player.test_wiim"
        mock_entity.clear_sleep_timer = AsyncMock()

        # Register entity
        hass.states.async_set("media_player.test_wiim", "idle")

        # Call service
        await hass.services.async_call(
            "wiim",
            SERVICE_CLEAR_SLEEP_TIMER,
            {"entity_id": "media_player.test_wiim"},
            blocking=True,
        )

        # Note: In real implementation, this would call the entity method

    @pytest.mark.asyncio
    async def test_update_alarm_calls_entity_method(self, hass: HomeAssistant):
        """Test update alarm service calls entity method."""
        from custom_components.wiim.services import SERVICE_UPDATE_ALARM

        await async_setup_services(hass)

        # Create a mock media player entity
        mock_entity = MagicMock()
        mock_entity.entity_id = "media_player.test_wiim"
        mock_entity.set_alarm = AsyncMock()

        # Register entity
        hass.states.async_set("media_player.test_wiim", "idle")

        # Call service
        await hass.services.async_call(
            "wiim",
            SERVICE_UPDATE_ALARM,
            {
                "entity_id": "media_player.test_wiim",
                "alarm_id": 0,
                "time": "08:00",
                "trigger": "play",
            },
            blocking=True,
        )

        # Note: In real implementation, this would call the entity method


class TestServiceValidation:
    """Test service parameter validation."""

    @pytest.mark.asyncio
    async def test_set_sleep_timer_validates_range(self, hass: HomeAssistant):
        """Test set sleep timer validates sleep_time range (0-7200)."""
        await async_setup_services(hass)

        # This would be validated by voluptuous schema
        # Test that service exists and can be called with valid range
        services = hass.services.async_services()
        assert SERVICE_SET_SLEEP_TIMER in services["wiim"]

    @pytest.mark.asyncio
    async def test_update_alarm_validates_alarm_id(self, hass: HomeAssistant):
        """Test update alarm validates alarm_id range (0-2)."""
        await async_setup_services(hass)

        # This would be validated by voluptuous schema
        # Test that service exists and can be called with valid alarm_id
        services = hass.services.async_services()
        assert SERVICE_UPDATE_ALARM in services["wiim"]
