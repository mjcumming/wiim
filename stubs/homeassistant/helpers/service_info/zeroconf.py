"""Zeroconf service info stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ZeroconfServiceInfo:
    name: str | None = None
    host: str | None = None
    port: int | None = None
