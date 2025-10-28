"""Centralized state store for WiiM device."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

_LOGGER = logging.getLogger(__name__)


@dataclass
class WiiMState:
    """Centralized state store for WiiM device.

    Stores all device state that comes from UPnP events or HTTP polling.
    Only meaningful state changes trigger entity updates.
    """

    # Transport state
    play_state: str | None = None  # play, pause, stop, etc.
    position: int | None = None  # Current position in seconds
    duration: int | None = None  # Track duration in seconds

    # Media metadata
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    image_url: str | None = None

    # Volume and mute
    volume: float | None = None  # 0.0 - 1.0
    muted: bool | None = None

    # Source
    source: str | None = None

    # Internal tracking
    _last_update_ts: float | None = field(default=None, init=False, repr=False)

    def apply_diff(self, changes: dict[str, Any]) -> bool:
        """Apply state changes and return True if meaningful change occurred.

        Args:
            changes: Dict of state changes to apply

        Returns:
            True if state meaningfully changed, False otherwise
        """
        import time

        changed = False

        for key, value in changes.items():
            old_value = getattr(self, key, None)
            if old_value != value:
                setattr(self, key, value)
                changed = True
                _LOGGER.debug(
                    "State change: %s: %s -> %s",
                    key,
                    old_value,
                    value,
                )

        if changed:
            self._last_update_ts = time.time()

        return changed

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary."""
        return {
            "play_state": self.play_state,
            "position": self.position,
            "duration": self.duration,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "image_url": self.image_url,
            "volume": self.volume,
            "muted": self.muted,
            "source": self.source,
        }

    def __repr__(self) -> str:
        """String representation."""
        state_str = ", ".join(f"{k}={v}" for k, v in self.to_dict().items() if v is not None)
        return f"WiiMState({state_str})"
