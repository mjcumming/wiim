"""Base entity class for WiiM integration - minimal HA glue only."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .data import Speaker


class WiimEntity(CoordinatorEntity):
    """Base class for all WiiM entities - minimal glue to coordinator."""

    def __init__(self, speaker: Speaker) -> None:
        """Initialize with speaker reference."""
        super().__init__(speaker.coordinator)
        self.speaker = speaker

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info from speaker."""
        return self.speaker.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.speaker.available

    async def _async_execute_command_with_refresh(self, _command_type: str) -> None:
        """Request coordinator refresh after command execution.

        Used by entities that execute commands and need immediate data refresh.
        """
        await self.coordinator.async_request_refresh()
