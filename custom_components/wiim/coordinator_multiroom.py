"""Multi-room media handling helpers for WiiM coordinator.

The original implementation in ``coordinator.py`` has been lifted verbatim (but
with ``self``→``coordinator`` substitutions) so that the *huge* media-mirroring
logic no longer bloats the core class.
"""

from __future__ import annotations

import logging
from typing import Any

from .models import PlayerStatus

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "resolve_multiroom_source_and_media",
]


async def resolve_multiroom_source_and_media(
    coordinator,
    status: PlayerStatus,
    metadata: dict[str, Any],
    role: str,
) -> None:
    """Public entry-point used by the polling loop."""

    # Check _multiroom_mode directly on the status object since it's a PrivateAttr
    if not getattr(status, "_multiroom_mode", False):
        _LOGGER.debug("Device %s not in multiroom mode, no source resolution needed", coordinator.client.host)
        return

    status_dict: dict[str, Any] = status.model_dump(exclude_none=False)

    if role == "master":
        await _resolve_master_source(coordinator, status)
    elif role == "slave":
        await _mirror_master_media(coordinator, status_dict, metadata)
    else:
        _LOGGER.debug("Solo device %s in multiroom mode – keeping multiroom source", coordinator.client.host)


# -----------------------------------------------------------------------------
# Internal helpers (kept private to this module)
# -----------------------------------------------------------------------------


async def _resolve_master_source(coordinator, status: PlayerStatus) -> None:
    """Masters expose their actual source instead of 'multiroom'."""

    _LOGGER.debug("Resolving actual source for master %s", coordinator.client.host)

    actual_source: str | None = None

    # Heuristic 1 – infer from track title pattern or presence of duration
    if status.title and status.title.lower() != "unknown":
        if "spotify" in status.title.lower():
            actual_source = "spotify"
        elif (status.duration or 0) > 0:
            actual_source = "wifi"  # generic network streamer

    if actual_source is None:
        actual_source = "network"

    status.source = actual_source  # type: ignore[assignment]
    _LOGGER.debug("Resolved master %s source: multiroom -> %s", coordinator.client.host, actual_source)


async def _mirror_master_media(coordinator, status: dict[str, Any], metadata: dict[str, Any]) -> None:
    """Slaves should mirror what the master is playing."""

    _LOGGER.debug("Mirroring master media info for slave %s", coordinator.client.host)

    from .data import find_speaker_by_ip, get_all_speakers

    master_speaker = None

    status_model_self = coordinator.data.get("status_model") if coordinator.data else None  # type: ignore[attr-defined]
    _device_status: dict[str, Any] = (
        status_model_self.model_dump(exclude_none=True) if isinstance(status_model_self, PlayerStatus) else {}
    )
    master_ip = _device_status.get("master_ip")

    if master_ip:
        master_speaker = find_speaker_by_ip(coordinator.hass, master_ip)
        if master_speaker and master_speaker.role != "master":
            master_speaker = None

    if not master_speaker:
        for speaker in get_all_speakers(coordinator.hass):
            if speaker.role == "master" and coordinator.client.host != speaker.ip_address:
                try:
                    slave_ips = [s.ip_address for s in speaker.group_members if hasattr(s, "ip_address")]
                    if coordinator.client.host in slave_ips:
                        master_speaker = speaker
                        break
                except Exception:  # pragma: no cover – defensive
                    continue

    if master_speaker and master_speaker.coordinator.data:
        master_status_model = master_speaker.coordinator.data.get("status_model")
        master_status: dict[str, Any] = (
            master_status_model.model_dump(exclude_none=True) if isinstance(master_status_model, PlayerStatus) else {}
        )
        master_metadata: dict[str, Any] = master_speaker.coordinator.data.get("metadata", {})

        # Mirror fields
        media_fields = [
            "title",
            "artist",
            "album",
            "source",
            "play_state",
            "position",
            "duration",
        ]
        for field in media_fields:
            if field in master_status:
                status[field] = master_status[field]

        for key, value in master_metadata.items():
            metadata[key] = value

        art_url = metadata.get("entity_picture") or metadata.get("cover_url")
        if art_url:
            status["entity_picture"] = art_url
            status.setdefault("cover_url", art_url)

        _LOGGER.debug("Slave %s now mirroring master %s media info", coordinator.client.host, master_speaker.name)
        return

    # If we could not determine the master … keep UX reasonable.
    _LOGGER.debug("Could not find master for slave %s – source remains 'follower'", coordinator.client.host)
    status["source"] = "follower"
