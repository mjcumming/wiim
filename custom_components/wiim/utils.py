"""Shared helper utilities for WiiM integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def coerce_on_off(value: Any) -> bool | None:
    """Convert pywiim trigger/subwoofer values to bool.

    Accepts bool/int/str variants commonly returned by LinkPlay APIs.
    Returns None when value cannot be interpreted.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "on", "yes", "enabled"}:
            return True
        if normalized in {"0", "false", "off", "no", "disabled"}:
            return False
    return None


def status_field(status: Any, field: str, default: Any = None) -> Any:
    """Read status field from either dict-like or object-like payload."""
    if status is None:
        return default
    if isinstance(status, Mapping):
        return status.get(field, default)
    return getattr(status, field, default)


def first_status_field(status: Any, fields: tuple[str, ...]) -> Any:
    """Return first non-None field value from status payload."""
    for field in fields:
        value = status_field(status, field)
        if value is not None:
            return value
    return None


def status_truthy(value: Any) -> bool:
    """Return boolean intent with conservative fallback for unknown values."""
    parsed = coerce_on_off(value)
    if parsed is not None:
        return parsed
    # Preserve prior truthiness behavior for unexpected enums/strings.
    return bool(value)

