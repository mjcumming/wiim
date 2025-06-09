"""WiiM Media Player Controller

Single controller handling ALL media player complexity including:
- Volume management with master/slave coordination
- Playback control with group awareness
- Source selection with EQ and mode management
- Group operations with validation and state sync
- Power control with device coordination
- Media metadata and artwork handling

This follows our simplified architecture avoiding over-engineering while
maintaining proper separation of concerns between the HA entity interface
and complex media player business logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_VOLUME_STEP,
    DEFAULT_VOLUME_STEP,
    EQ_PRESET_MAP,
    PLAY_MODE_NORMAL,
    PLAY_MODE_REPEAT_ALL,
    PLAY_MODE_REPEAT_ONE,
    PLAY_MODE_SHUFFLE,
)

if TYPE_CHECKING:
    from .data import Speaker
else:
    pass

_LOGGER = logging.getLogger(__name__)


class MediaPlayerController:
    """Single controller handling ALL media player complexity.

    This controller encapsulates:
    - Volume management with master/slave coordination
    - Playback control with group awareness
    - Source selection with EQ and mode management
    - Group operations with validation and state sync
    - Power control with device coordination
    - Media metadata and artwork handling
    """

    def __init__(self, speaker: Speaker) -> None:
        """Initialize the media player controller."""
        self.speaker = speaker
        self.hass = speaker.hass
        self._logger = logging.getLogger(f"{__name__}.{speaker.name}")

        # Get volume step from integration config or use default
        self._volume_step = (
            speaker.coordinator.config_entry.options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP) / 100.0
        )  # Convert percentage to 0.0-1.0

        # Media image caching (like LinkPlay integration)
        self._media_image_url_cached: str | None = None
        self._media_image_bytes: bytes | None = None
        self._media_image_content_type: str | None = None

        # Internal trackers to avoid noisy duplicate logs on every property poll
        self._last_sound_mode: str | None = None
        self._last_shuffle_state: bool | None = None
        self._last_repeat_mode: str | None = None

        self._logger.debug(
            "MediaPlayerController initialized for %s (volume_step=%.2f)",
            speaker.name,
            self._volume_step,
        )

    def clear_media_image_cache(self) -> None:
        """Clear the media image cache to force re-download on next request.

        Called when track metadata changes to ensure cover art updates.
        """
        if self._media_image_url_cached or self._media_image_bytes:
            self._logger.debug("Clearing media image cache for %s", self.speaker.name)
            self._media_image_url_cached = None
            self._media_image_bytes = None
            self._media_image_content_type = None

    # ===== VOLUME CONTROL =====

    async def set_volume(self, volume: float) -> None:
        """Set volume with master/slave logic.

        Args:
            volume: Volume level 0.0-1.0

        Raises:
            HomeAssistantError: If volume setting fails
        """
        try:
            self._logger.debug("Setting volume to %.2f for %s", volume, self.speaker.name)

            # Send volume directly to *this* device regardless of role.
            # Group-level aggregation is handled by the group-volume entity.
            await self.speaker.coordinator.client.set_volume(volume)

        except Exception as err:
            self._logger.error("Failed to set volume to %.2f: %s", volume, err)
            raise HomeAssistantError(
                f"Failed to set volume to {int(volume * 100)}% on {self.speaker.name}: {err}"
            ) from err

    async def set_mute(self, mute: bool) -> None:
        """Set mute with master/slave logic.

        Args:
            mute: True to mute, False to unmute

        Raises:
            HomeAssistantError: If mute setting fails
        """
        try:
            self._logger.debug("Setting mute to %s for %s", mute, self.speaker.name)

            # Implement master/slave logic
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                # Slave should control master mute
                self._logger.debug("Slave speaker redirecting mute to master")
                await self.speaker.coordinator_speaker.coordinator.client.set_mute(mute)
            else:
                # Master or solo speaker controls directly
                await self.speaker.coordinator.client.set_mute(mute)

        except Exception as err:
            self._logger.error("Failed to set mute to %s: %s", mute, err)
            raise HomeAssistantError(f"Failed to set mute: {err}") from err

    async def volume_up(self, step: float | None = None) -> None:
        """Volume up with configurable step.

        Args:
            step: Volume step (0.0-1.0), uses configured default if None
        """
        current_volume = self.get_volume_level()
        if current_volume is None:
            self._logger.warning("Cannot increase volume - current volume unknown")
            return

        step = step or self._volume_step
        new_volume = min(1.0, current_volume + step)

        self._logger.debug("Volume up: %.2f -> %.2f (step=%.2f)", current_volume, new_volume, step)
        await self.set_volume(new_volume)

    async def volume_down(self, step: float | None = None) -> None:
        """Volume down with configurable step.

        Args:
            step: Volume step (0.0-1.0), uses configured default if None
        """
        current_volume = self.get_volume_level()
        if current_volume is None:
            self._logger.warning("Cannot decrease volume - current volume unknown")
            return

        step = step or self._volume_step
        new_volume = max(0.0, current_volume - step)

        self._logger.debug("Volume down: %.2f -> %.2f (step=%.2f)", current_volume, new_volume, step)
        await self.set_volume(new_volume)

    def get_volume_level(self) -> float | None:
        """Get effective volume (master/slave aware).

        Returns:
            Volume level 0.0-1.0, or None if unknown
        """
        return self.speaker.get_volume_level()

    def is_volume_muted(self) -> bool | None:
        """Get effective mute state (master/slave aware).

        Returns:
            True if muted, False if not muted, None if unknown
        """
        return self.speaker.is_volume_muted()

    # ===== PLAYBACK CONTROL =====

    async def play(self) -> None:
        """Start playback (master/slave aware)."""
        try:
            self._logger.debug("Starting playback for %s", self.speaker.name)

            # Implement master/slave logic - slaves should control master
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                self._logger.debug("Slave speaker redirecting play to master")
                await self.speaker.coordinator_speaker.coordinator.client.play()
            else:
                await self.speaker.coordinator.client.play()

        except Exception as err:
            self._logger.error("Failed to start playback: %s", err)
            raise HomeAssistantError(f"Failed to play: {err}") from err

    async def pause(self) -> None:
        """Pause playback (master/slave aware)."""
        try:
            self._logger.debug("Pausing playback for %s", self.speaker.name)

            # Implement master/slave logic - slaves should control master
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                self._logger.debug("Slave speaker redirecting pause to master")
                await self.speaker.coordinator_speaker.coordinator.client.pause()
            else:
                await self.speaker.coordinator.client.pause()

        except Exception as err:
            self._logger.error("Failed to pause playback: %s", err)
            raise HomeAssistantError(f"Failed to pause: {err}") from err

    async def stop(self) -> None:
        """Stop playback."""
        try:
            self._logger.debug("Stopping playback for %s", self.speaker.name)

            # Implement master/slave logic - slaves should control master
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                self._logger.debug("Slave speaker redirecting stop to master")
                await self.speaker.coordinator_speaker.coordinator.client.stop()
            else:
                await self.speaker.coordinator.client.stop()

        except Exception as err:
            self._logger.error("Failed to stop playback: %s", err)
            raise HomeAssistantError(f"Failed to stop: {err}") from err

    async def next_track(self) -> None:
        """Next track (master/slave aware)."""
        try:
            self._logger.debug("Next track for %s", self.speaker.name)

            # Implement master/slave logic - slaves should control master
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                self._logger.debug("Slave speaker redirecting next to master")
                await self.speaker.coordinator_speaker.coordinator.client.next_track()
            else:
                await self.speaker.coordinator.client.next_track()

        except Exception as err:
            self._logger.error("Failed to skip to next track: %s", err)
            raise HomeAssistantError(f"Failed to skip to next track: {err}") from err

    async def previous_track(self) -> None:
        """Previous track (master/slave aware)."""
        try:
            self._logger.debug("Previous track for %s", self.speaker.name)

            # Implement master/slave logic - slaves should control master
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                self._logger.debug("Slave speaker redirecting previous to master")
                await self.speaker.coordinator_speaker.coordinator.client.previous_track()
            else:
                await self.speaker.coordinator.client.previous_track()

        except Exception as err:
            self._logger.error("Failed to skip to previous track: %s", err)
            raise HomeAssistantError(f"Failed to skip to previous track: {err}") from err

    async def seek(self, position: float) -> None:
        """Seek to position.

        Args:
            position: Position in seconds
        """
        try:
            self._logger.debug("Seeking to position %.1f for %s", position, self.speaker.name)

            await self.speaker.coordinator.client.seek(int(position))

        except Exception as err:
            self._logger.error("Failed to seek to position %.1f: %s", position, err)
            raise HomeAssistantError(f"Failed to seek: {err}") from err

    def get_playback_state(self) -> MediaPlayerState:
        """Get current playback state."""
        return self.speaker.get_playback_state()

    # ===== SOURCE & AUDIO CONTROL =====

    async def select_source(self, source: str) -> None:
        """Select source, handle slave group leaving.

        Args:
            source: Source name to select
        """
        try:
            self._logger.debug("Selecting source '%s' for %s", source, self.speaker.name)

            # Map friendly source names to WiiM source IDs
            from .const import SOURCE_MAP

            # Try to find the internal source ID for the friendly name
            wiim_source = None
            for internal_id, friendly_name in SOURCE_MAP.items():
                if source == friendly_name or source.lower() == friendly_name.lower():
                    wiim_source = internal_id
                    break

            # If no mapping found, use the source as-is (might be internal ID already)
            if wiim_source is None:
                wiim_source = source.lower()

            self._logger.debug("Mapped source '%s' to WiiM source '%s'", source, wiim_source)

            # Implement slave group leaving logic - slaves should leave group when changing source
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                self._logger.debug("Slave speaker leaving group before changing source")
                try:
                    await self.speaker.async_leave_group()
                except Exception as leave_err:
                    self._logger.warning("Failed to leave group before source change: %s", leave_err)
                    # Continue with source change anyway

            await self.speaker.coordinator.client.set_source(wiim_source)

        except Exception as err:
            self._logger.error("Failed to select source '%s': %s", source, err)
            raise HomeAssistantError(f"Failed to select source '{source}' on {self.speaker.name}: {err}") from err

    async def set_eq_preset(self, preset: str) -> None:
        """Set EQ preset.

        Args:
            preset: EQ preset name (either internal key or display name)
        """
        try:
            self._logger.debug("Setting EQ preset '%s' for %s", preset, self.speaker.name)

            # Handle both internal keys and display names
            preset_key = None

            # First, try direct key lookup (e.g., "bassreducer")
            if preset in EQ_PRESET_MAP:
                preset_key = preset
            else:
                # Try reverse lookup for display names (e.g., "Bass Reducer")
                for key, display_name in EQ_PRESET_MAP.items():
                    if preset == display_name or preset.lower() == display_name.lower():
                        preset_key = key
                        break

            if preset_key is None:
                available_keys = list(EQ_PRESET_MAP.keys())
                available_names = list(EQ_PRESET_MAP.values())
                raise ValueError(
                    f"Unknown EQ preset '{preset}' on {self.speaker.name}. "
                    f"Available keys: {available_keys}. "
                    f"Available names: {available_names}"
                )

            # The API client expects the internal key, not the display name
            await self.speaker.coordinator.client.set_eq_preset(preset_key)

        except Exception as err:
            self._logger.error("Failed to set EQ preset '%s': %s", preset, err)
            raise HomeAssistantError(f"Failed to set EQ preset '{preset}' on {self.speaker.name}: {err}") from err

    async def set_shuffle(self, shuffle: bool) -> None:
        """Set shuffle mode with repeat coordination.

        Args:
            shuffle: True to enable shuffle, False to disable
        """
        try:
            self._logger.debug("=== SHUFFLE OPERATION START ===")
            self._logger.debug("Setting shuffle to %s for %s", shuffle, self.speaker.name)
            self._logger.debug(
                "Current speaker state: role=%s, available=%s", self.speaker.role, self.speaker.available
            )

            # Map boolean to WiiM shuffle mode constants (NOT string numbers!)
            shuffle_mode = PLAY_MODE_SHUFFLE if shuffle else PLAY_MODE_NORMAL
            self._logger.debug("Mapped shuffle=%s to mode constant='%s'", shuffle, shuffle_mode)

            # Log what we're about to send to the API
            self._logger.debug("About to call client.set_shuffle_mode('%s')", shuffle_mode)

            await self.speaker.coordinator.client.set_shuffle_mode(shuffle_mode)

            self._logger.debug("Successfully sent shuffle command to device")
            self._logger.debug("=== SHUFFLE OPERATION END ===")

        except Exception as err:
            self._logger.error("=== SHUFFLE OPERATION FAILED ===")
            self._logger.error("Failed to set shuffle to %s: %s", shuffle, err)
            self._logger.error("Error type: %s", type(err).__name__)
            self._logger.error("=== SHUFFLE OPERATION END ===")
            raise HomeAssistantError(f"Failed to set shuffle: {err}") from err

    async def set_repeat(self, repeat: str) -> None:
        """Set repeat mode (off/one/all).

        Args:
            repeat: Repeat mode - "off", "one", "all"
        """
        try:
            self._logger.debug("=== REPEAT OPERATION START ===")
            self._logger.debug("Setting repeat to '%s' for %s", repeat, self.speaker.name)
            self._logger.debug(
                "Current speaker state: role=%s, available=%s", self.speaker.role, self.speaker.available
            )

            # Map HA repeat modes to WiiM repeat mode constants (NOT string numbers!)
            if repeat == "off":
                repeat_mode = PLAY_MODE_NORMAL
            elif repeat == "one":
                repeat_mode = PLAY_MODE_REPEAT_ONE
            elif repeat == "all":
                repeat_mode = PLAY_MODE_REPEAT_ALL
            else:
                self._logger.error("Invalid repeat mode received: '%s'", repeat)
                raise ValueError(f"Unknown repeat mode '{repeat}' on {self.speaker.name}. Valid modes: off, one, all")

            self._logger.debug("Mapped repeat='%s' to mode constant='%s'", repeat, repeat_mode)

            # Log what we're about to send to the API
            self._logger.debug("About to call client.set_repeat_mode('%s')", repeat_mode)

            await self.speaker.coordinator.client.set_repeat_mode(repeat_mode)

            self._logger.debug("Successfully sent repeat command to device")
            self._logger.debug("=== REPEAT OPERATION END ===")

        except Exception as err:
            self._logger.error("=== REPEAT OPERATION FAILED ===")
            self._logger.error("Failed to set repeat to '%s': %s", repeat, err)
            self._logger.error("Error type: %s", type(err).__name__)
            self._logger.error("=== REPEAT OPERATION END ===")
            raise HomeAssistantError(f"Failed to set repeat: {err}") from err

    def get_source_list(self) -> list[str]:
        """Get sources (master/slave aware)."""
        try:
            from .const import SOURCE_MAP

            # Return friendly names for the UI
            return list(SOURCE_MAP.values())
        except Exception as err:
            self._logger.error("Failed to get source list: %s", err)
            return ["WiFi", "Bluetooth", "Line In", "Optical"]  # Basic fallback

    def get_current_source(self) -> str | None:
        """Get current source (master/slave aware)."""
        try:
            # Get the internal source from speaker
            internal_source = self.speaker.get_current_source()
            if not internal_source:
                return None

            # Handle dynamic slave sources like "Following [Master Name]"
            if internal_source.startswith("Following "):
                return internal_source  # Return as-is for slave sources

            # Map other internal sources to friendly names
            from .const import SOURCE_MAP

            return SOURCE_MAP.get(internal_source.lower(), internal_source)

        except Exception as err:
            self._logger.error("Failed to get current source: %s", err)
            return None

    def get_shuffle_state(self) -> bool | None:
        """Get shuffle state."""
        try:
            shuffle_state = self.speaker.get_shuffle_state()

            if shuffle_state != self._last_shuffle_state:
                self._logger.debug("Detected shuffle state: %s for %s", shuffle_state, self.speaker.name)
                self._last_shuffle_state = shuffle_state

            return shuffle_state
        except Exception as err:
            self._logger.error("Error getting shuffle state: %s", err)
            return None

    def get_repeat_mode(self) -> str | None:
        """Get repeat mode."""
        try:
            repeat_mode = self.speaker.get_repeat_mode()

            # Log only on change
            if repeat_mode != self._last_repeat_mode:
                self._logger.debug("Detected repeat mode: '%s' for %s", repeat_mode, self.speaker.name)
                self._last_repeat_mode = repeat_mode

            return repeat_mode
        except Exception as err:
            self._logger.error("Error getting repeat mode: %s", err)
            return None

    def get_sound_mode_list(self) -> list[str]:
        """Get available EQ presets (capitalized display names)."""
        return list(EQ_PRESET_MAP.values())  # Return display names: ["Flat", "Acoustic", "Bass"]

    def get_sound_mode(self) -> str | None:
        """Get current EQ preset."""
        try:
            sound_mode = self.speaker.get_sound_mode()

            if sound_mode != self._last_sound_mode:
                self._logger.debug("Detected sound mode: '%s' for %s", sound_mode, self.speaker.name)
                self._last_sound_mode = sound_mode

            return sound_mode
        except Exception as err:
            self._logger.error("Error getting sound mode: %s", err)
            return None

    # ===== GROUP MANAGEMENT =====

    async def join_group(self, group_members: list[str]) -> None:
        """HA native join with WiiM multiroom backend.

        Args:
            group_members: List of entity IDs to group with
        """
        try:
            self._logger.debug("Joining group with members: %s", group_members)

            # Validate and resolve entity IDs to Speaker objects using new architecture
            from .data import get_all_speakers, find_speaker_by_uuid

            all_speakers = get_all_speakers(self.hass)
            speakers = []

            # Resolve each supplied entity_id to a Speaker object via the
            # entity-registry → unique_id → UUID mapping.  Slug-based fallbacks
            # were removed – during beta we assume all entities expose a valid
            # unique_id that matches the speaker UUID.

            from homeassistant.helpers import entity_registry as er

            ent_reg = er.async_get(self.hass)

            for entity_id in group_members:
                reg_entry = ent_reg.async_get(entity_id)
                if reg_entry and reg_entry.unique_id:
                    speaker_match = find_speaker_by_uuid(self.hass, reg_entry.unique_id)
                    if speaker_match:
                        speakers.append(speaker_match)
                    else:
                        self._logger.debug(
                            "Entity '%s' unique_id '%s' not found among registered speakers",
                            entity_id,
                            reg_entry.unique_id,
                        )
                else:
                    self._logger.debug("Entity '%s' not found in registry or has no unique_id", entity_id)

            if not speakers:
                self._logger.warning("No valid speakers found for entity IDs: %s", group_members)
                raise HomeAssistantError(
                    f"No valid speakers found in group member list {group_members}. Available: {len(all_speakers)} speakers"
                )

            # Filter out self from the list if present
            target_speakers = [s for s in speakers if s is not self.speaker]
            if not target_speakers:
                self._logger.warning("No other speakers to join with")
                return

            # Use existing Speaker group join method (this speaker becomes master)
            await self.speaker.async_join_group(target_speakers)

            self._logger.info("Successfully joined group with %d speakers", len(target_speakers))

        except Exception as err:
            self._logger.error("Failed to join group: %s", err)
            raise HomeAssistantError(
                "Failed to create group with {} on {}: {}".format(", ".join(group_members), self.speaker.name, err)
            ) from err

    async def leave_group(self) -> None:
        """Leave current group."""
        try:
            self._logger.debug("Leaving group for %s", self.speaker.name)

            # Use existing Speaker group leave method
            await self.speaker.async_leave_group()

            self._logger.info("Successfully left group")

        except Exception as err:
            self._logger.error("Failed to leave group: %s", err)
            raise HomeAssistantError(f"Failed to remove {self.speaker.name} from group: {err}") from err

    def get_group_members(self) -> list[str]:
        """Get group member entity IDs."""
        try:
            # Use existing Speaker method to get group member entity IDs
            return self.speaker.get_group_member_entity_ids()
        except Exception as err:
            self._logger.error("Failed to get group members: %s", err)
            return []

    def get_group_leader(self) -> str | None:
        """Get group leader entity ID."""
        try:
            # In WiiM groups, the master is the leader
            if self.speaker.role == "master":
                # This speaker is the leader - return entity ID based on our UUID
                # Following HA naming convention: media_player.{uuid_with_underscores}
                entity_id = f"media_player.{self.speaker.uuid.replace('-', '_').lower()}"
                return entity_id
            elif self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                # Find the master's entity ID
                master_uuid = self.speaker.coordinator_speaker.uuid
                entity_id = f"media_player.{master_uuid.replace('-', '_').lower()}"
                return entity_id
            # Solo speakers have no leader
            return None
        except Exception as err:
            self._logger.error("Failed to get group leader: %s", err)
            return None

    # ===== MEDIA METADATA =====

    def get_media_title(self) -> str | None:
        """Get clean track title."""
        return self.speaker.get_media_title()

    def get_media_artist(self) -> str | None:
        """Get clean artist name."""
        return self.speaker.get_media_artist()

    def get_media_album(self) -> str | None:
        """Get clean album name."""
        return self.speaker.get_media_album()

    def get_media_duration(self) -> int | None:
        """Get track duration in seconds."""
        return self.speaker.get_media_duration()

    def get_media_position(self) -> int | None:
        """Get current position in seconds."""
        return self.speaker.get_media_position()

    def get_media_position_updated_at(self) -> float | None:
        """Get position update timestamp."""
        return self.speaker.get_media_position_updated_at()

    def get_media_image_url(self) -> str | None:
        """Get media image URL."""
        return self.speaker.get_media_image_url()

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
            self._logger.debug("No media image URL available for %s", self.speaker.name)
            return None, None

        # Check cache first (like LinkPlay integration)
        if image_url == self._media_image_url_cached and self._media_image_bytes:
            self._logger.debug("Returning cached media image for %s", self.speaker.name)
            return self._media_image_bytes, self._media_image_content_type

        try:
            self._logger.debug("Fetching media image from: %s", image_url)

            # Import here to avoid circular imports
            import aiohttp
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            # Use Home Assistant's shared session for efficiency
            session = async_get_clientsession(self.hass)

            # Use the existing SSL context from the WiiM client
            # instead of creating a new one to avoid blocking calls
            ssl_context = self.speaker.coordinator.client._get_ssl_context()

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
                    self._logger.warning(
                        "Failed to fetch media image for %s: HTTP %d", self.speaker.name, response.status
                    )
                    # Clear cache on failure
                    self._media_image_url_cached = None
                    self._media_image_bytes = None
                    self._media_image_content_type = None
                    return None, None

                # Check content length to avoid downloading huge files
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB limit
                    self._logger.warning("Media image too large for %s: %s bytes", self.speaker.name, content_length)
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
                    self._logger.debug("Empty image data for %s", self.speaker.name)
                    # Clear cache on failure
                    self._media_image_url_cached = None
                    self._media_image_bytes = None
                    self._media_image_content_type = None
                    return None, None

                # Additional size check after download
                if len(image_data) > 10 * 1024 * 1024:  # 10MB limit
                    self._logger.warning(
                        "Downloaded image too large for %s: %d bytes", self.speaker.name, len(image_data)
                    )
                    # Clear cache on failure
                    self._media_image_url_cached = None
                    self._media_image_bytes = None
                    self._media_image_content_type = None
                    return None, None

                # Cache the result (like LinkPlay integration)
                self._media_image_url_cached = image_url
                self._media_image_bytes = image_data
                self._media_image_content_type = content_type

                self._logger.debug(
                    "Successfully fetched and cached media image for %s: %d bytes, type: %s",
                    self.speaker.name,
                    len(image_data),
                    content_type,
                )

                return image_data, content_type

        except TimeoutError:
            self._logger.debug("Timeout fetching media image for %s from %s", self.speaker.name, image_url)
            # Clear cache on failure
            self._media_image_url_cached = None
            self._media_image_bytes = None
            self._media_image_content_type = None
            return None, None

        except aiohttp.ClientError as err:
            self._logger.debug("Network error fetching media image for %s: %s", self.speaker.name, err)
            # Clear cache on failure
            self._media_image_url_cached = None
            self._media_image_bytes = None
            self._media_image_content_type = None
            return None, None

        except Exception as err:
            self._logger.warning("Unexpected error fetching media image for %s: %s", self.speaker.name, err)
            # Clear cache on failure
            self._media_image_url_cached = None
            self._media_image_bytes = None
            self._media_image_content_type = None
            return None, None

    # ===== ADVANCED FEATURES =====

    async def play_preset(self, preset: int) -> None:
        """Play preset (1-6).

        Args:
            preset: Preset number 1-6
        """
        try:
            if not 1 <= preset <= 6:
                raise ValueError(f"Preset must be 1-6, got {preset} for {self.speaker.name}")

            self._logger.debug("Playing preset %d for %s", preset, self.speaker.name)

            await self.speaker.coordinator.client.play_preset(preset)

        except Exception as err:
            self._logger.error("Failed to play preset %d: %s", preset, err)
            raise HomeAssistantError(f"Failed to play preset {preset} on {self.speaker.name}: {err}") from err

    async def play_url(self, url: str) -> None:
        """Play URL.

        Args:
            url: Media URL to play
        """
        try:
            self._logger.debug("Playing URL '%s' for %s", url, self.speaker.name)

            await self.speaker.coordinator.client.play_url(url)

        except Exception as err:
            self._logger.error("Failed to play URL '%s': %s", url, err)
            raise HomeAssistantError(f"Failed to play URL: {err}") from err
