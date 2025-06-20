"""Playback & source control helpers (stub).

Future PRs will migrate play/pause/seek/volume/* etc. from the legacy client
into this mixin while keeping signatures identical.
"""

from __future__ import annotations

from typing import Any

from .api_base import WiiMError
from .const import (
    API_ENDPOINT_CLEAR_PLAYLIST,
    API_ENDPOINT_MUTE,
    API_ENDPOINT_NEXT,
    API_ENDPOINT_PAUSE,
    API_ENDPOINT_PLAY,
    API_ENDPOINT_PREV,
    API_ENDPOINT_REPEAT,
    API_ENDPOINT_SEEK,
    API_ENDPOINT_SHUFFLE,
    API_ENDPOINT_SOURCE,
    API_ENDPOINT_SOURCES,
    API_ENDPOINT_STOP,
    API_ENDPOINT_VOLUME,
)


class PlaybackAPI:  # pylint: disable=too-few-public-methods
    """Playback & source control helpers – thin wrappers delegating to BaseClient."""

    # ------------------------------------------------------------------
    # Core transport wrappers ------------------------------------------
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

    # ------------------------------------------------------------------
    # Volume / mute -----------------------------------------------------
    # ------------------------------------------------------------------

    async def set_volume(self, volume: float) -> None:  # type: ignore[override]
        volume_pct = int(volume * 100)
        await self._request(f"{API_ENDPOINT_VOLUME}{volume_pct}")  # type: ignore[attr-defined]

    async def set_mute(self, mute: bool) -> None:  # type: ignore[override]
        await self._request(f"{API_ENDPOINT_MUTE}{1 if mute else 0}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Repeat / shuffle --------------------------------------------------
    # ------------------------------------------------------------------

    async def set_repeat_mode(self, mode: str) -> None:  # type: ignore[override]
        await self._request(f"{API_ENDPOINT_REPEAT}{mode}")  # type: ignore[attr-defined]

    async def set_shuffle_mode(self, mode: str) -> None:  # type: ignore[override]
        await self._request(f"{API_ENDPOINT_SHUFFLE}{mode}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Seek / clear ------------------------------------------------------
    # ------------------------------------------------------------------

    async def seek(self, position: int) -> None:  # type: ignore[override]
        await self._request(f"{API_ENDPOINT_SEEK}{position}")  # type: ignore[attr-defined]

    async def clear_playlist(self) -> None:  # type: ignore[override]
        await self._request(API_ENDPOINT_CLEAR_PLAYLIST)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Source selection --------------------------------------------------
    # ------------------------------------------------------------------

    async def set_source(self, source: str) -> None:  # type: ignore[override]
        await self._request(f"{API_ENDPOINT_SOURCE}{source}")  # type: ignore[attr-defined]

    async def get_sources(self) -> list[str]:  # type: ignore[override]
        response = await self._request(API_ENDPOINT_SOURCES)  # type: ignore[attr-defined]
        return response.get("sources", []) if isinstance(response, dict) else []

    # ------------------------------------------------------------------
    # Player status -----------------------------------------------------
    # ------------------------------------------------------------------

    async def get_player_status(self) -> dict[str, Any]:  # type: ignore[override]
        try:
            raw = await self._request("/httpapi.asp?command=getPlayerStatusEx")  # type: ignore[attr-defined]
            return self._parse_player_status(raw)  # type: ignore[attr-defined]
        except WiiMError:
            return {}

    # _parse_player_status is still inherited from api_base – no need to duplicate.

    # END PlaybackAPI
