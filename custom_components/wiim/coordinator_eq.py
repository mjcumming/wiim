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

    try:
        _LOGGER.debug("[WiiM] %s: Collecting EQ information", coordinator.client.host)

        eq_enabled = await coordinator.client.get_eq_status()
        eq_dict: dict[str, Any] = {"eq_enabled": eq_enabled}
        _LOGGER.debug("[WiiM] %s: EQ enabled status: %s", coordinator.client.host, eq_enabled)

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

            # Extract EQ preset from various possible field names.
            for field_name in ["preset", "EQ", "eq_preset", "eq_mode", "sound_mode"]:
                preset_val = eq_data.get(field_name)
                if preset_val is not None:
                    eq_dict["eq_preset"] = preset_val
                    _LOGGER.info("[WiiM] %s: Current EQ preset detected: %s", coordinator.client.host, preset_val)
                    break
        # Mark endpoint as working (first success).
        if coordinator._eq_supported is None:  # noqa: SLF001
            coordinator._eq_supported = True  # noqa: SLF001

        return EQInfo.model_validate(eq_dict)

    except WiiMError as err:
        if coordinator._eq_supported is None:  # noqa: SLF001
            coordinator._eq_supported = False  # noqa: SLF001
            _LOGGER.info("[WiiM] %s: EQ not supported by device: %s", coordinator.client.host, err)
        else:
            _LOGGER.debug("[WiiM] %s: EQ request failed: %s", coordinator.client.host, err)
        return EQInfo()
