"""Audio settings helpers for WiiM HTTP client.

This mixin handles audio-related configuration including SPDIF settings,
channel balance, and other audio parameters. These endpoints are unofficial
and may not be available on all firmware versions.

It assumes the base client provides the `_request` coroutine and logging via
`_log` or `_LOGGER`. No state is stored – all results come from the device each call.
"""

from __future__ import annotations

from typing import Any

from .api_base import WiiMError
from .const import (
    API_ENDPOINT_GET_CHANNEL_BALANCE,
    API_ENDPOINT_GET_SPDIF_SAMPLE_RATE,
    API_ENDPOINT_SET_CHANNEL_BALANCE,
    API_ENDPOINT_SET_SPDIF_SWITCH_DELAY,
)


class AudioSettingsAPI:  # mixin – must appear *before* the base client in MRO
    """Audio settings helpers (SPDIF, balance, etc.)."""

    # pylint: disable=no-member

    # ------------------------------------------------------------------
    # SPDIF sample rate configuration
    # ------------------------------------------------------------------

    async def get_spdif_sample_rate(self) -> str:  # type: ignore[override]
        """Get current SPDIF output sample rate.

        Returns:
            Sample rate in Hz as string (e.g., "48000", "96000", "192000")
            Empty string if SPDIF output is not active or endpoint not supported
        """
        try:
            response = await self._request(API_ENDPOINT_GET_SPDIF_SAMPLE_RATE)  # type: ignore[attr-defined]
            return str(response) if response else ""
        except WiiMError:
            return ""

    async def set_spdif_switch_delay(self, delay_ms: int) -> None:  # type: ignore[override]
        """Set SPDIF sample rate switch latency.

        Args:
            delay_ms: Delay in milliseconds (0-3000ms)

        Raises:
            ValueError: If delay is outside valid range
            WiiMRequestError: If the request fails
        """
        if not 0 <= delay_ms <= 3000:
            raise ValueError("SPDIF switch delay must be between 0 and 3000 milliseconds")

        await self._request(f"{API_ENDPOINT_SET_SPDIF_SWITCH_DELAY}{delay_ms}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Channel balance control
    # ------------------------------------------------------------------

    async def get_channel_balance(self) -> float:  # type: ignore[override]
        """Get current left/right channel balance.

        Returns:
            Balance value from -1.0 (fully left) to 1.0 (fully right)
            Returns 0.0 if unable to retrieve
        """
        try:
            response = await self._request(API_ENDPOINT_GET_CHANNEL_BALANCE)  # type: ignore[attr-defined]
            if isinstance(response, int | float):
                return float(response)
            if isinstance(response, str):
                return float(response)
            return 0.0
        except WiiMError:
            return 0.0

    async def set_channel_balance(self, balance: float) -> None:  # type: ignore[override]
        """Set left/right channel balance.

        Args:
            balance: Balance value from -1.0 (left) to 1.0 (right)
                    0.0 = center, -1.0 = full left, 1.0 = full right

        Raises:
            ValueError: If balance is outside valid range
            WiiMRequestError: If the request fails
        """
        if not -1.0 <= balance <= 1.0:
            raise ValueError("Channel balance must be between -1.0 and 1.0")

        # Format as string, removing unnecessary decimal places
        balance_str = f"{balance:g}"
        await self._request(f"{API_ENDPOINT_SET_CHANNEL_BALANCE}{balance_str}")  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    async def center_channel_balance(self) -> None:  # type: ignore[override]
        """Center the channel balance (set to 0.0)."""
        await self.set_channel_balance(0.0)

    async def get_spdif_sample_rate_int(self) -> int:  # type: ignore[override]
        """Get SPDIF sample rate as integer.

        Returns:
            Sample rate in Hz as integer, or 0 if unable to retrieve
        """
        try:
            rate_str = await self.get_spdif_sample_rate()
            return int(rate_str) if rate_str.isdigit() else 0
        except (ValueError, AttributeError):
            return 0

    async def is_spdif_output_active(self) -> bool:  # type: ignore[override]
        """Check if SPDIF output appears to be active.

        Returns:
            True if SPDIF sample rate is available and > 0
        """
        rate = await self.get_spdif_sample_rate_int()
        return rate > 0

    async def get_audio_settings_status(self) -> dict[str, Any]:  # type: ignore[override]
        """Get comprehensive audio settings status.

        Returns:
            Dict containing current audio settings:
            - spdif_sample_rate: Current SPDIF sample rate
            - channel_balance: Current balance setting
            - spdif_active: Whether SPDIF output appears active
        """
        try:
            return {
                "spdif_sample_rate": await self.get_spdif_sample_rate(),
                "channel_balance": await self.get_channel_balance(),
                "spdif_active": await self.is_spdif_output_active(),
            }
        except WiiMError:
            return {
                "spdif_sample_rate": "",
                "channel_balance": 0.0,
                "spdif_active": False,
            }
