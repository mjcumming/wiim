"""WiiM API response parser.

Extracted from api_base.py to keep it under 300 LOC.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import quote

from .api_constants import EQ_NUMERIC_MAP, MODE_MAP, STATUS_MAP
from .const import (
    PLAY_MODE_NORMAL,
    PLAY_MODE_REPEAT_ALL,
    PLAY_MODE_REPEAT_ONE,
    PLAY_MODE_SHUFFLE,
    PLAY_MODE_SHUFFLE_REPEAT_ALL,
)

_LOGGER = logging.getLogger(__name__)


def parse_player_status(raw: dict[str, Any], last_track: str | None = None) -> tuple[dict[str, Any], str | None]:
    """Normalise *getPlayerStatusEx* / *getStatusEx* responses.

    Returns:
        Tuple of (parsed_data, new_last_track)
    """
    data: dict[str, Any] = {}

    play_state_val = raw.get("state") or raw.get("player_state") or raw.get("status")
    if play_state_val is not None:
        data["play_status"] = play_state_val

    # Generic key mapping first.
    for k, v in raw.items():
        if k in ("status", "state", "player_state"):
            continue
        data[STATUS_MAP.get(k, k)] = v

    # Hex-encoded strings → UTF-8.
    data["title"] = _hex_to_str(raw.get("Title")) or raw.get("title")
    data["artist"] = _hex_to_str(raw.get("Artist")) or raw.get("artist")
    data["album"] = _hex_to_str(raw.get("Album")) or raw.get("album")

    # Track change detection for debug logging.
    new_last_track = last_track
    if data.get("title") and data["title"] != "Unknown":
        cur = f"{data.get('artist', 'Unknown')} - {data['title']}"
        if last_track != cur:
            _LOGGER.info("🎵 Track changed: %s", cur)
            new_last_track = cur

    # Power state defaults to *True* when missing.
    data.setdefault("power", True)

    # Volume (int percentage) → float 0-1.
    if (vol := raw.get("vol")) is not None:
        try:
            vol_i = int(vol)
            data["volume_level"] = vol_i / 100
            data["volume"] = vol_i
        except ValueError:
            _LOGGER.debug("Invalid volume value: %s", vol)

    # Playback position & duration (ms → s).
    if (pos := raw.get("curpos") or raw.get("offset_pts")) is not None:
        data["position"] = int(pos) // 1_000
        data["position_updated_at"] = asyncio.get_running_loop().time()
    if raw.get("totlen") is not None:
        data["duration"] = int(raw["totlen"]) // 1_000

    # Mute → bool.
    if "mute" in data:
        try:
            data["mute"] = bool(int(data["mute"]))
        except (TypeError, ValueError):  # noqa: PERF203 – clarity > micro perf.
            data["mute"] = bool(data["mute"])

    # Play-mode mapping.
    if "play_mode" not in data and "loop_mode" in data:
        try:
            loop_val = int(data["loop_mode"])
        except (TypeError, ValueError):
            loop_val = 4
        data["play_mode"] = {
            0: PLAY_MODE_REPEAT_ALL,
            1: PLAY_MODE_REPEAT_ONE,
            2: PLAY_MODE_SHUFFLE_REPEAT_ALL,
            3: PLAY_MODE_SHUFFLE,
        }.get(loop_val, PLAY_MODE_NORMAL)

    # Artwork – attempt cache-busting when metadata changes.
    cover = (
        raw.get("cover")
        or raw.get("cover_url")
        or raw.get("albumart")
        or raw.get("albumArtURI")
        or raw.get("albumArtUri")
        or raw.get("albumarturi")
        or raw.get("art_url")
        or raw.get("artwork_url")
        or raw.get("pic_url")
    )
    if cover:
        cache_key = f"{data.get('title', '')}-{data.get('artist', '')}-{data.get('album', '')}"
        if cache_key:
            encoded = quote(cache_key)
            sep = "&" if "?" in cover else "?"
            cover = f"{cover}{sep}cache={encoded}"
        data["entity_picture"] = cover

    # Source mapping from *mode* field.
    if (mode_val := raw.get("mode")) is not None and "source" not in data:
        if str(mode_val) == "99":
            data["source"] = "multiroom"
            data["_multiroom_mode"] = True
        else:
            data["source"] = MODE_MAP.get(str(mode_val), "unknown")

    # Vendor override (e.g. Amazon Music).
    vendor_val = raw.get("vendor") or raw.get("Vendor") or raw.get("app")
    if vendor_val:
        vendor_clean = str(vendor_val).strip()
        _VENDOR_MAP = {
            "amazon music": "amazon",
            "amazonmusic": "amazon",
            "prime": "amazon",
            "qobuz": "qobuz",
            "tidal": "tidal",
            "deezer": "deezer",
        }
        if data.get("source") in {None, "wifi", "unknown"}:
            data["source"] = _VENDOR_MAP.get(vendor_clean.lower(), vendor_clean.lower().replace(" ", "_"))
        data["vendor"] = vendor_clean

    # EQ numeric → textual preset.
    eq_raw = data.get("eq_preset")
    if isinstance(eq_raw, int | str) and str(eq_raw).isdigit():
        data["eq_preset"] = EQ_NUMERIC_MAP.get(str(eq_raw), eq_raw)

    # Qobuz quirk – always reports *stop* even when playing.
    if data.get("source") == "qobuz" and (
        not data.get("play_status") or str(data["play_status"]).lower() in {"stop", "stopped", "idle", ""}
    ):
        data["play_status"] = "play"

    return data, new_last_track


def _hex_to_str(val: str | None) -> str | None:
    """Decode hex-encoded UTF-8 strings as used by LinkPlay."""
    if not val:
        return None
    try:
        return bytes.fromhex(val).decode("utf-8", errors="replace")
    except ValueError:
        return val
