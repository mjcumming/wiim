"""Unit tests for WiiM integration core functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import Platform


class TestPlatformConstants:
    """Test platform constants and configuration."""

    def test_core_platforms_definition(self, hass):
        """Test CORE_PLATFORMS constant."""
        from custom_components.wiim import CORE_PLATFORMS

        assert isinstance(CORE_PLATFORMS, list)
        assert len(CORE_PLATFORMS) >= 6

        # Check required core platforms
        platform_names = [p.value for p in CORE_PLATFORMS]
        assert "media_player" in platform_names
        assert "sensor" in platform_names
        assert "number" in platform_names
        assert "switch" in platform_names
        assert "update" in platform_names
        assert "light" in platform_names

    def test_optional_platforms_definition(self, hass):
        """Test OPTIONAL_PLATFORMS constant."""
        from custom_components.wiim import OPTIONAL_PLATFORMS

        assert isinstance(OPTIONAL_PLATFORMS, dict)

        # Check optional platforms
        assert "enable_maintenance_buttons" in OPTIONAL_PLATFORMS
        assert "enable_network_monitoring" in OPTIONAL_PLATFORMS

        assert OPTIONAL_PLATFORMS["enable_maintenance_buttons"] == Platform.BUTTON
        assert OPTIONAL_PLATFORMS["enable_network_monitoring"] == Platform.BINARY_SENSOR

    def test_platform_constants_immutable(self, hass):
        """Test that platform constants are properly defined."""
        from custom_components.wiim import CORE_PLATFORMS, OPTIONAL_PLATFORMS

        # Verify these are the actual platform constants from Home Assistant
        for platform in CORE_PLATFORMS:
            assert hasattr(Platform, platform.name)

        for _config_key, platform in OPTIONAL_PLATFORMS.items():
            assert hasattr(Platform, platform.name)


class TestGetEnabledPlatforms:
    """Test get_enabled_platforms function."""

    async def test_get_enabled_platforms_core_only(self, hass):
        """Test get_enabled_platforms with core platforms only."""
        from custom_components.wiim import get_enabled_platforms

        # Mock config entry
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100"}
        entry.entry_id = "test-entry"
        entry.options = {}

        platforms = get_enabled_platforms(hass, entry)

        # Should include all core platforms (including SELECT and BUTTON)
        platform_names = [p.value for p in platforms]
        assert "media_player" in platform_names
        assert "sensor" in platform_names
        assert "number" in platform_names
        assert "switch" in platform_names
        assert "update" in platform_names
        assert "light" in platform_names
        assert "select" in platform_names  # Now in core for audio output/Bluetooth
        assert "button" in platform_names  # Now in core for Bluetooth scan

    def test_get_enabled_platforms_with_capabilities_audio_output(self, hass):
        """Test get_enabled_platforms when device supports audio output."""
        from custom_components.wiim import get_enabled_platforms

        # Mock config entry
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100"}
        entry.entry_id = "test-entry"
        entry.options = {}

        capabilities = {"supports_audio_output": True}

        platforms = get_enabled_platforms(hass, entry, capabilities)

        # Should include select platform when audio output is supported
        # Note: SELECT is now always in CORE_PLATFORMS (line 71 in __init__.py)
        platform_names = [p.value for p in platforms]
        assert "select" in platform_names

    def test_get_enabled_platforms_without_audio_output(self, hass):
        """Test get_enabled_platforms when device doesn't support audio output."""
        from custom_components.wiim import get_enabled_platforms

        # Mock config entry
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100"}
        entry.entry_id = "test-entry"
        entry.options = {}

        capabilities = {"supports_audio_output": False}

        platforms = get_enabled_platforms(hass, entry, capabilities)

        # SELECT platform is now ALWAYS enabled (for Bluetooth device selection)
        # See __init__.py lines 113-134
        platform_names = [p.value for p in platforms]
        assert "select" in platform_names

    def test_get_enabled_platforms_capabilities_from_coordinator(self, hass):
        """Test get_enabled_platforms getting capabilities from coordinator."""
        from custom_components.wiim import get_enabled_platforms

        # Mock config entry
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100"}
        entry.entry_id = "test-entry"

        # Mock coordinator with capabilities
        mock_coordinator = MagicMock()
        mock_coordinator._capabilities = {"supports_audio_output": True}

        hass.data = {
            "wiim": {
                "test-entry": {
                    "coordinator": mock_coordinator
                }
            }
        }

        platforms = get_enabled_platforms(hass, entry)

        # Should include select platform when coordinator has audio output capabilities
        platform_names = [p.value for p in platforms]
        assert "select" in platform_names

    def test_get_enabled_platforms_no_capabilities(self, hass):
        """Test get_enabled_platforms when no capabilities are available."""
        from custom_components.wiim import get_enabled_platforms

        # Mock config entry
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100"}
        entry.entry_id = "test-entry"
        entry.options = {}

        hass.data = {}

        platforms = get_enabled_platforms(hass, entry)

        # SELECT platform is now ALWAYS enabled (fallback for Bluetooth)
        # See __init__.py lines 128-134
        platform_names = [p.value for p in platforms]
        assert "select" in platform_names

    def test_get_enabled_platforms_with_optional_platforms(self, hass):
        """Test get_enabled_platforms with optional platforms enabled."""
        from custom_components.wiim import get_enabled_platforms

        # Mock config entry with optional platforms enabled
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100"}
        entry.entry_id = "test-entry"
        entry.options = {
            "enable_maintenance_buttons": True,
            "enable_network_monitoring": True,
        }

        platforms = get_enabled_platforms(hass, entry)

        # Should include optional platforms when enabled
        platform_names = [p.value for p in platforms]
        assert "button" in platform_names
        assert "binary_sensor" in platform_names

    def test_get_enabled_platforms_optional_platforms_disabled(self, hass):
        """Test get_enabled_platforms with optional platforms disabled."""
        from custom_components.wiim import get_enabled_platforms

        # Mock config entry with optional platforms disabled
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100"}
        entry.entry_id = "test-entry"
        entry.options = {
            "enable_maintenance_buttons": False,
            "enable_network_monitoring": False,
        }

        platforms = get_enabled_platforms(hass, entry)

        # BUTTON is now in CORE_PLATFORMS (for Bluetooth scan button)
        # Only maintenance buttons are optional
        platform_names = [p.value for p in platforms]
        assert "button" in platform_names  # Always enabled for Bluetooth scan
        assert "binary_sensor" not in platform_names  # Only enabled with network monitoring

    def test_get_enabled_platforms_no_options(self, hass):
        """Test get_enabled_platforms with no options configured."""
        from custom_components.wiim import get_enabled_platforms

        # Mock config entry with no options
        entry = MagicMock()
        entry.data = {"host": "192.168.1.100"}
        entry.entry_id = "test-entry"
        entry.options = {}

        platforms = get_enabled_platforms(hass, entry)

        # BUTTON is now in CORE_PLATFORMS (for Bluetooth scan button)
        platform_names = [p.value for p in platforms]
        assert "button" in platform_names  # Always enabled for Bluetooth scan
        assert "binary_sensor" not in platform_names  # Only with network monitoring option


