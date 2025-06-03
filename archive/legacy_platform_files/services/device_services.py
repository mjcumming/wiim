"""WiiM Device Services.

Handles device-specific operations like rebooting and time synchronization.
These services provide low-level device management capabilities.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..api import WiiMError

if TYPE_CHECKING:
    from ..media_player import WiiMMediaPlayer

_LOGGER = logging.getLogger(__name__)


class WiiMDeviceServices:
    """Service implementations for device-specific operations."""

    @staticmethod
    async def reboot_device(entity: WiiMMediaPlayer) -> None:
        """Reboot the speaker via entity service."""
        try:
            await entity.coordinator.client.reboot()
            _LOGGER.info("[WiiM] %s: Device reboot initiated", entity.entity_id)
        except WiiMError as err:
            _LOGGER.error("Failed to reboot WiiM device: %s", err)
            raise

    @staticmethod
    async def sync_time(entity: WiiMMediaPlayer) -> None:
        """Synchronise the speaker clock to Home Assistant time."""
        try:
            await entity.coordinator.client.sync_time()
            _LOGGER.info("[WiiM] %s: Time synchronization completed", entity.entity_id)
        except WiiMError as err:
            _LOGGER.error("Failed to sync time on WiiM device: %s", err)
            raise
