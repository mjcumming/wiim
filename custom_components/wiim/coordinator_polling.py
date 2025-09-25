from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.helpers.update_coordinator import UpdateFailed

from .api import WiiMError
from .models import DeviceInfo, PlayerStatus, PollingMetrics

# Verbose debug toggle (mirrors coordinator.py)
VERBOSE_DEBUG = False

# Number of consecutive failures after which we escalate to ERROR level
FAILURE_ERROR_THRESHOLD = 3  # keep behaviour identical to original implementation

# Smart polling intervals - match POLLING_STRATEGY.md
FAST_POLL_INTERVAL = 1  # seconds - during active playback
NORMAL_POLL_INTERVAL = 5  # seconds - when idle
DEVICE_INFO_INTERVAL = 60  # seconds - device health check
MULTIROOM_INTERVAL = 15  # seconds - role detection + group changes
IDLE_TIMEOUT = 600  # seconds (10 minutes) - return to normal polling after extended idle


_LOGGER = logging.getLogger(__name__)


def _determine_adaptive_interval(coordinator, status_model: PlayerStatus, role: str) -> int:
    """Enhanced adaptive polling with firmware awareness.

    Returns:
        Optimal polling interval based on device capabilities and state
    """
    from .firmware_capabilities import get_optimal_polling_interval

    capabilities = getattr(coordinator, "_capabilities", {})
    is_playing = str(status_model.play_state or "").lower() in (
        "play",
        "playing",
        "load",
    )

    return get_optimal_polling_interval(capabilities, role, is_playing)


def _should_update_device_info(coordinator) -> bool:
    """Check if device info should be updated (health check every 60s per POLLING_STRATEGY.md)."""
    if not hasattr(coordinator, "_last_device_info_check"):
        coordinator._last_device_info_check = 0

    current_time = time.time()
    return (current_time - coordinator._last_device_info_check) >= DEVICE_INFO_INTERVAL


def _should_update_eq_info(coordinator) -> bool:
    """Check if EQ info should be updated (every 60s per POLLING_STRATEGY.md).

    Respects capability detection - if EQ is permanently disabled, never fetch.
    """
    # CRITICAL: Don't waste time on unsupported endpoints
    if getattr(coordinator, "_eq_supported", None) is False:
        return False

    if not hasattr(coordinator, "_last_eq_info_check"):
        coordinator._last_eq_info_check = 0

    current_time = time.time()
    return (current_time - coordinator._last_eq_info_check) >= DEVICE_INFO_INTERVAL


def _should_update_multiroom(coordinator, is_activity_triggered: bool = False) -> bool:
    """Check if multiroom info should be updated (15s base + on activity)."""
    if not hasattr(coordinator, "_last_multiroom_check"):
        coordinator._last_multiroom_check = 0

    current_time = time.time()
    time_based = (current_time - coordinator._last_multiroom_check) >= MULTIROOM_INTERVAL

    return time_based or is_activity_triggered


def _track_changed(coordinator, status_model: PlayerStatus) -> bool:
    """Detect if track has changed (for metadata updates and artwork cache clearing)."""
    current_title = status_model.title or ""
    current_artist = status_model.artist or ""
    current_source = status_model.source or ""
    current_artwork = status_model.entity_picture or status_model.cover_url or ""

    if not hasattr(coordinator, "_last_track_info"):
        coordinator._last_track_info = (current_title, current_artist, current_source, current_artwork)
        return True  # First time, consider it changed

    last_title, last_artist, last_source, last_artwork = coordinator._last_track_info
    track_changed = (
        current_title != last_title
        or current_artist != last_artist
        or current_source != last_source
        or current_artwork != last_artwork  # Also detect artwork changes
    )

    if track_changed:
        coordinator._last_track_info = (current_title, current_artist, current_source, current_artwork)

        # Log specific change type for debugging
        if current_artwork != last_artwork:
            _LOGGER.debug(
                "Artwork changed for %s: '%s' -> '%s'",
                coordinator.client.host,
                last_artwork or "None",
                current_artwork or "None",
            )
        else:
            _LOGGER.debug(
                "Track/source changed for %s: %s - %s (%s)",
                coordinator.client.host,
                current_title,
                current_artist,
                current_source,
            )

    return track_changed


