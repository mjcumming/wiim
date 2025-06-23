"""Playback and volume helpers for WiiM HTTP client.

All networking (`_request`) and logging (`_log` via api_base) are supplied by
``api_base.WiiMClient``.  This mix-in must therefore be inherited **before** the
base client in the final MRO.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import quote

from .const import (
    API_ENDPOINT_CLEAR_PLAYLIST,
    API_ENDPOINT_MUTE,
    API_ENDPOINT_NEXT,
    API_ENDPOINT_PAUSE,
    API_ENDPOINT_PLAY,
    API_ENDPOINT_PLAY_M3U,
    API_ENDPOINT_PLAY_PROMPT_URL,
    API_ENDPOINT_PLAY_URL,
    API_ENDPOINT_PREV,
    API_ENDPOINT_REPEAT,
    API_ENDPOINT_SEEK,
    API_ENDPOINT_SHUFFLE,
    API_ENDPOINT_STOP,
    API_ENDPOINT_VOLUME,
    PLAY_MODE_NORMAL,
    PLAY_MODE_REPEAT_ALL,
    PLAY_MODE_REPEAT_ONE,
    PLAY_MODE_SHUFFLE,
    PLAY_MODE_SHUFFLE_REPEAT_ALL,
)

_LOGGER = logging.getLogger(__name__)


class PlaybackAPI:  # mix-in – must be left of base client in MRO
    """Transport-level playback controls (play, volume, seek, …)."""

    # ------------------------------------------------------------------
    # Core transport helpers
    # ------------------------------------------------------------------

    async def play(self) -> None:  # type: ignore[override]
        await self._request(API_ENDPOINT_PLAY)  # type: ignore[attr-defined]

    async def pause(self) -> None:  # type: ignore[override]
        await self._request(API_ENDPOINT_PAUSE)  # type: ignore[attr-defined]

    async def stop(self) -> None:  # type: ignore[override]
        await self._request(API_ENDPOINT_STOP)  # type: ignore[attr-defined]

    async def next_track(self) -> None:  # type: ignore[override]
        await self._request(API_ENDPOINT_NEXT)  # type: ignore[attr-defined]

    async def previous_track(self) -> None:  # type: ignore[override]
        await self._request(API_ENDPOINT_PREV)  # type: ignore[attr-defined]

    async def seek(self, position: int) -> None:  # type: ignore[override]
        """Seek to *position* (seconds)."""
        await self._request(f"{API_ENDPOINT_SEEK}{position}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Volume / mute
    # ------------------------------------------------------------------

    async def set_volume(self, volume: float) -> None:  # type: ignore[override]
        """Set absolute volume (0.0 – 1.0)."""
        vol_pct = int(max(0.0, min(volume, 1.0)) * 100)
        await self._request(f"{API_ENDPOINT_VOLUME}{vol_pct}")  # type: ignore[attr-defined]

    async def set_mute(self, mute: bool) -> None:  # type: ignore[override]
        await self._request(f"{API_ENDPOINT_MUTE}{1 if mute else 0}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Play-mode / shuffle
    # ------------------------------------------------------------------

    async def set_repeat_mode(self, mode: str) -> None:  # type: ignore[override]
        if mode not in (PLAY_MODE_NORMAL, PLAY_MODE_REPEAT_ALL, PLAY_MODE_REPEAT_ONE):
            raise ValueError(f"Invalid repeat mode: {mode}")
        await self._request(f"{API_ENDPOINT_REPEAT}{mode}")  # type: ignore[attr-defined]

    async def set_shuffle_mode(self, mode: str) -> None:  # type: ignore[override]
        if mode not in (PLAY_MODE_NORMAL, PLAY_MODE_SHUFFLE, PLAY_MODE_SHUFFLE_REPEAT_ALL):
            raise ValueError(f"Invalid shuffle mode: {mode}")
        await self._request(f"{API_ENDPOINT_SHUFFLE}{mode}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Playlist helpers
    # ------------------------------------------------------------------

    async def clear_playlist(self) -> None:  # type: ignore[override]
        await self._request(API_ENDPOINT_CLEAR_PLAYLIST)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # URL playback helpers – preserved for automation convenience
    # ------------------------------------------------------------------

    async def play_url(self, url: str) -> None:  # type: ignore[override]
        encoded = quote(url, safe=":/?&=#%")
        await self._request(f"{API_ENDPOINT_PLAY_URL}{encoded}")  # type: ignore[attr-defined]

    async def play_playlist(self, playlist_url: str) -> None:  # type: ignore[override]
        encoded = quote(playlist_url, safe=":/?&=#%")
        await self._request(f"{API_ENDPOINT_PLAY_M3U}{encoded}")  # type: ignore[attr-defined]

    async def play_notification(self, url: str) -> None:  # type: ignore[override]
        encoded = quote(url, safe="")
        await self._request(f"{API_ENDPOINT_PLAY_PROMPT_URL}{encoded}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Metadata helper (used by media-image caching)
    # ------------------------------------------------------------------

    async def get_meta_info(self) -> dict[str, Any]:  # type: ignore[override]
        """Retrieve current track metadata.

        Not all firmware supports this call – returns an empty dict when the
        endpoint is missing or replies with the old plain-text "unknown
        command" response.
        """
        try:
            resp = await self._request("/httpapi.asp?command=getMetaInfo")  # type: ignore[attr-defined]
            if "raw" in resp and str(resp["raw"]).lower().startswith("unknown command"):
                return {}
            if "metaData" in resp:
                return {"metaData": resp["metaData"]}
            return {}
        except Exception:  # noqa: BLE001 – older firmware returns plain text
            return {}

    # ------------------------------------------------------------------
    # Convenience: repeat/shuffle status check (non-blocking)
    # ------------------------------------------------------------------

    async def _verify_play_mode(self) -> None:
        try:
            await asyncio.sleep(0.5)
            status = await self.get_player_status()  # type: ignore[attr-defined]
            _LOGGER.debug("Status after mode change: %%s", status.get("loop_mode"))
        except Exception:  # noqa: BLE001 – best-effort only
            pass
