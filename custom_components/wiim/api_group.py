"""Multi-room (group) control helpers (stub).

This mixin will eventually house create_group/join_slave/leave_group etc.
"""

from __future__ import annotations

from typing import Any

from .api_base import WiiMError
from .const import (
    API_ENDPOINT_GROUP_EXIT,
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
