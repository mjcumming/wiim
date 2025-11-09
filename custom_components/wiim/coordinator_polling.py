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

# Enhanced logging escalation thresholds (more balanced for production)
# 1-2 failures: debug (likely transient network issues)
# 3-4 failures: warning (device having connectivity problems)
# 5+ failures: error (device likely offline/unavailable)
FAILURE_ERROR_THRESHOLD = 5  # More balanced - escalate after ~25s with normal polling

# Smart polling intervals - match POLLING_STRATEGY.md
FAST_POLL_INTERVAL = 1  # seconds - during active playback
NORMAL_POLL_INTERVAL = 5  # seconds - when idle
DEVICE_INFO_INTERVAL = 60  # seconds - device health check
MULTIROOM_INTERVAL = 15  # seconds - role detection + group changes
IDLE_TIMEOUT = 600  # seconds (10 minutes) - return to normal polling after extended idle


_LOGGER = logging.getLogger(__name__)


def _determine_adaptive_interval(coordinator, status_model: PlayerStatus, role: str) -> int:
    """Enhanced adaptive polling with firmware awareness and UPnP health.

    Returns:
        Optimal polling interval based on device capabilities, state, and UPnP health
    """
    from .firmware_capabilities import get_optimal_polling_interval

    capabilities = getattr(coordinator, "_capabilities", {})
    play_state_str = str(status_model.play_state or "").lower()
    # Check play state - valid states from model: "play", "pause", "stop", "load", "idle"
    # Also handle common variations: "playing", "paused", "stopped"
    is_playing = play_state_str in ("play", "playing", "load")

    # Check UPnP health: is it actively receiving events?
    upnp_working = False
    try:
        from .data_helpers import get_speaker_from_config_entry

        speaker = get_speaker_from_config_entry(coordinator.hass, coordinator.entry)
        if speaker and speaker._upnp_eventer:
            # UPnP is working if we've received events recently (within 5 minutes)
            upnp_working = speaker._upnp_eventer.is_upnp_working(recent_threshold=300.0)
    except Exception:
        # If we can't check, assume UPnP is not working (conservative)
        pass

    return get_optimal_polling_interval(capabilities, role, is_playing, upnp_working=upnp_working)


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


def _should_update_audio_output(coordinator) -> bool:
    """Check if audio output status should be updated (15s interval, or on first update).

    Audio output modes change rarely, but we need to understand why the API is failing.
    Keeping original 15s polling to maintain consistency with other features.

    Also checks device capabilities to avoid calling unsupported endpoints on older devices.
    """
    # Check if device supports audio output API before attempting to fetch
    capabilities = getattr(coordinator, "_capabilities", {})
    # Default to False - only call API if explicitly supported
    # This prevents failures on older Audio Pro devices that don't support this endpoint
    supports_audio_output = capabilities.get(
        "supports_audio_output", False
    )  # Default to False to avoid errors on unsupported devices

    if not supports_audio_output:
        # Device doesn't support audio output API - don't attempt to fetch
        # This prevents repeated failures on older Audio Pro devices
        return False

    if not hasattr(coordinator, "_last_audio_output_check"):
        coordinator._last_audio_output_check = 0

    # Always fetch on first update (when _last_audio_output_check is 0)
    if coordinator._last_audio_output_check == 0:
        return True

    try:
        current_time = time.time()
        time_since_last = current_time - coordinator._last_audio_output_check
        # Keep original 15 second polling - if it was working before, no need to change
        return time_since_last >= 15
    except (TypeError, AttributeError):
        # Handle test environments where time.time() might be mocked
        return True


def _check_and_clear_metadata_on_stop(coordinator, status_model: PlayerStatus) -> None:
    """Clear stored metadata when playback stops to prevent stale data persistence."""
    play_state = str(status_model.play_state or "").lower()
    is_stopped = play_state in ("stop", "stopped", "idle", "")

    # Only clear if we have stored metadata and playback has stopped
    if is_stopped and hasattr(coordinator, "_last_valid_metadata") and coordinator._last_valid_metadata:
        if VERBOSE_DEBUG:
            _LOGGER.debug(
                "Clearing stored metadata for %s - playback stopped (state: %s)",
                coordinator.client.host,
                play_state,
            )
        coordinator._last_valid_metadata = None


