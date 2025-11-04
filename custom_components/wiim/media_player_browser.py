"""WiiM Media Player Browser Support.

This module handles all media browsing functionality including:
- Media browser tree implementation
- Quick stations YAML loading and caching
- Hex URL decoding utilities
- App name validation and streaming service mapping

Extracted from media_player.py as part of Phase 2 refactor to create focused,
maintainable modules following natural code boundaries.

Following the successful API refactor pattern with logical cohesion over arbitrary size limits.
"""

from __future__ import annotations

import binascii
import logging
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from homeassistant.util import yaml as hass_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import Speaker

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "MediaBrowserMixin",
    "AppNameValidatorMixin",
    "QuickStationsMixin",
    "HexUrlDecoderMixin",
]


class QuickStationsMixin:
    """Mixin for quick stations YAML loading and caching."""

    def __init__(self) -> None:
        """Initialize quick stations tracking."""
        self._quick_stations_path: Path | None = None
        self._quick_station_cache: list[dict[str, str]] = []

    async def _async_load_quick_stations(self) -> list[dict[str, str]]:
        """Read user-defined quick stations from config/wiim_stations.yaml.

        YAML structure expected:
          - name: Friendly Name
            url: http://stream...
        Returns an empty list if the file is missing or malformed.
        """
        # Must be implemented by entity class
        hass: HomeAssistant = self.hass  # type: ignore[attr-defined]
        if hass is None:
            return []  # Should not happen once browse is called

        try:
            if self._quick_stations_path is None:
                self._quick_stations_path = Path(hass.config.path("wiim_stations.yaml"))

            if not self._quick_stations_path.exists():
                return []

            data = await hass.async_add_executor_job(hass_yaml.load_yaml, str(self._quick_stations_path))
            if not isinstance(data, list):
                return []

            stations: list[dict[str, str]] = []
            for entry in data:
                if isinstance(entry, dict) and entry.get("name") and entry.get("url"):
                    stations.append({"name": str(entry["name"]), "url": str(entry["url"])})

            # Cache for quick lookup in media_title
            self._quick_station_cache = stations
            return stations

        except Exception as err:  # pragma: no cover – non-critical
            _LOGGER.warning("Failed to load quick stations YAML: %s", err)
            return []

    async def _async_lookup_quick_station_title(self, url: str) -> str | None:
        """Return station name for given URL if present in quick stations list."""
        stations = await self._async_load_quick_stations()
        for st in stations:
            if st.get("url") == url:
                return st.get("name")
        return None


class HexUrlDecoderMixin:
    """Mixin for hex URL decoding utilities."""

    _HEX_CHARS = set("0123456789abcdefABCDEF")

    @staticmethod
    def _maybe_decode_hex_url(text: str) -> str | None:
        """Decode hex-encoded URL strings (e.g. '68747470...') to filename."""
        if not text or len(text) % 2 or any(c not in HexUrlDecoderMixin._HEX_CHARS for c in text):
            return None
        try:
            decoded_url = binascii.unhexlify(text).decode("utf-8", "ignore")
            path = urlparse(decoded_url).path
            if path:
                return path.rsplit("/", 1)[-1].lstrip("/") or decoded_url
            return decoded_url
        except Exception:
            return None


class AppNameValidatorMixin:
    """Mixin for app name validation and streaming service mapping."""

    def _is_valid_app_name(self, text: str) -> bool:
        """Check if app name text is valid and not garbage.

        Uses same comprehensive filtering as media text to prevent
        "wiim 192 168 1 68" and similar garbage from showing up.

        Args:
            text: The text to validate

        Returns:
            True if text is valid app/service name, False if garbage
        """
        if not text or not isinstance(text, str):
            return False

        text_clean = text.strip().lower()

        # Must be at least 2 characters
        if len(text_clean) < 2:
            return False

        # Filter out text starting with "wiim" (catches "wiim 192 168 1 68" etc.)
        if text_clean.startswith("wiim"):
            return False

        # Filter out text containing IP address patterns
        import re

        ip_pattern = r"\b\d{1,3}[\s\.]?\d{1,3}[\s\.]?\d{1,3}[\s\.]?\d{1,3}\b"
        if re.search(ip_pattern, text_clean):
            return False

        # Filter out generic garbage values
        garbage_values = {
            "unknown",
            "none",
            "null",
            "undefined",
            "n/a",
            "na",
            "not available",
            "no data",
            "empty",
            "---",
            "...",
            "loading",
            "buffering",
            "connecting",
            "error",
        }
        if text_clean in garbage_values:
            return False

        # Filter out purely numeric text (likely technical IDs)
        if text_clean.replace(" ", "").replace(".", "").replace("-", "").replace("_", "").isdigit():
            return False

        # Text passes all filters
        return True

    def get_app_name(self) -> str | None:
        """Return the name of the current streaming service.

        This maps internal source codes to user-friendly streaming service names.
        Requires the implementing class to have a 'speaker' attribute.
        """
        # Must be implemented by entity class
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        status_model = speaker.status_model

        if status_model is None:
            return None  # Typed model always expected in new architecture

        source = status_model.source
        streaming_service = getattr(status_model, "streaming_service", None)

        # First try explicit streaming service field
        if streaming_service and self._is_valid_app_name(str(streaming_service)):
            return str(streaming_service)

        if source and self._is_valid_app_name(str(source)):
            streaming_map = {
                "spotify": "Spotify",
                "tidal": "Tidal",
                "qobuz": "Qobuz",
                "amazon": "Amazon Music",
                "deezer": "Deezer",
                "airplay": "AirPlay",
                "dlna": "DLNA",
            }
            src_lower = str(source).lower()
            return streaming_map.get(src_lower)

        return None


