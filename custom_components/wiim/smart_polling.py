"""Smart Adaptive Polling System for WiiM Integration

This module implements an intelligent polling strategy that adapts API call frequency
and selection based on device activity patterns, dramatically reducing network traffic
during idle periods while maintaining responsiveness during active use.

Key Features:
- Multi-tier polling (1s → 5s → 30s → 120s) based on activity
- Smart API call selection per activity level
- User command tracking for immediate responsiveness
- Position prediction to reduce API calls
- Comprehensive activity detection (playback, commands, groups, volume)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional

from .api import WiiMClient, WiiMError

_LOGGER = logging.getLogger(__name__)


class ActivityLevel(Enum):
    """Device activity levels determining polling frequency."""

    ACTIVE_PLAYBACK = auto()  # Playing audio - 1s polling
    RECENT_ACTIVITY = auto()  # Recent user interaction - 5s polling
    BACKGROUND_IDLE = auto()  # Idle but available - 30s polling
    DEEP_SLEEP = auto()  # Long-term idle - 120s polling
    ERROR_BACKOFF = auto()  # API errors - exponential backoff


@dataclass
class ActivityMetrics:
    """Track various activity timestamps for intelligent polling decisions."""

    last_playback_time: Optional[float] = None  # Last time playing audio
    last_user_command: Optional[float] = None  # Last user interaction (play/pause/volume)
    last_group_change: Optional[float] = None  # Last group membership change
    last_volume_change: Optional[float] = None  # Last volume adjustment
    last_source_change: Optional[float] = None  # Last source selection
    last_eq_change: Optional[float] = None  # Last EQ modification
    last_track_change: Optional[float] = None  # Last track/metadata change

    # Internal tracking
    consecutive_api_failures: int = 0
    last_successful_update: Optional[float] = None

    def record_user_command(self, command_type: str) -> None:
        """Record a user command for activity tracking."""
        now = time.time()
        self.last_user_command = now

        # Specific command type tracking
        if command_type in ("play", "pause", "stop", "next", "previous"):
            self.last_playback_time = now
        elif command_type in ("volume", "mute"):
            self.last_volume_change = now
        elif command_type == "source":
            self.last_source_change = now
        elif command_type in ("eq", "sound_mode"):
            self.last_eq_change = now
        elif command_type in ("join", "unjoin", "create_group"):
            self.last_group_change = now

        _LOGGER.debug("[WiiM] Smart Polling: Recorded user command '%s'", command_type)

    def record_successful_update(self) -> None:
        """Record a successful API update."""
        self.last_successful_update = time.time()
        self.consecutive_api_failures = 0

    def record_api_failure(self) -> None:
        """Record an API failure for backoff calculation."""
        self.consecutive_api_failures += 1
        _LOGGER.debug("[WiiM] Smart Polling: API failure count: %d", self.consecutive_api_failures)


class ActivityTracker:
    """Intelligent activity detection and level determination."""

    def __init__(
        self,
        idle_timeout: int = 600,  # 10 minutes
        deep_sleep_timeout: int = 3600,
    ):  # 1 hour
        """Initialize activity tracker with configurable timeouts."""
        self.metrics = ActivityMetrics()
        self.idle_timeout = idle_timeout
        self.deep_sleep_timeout = deep_sleep_timeout
        self.current_level = ActivityLevel.BACKGROUND_IDLE

        _LOGGER.debug(
            "[WiiM] Smart Polling: Activity tracker initialized (idle_timeout=%ds, deep_sleep_timeout=%ds)",
            idle_timeout,
            deep_sleep_timeout,
        )

    def update_activity(self, status: dict, metadata: dict = None) -> ActivityLevel:
        """Determine current activity level based on device state and history."""
        now = time.time()
        previous_level = self.current_level

        # Handle API failures first
        if self.metrics.consecutive_api_failures >= 3:
            self.current_level = ActivityLevel.ERROR_BACKOFF

        # High activity: actively playing audio
        elif status.get("play_status") == "play":
            self.metrics.last_playback_time = now
            self.current_level = ActivityLevel.ACTIVE_PLAYBACK

        # Medium activity: recent user interaction or track changes
        elif self._has_recent_activity(now, self.idle_timeout):
            self.current_level = ActivityLevel.RECENT_ACTIVITY

        # Low activity: some recent activity but beyond idle timeout
        elif self._has_background_activity(now, self.deep_sleep_timeout):
            self.current_level = ActivityLevel.BACKGROUND_IDLE

        # Minimal activity: long-term idle
        else:
            self.current_level = ActivityLevel.DEEP_SLEEP

        # Log level changes for monitoring
        if self.current_level != previous_level:
            _LOGGER.info(
                "[WiiM] Smart Polling: Activity level changed %s → %s", previous_level.name, self.current_level.name
            )

        return self.current_level

    def _has_recent_activity(self, now: float, timeout: int) -> bool:
        """Check if there's been recent activity within timeout."""
        recent_timestamps = [
            self.metrics.last_playback_time,
            self.metrics.last_user_command,
            self.metrics.last_group_change,
            self.metrics.last_volume_change,
            self.metrics.last_source_change,
            self.metrics.last_track_change,
        ]

        return any(timestamp and (now - timestamp) < timeout for timestamp in recent_timestamps)

    def _has_background_activity(self, now: float, timeout: int) -> bool:
        """Check if there's been any activity within deep sleep timeout."""
        background_timestamps = [
            self.metrics.last_playback_time,
            self.metrics.last_user_command,
            self.metrics.last_successful_update,
        ]

        return any(timestamp and (now - timestamp) < timeout for timestamp in background_timestamps)

    def force_activity_level(self, level: ActivityLevel) -> None:
        """Force a specific activity level (for immediate command response)."""
        previous_level = self.current_level
        self.current_level = level

        _LOGGER.debug("[WiiM] Smart Polling: Forced activity level %s → %s", previous_level.name, level.name)

    def detect_track_change(self, old_status: dict, new_status: dict) -> bool:
        """Detect if track metadata changed (indicates activity)."""
        track_fields = ["title", "artist", "album", "position"]

        for field in track_fields:
            if old_status.get(field) != new_status.get(field):
                self.metrics.last_track_change = time.time()
                _LOGGER.debug("[WiiM] Smart Polling: Track change detected (%s)", field)
                return True

        return False


