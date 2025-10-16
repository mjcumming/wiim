"""Multi-room (group) helpers for WiiM HTTP client.

All networking is delegated to the base client; this mix-in keeps only the
minimal state necessary for helper convenience (`_group_master` and
`_group_slaves`).  No attempt is made to be 100 % authoritative – callers should
still refresh via `get_multiroom_status` periodically.
"""

from __future__ import annotations

from typing import Any

from .const import (
    API_ENDPOINT_GROUP_EXIT,
    API_ENDPOINT_GROUP_KICK,
    API_ENDPOINT_GROUP_SLAVE_MUTE,
    API_ENDPOINT_GROUP_SLAVES,
)


class GroupAPI:  # mix-in – must precede base client in MRO
    """Helpers for creating / managing LinkPlay multi-room groups."""

    # pylint: disable=no-member

    # --------------------------
    # internal convenience state
    # --------------------------
    _group_master: str | None = None
    _group_slaves: list[str] = []

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    async def get_multiroom_status(self) -> dict[str, Any]:  # type: ignore[override]
        """Return the `multiroom` section from `getStatusEx` and update caches."""
        status = await self.get_status()  # type: ignore[attr-defined]
        multiroom = status.get("multiroom", {}) if isinstance(status, dict) else {}
        self._group_master = multiroom.get("master")
        self._group_slaves = multiroom.get("slaves", []) or []
        return multiroom

    # ------------------------------------------------------------------
    # Role helpers
    # ------------------------------------------------------------------

    @property
    def is_master(self) -> bool:  # noqa: D401 – property
        return self._group_master == self.host  # type: ignore[attr-defined]

    @property
    def is_slave(self) -> bool:  # noqa: D401 – property
        return self._group_master is not None and not self.is_master

    @property
    def group_master(self) -> str | None:  # noqa: D401 – property
        return self._group_master

    @property
    def group_slaves(self) -> list[str]:  # noqa: D401 – property
        return self._group_slaves if self.is_master else []

    # ------------------------------------------------------------------
    # Group operations (HTTP wrappers)
    # ------------------------------------------------------------------

    async def create_group(self) -> None:  # type: ignore[override]
        """Prepare this device to become master (no HTTP call required)."""
        self._group_master = self.host  # type: ignore[attr-defined]
        self._group_slaves = []

    async def delete_group(self) -> None:  # type: ignore[override]
        if self._group_master is None:
            raise RuntimeError("Not part of a multiroom group")
        await self._request(API_ENDPOINT_GROUP_EXIT)  # type: ignore[attr-defined]
        self._group_master = None
        self._group_slaves = []

    async def join_slave(self, master_ip: str) -> None:  # type: ignore[override]
        """Join the group hosted by *master_ip*."""
        command = f"ConnectMasterAp:JoinGroupMaster:eth{master_ip}:wifi0.0.0.0"
        endpoint = f"/httpapi.asp?command={command}"
        await self._request(endpoint)  # type: ignore[attr-defined]
        self._group_master = master_ip
        self._group_slaves = []

    async def leave_group(self) -> None:  # type: ignore[override]
        await self._request(API_ENDPOINT_GROUP_EXIT)  # type: ignore[attr-defined]
        self._group_master = None
        self._group_slaves = []

    # ------------------------------------------------------------------
    # Slave management (master-only helpers)
    # ------------------------------------------------------------------

    async def get_slaves(self) -> list[str]:  # type: ignore[override]
        resp = await self._request(API_ENDPOINT_GROUP_SLAVES)  # type: ignore[attr-defined]
        data = resp.get("slaves", []) if isinstance(resp, dict) else []
        if isinstance(data, list):
            out: list[str] = []
            for item in data:
                if isinstance(item, dict):
                    out.append(item.get("ip", ""))
                else:
                    out.append(str(item))
            return out
        return []

    async def kick_slave(self, slave_ip: str) -> None:  # type: ignore[override]
        if not self.is_master:
            raise RuntimeError("Not a group master")
        await self._request(f"{API_ENDPOINT_GROUP_KICK}{slave_ip}")  # type: ignore[attr-defined]

    async def mute_slave(self, slave_ip: str, mute: bool) -> None:  # type: ignore[override]
        if not self.is_master:
            raise RuntimeError("Not a group master")
        await self._request(f"{API_ENDPOINT_GROUP_SLAVE_MUTE}{slave_ip}:{1 if mute else 0}")  # type: ignore[attr-defined]
