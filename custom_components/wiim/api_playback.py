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
    API_ENDPOINT_AUDIO_OUTPUT_SET,
    API_ENDPOINT_AUDIO_OUTPUT_STATUS,
    API_ENDPOINT_CLEAR_PLAYLIST,
    API_ENDPOINT_LOOPMODE,
    API_ENDPOINT_MUTE,
    API_ENDPOINT_NEXT,
    API_ENDPOINT_PAUSE,
    API_ENDPOINT_PLAY,
    API_ENDPOINT_PLAY_M3U,
    API_ENDPOINT_PLAY_PROMPT_URL,
    API_ENDPOINT_PLAY_URL,
    API_ENDPOINT_PREV,
    API_ENDPOINT_SEEK,
    API_ENDPOINT_SOURCE,
    API_ENDPOINT_STOP,
    API_ENDPOINT_VOLUME,
)

_LOGGER = logging.getLogger(__name__)


class PlaybackAPI:  # mix-in – must be left of base client in MRO
    """Transport-level playback controls (play, volume, seek, …)."""

    # pylint: disable=no-member

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
        endpoint = f"{API_ENDPOINT_VOLUME}{vol_pct}"
        _LOGGER.info("Sending volume API request: %s to %s (%.0f%%)", endpoint, self._host, vol_pct)
        try:
            result = await self._request(endpoint)  # type: ignore[attr-defined]
            _LOGGER.debug("Volume API request successful: %s", result)
        except Exception as err:
            _LOGGER.error(
                "Volume API request failed: %s to %s: %s (type: %s)",
                endpoint,
                self._host,
                err,
                type(err).__name__,
                exc_info=True,
            )
            raise

    async def set_mute(self, mute: bool) -> None:  # type: ignore[override]
        await self._request(f"{API_ENDPOINT_MUTE}{1 if mute else 0}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Loop mode (shuffle/repeat combined)
    # ------------------------------------------------------------------

    async def set_loop_mode(self, mode: int) -> None:  # type: ignore[override]
        """Set loop mode using WiiM's loopmode command.

        Values: 0=normal, 1=repeat_one, 2=repeat_all, 4=shuffle, 5=shuffle+repeat_one, 6=shuffle+repeat_all
        """
        if mode not in (0, 1, 2, 4, 5, 6):
            raise ValueError(f"Invalid loop mode: {mode}. Valid values: 0,1,2,4,5,6")
        await self._request(f"{API_ENDPOINT_LOOPMODE}{mode}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Source selection
    # ------------------------------------------------------------------

    async def set_source(self, source: str) -> None:  # type: ignore[override]
        """Set audio source using WiiM's switchmode command.

        Args:
            source: Source to switch to (e.g., "wifi", "bluetooth", "line_in", "optical")
        """
        await self._request(f"{API_ENDPOINT_SOURCE}{source}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Audio Output Control
    # ------------------------------------------------------------------

    async def get_audio_output_status(self) -> dict[str, Any] | None:  # type: ignore[override]
        """Get current audio output status including Bluetooth output mode.

        Returns:
            dict with keys: hardware, source, audiocast if supported, None if not supported
            - hardware: Hardware output mode (0=Line Out, 1=Optical Out, 2=Line Out, 3=Coax Out, 4=Bluetooth Out)
            - source: Bluetooth output mode (0=disabled, 1=active)
            - audiocast: Audio cast mode (0=disabled, 1=active)
        """
        try:
            result = await self._request(API_ENDPOINT_AUDIO_OUTPUT_STATUS)  # type: ignore[attr-defined]
            return result if result else None
        except Exception as e:
            # Log with more details for first few failures
            if not hasattr(self, "_audio_output_error_count"):
                self._audio_output_error_count = 0
            self._audio_output_error_count += 1

            # Log first 5 failures with full details, then throttle
            if self._audio_output_error_count <= 5:
                _LOGGER.warning(
                    "%s: Audio output API call failed (attempt %d), error type: %s, error: %s",
                    self.host,
                    self._audio_output_error_count,
                    type(e).__name__,
                    str(e),
                )
            elif self._audio_output_error_count % 10 == 1:
                _LOGGER.debug(
                    "%s: Audio output API still failing (%d consecutive failures)",
                    self.host,
                    self._audio_output_error_count,
                )
            return None

    async def set_audio_output_hardware_mode(self, mode: int) -> None:  # type: ignore[override]
        """Set hardware audio output mode.

        Args:
            mode: Hardware output mode (1=SPDIF, 2=AUX, 3=COAX)
        """
        await self._request(f"{API_ENDPOINT_AUDIO_OUTPUT_SET}{mode}")  # type: ignore[attr-defined]

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
            await self.get_player_status()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 – best-effort only
            pass
