"""Read device capability flags from ``WiiMClient.capabilities`` only."""

from __future__ import annotations

from typing import Any


def get_client_capability(player: Any, key: str) -> Any:
    """Return ``player.client.capabilities[key]``, or ``None`` if missing or no client."""
    client = getattr(player, "client", None)
    if client is None:
        return None
    caps = getattr(client, "capabilities", None)
    if not isinstance(caps, dict):
        return None
    return caps.get(key)


def client_has_capability(player: Any, key: str) -> bool:
    """Return True when the capability value is truthy in ``player.client.capabilities``."""
    return bool(get_client_capability(player, key))
