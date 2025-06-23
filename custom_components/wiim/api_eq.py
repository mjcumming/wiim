"""Equaliser (EQ) helpers for WiiM HTTP client.

This mixin handles preset selection, custom 10-band EQ upload, enable/disable,
and querying current EQ status and the list of presets.

It assumes the base client provides the `_request` coroutine, `_EQ_NUMERIC_MAP`
(for code→name), and logging via `_log` or `_LOGGER`.  No state is stored – all
results come from the device each call.
"""

from __future__ import annotations

from typing import Any

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


class EQAPI:  # mix-in – appear before base client in MRO
    """Equaliser helpers (presets, on/off, custom bands)."""

    # ------------------------------------------------------------------
    # Preset handling
    # ------------------------------------------------------------------

    async def set_eq_preset(self, preset: str) -> None:  # type: ignore[override]
        """Apply a named EQ preset (e.g. "rock", "flat")."""
        if preset not in EQ_PRESET_MAP:
            raise ValueError(f"Invalid EQ preset: {preset}")
        api_value = EQ_PRESET_MAP[preset]  # convert key → label
        await self._request(f"{API_ENDPOINT_EQ_PRESET}{api_value}")  # type: ignore[attr-defined]

    async def get_eq_presets(self) -> list[str]:  # type: ignore[override]
        resp = await self._request(API_ENDPOINT_EQ_LIST)  # type: ignore[attr-defined]
        return resp if isinstance(resp, list) else []

    # ------------------------------------------------------------------
    # Custom 10-band upload
    # ------------------------------------------------------------------

    async def set_eq_custom(self, eq_values: list[int]) -> None:  # type: ignore[override]
        """Upload custom 10-band EQ in LinkPlay format (list of 10 ints)."""
        if len(eq_values) != 10:
            raise ValueError("EQ must have exactly 10 bands")
        eq_str = ",".join(str(v) for v in eq_values)
        await self._request(f"{API_ENDPOINT_EQ_CUSTOM}{eq_str}")  # type: ignore[attr-defined]

    async def get_eq(self) -> dict[str, Any]:  # type: ignore[override]
        return await self._request(API_ENDPOINT_EQ_GET)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Enable / disable
    # ------------------------------------------------------------------

    async def set_eq_enabled(self, enabled: bool) -> None:  # type: ignore[override]
        await self._request(API_ENDPOINT_EQ_ON if enabled else API_ENDPOINT_EQ_OFF)  # type: ignore[attr-defined]

    async def get_eq_status(self) -> bool:  # type: ignore[override]
        """Return True if device reports EQ enabled (best-effort)."""
        try:
            response = await self._request(API_ENDPOINT_EQ_STATUS)  # type: ignore[attr-defined]
            if "EQStat" in response:
                return str(response["EQStat"]).lower() == "on"
            if str(response.get("status", "")).lower() == "failed":
                # heuristic: if /getEQ succeeds, EQ subsystem exists – treat as enabled
                try:
                    await self._request(API_ENDPOINT_EQ_GET)  # type: ignore[attr-defined]
                    return True
                except Exception:  # noqa: BLE001
                    return False
            return False
        except Exception:  # noqa: BLE001
            return False