async def _schedule_delayed_metadata_fetch(coordinator, status_model: PlayerStatus) -> None:
    """Schedule a delayed metadata fetch to give WiiM time to process track changes.

    This implements the user's suggestion for delayed polling to address metadata
    processing timing issues.
    """
    # Cancel any existing delayed fetch
    if hasattr(coordinator, "_metadata_fetch_task") and coordinator._metadata_fetch_task:
        coordinator._metadata_fetch_task.cancel()

    async def delayed_fetch():
        """Delayed metadata fetch with 2-second delay."""
        try:
            await asyncio.sleep(2.0)  # Give WiiM time to process track changes
            if VERBOSE_DEBUG:
                _LOGGER.debug("Executing delayed metadata fetch for %s", coordinator.client.host)
            metadata_model = await coordinator._fetch_track_metadata(status_model)

            # Update coordinator data with the fetched metadata
            if coordinator.data and metadata_model:
                coordinator.data["metadata_model"] = metadata_model
                coordinator.data["metadata"] = metadata_model.model_dump(exclude_none=True)
                if VERBOSE_DEBUG:
                    _LOGGER.debug(
                        "Updated coordinator data with delayed metadata for %s",
                        coordinator.client.host,
                    )
        except asyncio.CancelledError:
            if VERBOSE_DEBUG:
                _LOGGER.debug("Delayed metadata fetch cancelled for %s", coordinator.client.host)
        except Exception as e:
            if VERBOSE_DEBUG:
                _LOGGER.debug(
                    "Delayed metadata fetch failed for %s: %s",
                    coordinator.client.host,
                    e,
                )
        finally:
            coordinator._metadata_fetch_task = None

    # Schedule the delayed fetch
    coordinator._metadata_fetch_task = asyncio.create_task(delayed_fetch())
    if VERBOSE_DEBUG:
        _LOGGER.debug(
            "Scheduled delayed metadata fetch for %s (2s delay)",
            coordinator.client.host,
        )


