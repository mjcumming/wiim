"""Role detection logic for WiiM coordinator.

This file extracts the extensive *master/slave/solo* role detection state
machine into an isolated helper for readability and to keep the main
coordinator lean.
"""

from __future__ import annotations

import logging
from typing import Any

from .models import DeviceInfo, PlayerStatus

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "detect_role_from_status_and_slaves",
]


async def detect_role_from_status_and_slaves(
    coordinator,
    status: PlayerStatus,
    multiroom: dict[str, Any],
    device_info: DeviceInfo,
) -> str:
    """Return the detected role ("master", "slave", "solo") with firmware compatibility."""

    current_role = coordinator.get_current_role()
    capabilities = getattr(coordinator, "_capabilities", {})

    # For legacy devices, use simplified detection
    if capabilities and capabilities.get("is_legacy_device", False):
        return _detect_role_legacy_firmware(coordinator, status, multiroom, device_info, current_role)

    # Enhanced detection for WiiM devices
    return _detect_role_enhanced_firmware(coordinator, status, multiroom, device_info, current_role)


def _detect_role_legacy_firmware(
    coordinator, status: PlayerStatus, multiroom: dict[str, Any], device_info: DeviceInfo, current_role: str
) -> str:
    """Simplified role detection for older Audio Pro units.

    Args:
        coordinator: WiiM coordinator instance
        status: Player status
        multiroom: Multiroom information (may contain slave_list)
        device_info: Device information
        current_role: Current detected role

    Returns:
        Detected role for legacy device
    """
    # Handle case where device_info may be None (e.g., API call failed)
    if device_info is None:
        group_field = getattr(status, "group", "0") or "0"
        master_uuid = getattr(status, "master_uuid", None)
        device_name = getattr(status, "name", "Unknown") or "Unknown"
    else:
        group_field = device_info.group or getattr(status, "group", "0") or "0"
        master_uuid = device_info.master_uuid or getattr(status, "master_uuid", None)
        device_name = device_info.name or "Unknown"

    # Get slave count from multiroom data (from getSlaveList if available)
    slaves_data = multiroom.get("slaves", 0)
    slaves_list = multiroom.get("slave_list", [])

    # Handle different data types for slaves field
    if isinstance(slaves_data, list):
        slave_count = len(slaves_data)
        slaves_list = slaves_data
    elif isinstance(slaves_data, int):
        slave_count = slaves_data
    else:
        slave_count = multiroom.get("slave_count", 0)

    # If slaves_list is a number, use it as count
    if isinstance(slaves_list, int):
        slave_count = slaves_list
        slaves_list = []
    elif isinstance(slaves_list, list) and slave_count == 0:
        slave_count = len(slaves_list)

    # Legacy devices often have unreliable group state
    # Use conservative detection to avoid false positives

    # MASTER – device has at least one slave attached (from getSlaveList)
    if slave_count > 0:
        if current_role != "master":
            _LOGGER.info(
                "LEGACY ROLE DETECTION: %s (%s) is MASTER because slave_count=%s > 0",
                coordinator.client.host,
                device_name,
                slave_count,
            )
        role = "master"
        coordinator.client._group_master = coordinator.client.host  # type: ignore[attr-defined]
        coordinator.client._group_slaves = [
            entry.get("ip") for entry in slaves_list if isinstance(entry, dict) and entry.get("ip") is not None
        ]  # type: ignore[attr-defined]

    # SLAVE – part of a group (group_field == "1") and knows master
    elif group_field == "1" and master_uuid:
        if current_role != "slave":
            _LOGGER.info(
                "LEGACY ROLE DETECTION: %s (%s) detected as SLAVE",
                coordinator.client.host,
                device_name,
            )
        role = "slave"
        coordinator.client._group_master = master_uuid  # type: ignore[attr-defined]
        coordinator.client._group_slaves = []  # type: ignore[attr-defined]

    # SOLO – group_field == "0" and no slaves detected
    elif group_field == "0":
        if current_role != "solo":
            _LOGGER.info(
                "LEGACY ROLE DETECTION: %s (%s) detected as SOLO (group='0', slave_count=%s)",
                coordinator.client.host,
                device_name,
                slave_count,
            )
        role = "solo"
        coordinator.client._group_master = None  # type: ignore[attr-defined]
        coordinator.client._group_slaves = []  # type: ignore[attr-defined]

    # Ambiguous state - treat as solo to avoid breaking controls
    else:
        _LOGGER.warning(
            "LEGACY ROLE DETECTION: %s (%s) has ambiguous group state (group='%s'), treating as SOLO",
            coordinator.client.host,
            device_name,
            group_field,
        )
        role = "solo"
        coordinator.client._group_master = None  # type: ignore[attr-defined]
        coordinator.client._group_slaves = []  # type: ignore[attr-defined]

    return role


