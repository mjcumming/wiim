"""Preset helpers – manage and play stored preset slots."""

from __future__ import annotations

from typing import Any

from .const import API_ENDPOINT_PRESET, API_ENDPOINT_PRESET_INFO


class PresetAPI:  # mix-in
    """List and play device presets."""

    async def get_presets(self) -> list[dict[str, Any]]:  # type: ignore[override]
        """Return list of preset entries from getPresetInfo.

        Each entry looks like::
            {"number": 1, "name": "Radio Paradise", "url": "...", "picurl": "..."}
        """
        try:
            payload = await self._request(API_ENDPOINT_PRESET_INFO)  # type: ignore[attr-defined]
            if isinstance(payload, dict):
                return payload.get("preset_list", []) or []
            return []
        except Exception:  # noqa: BLE001 – caller decides on failure
            raise  # let higher layer treat as capability unsupported

    async def play_preset(self, preset: int) -> None:  # type: ignore[override]
        """Initiate playback of preset slot *preset* (1-based)."""
        if preset < 1:
            raise ValueError("Preset number must be 1 or higher")
        await self._request(f"{API_ENDPOINT_PRESET}{preset}")  # type: ignore[attr-defined]