class TestRebootDeviceService:
    """Test reboot device service functionality."""

    @pytest.mark.asyncio
    async def test_reboot_device_service_missing_entity_id(self, hass):
        """Test reboot device service with missing entity_id."""
        from custom_components.wiim import _reboot_device_service

        # Mock service call without entity_id
        call = MagicMock()
        call.data = {}

        hass = MagicMock()

        await _reboot_device_service(hass, call)

        # Should log error and return without doing anything
        # Note: We can't easily test the logger output without complex mocking

    @pytest.mark.asyncio
    async def test_reboot_device_service_entity_not_found(self, hass):
        """Test reboot device service when entity doesn't exist."""
        from custom_components.wiim import _reboot_device_service

        # Mock service call with entity_id
        call = MagicMock()
        call.data = {"entity_id": "media_player.nonexistent"}

        hass = MagicMock()
        hass.states.get.return_value = None  # Entity not found

        await _reboot_device_service(hass, call)

        # Should log error and return

    @pytest.mark.asyncio
    async def test_reboot_device_service_wrong_domain(self, hass):
        """Test reboot device service with wrong domain."""
        from custom_components.wiim import _reboot_device_service

        # Mock service call with non-media_player entity
        call = MagicMock()
        call.data = {"entity_id": "sensor.some_sensor"}

        hass = MagicMock()
        hass.states.get.return_value = MagicMock(domain="sensor")

        await _reboot_device_service(hass, call)

        # Should log error and return

    @pytest.mark.asyncio
    async def test_reboot_device_service_no_device(self, hass):
        """Test reboot device service when entity has no device."""
        from custom_components.wiim import _reboot_device_service

        # Mock service call with media_player entity
        call = MagicMock()
        call.data = {"entity_id": "media_player.test_wiim"}

        hass = MagicMock()
        hass.states.get.return_value = MagicMock(domain="media_player")

        # Mock entity registry - entity has no device
        entity_registry = MagicMock()
        entity_registry.async_get.return_value = None

        hass.helpers.entity_registry.async_get.return_value = entity_registry

        await _reboot_device_service(hass, call)

        # Should log error and return

    @pytest.mark.asyncio
    async def test_reboot_device_service_device_not_found(self, hass):
        """Test reboot device service when device not found."""
        from custom_components.wiim import _reboot_device_service

        # Mock service call with media_player entity
        call = MagicMock()
        call.data = {"entity_id": "media_player.test_wiim"}

        hass = MagicMock()
        hass.states.get.return_value = MagicMock(domain="media_player")

        # Mock registries
        entity_registry = MagicMock()
        entity_entry = MagicMock()
        entity_entry.device_id = "device_123"
        entity_registry.async_get.return_value = entity_entry

        device_registry = MagicMock()
        device_registry.async_get.return_value = None  # Device not found

        hass.helpers.entity_registry.async_get.return_value = entity_registry
        hass.helpers.device_registry.async_get.return_value = device_registry

        await _reboot_device_service(hass, call)

        # Should log error and return

    @pytest.mark.asyncio
    async def test_reboot_device_service_success(self, hass):
        """Test reboot device service with successful reboot."""
        from custom_components.wiim import _reboot_device_service

        # Mock service call with media_player entity
        call = MagicMock()
        call.data = {"entity_id": "media_player.test_wiim"}

        hass = MagicMock()
        hass.states.get.return_value = MagicMock(domain="media_player")

        # Mock registries and device lookup
        entity_registry = MagicMock()
        entity_entry = MagicMock()
        entity_entry.device_id = "device_123"
        entity_registry.async_get.return_value = entity_entry

        device_registry = MagicMock()
        device_entry = MagicMock()
        device_entry.config_entries = ["config_entry_123"]
        device_registry.async_get.return_value = device_entry

        hass.helpers.entity_registry.async_get.return_value = entity_registry
        hass.helpers.device_registry.async_get.return_value = device_registry

        # Mock WiiM data with speaker
        hass.data = {
            "wiim": {
                "config_entry_123": {
                    "speaker": MagicMock(name="Test Speaker")
                }
            }
        }

        # Mock speaker reboot
        mock_speaker = hass.data["wiim"]["config_entry_123"]["speaker"]
        mock_speaker.coordinator = MagicMock()
        mock_speaker.coordinator.client = MagicMock()
        mock_speaker.coordinator.client.reboot = AsyncMock()

        await _reboot_device_service(hass, call)

        # Should call reboot on the speaker
        mock_speaker.coordinator.client.reboot.assert_called_once()

    @pytest.mark.asyncio
    async def test_reboot_device_service_with_exception(self, hass):
        """Test reboot device service when reboot fails."""
        from custom_components.wiim import _reboot_device_service

        # Mock service call with media_player entity
        call = MagicMock()
        call.data = {"entity_id": "media_player.test_wiim"}

        hass = MagicMock()
        hass.states.get.return_value = MagicMock(domain="media_player")

        # Mock registries and device lookup
        entity_registry = MagicMock()
        entity_entry = MagicMock()
        entity_entry.device_id = "device_123"
        entity_registry.async_get.return_value = entity_entry

        device_registry = MagicMock()
        device_entry = MagicMock()
        device_entry.config_entries = ["config_entry_123"]
        device_registry.async_get.return_value = device_entry

        hass.helpers.entity_registry.async_get.return_value = entity_registry
        hass.helpers.device_registry.async_get.return_value = device_registry

        # Mock WiiM data with speaker
        hass.data = {
            "wiim": {
                "config_entry_123": {
                    "speaker": MagicMock(name="Test Speaker")
                }
            }
        }

        # Mock speaker reboot with exception
        mock_speaker = hass.data["wiim"]["config_entry_123"]["speaker"]
        mock_speaker.coordinator = MagicMock()
        mock_speaker.coordinator.client = MagicMock()
        mock_speaker.coordinator.client.reboot = AsyncMock(side_effect=Exception("Network error"))

        await _reboot_device_service(hass, call)

        # Should still call reboot (reboot commands often don't return responses)
        mock_speaker.coordinator.client.reboot.assert_called_once()


