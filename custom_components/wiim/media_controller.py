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

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry

from .api import WiiMError
from .const import (
    CONF_VOLUME_STEP,
    DEFAULT_VOLUME_STEP,
    EQ_PRESET_MAP,
    PLAY_MODE_NORMAL,
    PLAY_MODE_REPEAT_ALL,
    PLAY_MODE_REPEAT_ONE,
    PLAY_MODE_SHUFFLE,
    PLAY_MODE_SHUFFLE_REPEAT_ALL,
    SOURCE_MAP,
)

if TYPE_CHECKING:
    from .data import Speaker, get_wiim_data
else:
    from .data import get_wiim_data

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

        self._logger.debug(
            "MediaPlayerController initialized for %s (volume_step=%.2f)",
            speaker.name,
            self._volume_step,
        )

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

            # Implement master/slave logic
            if self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                # Slave should control master volume
                self._logger.debug("Slave speaker redirecting volume to master")
                await self.speaker.coordinator_speaker.coordinator.client.set_volume(volume)
            else:
                # Master or solo speaker controls directly
                await self.speaker.coordinator.client.set_volume(volume)

        except Exception as err:
            self._logger.error("Failed to set volume to %.2f: %s", volume, err)
            raise HomeAssistantError(
                "Failed to set volume to %d%% on %s: %s" % (int(volume * 100), self.speaker.name, err)
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
            raise HomeAssistantError("Failed to set mute: %s" % err) from err

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
            raise HomeAssistantError("Failed to play: %s" % err) from err

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
            raise HomeAssistantError("Failed to pause: %s" % err) from err

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
            raise HomeAssistantError("Failed to stop: %s" % err) from err

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
            raise HomeAssistantError("Failed to skip to next track: %s" % err) from err

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
            raise HomeAssistantError("Failed to skip to previous track: %s" % err) from err

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
            raise HomeAssistantError("Failed to seek: %s" % err) from err

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
            raise HomeAssistantError(
                "Failed to select source '%s' on %s: %s" % (source, self.speaker.name, err)
            ) from err

    async def set_eq_preset(self, preset: str) -> None:
        """Set EQ preset.

        Args:
            preset: EQ preset name
        """
        try:
            self._logger.debug("Setting EQ preset '%s' for %s", preset, self.speaker.name)

            # Map friendly preset names to WiiM preset IDs
            preset_id = EQ_PRESET_MAP.get(preset)
            if preset_id is None:
                raise ValueError(
                    "Unknown EQ preset '%s' on %s. Available presets: %s"
                    % (preset, self.speaker.name, ", ".join(EQ_PRESET_MAP.keys()))
                )

            await self.speaker.coordinator.client.set_eq_preset(preset_id)

        except Exception as err:
            self._logger.error("Failed to set EQ preset '%s': %s", preset, err)
            raise HomeAssistantError(
                "Failed to set EQ preset '%s' on %s: %s" % (preset, self.speaker.name, err)
            ) from err

    async def set_shuffle(self, shuffle: bool) -> None:
        """Set shuffle mode with repeat coordination.

        Args:
            shuffle: True to enable shuffle, False to disable
        """
        try:
            self._logger.debug("Setting shuffle to %s for %s", shuffle, self.speaker.name)

            # Map boolean to WiiM shuffle mode string
            shuffle_mode = "1" if shuffle else "0"
            await self.speaker.coordinator.client.set_shuffle_mode(shuffle_mode)

        except Exception as err:
            self._logger.error("Failed to set shuffle to %s: %s", shuffle, err)
            raise HomeAssistantError("Failed to set shuffle: %s" % err) from err

    async def set_repeat(self, repeat: str) -> None:
        """Set repeat mode (off/one/all).

        Args:
            repeat: Repeat mode - "off", "one", "all"
        """
        try:
            self._logger.debug("Setting repeat to '%s' for %s", repeat, self.speaker.name)

            # Map HA repeat modes to WiiM repeat modes
            if repeat == "off":
                repeat_mode = "0"
            elif repeat == "one":
                repeat_mode = "1"
            elif repeat == "all":
                repeat_mode = "2"
            else:
                raise ValueError(
                    "Unknown repeat mode '%s' on %s. Valid modes: off, one, all" % (repeat, self.speaker.name)
                )

            await self.speaker.coordinator.client.set_repeat_mode(repeat_mode)

        except Exception as err:
            self._logger.error("Failed to set repeat to '%s': %s", repeat, err)
            raise HomeAssistantError("Failed to set repeat: %s" % err) from err

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

            # Map internal source to friendly name
            from .const import SOURCE_MAP

            return SOURCE_MAP.get(internal_source.lower(), internal_source)

        except Exception as err:
            self._logger.error("Failed to get current source: %s", err)
            return None

    def get_shuffle_state(self) -> bool | None:
        """Get shuffle state."""
        return self.speaker.get_shuffle_state()

    def get_repeat_mode(self) -> str | None:
        """Get repeat mode."""
        return self.speaker.get_repeat_mode()

    def get_sound_mode_list(self) -> list[str]:
        """Get available EQ presets."""
        return list(EQ_PRESET_MAP.keys())

    def get_sound_mode(self) -> str | None:
        """Get current EQ preset."""
        return self.speaker.get_sound_mode()

    # ===== GROUP MANAGEMENT =====

    async def join_group(self, group_members: list[str]) -> None:
        """HA native join with WiiM multiroom backend.

        Args:
            group_members: List of entity IDs to group with
        """
        try:
            self._logger.debug("Joining group with members: %s", group_members)

            # Validate and resolve entity IDs to Speaker objects
            speakers = self.speaker.resolve_entity_ids_to_speakers(group_members)
            if not speakers:
                raise ValueError("No valid speakers found in group member list")

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
                "Failed to create group with %s on %s: %s" % (", ".join(group_members), self.speaker.name, err)
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
            raise HomeAssistantError("Failed to remove %s from group: %s" % (self.speaker.name, err)) from err

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
                # This speaker is the leader - find our entity ID
                data = get_wiim_data(self.hass)
                for entity_id, speaker in data.entity_id_mappings.items():
                    if speaker is self.speaker:
                        return entity_id
            elif self.speaker.role == "slave" and self.speaker.coordinator_speaker:
                # Find the master's entity ID
                data = get_wiim_data(self.hass)
                for entity_id, speaker in data.entity_id_mappings.items():
                    if speaker is self.speaker.coordinator_speaker:
                        return entity_id
            # Solo speakers have no leader
            return None
        except Exception as err:
            self._logger.error("Failed to get group leader: %s", err)
            return None

    # ===== POWER CONTROL =====

    async def turn_on(self) -> None:
        """Turn device on."""
        try:
            self._logger.debug("Turning on %s", self.speaker.name)

            await self.speaker.coordinator.client.set_power(True)

        except Exception as err:
            self._logger.error("Failed to turn on device: %s", err)
            raise HomeAssistantError("Failed to turn on: %s" % err) from err

    async def turn_off(self) -> None:
        """Turn device off."""
        try:
            self._logger.debug("Turning off %s", self.speaker.name)

            await self.speaker.coordinator.client.set_power(False)

        except Exception as err:
            self._logger.error("Failed to turn off device: %s", err)
            raise HomeAssistantError("Failed to turn off: %s" % err) from err

    async def toggle_power(self) -> None:
        """Toggle power state."""
        try:
            self._logger.debug("Toggling power for %s", self.speaker.name)

            await self.speaker.coordinator.client.toggle_power()

        except Exception as err:
            self._logger.error("Failed to toggle power: %s", err)
            raise HomeAssistantError("Failed to toggle power: %s" % err) from err

    def is_powered_on(self) -> bool:
        """Get power state."""
        try:
            # Check if we have recent coordinator data (indicates device is responding)
            if not self.speaker.coordinator.data:
                return False

            # Check if coordinator was successful recently
            if not self.speaker.coordinator.last_update_success:
                return False

            # Check for explicit power status in data
            status = self.speaker.coordinator.data.get("status", {})
            power_state = status.get("power") or status.get("power_state")

            if power_state is not None:
                # Handle various power state formats
                if isinstance(power_state, bool):
                    return power_state
                if isinstance(power_state, str):
                    return power_state.lower() in ("1", "on", "true", "yes", "power_on")
                if isinstance(power_state, int):
                    return power_state != 0

            # If no explicit power state, assume device is on if we have data
            return True

        except Exception as err:
            self._logger.debug("Failed to determine power state: %s", err)
            return False

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

    # ===== ADVANCED FEATURES =====

    async def play_preset(self, preset: int) -> None:
        """Play preset (1-6).

        Args:
            preset: Preset number 1-6
        """
        try:
            if not 1 <= preset <= 6:
                raise ValueError("Preset must be 1-6, got %d for %s" % (preset, self.speaker.name))

            self._logger.debug("Playing preset %d for %s", preset, self.speaker.name)

            await self.speaker.coordinator.client.play_preset(preset)

        except Exception as err:
            self._logger.error("Failed to play preset %d: %s", preset, err)
            raise HomeAssistantError("Failed to play preset %d on %s: %s" % (preset, self.speaker.name, err)) from err

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
            raise HomeAssistantError("Failed to play URL: %s" % err) from err

    async def browse_media(self, media_content_type=None, media_content_id=None):
        """Browse media for presets.

        Returns:
            BrowseMedia object for HA media browser
        """
        try:
            from homeassistant.components.media_player.browse_media import (
                BrowseMedia,
                MediaClass,
                MediaType,
            )

            # Root level - show preset category
            if media_content_id is None:
                return BrowseMedia(
                    title="WiiM Media",
                    media_class=MediaClass.DIRECTORY,
                    media_content_id="wiim_root",
                    media_content_type="wiim",
                    can_play=False,
                    can_expand=True,
                    children=[
                        BrowseMedia(
                            title="Presets",
                            media_class=MediaClass.DIRECTORY,
                            media_content_id="wiim_presets",
                            media_content_type="wiim_presets",
                            can_play=False,
                            can_expand=True,
                        )
                    ],
                )

            # Preset level - show individual presets
            elif media_content_id == "wiim_presets":
                presets = []
                for i in range(1, 7):  # Presets 1-6
                    presets.append(
                        BrowseMedia(
                            title=f"Preset {i}",
                            media_class=MediaClass.MUSIC,
                            media_content_id=f"wiim_preset_{i}",
                            media_content_type="wiim_preset",
                            can_play=True,
                            can_expand=False,
                        )
                    )

                return BrowseMedia(
                    title="WiiM Presets",
                    media_class=MediaClass.DIRECTORY,
                    media_content_id="wiim_presets",
                    media_content_type="wiim_presets",
                    can_play=False,
                    can_expand=True,
                    children=presets,
                )

            # Individual preset - play it
            elif media_content_id.startswith("wiim_preset_"):
                preset_num = int(media_content_id.split("_")[-1])
                await self.play_preset(preset_num)
                return None

            else:
                self._logger.warning("Unknown media content ID: %s", media_content_id)
                return None

        except Exception as err:
            self._logger.error("Failed to browse media: %s", err)
            return None
