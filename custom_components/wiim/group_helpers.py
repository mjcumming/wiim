"""Utility helpers for multi-room groups.

These helpers are intentionally **HA-agnostic** – they operate purely on
`Speaker` objects so they can be imported by both entity layers and
business-logic modules without causing circular imports.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable, List

from .data import Speaker

_LOGGER = logging.getLogger(__name__)
__all__ = [
    "calc_group_volume",
    "all_muted",
    "async_set_group_volume",
    "async_set_group_mute",
]


# ---------------------------------------------------------------------------
# Pure helpers (sync)
# ---------------------------------------------------------------------------

def calc_group_volume(speakers: Iterable[Speaker]) -> float | None:
    """Return the loudest volume (0–1) among *speakers* or None if unknown."""
    levels = [s.get_volume_level() for s in speakers]
    levels = [v for v in levels if v is not None]
    return max(levels) if levels else None


def all_muted(speakers: Iterable[Speaker]) -> bool | None:
    """Return True only when *every* speaker reports muted (None if unknown)."""
    states = [s.is_volume_muted() for s in speakers]
    if None in states:
        return None  # unknown state propagates
    return all(states)


# ---------------------------------------------------------------------------
# Async helpers (network I/O via WiiM API)
# ---------------------------------------------------------------------------

async def async_set_group_volume(master: Speaker, members: List[Speaker], volume: float) -> None:
    """Set *volume* on master plus *members* concurrently."""

    _LOGGER.debug("Group-volume %.2f on %s + %d slaves", volume, master.name, len(members))
    tasks = [master.coordinator.client.set_volume(volume)]
    for slave in members:
        if slave is master:
            continue
        tasks.append(slave.coordinator.client.set_volume(volume))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    failures = [r for r in results if isinstance(r, Exception)]
    if failures:
        _LOGGER.debug("%d/%d volume requests failed (group)", len(failures), len(results))


async def async_set_group_mute(master: Speaker, members: List[Speaker], mute: bool) -> None:
    """Mute/unmute entire group concurrently."""

    _LOGGER.debug("Group-mute=%s on %s + %d slaves", mute, master.name, len(members))
    tasks = [master.coordinator.client.set_mute(mute)]
    for slave in members:
        if slave is master:
            continue
        tasks.append(slave.coordinator.client.set_mute(mute))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    failures = [r for r in results if isinstance(r, Exception)]
    if failures:
        _LOGGER.debug("%d/%d mute requests failed (group)", len(failures), len(results)) 