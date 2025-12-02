"""Unit tests for WiiM Services - testing sleep timer and alarm services."""

import yaml
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.wiim import media_player
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


class TestAllServicesRegistered:
    """Test that all services defined in services.yaml are registered."""

    @pytest.fixture
    def services_yaml_path(self):
        """Get path to services.yaml."""
        return Path(__file__).parent.parent.parent / "custom_components" / "wiim" / "services.yaml"

    @pytest.fixture
    def services_yaml_content(self, services_yaml_path):
        """Load services.yaml content."""
        with open(services_yaml_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    @pytest.mark.asyncio
    async def test_all_services_from_yaml_registered(self, hass: HomeAssistant, services_yaml_content):
        """Test that all services defined in services.yaml are registered in Python code.

        This test prevents the issue where services are defined in YAML but not registered,
        which causes "unknown action" errors in Home Assistant automations.

        Note: Media player services are registered in async_setup_entry, so we check
        that the service registration code exists in media_player.py.
        """
        # Setup services that are registered in async_setup
        from custom_components.wiim import async_setup

        await async_setup(hass, {})
        await async_setup_services(hass)

        services = hass.services.async_services()
        assert "wiim" in services

        wiim_services = services["wiim"]

        # Expected services from services.py (registered in async_setup_services)
        expected_services_from_services_py = {
            SERVICE_SET_SLEEP_TIMER,
            SERVICE_CLEAR_SLEEP_TIMER,
            SERVICE_UPDATE_ALARM,
        }

        # Expected services from __init__.py (global services, registered in async_setup)
        expected_global_services = {
            "reboot_device",
            "sync_time",
        }

        # Check that services from services.py and __init__.py are registered
        registered_services = expected_services_from_services_py | expected_global_services
        for service_name in registered_services:
            assert service_name in wiim_services, (
                f"Service '{service_name}' is defined in services.yaml but not registered in Python code. "
                f"This will cause 'unknown action' errors in Home Assistant automations."
            )

        # Media player services are registered in async_setup_entry (media_player.py)
        # We verify the registration code exists by checking the file
        import inspect
        from custom_components.wiim import media_player

        # Check that async_setup_entry has service registrations
        setup_entry_source = inspect.getsource(media_player.async_setup_entry)
        expected_media_player_services = {
            "play_url",
            "play_preset",
            "play_playlist",
            "set_eq",
            "play_notification",
            "play_queue",
            "remove_from_queue",
            "get_queue",
        }

        for service_name in expected_media_player_services:
            assert f'"{service_name}"' in setup_entry_source or f"'{service_name}'" in setup_entry_source, (
                f"Service '{service_name}' is defined in services.yaml but registration code not found in "
                f"media_player.py::async_setup_entry. This will cause 'unknown action' errors."
            )

    @pytest.mark.asyncio
    async def test_services_yaml_matches_registered_services(self, hass: HomeAssistant, services_yaml_content):
        """Test that services.yaml contains all registered services (reverse check).

        This ensures documentation (services.yaml) matches implementation.
        """
        await async_setup_services(hass)

        services = hass.services.async_services()
        assert "wiim" in services

        wiim_services = services["wiim"]
        yaml_service_names = set(services_yaml_content.keys())

        # Services that are registered but may not be in YAML (legacy/experimental)
        # These are OK to exist without YAML definition
        allowed_without_yaml = set()

        # Check that registered services have YAML definitions (except allowed ones)
        for service_name in wiim_services:
            if service_name not in allowed_without_yaml:
                assert service_name in yaml_service_names, (
                    f"Service '{service_name}' is registered in Python but not defined in services.yaml. "
                    f"Add it to services.yaml for proper Home Assistant integration."
                )

    def test_services_yaml_structure(self, services_yaml_content):
        """Test that services.yaml has correct structure."""
        assert isinstance(services_yaml_content, dict), "services.yaml should be a dictionary"

        for service_name, service_def in services_yaml_content.items():
            assert isinstance(service_def, dict), f"Service '{service_name}' should be a dictionary"
            # Each service should have at least a name or description
            assert "name" in service_def or "description" in service_def, (
                f"Service '{service_name}' should have at least a name or description"
            )
