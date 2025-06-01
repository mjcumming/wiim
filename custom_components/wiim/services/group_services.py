"""WiiM Group Services.

Handles all group management operations extracted from the main media player entity.
This follows the single responsibility principle by separating group logic
from entity state management.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..media_player import WiiMMediaPlayer

_LOGGER = logging.getLogger(__name__)


class WiiMGroupServices:
    """Service implementations for group management operations."""

    @staticmethod
    async def create_group_with_members(entity: WiiMMediaPlayer, group_members: list[str]) -> None:
        """Create a new group with specified members (this device as master)."""
        _LOGGER.info("[WiiM] %s: Creating group with members: %s", entity.entity_id, group_members)

        # Ensure we include ourselves as the master
        all_members = [entity.entity_id] + [m for m in group_members if m != entity.entity_id]
        await entity.async_join(all_members)

    @staticmethod
    async def add_to_group(entity: WiiMMediaPlayer, target_entity: str) -> None:
        """Add another device to this device's group."""
        _LOGGER.info("[WiiM] %s: Adding %s to group", entity.entity_id, target_entity)

        # Get current group members and add the new one
        current_members = list(entity.group_members) or [entity.entity_id]
        if target_entity not in current_members:
            current_members.append(target_entity)

        await entity.async_join(current_members)

    @staticmethod
    async def remove_from_group(entity: WiiMMediaPlayer, target_entity: str) -> None:
        """Remove a device from this device's group."""
        _LOGGER.info("[WiiM] %s: Removing %s from group", entity.entity_id, target_entity)

        # Import here to avoid circular imports
        from ..media_player import _find_coordinator

        # Find the target coordinator and make it leave
        target_coord = _find_coordinator(entity.hass, target_entity)
        if target_coord:
            await target_coord.leave_wiim_group()
            await entity.coordinator.async_request_refresh()
            await target_coord.async_request_refresh()
        else:
            _LOGGER.warning(
                "[WiiM] %s: Could not find coordinator for %s",
                entity.entity_id,
                target_entity,
            )

    @staticmethod
    async def disband_group(entity: WiiMMediaPlayer) -> None:
        """Disband the entire group."""
        _LOGGER.info("[WiiM] %s: Disbanding group", entity.entity_id)

        if entity.coordinator.client.is_master:
            await entity.coordinator.delete_wiim_group()
        else:
            # If not master, just leave the group
            await entity.coordinator.leave_wiim_group()

        await entity.coordinator.async_request_refresh()