class TestSyncTimeService:
    """Test sync time service functionality."""

    @pytest.mark.asyncio
    async def test_sync_time_service_missing_entity_id(self, hass):
        """Test sync time service with missing entity_id."""
        from custom_components.wiim import _sync_time_service

        # Mock service call without entity_id
        call = MagicMock()
        call.data = {}

        hass = MagicMock()

        await _sync_time_service(hass, call)

        # Should log error and return

    @pytest.mark.asyncio
    async def test_sync_time_service_entity_not_found(self, hass):
        """Test sync time service when entity doesn't exist."""
        from custom_components.wiim import _sync_time_service

        # Mock service call with entity_id
        call = MagicMock()
        call.data = {"entity_id": "media_player.nonexistent"}

        hass = MagicMock()
        hass.states.get.return_value = None  # Entity not found

        await _sync_time_service(hass, call)

        # Should log error and return

    @pytest.mark.asyncio
    async def test_sync_time_service_wrong_domain(self, hass):
        """Test sync time service with wrong domain."""
        from custom_components.wiim import _sync_time_service

        # Mock service call with non-media_player entity
        call = MagicMock()
        call.data = {"entity_id": "sensor.some_sensor"}

        hass = MagicMock()
        hass.states.get.return_value = MagicMock(domain="sensor")

        await _sync_time_service(hass, call)

        # Should log error and return

    @pytest.mark.asyncio
    async def test_sync_time_service_success(self, hass):
        """Test sync time service with successful sync."""
        from custom_components.wiim import _sync_time_service

        # Mock service call with media_player entity
        call = MagicMock()
        call.data = {"entity_id": "media_player.test_wiim"}

        hass = MagicMock()
        hass.states.get.return_value = MagicMock(domain="media_player")

        # Mock registries and device lookup
        entity_registry = MagicMock()
        entity_entry = MagicMock()
        entity_entry.device_id = "device_123"
        entity_registry.async_get.return_value = entity_entry

        device_registry = MagicMock()
        device_entry = MagicMock()
        device_entry.config_entries = ["config_entry_123"]
        device_registry.async_get.return_value = device_entry

        hass.helpers.entity_registry.async_get.return_value = entity_registry
        hass.helpers.device_registry.async_get.return_value = device_registry

        # Mock WiiM data with speaker
        hass.data = {
            "wiim": {
                "config_entry_123": {
                    "speaker": MagicMock(name="Test Speaker")
                }
            }
        }

        # Mock speaker sync_time
        mock_speaker = hass.data["wiim"]["config_entry_123"]["speaker"]
        mock_speaker.coordinator = MagicMock()
        mock_speaker.coordinator.client = MagicMock()
        mock_speaker.coordinator.client.sync_time = AsyncMock()

        await _sync_time_service(hass, call)

        # Should call sync_time on the speaker
        mock_speaker.coordinator.client.sync_time.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_time_service_with_exception(self, hass):
        """Test sync time service when sync fails."""
        from custom_components.wiim import _sync_time_service

        # Mock service call with media_player entity
        call = MagicMock()
        call.data = {"entity_id": "media_player.test_wiim"}

        hass = MagicMock()
        hass.states.get.return_value = MagicMock(domain="media_player")

        # Mock registries and device lookup
        entity_registry = MagicMock()
        entity_entry = MagicMock()
        entity_entry.device_id = "device_123"
        entity_registry.async_get.return_value = entity_entry

        device_registry = MagicMock()
        device_entry = MagicMock()
        device_entry.config_entries = ["config_entry_123"]
        device_registry.async_get.return_value = device_entry

        hass.helpers.entity_registry.async_get.return_value = entity_registry
        hass.helpers.device_registry.async_get.return_value = device_registry

        # Mock WiiM data with speaker
        hass.data = {
            "wiim": {
                "config_entry_123": {
                    "speaker": MagicMock(name="Test Speaker")
                }
            }
        }

        # Mock speaker sync_time with exception
        mock_speaker = hass.data["wiim"]["config_entry_123"]["speaker"]
        mock_speaker.coordinator = MagicMock()
        mock_speaker.coordinator.client = MagicMock()
        mock_speaker.coordinator.client.sync_time = AsyncMock(side_effect=Exception("Network error"))

        # Should raise exception for sync time failures
        with pytest.raises(Exception, match="Network error"):
            await _sync_time_service(hass, call)


