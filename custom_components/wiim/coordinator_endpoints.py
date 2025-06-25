"""Network endpoint helpers for WiiM Coordinator.

Each helper isolates *one* HTTP-API call, returning a fully-typed
Pydantic model.  Splitting them out keeps complex device-I/O away from
`coordinator_polling.py` and ensures the core coordinator stays below
the 300-LOC soft cap.
"""

from __future__ import annotations

from typing import Any

from .api import WiiMClient
from .models import DeviceInfo, PlayerStatus

__all__ = [
    "fetch_player_status",
    "fetch_device_info",
]


# ---------------------------------------------------------------------------
# Player-status (getPlayerStatusEx)
# ---------------------------------------------------------------------------


async def fetch_player_status(client: WiiMClient) -> PlayerStatus:
    """Return *typed* :class:`PlayerStatus` for the given client."""

    # Prefer the dedicated typed helper (fast-path)
    if hasattr(client, "get_player_status_model"):
        return await client.get_player_status_model()  # type: ignore[return-value]

    # Fallback: raw dict → Pydantic validation
    raw: dict[str, Any] = await client.get_player_status()
    return PlayerStatus.model_validate(raw)


# ---------------------------------------------------------------------------
# Device-info (getStatusEx)
# ---------------------------------------------------------------------------


async def fetch_device_info(client: WiiMClient) -> DeviceInfo:
    """Return *typed* :class:`DeviceInfo` for the given client."""

    if hasattr(client, "get_device_info_model"):
        return await client.get_device_info_model()  # type: ignore[return-value]

    raw: dict[str, Any] = await client.get_device_info()
    return DeviceInfo.model_validate(raw)
