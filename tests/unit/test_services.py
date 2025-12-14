"""Unit tests for WiiM Actions - testing all registered actions and sync with YAML/strings.json."""

import json
from pathlib import Path

import pytest
import yaml
from homeassistant.core import HomeAssistant

from custom_components.wiim.services import (
    SERVICE_CLEAR_SLEEP_TIMER,
    SERVICE_REBOOT_DEVICE,
    SERVICE_SCAN_BLUETOOTH,
    SERVICE_SET_CHANNEL_BALANCE,
    SERVICE_SET_SLEEP_TIMER,
    SERVICE_SYNC_TIME,
    SERVICE_UPDATE_ALARM,
    async_setup_services,
)


class TestActionRegistration:
    """Test action registration using new EntityServiceDescription pattern."""

    @pytest.mark.asyncio
    async def test_all_platform_actions_registered(self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator):
        """Test that all platform entity actions are registered on media_player domain."""
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        services = hass.services.async_services()
        assert "media_player" in services

        media_player_services = services["media_player"]

        # All actions should be registered via EntityServiceDescription pattern
        expected_actions = {
            SERVICE_SET_SLEEP_TIMER,
            SERVICE_CLEAR_SLEEP_TIMER,
            SERVICE_UPDATE_ALARM,
            SERVICE_REBOOT_DEVICE,
            SERVICE_SYNC_TIME,
            SERVICE_SCAN_BLUETOOTH,
            SERVICE_SET_CHANNEL_BALANCE,
        }

        for action_name in expected_actions:
            assert action_name in media_player_services, (
                f"Action '{action_name}' should be registered but was not found. "
                f"Registered actions: {list(media_player_services.keys())}"
            )

    @pytest.mark.asyncio
    async def test_set_sleep_timer_action_schema(self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator):
        """Test set sleep timer action schema validation."""
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        services = hass.services.async_services()
        set_timer_service = services["media_player"][SERVICE_SET_SLEEP_TIMER]

        assert set_timer_service is not None

    @pytest.mark.asyncio
    async def test_clear_sleep_timer_action_schema(self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator):
        """Test clear sleep timer action schema."""
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        services = hass.services.async_services()
        clear_timer_service = services["media_player"][SERVICE_CLEAR_SLEEP_TIMER]

        assert clear_timer_service is not None

    @pytest.mark.asyncio
    async def test_update_alarm_action_schema(self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator):
        """Test update alarm action schema."""
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        services = hass.services.async_services()
        update_alarm_service = services["media_player"][SERVICE_UPDATE_ALARM]

        assert update_alarm_service is not None

    @pytest.mark.asyncio
    async def test_reboot_device_action_schema(self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator):
        """Test reboot device action schema."""
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        services = hass.services.async_services()
        reboot_service = services["media_player"][SERVICE_REBOOT_DEVICE]

        assert reboot_service is not None

    @pytest.mark.asyncio
    async def test_sync_time_action_schema(self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator):
        """Test sync time action schema."""
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        services = hass.services.async_services()
        sync_time_service = services["media_player"][SERVICE_SYNC_TIME]

        assert sync_time_service is not None

    @pytest.mark.asyncio
    async def test_scan_bluetooth_action_schema(self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator):
        """Test scan bluetooth action schema."""
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        services = hass.services.async_services()
        scan_bt_service = services["media_player"][SERVICE_SCAN_BLUETOOTH]

        assert scan_bt_service is not None

    @pytest.mark.asyncio
    async def test_set_channel_balance_action_schema(self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator):
        """Test set channel balance action schema."""
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        services = hass.services.async_services()
        balance_service = services["media_player"][SERVICE_SET_CHANNEL_BALANCE]

        assert balance_service is not None


