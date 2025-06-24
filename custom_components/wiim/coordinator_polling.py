from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.helpers.update_coordinator import UpdateFailed

from . import coordinator_endpoints as _endpoints
from .api import WiiMError
from .models import DeviceInfo, PlayerStatus, PollingMetrics

# Verbose debug toggle (mirrors coordinator.py)
VERBOSE_DEBUG = False

# Number of consecutive failures after which we escalate to ERROR level
FAILURE_ERROR_THRESHOLD = 3  # keep behaviour identical to original implementation

# Adaptive polling intervals
FAST_POLL_INTERVAL = 1  # seconds - during active playback
NORMAL_POLL_INTERVAL = 5  # seconds - when idle (original fixed interval)

_LOGGER = logging.getLogger(__name__)


def _determine_adaptive_interval(coordinator, status_model: PlayerStatus, role: str) -> int:
    """Determine polling interval based on playback state and group role.

    Returns:
        1 second if any device in the ecosystem is playing
        5 seconds if all devices are idle
    """
    # Check if this device is playing
    is_playing = str(status_model.play_state or "").lower() == "play"

    # For group masters, also check if any slaves are playing
    if role == "master" and not is_playing:
        try:
            from .data import get_speaker_from_config_entry

            speaker = get_speaker_from_config_entry(coordinator.hass, coordinator.entry)
            for member in speaker.group_members:
                member_state = member.get_playback_state()
                if member_state and str(member_state).lower() == "playing":
                    is_playing = True
                    _LOGGER.debug("Group member %s is playing, enabling fast polling", member.name)
                    break
        except Exception as err:
            _LOGGER.debug("Could not check group member states: %s", err)
            # Fallback to device-only check

    return FAST_POLL_INTERVAL if is_playing else NORMAL_POLL_INTERVAL


