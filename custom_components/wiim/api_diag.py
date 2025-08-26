"""Diagnostics / maintenance helpers (reboot, time sync, raw commands)."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote


class DiagnosticsAPI:  # mix-in
    """Low-level device maintenance helpers."""

    async def reboot(self) -> None:  # type: ignore[override]
        """Reboot the device. Note: This command may not return a response."""
        try:
            # Send reboot command - device may not respond after this
            await self._request("/httpapi.asp?command=reboot")  # type: ignore[attr-defined]
        except Exception as err:
            # Reboot commands often don't return proper responses
            # Log the attempt but don't fail the service call
            import logging

            _LOGGER = logging.getLogger(__name__)
            _LOGGER.info("Reboot command sent to device (device may not respond): %s", err)
            # Don't re-raise - reboot command was sent successfully

    async def sync_time(self, ts: int | None = None) -> None:  # type: ignore[override]
        if ts is None:
            ts = int(time.time())
        await self._request(f"/httpapi.asp?command=timeSync:{ts}")  # type: ignore[attr-defined]

    async def send_command(self, command: str) -> dict[str, Any]:  # type: ignore[override]
        """Send arbitrary LinkPlay HTTP command (expert use only)."""
        endpoint = f"/httpapi.asp?command={quote(command)}"
        return await self._request(endpoint)  # type: ignore[attr-defined]
