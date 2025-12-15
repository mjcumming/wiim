"""Tests for WiiM update platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError


class TestFirmwareUpdateEntity:
    """Test firmware update entity behavior."""

    def test_update_available_false_when_missing_device_info(self) -> None:
        """update_available should be False when not reported by player.

        latest_version should return installed_version when latest_firmware_version is None
        to ensure UpdateEntity.state is never None (which shows as "Unavailable").
        """
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.device_info = None
        coordinator.player.firmware = "Linkplay.4.8.731953"
        coordinator.player.firmware_update_available = False
        coordinator.player.latest_firmware_version = None

        entry = MagicMock(spec=ConfigEntry)
        entry.unique_id = "test-uuid"
        entry.title = "Test WiiM"

        entity = WiiMFirmwareUpdateEntity(coordinator, entry)

        assert entity.installed_version == "Linkplay.4.8.731953"
        assert entity.update_available is False
        # latest_version should return installed_version when latest_firmware_version is None
        # This ensures UpdateEntity.state is never None
        assert entity.latest_version == "Linkplay.4.8.731953"

    def test_update_available_true_with_latest_version(self) -> None:
        """update_available should be True when pywiim reports update available."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.device_info = None
        coordinator.player.firmware = "Linkplay.4.8.731953"
        coordinator.player.firmware_update_available = True
        coordinator.player.latest_firmware_version = "Linkplay.4.8.738046"

        entry = MagicMock(spec=ConfigEntry)
        entry.unique_id = "test-uuid"
        entry.title = "Test WiiM"

        entity = WiiMFirmwareUpdateEntity(coordinator, entry)

        assert entity.installed_version == "Linkplay.4.8.731953"
        assert entity.update_available is True
        assert entity.latest_version == "Linkplay.4.8.738046"

    def test_latest_version_hidden_when_no_update(self) -> None:
        """latest_version should still be exposed even if update not ready."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.device_info = None
        coordinator.player.firmware = "Linkplay.4.8.731953"
        coordinator.player.firmware_update_available = False
        coordinator.player.latest_firmware_version = "Linkplay.4.8.738046"

        entry = MagicMock(spec=ConfigEntry)
        entry.unique_id = "test-uuid"
        entry.title = "Test WiiM"

        entity = WiiMFirmwareUpdateEntity(coordinator, entry)

        assert entity.update_available is False
        assert entity.latest_version == "Linkplay.4.8.738046"

    @pytest.mark.asyncio
    async def test_async_install_calls_pywiim_install_when_supported(self) -> None:
        """async_install should call pywiim install method when supported."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.name = "Test WiiM"
        coordinator.player.device_info = None
        coordinator.player.firmware_update_available = True
        coordinator.player.latest_firmware_version = "Linkplay.4.8.738046"
        coordinator.player.supports_firmware_install = True
        coordinator.player.install_firmware_update = AsyncMock()
        coordinator.player.get_update_install_status = AsyncMock(return_value={})
        coordinator.async_refresh = AsyncMock()

        entry = MagicMock(spec=ConfigEntry)
        entry.unique_id = "test-uuid"
        entry.title = "Test WiiM"

        entity = WiiMFirmwareUpdateEntity(coordinator, entry)
        # Unit-test context: entity isn't added to HA, so avoid scheduling background tracking.
        entity._start_install_tracking = MagicMock()
        await entity.async_install(version=None, backup=False)

        coordinator.player.install_firmware_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_install_tracking_sets_in_progress(self) -> None:
        """Starting install tracking should mark the entity as in progress."""
        import asyncio
        from contextlib import suppress

        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.name = "Test WiiM"
        coordinator.player.device_info = None
        coordinator.player.firmware = "Linkplay.4.8.731953"
        coordinator.player.firmware_update_available = True
        coordinator.player.latest_firmware_version = "Linkplay.4.8.738046"
        coordinator.player.supports_firmware_install = True
        coordinator.player.get_update_install_status = AsyncMock(return_value={})
        coordinator.async_refresh = AsyncMock()

        entry = MagicMock(spec=ConfigEntry)
        entry.unique_id = "test-uuid"
        entry.title = "Test WiiM"

        entity = WiiMFirmwareUpdateEntity(coordinator, entry)
        # Provide a fake hass + no-op state write so tracking can start in unit-test context.
        entity.hass = MagicMock()
        entity.async_write_ha_state = MagicMock()

        entity._start_install_tracking()
        assert entity._attr_in_progress is True
        assert entity._install_task is not None

        entity._install_task.cancel()
        with suppress(asyncio.CancelledError):
            await entity._install_task

    @pytest.mark.asyncio
    async def test_async_install_raises_when_no_update(self) -> None:
        """async_install should raise when no update is available."""
        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"
        coordinator.player.firmware_update_available = False
        coordinator.player.latest_firmware_version = "Linkplay.4.8.738046"
        coordinator.player.supports_firmware_install = True
        coordinator.player.install_firmware_update = AsyncMock()

        entry = MagicMock(spec=ConfigEntry)
        entry.unique_id = "test-uuid"
        entry.title = "Test WiiM"

        entity = WiiMFirmwareUpdateEntity(coordinator, entry)

        with pytest.raises(HomeAssistantError):
            await entity.async_install(version=None, backup=False)

        coordinator.player.install_firmware_update.assert_not_called()


class TestUpdatePlatformSetup:
    """Test update platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_adds_entity(self) -> None:
        """async_setup_entry should add the update entity."""
        from custom_components.wiim.const import DOMAIN
        from custom_components.wiim.update import async_setup_entry

        hass = MagicMock()
        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.entry_id = "test-entry"
        config_entry.unique_id = "test-uuid"
        config_entry.title = "Test WiiM"

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.name = "Test WiiM"
        coordinator.player.supports_firmware_install = True
        hass.data = {DOMAIN: {config_entry.entry_id: {"coordinator": coordinator, "entry": config_entry}}}

        async_add_entities = MagicMock()
        await async_setup_entry(hass, config_entry, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert entities[0].__class__.__name__ == "WiiMFirmwareUpdateEntity"