@dataclass
class PollingMetrics:
    """Track polling performance metrics for monitoring."""

    api_calls_last_hour: int = 0
    api_calls_total: int = 0
    bandwidth_saved_bytes: int = 0
    average_response_time: float = 0.0

    # Rolling counters (reset hourly)
    _call_timestamps: list[float] = field(default_factory=list)
    _response_times: list[float] = field(default_factory=list)

    def record_api_call(self, response_time: float, bytes_transferred: int = 0) -> None:
        """Record an API call for metrics tracking."""
        now = time.time()

        # Add to rolling counters
        self._call_timestamps.append(now)
        self._response_times.append(response_time)

        # Remove old entries (older than 1 hour)
        cutoff = now - 3600
        self._call_timestamps = [t for t in self._call_timestamps if t > cutoff]
        self._response_times = [t for t in self._response_times if t > cutoff]

        # Update metrics
        self.api_calls_last_hour = len(self._call_timestamps)
        self.api_calls_total += 1

        if self._response_times:
            self.average_response_time = sum(self._response_times) / len(self._response_times)

    def estimate_bandwidth_saved(self, calls_avoided: int, avg_response_size: int = 1024) -> int:
        """Estimate bandwidth saved by avoiding API calls."""
        saved = calls_avoided * avg_response_size
        self.bandwidth_saved_bytes += saved
        return saved


