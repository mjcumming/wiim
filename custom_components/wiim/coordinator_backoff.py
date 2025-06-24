"""Back-off logic for polling failures.

Keeps the ruleset separate from the main coordinator so the class remains
small and testable.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final

# Mapping: consecutive_failures → new polling interval (seconds)
_BACKOFF_STEPS: Final[dict[int, int]] = {
    2: 10,  # after 2 failures → 10-second polling
    3: 30,  # after 3 → 30-second polling
    5: 60,  # after 5 → 60-second polling
}


class BackoffController:
    """Tracks consecutive failures and recommends next interval."""

    def __init__(self) -> None:  # noqa: D401
        self._failures = 0

    # ---------------------------------------------------------------------
    # Recording helpers
    # ---------------------------------------------------------------------

    def record_success(self) -> None:
        """Reset failure counter after a successful poll."""
        self._failures = 0

    def record_failure(self) -> None:
        """Increment failure counter after an exception."""
        self._failures += 1

    # ---------------------------------------------------------------------
    # Query helpers
    # ---------------------------------------------------------------------

    @property
    def consecutive_failures(self) -> int:  # noqa: D401
        return self._failures

    def next_interval(self, default_seconds: int) -> timedelta:
        """Return recommended polling interval after last event."""
        # Find the highest threshold that has been reached
        active_seconds = default_seconds
        for threshold, seconds in sorted(_BACKOFF_STEPS.items()):
            if self._failures >= threshold:
                active_seconds = seconds
        return timedelta(seconds=active_seconds)
