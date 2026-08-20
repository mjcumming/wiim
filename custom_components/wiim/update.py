"""WiiM update platform.

Exposes device firmware update availability via Home Assistant's `update` domain.

pywiim provides firmware update support via Player properties/methods:
- `player.firmware_update_available`: update downloaded & ready (bool)
- `player.latest_firmware_version`: latest available version string (str | None)
- `player.client.capabilities["supports_firmware_install"]`: whether install via API is supported (WiiM only)
- `await player.install_firmware_update()`: start installation (WiiM only)

This integration stays thin: we only expose pywiim's state and call its APIs.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .capability_flags import client_has_capability
from .const import DOMAIN
from .coordinator import WiiMCoordinator
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)

_INSTALL_POLL_INTERVAL_SECONDS = 10
_INSTALL_TIMEOUT_SECONDS = 20 * 60  # 20 minutes


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM firmware update entity from a config entry.

    Creates update entity only for devices that support firmware updates via API.
    This matches the platform enablement check in __init__.py which only enables
    UPDATE platform when supports_firmware_install is True.

    Per pywiim guide:
    - WiiM devices: support API installation (``supports_firmware_install`` in client capabilities)
    - Other devices: require reboot to install (not supported via HA update entity)
    """
    coordinator: WiiMCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    player = coordinator.player

    # Only create update entity for devices that support firmware installation via API
    # This matches the platform enablement check in __init__.py
    if not client_has_capability(player, "supports_firmware_install"):
        device_name = player.name or config_entry.title or "WiiM Speaker"
        _LOGGER.debug(
            "Skipping firmware update entity for %s (device does not support API-based firmware installation)",
            device_name,
        )
        return

    async_add_entities([WiiMFirmwareUpdateEntity(coordinator, config_entry)])
    device_name = player.name or config_entry.title or "WiiM Speaker"
    _LOGGER.debug("Created firmware update entity for %s", device_name)


