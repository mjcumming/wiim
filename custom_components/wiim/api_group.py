"""Multi-room (group) control helpers (stub).

This mixin will eventually house create_group/join_slave/leave_group etc.
"""

from __future__ import annotations

from typing import Any

from .api_base import WiiMError
from .const import (
    API_ENDPOINT_GROUP_EXIT,
    API_ENDPOINT_GROUP_SLAVES,
    API_ENDPOINT_GROUP_KICK,
    API_ENDPOINT_GROUP_SLAVE_MUTE,
)


class GroupAPI:  # pylint: disable=too-few-public-methods
    """Multi-room helpers."""

    # ------------------------------------------------------------------
    # Status ------------------------------------------------------------
    # ------------------------------------------------------------------

    async def get_multiroom_status(self) -> dict[str, Any]:  # type: ignore[override]
        status = await self.get_status()  # type: ignore[attr-defined]
        multiroom = status.get("multiroom", {})
        self._group_master = multiroom.get("master")  # type: ignore[attr-defined]
        self._group_slaves = multiroom.get("slaves", [])  # type: ignore[attr-defined]
        return multiroom

    async def get_multiroom_info(self) -> dict[str, Any]:  # type: ignore[override]
        """Return detailed multiroom info (slave list & count)."""
        try:
            response = await self._request(API_ENDPOINT_GROUP_SLAVES)  # type: ignore[attr-defined]
            slaves_count = response.get("slaves", 0)
            slave_list = response.get("slave_list", [])
            return {
                "slave_count": slaves_count,
                "slaves": slave_list,
                "slave_list": slave_list,
            }
        except WiiMError:
            return {"slaves": [], "slave_count": 0, "slave_list": []}

    async def get_slaves(self) -> list[str]:  # type: ignore[override]
        try:
            response = await self._request(API_ENDPOINT_GROUP_SLAVES)  # type: ignore[attr-defined]
            slaves_data = response.get("slaves", [])
            if isinstance(slaves_data, list):
                ips: list[str] = []
                for entry in slaves_data:
                    if isinstance(entry, dict) and "ip" in entry:
                        ips.append(entry["ip"])
                    elif isinstance(entry, str):
                        ips.append(entry)
                return ips
            return []
        except WiiMError:
            return []

    # ------------------------------------------------------------------
    # Master / slave ops ------------------------------------------------
    # ------------------------------------------------------------------

    async def create_group(self) -> None:  # type: ignore[override]
        self._group_master = self.host  # type: ignore[attr-defined]
        self._group_slaves = []  # type: ignore[attr-defined]

    async def delete_group(self) -> None:  # type: ignore[override]
        if not getattr(self, "_group_master", None):
            raise WiiMError("Not part of a multiroom group")
        await self._request(API_ENDPOINT_GROUP_EXIT)  # type: ignore[attr-defined]
        self._group_master = None  # type: ignore[attr-defined]
        self._group_slaves = []  # type: ignore[attr-defined]

    async def join_slave(self, master_ip: str) -> None:  # type: ignore[override]
        command = f"ConnectMasterAp:JoinGroupMaster:eth{master_ip}:wifi0.0.0.0"
        endpoint = f"/httpapi.asp?command={command}"
        await self._request(endpoint)  # type: ignore[attr-defined]
        self._group_master = master_ip  # type: ignore[attr-defined]
        self._group_slaves = []  # type: ignore[attr-defined]

    async def leave_group(self) -> None:  # type: ignore[override]
        await self._request(API_ENDPOINT_GROUP_EXIT)  # type: ignore[attr-defined]
        self._group_master = None  # type: ignore[attr-defined]
        self._group_slaves = []  # type: ignore[attr-defined]

    async def kick_slave(self, slave_ip: str) -> None:  # type: ignore[override]
        if not self.is_master:
            raise WiiMError("Not a group master")
        await self._request(f"{API_ENDPOINT_GROUP_KICK}{slave_ip}")  # type: ignore[attr-defined]

    async def mute_slave(self, slave_ip: str, mute: bool) -> None:  # type: ignore[override]
        if not self.is_master:
            raise WiiMError("Not a group master")
        await self._request(f"{API_ENDPOINT_GROUP_SLAVE_MUTE}{slave_ip}:{1 if mute else 0}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Properties --------------------------------------------------------
    # ------------------------------------------------------------------

    @property
    def is_master(self) -> bool:  # type: ignore[override]
        return getattr(self, "_group_master", None) == self.host  # type: ignore[attr-defined]

    @property
    def is_slave(self) -> bool:  # type: ignore[override]
        return getattr(self, "_group_master", None) is not None and not self.is_master

    @property
    def group_master(self) -> str | None:  # type: ignore[override]
        return getattr(self, "_group_master", None)

    @property
    def group_slaves(self) -> list[str]:  # type: ignore[override]
        if self.is_master:
            return getattr(self, "_group_slaves", [])
        return []

    # END GroupAPI
