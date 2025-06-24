"""EQ related helpers for WiiM coordinator.

Keeps heavy logic for EQ polling and preset extraction separate from the core
coordinator to adhere to the 300-LOC guideline.
"""

from __future__ import annotations

import logging
from typing import Any

from .api import WiiMError
from .models import EQInfo

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "fetch_eq_info",
]


async def fetch_eq_info(coordinator) -> EQInfo:
    """Return EQ information model (may be empty)."""

    if coordinator._eq_supported is False:  # noqa: SLF001
        _LOGGER.debug("[WiiM] %s: EQ not supported, skipping EQ info collection", coordinator.client.host)
        return EQInfo()

    _LOGGER.debug("[WiiM] %s: Collecting EQ information", coordinator.client.host)

    eq_dict: dict[str, Any] = {}

    # Try to get EQ status first
    try:
        eq_enabled = await coordinator.client.get_eq_status()
        eq_dict["eq_enabled"] = eq_enabled
        _LOGGER.debug("[WiiM] %s: EQ enabled status: %s", coordinator.client.host, eq_enabled)
    except WiiMError as err:
        _LOGGER.debug("[WiiM] %s: EQ status request failed: %s", coordinator.client.host, err)
        # Don't return early - still try to get EQ data

    # Try to get EQ data
    try:
        eq_data = await coordinator.client.get_eq()
        if eq_data:
            # Detect 'unknown command' responses and treat as unsupported.
            if "raw" in eq_data and str(eq_data["raw"]).lower().startswith("unknown command"):
                _LOGGER.info(
                    "[WiiM] %s: Device responded 'unknown command' to getEQ – disabling EQ polling",
                    coordinator.client.host,
                )
                coordinator._eq_supported = False  # noqa: SLF001
                return EQInfo.model_validate(eq_dict)

            eq_dict.update(eq_data)
            _LOGGER.debug("[WiiM] %s: Raw EQ data: %s", coordinator.client.host, eq_data)

            # Extract eq_enabled from EQ data if not already set
            if "eq_enabled" not in eq_dict and "enabled" in eq_data:
                eq_dict["eq_enabled"] = eq_data["enabled"]

            # Extract EQ preset from various possible field names.
            # Prioritize "EQ" field as it usually contains the display name
            for field_name in ["EQ", "eq_preset", "eq_mode", "sound_mode", "preset"]:
                preset_val = eq_data.get(field_name)
                if preset_val is not None:
                    eq_dict["eq_preset"] = preset_val
                    _LOGGER.info("[WiiM] %s: Current EQ preset detected: %s", coordinator.client.host, preset_val)
                    break
    except WiiMError as err:
        _LOGGER.debug("[WiiM] %s: EQ data request failed: %s", coordinator.client.host, err)
        # Continue with whatever data we have

    # Check if we got any useful data
    if not eq_dict:
        # Both calls failed - mark as unsupported if first time
        if coordinator._eq_supported is None:  # noqa: SLF001
            coordinator._eq_supported = False  # noqa: SLF001
            _LOGGER.info("[WiiM] %s: EQ not supported by device", coordinator.client.host)
        return EQInfo()

    # Mark endpoint as working (first success).
    if coordinator._eq_supported is None:  # noqa: SLF001
        coordinator._eq_supported = True  # noqa: SLF001

    return EQInfo.model_validate(eq_dict)
