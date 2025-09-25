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
            # Use a custom request method that handles empty responses gracefully
            await self._request_reboot("/httpapi.asp?command=reboot")  # type: ignore[attr-defined]
        except Exception as err:
            # Reboot commands often don't return proper responses
            # Log the attempt but don't fail the service call
            import logging

            _LOGGER = logging.getLogger(__name__)
            _LOGGER.info("Reboot command sent to device (device may not respond): %s", err)
            # Don't re-raise - reboot command was sent successfully

    async def _request_reboot(self, endpoint: str) -> None:
        """Special request method for reboot that handles empty responses gracefully."""
        try:
            # Try to send the reboot command
            await self._request(endpoint)  # type: ignore[attr-defined]
        except Exception as err:
            # If the request fails due to parsing issues (common with reboot),
            # we still consider it successful since the command was sent
            import logging
            _LOGGER = logging.getLogger(__name__)

            error_str = str(err).lower()
            if any(x in error_str for x in ["expecting value", "json decode", "empty response"]):
                _LOGGER.info("Reboot command sent successfully (device stopped responding as expected)")
                return
            else:
                # Re-raise other types of errors
                raise

    async def sync_time(self, ts: int | None = None) -> None:  # type: ignore[override]
        if ts is None:
            ts = int(time.time())
        await self._request(f"/httpapi.asp?command=timeSync:{ts}")  # type: ignore[attr-defined]

    async def send_command(self, command: str) -> dict[str, Any]:  # type: ignore[override]
        """Send arbitrary LinkPlay HTTP command (expert use only)."""
        endpoint = f"/httpapi.asp?command={quote(command)}"
        return await self._request(endpoint)  # type: ignore[attr-defined]