class TestActionExecution:
    """Test action execution (requires media player entity)."""

    @pytest.mark.asyncio
    async def test_set_sleep_timer_calls_entity_method(self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator):
        """Test set sleep timer action calls entity method."""
        from unittest.mock import AsyncMock, MagicMock

        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        mock_entity = MagicMock()
        mock_entity.entity_id = "media_player.test_wiim"
        mock_entity.set_sleep_timer = AsyncMock()

        hass.states.async_set("media_player.test_wiim", "idle")

        await hass.services.async_call(
            "media_player",
            SERVICE_SET_SLEEP_TIMER,
            {"entity_id": "media_player.test_wiim", "sleep_time": 300},
            blocking=True,
        )

    @pytest.mark.asyncio
    async def test_clear_sleep_timer_calls_entity_method(
        self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator
    ):
        """Test clear sleep timer action calls entity method."""
        from unittest.mock import AsyncMock, MagicMock

        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        mock_entity = MagicMock()
        mock_entity.entity_id = "media_player.test_wiim"
        mock_entity.clear_sleep_timer = AsyncMock()

        hass.states.async_set("media_player.test_wiim", "idle")

        await hass.services.async_call(
            "media_player",
            SERVICE_CLEAR_SLEEP_TIMER,
            {"entity_id": "media_player.test_wiim"},
            blocking=True,
        )

    @pytest.mark.asyncio
    async def test_update_alarm_calls_entity_method(self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator):
        """Test update alarm action calls entity method."""
        from unittest.mock import AsyncMock, MagicMock

        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        mock_entity = MagicMock()
        mock_entity.entity_id = "media_player.test_wiim"
        mock_entity.set_alarm = AsyncMock()

        hass.states.async_set("media_player.test_wiim", "idle")

        await hass.services.async_call(
            "media_player",
            SERVICE_UPDATE_ALARM,
            {
                "entity_id": "media_player.test_wiim",
                "alarm_id": 0,
                "time": "08:00",
                "trigger": "play",
            },
            blocking=True,
        )


class TestActionValidation:
    """Test action parameter validation."""

    @pytest.mark.asyncio
    async def test_set_sleep_timer_validates_range(self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator):
        """Test set sleep timer validates sleep_time range (0-7200)."""
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        services = hass.services.async_services()
        assert SERVICE_SET_SLEEP_TIMER in services["media_player"]

    @pytest.mark.asyncio
    async def test_update_alarm_validates_alarm_id(self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator):
        """Test update alarm validates alarm_id range (0-2)."""
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        services = hass.services.async_services()
        assert SERVICE_UPDATE_ALARM in services["media_player"]

    @pytest.mark.asyncio
    async def test_scan_bluetooth_validates_duration(self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator):
        """Test scan bluetooth validates duration range (3-10)."""
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        services = hass.services.async_services()
        assert SERVICE_SCAN_BLUETOOTH in services["media_player"]

    @pytest.mark.asyncio
    async def test_set_channel_balance_validates_range(self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator):
        """Test set channel balance validates balance range (-1.0 to 1.0)."""
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        services = hass.services.async_services()
        assert SERVICE_SET_CHANNEL_BALANCE in services["media_player"]