def _detect_role_enhanced_firmware(
    coordinator, status: PlayerStatus, multiroom: dict[str, Any], device_info: DeviceInfo, current_role: str
) -> str:
    """Enhanced role detection for WiiM devices (original logic).

    Args:
        coordinator: WiiM coordinator instance
        status: Player status
        multiroom: Multiroom information
        device_info: Device information
        current_role: Current detected role

    Returns:
        Detected role for enhanced device
    """
    # Handle case where device_info may be None (e.g., API call failed)
    if device_info is None:
        group_field = getattr(status, "group", "0") or "0"
        master_uuid = getattr(status, "master_uuid", None)
        master_ip = getattr(status, "master_ip", None)
        device_uuid = getattr(status, "uuid", None)
        device_name = getattr(status, "name", "Unknown") or "Unknown"
    else:
        group_field = device_info.group or getattr(status, "group", "0") or "0"
        master_uuid = device_info.master_uuid or getattr(status, "master_uuid", None)
        master_ip = device_info.master_ip or getattr(status, "master_ip", None)
        device_uuid = device_info.uuid or getattr(status, "uuid", None)
        device_name = device_info.name or "Unknown"

    # Get slave count from API (field is "slaves", not "slave_count")
    slaves_data = multiroom.get("slaves", 0)
    slaves_list = multiroom.get("slave_list", [])

    # Handle different data types for slaves field
    if isinstance(slaves_data, list):
        # If slaves is a list, use its length as count
        slave_count = len(slaves_data)
        slaves_list = slaves_data  # Use the slaves list directly
    elif isinstance(slaves_data, int):
        # If slaves is already a count, use it
        slave_count = slaves_data
    else:
        # Fallback to slave_count field or 0
        slave_count = multiroom.get("slave_count", 0)

    # If slaves_list is a number (API sometimes returns count in slaves field), use it
    if isinstance(slaves_list, int):
        slave_count = slaves_list
        slaves_list = []
    elif isinstance(slaves_list, list) and slave_count == 0:
        slave_count = len(slaves_list)

    _log = _LOGGER.debug
    _log("Enhanced role detection inputs for %s:", coordinator.client.host)
    _log("  - device_name: '%s'", device_name)
    _log("  - device_uuid: '%s'", device_uuid)
    _log("  - group_field: '%s'", group_field)
    _log(
        "  - slave_count: %s (from multiroom.slaves=%s)",
        slave_count,
        multiroom.get("slaves"),
    )
    _log("  - slaves_list: %s", slaves_list)
    _log("  - master_uuid: '%s'", master_uuid)
    _log("  - master_ip: '%s'", master_ip)
    _log("  - current_role: '%s'", current_role)

    # ------------------------------------------------------------
    # MASTER – device has at least one slave attached
    # ------------------------------------------------------------
    if slave_count > 0:
        if current_role != "master":
            _LOGGER.info(
                "ENHANCED ROLE DETECTION: %s (%s) is MASTER because slave_count=%s > 0",
                coordinator.client.host,
                device_name,
                slave_count,
            )
        role = "master"

        # Update cached client state for group operations.
        coordinator.client._group_master = coordinator.client.host  # type: ignore[attr-defined]
        coordinator.client._group_slaves = [
            entry.get("ip") for entry in slaves_list if isinstance(entry, dict) and entry.get("ip") is not None
        ]  # type: ignore[attr-defined]

    # ------------------------------------------------------------
    # SLAVE – part of a group (group_field != "0") and knows master
    # ------------------------------------------------------------
    elif group_field != "0":
        if master_uuid or master_ip:
            if current_role != "slave":
                _LOGGER.info(
                    "ENHANCED ROLE DETECTION: %s (%s) is SLAVE – group='%s', master uuid/ip present",
                    coordinator.client.host,
                    device_name,
                    group_field,
                )
            role = "slave"
            coordinator.client._group_master = master_ip  # type: ignore[attr-defined]
            coordinator.client._group_slaves = []  # type: ignore[attr-defined]
        else:
            # Missing master info – treat as solo to avoid breaking controls.
            _LOGGER.warning(
                "ENHANCED ROLE DETECTION: %s (%s) group='%s' but NO master info – treating as SOLO",
                coordinator.client.host,
                device_name,
                group_field,
            )
            role = "solo"
            coordinator.client._group_master = None  # type: ignore[attr-defined]
            coordinator.client._group_slaves = []  # type: ignore[attr-defined]

    # ------------------------------------------------------------
    # FOLLOWER (mode=99) – treat as SLAVE while playing
    # ------------------------------------------------------------
    elif status.mode == "99":
        play_state = (status.play_state or "").lower()
        if play_state == "play":
            if current_role != "slave":
                _LOGGER.info(
                    "ENHANCED ROLE DETECTION: %s (%s) acting as FOLLOWER (mode=99) – SLAVE",
                    coordinator.client.host,
                    device_name,
                )
            role = "slave"
            coordinator.client._group_master = None  # type: ignore[attr-defined]
            coordinator.client._group_slaves = []  # type: ignore[attr-defined]
        else:
            role = "solo"
            coordinator.client._group_master = None  # type: ignore[attr-defined]
            coordinator.client._group_slaves = []  # type: ignore[attr-defined]

    # ------------------------------------------------------------
    # Default – SOLO
    # ------------------------------------------------------------
    else:
        if current_role != "solo":
            _LOGGER.info(
                "ENHANCED ROLE DETECTION: %s (%s) is SOLO (group='%s', slave_count=%s)",
                coordinator.client.host,
                device_name,
                group_field,
                slave_count,
            )
        role = "solo"
        coordinator.client._group_master = None  # type: ignore[attr-defined]
        coordinator.client._group_slaves = []  # type: ignore[attr-defined]

    _LOGGER.debug("FINAL ENHANCED ROLE for %s (%s): %s", coordinator.client.host, device_name, role.upper())

    return role
