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

    # CRITICAL FIX: Keep the original raw status dict for artwork extraction
    # Pydantic filtering with exclude_none=True may remove artwork fields that older devices provide
    raw_status_dict: dict[str, Any] = cast(dict[str, Any], status.model_dump(exclude_none=False))

    # ------------------------------------------------------------------
    # Shortcut – we already know the device does *not* support getMetaInfo
    # ------------------------------------------------------------------
    if coordinator._metadata_supported is False:  # noqa: SLF001
        _LOGGER.debug("Device %s doesn't support getMetaInfo – using basic metadata", coordinator.client.host)
        basic_metadata = await _extract_basic_metadata(coordinator, status_dict)
        # RESTORED OLD PATTERN: Always enhance metadata with artwork using raw status
        enhanced_metadata = _enhance_metadata_with_artwork(coordinator, basic_metadata, raw_status_dict)
        return TrackMetadata.model_validate(enhanced_metadata)

    try:
        _LOGGER.debug("Attempting getMetaInfo for %s", coordinator.client.host)
        metadata_response = await coordinator.client.get_meta_info()
        _LOGGER.debug("getMetaInfo response for %s: %s", coordinator.client.host, metadata_response)

        if metadata_response and metadata_response.get("metaData"):
            metadata = metadata_response["metaData"]
            if coordinator._metadata_supported is None:  # noqa: SLF001
                coordinator._metadata_supported = True  # noqa: SLF001
                _LOGGER.info("getMetaInfo works for %s – full metadata available", coordinator.client.host)

            # Extract audio quality fields
            audio_quality = _extract_audio_quality_fields(metadata)
            metadata.update(audio_quality)

            # Enhance metadata with cover art extraction and merge with status fallbacks.
            # FIXED: Use raw status dict for artwork extraction, not Pydantic-filtered
            enhanced_metadata = _enhance_metadata_with_artwork(coordinator, metadata, raw_status_dict)
            # Merge missing fields from status data as fallback
            merged_metadata = _merge_metadata_with_status_fallback(enhanced_metadata, status_dict)
            _LOGGER.debug("Enhanced and merged metadata for %s: %s", coordinator.client.host, merged_metadata)

            # Store valid metadata for persistence during track changes
            if any(
                [merged_metadata.get("sample_rate"), merged_metadata.get("bit_depth"), merged_metadata.get("bit_rate")]
            ):
                coordinator._last_valid_metadata = {
                    "sample_rate": merged_metadata.get("sample_rate"),
                    "bit_depth": merged_metadata.get("bit_depth"),
                    "bit_rate": merged_metadata.get("bit_rate"),
                }

            return TrackMetadata.model_validate(merged_metadata)

    except WiiMError as err:
        if coordinator._metadata_supported is None:  # noqa: SLF001
            coordinator._metadata_supported = False  # noqa: SLF001
            _LOGGER.info("getMetaInfo not supported for %s: %s – using basic metadata", coordinator.client.host, err)

    # ------------------------------------------------------------------
    # Fallback – old firmwares, missing endpoint, etc.
    # ------------------------------------------------------------------
    _LOGGER.debug("Using basic metadata fallback for %s", coordinator.client.host)
    basic_metadata = await _extract_basic_metadata(coordinator, status_dict)
    # RESTORED OLD PATTERN: Always enhance metadata with artwork using raw status
    enhanced_metadata = _enhance_metadata_with_artwork(coordinator, basic_metadata, raw_status_dict)
    return TrackMetadata.model_validate(enhanced_metadata)


# ---------------------------------------------------------------------------
# Internal helpers – kept private to this module
# ---------------------------------------------------------------------------


