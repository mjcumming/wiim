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
    """Return the detected role ("master", "slave", "solo")."""

    current_role = coordinator.get_current_role()

    group_field = device_info.group or status.group or "0"
    master_uuid = device_info.master_uuid or getattr(status, "master_uuid", None)
    master_ip = device_info.master_ip or getattr(status, "master_ip", None)
    device_uuid = device_info.uuid or getattr(status, "uuid", None)

    device_name = device_info.name or "Unknown"

    slave_count = multiroom.get("slave_count", 0)
    slaves_list = multiroom.get("slaves", [])

    _log = _LOGGER.debug
    _log("Role detection inputs for %s:", coordinator.client.host)
    _log("  - device_name: '%s'", device_name)
    _log("  - device_uuid: '%s'", device_uuid)
    _log("  - group_field: '%s'", group_field)
    _log("  - slave_count: %s", slave_count)
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
                "ROLE DETECTION: %s (%s) is MASTER because slave_count=%s > 0",
                coordinator.client.host,
                device_name,
                slave_count,
            )
        role = "master"

        # Update cached client state for group operations.
        coordinator.client._group_master = coordinator.client.host  # type: ignore[attr-defined]
        coordinator.client._group_slaves = [
            entry.get("ip")
            for entry in slaves_list
            if isinstance(entry, dict) and entry.get("ip") is not None
        ]  # type: ignore[attr-defined]

    # ------------------------------------------------------------
    # SLAVE – part of a group (group_field != "0") and knows master
    # ------------------------------------------------------------
    elif group_field != "0":
        if master_uuid or master_ip:
            if current_role != "slave":
                _LOGGER.info(
                    "ROLE DETECTION: %s (%s) is SLAVE – group='%s', master uuid/ip present",
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
                "ROLE DETECTION: %s (%s) group='%s' but NO master info – treating as SOLO",
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
                    "ROLE DETECTION: %s (%s) acting as FOLLOWER (mode=99) – SLAVE",
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
                "ROLE DETECTION: %s (%s) is SOLO (group='%s', slave_count=%s)",
                coordinator.client.host,
                device_name,
                group_field,
                slave_count,
            )
        role = "solo"
        coordinator.client._group_master = None  # type: ignore[attr-defined]
        coordinator.client._group_slaves = []  # type: ignore[attr-defined]

    _LOGGER.debug("FINAL ROLE for %s (%s): %s", coordinator.client.host, device_name, role.upper())

    return role
