"""Shared utility functions for WiiM integration."""

from __future__ import annotations

import hashlib
import logging
from contextlib import asynccontextmanager

from homeassistant.exceptions import HomeAssistantError
from pywiim.exceptions import WiiMConnectionError, WiiMError, WiiMTimeoutError

_LOGGER = logging.getLogger(__name__)


def is_connection_error(err: Exception) -> bool:
    """Check if error is a connection or timeout error (including in exception chain)."""
    if isinstance(err, (WiiMConnectionError, WiiMTimeoutError)):
        return True
    # Check exception chain for wrapped connection errors
    cause = getattr(err, "__cause__", None)
    if cause and isinstance(cause, (WiiMConnectionError, WiiMTimeoutError)):
        return True
    # Check for TimeoutError in chain (common underlying cause)
    if isinstance(err, TimeoutError):
        return True
    if cause and isinstance(cause, TimeoutError):
        return True
    return False


def capitalize_source_name(source: str) -> str:
    """Capitalize source name properly (Amazon, USB, etc.).

    Handles common source names that need special capitalization:
    - amazon -> Amazon
    - usb -> USB
    - bluetooth -> Bluetooth
    - airplay -> AirPlay
    - spotify -> Spotify
    - etc.
    """
    source_lower = source.lower()

    # Special cases for proper capitalization
    special_cases = {
        "amazon": "Amazon",
        "usb": "USB",
        "bluetooth": "Bluetooth",
        "airplay": "AirPlay",
        "spotify": "Spotify",
        "tidal": "Tidal",
        "qobuz": "Qobuz",
        "deezer": "Deezer",
        "pandora": "Pandora",
        "iheartradio": "iHeartRadio",
        "tunein": "TuneIn",
        "chromecast": "Chromecast",
        "dlna": "DLNA",
        "upnp": "UPnP",
        "wifi": "WiFi",
        "coax": "Coax",
        "optical": "Optical",
        "toslink": "TOSLINK",
        "spdif": "S/PDIF",
        "rca": "RCA",
        "aux": "Aux",
        "line": "Line",
        "hdmi": "HDMI",
    }

    # Check for exact match first
    if source_lower in special_cases:
        return special_cases[source_lower]

    # Check for partial matches (e.g., "usb audio" -> "USB Audio")
    for key, value in special_cases.items():
        if source_lower.startswith(key):
            # Replace the matched part with capitalized version
            return value + source[len(key) :].title()

    # Default: title case (first letter of each word capitalized)
    return source.title()


def derive_media_player_state(play_state: str | None) -> str | None:
    """Map pywiim's play_state to MediaPlayerState string.

    Args:
        play_state: The play state from pywiim Player

    Returns:
        MediaPlayerState string or None
    """
    from homeassistant.components.media_player import MediaPlayerState

    if not play_state:
        return MediaPlayerState.IDLE

    play_state_str = str(play_state).lower()
    if play_state_str in ("play", "playing", "load"):
        return MediaPlayerState.PLAYING
    if play_state_str == "pause":
        return MediaPlayerState.PAUSED
    return MediaPlayerState.IDLE


def generate_cover_art_hash(state: str | None, title: str | None, artist: str | None, album: str | None = None) -> str:
    """Generate a hash for cover art based on state and metadata.

    Args:
        state: Current media player state
        title: Media title
        artist: Media artist
        album: Media album (optional)

    Returns:
        Hex digest hash string (16 characters)
    """
    title = title or ""
    artist = artist or ""
    album = album or ""
    state = str(state or "idle")

    if album:
        track_id = f"{state}|{title}|{artist}|{album}".encode()
    else:
        track_id = f"{state}|{title}|{artist}".encode()

    return hashlib.sha256(track_id).hexdigest()[:16]


@asynccontextmanager
async def wiim_command(entity_name: str, operation: str):
    """Context manager for consistent WiiM command error handling.

    Args:
        entity_name: Name of the entity performing the operation
        operation: Description of the operation (e.g., "set volume", "play")

    Yields:
        None - use with async with statement

    Raises:
        HomeAssistantError: Wrapped WiiM error with appropriate message
    """
    try:
        yield
    except WiiMError as err:
        if is_connection_error(err):
            _LOGGER.warning("%s: %s failed (connection issue): %s", entity_name, operation, err)
            raise HomeAssistantError(f"{operation} on {entity_name}: device unreachable") from err
        _LOGGER.error("%s: %s failed: %s", entity_name, operation, err, exc_info=True)
        raise HomeAssistantError(f"Failed to {operation}: {err}") from err
