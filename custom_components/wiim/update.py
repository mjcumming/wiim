"""WiiM update platform.

Exposes device firmware update availability via Home Assistant's `update` domain.

pywiim provides firmware update support via Player properties/methods:
- `player.firmware_update_available`: update downloaded & ready (bool)
- `player.latest_firmware_version`: latest available version string (str | None)
- `player.supports_firmware_install`: whether install via API is supported (bool; WiiM only)
- `await player.install_firmware_update()`: start installation (WiiM only)

This integration stays thin: we only expose pywiim's state and call its APIs.
"""

from __future__ import annotations

import asyncio
import logging
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
    - WiiM devices: support API installation (supports_firmware_install = True)
    - Other devices: require reboot to install (not supported via HA update entity)
    """
    coordinator: WiiMCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    player = coordinator.player

    # Only create update entity for devices that support firmware installation via API
    # This matches the platform enablement check in __init__.py
    if not getattr(player, "supports_firmware_install", False):
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

        # Set supported features: INSTALL is always supported since we only create
        # this entity when supports_firmware_install is True (checked in async_setup_entry)
        # PROGRESS allows us to keep HA UI in an "installing" state while the device
        # reboots/installs (otherwise HA clears in_progress as soon as async_install returns).
        self._attr_supported_features = UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS

        self._install_task: asyncio.Task[None] | None = None

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

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:  # type: ignore[override]
        """Install the update.

        For WiiM devices: Uses API installation via install_firmware_update()
        For other devices: Update is already downloaded, reboot required (not supported via HA)
        """
        if not self.update_available:
            raise HomeAssistantError("No firmware update is ready to install.")

        device_name = self.player.name or self._config_entry.title or "WiiM Speaker"

        # Check if device supports API installation
        if not getattr(self.player, "supports_firmware_install", False):
            raise HomeAssistantError(
                "Firmware installation via API is not supported on this device. "
                "The update is downloaded and ready. Please reboot the device to install."
            )

        # If we already have an install task running, don't start another.
        if self._install_task and not self._install_task.done():
            raise HomeAssistantError("Firmware installation already in progress.")

        try:
            _LOGGER.info("Starting firmware installation for %s", device_name)
            await self.player.install_firmware_update()
            _LOGGER.info("Firmware installation started for %s", device_name)
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Failed to start firmware update install: {err}") from err

        # Start background tracking so HA UI reflects that installation is ongoing.
        # We intentionally do NOT block this service call for minutes while the device
        # installs/reboots; instead we mark in-progress and poll for completion.
        self._start_install_tracking()

    def _start_install_tracking(self) -> None:
        """Start background polling for firmware install progress/completion."""
        if self._install_task and not self._install_task.done():
            return

        self._attr_in_progress = True
        self._attr_update_percentage = None
        self.async_write_ha_state()
        self._install_task = asyncio.create_task(self._async_track_install())

    async def _async_track_install(self) -> None:
        """Poll pywiim for install progress and refresh after reboot."""
        start_firmware = self.installed_version

        try:
            async with asyncio.timeout(_INSTALL_TIMEOUT_SECONDS):
                while True:
                    # Attempt to read install progress from pywiim.
                    try:
                        status: dict[str, Any] = await self.player.get_update_install_status()
                        progress_raw = status.get("progress")
                        if progress_raw is not None:
                            try:
                                progress = int(str(progress_raw).strip())
                            except ValueError:
                                progress = None
                            if progress is not None and 0 <= progress <= 100:
                                self._attr_update_percentage = progress
                                self.async_write_ha_state()
                    except Exception:  # noqa: BLE001
                        # Device may be rebooting/unreachable; keep polling.
                        pass

                    # Refresh coordinator/player state; device may be rebooting.
                    try:
                        await self.coordinator.async_refresh()
                    except Exception:  # noqa: BLE001
                        pass

                    # Completion conditions:
                    # - firmware version changed
                    # - or update flag cleared and latest==installed
                    current_firmware = self.installed_version
                    if current_firmware and start_firmware and current_firmware != start_firmware:
                        return
                    if not self.update_available and self.latest_version == self.installed_version:
                        return

                    await asyncio.sleep(_INSTALL_POLL_INTERVAL_SECONDS)
        except TimeoutError:
            _LOGGER.warning("[%s] Firmware install tracking timed out", self.name)
        finally:
            self._attr_in_progress = False
            self._attr_update_percentage = None
            self.async_write_ha_state()

    # Some HA type-checkers/pylint versions expect a synchronous `install` method.
    # Provide it as a thin wrapper to satisfy tooling without changing behavior.
    def install(self, version: str | None, backup: bool, **kwargs: Any) -> None:  # type: ignore[override]
        """Sync wrapper for firmware installation (not supported)."""
        raise HomeAssistantError("Firmware installation must be triggered from Home Assistant asynchronously.")