def _process_heavy_operations(raw_data: dict) -> dict[str, Any]:
    """Process heavy operations (parsing, validation) off the main thread.

    This function contains all the CPU-intensive work that was causing >100ms
    asyncio warnings. By running it in a thread pool, we keep the main event
    loop responsive.
    """
    # This will run in a thread pool, so it's safe to do heavy processing
    processed = {}

    # Parse player status if available
    if "status_raw" in raw_data:
        try:
            processed["status_model"] = PlayerStatus.model_validate(raw_data["status_raw"])
        except Exception as err:
            _LOGGER.debug("Failed to parse status model: %s", err)

    # Parse device info if available
    if "device_raw" in raw_data:
        try:
            device_model = DeviceInfo.model_validate(raw_data["device_raw"])

            # Normalize device info (also heavy processing)
            try:
                from . import coordinator_normalise as _norm

                normalised = _norm.normalise_device_info(device_model)
                device_model = device_model.model_copy(update=normalised)
            except Exception as norm_err:
                _LOGGER.debug("Normalising device_info failed: %s", norm_err)

            processed["device_model"] = device_model
        except Exception as err:
            _LOGGER.debug("Failed to parse device model: %s", err)

    # Heavy model_dump operations
    if "metadata_model" in raw_data and raw_data["metadata_model"]:
        try:
            processed["metadata"] = raw_data["metadata_model"].model_dump(exclude_none=True)
        except Exception as err:
            _LOGGER.debug("Failed to dump metadata model: %s", err)

    if "eq_model" in raw_data and raw_data["eq_model"]:
        try:
            processed["eq"] = raw_data["eq_model"].model_dump(exclude_none=True)
        except Exception as err:
            _LOGGER.debug("Failed to dump EQ model: %s", err)

    return processed


