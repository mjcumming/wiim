"""Diagnostics / maintenance helpers (reboot, time sync, raw commands)."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote


class DiagnosticsAPI:  # mix-in
    """Low-level device maintenance helpers."""

    async def reboot(self) -> None:  # type: ignore[override]
        await self._request("/httpapi.asp?command=reboot")  # type: ignore[attr-defined]

    async def sync_time(self, ts: int | None = None) -> None:  # type: ignore[override]
        if ts is None:
            ts = int(time.time())
        await self._request(f"/httpapi.asp?command=timeSync:{ts}")  # type: ignore[attr-defined]

    async def send_command(self, command: str) -> dict[str, Any]:  # type: ignore[override]
        """Send arbitrary LinkPlay HTTP command (expert use only)."""
        endpoint = f"/httpapi.asp?command={quote(command)}"
        return await self._request(endpoint)  # type: ignore[attr-defined]
