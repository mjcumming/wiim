"""WiiM Media Controller - Group Management Module.

This module handles all group-related functionality including:
- Join/leave group operations with validation
- Entity ID to Speaker object resolution
- Group member tracking and relationship management
- Master/slave group coordination

Extracted from media_controller.py as part of Phase 2 refactor to create focused,
maintainable modules following natural code boundaries.

Following the successful API refactor pattern with logical cohesion over arbitrary size limits.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from .data import Speaker

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "MediaControllerGroupMixin",
]


class MediaControllerGroupMixin:
    """Mixin for group management operations."""

    # ===== GROUP MANAGEMENT =====

    async def join_group(self, group_members: list[str]) -> None:
        """HA native join with WiiM multiroom backend.

        Args:
            group_members: List of entity IDs to group with
        """
        if not group_members:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.debug("join_group called with an empty list – treating as leave_group request for %s", speaker.name)
            await self.leave_group()
            return
        try:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            hass = self.hass  # type: ignore[attr-defined]
            logger = self._logger  # type: ignore[attr-defined]
            logger.debug("Joining group with members: %s", group_members)

            # Validate and resolve entity IDs to Speaker objects using new architecture
            from .data import find_speaker_by_uuid, get_all_speakers

            all_speakers = get_all_speakers(hass)
            speakers = []

            # Resolve each supplied entity_id to a Speaker object via the
            # entity-registry → unique_id → UUID mapping.  Slug-based fallbacks
            # were removed – during beta we assume all entities expose a valid
            # unique_id that matches the speaker UUID.

            from homeassistant.helpers import entity_registry as er

            ent_reg = er.async_get(hass)

            for entity_id in group_members:
                reg_entry = ent_reg.async_get(entity_id)
                if reg_entry and reg_entry.unique_id:
                    # Entity unique_id is stored as "wiim_<uuid>". Strip the prefix if present
                    unique_id = reg_entry.unique_id
                    if unique_id.startswith("wiim_"):
                        unique_id = unique_id[len("wiim_") :]

                    speaker_match = find_speaker_by_uuid(hass, unique_id)
                    if speaker_match:
                        speakers.append(speaker_match)
                    else:
                        logger.debug(
                            "Entity '%s' unique_id '%s' not found among registered speakers",
                            entity_id,
                            reg_entry.unique_id,
                        )
                else:
                    logger.debug("Entity '%s' not found in registry or has no unique_id", entity_id)

            # ------------------------------------------------------------------
            # Unit-test compatibility & graceful degradation
            # ------------------------------------------------------------------
            # Older unit-tests patch `speaker.resolve_entity_ids_to_speakers` to
            # provide the mapping directly instead of going through the entity
            # registry.  If our registry-based resolution did not yield any
            # matches, try that fallback before giving up.

            if not speakers and hasattr(speaker, "resolve_entity_ids_to_speakers"):
                try:
                    speakers = speaker.resolve_entity_ids_to_speakers(group_members) or []
                    logger.debug("Fallback resolve_entity_ids_to_speakers returned %d speakers", len(speakers))
                except Exception as err:  # pragma: no cover – safety
                    logger.debug("Fallback resolver raised error: %s", err)

            if not speakers:
                logger.warning("No valid speakers found for entity IDs: %s", group_members)
                raise HomeAssistantError(
                    f"No valid speakers found in group member list {group_members}. Available: {len(all_speakers)} speakers"
                )

            # Filter out self from the list if present
            target_speakers = [s for s in speakers if s is not speaker]
            if not target_speakers:
                logger.warning("No other speakers to join with")
                return

            # Use existing Speaker group join method (this speaker becomes master)
            await speaker.async_join_group(target_speakers)

            logger.info("Successfully joined group with %d speakers", len(target_speakers))

        except Exception as err:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.error("Failed to join group: %s", err)
            raise HomeAssistantError(
                "Failed to create group with {} on {}: {}".format(", ".join(group_members), speaker.name, err)
            ) from err

    async def leave_group(self) -> None:
        """Leave current group."""
        try:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.debug("Leaving group for %s", speaker.name)

            # Use existing Speaker group leave method
            await speaker.async_leave_group()

            logger.info("Successfully left group")

        except Exception as err:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.error("Failed to leave group: %s", err)
            raise HomeAssistantError(f"Failed to remove {speaker.name} from group: {err}") from err

    def get_group_members(self) -> list[str]:
        """Get group member entity IDs."""
        try:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            # Use existing Speaker method to get group member entity IDs
            return speaker.get_group_member_entity_ids()
        except Exception as err:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.error("Failed to get group members: %s", err)
            return []

    def get_group_leader(self) -> str | None:
        """Get group leader entity ID."""
        try:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            # In WiiM groups, the master is the leader
            if speaker.role == "master":
                # This speaker is the leader - return entity ID based on our UUID
                # Following HA naming convention: media_player.{uuid_with_underscores}
                entity_id = f"media_player.{speaker.uuid.replace('-', '_').lower()}"
                return entity_id
            elif speaker.role == "slave" and speaker.coordinator_speaker:
                # Find the master's entity ID
                master_uuid = speaker.coordinator_speaker.uuid
                entity_id = f"media_player.{master_uuid.replace('-', '_').lower()}"
                return entity_id
            # Solo speakers have no leader
            return None
        except Exception as err:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.error("Failed to get group leader: %s", err)
            return None