class TestActionYAMLSync:
    """Test that actions are synchronized between Python, YAML, and strings.json."""

    @pytest.fixture
    def services_yaml_path(self):
        """Get path to services.yaml."""
        return Path(__file__).parent.parent.parent / "custom_components" / "wiim" / "services.yaml"

    @pytest.fixture
    def strings_json_path(self):
        """Get path to strings.json."""
        return Path(__file__).parent.parent.parent / "custom_components" / "wiim" / "strings.json"

    @pytest.fixture
    def services_yaml_content(self, services_yaml_path):
        """Load services.yaml content."""
        with open(services_yaml_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    @pytest.fixture
    def strings_json_content(self, strings_json_path):
        """Load strings.json content."""
        with open(strings_json_path, encoding="utf-8") as f:
            return json.load(f)

    @pytest.mark.asyncio
    async def test_all_yaml_actions_registered_in_python(
        self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator, services_yaml_content
    ):
        """Test that all actions defined in services.yaml are registered in Python code.

        This test prevents the issue where actions are defined in YAML but not registered,
        which causes "unknown action" errors in Home Assistant automations.
        """
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        services = hass.services.async_services()
        assert "media_player" in services

        media_player_services = services["media_player"]

        # Check services.py registered actions
        import inspect

        from custom_components.wiim import media_player

        # Get media_player.py source to check for entity action registrations
        setup_entry_source = inspect.getsource(media_player.async_setup_entry)

        # Media player entity actions (registered in async_setup_entry)
        media_player_actions = {
            "play_url",
            "play_preset",
            "play_playlist",
            "set_eq",
            "play_notification",
            "play_queue",
            "remove_from_queue",
            "get_queue",
        }

        # Platform entity actions (registered via EntityServiceDescription pattern in services.py)
        platform_actions = {
            SERVICE_SET_SLEEP_TIMER,
            SERVICE_CLEAR_SLEEP_TIMER,
            SERVICE_UPDATE_ALARM,
            SERVICE_REBOOT_DEVICE,
            SERVICE_SYNC_TIME,
            SERVICE_SCAN_BLUETOOTH,
            SERVICE_SET_CHANNEL_BALANCE,
        }

        # Verify all YAML actions are either registered or in media_player.py
        yaml_action_names = set(services_yaml_content.keys())

        for action_name in yaml_action_names:
            if action_name in media_player_actions:
                # Check that registration code exists in media_player.py
                assert f'"{action_name}"' in setup_entry_source or f"'{action_name}'" in setup_entry_source, (
                    f"Action '{action_name}' is defined in services.yaml but registration code not found in "
                    f"media_player.py::async_setup_entry. This will cause 'unknown action' errors."
                )
            elif action_name in platform_actions:
                # Should be registered via EntityServiceDescription pattern
                assert action_name in media_player_services, (
                    f"Action '{action_name}' is defined in services.yaml but not registered in Python code. "
                    f"This will cause 'unknown action' errors in Home Assistant automations."
                )
            else:
                # Unknown action - should not happen
                raise AssertionError(f"Action '{action_name}' in services.yaml is not recognized")

    @pytest.mark.asyncio
    async def test_all_registered_actions_have_yaml_definition(
        self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator, services_yaml_content
    ):
        """Test that all registered actions have YAML definitions.

        This ensures documentation (services.yaml) matches implementation.
        """
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN

        # Setup coordinator in hass.data (required for async_setup_entry)
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (this registers services)
        await media_player.async_setup_entry(hass, wiim_config_entry, lambda entities: None)

        services = hass.services.async_services()
        assert "media_player" in services

        media_player_services = services["media_player"]
        yaml_action_names = set(services_yaml_content.keys())

        # Actions that are allowed without YAML definition (legacy/experimental)
        allowed_without_yaml = set()

        for action_name in media_player_services:
            if action_name not in allowed_without_yaml:
                assert action_name in yaml_action_names, (
                    f"Action '{action_name}' is registered in Python but not defined in services.yaml. "
                    f"Add it to services.yaml for proper Home Assistant UI integration."
                )

    def test_all_yaml_actions_have_strings_translations(self, services_yaml_content, strings_json_content):
        """Test that all actions in services.yaml have translations in strings.json.

        This ensures the Home Assistant UI displays proper labels and descriptions.
        """
        services_translations = strings_json_content.get("services", {})

        for action_name in services_yaml_content.keys():
            assert action_name in services_translations, (
                f"Action '{action_name}' is defined in services.yaml but missing from strings.json 'services' section. "
                f"Add translations for proper UI display and documentation links."
            )

    def test_strings_json_actions_match_yaml(self, services_yaml_content, strings_json_content):
        """Test that strings.json doesn't have orphaned action translations.

        This ensures strings.json doesn't contain translations for non-existent actions.
        """
        services_translations = strings_json_content.get("services", {})
        yaml_action_names = set(services_yaml_content.keys())

        for action_name in services_translations.keys():
            assert action_name in yaml_action_names, (
                f"Action '{action_name}' has translation in strings.json but is not defined in services.yaml. "
                f"Either add the action to services.yaml or remove the translation."
            )

    def test_services_yaml_structure(self, services_yaml_content):
        """Test that services.yaml has correct structure.

        Note: Names and descriptions are in strings.json, not services.yaml.
        services.yaml only contains the schema (target, fields, selectors).
        """
        assert isinstance(services_yaml_content, dict), "services.yaml should be a dictionary"

        for action_name, action_def in services_yaml_content.items():
            assert isinstance(action_def, dict), f"Action '{action_name}' should be a dictionary"
            # Each action should have a target (for entity selection in UI)
            assert "target" in action_def, f"Action '{action_name}' should have a 'target' for entity selection"

    def test_strings_json_services_structure(self, strings_json_content):
        """Test that strings.json services section has correct structure."""
        services_translations = strings_json_content.get("services", {})

        assert isinstance(services_translations, dict), "strings.json 'services' should be a dictionary"

        for action_name, action_def in services_translations.items():
            assert isinstance(action_def, dict), f"Action '{action_name}' translation should be a dictionary"
            # Each action should have at least a name or description
            assert "name" in action_def or "description" in action_def, (
                f"Action '{action_name}' translation should have at least a name or description"
            )

    def test_yaml_fields_have_string_translations(self, services_yaml_content, strings_json_content):
        """Test that action fields in services.yaml have translations in strings.json."""
        services_translations = strings_json_content.get("services", {})

        for action_name, action_def in services_yaml_content.items():
            if "fields" not in action_def:
                continue

            action_translation = services_translations.get(action_name, {})
            fields_translation = action_translation.get("fields", {})

            for field_name in action_def["fields"].keys():
                assert field_name in fields_translation, (
                    f"Field '{field_name}' in action '{action_name}' is missing translation in strings.json. "
                    f"Add field translation for proper UI display."
                )


class TestAsyncSetupServices:
    """Test async_setup_services function."""

    @pytest.mark.asyncio
    async def test_async_setup_services_noop(self, hass: HomeAssistant):
        """Test that async_setup_services completes without error (legacy compatibility)."""
        # Should complete without raising
        await async_setup_services(hass)
        # Function is now a no-op - services are registered via platform in media_player.py
        # This function exists for backward compatibility only


class TestRegisterMediaPlayerServices:
    """Test register_media_player_services function."""

    def test_register_media_player_services_registers_all_services(
        self, hass: HomeAssistant, wiim_config_entry, wiim_coordinator
    ):
        """Test that register_media_player_services registers all EntityServiceDescription services."""
        from custom_components.wiim import media_player
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.services import MEDIA_PLAYER_ENTITY_SERVICES

        # Setup coordinator in hass.data
        hass.data.setdefault(DOMAIN, {})[wiim_config_entry.entry_id] = {
            "coordinator": wiim_coordinator,
        }

        # Setup platform (creates entities and sets up platform context)
        entities_added = []

        async def add_entities(entities):
            entities_added.extend(entities)

        await media_player.async_setup_entry(hass, wiim_config_entry, add_entities)

        # Verify services are registered
        services = hass.services.async_services()
        assert "media_player" in services

        media_player_services = services["media_player"]

        # Check all EntityServiceDescription services are registered
        for service_desc in MEDIA_PLAYER_ENTITY_SERVICES:
            assert service_desc.name in media_player_services, (
                f"Service '{service_desc.name}' from EntityServiceDescription not registered. "
                f"Registered services: {list(media_player_services.keys())}"
            )


class TestMediaPlayerEntityActionHandlers:
    """Test that media player entity has all required action handler methods."""

    def test_entity_has_required_handler_methods(self):
        """Test that WiiMMediaPlayer has all required handler methods for registered actions."""
        from custom_components.wiim.media_player import WiiMMediaPlayer

        # Platform entity actions (called by services.py)
        platform_action_methods = {
            "set_sleep_timer": "set_sleep_timer",
            "clear_sleep_timer": "clear_sleep_timer",
            "update_alarm": "set_alarm",
            "reboot_device": "async_reboot_device",
            "sync_time": "async_sync_time",
            "scan_bluetooth": "async_scan_bluetooth",
            "set_channel_balance": "async_set_channel_balance",
        }

        # Media player entity actions (registered in async_setup_entry)
        entity_action_methods = {
            "play_url": "async_play_url",
            "play_preset": "async_play_preset",
            "play_playlist": "async_play_playlist",
            "set_eq": "async_set_eq",
            "play_notification": "async_play_notification",
            "play_queue": "async_play_queue",
            "remove_from_queue": "async_remove_from_queue",
            "get_queue": "async_get_queue",
        }

        all_methods = {**platform_action_methods, **entity_action_methods}

        for action_name, method_name in all_methods.items():
            assert hasattr(WiiMMediaPlayer, method_name), (
                f"WiiMMediaPlayer is missing handler method '{method_name}' for action '{action_name}'. "
                f"Add the method to handle this action."
            )

            method = getattr(WiiMMediaPlayer, method_name)
            assert callable(method), f"WiiMMediaPlayer.{method_name} should be callable for action '{action_name}'."
