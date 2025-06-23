"""SSDP service info stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SsdpServiceInfo:
    """Minimal placeholder for Home Assistant's SSDP service info."""

    ip_address: str | None = None
    port: int | None = None
    ssdp_usn: str | None = None