async def async_update_data(coordinator) -> dict[str, Any]:
    """Heavy polling implementation extracted from ``WiiMCoordinator``.

    The full implementation now lives here to keep ``coordinator.py`` under
    the 300-LOC soft limit while providing identical behaviour.

    Enhanced with adaptive polling that switches between 1s (playback) and 5s (idle).
    """

    _LOGGER.debug("=== COORDINATOR UPDATE START for %s ===", coordinator.client.host)

    # Track latency of the entire update cycle for diagnostics.
    _start_time = time.perf_counter()

    # 0. One-time attempt to fetch the full preset list (EQGetList)
    if not coordinator._eq_list_extended:
        await coordinator._extend_eq_preset_map_once()

    try:
        # ------------------------------------------------------------------
        # Core data – always required
        # ------------------------------------------------------------------
        # Fetch *typed* player status
        status_model: PlayerStatus = await _endpoints.fetch_player_status(coordinator.client)
        _LOGGER.debug(
            "Player status result for %s (fields=%s)",
            coordinator.client.host,
            list(status_model.model_dump(exclude_none=True).keys()),
        )

        # Endpoint health – if we reach here the call succeeded.
        coordinator._player_status_working = True

        # ------------------------------------------------------------------
        # Device info
        # ------------------------------------------------------------------
        _LOGGER.debug("Step 2: Getting device info for %s", coordinator.client.host)
        device_model: DeviceInfo = await _endpoints.fetch_device_info(coordinator.client)

        if VERBOSE_DEBUG:
            _LOGGER.debug(
                "Device info result for %s: %s",
                coordinator.client.host,
                device_model.model_dump(exclude_none=True),
            )
        else:
            _LOGGER.debug(
                "Device info result for %s (keys=%s)",
                coordinator.client.host,
                list(device_model.model_dump(exclude_none=True).keys()),
            )

        coordinator._device_info_working = True

        # --------------------------------------------------------
        # Normalise extra device info so sensors remain clean.  The helper
        # now operates directly on the *model* to remove dict.get() logic.
        # --------------------------------------------------------
        try:
            from . import coordinator_normalise as _norm

            normalised = _norm.normalise_device_info(device_model)
            # Inject derived fields back into the DeviceInfo model via model_copy(update=…)
            device_model = device_model.model_copy(update=normalised)  # type: ignore[attr-defined]
        except Exception as norm_err:  # pragma: no cover – non-critical
            _LOGGER.debug("Normalising device_info failed for %s: %s", coordinator.client.host, norm_err)

        # ------------------------------------------------------------------
        # Multi-room info
        # ------------------------------------------------------------------
        _LOGGER.debug("Step 3: Getting multiroom info for %s", coordinator.client.host)
        multiroom_info = await coordinator._fetch_multiroom_info()
        _LOGGER.debug(
            "Multiroom info result for %s%s",
            coordinator.client.host,
            f": {multiroom_info}" if VERBOSE_DEBUG else f" (keys={list(multiroom_info.keys())})",
        )
        coordinator._multiroom_working = bool(multiroom_info)

        # ------------------------------------------------------------------
        # Track metadata
        # ------------------------------------------------------------------
        _LOGGER.debug("Step 4: Getting track metadata for %s", coordinator.client.host)
        track_metadata_model = await coordinator._fetch_track_metadata(status_model)
        track_metadata = track_metadata_model.model_dump(exclude_none=True)
        _LOGGER.debug(
            "Track metadata result for %s%s",
            coordinator.client.host,
            f": {track_metadata}" if VERBOSE_DEBUG else f" (keys={list(track_metadata.keys())})",
        )

        # ------------------------------------------------------------------
        # Preset list (optional)
        # ------------------------------------------------------------------
        presets_list: list[dict] = []
        if coordinator._presets_supported is not False:
            try:
                presets_list = await coordinator.client.get_presets()
                if presets_list and coordinator._presets_supported is None:
                    coordinator._presets_supported = True
            except WiiMError:
                if coordinator._presets_supported is None:
                    coordinator._presets_supported = False
            except Exception as pre_err:
                _LOGGER.debug("get_presets failed for %s: %s", coordinator.client.host, pre_err)

        # ------------------------------------------------------------------
        # Artwork propagation
        # ------------------------------------------------------------------
        if track_metadata:
            art_url = track_metadata.get("entity_picture") or track_metadata.get("cover_url")
            if art_url and getattr(status_model, "entity_picture", None) != art_url:
                _LOGGER.debug("Propagating artwork URL to PlayerStatus: %s", art_url)

                status_model.entity_picture = art_url  # type: ignore[attr-defined]
                status_model.cover_url = art_url  # type: ignore[attr-defined]

        # ------------------------------------------------------------------
        # EQ info
        # ------------------------------------------------------------------
        _LOGGER.debug("Step 5: Getting EQ info for %s", coordinator.client.host)
        eq_info_model = await coordinator._fetch_eq_info()
        eq_info = eq_info_model.model_dump(exclude_none=True)
        _LOGGER.debug(
            "EQ info result for %s%s",
            coordinator.client.host,
            f": {eq_info}" if VERBOSE_DEBUG else f" (keys={list(eq_info.keys())})",
        )

        # ------------------------------------------------------------------
        # Role detection
        # ------------------------------------------------------------------
        _LOGGER.debug("Step 6: Detecting role for %s", coordinator.client.host)
        role = await coordinator._detect_role_from_status_and_slaves(status_model, multiroom_info, device_model)
        _LOGGER.debug("Detected role for %s: %s", coordinator.client.host, role)

        # ------------------------------------------------------------------
        # Multi-room source / media resolution
        # ------------------------------------------------------------------
        _LOGGER.debug("Step 7: Resolving multiroom source and media for %s", coordinator.client.host)
        await coordinator._resolve_multiroom_source_and_media(status_model, track_metadata, role)

        # ------------------------------------------------------------------
        # Adaptive polling interval determination
        # ------------------------------------------------------------------
        new_interval = _determine_adaptive_interval(coordinator, status_model, role)
        interval_changed = coordinator.update_interval.total_seconds() != new_interval

        # ------------------------------------------------------------------
        # Polling diagnostics & final data structure
        # ------------------------------------------------------------------
        polling_data_model = PollingMetrics(
            interval=new_interval,  # Use adaptive interval
            is_playing=(str(status_model.play_state or "").lower() == "play"),
            api_capabilities={
                "statusex_supported": coordinator._statusex_supported,
                "metadata_supported": coordinator._metadata_supported,
                "eq_supported": coordinator._eq_supported,
            },
        )
        polling_data = polling_data_model.model_dump(exclude_none=True)

        # Add adaptive polling state for diagnostics
        polling_data.update(
            {
                "adaptive_polling": True,
                "interval_reason": "playback_active" if new_interval == FAST_POLL_INTERVAL else "idle",
                "fast_polling_active": new_interval == FAST_POLL_INTERVAL,
            }
        )

        # Final aggregated data exposed via the coordinator.  Only *typed models* are
        # propagated – legacy dict dumps have been removed as part of the Pydantic
        # rollout (see TODO §1).  Down-stream code must now consume the models via
        # ``status_model`` and ``device_model``.

        data: dict[str, Any] = {
            "status_model": status_model,
            "device_model": device_model,
            "multiroom": multiroom_info,
            "metadata_model": track_metadata_model,
            "metadata": track_metadata,
            "eq_model": eq_info_model,
            "eq": eq_info,
            "presets": presets_list,
            "role": role,
            "polling_metrics": polling_data_model,
            "polling": polling_data,
        }

        if eq_info_model.eq_preset is not None:
            status_model.eq_preset = eq_info_model.eq_preset  # type: ignore[attr-defined]
            _LOGGER.debug("Propagated EQ preset to PlayerStatus: %s", eq_info_model.eq_preset)

        # Ensure UUID is present – some firmwares omit it.
        if device_model.uuid is None and coordinator.entry and getattr(coordinator.entry, "unique_id", None):
            device_model.uuid = coordinator.entry.unique_id  # type: ignore[assignment]
            _LOGGER.debug("Injected UUID from config entry as API did not provide one")

        _LOGGER.debug(
            "Step 8: Final coordinator data for %s (keys=%s)",
            coordinator.client.host,
            list(data.keys()),
        )

        # Update speaker object with comprehensive data
        _LOGGER.debug("Step 9: Updating speaker object for %s", coordinator.client.host)
        await coordinator._update_speaker_object(data)

        # ------------------------------------------------------------------
        # Success handling – adaptive polling interval adjustment
        # ------------------------------------------------------------------
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

        if coordinator._last_command_failure is not None:
            coordinator.clear_command_failures()

        # Record overall turnaround time in milliseconds
        coordinator._last_response_time = (time.perf_counter() - _start_time) * 1000.0

        _LOGGER.debug("=== COORDINATOR UPDATE SUCCESS for %s ===", coordinator.client.host)
        return data

    except WiiMError as err:
        # ------------------------------------------------------------------
        # Failure handling – back-off & logging
        # ------------------------------------------------------------------
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
            "%s: Coordinator update failed (attempt %d): %s",
            coordinator.client.host,
            coordinator._backoff.consecutive_failures,
            err,
        )

        # On error, use backoff logic but ensure minimum safe interval
        backoff_interval = coordinator._backoff.next_interval(NORMAL_POLL_INTERVAL)
        coordinator.update_interval = timedelta(seconds=backoff_interval)

        raise UpdateFailed(f"Error updating WiiM device: {err}") from err