class WiiMFirmwareUpdateEntity(WiimEntity, UpdateEntity):
    """Firmware update availability for a WiiM device."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    # Entity category will be CONFIG (default) since we support INSTALL feature
    # This follows HA guidelines: entities with INSTALL feature should be CONFIG category
    _attr_has_entity_name = True
    _attr_icon = "mdi:update"

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize firmware update entity."""
        super().__init__(coordinator, config_entry)
        uuid = config_entry.unique_id or coordinator.player.host
        # Keep stable unique_id to avoid orphaning/duplicating entities in HA.
        # Existing entity registry entries use the `_fw_update` suffix.
        self._attr_unique_id = f"{uuid}_fw_update"
        self._attr_name = "Firmware Update"

        # INSTALL is always supported since we only create this entity when
        # ``supports_firmware_install`` is set on ``player.client.capabilities``.
        # PROGRESS is reported natively via ``in_progress`` / ``update_percentage``.
        # Home Assistant's ``async_install_with_progress`` always sets
        # ``_attr_in_progress = False`` when ``async_install`` returns, so tracking
        # continues in a config-entry background task (started after that finally
        # runs) and we re-assert progress there.
        self._attr_supported_features = UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
        self._installing = False
        self._install_percentage: int | None = None
        self._install_task: asyncio.Task[None] | None = None
        self._saved_update_interval: timedelta | None = None

    @property
    def installed_version(self) -> str | None:  # type: ignore[override]
        """Return the currently installed firmware string.

        Tries multiple sources to ensure we always have a firmware version when available.
        This prevents the entity from being disabled due to None state.

        CRITICAL: Must return a non-None value when device is available, otherwise
        UpdateEntity.state will be None and entity will be disabled.
        """
        # Try device_info.firmware first (most reliable)
        if self.player.device_info and hasattr(self.player.device_info, "firmware"):
            firmware = self.player.device_info.firmware
            if firmware:
                fw = str(firmware).strip()
                if fw and fw not in {"", "0", "-", "unknown"}:
                    return fw

        # Fall back to player.firmware (direct attribute)
        firmware = getattr(self.player, "firmware", None)
        if firmware:
            fw = str(firmware).strip()
            if fw and fw not in {"", "0", "-", "unknown"}:
                return fw

        return None

    @property
    def latest_version(self) -> str | None:  # type: ignore[override]
        """Return the latest available firmware version (if known).

        If no update is available, return installed_version to ensure state is never None.
        This matches the pattern used by other Home Assistant update integrations.
        """
        latest = getattr(self.player, "latest_firmware_version", None)
        if latest is None:
            # Return installed_version when no update info available
            # This ensures UpdateEntity.state is never None (which shows as "Unavailable")
            return self.installed_version
        latest_str = str(latest).strip()
        if latest_str in {"", "0", "-", "unknown"}:
            # Invalid latest version, fall back to installed_version
            return self.installed_version
        return latest_str

    @property
    def update_available(self) -> bool:  # type: ignore[override]
        """Return True if an update is available and ready (per pywiim)."""
        return bool(getattr(self.player, "firmware_update_available", False))

    @property
    def release_notes(self) -> str | None:  # type: ignore[override]
        """Return release notes for the latest version (not provided by device)."""
        return None

    @property
    def in_progress(self) -> bool:  # type: ignore[override]
        """Return True while a firmware install is running on the device."""
        return self._installing

    @property
    def update_percentage(self) -> int | float | None:  # type: ignore[override]
        """Return flash percentage, or None for an indeterminate installer."""
        if not self._installing:
            return None
        return self._install_percentage

    @property
    def available(self) -> bool:
        """Return True while firmware install is running.

        The speaker often reboots (or stops answering) mid-install. Without this,
        coordinator failure would hide the update dialog before flashing finishes.
        """
        if self._installing:
            return True
        return super().available

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:  # type: ignore[override]
        """Start firmware installation.

        ``getMvRemoteUpdateStart`` returns immediately; flashing and reboot take
        minutes. Home Assistant may cancel this service call when the UI times
        out, so tracking runs as a config-entry background task. ``in_progress``
        stays True until the installed firmware string actually changes.
        """
        if not self.update_available:
            raise HomeAssistantError("No firmware update is ready to install.")

        device_name = self.player.name or self._config_entry.title or "WiiM Speaker"

        if not client_has_capability(self.player, "supports_firmware_install"):
            raise HomeAssistantError(
                "Firmware installation via API is not supported on this device. "
                "The update is downloaded and ready. Please reboot the device to install."
            )

        if self._installing:
            raise HomeAssistantError("Firmware installation already in progress.")

        self._set_install_progress_state(True)

        try:
            await self.player.install_firmware_update()
        except Exception as err:  # noqa: BLE001
            self._set_install_progress_state(False)
            raise HomeAssistantError(f"Failed to start firmware update install: {err}") from err

        _LOGGER.info("Firmware installation started for %s", device_name)
        # eager_start=False so this task starts after HA's install finally block
        # has cleared _attr_in_progress; tracking immediately sets it True again.
        self._install_task = self._config_entry.async_create_background_task(
            self.hass,
            self._async_track_install(),
            f"{device_name} firmware install",
            eager_start=False,
        )

    def _apply_install_progress(self, status: dict[str, Any]) -> None:
        """Surface flash progress from pywiim when the device is actually burning.

        Idle/downloading devices report ``progress: "0"``; treating that as 0%
        would look stuck. HA shows an indeterminate bar when percentage is None.
        """
        progress_raw = status.get("progress")
        if progress_raw is None:
            return
        try:
            progress = int(str(progress_raw).strip())
        except ValueError:
            return
        if 1 <= progress <= 100 and progress != self._install_percentage:
            self._install_percentage = progress
            self._attr_update_percentage = progress
            self.async_write_ha_state()

    def _set_install_progress_state(self, installing: bool, percentage: int | None = None) -> None:
        """Publish install progress using both the local flag and HA's _attr cache."""
        self._installing = installing
        if installing:
            self._install_percentage = percentage
            self._attr_in_progress = True
            self._attr_update_percentage = percentage
        else:
            self._install_percentage = None
            self._attr_in_progress = False
            self._attr_update_percentage = None
        self.async_write_ha_state()

    def _pause_coordinator_polling(self) -> None:
        """Stop 5s coordinator polls so they cannot cancel in-flight OTA requests."""
        if self._saved_update_interval is None:
            self._saved_update_interval = self.coordinator.update_interval
        self.coordinator.update_interval = None

    def _resume_coordinator_polling(self) -> None:
        """Restore coordinator polling after firmware install tracking stops."""
        saved = self._saved_update_interval
        self._saved_update_interval = None
        if saved is None:
            return
        self.coordinator.update_interval = saved

    async def _async_track_install(self) -> None:
        """Poll pywiim for install progress until firmware version changes."""
        start_firmware = self.installed_version
        device_name = self.player.name or self._config_entry.title or "WiiM Speaker"
        # Re-assert after HA's async_install_with_progress finally cleared _attr_in_progress.
        self._set_install_progress_state(True, self._install_percentage)
        self._pause_coordinator_polling()

        try:
            async with asyncio.timeout(_INSTALL_TIMEOUT_SECONDS):
                while True:
                    try:
                        status = await self.player.get_update_install_status()
                        if isinstance(status, dict):
                            self._apply_install_progress(status)
                    except Exception:  # noqa: BLE001
                        # Device may be rebooting/unreachable; keep polling.
                        pass

                    try:
                        # Regular coordinator polls skip device_info (firmware / VersionUpdate).
                        # A full refresh is required to see the new firmware after OTA.
                        await self.player.refresh(full=True)
                        self.coordinator.async_set_updated_data({"player": self.player})
                    except Exception:  # noqa: BLE001
                        pass

                    current_firmware = self.installed_version
                    if current_firmware and start_firmware and current_firmware != start_firmware:
                        _LOGGER.info(
                            "Firmware installation finished for %s (%s -> %s)",
                            device_name,
                            start_firmware,
                            current_firmware,
                        )
                        return

                    await asyncio.sleep(_INSTALL_POLL_INTERVAL_SECONDS)
        except TimeoutError:
            _LOGGER.warning(
                "[%s] Firmware install tracking timed out (still on %s)",
                device_name,
                self.installed_version,
            )
        except asyncio.CancelledError:
            _LOGGER.info("Firmware install tracking cancelled for %s", device_name)
            raise
        finally:
            self._resume_coordinator_polling()
            self._set_install_progress_state(False)
            _LOGGER.debug(
                "Firmware install tracking stopped for %s (installed %s)",
                device_name,
                self.installed_version,
            )

    # Some HA type-checkers/pylint versions expect a synchronous `install` method.
    # Provide it as a thin wrapper to satisfy tooling without changing behavior.
    def install(self, version: str | None, backup: bool, **kwargs: Any) -> None:  # type: ignore[override]
        """Sync wrapper for firmware installation (not supported)."""
        raise HomeAssistantError("Firmware installation must be triggered from Home Assistant asynchronously.")
