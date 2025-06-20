"""EQ (equalizer) control helpers (stub)."""

from __future__ import annotations

from typing import Any

from .api_base import WiiMError
from .const import (
    API_ENDPOINT_EQ_CUSTOM,
    API_ENDPOINT_EQ_GET,
    API_ENDPOINT_EQ_LIST,
    API_ENDPOINT_EQ_OFF,
    API_ENDPOINT_EQ_ON,
    API_ENDPOINT_EQ_PRESET,
    API_ENDPOINT_EQ_STATUS,
    EQ_PRESET_MAP,
)


class EQAPI:  # pylint: disable=too-few-public-methods
    """Equalizer helpers."""

    async def set_eq_preset(self, preset: str) -> None:  # type: ignore[override]
        if preset not in EQ_PRESET_MAP:
            raise ValueError(f"Invalid EQ preset: {preset}")
        api_value = EQ_PRESET_MAP[preset]
        await self._request(f"{API_ENDPOINT_EQ_PRESET}{api_value}")  # type: ignore[attr-defined]

    async def set_eq_custom(self, eq_values: list[int]) -> None:  # type: ignore[override]
        if len(eq_values) != 10:
            raise ValueError("EQ must have exactly 10 bands")
        eq_str = ",".join(str(v) for v in eq_values)
        await self._request(f"{API_ENDPOINT_EQ_CUSTOM}{eq_str}")  # type: ignore[attr-defined]

    async def get_eq(self) -> dict[str, Any]:  # type: ignore[override]
        return await self._request(API_ENDPOINT_EQ_GET)  # type: ignore[attr-defined]

    async def set_eq_enabled(self, enabled: bool) -> None:  # type: ignore[override]
        await self._request(API_ENDPOINT_EQ_ON if enabled else API_ENDPOINT_EQ_OFF)  # type: ignore[attr-defined]

    async def get_eq_status(self) -> bool:  # type: ignore[override]
        try:
            response = await self._request(API_ENDPOINT_EQ_STATUS)  # type: ignore[attr-defined]
            if "EQStat" in response:
                return str(response["EQStat"]).lower() == "on"
            if str(response.get("status", "")).lower() == "failed":
                try:
                    await self._request(API_ENDPOINT_EQ_GET)  # type: ignore[attr-defined]
                    return True
                except WiiMError:
                    return False
            return False
        except WiiMError:
            return False

    async def get_eq_presets(self) -> list[str]:  # type: ignore[override]
        response = await self._request(API_ENDPOINT_EQ_LIST)  # type: ignore[attr-defined]
        return response if isinstance(response, list) else []

    # END EQAPI
