"""Media image download & caching helper.

Extracted from MediaPlayerController to reduce file size and improve reusability.
The helper keeps a per-instance in-memory cache (URL → bytes, content-type).
It intentionally contains **no** Home-Assistant specific code except for
requiring the shared aiohttp client session via `hass`.
"""
from __future__ import annotations

import logging
import asyncio
from typing import Tuple, Any

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

__all__ = ["MediaImageCache"]


class MediaImageCache:
    """Lightweight cache for album-art images served by WiiM devices."""

    _MAX_BYTES = 10 * 1024 * 1024  # 10 MB hard limit

    def __init__(self) -> None:
        self._cached_url: str | None = None
        self._cached_bytes: bytes | None = None
        self._cached_content_type: str | None = None

    async def fetch(self, hass, url: str, *, ssl_context) -> Tuple[bytes | None, str | None]:
        """Return (bytes, content_type) for *url* or (None, None) on failure.

        The helper remembers the last successful image so repeated UI refreshes
        don't hammer the device.
        """
        if not url:
            return None, None

        # Return cached result when possible
        if url == self._cached_url and self._cached_bytes:
            return self._cached_bytes, self._cached_content_type

        session = async_get_clientsession(hass)
        timeout = aiohttp.ClientTimeout(total=5.0)
        req_kwargs: dict[str, Any] = {
            "timeout": timeout,
            "headers": {"User-Agent": "HomeAssistant/WiiM-Integration"},
        }
        if url.lower().startswith("https"):
            req_kwargs["ssl"] = ssl_context

        try:
            async with session.get(url, **req_kwargs) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Image fetch failed: HTTP %s for %s", resp.status, url)
                    self._clear()
                    return None, None

                if (clen := resp.headers.get("Content-Length")) and int(clen) > self._MAX_BYTES:
                    _LOGGER.debug("Image too large (%s bytes) – skipping %s", clen, url)
                    self._clear()
                    return None, None

                data = await resp.read()
                if not data or len(data) > self._MAX_BYTES:
                    _LOGGER.debug("Image empty or too large after download from %s", url)
                    self._clear()
                    return None, None

                ctype = resp.headers.get("Content-Type", "image/jpeg").split(";", 1)[0]

                # Cache result
                self._cached_url = url
                self._cached_bytes = data
                self._cached_content_type = ctype

                return data, ctype
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Network error fetching image %s: %s", url, err)
        except Exception as err:  # pragma: no cover – safety net
            _LOGGER.debug("Unexpected error fetching image %s: %s", url, err)

        self._clear()
        return None, None

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    def _clear(self) -> None:
        self._cached_url = None
        self._cached_bytes = None
        self._cached_content_type = None 