class MediaBrowserMixin:
    """Mixin for media browser tree implementation."""

    def _media_source_filter(self, browse_item) -> bool:
        """Filter media sources to show only audio content compatible with WiiM.

        This filter ensures that only audio content is shown in the media browser,
        excluding video and other non-audio media types that WiiM cannot play.

        Args:
            browse_item: BrowseMedia item to check

        Returns:
            True if item should be shown (audio content or expandable directories)
        """
        # Always allow directories to be browsed (they may contain audio)
        if browse_item.can_expand:
            return True

        # Filter by media content type - only audio
        if hasattr(browse_item, "media_content_type") and browse_item.media_content_type:
            return browse_item.media_content_type.startswith("audio/")

        # Use the existing _is_audio_content check as fallback
        return self._is_audio_content(browse_item)

    def _is_audio_content(self, browse_item) -> bool:
        """Check if a browse item represents audio content compatible with WiiM.

        Args:
            browse_item: BrowseMedia item to check

        Returns:
            True if item is audio content that WiiM can play
        """
        from homeassistant.components.media_player.browse_media import MediaClass

        # Always allow directories to be browsed
        if browse_item.media_class == MediaClass.DIRECTORY:
            return True

        # Check for audio media classes
        audio_classes = {
            MediaClass.MUSIC,
            MediaClass.PODCAST,
            MediaClass.ALBUM,
            MediaClass.ARTIST,
            MediaClass.PLAYLIST,
            MediaClass.TRACK,
        }
        if browse_item.media_class in audio_classes:
            return True

        # Check MIME types for audio content
        if hasattr(browse_item, "media_content_type") and browse_item.media_content_type:
            content_type = browse_item.media_content_type.lower()
            if content_type.startswith("audio/"):
                return True

        # Check file extensions for common audio formats
        if hasattr(browse_item, "media_content_id") and browse_item.media_content_id:
            content_id = browse_item.media_content_id.lower()
            audio_extensions = {
                ".mp3",
                ".flac",
                ".wav",
                ".aac",
                ".ogg",
                ".m4a",
                ".wma",
                ".aiff",
                ".dsd",
                ".dsf",
                ".dff",
            }
            if any(content_id.endswith(ext) for ext in audio_extensions):
                return True

        return False

    async def async_browse_media(self, media_content_type: str | None = None, media_content_id: str | None = None):
        """Provide a Media Browser tree with Presets, Quick Stations, and HA Media Sources."""
        from homeassistant.components import media_source
        from homeassistant.components.media_player.browse_media import (
            BrowseMedia,
            MediaClass,
        )

        # HA 2024.6 renamed BrowseError → BrowseMediaError; add fallback.
        try:
            from homeassistant.components.media_player.browse_media import BrowseError as _BrowseError
        except ImportError:  # pragma: no cover
            from homeassistant.exceptions import HomeAssistantError as _BrowseError

        # Must be implemented by entity class
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        hass = self.hass  # type: ignore[attr-defined]

        _LOGGER.info(
            "Media browser request for %s: content_type=%s, content_id=%s",
            speaker.name,
            media_content_type,
            media_content_id,
        )

        # Handle media-source:// URLs by delegating to HA media source system
        if media_content_id and media_source.is_media_source_id(media_content_id):
            try:
                # Use content filter to ensure only audio content is shown
                browse_result = await media_source.async_browse_media(
                    hass, media_content_id, content_filter=self._media_source_filter
                )

                return browse_result
            except Exception as err:
                _LOGGER.warning("Failed to browse media source %s: %s", media_content_id, err)
                raise _BrowseError(f"Failed to browse media source: {err}") from err

        # Fetch presets from coordinator
        presets: list[dict] = speaker.coordinator.data.get("presets", []) if speaker.coordinator.data else []
        # Show the Presets shelf whenever the device claims to support presets OR
        # we have not yet determined support. Only hide it when we explicitly
        # know presets are unsupported.
        presets_capability = getattr(speaker.coordinator, "_presets_supported", None)
        presets_supported = presets_capability is not False  # None (unknown) or True ⇒ show

        # Load user defined quick stations (if any)
        quick_stations: list[dict[str, str]] = await self._async_load_quick_stations()

        # ===== ROOT LEVEL =====
        if media_content_id in (None, "root"):
            children: list[BrowseMedia] = []

            # Add HA Media Library sources (DLNA, local media, etc.)
            try:
                media_source_root = await media_source.async_browse_media(
                    hass, None, content_filter=self._media_source_filter
                )
                if media_source_root:
                    # Handle case where children might be a coroutine
                    root_children = media_source_root.children
                    if hasattr(root_children, "__await__"):
                        root_children = await root_children

                    # If domain is None, it's an overview of available sources
                    # Show individual sources directly (like DLNA servers) instead of nesting them
                    if media_source_root.domain is None and root_children:
                        # Extend with individual media sources (DLNA, etc.)
                        children.extend(root_children)
                    elif root_children or media_source_root.can_expand:
                        # Show Media Library entry as a container
                        children.append(
                            BrowseMedia(
                                media_class=MediaClass.DIRECTORY,
                                media_content_id="media-source://",
                                media_content_type="media_source",
                                title="Media Library",
                                can_play=False,
                                can_expand=True,
                                children=[],
                                thumbnail="mdi:folder-music",
                            )
                        )
            except Exception as err:
                _LOGGER.warning(
                    "Media sources not available for %s: %s (type: %s)", speaker.name, err, type(err).__name__
                )

            if presets_supported:
                children.append(
                    BrowseMedia(
                        media_class=MediaClass.DIRECTORY,
                        media_content_id="presets",
                        media_content_type="presets",
                        title="Presets",
                        can_play=False,
                        can_expand=True,
                        children=[],
                        thumbnail="mdi:star",
                    )
                )

            if quick_stations:
                children.append(
                    BrowseMedia(
                        media_class=MediaClass.DIRECTORY,
                        media_content_id="quick",
                        media_content_type="quick",
                        title="Quick Stations",
                        can_play=False,
                        can_expand=True,
                        children=[],
                        thumbnail="mdi:radio",
                    )
                )

            if not children:
                # No content to show – return empty shelf
                return BrowseMedia(
                    media_class=MediaClass.DIRECTORY,
                    media_content_id="root",
                    media_content_type="root",
                    title=speaker.name,
                    can_play=False,
                    can_expand=False,
                    children=[],
                )

            return BrowseMedia(
                media_class=MediaClass.DIRECTORY,
                media_content_id="root",
                media_content_type="root",
                title=speaker.name,
                can_play=False,
                can_expand=True,
                children=children,
            )

        # ===== QUICK STATIONS LEVEL =====
        if media_content_id == "quick":
            items: list[BrowseMedia] = []
            for st in quick_stations:
                items.append(
                    BrowseMedia(
                        media_class=MediaClass.MUSIC,
                        media_content_id=st["url"],
                        media_content_type="url",
                        title=st["name"],
                        can_play=True,
                        can_expand=False,
                        thumbnail=None,
                    )
                )

            # Cache for quick lookup in media_title
            self._quick_station_cache = quick_stations
            return BrowseMedia(
                media_class=MediaClass.DIRECTORY,
                media_content_id="quick",
                media_content_type="quick",
                title="Quick Stations",
                can_play=False,
                can_expand=True,
                children=items,
            )

        # ===== PRESETS LEVEL =====
        if media_content_id == "presets":
            items: list[BrowseMedia] = []
            for entry in presets:
                title = entry.get("name") or f"Preset {entry.get('number')}"
                number = entry.get("number")
                url = entry.get("url") or ""
                if not number or not url:
                    continue
                items.append(
                    BrowseMedia(
                        media_class=MediaClass.MUSIC,
                        media_content_id=str(number),
                        media_content_type="preset",
                        title=title,
                        can_play=True,
                        can_expand=False,
                        thumbnail=entry.get("picurl"),
                    )
                )

            return BrowseMedia(
                media_class=MediaClass.DIRECTORY,
                media_content_id="presets",
                media_content_type="presets",
                title="Presets",
                can_play=False,
                can_expand=True,
                children=items,
            )

        # Unknown
        raise _BrowseError("Unknown media_content_id")
