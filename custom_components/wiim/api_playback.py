"""Playback & source control helpers (stub).

Future PRs will migrate play/pause/seek/volume/* etc. from the legacy client
into this mixin while keeping signatures identical.
"""

from __future__ import annotations

from typing import Any

from .api_base import WiiMError, _LOGGER
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
    API_ENDPOINT_POWER,
    PLAY_MODE_NORMAL,
    PLAY_MODE_REPEAT_ALL,
    PLAY_MODE_REPEAT_ONE,
    PLAY_MODE_SHUFFLE,
    PLAY_MODE_SHUFFLE_REPEAT_ALL,
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
    # Power (deprecated) ------------------------------------------------
    # ------------------------------------------------------------------

    async def set_power(self, power: bool) -> None:  # type: ignore[override]
        """Set the power state (deprecated & unreliable).

        This mirrors the legacy helper so existing callers keep working, but
        still emits the deprecation warning every time.
        """
        _LOGGER.warning(
            "Power control is deprecated and unreliable on WiiM devices. "
            "Use physical power buttons or smart switches instead. Host: %s",
            self.host,  # type: ignore[attr-defined]
        )
        await self._request(f"{API_ENDPOINT_POWER}{1 if power else 0}")  # type: ignore[attr-defined]

    async def toggle_power(self) -> None:  # type: ignore[override]
        """Toggle power state using set_power helper."""
        status = await self.get_status()  # type: ignore[attr-defined]
        power = status.get("power", False)
        await self.set_power(not power)

    # ------------------------------------------------------------------
    # Repeat / shuffle with validation & logging ------------------------
    # ------------------------------------------------------------------

    async def set_repeat_mode(self, mode: str) -> None:  # type: ignore[override]
        _LOGGER.debug("🔁 API set_repeat_mode called with mode='%s' for %s", mode, self.host)  # type: ignore[attr-defined]
        if mode not in (PLAY_MODE_NORMAL, PLAY_MODE_REPEAT_ALL, PLAY_MODE_REPEAT_ONE):
            _LOGGER.error("🔁 Invalid repeat mode: %s", mode)
            raise ValueError(f"Invalid repeat mode: {mode}")

        endpoint_url = f"{API_ENDPOINT_REPEAT}{mode}"
        try:
            await self._request(endpoint_url)  # type: ignore[attr-defined]
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("🔁 HTTP request failed for repeat mode: %s", err)
            raise

    async def set_shuffle_mode(self, mode: str) -> None:  # type: ignore[override]
        _LOGGER.debug("🔀 API set_shuffle_mode called with mode='%s' for %s", mode, self.host)  # type: ignore[attr-defined]
        if mode not in (PLAY_MODE_NORMAL, PLAY_MODE_SHUFFLE, PLAY_MODE_SHUFFLE_REPEAT_ALL):
            _LOGGER.error("🔀 Invalid shuffle mode: %s", mode)
            raise ValueError(f"Invalid shuffle mode: {mode}")

        endpoint_url = f"{API_ENDPOINT_SHUFFLE}{mode}"
        try:
            await self._request(endpoint_url)  # type: ignore[attr-defined]
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("🔀 HTTP request failed for shuffle mode: %s", err)
            raise

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
