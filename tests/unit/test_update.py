"""Tests for WiiM update platform."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError


def _attach_client_capabilities(player: MagicMock, capabilities: dict) -> None:
    player.client = MagicMock()
    player.client.capabilities = capabilities


def _firmware_entity(
    *,
    update_available: bool = True,
    firmware: str = "Linkplay.4.8.731953",
    latest: str = "Linkplay.4.8.738046",
    supports_install: bool = True,
) -> tuple[MagicMock, MagicMock, object]:
    from custom_components.wiim.update import WiiMFirmwareUpdateEntity

    coordinator = MagicMock()
    coordinator.async_refresh = AsyncMock()
    coordinator.last_update_success = True
    coordinator.player = MagicMock()
    coordinator.player.host = "192.168.1.100"
    coordinator.player.name = "Test WiiM"
    coordinator.player.device_info = None
    coordinator.player.firmware = firmware
    coordinator.player.firmware_update_available = update_available
    coordinator.player.latest_firmware_version = latest
    _attach_client_capabilities(coordinator.player, {"supports_firmware_install": supports_install})
    coordinator.player.install_firmware_update = AsyncMock()
    coordinator.player.get_update_install_status = AsyncMock(return_value={})
    coordinator.player.refresh = AsyncMock()
    coordinator.async_set_updated_data = MagicMock()
    coordinator.update_interval = timedelta(seconds=5)

    entry = MagicMock(spec=ConfigEntry)
    entry.unique_id = "test-uuid"
    entry.title = "Test WiiM"

    entity = WiiMFirmwareUpdateEntity(coordinator, entry)
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()
    def _bg(_hass: object, coro: object, _name: str, eager_start: bool = True) -> MagicMock:
        if hasattr(coro, "close"):
            coro.close()
        return MagicMock()

    entry.async_create_background_task = MagicMock(side_effect=_bg)
    return coordinator, entry, entity


class TestFirmwareUpdateEntity:
    """Test firmware update entity behavior."""

    def test_unique_id_and_supported_features(self) -> None:
        """Entity should keep stable unique_id and expose INSTALL|PROGRESS."""
        from homeassistant.components.update import UpdateEntityFeature

        from custom_components.wiim.update import WiiMFirmwareUpdateEntity

        coordinator = MagicMock()
        coordinator.player = MagicMock()
        coordinator.player.host = "192.168.1.100"

        entry = MagicMock(spec=ConfigEntry)
        entry.unique_id = "test-uuid"
        entry.title = "Test WiiM"

        entity = WiiMFirmwareUpdateEntity(coordinator, entry)

        assert entity.unique_id == "test-uuid_fw_update"
        assert UpdateEntityFeature.INSTALL in entity.supported_features
        assert UpdateEntityFeature.PROGRESS in entity.supported_features

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
    async def test_async_install_starts_background_tracking(self) -> None:
        """async_install should start the device update then return while still installing."""
        coordinator, entry, entity = _firmware_entity()
        seen_in_progress: list[bool] = []

        async def _install() -> None:
            seen_in_progress.append(entity.in_progress)

        coordinator.player.install_firmware_update = AsyncMock(side_effect=_install)

        await entity.async_install(version=None, backup=False)

        assert seen_in_progress == [True]
        assert entity.in_progress is True
        coordinator.player.install_firmware_update.assert_called_once()
        entry.async_create_background_task.assert_called_once()
        assert entry.async_create_background_task.call_args.kwargs["eager_start"] is False

    @pytest.mark.asyncio
    async def test_async_install_raises_when_already_in_progress(self) -> None:
        """A second install click should fail while the first is still running."""
        coordinator, _entry, entity = _firmware_entity()
        entity._installing = True

        with pytest.raises(HomeAssistantError, match="already in progress"):
            await entity.async_install(version=None, backup=False)

        coordinator.player.install_firmware_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_install_clears_in_progress_when_start_fails(self) -> None:
        """in_progress should clear if the device rejects the start command."""
        coordinator, _entry, entity = _firmware_entity()
        coordinator.player.install_firmware_update = AsyncMock(side_effect=RuntimeError("busy"))

        with pytest.raises(HomeAssistantError, match="Failed to start firmware update install"):
            await entity.async_install(version=None, backup=False)

        assert entity.in_progress is False

    def test_available_stays_true_during_install(self) -> None:
        """Entity should stay available while installing even if the coordinator fails."""
        coordinator, _entry, entity = _firmware_entity()
        coordinator.last_update_success = False

        assert entity.available is False

        entity._installing = True
        assert entity.available is True

    def test_apply_install_progress_ignores_idle_zero(self) -> None:
        """Idle devices report progress 0; that must not show as 0% in HA."""
        _coordinator, _entry, entity = _firmware_entity()
        entity._installing = True

        entity._apply_install_progress({"progress": "0"})
        assert entity.update_percentage is None

        entity._apply_install_progress({"progress": "50"})
        assert entity.update_percentage == 50

        entity._apply_install_progress({"progress": "not-a-number"})
        assert entity.update_percentage == 50

    @pytest.mark.asyncio
    async def test_async_track_install_reports_progress_and_completes_on_firmware_change(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Install tracking should update progress and finish when firmware changes."""
        import custom_components.wiim.update as update_mod

        monkeypatch.setattr(update_mod, "_INSTALL_POLL_INTERVAL_SECONDS", 0)
        monkeypatch.setattr(update_mod, "_INSTALL_TIMEOUT_SECONDS", 2)

        coordinator, _entry, entity = _firmware_entity()
        coordinator.player.get_update_install_status = AsyncMock(return_value={"progress": "50"})

        async def _refresh_side_effect(*_args: object, **_kwargs: object) -> None:
            coordinator.player.firmware = "Linkplay.4.8.738046"

        coordinator.player.refresh = AsyncMock(side_effect=_refresh_side_effect)
        coordinator.async_set_updated_data = MagicMock()

        entity._installing = True
        await entity._async_track_install()

        assert entity.update_percentage is None
        assert entity.in_progress is False
        assert coordinator.update_interval == timedelta(seconds=5)
        assert entity.async_write_ha_state.call_count >= 1

    @pytest.mark.asyncio
    async def test_async_track_install_does_not_finish_when_update_flag_clears(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Clearing VersionUpdate without a new firmware string is not completion.

        During OTA the device may omit NewVer / VersionUpdate. latest_version then
        falls back to installed_version, which previously ended tracking early.
        """
        import custom_components.wiim.update as update_mod

        monkeypatch.setattr(update_mod, "_INSTALL_POLL_INTERVAL_SECONDS", 0)
        monkeypatch.setattr(update_mod, "_INSTALL_TIMEOUT_SECONDS", 0.05)

        coordinator, _entry, entity = _firmware_entity()
        coordinator.player.firmware_update_available = True

        async def _refresh_side_effect(*_args: object, **_kwargs: object) -> None:
            coordinator.player.firmware_update_available = False
            coordinator.player.latest_firmware_version = None

        coordinator.player.refresh = AsyncMock(side_effect=_refresh_side_effect)
        coordinator.async_set_updated_data = MagicMock()

        entity._installing = True
        await entity._async_track_install()

        assert coordinator.player.refresh.call_count >= 2
        coordinator.player.refresh.assert_called_with(full=True)
        assert coordinator.player.firmware == "Linkplay.4.8.731953"
        assert entity.in_progress is False
        assert coordinator.update_interval == timedelta(seconds=5)

    @pytest.mark.asyncio
    async def test_async_track_install_pauses_coordinator_polling(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OTA tracking should pause coordinator polls so they cannot cancel it."""
        import custom_components.wiim.update as update_mod

        monkeypatch.setattr(update_mod, "_INSTALL_POLL_INTERVAL_SECONDS", 0)
        monkeypatch.setattr(update_mod, "_INSTALL_TIMEOUT_SECONDS", 2)

        coordinator, _entry, entity = _firmware_entity()
        seen_intervals: list[object] = []

        async def _refresh_side_effect(*_args: object, **_kwargs: object) -> None:
            seen_intervals.append(coordinator.update_interval)
            coordinator.player.firmware = "Linkplay.4.8.738046"

        coordinator.player.refresh = AsyncMock(side_effect=_refresh_side_effect)
        entity._installing = True
        await entity._async_track_install()

        assert seen_intervals == [None]
        assert coordinator.update_interval == timedelta(seconds=5)

    @pytest.mark.asyncio
    async def test_async_track_install_clears_progress_when_cancelled(self) -> None:
        """Config-entry unload should clear in_progress and restore polling."""
        coordinator, _entry, entity = _firmware_entity()
        coordinator.player.get_update_install_status = AsyncMock(side_effect=asyncio.CancelledError)

        entity._installing = True
        with pytest.raises(asyncio.CancelledError):
            await entity._async_track_install()

        assert entity.in_progress is False
        assert coordinator.update_interval == timedelta(seconds=5)

    @pytest.mark.asyncio
    async def test_async_install_raises_when_no_update(self) -> None:
        """async_install should raise when no update is available."""
        coordinator, _entry, entity = _firmware_entity(update_available=False)

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
        _attach_client_capabilities(coordinator.player, {"supports_firmware_install": True})
        hass.data = {DOMAIN: {config_entry.entry_id: {"coordinator": coordinator, "entry": config_entry}}}

        async_add_entities = MagicMock()
        await async_setup_entry(hass, config_entry, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert entities[0].__class__.__name__ == "WiiMFirmwareUpdateEntity"

    @pytest.mark.asyncio
    async def test_async_setup_entry_skips_when_not_supported(self) -> None:
        """async_setup_entry should not add entity when firmware install unsupported."""
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
        _attach_client_capabilities(coordinator.player, {"supports_firmware_install": False})
        hass.data = {DOMAIN: {config_entry.entry_id: {"coordinator": coordinator, "entry": config_entry}}}

        async_add_entities = MagicMock()
        await async_setup_entry(hass, config_entry, async_add_entities)

        async_add_entities.assert_not_called()
