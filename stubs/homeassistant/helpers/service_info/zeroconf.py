"""Zeroconf service info stub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ZeroconfServiceInfo:
    name: str | None = None
    host: str | None = None
    port: int | None = None
    type: str | None = None
    properties: dict[str, Any] | None = None
