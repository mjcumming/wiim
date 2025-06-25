"""Normalisation helpers for Coordinator polling.

Pure functions only – no network or HA dependencies.
"""

from __future__ import annotations

from typing import Any

from .const import (
    DSP_VERSION_KEY,
    FIRMWARE_DATE_KEY,
    FIRMWARE_KEY,
    HARDWARE_KEY,
    LATEST_VERSION_KEY,
    MCU_VERSION_KEY,
    PRESET_SLOTS_KEY,
    PROJECT_KEY,
    UPDATE_AVAILABLE_KEY,
    WMRM_VERSION_KEY,
)
from .models import DeviceInfo

__all__ = ["normalise_device_info"]


def normalise_device_info(device_info: DeviceInfo) -> dict[str, Any]:
    """Return a *new* dict with additional derived fields.

    The helper now works directly with a :class:`DeviceInfo` model to avoid
    fragile key look-ups.  The returned mapping is suitable for merging back
    into the ``device_info`` dict exposed via ``model_dump()``.
    """

    payload: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Core firmware / build information
    # ------------------------------------------------------------------
    if device_info.firmware:
        payload[FIRMWARE_KEY] = device_info.firmware

    if device_info.release_date:
        payload[FIRMWARE_DATE_KEY] = device_info.release_date

    # ------------------------------------------------------------------
    # Hardware & project identifiers
    # ------------------------------------------------------------------
    if device_info.hardware:
        payload[HARDWARE_KEY] = device_info.hardware

    if device_info.model:  # The "project" field maps to model alias
        payload[PROJECT_KEY] = device_info.model

    # ------------------------------------------------------------------
    # MCU / DSP versions
    # ------------------------------------------------------------------
    if device_info.mcu_ver is not None:
        payload[MCU_VERSION_KEY] = str(device_info.mcu_ver)

    if device_info.dsp_ver is not None:
        payload[DSP_VERSION_KEY] = str(device_info.dsp_ver)

    # ------------------------------------------------------------------
    # Preset slots – convert *preset_key* to an integer count when valid
    # ------------------------------------------------------------------
    if device_info.preset_key is not None:
        try:
            payload[PRESET_SLOTS_KEY] = int(device_info.preset_key)
        except (TypeError, ValueError):
            pass  # Leave unset if conversion fails

    # ------------------------------------------------------------------
    # WiiM multi-room protocol version
    # ------------------------------------------------------------------
    if device_info.wmrm_version:
        payload[WMRM_VERSION_KEY] = device_info.wmrm_version

    # ------------------------------------------------------------------
    # Firmware update availability
    # ------------------------------------------------------------------
    if device_info.version_update is not None:
        update_flag = str(device_info.version_update)
        payload[UPDATE_AVAILABLE_KEY] = update_flag == "1"

        if device_info.latest_version:
            payload[LATEST_VERSION_KEY] = device_info.latest_version

    return payload