async def async_update_data(coordinator) -> dict[str, Any]:
    """Optimized polling with HTTP/parsing separation to reduce asyncio warnings.

    Strategy:
    1. Fast HTTP calls (keep main thread responsive)
    2. Offload heavy parsing/validation to thread pool
    3. Quick assembly of final data structure

    Polling frequency:
    - Player status: Adaptive (1s playing, 5s idle)
    - Multiroom: 15s + on activity (role detection)
    - Device info: 60s (health check only)
    - EQ info: 60s (settings rarely change)
    - Metadata: On track change (if supported)
    - Presets: Startup only
    """

    _LOGGER.debug("=== OPTIMIZED COORDINATOR UPDATE START for %s ===", coordinator.client.host)
    _start_time = time.perf_counter()

    # One-time startup calls
    if not coordinator._eq_list_extended:
        await coordinator._extend_eq_preset_map_once()

    try:
        # ------------------------------------------------------------------
        # PHASE 1: FAST HTTP CALLS (minimize event loop blocking)
        # ------------------------------------------------------------------

        # Always fetch player status (this is fast - just HTTP + basic JSON parse)
        status_raw = await coordinator.client.get_player_status()
        coordinator._player_status_working = True

        # Quick validation to create status model for activity detection
        status_model: PlayerStatus = PlayerStatus.model_validate(status_raw)

        # Detect activity for conditional polling triggers
        track_changed = _track_changed(coordinator, status_model)
        is_activity = track_changed

        # ------------------------------------------------------------------
        # CONDITIONAL HTTP CALLS: Fast, minimal processing
        # ------------------------------------------------------------------
        fetch_tasks = []
        task_names = []
        raw_data = {"status_raw": status_raw}

        # Device info (health check - every 60s per POLLING_STRATEGY.md)
        if _should_update_device_info(coordinator):
            fetch_tasks.append(coordinator.client.get_device_info())
            task_names.append("device_info")
            coordinator._last_device_info_check = time.time()

        # Multiroom (role detection - 15s + on activity per POLLING_STRATEGY.md)
        if _should_update_multiroom(coordinator, is_activity):
            fetch_tasks.append(coordinator._fetch_multiroom_info())
            task_names.append("multiroom")
            coordinator._last_multiroom_check = time.time()

        # Metadata (only on track change, if supported)
        # Skip metadata fetch during initial setup to prevent blocking on older devices
        # that don't support getMetaInfo - only fetch after device is confirmed working
        is_initial_setup = not hasattr(coordinator, "_initial_setup_complete")
        should_fetch_metadata = (
            track_changed and not is_initial_setup and getattr(coordinator, "_metadata_supported", None) is not False
        )

        if should_fetch_metadata:
            fetch_tasks.append(coordinator._fetch_track_metadata(status_model))
            task_names.append("metadata")

        # EQ info (every 60s per POLLING_STRATEGY.md - settings rarely change)
        if _should_update_eq_info(coordinator):
            fetch_tasks.append(coordinator._fetch_eq_info())
            task_names.append("eq_info")
            coordinator._last_eq_info_check = time.time()

        # Execute fast HTTP calls in parallel
        results = []
        if fetch_tasks:
            _LOGGER.debug(
                "Fast-fetching %s in parallel for %s",
                ", ".join(task_names),
                coordinator.client.host,
            )
            results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        # ------------------------------------------------------------------
        # PHASE 2: PROCESS HTTP RESULTS (still fast - just assignments)
        # ------------------------------------------------------------------

        # Collect raw results for heavy processing
        result_idx = 0
        multiroom_info = coordinator.data.get("multiroom", {}) if coordinator.data else {}
        track_metadata_model = coordinator.data.get("metadata_model") if coordinator.data else None
        eq_info_model = coordinator.data.get("eq_model") if coordinator.data else None

        # Process device info result
        if "device_info" in task_names:
            if isinstance(results[result_idx], Exception):
                _LOGGER.debug("Device info fetch failed: %s", results[result_idx])
                coordinator._device_info_working = False
            else:
                raw_data["device_raw"] = results[result_idx]
                coordinator._device_info_working = True
            result_idx += 1

        # Process multiroom result
        if "multiroom" in task_names:
            if isinstance(results[result_idx], Exception):
                _LOGGER.debug("Multiroom fetch failed: %s", results[result_idx])
                coordinator._multiroom_working = False
            else:
                multiroom_info = results[result_idx] or {}
                coordinator._multiroom_working = bool(multiroom_info)
            result_idx += 1

        # Process metadata result
        if "metadata" in task_names:
            if isinstance(results[result_idx], Exception):
                _LOGGER.debug(
                    "Metadata fetch failed, marking as unsupported: %s",
                    results[result_idx],
                )
                coordinator._metadata_supported = False
            else:
                track_metadata_model = results[result_idx]
                coordinator._metadata_supported = True
            result_idx += 1

        # Process EQ result
        if "eq_info" in task_names:
            if isinstance(results[result_idx], Exception):
                _LOGGER.debug("EQ info fetch failed: %s", results[result_idx])
            else:
                eq_info_model = results[result_idx]
            result_idx += 1

        # ------------------------------------------------------------------
        # PHASE 3: HEAVY PROCESSING (offloaded to thread pool)
        # ------------------------------------------------------------------

        # Prepare data for heavy processing
        raw_data.update(
            {
                "metadata_model": track_metadata_model,
                "eq_model": eq_info_model,
            }
        )

        # Offload CPU-intensive operations to thread pool
        http_time = (time.perf_counter() - _start_time) * 1000.0
        heavy_start = time.perf_counter()

        try:
            # Use asyncio.to_thread if available (Python 3.9+)
            if hasattr(asyncio, "to_thread"):
                processed_data = await asyncio.to_thread(_process_heavy_operations, raw_data)
            else:
                # Fallback for older Python versions
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    processed_data = await coordinator.hass.loop.run_in_executor(
                        executor, _process_heavy_operations, raw_data
                    )
        except Exception as processing_err:
            _LOGGER.debug("Heavy processing failed, using light fallback: %s", processing_err)
            processed_data = {}

        heavy_time = (time.perf_counter() - heavy_start) * 1000.0

        # Extract processed results
        status_model = processed_data.get("status_model") or status_model
        device_model = processed_data.get("device_model")

        # Use existing data if not fetched/processed this cycle
        if not device_model and coordinator.data:
            device_model = coordinator.data.get("device_model")
        if not track_metadata_model and coordinator.data:
            track_metadata_model = coordinator.data.get("metadata_model")
        if not eq_info_model and coordinator.data:
            eq_info_model = coordinator.data.get("eq_model")

        # ------------------------------------------------------------------
        # PHASE 4: FINAL PROCESSING (keep light)
        # ------------------------------------------------------------------

        # Light role detection (avoid heavy processing here)
        role = await coordinator._detect_role_from_status_and_slaves(status_model, multiroom_info, device_model)

        # Use pre-processed metadata or create light version
        track_metadata = processed_data.get("metadata", {})
        if not track_metadata and track_metadata_model:
            # Fallback to light processing if thread pool failed
            track_metadata = {"title": getattr(track_metadata_model, "title", None)}

        # Light multiroom source resolution
        await coordinator._resolve_multiroom_source_and_media(status_model, track_metadata, role)

        # ------------------------------------------------------------------
        # Adaptive polling interval determination
        # ------------------------------------------------------------------
        new_interval = _determine_adaptive_interval(coordinator, status_model, role)
        interval_changed = coordinator.update_interval.total_seconds() != new_interval

        # ------------------------------------------------------------------
        # Presets (startup only)
        # ------------------------------------------------------------------
        presets_list: list[dict] = coordinator.data.get("presets", []) if coordinator.data else []
        if not presets_list and coordinator._presets_supported is not False:
            try:
                presets_list = await coordinator.client.get_presets()
                coordinator._presets_supported = True if presets_list else False
            except WiiMError:
                coordinator._presets_supported = False
                presets_list = []

        # ------------------------------------------------------------------
        # Artwork propagation
        # ------------------------------------------------------------------
        if track_metadata and track_metadata_model:
            art_url = track_metadata.get("entity_picture") or track_metadata.get("cover_url")
            if art_url:
                status_model.entity_picture = art_url
                status_model.cover_url = art_url

        # ------------------------------------------------------------------
        # Polling diagnostics
        # ------------------------------------------------------------------
        polling_data_model = PollingMetrics(
            interval=new_interval,
            is_playing=(str(status_model.play_state or "").lower() in ("play", "playing", "load")),
            api_capabilities={
                "statusex_supported": coordinator._statusex_supported,
                "metadata_supported": coordinator._metadata_supported,
                "eq_supported": coordinator._eq_supported,
            },
        )
        polling_data = polling_data_model.model_dump(exclude_none=True)
        polling_data.update(
            {
                "adaptive_polling": True,
                "interval_reason": "playback_active" if new_interval == FAST_POLL_INTERVAL else "idle",
                "fast_polling_active": new_interval == FAST_POLL_INTERVAL,
                "last_device_info_check": getattr(coordinator, "_last_device_info_check", 0),
                "last_multiroom_check": getattr(coordinator, "_last_multiroom_check", 0),
            }
        )

        # Final data structure (use pre-processed data when available)
        eq_data = processed_data.get("eq", {})
        if not eq_data and eq_info_model:
            # Fallback: light EQ processing if heavy processing failed
            try:
                eq_data = eq_info_model.model_dump(exclude_none=True)
            except Exception as eq_err:
                _LOGGER.debug("Fallback EQ processing failed: %s", eq_err)
                eq_data = {}

        data: dict[str, Any] = {
            "status_model": status_model,
            "device_model": device_model,
            "multiroom": multiroom_info,
            "metadata_model": track_metadata_model,
            "metadata": track_metadata,
            "eq_model": eq_info_model,
            "eq": eq_data,
            "presets": presets_list,
            "role": role,
            "polling_metrics": polling_data_model,
            "polling": polling_data,
        }

        # Propagate EQ preset to status
        if eq_info_model and eq_info_model.eq_preset:
            status_model.eq_preset = eq_info_model.eq_preset

        # Ensure UUID is present
        if device_model and not device_model.uuid and coordinator.entry:
            device_model.uuid = getattr(coordinator.entry, "unique_id", None)

        # Update speaker object
        await coordinator._update_speaker_object(data)

        # Success handling
        coordinator._backoff.record_success()

        # Apply adaptive polling interval
        if interval_changed:
            coordinator.update_interval = timedelta(seconds=new_interval)
            _LOGGER.debug(
                "%s: Switched to %s polling (%ds) - device is %s",
                coordinator.client.host,
                "fast" if new_interval == FAST_POLL_INTERVAL else "normal",
                new_interval,
                "playing" if new_interval == FAST_POLL_INTERVAL else "idle",
            )

        coordinator._last_response_time = (time.perf_counter() - _start_time) * 1000.0
        _LOGGER.debug(
            "=== OPTIMIZED UPDATE SUCCESS for %s (%.1fms total: %.1fms HTTP + %.1fms processing) ===",
            coordinator.client.host,
            coordinator._last_response_time,
            http_time,
            heavy_time,
        )

        total_time = (time.perf_counter() - _start_time) * 1000.0

        if VERBOSE_DEBUG or total_time > 100:
            _LOGGER.info(
                "🚀 Coordinator update for %s: %0.1fms total (HTTP: %0.1fms, processing: %0.1fms) "
                "| interval=%ds%s | role=%s | metadata=%s | multiroom=%s",
                coordinator.client.host,
                total_time,
                http_time,
                heavy_time,
                int(new_interval),
                " ⚡" if interval_changed else "",
                role,
                "✓" if track_metadata_model else "✗",
                "✓" if multiroom_info else "✗",
            )

        # Mark initial setup as complete after first successful update
        # This enables metadata fetching in subsequent updates
        if not hasattr(coordinator, "_initial_setup_complete"):
            coordinator._initial_setup_complete = True
            _LOGGER.debug("Initial setup complete for %s - metadata fetching now enabled", coordinator.client.host)

        return data

    except WiiMError as err:
        # Failure handling
        coordinator._player_status_working = False
        coordinator._device_info_working = False
        coordinator._multiroom_working = False
        coordinator._backoff.record_failure()

        if coordinator._backoff.consecutive_failures < 3:
            log_fn = _LOGGER.debug
        elif coordinator._backoff.consecutive_failures < FAILURE_ERROR_THRESHOLD:
            log_fn = _LOGGER.warning
        else:
            log_fn = _LOGGER.error

        log_fn(
            "%s: Smart coordinator update failed (attempt %d): %s",
            coordinator.client.host,
            coordinator._backoff.consecutive_failures,
            err,
        )

        # On error, use backoff logic
        backoff_interval = coordinator._backoff.next_interval(NORMAL_POLL_INTERVAL)
        coordinator.update_interval = backoff_interval

        raise UpdateFailed(f"Error updating WiiM device: {err}") from err
