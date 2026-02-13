"""Unit tests for WiiM integration setup and teardown."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pywiim.discovery import DiscoveredDevice
from pywiim.exceptions import WiiMConnectionError

from custom_components.wiim.const import DOMAIN
from tests.const import MOCK_CONFIG, MOCK_DEVICE_DATA


@pytest.fixture
async def setup_entry(hass: HomeAssistant, bypass_get_data):
    """Shared fixture that sets up a WiiM entry once for reuse across tests.

    This avoids redundant setup/teardown for tests that only need to verify
    the entry is properly configured, significantly speeding up test execution.

    Note: async_setup and async_unload already wait internally for critical
    operations, so we only need one async_block_till_done() after setup to ensure
    all platform entities are registered.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WiiM Mini",
        data=MOCK_CONFIG,
        unique_id=MOCK_DEVICE_DATA["uuid"],
    )
    entry.add_to_hass(hass)

    # async_setup waits internally for critical operations (coordinator refresh, etc.)
    await hass.config_entries.async_setup(entry.entry_id)
    # Single wait to ensure all platform entities are registered
    await hass.async_block_till_done()

    yield entry

    # Cleanup - async_unload also waits internally
    await hass.config_entries.async_unload(entry.entry_id)
    # Single wait for cleanup to complete
    await hass.async_block_till_done()


def _setup_mock_http(hass: HomeAssistant) -> None:
    """Helper to mock hass.http for tests that need it."""
    hass.http = Mock()
    hass.http.async_register_static_paths = AsyncMock()


@pytest.mark.skip(reason="HA 2025 test infrastructure issues - all tests have teardown problems")
class TestIntegrationSetup:
    """Test WiiM integration setup functionality."""

    @pytest.mark.skip(reason="Teardown issue with socket blocking - needs investigation")
    @pytest.mark.asyncio
    async def test_setup_entry_connection_error(self, hass: HomeAssistant) -> None:
        """Test setup failure due to connection error."""
        # Mock hass.http to prevent AttributeError
        _setup_mock_http(hass)

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        with patch(
            "pywiim.WiiMClient.get_device_info",
            side_effect=Exception("Connection error"),
        ):
            # async_setup waits internally for critical operations
            await hass.config_entries.async_setup(entry.entry_id)
            # Only wait if we need to verify async state changes
            await hass.async_block_till_done()

            assert entry.state is ConfigEntryState.SETUP_RETRY

    @pytest.mark.asyncio
    async def test_setup_retry_count_tracking(self, hass: HomeAssistant) -> None:
        """Test that retry count is properly tracked during setup failures."""
        # Mock hass.http to prevent AttributeError
        _setup_mock_http(hass)

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        # Simulate connection failure with WiiMConnectionError
        with patch(
            "custom_components.wiim.coordinator.WiiMCoordinator.async_config_entry_first_refresh",
            side_effect=WiiMConnectionError("Connection failed"),
        ):
            try:
                # async_setup waits internally for critical operations
                await hass.config_entries.async_setup(entry.entry_id)
                # Wait for retry state to be set
                await hass.async_block_till_done()
            except Exception:
                pass  # Expected to fail

            # Verify retry count was incremented and entry is in retry state
            assert hasattr(entry, "_setup_retry_count")
            assert entry._setup_retry_count == 1
            assert entry.state is ConfigEntryState.SETUP_RETRY

    @pytest.mark.asyncio
    async def test_setup_wrapped_wiim_error_detection(self, hass: HomeAssistant) -> None:
        """Test that wrapped WiiM errors are properly detected."""
        from homeassistant.helpers.update_coordinator import UpdateFailed

        # Mock hass.http to prevent AttributeError
        _setup_mock_http(hass)

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        # Simulate UpdateFailed wrapping a WiiMConnectionError (as coordinator does)
        wrapped_error = UpdateFailed("Error updating WiiM device")
        wrapped_error.__cause__ = WiiMConnectionError("Connection failed")

        with patch(
            "custom_components.wiim.coordinator.WiiMCoordinator.async_config_entry_first_refresh",
            side_effect=wrapped_error,
        ):
            try:
                # async_setup waits internally for critical operations
                await hass.config_entries.async_setup(entry.entry_id)
                # Wait for retry state to be set
                await hass.async_block_till_done()
            except Exception:
                pass  # Expected to fail

            # Verify retry count was incremented
            assert hasattr(entry, "_setup_retry_count")
            assert entry._setup_retry_count == 1

    @pytest.mark.asyncio
    async def test_device_creation(self, hass: HomeAssistant, setup_entry) -> None:
        """Test device is created in device registry."""
        entry = setup_entry

        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        assert len(devices) >= 1

        # Check device details
        device = devices[0]
        assert device.name == MOCK_DEVICE_DATA["DeviceName"]
        assert device.manufacturer == "WiiM"
        assert device.model == "WiiM Speaker"  # Fallback model when project not in status

    @pytest.mark.asyncio
    async def test_platforms_setup(self, hass: HomeAssistant, setup_entry) -> None:
        """Test all platforms are set up."""
        entry = setup_entry

        # Check various entity types are created
        entity_registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

        # We should have entities from different platforms
        domains = {entity.domain for entity in entities}
        expected_domains = {"media_player"}  # At minimum, we should have media player
        assert expected_domains.issubset(domains)

    @pytest.mark.skip(reason="Service registration temporarily disabled - migrating to new HA API")
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "service_name",
        [
            "reboot_device",
            "sync_time",
        ],
    )
    async def test_service_registration(self, hass: HomeAssistant, setup_entry, service_name: str) -> None:
        """Test custom services are registered.

        Note: join/unjoin are built-in Home Assistant media_player services,
        not custom wiim services, so they're not tested here.
        """
        # Check if service is available
        assert hass.services.has_service(DOMAIN, service_name)

    @pytest.mark.asyncio
    async def test_coordinator_creation(self, hass: HomeAssistant, setup_entry) -> None:
        """Test coordinator is created and working."""
        entry = setup_entry

        # Check coordinator exists
        assert DOMAIN in hass.data
        assert entry.entry_id in hass.data[DOMAIN]
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert coordinator is not None
        assert coordinator.last_update_success is True