def _extract_audio_quality_fields(metadata: dict) -> dict[str, Any]:
    """Extract audio quality fields from metadata response."""
    audio_quality = {}

    # Extract sample rate
    sample_rate = metadata.get("sampleRate")
    if sample_rate and sample_rate not in ("unknow", "unknown", "un_known", ""):
        try:
            audio_quality["sample_rate"] = int(sample_rate)
        except (ValueError, TypeError):
            _LOGGER.debug("Invalid sample rate value: %s", sample_rate)

    # Extract bit depth
    bit_depth = metadata.get("bitDepth")
    if bit_depth and bit_depth not in ("unknow", "unknown", "un_known", ""):
        try:
            audio_quality["bit_depth"] = int(bit_depth)
        except (ValueError, TypeError):
            _LOGGER.debug("Invalid bit depth value: %s", bit_depth)

    # Extract bit rate
    bit_rate = metadata.get("bitRate")
    if bit_rate and bit_rate not in ("unknow", "unknown", "un_known", ""):
        try:
            audio_quality["bit_rate"] = int(bit_rate)
        except (ValueError, TypeError):
            _LOGGER.debug("Invalid bit rate value: %s", bit_rate)

    return audio_quality


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

    # Enhanced artwork field search - prioritized for older LinkPlay devices
    # Based on working v0.1.0 implementation that supported Audio Pro devices
    artwork_fields = [
        # Primary artwork fields (most common)
        "albumArtURI",
        "albumart",
        "cover_url",
        "cover",
        # Secondary fields for older LinkPlay devices
        "albumArtUri",
        "albumarturi",
        "art_url",
        "artwork_url",
        "pic_url",
        "entity_picture",
        # Alternative fields found in various LinkPlay firmware versions
        "thumbnail",
        "image",
        "coverart",
        "cover_art",
        "album_art",
        "artworkUrl",
        "imageUrl",
        "art",  # Simple "art" field used by some devices
        "picture",  # Basic "picture" field
        "albumcover",  # Alternative album cover field
        "track_image",  # Track-specific image field
    ]

    _LOGGER.debug("Looking for artwork in metadata for %s", coordinator.client.host)
    _LOGGER.debug("Metadata fields available: %s", list(metadata.keys()))
    _LOGGER.debug("Status fields available: %s", list(status.keys()))

    artwork_url: str | None = None
    found_field: str | None = None

    # 1. Try metaData payload first …
    for field in artwork_fields:
        artwork_url = metadata.get(field)  # type: ignore[index]
        if artwork_url and artwork_url != "un_known" and str(artwork_url).strip():  # Enhanced validation
            found_field = f"metadata.{field}"
            break

    # 2. … then fall back to the original *status* payload.
    if not artwork_url:
        for field in artwork_fields:
            artwork_url = status.get(field)  # type: ignore[index]
            if (
                artwork_url and artwork_url not in ("un_known", "unknow") and str(artwork_url).strip()
            ):  # Enhanced validation
                found_field = f"status.{field}"
                break

    # Track last artwork URL to reduce repetitive logging (uses instance attr).
    if not hasattr(coordinator, "_last_artwork_url"):
        coordinator._last_artwork_url = None  # type: ignore[attr-defined]

    if artwork_url and artwork_url not in ("un_known", "unknow"):
        artwork_url = str(artwork_url).strip()

        # Basic URL validation - must look like a URL
        if artwork_url and ("http" in artwork_url.lower() or artwork_url.startswith("/")):
            enhanced["entity_picture"] = artwork_url
            enhanced["cover_url"] = artwork_url

            if coordinator._last_artwork_url != artwork_url:  # type: ignore[attr-defined]
                _LOGGER.info("🎨 Artwork changed for %s (%s): %s", coordinator.client.host, found_field, artwork_url)
                coordinator._last_artwork_url = artwork_url  # type: ignore[attr-defined]
            else:
                _LOGGER.debug("🎨 Artwork unchanged for %s: %s", coordinator.client.host, artwork_url)
        else:
            _LOGGER.debug("❌ Invalid artwork URL format for %s: '%s'", coordinator.client.host, artwork_url)
    else:
        if getattr(coordinator, "_last_artwork_url", None):
            _LOGGER.info("🎨 Artwork removed for %s", coordinator.client.host)
            coordinator._last_artwork_url = None  # type: ignore[attr-defined]
        else:
            _LOGGER.debug("❌ No valid artwork URL found for %s", coordinator.client.host)

    return enhanced


async def _extract_basic_metadata(coordinator, status_dict: dict[str, Any]) -> dict[str, Any]:
    """Extract basic metadata (title, artist, album) from status data only.

    This is the fallback for older devices that don't support getMetaInfo.
    CRITICAL: This function no longer handles artwork - that's delegated to
    _enhance_metadata_with_artwork() to match the old working pattern.
    """
    _LOGGER.debug("Extracting basic metadata from status data")

    # Extract title, artist, album using proper field extraction
    metadata: dict[str, Any] = {}

    # Title field extraction
    if status_dict.get("title"):
        metadata["title"] = status_dict["title"]
    elif status_dict.get("Title"):  # Capital T for some devices
        metadata["title"] = status_dict["Title"]
    else:
        metadata["title"] = "Unknown"

    # Artist field extraction
    if status_dict.get("artist"):
        metadata["artist"] = status_dict["artist"]
    elif status_dict.get("Artist"):  # Capital A for some devices
        metadata["artist"] = status_dict["Artist"]
    else:
        metadata["artist"] = "Unknown"

    # Album field extraction
    if status_dict.get("album"):
        metadata["album"] = status_dict["album"]
    elif status_dict.get("Album"):  # Capital A for some devices
        metadata["album"] = status_dict["Album"]
    else:
        metadata["album"] = "Unknown"

    _LOGGER.debug("Basic metadata extracted: %s", metadata)
    return metadata
