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

    # For slaves, always attempt to mirror master data when in a group
    if role == "slave":
        await _mirror_master_media(coordinator, status, metadata)
        return

    # For masters and solo devices, only do source resolution if in multiroom mode
    # Check _multiroom_mode directly on the status object since it's a PrivateAttr
    if not getattr(status, "_multiroom_mode", False):
        _LOGGER.debug("Device %s not in multiroom mode, no source resolution needed", coordinator.client.host)
        return

    if role == "master":
        await _resolve_master_source(coordinator, status)
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


async def _mirror_master_media(coordinator, status: PlayerStatus, metadata: dict[str, Any]) -> None:
    """Slaves should mirror what the master is playing.

    IMPORTANT: This function mirrors MEDIA CONTENT only (title, artist, playback state, etc.)
    It explicitly DOES NOT mirror volume or mute state - those remain per-speaker.
    """

    _LOGGER.debug("Mirroring master media info for slave %s", coordinator.client.host)

    from .data_helpers import find_speaker_by_ip, get_all_speakers

    master_speaker = None

    # Try to find master using multiple approaches
    # 1. First try using master_ip from device status if available
    if coordinator.data:
        status_model_self = coordinator.data.get("status_model")
        if isinstance(status_model_self, PlayerStatus):
            status_dict = status_model_self.model_dump(exclude_none=True)
            master_ip = status_dict.get("master_ip")
            if master_ip:
                master_speaker = find_speaker_by_ip(coordinator.hass, master_ip)
                if master_speaker and master_speaker.role != "master":
                    master_speaker = None

    # 2. Fallback: Search all speakers to find our master
    if not master_speaker:
        for speaker in get_all_speakers(coordinator.hass):
            if speaker.role == "master" and coordinator.client.host != speaker.ip_address:
                try:
                    # Check if this slave is in the master's group members
                    slave_ips = [s.ip_address for s in speaker.group_members if hasattr(s, "ip_address")]
                    if coordinator.client.host in slave_ips:
                        master_speaker = speaker
                        break
                except Exception:  # pragma: no cover – defensive
                    continue

    if master_speaker and master_speaker.coordinator.data:
        master_status_model = master_speaker.coordinator.data.get("status_model")
        if isinstance(master_status_model, PlayerStatus):
            master_metadata = master_speaker.coordinator.data.get("metadata", {})

            # Mirror media fields directly on the PlayerStatus model
            _LOGGER.debug(
                "Mirroring media data from master %s to slave %s", master_speaker.name, coordinator.client.host
            )

            # Core media information
            if master_status_model.title:
                status.title = master_status_model.title
            if master_status_model.artist:
                status.artist = master_status_model.artist
            if master_status_model.album:
                status.album = master_status_model.album

            # Playback state and timing
            if master_status_model.play_state:
                status.play_state = master_status_model.play_state
                _LOGGER.debug(
                    "Slave %s mirroring playback state: %s", coordinator.client.host, master_status_model.play_state
                )
            if master_status_model.position is not None:
                status.position = master_status_model.position
            if master_status_model.duration is not None:
                status.duration = master_status_model.duration

            # Source information
            if master_status_model.source:
                status.source = master_status_model.source

            # EXPLICITLY DO NOT COPY: volume, mute (these are per-speaker)
            # status.volume = master_status_model.volume  # ❌ NEVER copy this
            # status.mute = master_status_model.mute      # ❌ NEVER copy this

            # Copy metadata dict for additional fields (but filter out volume/mute)
            for key, value in master_metadata.items():
                # Skip volume/mute related metadata to prevent accidental propagation
                if key.lower() not in ["volume", "mute", "vol", "muted"]:
                    metadata[key] = value

            # Handle artwork
            art_url = (
                master_metadata.get("entity_picture")
                or master_metadata.get("cover_url")
                or getattr(master_status_model, "entity_picture", None)
                or getattr(master_status_model, "cover_url", None)
            )

            if art_url:
                status.entity_picture = art_url
                status.cover_url = art_url
                metadata["entity_picture"] = art_url
                metadata["cover_url"] = art_url

            _LOGGER.debug(
                "Slave %s successfully mirrored master %s: title='%s', play_state='%s' (volume/mute preserved as per-speaker)",
                coordinator.client.host,
                master_speaker.name,
                status.title,
                status.play_state,
            )
            return

    # If we could not determine the master, set appropriate fallback
    _LOGGER.debug("Could not find master for slave %s – setting source to 'follower'", coordinator.client.host)
    status.source = "follower"