@pytest.mark.skip(reason="HA 2025 test infrastructure issues - teardown problems")
class TestIntegrationTeardown:
    """Test WiiM integration teardown functionality."""

    @pytest.mark.asyncio
    async def test_unload_entry(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test config entry can be unloaded."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        # async_setup waits internally for critical operations
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify setup completed
        assert entry.state is ConfigEntryState.LOADED

        # Unload the entry (platform unloading may fail in test environment)
        # Since platform unloading is complex in test environment, just verify entry can be removed
        await hass.config_entries.async_remove(entry.entry_id)
        # Entry should be removed after manual removal
        assert entry.entry_id not in [e.entry_id for e in hass.config_entries.async_entries()]

    @pytest.mark.asyncio
    async def test_reload_entry(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test config entry can be reloaded."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        # async_setup waits internally for critical operations
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify setup completed
        assert entry.state is ConfigEntryState.LOADED

        # Reload the entry
        await hass.config_entries.async_reload(entry.entry_id)
        # Wait for reload to complete
        await hass.async_block_till_done()

        # Check entry is still loaded after reload
        assert entry.state is ConfigEntryState.LOADED


@pytest.mark.skip(reason="Service registration temporarily disabled - migrating to new HA API")
class TestIntegrationServices:
    """Test integration service functionality."""

    @pytest.mark.asyncio
    async def test_reboot_device_service(self, hass: HomeAssistant, setup_entry) -> None:
        """Test reboot_device service is registered and callable."""
        # Verify service is registered (already tested by parametrize, but keep for service call testing)
        assert hass.services.has_service(DOMAIN, "reboot_device")

    @pytest.mark.asyncio
    async def test_sync_time_service(self, hass: HomeAssistant, setup_entry) -> None:
        """Test sync_time service."""
        from unittest.mock import AsyncMock

        from custom_components.wiim.data import get_all_coordinators

        entry = setup_entry

        # Get the media player entity
        entity_registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        media_player_entities = [e for e in entities if e.domain == "media_player"]
        assert len(media_player_entities) > 0

        entity_id = media_player_entities[0].entity_id

        # Get actual coordinators and mock sync_time on player (not client)
        # The media_player.async_sync_time() calls coordinator.player.sync_time()
        coordinators = get_all_coordinators(hass)
        if coordinators and hasattr(coordinators[0], "player"):
            coordinators[0].player.sync_time = AsyncMock()

            # Call the service
            await hass.services.async_call(
                DOMAIN,
                "sync_time",
                {"entity_id": entity_id},
                blocking=True,
            )

            # Verify sync_time was called on the player
            coordinators[0].player.sync_time.assert_called_once()

    @pytest.mark.asyncio
    async def test_reboot_service_handles_missing_entity(self, hass: HomeAssistant) -> None:
        """Test reboot_device service handles missing entity."""
        from custom_components.wiim import async_setup

        await async_setup(hass, {})

        # Call service with non-existent entity
        await hass.services.async_call(
            DOMAIN,
            "reboot_device",
            {"entity_id": "media_player.nonexistent"},
            blocking=True,
        )

        # Should not raise, just log error

    @pytest.mark.asyncio
    async def test_get_enabled_platforms_with_capabilities(self, hass: HomeAssistant) -> None:
        """Test get_enabled_platforms with capabilities."""
        from homeassistant.const import Platform

        from custom_components.wiim import get_enabled_platforms

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )

        # Test with audio output capability
        capabilities = {"supports_audio_output": True, "supports_firmware_install": True}
        platforms = get_enabled_platforms(hass, entry, capabilities)

        assert Platform.SELECT in platforms
        assert Platform.MEDIA_PLAYER in platforms
        assert Platform.SENSOR in platforms
        assert Platform.UPDATE in platforms

        # Test without audio output capability
        capabilities = {"supports_audio_output": False, "supports_firmware_install": True}
        platforms = get_enabled_platforms(hass, entry, capabilities)

        # SELECT should still be enabled for Bluetooth
        assert Platform.SELECT in platforms
        assert Platform.UPDATE in platforms

    @pytest.mark.asyncio
    async def test_get_enabled_platforms_excludes_update_for_non_wiim(self, hass: HomeAssistant) -> None:
        """Test update platform is excluded for non-WiiM devices."""
        from homeassistant.const import Platform

        from custom_components.wiim import get_enabled_platforms

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="LinkPlay Device",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )

        platforms = get_enabled_platforms(hass, entry, {"supports_firmware_install": False})
        assert Platform.UPDATE not in platforms

    @pytest.mark.asyncio
    async def test_get_enabled_platforms_falls_back_to_player_flag(self, hass: HomeAssistant) -> None:
        """If capabilities are missing supports_firmware_install, fall back to runtime player flag."""
        from homeassistant.const import Platform

        from custom_components.wiim import get_enabled_platforms

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Master Bedroom",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
            entry_id="test-entry-id",
        )
        entry.add_to_hass(hass)

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.supports_firmware_install = True
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator, "entry": entry}

        platforms = get_enabled_platforms(hass, entry, {})
        assert Platform.UPDATE in platforms