def _track_changed(coordinator, status_model: PlayerStatus) -> bool:
    """Detect if track has changed (for metadata updates and artwork cache clearing)."""
    current_title = status_model.title or ""
    current_artist = status_model.artist or ""
    current_source = status_model.source or ""
    current_artwork = status_model.entity_picture or status_model.cover_url or ""

    if not hasattr(coordinator, "_last_track_info"):
        coordinator._last_track_info = (
            current_title,
            current_artist,
            current_source,
            current_artwork,
        )
        return True  # First time, consider it changed

    last_title, last_artist, last_source, last_artwork = coordinator._last_track_info
    track_changed = (
        current_title != last_title
        or current_artist != last_artist
        or current_source != last_source
        or current_artwork != last_artwork  # Also detect artwork changes
    )

    if track_changed:
        coordinator._last_track_info = (
            current_title,
            current_artist,
            current_source,
            current_artwork,
        )

        # Log specific change type for debugging (only in verbose mode to reduce log noise)
        if VERBOSE_DEBUG:
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

    if VERBOSE_DEBUG:
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

        # Check if we should use UPnP volume instead of HTTP polling
        # For Audio Pro devices: HTTP API doesn't provide volume (no getPlayerStatus endpoint),
        # so once UPnP is subscribed, we must exclude volume from HTTP polling immediately.
        # For other devices: Only exclude HTTP volume if UPnP has actually provided volume data.
        status_raw_copy = status_raw.copy()  # Don't modify original dict
        try:
            from .data_helpers import get_speaker_from_config_entry

            speaker = get_speaker_from_config_entry(coordinator.hass, coordinator.entry)
            if not speaker:
                # No speaker found, continue with normal polling
                pass
            else:
                capabilities = getattr(coordinator, "_capabilities", {})
                is_legacy_device = capabilities.get("is_legacy_device", False)

                # For Audio Pro devices: HTTP API doesn't provide player state (no getPlayerStatus),
                # so once UPnP is subscribed, we must exclude volume from HTTP polling immediately.
                # This prevents HTTP polling from setting volume to None.
                if is_legacy_device and speaker._upnp_eventer:
                    # Audio Pro device with UPnP subscribed - exclude volume from HTTP polling
                    # HTTP will never provide volume for Audio Pro, so we must rely on UPnP
                    status_raw_copy.pop("vol", None)
                    status_raw_copy.pop("volume", None)
                    status_raw_copy.pop("volume_level", None)
                    if VERBOSE_DEBUG:
                        _LOGGER.debug(
                            "Audio Pro device %s: UPnP subscribed, excluding volume from HTTP polling",
                            coordinator.client.host,
                        )
                elif speaker.should_use_upnp_volume():
                    # Non-Audio Pro device: UPnP has provided volume data - exclude from HTTP polling to avoid conflicts
                    status_raw_copy.pop("vol", None)
                    status_raw_copy.pop("volume", None)
                    status_raw_copy.pop("volume_level", None)
                    if VERBOSE_DEBUG:
                        _LOGGER.debug(
                            "Using UPnP volume for %s - excluding volume from HTTP polling",
                            coordinator.client.host,
                        )
                else:
                    # UPnP not active or hasn't provided volume yet - keep HTTP volume polling
                    # This ensures volume is available at startup before UPnP sends first event
                    # (for non-Audio Pro devices)
                    if VERBOSE_DEBUG and speaker._upnp_eventer:
                        _LOGGER.debug(
                            "UPnP subscribed but no volume data yet for %s - using HTTP volume",
                            coordinator.client.host,
                        )
        except Exception as err:
            # If speaker lookup fails, continue with normal polling (graceful fallback)
            if VERBOSE_DEBUG:
                _LOGGER.debug("Could not check UPnP volume status: %s", err)

        # Lightweight activity detection without full validation (avoids blocking event loop)
        # Extract minimal fields needed for activity detection from raw dict
        play_state_str = str(status_raw_copy.get("play_status") or status_raw_copy.get("status") or "").lower()

        # Quick track change detection using raw dict (avoids expensive validation)
        current_title = status_raw_copy.get("Title") or status_raw_copy.get("title") or ""
        current_artist = status_raw_copy.get("Artist") or status_raw_copy.get("artist") or ""
        current_source = status_raw_copy.get("mode") or status_raw_copy.get("source") or ""
        current_artwork = status_raw_copy.get("entity_picture") or status_raw_copy.get("cover_url") or ""

        if not hasattr(coordinator, "_last_track_info"):
            coordinator._last_track_info = (
                current_title,
                current_artist,
                current_source,
                current_artwork,
            )
            track_changed = True
        else:
            last_title, last_artist, last_source, last_artwork = coordinator._last_track_info
            track_changed = (
                current_title != last_title
                or current_artist != last_artist
                or current_source != last_source
                or current_artwork != last_artwork
            )
            if track_changed:
                coordinator._last_track_info = (
                    current_title,
                    current_artist,
                    current_source,
                    current_artwork,
                )

        is_activity = track_changed

        # Quick play state check for metadata clearing (lightweight)
        is_stopped = play_state_str in ("stop", "stopped", "idle", "")
        if is_stopped and hasattr(coordinator, "_last_valid_metadata") and coordinator._last_valid_metadata:
            if VERBOSE_DEBUG:
                _LOGGER.debug(
                    "Clearing stored metadata for %s - playback stopped (state: %s)",
                    coordinator.client.host,
                    play_state_str,
                )
            coordinator._last_valid_metadata = None

        # ------------------------------------------------------------------
        # CONDITIONAL HTTP CALLS: Fast, minimal processing
        # ------------------------------------------------------------------
        fetch_tasks = []
        task_names = []
        raw_data = {"status_raw": status_raw_copy}

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

        # Audio Output Status (every 15s - not critical, but useful for automation)
        if _should_update_audio_output(coordinator):
            fetch_tasks.append(coordinator.client.get_audio_output_status())
            task_names.append("audio_output")
            coordinator._last_audio_output_check = time.time()

        # Bluetooth Pairing Status (only when BT output is active, every 15s)
        # Fetch pairing status when we're fetching audio_output (same interval)
        # We'll only store it if BT output is actually active
        bt_output_was_active = False
        if hasattr(coordinator, "_last_audio_output_data") and coordinator._last_audio_output_data:
            bt_output_was_active = coordinator._last_audio_output_data.get("source") == "1"

        # Fetch Bluetooth history if:
        # 1. History hasn't been fetched yet (startup - needed for Audio Output Mode select dropdown)
        # 2. BT output was active (to show connected device and refresh periodically)
        # Note: We do NOT fetch every 15s when BT is inactive - only at startup and when BT is active
        should_fetch_bt_history = not hasattr(coordinator, "_bt_history_fetched") or bt_output_was_active

        if should_fetch_bt_history:
            # Also fetch Bluetooth history to identify connected device and populate dropdown
            fetch_tasks.append(coordinator.client.get_bluetooth_history())
            task_names.append("bt_history")
            if not hasattr(coordinator, "_bt_history_fetched"):
                coordinator._bt_history_fetched = True
                _LOGGER.info(
                    "Fetching Bluetooth history for %s at startup (for Audio Output Mode dropdown)",
                    coordinator.client.host,
                )
            elif bt_output_was_active:
                _LOGGER.debug(
                    "Fetching Bluetooth history for %s (BT output active)",
                    coordinator.client.host,
                )

        # Fetch pairing status only if BT output was active or we're checking audio_output
        if bt_output_was_active or "audio_output" in task_names:
            fetch_tasks.append(coordinator.client.get_bluetooth_pair_status())
            task_names.append("bt_pair_status")

        # Metadata (only on track change, if supported)
        # Skip metadata fetch during initial setup to prevent blocking on older devices
        # that don't support getMetaInfo - only fetch after device is confirmed working
        is_initial_setup = not hasattr(coordinator, "_initial_setup_complete")
        should_fetch_metadata = (
            track_changed and not is_initial_setup and getattr(coordinator, "_metadata_supported", None) is not False
        )

        if should_fetch_metadata:
            # Create status_model only when needed for metadata fetching (deferred validation)
            # This avoids expensive validation on every poll cycle
            status_model_for_metadata: PlayerStatus = PlayerStatus.model_validate(status_raw_copy)

            # For testing, use immediate metadata fetch to avoid async task issues
            # In production, this could be delayed, but tests need immediate results
            if hasattr(coordinator, "_test_mode") and coordinator._test_mode:
                # Immediate fetch for tests
                try:
                    track_metadata_model = await coordinator._fetch_track_metadata(status_model_for_metadata)
                    if track_metadata_model:
                        raw_data["metadata_model"] = track_metadata_model
                        fetch_tasks.append(asyncio.create_task(asyncio.sleep(0)))  # Dummy task
                        task_names.append("metadata")
                except Exception as e:
                    _LOGGER.debug("Test metadata fetch failed: %s", e)
            else:
                # Implement delayed metadata fetch to give WiiM time to process track changes
                # This addresses the user's suggestion for delayed polling
                await _schedule_delayed_metadata_fetch(coordinator, status_model_for_metadata)

        # EQ info (every 60s per POLLING_STRATEGY.md - settings rarely change)
        if _should_update_eq_info(coordinator):
            fetch_tasks.append(coordinator._fetch_eq_info())
            task_names.append("eq_info")
            coordinator._last_eq_info_check = time.time()

        # Execute fast HTTP calls in parallel
        results = []
        if fetch_tasks:
            if VERBOSE_DEBUG:
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

        # Process device info result (core status)
        if "device_info" in task_names:
            if isinstance(results[result_idx], Exception):
                _LOGGER.debug("Device info fetch failed: %s", results[result_idx])
                coordinator._device_info_working = False

                # Track consecutive failures for core device communication
                if not hasattr(coordinator, "_core_comm_failures"):
                    coordinator._core_comm_failures = 0
                coordinator._core_comm_failures += 1

                # Only log core communication failures occasionally to reduce spam
                if coordinator._core_comm_failures <= 3:
                    _LOGGER.warning(
                        "Core device communication failed (%d consecutive): %s",
                        coordinator._core_comm_failures,
                        results[result_idx],
                    )
                    _LOGGER.info("This may cause audio output and other features to be unavailable")
                elif coordinator._core_comm_failures % 10 == 1:
                    _LOGGER.debug(
                        "Core device communication still failing after %d attempts",
                        coordinator._core_comm_failures,
                    )
            else:
                raw_data["device_raw"] = results[result_idx]
                coordinator._device_info_working = True
                # Reset failure counter on success
                if hasattr(coordinator, "_core_comm_failures"):
                    if coordinator._core_comm_failures > 0:
                        # Get device info for enhanced recovery logging
                        device_info = getattr(coordinator, "_capabilities", {})
                        firmware = device_info.get("firmware_version", "unknown") if device_info else "unknown"

                        # Enhanced recovery logging with comprehensive device info
                        device_type = (
                            "WiiM"
                            if device_info.get("is_wiim_device")
                            else "Legacy"
                            if device_info.get("is_legacy_device")
                            else "Unknown"
                        )
                        device_model = device_info.get("device_type", "Unknown")

                        _LOGGER.info(
                            "%s: Core device communication restored after %d failures (%s %s fw:%s)",
                            coordinator.client.host,
                            coordinator._core_comm_failures,
                            device_type,
                            device_model,
                            firmware,
                        )
                    coordinator._core_comm_failures = 0
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

        # Process audio output result
        audio_output_data: dict[str, Any] | None = None
        if "audio_output" in task_names:
            if isinstance(results[result_idx], Exception):
                # Log audio output failures with full details for first few attempts
                if not hasattr(coordinator, "_audio_output_error_count"):
                    coordinator._audio_output_error_count = 0
                coordinator._audio_output_error_count += 1

                if coordinator._audio_output_error_count <= 3:
                    _LOGGER.warning(
                        "[AUDIO OUTPUT DEBUG] %s: Audio output fetch failed (attempt %d): %s",
                        coordinator.client.host,
                        coordinator._audio_output_error_count,
                        results[result_idx],
                    )
                elif coordinator._audio_output_error_count % 10 == 1:
                    _LOGGER.debug(
                        "[AUDIO OUTPUT DEBUG] %s: Audio output still failing after %d attempts",
                        coordinator.client.host,
                        coordinator._audio_output_error_count,
                    )

                audio_output_data = None
            else:
                audio_output_data = results[result_idx]  # Can be None if API not supported
                # Reset error counter on success
                if hasattr(coordinator, "_audio_output_error_count"):
                    coordinator._audio_output_error_count = 0
            result_idx += 1

        # Process Bluetooth pairing status result (only store if BT output is active)
        bt_pair_status_data: dict[str, Any] | None = None
        if "bt_pair_status" in task_names:
            # Only store pairing status if BT output is actually active
            bt_output_is_active = False
            if audio_output_data:
                bt_output_is_active = audio_output_data.get("source") == "1"
            elif bt_output_was_active:
                # If we didn't fetch audio_output this cycle but BT was active, use previous state
                bt_output_is_active = True

            if isinstance(results[result_idx], Exception):
                _LOGGER.debug(
                    "Bluetooth pairing status fetch failed for %s: %s",
                    coordinator.client.host,
                    results[result_idx],
                )
                bt_pair_status_data = None
            elif bt_output_is_active:
                # Only store if BT output is active
                bt_pair_status_data = results[result_idx] if isinstance(results[result_idx], dict) else None
                if bt_pair_status_data:
                    _LOGGER.debug(
                        "Bluetooth pairing status for %s: %s (BT output active)",
                        coordinator.client.host,
                        bt_pair_status_data,
                    )
                else:
                    _LOGGER.debug(
                        "Bluetooth pairing status fetch returned non-dict for %s: %s",
                        coordinator.client.host,
                        type(results[result_idx]).__name__
                        if not isinstance(results[result_idx], Exception)
                        else "Exception",
                    )
            else:
                # BT output not active, don't store pairing status
                bt_pair_status_data = None
                if VERBOSE_DEBUG:
                    _LOGGER.debug(
                        "Bluetooth output not active for %s, skipping pairing status",
                        coordinator.client.host,
                    )
            result_idx += 1

        # Process Bluetooth history result
        # Always store history (needed for Audio Output Mode select dropdown)
        # even when BT output is not active, so users can see available paired devices
        bt_history_data: list[dict[str, Any]] | None = None
        if "bt_history" in task_names:
            bt_output_is_active = False
            if audio_output_data:
                bt_output_is_active = audio_output_data.get("source") == "1"
            elif bt_output_was_active:
                # If we didn't fetch audio_output this cycle but BT was active, use previous state
                bt_output_is_active = True

            if isinstance(results[result_idx], Exception):
                _LOGGER.debug(
                    "Bluetooth history fetch failed for %s: %s",
                    coordinator.client.host,
                    results[result_idx],
                )
                bt_history_data = None
            elif isinstance(results[result_idx], list):
                # Always store history (needed for dropdown even when BT not active)
                bt_history_data = results[result_idx]
                if bt_output_is_active:
                    _LOGGER.info(
                        "Bluetooth history for %s: %d devices (BT output active): %s",
                        coordinator.client.host,
                        len(bt_history_data),
                        [d.get("name", "Unknown") for d in bt_history_data[:5]],
                    )
                else:
                    _LOGGER.info(
                        "Bluetooth history for %s: %d devices (for dropdown): %s",
                        coordinator.client.host,
                        len(bt_history_data),
                        [d.get("name", "Unknown") for d in bt_history_data[:5]],
                    )
            else:
                bt_history_data = None
                _LOGGER.debug(
                    "Bluetooth history fetch returned non-list for %s: %s",
                    coordinator.client.host,
                    type(results[result_idx]).__name__
                    if not isinstance(results[result_idx], Exception)
                    else "Exception",
                )
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
                # For test mode, we already have the metadata_model in raw_data
                if hasattr(coordinator, "_test_mode") and coordinator._test_mode:
                    track_metadata_model = raw_data.get("metadata_model")
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
        status_model = processed_data.get("status_model")
        if not status_model:
            # Fallback: create status_model from raw dict if thread pool processing failed
            # This should be rare, but ensures we always have a status_model
            try:
                status_model = PlayerStatus.model_validate(status_raw_copy)
            except Exception as fallback_err:
                _LOGGER.debug("Failed to create fallback status_model: %s", fallback_err)
                # Use existing status_model from previous update if available
                status_model = coordinator.data.get("status_model") if coordinator.data else None
                if not status_model:
                    # Last resort: create minimal status_model
                    status_model = PlayerStatus(play_status="idle")

        device_model = processed_data.get("device_model")

        # Use existing data if not fetched/processed this cycle
        if not device_model and coordinator.data:
            device_model = coordinator.data.get("device_model")
        if not track_metadata_model and coordinator.data:
            track_metadata_model = coordinator.data.get("metadata_model")
        if not eq_info_model and coordinator.data:
            eq_info_model = coordinator.data.get("eq_model")
        # Preserve bt_history if we didn't fetch it this cycle (needed for dropdown)
        if bt_history_data is None and coordinator.data:
            bt_history_data = coordinator.data.get("bt_history")
            if bt_history_data:
                _LOGGER.debug(
                    "Preserving existing bt_history for %s: %d devices",
                    coordinator.client.host,
                    len(bt_history_data) if isinstance(bt_history_data, list) else 0,
                )

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

        # Preserve UPnP volume/mute if UPnP is being used (don't overwrite with HTTP polling)
        # Following DLNA DMR pattern: HTTP polling and UPnP work together
        # For Audio Pro devices: Always preserve UPnP volume once UPnP is subscribed (HTTP doesn't provide it)
        # For other devices: Only preserve if UPnP has actually provided volume data
        try:
            from .data_helpers import get_speaker_from_config_entry

            speaker = get_speaker_from_config_entry(coordinator.hass, coordinator.entry)
            if speaker and coordinator.data:
                capabilities = getattr(coordinator, "_capabilities", {})
                is_legacy_device = capabilities.get("is_legacy_device", False)

                # UPnP is working - preserve UPnP state where appropriate
                existing_status = coordinator.data.get("status_model")

                # For Audio Pro devices: If UPnP is subscribed, preserve any UPnP volume we have
                # (even if None, don't let HTTP overwrite it since HTTP will never provide volume)
                if is_legacy_device and speaker._upnp_eventer and isinstance(existing_status, PlayerStatus):
                    # Audio Pro device with UPnP subscribed - preserve UPnP volume if available
                    if existing_status.volume is not None:
                        status_model.volume = existing_status.volume
                        if existing_status.mute is not None:
                            status_model.mute = existing_status.mute
                        if VERBOSE_DEBUG:
                            _LOGGER.debug(
                                "Preserving UPnP volume %d for Audio Pro device %s",
                                existing_status.volume,
                                coordinator.client.host,
                            )
                elif speaker.should_use_upnp_volume() and isinstance(existing_status, PlayerStatus):
                    # Non-Audio Pro device: UPnP has provided volume data - preserve it
                    if existing_status.volume is not None:
                        status_model.volume = existing_status.volume
                        if existing_status.mute is not None:
                            status_model.mute = existing_status.mute
                        if VERBOSE_DEBUG:
                            _LOGGER.debug(
                                "Preserving UPnP volume %d for %s",
                                existing_status.volume,
                                coordinator.client.host,
                            )
        except Exception as err:
            # Graceful fallback if speaker lookup fails
            if VERBOSE_DEBUG:
                _LOGGER.debug("Could not preserve UPnP volume: %s", err)

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
            "audio_output": audio_output_data,
            "bt_pair_status": bt_pair_status_data,
            "bt_history": bt_history_data,
        }

        # Propagate EQ preset to status
        if eq_info_model and eq_info_model.eq_preset:
            status_model.eq_preset = eq_info_model.eq_preset

        # Propagate audio output data to status model
        # Audio output is polled every 15s, so preserve last known value between polls
        if audio_output_data is not None:
            # We fetched it this cycle - use fresh data
            status_model.audio_output = audio_output_data
            coordinator._last_audio_output_data = audio_output_data
        elif hasattr(coordinator, "_last_audio_output_data") and coordinator._last_audio_output_data is not None:
            # Not fetched this cycle, but we have a previous value - reuse it
            status_model.audio_output = coordinator._last_audio_output_data
        # else: Never fetched successfully - leave audio_output as None

        # Ensure UUID is present
        if device_model and not device_model.uuid and coordinator.entry:
            device_model.uuid = getattr(coordinator.entry, "unique_id", None)

        # Update speaker object
        if VERBOSE_DEBUG:
            _LOGGER.debug(
                "🎵 About to call _update_speaker_object with data keys: %s",
                list(data.keys()) if data else "None",
            )
        await coordinator._update_speaker_object(data)

        # Success handling
        previous_failures = coordinator._backoff.consecutive_failures
        coordinator._backoff.record_success()

        # Log recovery if we had failures
        if previous_failures > 0:
            # Enhanced recovery logging with device context
            device_info = getattr(coordinator, "_capabilities", {})
            device_type = (
                "WiiM"
                if device_info.get("is_wiim_device")
                else "Legacy"
                if device_info.get("is_legacy_device")
                else "Unknown"
            )
            device_model = device_info.get("device_type", "Unknown")
            firmware = device_info.get("firmware_version", "unknown") if device_info else "unknown"

            _LOGGER.info(
                "%s: Device communication restored after %d consecutive failures (%s %s fw:%s)",
                coordinator.client.host,
                previous_failures,
                device_type,
                device_model,
                firmware,
            )

        # Apply adaptive polling interval
        if interval_changed:
            coordinator.update_interval = timedelta(seconds=new_interval)
            if VERBOSE_DEBUG:
                _LOGGER.debug(
                    "%s: Switched to %s polling (%ds) - device is %s",
                    coordinator.client.host,
                    "fast" if new_interval == FAST_POLL_INTERVAL else "normal",
                    new_interval,
                    "playing" if new_interval == FAST_POLL_INTERVAL else "idle",
                )

        coordinator._last_response_time = (time.perf_counter() - _start_time) * 1000.0
        if VERBOSE_DEBUG:
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
            _LOGGER.debug(
                "Initial setup complete for %s - metadata fetching now enabled",
                coordinator.client.host,
            )

        return data

    except WiiMError as err:
        # Failure handling
        coordinator._player_status_working = False
        coordinator._device_info_working = False
        coordinator._multiroom_working = False
        coordinator._backoff.record_failure()

        # Enhanced escalation: debug → debug → warning → warning → error
        failures = coordinator._backoff.consecutive_failures
        if failures <= 2:
            log_fn = _LOGGER.debug  # Likely transient network issues
        elif failures <= 4:
            log_fn = _LOGGER.warning  # Device having connectivity problems
        else:
            log_fn = _LOGGER.error  # Device likely offline/unavailable

        # Enhanced error logging with context
        context_parts = []

        # Add error context from enhanced error classes
        if hasattr(err, "endpoint"):
            context_parts.append(f"endpoint={err.endpoint}")
        if hasattr(err, "attempts"):
            context_parts.append(f"attempts={err.attempts}")
        if hasattr(err, "device_info") and err.device_info:
            firmware = err.device_info.get("firmware_version", "unknown")
            context_parts.append(f"firmware={firmware}")
        if hasattr(err, "operation_context") and err.operation_context != "api_call":
            context_parts.append(f"context={err.operation_context}")

        context_str = f" ({', '.join(context_parts)})" if context_parts else ""

        # Determine if this is user-initiated or automated polling
        is_user_action = False
        if hasattr(coordinator, "hass") and coordinator.hass:
            # Check if there are any pending service calls or user interactions
            # This is a simple heuristic - could be enhanced with more sophisticated tracking
            is_user_action = getattr(coordinator, "_user_action_pending", False)

        operation_type = "user action" if is_user_action else "automated polling"

        log_fn(
            "%s: Smart coordinator update failed (%s, attempt %d): %s%s",
            coordinator.client.host,
            operation_type,
            coordinator._backoff.consecutive_failures,
            err,
            context_str,
        )

        # On error, use backoff logic
        backoff_interval = coordinator._backoff.next_interval(NORMAL_POLL_INTERVAL)
        coordinator.update_interval = backoff_interval

        # For transient failures (first 2-3), return cached data instead of raising UpdateFailed
        # This prevents the base coordinator from logging every transient network hiccup as ERROR.
        # Only raise UpdateFailed after consecutive failures indicate a real problem.
        # This follows the pattern used by other integrations (e.g., Goodwe) to reduce log noise.
        if failures <= 2:
            # Return cached data for transient failures - don't raise UpdateFailed
            # This prevents the base coordinator from logging ERROR on every transient network issue
            # Only return cached data if we've had at least one successful update (coordinator.data exists)
            if coordinator.data:
                if VERBOSE_DEBUG:
                    _LOGGER.debug(
                        "%s: Returning cached data after transient failure (attempt %d)",
                        coordinator.client.host,
                        failures,
                    )
                return coordinator.data
            else:
                # No cached data available - must raise to indicate failure
                # This ensures proper initialization during setup (first update must succeed)
                raise UpdateFailed(f"Error updating WiiM device (no cached data): {err}") from err

        # After 3+ consecutive failures, raise UpdateFailed to indicate a real problem
        # The base coordinator will log this, but only if it's the first failure after a success
        raise UpdateFailed(f"Error updating WiiM device: {err}") from err
