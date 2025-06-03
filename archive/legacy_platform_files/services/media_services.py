"""WiiM Media Services.

Handles all media-related service calls extracted from the main media player entity.
This follows the single responsibility principle by separating service logic
from entity state management.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from ..api import WiiMError
from ..const import EQ_PRESET_CUSTOM

if TYPE_CHECKING:
    from ..media_player import WiiMMediaPlayer

_LOGGER = logging.getLogger(__name__)


class WiiMMediaServices:
    """Service implementations for media-related operations."""

    @staticmethod
    async def play_preset(entity: WiiMMediaPlayer, preset: int) -> None:
        """Handle the play_preset service call."""
        try:
            await entity.coordinator.client.play_preset(preset)
            await entity.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to play preset on WiiM device: %s", err)
            raise

    @staticmethod
    async def play_url(entity: WiiMMediaPlayer, url: str) -> None:
        """Play a URL."""
        try:
            await entity.coordinator.client.play_url(url)
            await entity.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to play URL on WiiM device: %s", err)
            raise

    @staticmethod
    async def play_playlist(entity: WiiMMediaPlayer, playlist_url: str) -> None:
        """Play an M3U playlist."""
        try:
            await entity.coordinator.client.play_playlist(playlist_url)
            await entity.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to play playlist on WiiM device: %s", err)
            raise

    @staticmethod
    async def play_notification(entity: WiiMMediaPlayer, url: str) -> None:
        """Play a notification sound."""
        try:
            await entity.coordinator.client.play_notification(url)
            await entity.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to play notification on WiiM device: %s", err)
            raise

    @staticmethod
    async def set_eq(entity: WiiMMediaPlayer, preset: str, custom_values: list[int] | None = None) -> None:
        """Set EQ preset or custom values."""
        if preset == EQ_PRESET_CUSTOM and custom_values is None:
            raise ValueError("Custom values required for custom EQ preset")

        try:
            # Enable EQ if it's not already enabled
            if not entity.coordinator.eq_enabled:
                await entity.coordinator.client.set_eq_enabled(True)
                await asyncio.sleep(0.1)  # Small delay to ensure EQ is enabled

            if preset == EQ_PRESET_CUSTOM:
                await entity.coordinator.client.set_eq_custom(custom_values)
            else:
                await entity.coordinator.client.set_eq_preset(preset)
            await entity.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to set EQ on WiiM device: %s", err)
            raise

    @staticmethod
    async def toggle_power(entity: WiiMMediaPlayer) -> None:
        """Handle the toggle_power service call."""
        try:
            await entity.coordinator.client.toggle_power()
            await entity.coordinator.async_refresh()
        except WiiMError as err:
            _LOGGER.error("Failed to toggle power on WiiM device: %s", err)
            raise