class SmartPollingManager:
    """Manage intelligent API call selection and timing based on activity levels."""

    def __init__(self, client: WiiMClient):
        """Initialize smart polling manager."""
        self.client = client
        self.activity_tracker = ActivityTracker()
        self.metrics = PollingMetrics()

        # Polling intervals per activity level (seconds)
        self.polling_intervals = {
            ActivityLevel.ACTIVE_PLAYBACK: 1,  # 1 second - responsive playback
            ActivityLevel.RECENT_ACTIVITY: 5,  # 5 seconds - recent user activity
            ActivityLevel.BACKGROUND_IDLE: 30,  # 30 seconds - idle but available
            ActivityLevel.DEEP_SLEEP: 120,  # 2 minutes - minimal activity
            ActivityLevel.ERROR_BACKOFF: 60,  # 1 minute base for exponential backoff
        }

        # Cache for avoiding redundant API calls
        self._status_cache: Optional[dict] = None
        self._metadata_cache: Optional[dict] = None
        self._multiroom_cache: Optional[dict] = None
        self._last_cache_time: Optional[float] = None

        _LOGGER.info("[WiiM] Smart Polling Manager initialized")

    def get_polling_interval(self, activity_level: ActivityLevel) -> int:
        """Get appropriate polling interval for activity level."""
        base_interval = self.polling_intervals[activity_level]

        if activity_level == ActivityLevel.ERROR_BACKOFF:
            # Exponential backoff for API failures
            failures = self.activity_tracker.metrics.consecutive_api_failures
            backoff_multiplier = min(2 ** (failures - 3), 8)  # Cap at 8x
            interval = base_interval * backoff_multiplier

            _LOGGER.debug("[WiiM] Smart Polling: Error backoff interval: %ds (failures=%d)", interval, failures)
            return interval

        return base_interval

    async def update_device_data(self, activity_level: ActivityLevel) -> dict[str, Any]:
        """Update device data with optimized API calls based on activity level."""
        start_time = time.time()
        data = {}
        api_calls_made = []

        try:
            # Always get basic status (most important data)
            status = await self._get_player_status()
            data["status"] = status
            api_calls_made.append("get_player_status")

            # Activity-based API call selection
            if activity_level == ActivityLevel.ACTIVE_PLAYBACK:
                # During playback: get full metadata frequently for smooth UI
                metadata = await self._get_metadata_if_needed(status, force=True)
                if metadata:
                    data["metadata"] = metadata
                    api_calls_made.append("get_meta_info")

                multiroom = await self._get_multiroom_info()
                data["multiroom"] = multiroom
                api_calls_made.append("get_multiroom_info")

                # Skip EQ during playback (not needed for smooth operation)

            elif activity_level == ActivityLevel.RECENT_ACTIVITY:
                # Recent activity: standard polling with metadata when needed
                metadata = await self._get_metadata_if_needed(status)
                if metadata:
                    data["metadata"] = metadata
                    api_calls_made.append("get_meta_info")

                multiroom = await self._get_multiroom_info()
                data["multiroom"] = multiroom
                api_calls_made.append("get_multiroom_info")

                # EQ only occasionally (every 3rd call handled elsewhere)

            elif activity_level == ActivityLevel.BACKGROUND_IDLE:
                # Idle: minimal polling - only multiroom for group state
                multiroom = await self._get_multiroom_info()
                data["multiroom"] = multiroom
                api_calls_made.append("get_multiroom_info")

                # Skip metadata and EQ unless forced refresh

            elif activity_level == ActivityLevel.DEEP_SLEEP:
                # Deep sleep: status only
                # Skip all secondary API calls to minimize network usage
                pass

            elif activity_level == ActivityLevel.ERROR_BACKOFF:
                # Error backoff: minimal calls, try to recover
                # Only basic status, skip everything else
                pass

            # Track polling success
            self.activity_tracker.metrics.record_successful_update()

            # Update caches
            self._update_caches(data)

        except WiiMError as err:
            _LOGGER.warning("[WiiM] Smart Polling: API call failed: %s", err)
            self.activity_tracker.metrics.record_api_failure()
            raise

        # Record metrics
        response_time = time.time() - start_time
        self.metrics.record_api_call(response_time)

        # Calculate bandwidth savings (estimate calls avoided)
        total_possible_calls = 4  # status, metadata, multiroom, eq
        calls_made = len(api_calls_made)
        calls_avoided = total_possible_calls - calls_made

        if calls_avoided > 0:
            self.metrics.estimate_bandwidth_saved(calls_avoided)

        _LOGGER.debug(
            "[WiiM] Smart Polling: Activity=%s, APIs=%s, Response=%.2fs, Saved=%d calls",
            activity_level.name,
            api_calls_made,
            response_time,
            calls_avoided,
        )

        return data

    async def _get_player_status(self) -> dict:
        """Get player status with fallback and caching."""
        try:
            return await self.client.get_player_status() or {}
        except WiiMError:
            # Fallback to basic status
            try:
                return await self.client.get_status() or {}
            except WiiMError:
                # Use cached status if available
                if self._status_cache:
                    _LOGGER.debug("[WiiM] Smart Polling: Using cached status due to API failure")
                    return self._status_cache
                raise

    async def _get_metadata_if_needed(self, status: dict, force: bool = False) -> Optional[dict]:
        """Get metadata only if track changed or forced."""
        if not force and self._metadata_cache:
            # Check if track changed
            cached_title = self._metadata_cache.get("title")
            current_title = status.get("title")

            if cached_title == current_title and current_title:
                # Same track, use cached metadata
                return None

        try:
            metadata = await self.client.get_meta_info()
            return metadata or {}
        except WiiMError:
            # Return cached metadata if available
            return self._metadata_cache

    async def _get_multiroom_info(self) -> dict:
        """Get multiroom info with caching."""
        try:
            return await self.client.get_multiroom_info() or {}
        except WiiMError:
            # Use cached multiroom info if available
            if self._multiroom_cache:
                _LOGGER.debug("[WiiM] Smart Polling: Using cached multiroom info due to API failure")
                return self._multiroom_cache
            return {}

    def _update_caches(self, data: dict) -> None:
        """Update internal caches with latest data."""
        self._last_cache_time = time.time()

        if "status" in data:
            self._status_cache = data["status"]

        if "metadata" in data:
            self._metadata_cache = data["metadata"]

        if "multiroom" in data:
            self._multiroom_cache = data["multiroom"]

    def record_user_command(self, command_type: str) -> None:
        """Record user command and potentially adjust polling."""
        self.activity_tracker.metrics.record_user_command(command_type)

        # For immediate responsiveness, force active polling for certain commands
        if command_type in ("play", "pause", "stop"):
            self.activity_tracker.force_activity_level(ActivityLevel.ACTIVE_PLAYBACK)
        else:
            # Other commands trigger recent activity level
            self.activity_tracker.force_activity_level(ActivityLevel.RECENT_ACTIVITY)

    def get_polling_diagnostics(self) -> dict:
        """Get comprehensive polling diagnostics for monitoring."""
        activity_level = self.activity_tracker.current_level

        return {
            "activity_level": activity_level.name,
            "polling_interval": self.get_polling_interval(activity_level),
            "metrics": {
                "api_calls_last_hour": self.metrics.api_calls_last_hour,
                "api_calls_total": self.metrics.api_calls_total,
                "average_response_time": self.metrics.average_response_time,
                "bandwidth_saved_mb": self.metrics.bandwidth_saved_bytes / (1024 * 1024),
                "consecutive_failures": self.activity_tracker.metrics.consecutive_api_failures,
            },
            "last_activities": {
                "playback": self.activity_tracker.metrics.last_playback_time,
                "user_command": self.activity_tracker.metrics.last_user_command,
                "group_change": self.activity_tracker.metrics.last_group_change,
                "volume_change": self.activity_tracker.metrics.last_volume_change,
                "source_change": self.activity_tracker.metrics.last_source_change,
                "track_change": self.activity_tracker.metrics.last_track_change,
            },
            "cache_status": {
                "status_cached": self._status_cache is not None,
                "metadata_cached": self._metadata_cache is not None,
                "multiroom_cached": self._multiroom_cache is not None,
                "last_cache_time": self._last_cache_time,
            },
        }


