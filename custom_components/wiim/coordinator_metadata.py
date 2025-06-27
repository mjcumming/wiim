"""Metadata polling helpers.

Collects and normalises track/artist/album information returned by the
WiiM / LinkPlay firmware.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from .api import WiiMError
from .models import PlayerStatus, TrackMetadata

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "fetch_track_metadata",
]


async def fetch_track_metadata(coordinator, status: PlayerStatus) -> TrackMetadata:
    """Return rich track metadata with graceful fall-back.

    The logic is identical to the previous ``WiiMCoordinator._get_track_metadata_defensive``
    implementation but has been converted into a standalone helper so the heavy
    lifting sits outside the main coordinator class.
    """

    _LOGGER.debug("Getting track metadata for %s", coordinator.client.host)

    # Convert the *typed* model into a plain dict once so we can reuse the
    # battle-tested parsing logic with minimal changes.
    status_dict: dict[str, Any] = cast(dict[str, Any], status.model_dump(exclude_none=True))

    # ------------------------------------------------------------------
    # Shortcut – we already know the device does *not* support getMetaInfo
    # ------------------------------------------------------------------
    if coordinator._metadata_supported is False:  # noqa: SLF001
        _LOGGER.debug("Device %s doesn't support getMetaInfo – using basic metadata", coordinator.client.host)
        return TrackMetadata.model_validate(await _extract_basic_metadata(coordinator, status_dict))

    try:
        _LOGGER.debug("Attempting getMetaInfo for %s", coordinator.client.host)
        metadata_response = await coordinator.client.get_meta_info()
        _LOGGER.debug("getMetaInfo response for %s: %s", coordinator.client.host, metadata_response)

        if metadata_response and metadata_response.get("metaData"):
            metadata = metadata_response["metaData"]
            if coordinator._metadata_supported is None:  # noqa: SLF001
                coordinator._metadata_supported = True  # noqa: SLF001
                _LOGGER.info("getMetaInfo works for %s – full metadata available", coordinator.client.host)

            # Enhance metadata with cover art extraction and merge with status fallbacks.
            enhanced_metadata = _enhance_metadata_with_artwork(coordinator, metadata, status_dict)
            # Merge missing fields from status data as fallback
            merged_metadata = _merge_metadata_with_status_fallback(enhanced_metadata, status_dict)
            _LOGGER.debug("Enhanced and merged metadata for %s: %s", coordinator.client.host, merged_metadata)
            return TrackMetadata.model_validate(merged_metadata)

    except WiiMError as err:
        if coordinator._metadata_supported is None:  # noqa: SLF001
            coordinator._metadata_supported = False  # noqa: SLF001
            _LOGGER.info("getMetaInfo not supported for %s: %s – using basic metadata", coordinator.client.host, err)

    # ------------------------------------------------------------------
    # Fallback – old firmwares, missing endpoint, etc.
    # ------------------------------------------------------------------
    _LOGGER.debug("Using basic metadata fallback for %s", coordinator.client.host)
    return TrackMetadata.model_validate(await _extract_basic_metadata(coordinator, status_dict))


# ---------------------------------------------------------------------------
# Internal helpers – kept private to this module
# ---------------------------------------------------------------------------


def _merge_metadata_with_status_fallback(metadata: dict, status: dict) -> dict[str, Any]:
    """Merge metadata with status data as fallback for missing fields."""
    merged = metadata.copy()

    # Use status data as fallback for missing essential fields
    if not merged.get("title") and status.get("title"):
        merged["title"] = status["title"]
    if not merged.get("artist") and status.get("artist"):
        merged["artist"] = status["artist"]
    if not merged.get("album") and status.get("album"):
        merged["album"] = status["album"]

    return merged


def _enhance_metadata_with_artwork(coordinator, metadata: dict, status: dict) -> dict[str, Any]:
    """Add artwork URL(s) to *metadata* in-place, returns *enhanced* dict."""

    enhanced = metadata.copy()

    artwork_fields = [
        "cover",
        "cover_url",
        "albumart",
        "albumArtURI",
        "albumArtUri",
        "albumarturi",
        "art_url",
        "artwork_url",
        "pic_url",
        "thumbnail",
        "image",
        "coverart",
        "cover_art",
        "album_art",
        "artworkUrl",
        "imageUrl",
    ]

    _LOGGER.debug("Looking for artwork in metadata for %s", coordinator.client.host)
    _LOGGER.debug("Metadata fields available: %s", list(metadata.keys()))

    artwork_url: str | None = None
    found_field: str | None = None

    # 1. Try metaData payload first …
    for field in artwork_fields:
        artwork_url = metadata.get(field)  # type: ignore[index]
        if artwork_url and artwork_url != "un_known":  # Filter invalid URLs
            found_field = f"metadata.{field}"
            break

    # 2. … then fall back to the original *status* payload.
    if not artwork_url:
        for field in artwork_fields:
            artwork_url = status.get(field)  # type: ignore[index]
            if artwork_url and artwork_url != "un_known":
                found_field = f"status.{field}"
                break

    # Track last artwork URL to reduce repetitive logging (uses instance attr).
    if not hasattr(coordinator, "_last_artwork_url"):
        coordinator._last_artwork_url = None  # type: ignore[attr-defined]

    if artwork_url and artwork_url != "un_known":
        enhanced["entity_picture"] = artwork_url
        enhanced["cover_url"] = artwork_url

        if coordinator._last_artwork_url != artwork_url:  # type: ignore[attr-defined]
            _LOGGER.info("🎨 Artwork changed for %s (%s): %s", coordinator.client.host, found_field, artwork_url)
            coordinator._last_artwork_url = artwork_url  # type: ignore[attr-defined]
        else:
            _LOGGER.debug("🎨 Artwork unchanged for %s: %s", coordinator.client.host, artwork_url)
    else:
        if getattr(coordinator, "_last_artwork_url", None):
            _LOGGER.info("🎨 Artwork removed for %s", coordinator.client.host)
            coordinator._last_artwork_url = None  # type: ignore[attr-defined]
        else:
            _LOGGER.debug("❌ No valid artwork URL found for %s", coordinator.client.host)

    return enhanced


async def _extract_basic_metadata(coordinator, status: dict) -> dict[str, Any]:
    """Extract minimal metadata (title/artist/album/artwork) from *status*.

    For older LinkPlay devices, also attempts to fetch artwork from getPlayerStatus
    if not found in the basic status payload.
    """

    _LOGGER.debug("Extracting basic metadata from status for %s", coordinator.client.host)

    metadata: dict[str, Any] = {}
    if status.get("title"):
        metadata["title"] = status["title"]  # type: ignore[index]
    if status.get("artist"):
        metadata["artist"] = status["artist"]  # type: ignore[index]
    if status.get("album"):
        metadata["album"] = status["album"]  # type: ignore[index]

    artwork_fields = [
        "cover",
        "cover_url",
        "albumart",
        "albumArtURI",
        "albumArtUri",
        "albumarturi",
        "art_url",
        "artwork_url",
        "pic_url",
        "entity_picture",
        "thumbnail",
        "image",
        "coverart",
        "cover_art",
        "album_art",
        "artworkUrl",
        "imageUrl",
    ]

    artwork_url: str | None = None
    found_field: str | None = None
    for field in artwork_fields:
        artwork_url = status.get(field)  # type: ignore[index]
        if artwork_url and artwork_url != "un_known":
            found_field = f"status.{field}"
            break

    # If no artwork found in basic status, try fetching fresh status for older devices
    if not artwork_url:
        _LOGGER.debug("No artwork in basic status for %s, attempting fresh status fetch", coordinator.client.host)
        try:
            fresh_status = await coordinator.client.get_status()
            if fresh_status:
                _LOGGER.debug("Fresh status fields for %s: %s", coordinator.client.host, list(fresh_status.keys()))
                for field in artwork_fields:
                    artwork_url = fresh_status.get(field)  # type: ignore[index]
                    if artwork_url and artwork_url != "un_known":
                        found_field = f"fresh_status.{field}"
                        break
        except (WiiMError, Exception) as err:
            _LOGGER.debug("Failed to fetch fresh status for artwork on %s: %s", coordinator.client.host, err)

    if artwork_url and artwork_url != "un_known":
        metadata["entity_picture"] = artwork_url
        metadata["cover_url"] = artwork_url
        _LOGGER.info(
            "🎨 Artwork extracted from basic status for %s (%s): %s", coordinator.client.host, found_field, artwork_url
        )
    else:
        _LOGGER.debug("❌ No valid artwork URL found in basic status for %s", coordinator.client.host)

    _LOGGER.debug(
        "Basic metadata extracted for %s: title='%s', artist='%s', album='%s', artwork='%s'",
        coordinator.client.host,
        metadata.get("title"),
        metadata.get("artist"),
        metadata.get("album"),
        "YES" if metadata.get("entity_picture") else "NO",
    )

    return metadata
