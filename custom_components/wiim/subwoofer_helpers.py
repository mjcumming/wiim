"""Helpers for pywiim subwoofer status: legacy dict vs SubwooferStatus dataclass."""

from __future__ import annotations

from typing import Any


def subwoofer_plugged(status: Any) -> bool:
    """Return True if a subwoofer is physically connected."""
    if status is None:
        return False
    if isinstance(status, dict):
        return bool(status.get("plugged"))
    return bool(getattr(status, "plugged", False))


def subwoofer_enabled_from_status(status: Any) -> bool | None:
    """Return whether subwoofer output is enabled (None if unknown)."""
    if status is None:
        return None
    if isinstance(status, dict):
        return bool(status.get("status"))
    return getattr(status, "enabled", None)


def subwoofer_level_from_status(status: Any) -> float | None:
    """Return subwoofer level in dB, or None if unknown."""
    if status is None:
        return None
    if isinstance(status, dict):
        return float(status.get("level", 0))
    level = getattr(status, "level", None)
    if level is None:
        return None
    return float(level)


def subwoofer_status_for_diagnostics(status: Any) -> dict[str, Any]:
    """Build diagnostics dict from cached dict or SubwooferStatus."""
    if status is None:
        return {}
    if isinstance(status, dict):
        return {
            "connected": bool(status.get("plugged")),
            "enabled": bool(status.get("status")),
            "level_db": status.get("level"),
            "crossover_hz": status.get("cross"),
            "phase_degrees": status.get("phase"),
            "sub_delay_ms": status.get("sub_delay"),
            "main_filter_enabled": status.get("main_filter"),
            "sub_filter_enabled": status.get("sub_filter"),
        }
    return {
        "connected": bool(getattr(status, "plugged", False)),
        "enabled": bool(getattr(status, "enabled", False)),
        "level_db": getattr(status, "level", None),
        "crossover_hz": getattr(status, "crossover", None),
        "phase_degrees": getattr(status, "phase", None),
        "sub_delay_ms": getattr(status, "sub_delay", None),
        "main_filter_enabled": getattr(status, "main_filter_enabled", None),
        "sub_filter_enabled": getattr(status, "sub_filter_enabled", None),
    }
