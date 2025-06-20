"""Diagnostics & maintenance helpers (stub)."""

from __future__ import annotations

from typing import Any

REBOOT_ENDPOINT = "/httpapi.asp?command=reboot"


class DiagnosticsAPI:  # pylint: disable=too-few-public-methods
    """Maintenance & diagnostic helpers."""

    async def reboot(self) -> None:  # type: ignore[override]
        await self._request(REBOOT_ENDPOINT)  # type: ignore[attr-defined]

    async def sync_time(self, ts: int | None = None) -> None:  # type: ignore[override]
        if ts is None:
            import time

            ts = int(time.time())
        await self._request(f"/httpapi.asp?command=setTime:{ts}")  # type: ignore[attr-defined]

    async def get_meta_info(self) -> dict[str, Any]:  # type: ignore[override]
        return await self._request("/httpapi.asp?command=getMetaDataEx")  # type: ignore[attr-defined]

    async def play_url(self, url: str) -> None:  # type: ignore[override]
        from urllib.parse import quote

        await self._request(f"/httpapi.asp?command=play:{quote(url, safe='')}")  # type: ignore[attr-defined]

    async def play_playlist(self, playlist_url: str) -> None:  # type: ignore[override]
        from urllib.parse import quote

        await self._request(f"/httpapi.asp?command=playPlaylist:{quote(playlist_url, safe='')}")  # type: ignore[attr-defined]

    async def play_notification(self, url: str) -> None:  # type: ignore[override]
        from urllib.parse import quote

        await self._request(f"/httpapi.asp?command=prompt_url:{quote(url, safe='')}")  # type: ignore[attr-defined]

    async def send_command(self, command: str) -> dict[str, Any]:  # type: ignore[override]
        return await self._request(f"/httpapi.asp?command={command}")  # type: ignore[attr-defined]

    # END DiagnosticsAPI
