"""WiiM Diagnostic Services.

Handles all diagnostic and maintenance operations extracted from the main media player entity.
These services help troubleshoot entity issues and maintain a clean entity registry.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..const import DOMAIN

if TYPE_CHECKING:
    from ..media_player import WiiMMediaPlayer

_LOGGER = logging.getLogger(__name__)


class WiiMDiagnosticServices:
    """Service implementations for diagnostic and maintenance operations."""

    @staticmethod
    async def diagnose_entities(entity: WiiMMediaPlayer) -> None:
        """Diagnose WiiM entities and coordinators for troubleshooting."""
        hass = entity.hass
        _LOGGER.info("[WiiM] %s: Starting entity diagnostics", entity.entity_id)

        # Get all WiiM entities from entity registry
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)

        wiim_entities = []
        stale_entities = []
        active_coordinators = []

        # Collect all WiiM entities
        for entry in ent_reg.entities.values():
            if entry.domain == "media_player" and entry.platform == DOMAIN:
                wiim_entities.append(
                    {
                        "entity_id": entry.entity_id,
                        "unique_id": entry.unique_id,
                        "name": entry.name or entry.original_name,
                        "disabled": entry.disabled_by is not None,
                    }
                )

        # Collect active coordinators
        for coord in hass.data[DOMAIN].values():
            if hasattr(coord, "client"):
                active_coordinators.append(
                    {
                        "host": coord.client.host,
                        "has_data": coord.data is not None,
                        "device_name": coord.data.get("status", {}).get("DeviceName") if coord.data else None,
                        "role": coord.data.get("role") if coord.data else None,
                    }
                )

        # Find stale entities (entities without corresponding coordinators)
        coordinator_hosts = {coord["host"] for coord in active_coordinators}

        for entity_entry in wiim_entities:
            if entity_entry["unique_id"] not in coordinator_hosts:
                # Check if entity still exists in HA state
                entity_state = hass.states.get(entity_entry["entity_id"])
                stale_entities.append(
                    {
                        **entity_entry,
                        "state_exists": entity_state is not None,
                        "state": entity_state.state if entity_state else None,
                    }
                )

        # Log comprehensive diagnostics
        _LOGGER.info(
            "[WiiM] %s: Diagnostics Results:\n"
            "  Total WiiM Entities: %d\n"
            "  Active Coordinators: %d\n"
            "  Potentially Stale Entities: %d\n"
            "\nActive Coordinators:\n%s\n"
            "\nAll WiiM Entities:\n%s\n"
            "\nPotentially Stale Entities:\n%s",
            entity.entity_id,
            len(wiim_entities),
            len(active_coordinators),
            len(stale_entities),
            "\n".join(
                f"  - {coord['host']}: {coord['device_name']} ({coord['role']})" for coord in active_coordinators
            ),
            "\n".join(
                f"  - {ent['entity_id']}: {ent['name']} (unique_id: {ent['unique_id']}, disabled: {ent['disabled']})"
                for ent in wiim_entities
            ),
            (
                "\n".join(
                    f"  - {ent['entity_id']}: {ent['name']} (state_exists: {ent['state_exists']}, state: {ent['state']})"
                    for ent in stale_entities
                )
                if stale_entities
                else "  None"
            ),
        )

        if stale_entities:
            _LOGGER.warning(
                "[WiiM] %s: Found %d potentially stale entities. "
                "These entities exist in the registry but have no active coordinator. "
                "This usually happens when devices are removed or renamed. "
                "Consider removing these entities from Home Assistant if they're no longer needed.",
                entity.entity_id,
                len(stale_entities),
            )
        else:
            _LOGGER.info("[WiiM] %s: All WiiM entities appear to be healthy!", entity.entity_id)

    @staticmethod
    async def cleanup_stale_entities(entity: WiiMMediaPlayer, dry_run: bool = True) -> None:
        """Clean up stale WiiM entities (with optional dry-run mode)."""
        hass = entity.hass
        _LOGGER.info("[WiiM] %s: Starting stale entity cleanup (dry_run=%s)", entity.entity_id, dry_run)

        # Get all WiiM entities from entity registry
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)

        wiim_entities = []
        stale_entities = []

        # Collect all WiiM entities
        for entry in ent_reg.entities.values():
            if entry.domain == "media_player" and entry.platform == DOMAIN:
                wiim_entities.append(entry)

        # Collect active coordinators
        coordinator_hosts = set()
        for coord in hass.data[DOMAIN].values():
            if hasattr(coord, "client"):
                coordinator_hosts.add(coord.client.host)

        # Find stale entities
        for entity_entry in wiim_entities:
            if entity_entry.unique_id not in coordinator_hosts:
                # Additional check: see if entity state exists and is unavailable
                entity_state = hass.states.get(entity_entry.entity_id)
                is_stale = (
                    entity_state is None
                    or entity_state.state in ("unavailable", "unknown")
                    or entity_state.attributes.get("restored", False)
                )

                if is_stale:
                    stale_entities.append(entity_entry)

        if not stale_entities:
            _LOGGER.info("[WiiM] %s: No stale entities found!", entity.entity_id)
            return

        _LOGGER.info(
            "[WiiM] %s: Found %d stale entities to %s",
            entity.entity_id,
            len(stale_entities),
            "remove" if not dry_run else "potentially remove",
        )

        removed_count = 0
        for entity_entry in stale_entities:
            entity_name = entity_entry.name or entity_entry.original_name or entity_entry.entity_id

            if dry_run:
                _LOGGER.info(
                    "[WiiM] %s: [DRY RUN] Would remove stale entity: %s (%s)",
                    entity.entity_id,
                    entity_entry.entity_id,
                    entity_name,
                )
            else:
                try:
                    # Remove the entity from registry
                    ent_reg.async_remove(entity_entry.entity_id)
                    removed_count += 1
                    _LOGGER.info(
                        "[WiiM] %s: Removed stale entity: %s (%s)",
                        entity.entity_id,
                        entity_entry.entity_id,
                        entity_name,
                    )
                except Exception as remove_err:
                    _LOGGER.error(
                        "[WiiM] %s: Failed to remove stale entity %s: %s",
                        entity.entity_id,
                        entity_entry.entity_id,
                        remove_err,
                    )

        if dry_run:
            _LOGGER.info(
                "[WiiM] %s: [DRY RUN] Would remove %d stale entities. "
                "To actually remove them, call this service with dry_run: false",
                entity.entity_id,
                len(stale_entities),
            )
        else:
            _LOGGER.info(
                "[WiiM] %s: Successfully removed %d/%d stale entities",
                entity.entity_id,
                removed_count,
                len(stale_entities),
            )

    @staticmethod
    async def auto_maintain(entity: WiiMMediaPlayer, auto_cleanup: bool = False, dry_run: bool = True) -> None:
        """Run comprehensive maintenance: diagnostics + optional cleanup."""
        _LOGGER.info(
            "[WiiM] %s: Starting auto maintenance (auto_cleanup=%s, dry_run=%s)",
            entity.entity_id,
            auto_cleanup,
            dry_run,
        )

        # First run diagnostics
        await WiiMDiagnosticServices.diagnose_entities(entity)

        # If auto_cleanup is enabled, run cleanup
        if auto_cleanup:
            _LOGGER.info("[WiiM] %s: Running automatic cleanup as requested", entity.entity_id)
            await WiiMDiagnosticServices.cleanup_stale_entities(entity, dry_run=dry_run)
        else:
            _LOGGER.info(
                "[WiiM] %s: Auto cleanup disabled. To enable cleanup, set auto_cleanup=true",
                entity.entity_id,
            )

    @staticmethod
    async def nuclear_reset_entities(
        entity: WiiMMediaPlayer, i_understand_this_removes_all_wiim_entities: bool = False
    ) -> None:
        """Nuclear option: Remove ALL WiiM entities from Home Assistant.

        Use this when entity naming gets completely corrupted with _2, _3, etc.
        """
        if not i_understand_this_removes_all_wiim_entities:
            _LOGGER.error(
                "[WiiM] %s: Nuclear reset cancelled - confirmation required",
                entity.entity_id,
            )
            raise ValueError(
                "You must set 'i_understand_this_removes_all_wiim_entities: true' to confirm this destructive operation"
            )

        hass = entity.hass
        _LOGGER.warning(
            "[WiiM] %s: NUCLEAR RESET - Removing ALL WiiM entities from Home Assistant",
            entity.entity_id,
        )

        try:
            from homeassistant.helpers import entity_registry as er

            ent_reg = er.async_get(hass)

            # Find ALL WiiM entities
            wiim_entities = []
            for entry in ent_reg.entities.values():
                if (entry.domain == "media_player" and entry.platform == DOMAIN) or (
                    entry.platform == DOMAIN
                ):  # Catch any WiiM entities
                    wiim_entities.append(entry)

            _LOGGER.warning(
                "[WiiM] %s: Found %d WiiM entities to remove",
                entity.entity_id,
                len(wiim_entities),
            )

            # Remove all WiiM entities
            removed_count = 0
            for entity_entry in wiim_entities:
                try:
                    _LOGGER.warning(
                        "[WiiM] %s: REMOVING entity %s (%s)",
                        entity.entity_id,
                        entity_entry.entity_id,
                        entity_entry.name or entity_entry.original_name,
                    )
                    ent_reg.async_remove(entity_entry.entity_id)
                    removed_count += 1
                except Exception as remove_err:
                    _LOGGER.error(
                        "[WiiM] %s: Failed to remove entity %s: %s",
                        entity.entity_id,
                        entity_entry.entity_id,
                        remove_err,
                    )

            _LOGGER.warning(
                "[WiiM] %s: NUCLEAR RESET COMPLETE - Removed %d/%d entities. "
                "RESTART HOME ASSISTANT and re-add WiiM integration for clean setup.",
                entity.entity_id,
                removed_count,
                len(wiim_entities),
            )

        except Exception as nuclear_err:
            _LOGGER.error(
                "[WiiM] %s: Nuclear reset failed: %s",
                entity.entity_id,
                nuclear_err,
            )
            raise