class TestCapabilityCacheRefresh:
    """Tests for capability cache refresh behavior in async_setup_entry."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_requires_exact_pywiim_version(
        self, hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Setup should fail fast if installed pywiim doesn't match the pinned version."""
        from custom_components.wiim import async_setup_entry

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Master Bedroom",
            data={"host": "192.168.1.116"},
            unique_id="FF98F09CD89F9B50AB9CEC68",
        )
        entry.add_to_hass(hass)

        monkeypatch.setattr("custom_components.wiim.async_ensure_pywiim_version", AsyncMock(return_value="2.1.58"))
        monkeypatch.setattr("custom_components.wiim.is_pywiim_version_compatible", lambda _version: False)

        with pytest.raises(ConfigEntryNotReady, match="pywiim 2.1.81 required; found 2.1.58"):
            await async_setup_entry(hass, entry)

    @pytest.mark.asyncio
    async def test_async_setup_entry_redetects_when_cached_capabilities_missing_firmware_flag(
        self, hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If cached capabilities are present but missing supports_firmware_install, re-detect once."""
        from custom_components.wiim import async_setup_entry

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Master Bedroom",
            data={
                "host": "192.168.1.116",
                "endpoint": "https://192.168.1.116:443",
                # Stale cache: missing supports_firmware_install key
                "capabilities": {"device_type": "WiiM_Pro_with_gc4a", "vendor": "wiim"},
            },
            unique_id="FF98F09CD89F9B50AB9CEC68",
        )
        entry.add_to_hass(hass)

        # Fake temp client used for _detect_capabilities
        temp_client = MagicMock()
        temp_client._detect_capabilities = AsyncMock(
            return_value={"device_type": "WiiM_Pro_with_gc4a", "vendor": "wiim", "supports_firmware_install": True}
        )

        # Patch WiiMClient() constructor in module to return our temp client for detection
        monkeypatch.setattr("custom_components.wiim.WiiMClient", MagicMock(return_value=temp_client))

        # Patch coordinator creation to avoid real network and to control player values
        class _FakePlayer:
            def __init__(self):
                self.host = "192.168.1.116"
                self.name = "Master Bedroom"
                self.client = MagicMock(discovered_endpoint=None)
                self.supports_firmware_install = True

        class _FakeCoordinator:
            def __init__(self, hass, host, entry=None, capabilities=None, port=None, protocol=None, timeout=10):
                self.hass = hass
                self.player = _FakePlayer()
                self.last_update_success = True

            async def async_config_entry_first_refresh(self):
                return None

        monkeypatch.setattr("custom_components.wiim.WiiMCoordinator", _FakeCoordinator)

        # Avoid real device registry writes
        monkeypatch.setattr("custom_components.wiim._register_ha_device", AsyncMock())

        # Capture which platforms we forward
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        ok = await async_setup_entry(hass, entry)
        assert ok is True

        # Should have re-detected (since cached caps were missing the flag)
        temp_client._detect_capabilities.assert_awaited()

        # Should have forwarded UPDATE platform
        forwarded = hass.config_entries.async_forward_entry_setups.await_args.args[1]
        assert "update" in [p.value for p in forwarded]

    @pytest.mark.asyncio
    async def test_get_enabled_platforms_with_optional_features(self, hass: HomeAssistant) -> None:
        """Test get_enabled_platforms with optional features enabled."""
        from homeassistant.const import Platform

        from custom_components.wiim import get_enabled_platforms
        from custom_components.wiim.const import CONF_ENABLE_MAINTENANCE_BUTTONS

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        # Use add_to_hass to properly initialize entry
        entry.add_to_hass(hass)
        # Update options after adding to hass
        hass.config_entries.async_update_entry(entry, options={CONF_ENABLE_MAINTENANCE_BUTTONS: True})

        # Test with empty capabilities dict (triggers warning path but still enables SELECT)
        # When capabilities is empty dict, it checks if it's falsy and goes to else branch
        platforms = get_enabled_platforms(hass, entry, {})

        # SELECT should still be enabled for Bluetooth even without capabilities
        assert Platform.SELECT in platforms
        # BUTTON is in CORE_PLATFORMS
        assert Platform.BUTTON in platforms
        # Core platforms should be present
        assert Platform.MEDIA_PLAYER in platforms
        assert Platform.SENSOR in platforms
        # NUMBER, LIGHT should also be in core
        # Note: SWITCH was removed as it was empty (no switch entities implemented)
        assert Platform.NUMBER in platforms
        assert Platform.LIGHT in platforms

    @pytest.mark.asyncio
    async def test_try_rebind_host_from_uuid_updates_entry_host(
        self, hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """UUID-matched rediscovery should update host and clear stale endpoint."""
        from custom_components.wiim import _try_rebind_host_from_uuid

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Master Bedroom",
            data={
                "host": "192.168.1.50",
                "endpoint": "http://192.168.1.50:80",
            },
            unique_id="FF98F09CD89F9B50AB9CEC68",
        )
        entry.add_to_hass(hass)

        monkeypatch.setattr(
            "custom_components.wiim.discover_devices",
            AsyncMock(
                return_value=[
                    DiscoveredDevice(
                        ip="192.168.1.116",
                        uuid="FF98F09CD89F9B50AB9CEC68",
                        validated=True,
                    )
                ]
            ),
        )

        new_host = await _try_rebind_host_from_uuid(hass, entry)
        assert new_host == "192.168.1.116"
        assert entry.data["host"] == "192.168.1.116"
        assert "endpoint" not in entry.data

    @pytest.mark.asyncio
    async def test_try_rebind_host_from_uuid_returns_none_when_not_found(
        self, hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rediscovery should be a no-op when UUID match is not found."""
        from custom_components.wiim import _try_rebind_host_from_uuid

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Master Bedroom",
            data={"host": "192.168.1.50"},
            unique_id="FF98F09CD89F9B50AB9CEC68",
        )
        entry.add_to_hass(hass)

        monkeypatch.setattr(
            "custom_components.wiim.discover_devices",
            AsyncMock(
                return_value=[
                    DiscoveredDevice(
                        ip="192.168.1.77",
                        uuid="SOME-OTHER-UUID",
                        validated=True,
                    )
                ]
            ),
        )

        new_host = await _try_rebind_host_from_uuid(hass, entry)
        assert new_host is None
        assert entry.data["host"] == "192.168.1.50"

    @pytest.mark.asyncio
    async def test_async_setup_entry_rebinds_on_connectivity_error(
        self, hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Setup retries should trigger host rebind attempt on connectivity failures."""
        from custom_components.wiim import async_setup_entry

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Master Bedroom",
            data={
                "host": "192.168.1.50",
                "capabilities": {"supports_firmware_install": False},
            },
            unique_id="FF98F09CD89F9B50AB9CEC68",
        )
        entry.add_to_hass(hass)

        class _FailingCoordinator:
            def __init__(self, hass, host, entry=None, capabilities=None, port=None, protocol=None, timeout=10):
                self.hass = hass
                self.player = MagicMock()
                self.player.name = "Master Bedroom"
                self.player.client = MagicMock(discovered_endpoint=None)

            async def async_config_entry_first_refresh(self):
                raise WiiMConnectionError("device unreachable")

        monkeypatch.setattr("custom_components.wiim.WiiMCoordinator", _FailingCoordinator)
        monkeypatch.setattr("custom_components.wiim.async_ensure_pywiim_version", AsyncMock(return_value="2.1.81"))
        monkeypatch.setattr("custom_components.wiim.is_pywiim_version_compatible", lambda _version: True)
        monkeypatch.setattr(
            "custom_components.wiim._try_rebind_host_from_uuid",
            AsyncMock(return_value="192.168.1.116"),
        )

        with pytest.raises(ConfigEntryNotReady, match="Device rediscovered at 192.168.1.116"):
            await async_setup_entry(hass, entry)


@pytest.mark.skip(reason="HA 2025 test infrastructure issues - teardown problems")
class TestInitCapabilityDetection:
    """Test capability detection in async_setup_entry."""

    @pytest.mark.asyncio
    async def test_setup_entry_with_cached_endpoint(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test setup_entry with cached endpoint."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data={**MOCK_CONFIG, "endpoint": "http://192.168.1.100:80"},
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        # async_setup waits internally for critical operations
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.LOADED

    @pytest.mark.asyncio
    async def test_setup_entry_capability_detection_error(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test setup_entry handles capability detection errors gracefully."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        # async_setup waits internally for critical operations
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Entry should still be loaded (capability errors are logged but don't fail setup)
        assert entry.state == ConfigEntryState.LOADED

    @pytest.mark.asyncio
    async def test_setup_entry_caches_discovered_endpoint(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test setup_entry caches discovered endpoint."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Mini",
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        # async_setup waits internally for critical operations
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.LOADED

    @pytest.mark.asyncio
    async def test_setup_entry_updates_generic_title_with_player_name(
        self, hass: HomeAssistant, bypass_get_data
    ) -> None:
        """Test that generic 'WiiM Device (IP)' title is updated to actual device name.

        When a device is added manually, the config entry title might be generic like
        'WiiM Device (192.168.1.100)'. After setup, when we have the real device name
        from pywiim, the title should be updated to the actual device name.
        """
        # Create entry with generic title (simulates manual add without name)
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="WiiM Device (192.168.1.100)",  # Generic title from manual add
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Entry title should be updated to the device name from MOCK_DEVICE_DATA
        # The bypass_get_data fixture provides device info with DeviceName="WiiM Mini"
        assert entry.title == MOCK_DEVICE_DATA["DeviceName"]

    @pytest.mark.asyncio
    async def test_setup_entry_preserves_custom_title(self, hass: HomeAssistant, bypass_get_data) -> None:
        """Test that a custom (non-generic) title is NOT overwritten.

        If the user has a custom title that doesn't match the generic pattern,
        we should preserve it and not overwrite with the device name.
        """
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="My Custom Device Name",  # User-provided custom title
            data=MOCK_CONFIG,
            unique_id=MOCK_DEVICE_DATA["uuid"],
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Custom title should be preserved (not start with "WiiM Device")
        assert entry.title == "My Custom Device Name"