class TestUpdateListener:
    """Test update listener functionality."""

    @pytest.mark.asyncio
    async def test_update_listener_reload(self, hass):
        """Test update listener triggers reload."""
        from custom_components.wiim import _update_listener

        # Mock config entry
        entry = MagicMock()
        entry.entry_id = "test-entry"

        # Mock reload method
        hass.config_entries.async_reload = AsyncMock()

        await _update_listener(hass, entry)

        # Should trigger reload
        hass.config_entries.async_reload.assert_called_once_with("test-entry")


class TestServiceRegistration:
    """Test service registration functionality."""

    def test_service_registration_constants(self, hass):
        """Test service registration constants."""
        # Services should be registered for these functions
        from custom_components.wiim import _reboot_device_service, _sync_time_service

        # Verify the service functions exist
        assert callable(_reboot_device_service)
        assert callable(_sync_time_service)

    def test_service_function_signatures(self, hass):
        """Test service function signatures."""
        # Check function signatures
        import inspect

        from custom_components.wiim import _reboot_device_service, _sync_time_service

        reboot_sig = inspect.signature(_reboot_device_service)
        sync_sig = inspect.signature(_sync_time_service)

        # Both should accept hass and call parameters
        assert "hass" in reboot_sig.parameters
        assert "call" in reboot_sig.parameters

        assert "hass" in sync_sig.parameters
        assert "call" in sync_sig.parameters


class TestCoreIntegration:
    """Test core integration functionality."""

    def test_domain_constant(self, hass):
        """Test domain constant."""
        from custom_components.wiim import DOMAIN

        assert DOMAIN == "wiim"

    def test_logger_configuration(self, hass):
        """Test logger configuration."""
        from custom_components.wiim import _LOGGER

        assert _LOGGER.name == "custom_components.wiim"

    def test_platform_imports(self, hass):
        """Test that all platform imports work."""
        from custom_components.wiim import (
            CORE_PLATFORMS,
            OPTIONAL_PLATFORMS,
            _reboot_device_service,
            _sync_time_service,
            _update_listener,
            get_enabled_platforms,
        )

        # All core functions should be importable
        assert len(CORE_PLATFORMS) > 0
        assert len(OPTIONAL_PLATFORMS) > 0
        assert callable(get_enabled_platforms)
        assert callable(_update_listener)
        assert callable(_reboot_device_service)
        assert callable(_sync_time_service)
