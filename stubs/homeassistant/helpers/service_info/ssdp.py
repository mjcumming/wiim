"""SSDP service info stub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SsdpServiceInfo:
    """Minimal placeholder for Home Assistant's SSDP service info."""

    ip_address: str | None = None
    port: int | None = None
    ssdp_usn: str | None = None
    ssdp_location: str | None = None
    ssdp_st: str | None = None
    ssdp_server: str | None = None
    upnp: dict[str, Any] | None = None
