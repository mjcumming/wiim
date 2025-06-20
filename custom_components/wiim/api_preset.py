"""Preset handling helpers (stub)."""

from __future__ import annotations

from typing import Any

from .api_base import WiiMError, WiiMResponseError
from .const import API_ENDPOINT_PRESET, API_ENDPOINT_PRESET_INFO


class PresetAPI:  # pylint: disable=too-few-public-methods
    """Preset list handling."""

    async def play_preset(self, preset: int) -> None:  # type: ignore[override]
        if preset < 1:
            raise ValueError("Preset number must be 1 or higher")
        await self._request(f"{API_ENDPOINT_PRESET}{preset}")  # type: ignore[attr-defined]

    async def get_presets(self) -> list[dict[str, Any]]:  # type: ignore[override]
        try:
            payload = await self._request(API_ENDPOINT_PRESET_INFO)  # type: ignore[attr-defined]
            if not isinstance(payload, dict):
                raise WiiMResponseError("Invalid preset info response")
            return payload.get("preset_list", [])
        except WiiMError:
            raise  # Propagate so callers can handle capability absence

    # END PresetAPI
