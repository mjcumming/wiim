"""WiiM Media Controller - Media Handling Module.

This module handles all media-related functionality including:
- Media metadata retrieval (title, artist, album, duration, position)
- Media image handling with SSL support and caching
- Advanced features (preset playback, URL playback)

Extracted from media_controller.py as part of Phase 2 refactor to create focused,
maintainable modules following natural code boundaries.

Following the successful API refactor pattern with logical cohesion over arbitrary size limits.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError

from .const import PRESET_SLOTS_KEY

if TYPE_CHECKING:
    from .data import Speaker

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "MediaControllerMediaMixin",
]


class MediaControllerMediaMixin:
    """Mixin for media metadata, image handling, and advanced features."""

    def __init__(self) -> None:
        """Initialize media handling tracking."""
        # Media image caching (like LinkPlay integration)
        self._media_image_url_cached: str | None = None
        self._media_image_bytes: bytes | None = None
        self._media_image_content_type: str | None = None

    def clear_media_image_cache(self) -> None:
        """Clear the media image cache to force re-download on next request.

        Called when track metadata changes to ensure cover art updates.
        """
        # Clear individual cache attributes
        self._media_image_url_cached = None
        self._media_image_bytes = None
        self._media_image_content_type = None
        # Must be implemented by main controller class
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        logger = getattr(self, "_logger", _LOGGER)
        logger.debug("Cleared media image cache for %s", speaker.name)

    # ===== MEDIA METADATA =====

    def get_media_title(self) -> str | None:
        """Get clean track title."""
        # Must be implemented by main controller class
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        return speaker.get_media_title()

    def get_media_artist(self) -> str | None:
        """Get clean artist name."""
        # Must be implemented by main controller class
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        return speaker.get_media_artist()

    def get_media_album(self) -> str | None:
        """Get clean album name."""
        # Must be implemented by main controller class
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        return speaker.get_media_album()

    def get_media_duration(self) -> int | None:
        """Get track duration in seconds."""
        # Must be implemented by main controller class
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        return speaker.get_media_duration()

    def get_media_position(self) -> int | None:
        """Get current position in seconds."""
        # Must be implemented by main controller class
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        return speaker.get_media_position()

    def get_media_position_updated_at(self) -> float | None:
        """Get position update timestamp."""
        # Must be implemented by main controller class
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        return speaker.get_media_position_updated_at()

    def get_media_image_url(self) -> str | None:
        """Get media image URL."""
        # Must be implemented by main controller class
        speaker: Speaker = self.speaker  # type: ignore[attr-defined]
        return speaker.get_media_image_url()

    async def get_media_image(self) -> tuple[bytes | None, str | None]:
        """Fetch media image of current playing media.

        This method handles:
        - SSL certificate issues with self-signed certs
        - Various image formats and content types
        - Network timeouts and connection errors
        - Large image handling with size limits
        - Caching to avoid unnecessary re-downloads

        Returns:
            Tuple of (image_bytes, content_type) or (None, None) if unavailable.
        """
        image_url = self.get_media_image_url()
        if not image_url:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.debug("No media image URL available for %s", speaker.name)
            return None, None

        # Check cache first (like LinkPlay integration)
        if image_url == self._media_image_url_cached and self._media_image_bytes:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.debug("Returning cached media image for %s", speaker.name)
            return self._media_image_bytes, self._media_image_content_type

        try:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            hass = self.hass  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.debug("Fetching media image from: %s", image_url)

            # Import here to avoid circular imports
            import aiohttp
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            # Use Home Assistant's shared session for efficiency
            session = async_get_clientsession(hass)

            # Use the existing SSL context from the WiiM client
            # instead of creating a new one to avoid blocking calls
            ssl_context = await speaker.coordinator.client._get_ssl_context()

            # Set reasonable timeout for image fetching (match LinkPlay's 5s)
            timeout = aiohttp.ClientTimeout(total=5.0)

            # aiohttp only accepts the *ssl* parameter for HTTPS requests. Passing it for
            # plain HTTP raises a ValueError ("ssl parameter is only for https URLs").
            # Determine protocol first and attach SSL context only when required.

            request_kwargs = {
                "timeout": timeout,
                "headers": {"User-Agent": "HomeAssistant/WiiM-Integration"},
            }

            if image_url.lower().startswith("https"):
                # HTTPS → use permissive context from the WiiM client
                request_kwargs["ssl"] = ssl_context
            # HTTP → **do not** set the ssl kwarg (would raise ValueError)

            async with session.get(image_url, **request_kwargs) as response:
                if response.status != 200:
                    logger.warning("Failed to fetch media image for %s: HTTP %d", speaker.name, response.status)
                    # Clear cache on failure
                    self._media_image_url_cached = None
                    self._media_image_bytes = None
                    self._media_image_content_type = None
                    return None, None

                # Check content length to avoid downloading huge files
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB limit
                    logger.warning("Media image too large for %s: %s bytes", speaker.name, content_length)
                    # Clear cache on failure
                    self._media_image_url_cached = None
                    self._media_image_bytes = None
                    self._media_image_content_type = None
                    return None, None

                # Read image data
                image_data = await response.read()

                # Get content type, with fallback
                content_type = response.headers.get("Content-Type", "image/jpeg")
                if ";" in content_type:
                    content_type = content_type.split(";")[0]  # Remove charset info

                # Basic validation - ensure we got some data
                if not image_data or len(image_data) == 0:
                    logger.debug("Empty image data for %s", speaker.name)
                    # Clear cache on failure
                    self._media_image_url_cached = None
                    self._media_image_bytes = None
                    self._media_image_content_type = None
                    return None, None

                # Additional size check after download
                if len(image_data) > 10 * 1024 * 1024:  # 10MB limit
                    logger.warning("Downloaded image too large for %s: %d bytes", speaker.name, len(image_data))
                    # Clear cache on failure
                    self._media_image_url_cached = None
                    self._media_image_bytes = None
                    self._media_image_content_type = None
                    return None, None

                # Cache the result (like LinkPlay integration)
                self._media_image_url_cached = image_url
                self._media_image_bytes = image_data
                self._media_image_content_type = content_type

                logger.debug(
                    "Successfully fetched and cached media image for %s: %d bytes, type: %s",
                    speaker.name,
                    len(image_data),
                    content_type,
                )

                return image_data, content_type

        except TimeoutError:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.debug("Timeout fetching media image for %s from %s", speaker.name, image_url)
            # Clear cache on failure
            self._media_image_url_cached = None
            self._media_image_bytes = None
            self._media_image_content_type = None
            return None, None

        except aiohttp.ClientError as err:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.debug("Network error fetching media image for %s: %s", speaker.name, err)
            # Clear cache on failure
            self._media_image_url_cached = None
            self._media_image_bytes = None
            self._media_image_content_type = None
            return None, None

        except Exception as err:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.warning("Unexpected error fetching media image for %s: %s", speaker.name, err)
            # Clear cache on failure
            self._media_image_url_cached = None
            self._media_image_bytes = None
            self._media_image_content_type = None
            return None, None

    # ===== ADVANCED FEATURES =====

    async def play_preset(self, preset: int) -> None:
        """Play a device preset.

        The valid preset range depends on the device model/firmware and is
        reported via the ``preset_key`` field of *getStatusEx*.  We fetch the
        normalised value (``preset_slots``) from the coordinator data to
        validate user input dynamically instead of assuming a hard-coded
        1-6 range.

        Args:
            preset: Preset number starting at **1**
        """
        try:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)

            # Determine the maximum number of available preset slots at
            # run-time – fall back to 6 for older firmwares that do not
            # expose the ``preset_key`` field.
            max_slots: int = 6
            device_model = speaker.coordinator.data.get("device_model") if speaker.coordinator.data else None
            device_info: dict[str, Any] = (
                device_model.model_dump(exclude_none=True) if hasattr(device_model, "model_dump") else {}
            )
            try:
                max_slots = int(device_info.get(PRESET_SLOTS_KEY, max_slots))
            except (TypeError, ValueError):
                pass

            if not 1 <= preset <= max_slots:
                raise ValueError(f"Preset must be between 1 and {max_slots}, got {preset} for {speaker.name}")

            logger.debug("Playing preset %d for %s", preset, speaker.name)

            await speaker.coordinator.client.play_preset(preset)

        except Exception as err:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.error("Failed to play preset %d: %s", preset, err)
            raise HomeAssistantError(f"Failed to play preset {preset} on {speaker.name}: {err}") from err

    async def play_url(self, url: str) -> None:
        """Play URL.

        Args:
            url: Media URL to play
        """
        try:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.debug("Playing URL '%s' for %s", url, speaker.name)

            await speaker.coordinator.client.play_url(url)

        except Exception as err:
            speaker: Speaker = self.speaker  # type: ignore[attr-defined]
            logger = getattr(self, "_logger", _LOGGER)
            logger.error("Failed to play URL '%s': %s", url, err)
            raise HomeAssistantError(f"Failed to play URL: {err}") from err
