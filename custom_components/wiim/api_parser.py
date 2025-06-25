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
    # Process API response

    data: dict[str, Any] = {}

    play_state_val = raw.get("state") or raw.get("player_state") or raw.get("status")
    if play_state_val is not None:
        data["play_status"] = play_state_val

    # Generic key mapping first.
    for k, v in raw.items():
        if k in ("status", "state", "player_state"):
            continue
        data[STATUS_MAP.get(k, k)] = v

    # Hex-encoded strings → UTF-8 (per LinkPlay API standard)
    data["title"] = _decode_text(raw.get("Title")) or _decode_text(raw.get("title"))
    data["artist"] = _decode_text(raw.get("Artist")) or _decode_text(raw.get("artist"))
    data["album"] = _decode_text(raw.get("Album")) or _decode_text(raw.get("album"))

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
    # Parse position and duration (convert ms to seconds)
    if (pos := raw.get("curpos") or raw.get("offset_pts")) is not None:
        try:
            data["position"] = int(pos) // 1_000
            data["position_updated_at"] = asyncio.get_running_loop().time()
        except (ValueError, TypeError):
            _LOGGER.debug("Invalid position value: %s", pos)

    if raw.get("totlen") is not None:
        try:
            duration_ms = int(raw["totlen"])
            if duration_ms > 0:  # Only set duration if it's actually provided
                data["duration"] = duration_ms // 1_000
        except (ValueError, TypeError):
            _LOGGER.debug("Invalid duration value: %s", raw.get("totlen"))

    # Mute → bool.
    if "mute" in data:
        try:
            data["mute"] = bool(int(data["mute"]))
        except (TypeError, ValueError):  # noqa: PERF203 – clarity > micro perf.
            data["mute"] = bool(data["mute"])

    # Play-mode mapping from loop_mode bit flags.
    # WiiM devices use bit flags: bit 0=repeat_one, bit 1=repeat_all, bit 2=shuffle
    if "play_mode" not in data and "loop_mode" in data:
        try:
            loop_val = int(data["loop_mode"])
        except (TypeError, ValueError):
            loop_val = 0

        # Decode bit flags
        is_shuffle = bool(loop_val & 4)  # bit 2
        is_repeat_one = bool(loop_val & 1)  # bit 0
        is_repeat_all = bool(loop_val & 2)  # bit 1

        # Map to play modes
        if is_shuffle and is_repeat_all:
            data["play_mode"] = PLAY_MODE_SHUFFLE_REPEAT_ALL
        elif is_shuffle and is_repeat_one:
            data["play_mode"] = PLAY_MODE_SHUFFLE  # WiiM doesn't support shuffle+repeat_one as separate mode
        elif is_shuffle:
            data["play_mode"] = PLAY_MODE_SHUFFLE
        elif is_repeat_one:
            data["play_mode"] = PLAY_MODE_REPEAT_ONE
        elif is_repeat_all:
            data["play_mode"] = PLAY_MODE_REPEAT_ALL
        else:
            data["play_mode"] = PLAY_MODE_NORMAL

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


def _decode_text(val: str | None) -> str | None:
    """Decode hex-encoded UTF-8 strings, then clean up HTML entities."""
    if not val:
        return None

    # First: Standard hex decoding as per API specification
    decoded = _hex_to_str(val)
    if decoded:
        # Second: Clean up HTML entities that may appear in hex-decoded text
        import html

        return html.unescape(decoded)

    return val