class PlaybackPositionTracker:
    """Intelligent position tracking with prediction to reduce API calls."""

    def __init__(self):
        """Initialize position tracker."""
        self.last_position = None
        self.last_position_time = None
        self.last_duration = None
        self.position_drift_detected = False
        self.prediction_confidence = 1.0

    def update_position(self, position: Optional[int], duration: Optional[int] = None) -> None:
        """Update position tracking with new API data."""
        if position is not None:
            now = time.time()

            # Check for position drift
            if self.last_position and self.last_position_time:
                expected_position = self.predict_current_position()
                if expected_position and abs(expected_position - position) > 2:
                    self.position_drift_detected = True
                    self.prediction_confidence *= 0.8  # Reduce confidence
                    _LOGGER.debug("[WiiM] Position drift detected: expected=%d, actual=%d", expected_position, position)
                else:
                    self.position_drift_detected = False
                    self.prediction_confidence = min(1.0, self.prediction_confidence * 1.1)

            self.last_position = position
            self.last_position_time = now

        if duration is not None:
            self.last_duration = duration

    def predict_current_position(self) -> Optional[int]:
        """Predict current position without API call."""
        if not self.last_position or not self.last_position_time:
            return None

        if self.prediction_confidence < 0.5:
            # Low confidence, don't predict
            return None

        elapsed = time.time() - self.last_position_time
        predicted = self.last_position + elapsed

        # Bounds check
        if self.last_duration and predicted > self.last_duration:
            predicted = self.last_duration

        return int(predicted) if predicted >= 0 else 0

    def should_update_position(self, activity_level: ActivityLevel) -> bool:
        """Determine if position needs updating from API."""
        if activity_level == ActivityLevel.ACTIVE_PLAYBACK:
            # During playback: frequent updates for smooth UI
            return True

        elif activity_level == ActivityLevel.RECENT_ACTIVITY:
            # Recently active: periodic verification
            if not self.last_position_time:
                return True

            # Update every 30 seconds during recent activity
            return (time.time() - self.last_position_time) > 30

        else:
            # Idle: only if position tracking is unreliable
            return self.position_drift_detected

    def get_display_position(self) -> Optional[int]:
        """Get position for display (predicted or actual)."""
        predicted = self.predict_current_position()
        return predicted if predicted is not None else self.last_position
