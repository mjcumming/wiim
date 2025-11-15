"""WiiM media player platform - minimal integration using pywiim."""

from __future__ import annotations

import base64
import logging
from typing import Any

from homeassistant.components.media_player import (
    ATTR_MEDIA_ENQUEUE,
    BrowseMedia,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    MediaClass,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pywiim.exceptions import WiiMError

from .const import DOMAIN
from .data import Speaker, find_speaker_by_uuid, get_speaker_from_config_entry
from .entity import WiimEntity
from .logo_data import LOGO_BASE64, LOGO_CONTENT_TYPE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM Media Player platform."""
    speaker = get_speaker_from_config_entry(hass, config_entry)
    async_add_entities([WiiMMediaPlayer(speaker)])


class WiiMMediaPlayer(WiimEntity, MediaPlayerEntity):
    """WiiM media player entity - minimal integration using pywiim."""

    def __init__(self, speaker: Speaker) -> None:
        """Initialize the media player."""
        super().__init__(speaker)
        self._attr_unique_id = speaker.uuid
        self._attr_name = None  # Use device name

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.speaker.name

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features supported by WiiM."""
        features = (
            MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.SHUFFLE_SET
            | MediaPlayerEntityFeature.REPEAT_SET
            | MediaPlayerEntityFeature.GROUPING
            | MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.BROWSE_MEDIA
            | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
            | MediaPlayerEntityFeature.CLEAR_PLAYLIST
        )

        # Enable EQ (sound mode) only if device supports it
        if self._is_eq_supported():
            features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE

        # Enable seek if we have duration
        if self.media_duration and self.media_duration > 0:
            features |= MediaPlayerEntityFeature.SEEK

        # Enable queue management if UPnP client is available
        if self._has_queue_support():
            features |= MediaPlayerEntityFeature.MEDIA_ENQUEUE

        return features

    def _is_eq_supported(self) -> bool:
        """Check if device supports EQ - query from pywiim."""
        if hasattr(self.coordinator, "_capabilities") and self.coordinator._capabilities:
            # Check both possible capability keys for compatibility
            return bool(
                self.coordinator._capabilities.get("supports_eq", False)
                or self.coordinator._capabilities.get("eq_supported", False)
            )
        return False

    def _has_queue_support(self) -> bool:
        """Check if queue management is available - query from Player."""
        if not hasattr(self.coordinator, "player") or self.coordinator.player is None:
            return False
        # Check if Player has UPnP client (required for queue management)
        return hasattr(self.coordinator.player, "_upnp_client") and self.coordinator.player._upnp_client is not None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.speaker.available and self.coordinator.last_update_success

    # ===== STATE =====

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state."""
        if not self.available:
            return None

        # Use Player properties from coordinator data
        play_state = self.coordinator.data.get("play_state") if self.coordinator.data else None
        if not play_state:
            return MediaPlayerState.IDLE

        play_state_str = str(play_state).lower()
        if play_state_str in ("play", "playing", "load"):
            return MediaPlayerState.PLAYING
        elif play_state_str == "pause":
            return MediaPlayerState.PAUSED
        else:
            return MediaPlayerState.IDLE

    # ===== VOLUME =====

    @property
    def volume_level(self) -> float | None:
        """Return volume level 0..1 (already converted by Player)."""
        if self.coordinator.data:
            return self.coordinator.data.get("volume_level")
        return None

    @property
    def is_volume_muted(self) -> bool | None:
        """Return True if muted."""
        if self.coordinator.data:
            return self.coordinator.data.get("is_muted")
        return None

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level 0..1."""
        try:
            await self.coordinator.player.set_volume(volume)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(f"Failed to set volume: {err}") from err

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute/unmute volume."""
        try:
            await self.coordinator.player.set_mute(mute)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(f"Failed to set mute: {err}") from err

    # ===== PLAYBACK =====

    async def async_media_play(self) -> None:
        """Start playback."""
        try:
            await self.coordinator.player.play()
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(f"Failed to play: {err}") from err

    async def async_media_pause(self) -> None:
        """Pause playback."""
        try:
            await self.coordinator.player.pause()
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(f"Failed to pause: {err}") from err

    async def async_media_stop(self) -> None:
        """Stop playback."""
        try:
            await self.coordinator.player.stop()
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(f"Failed to stop: {err}") from err

    async def async_media_next_track(self) -> None:
        """Skip to next track."""
        try:
            await self.coordinator.player.next_track()
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(f"Failed to next track: {err}") from err

    async def async_media_previous_track(self) -> None:
        """Skip to previous track."""
        try:
            await self.coordinator.player.previous_track()
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(f"Failed to previous track: {err}") from err

    async def async_media_seek(self, position: float) -> None:
        """Seek to position."""
        try:
            await self.coordinator.player.seek(int(position))
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(f"Failed to seek: {err}") from err

    # ===== SOURCE =====

    @property
    def source(self) -> str | None:
        """Return current source."""
        if self.coordinator.data:
            source = self.coordinator.data.get("source")
            if source:
                return str(source).title()
        return None

    @property
    def source_list(self) -> list[str]:
        """Return list of available sources from Player."""
        # Use input_list from Player (provided by pywiim)
        input_list = self.speaker.input_list
        if not input_list and self.coordinator.data:
            # Fallback: try to get directly from player object
            player = self.coordinator.data.get("player")
            if player and player.device_info and player.device_info.input_list:
                input_list = player.device_info.input_list

        if input_list:
            return [s.title() for s in input_list]
        # Return empty list if pywiim hasn't provided input_list yet
        return []

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        source_lower = source.lower()

        # Check if trying to select WiFi (network connection method, not an input source)
        if source_lower in ("wifi", "ethernet", "network"):
            raise HomeAssistantError(
                f"'{source}' is not a selectable input source. "
                "WiFi/Ethernet are network connection methods, not audio input sources. "
                "Please select a valid input source like Bluetooth, Line In, or Optical."
            )

        try:
            # Normalize source name
            source_normalized = source_lower.replace(" ", "-")
            await self.coordinator.player.client.set_source(source_normalized)
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
            # Check for JSON parsing errors which often indicate invalid source
            error_msg = str(err).lower()
            if "invalid json" in error_msg or "json" in error_msg or "expecting value" in error_msg:
                raise HomeAssistantError(
                    f"Failed to select source '{source}': The device returned an invalid response. "
                    f"This source may not be available or supported on this device. "
                    f"Error: {err}"
                ) from err
            raise HomeAssistantError(f"Failed to select source '{source}': {err}") from err
        except Exception as err:
            raise HomeAssistantError(f"Failed to select source '{source}': {err}") from err

    # ===== MEDIA =====

    @property
    def media_content_type(self) -> MediaType:
        """Return content type."""
        return MediaType.MUSIC

    @property
    def media_title(self) -> str | None:
        """Return media title."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_title")
        return None

    @property
    def media_artist(self) -> str | None:
        """Return media artist."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_artist")
        return None

    @property
    def media_album_name(self) -> str | None:
        """Return media album."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_album")
        return None

    @property
    def media_duration(self) -> int | None:
        """Return media duration."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_duration")
        return None

    @property
    def media_position(self) -> int | None:
        """Return media position."""
        if self.coordinator.data:
            return self.coordinator.data.get("media_position")
        return None

    @property
    def media_image_url(self) -> str | None:
        """Return media image URL from Player."""
        if self.coordinator.data:
            image_url = self.coordinator.data.get("media_image_url")
            if image_url:
                return str(image_url)
        return f"data:{LOGO_CONTENT_TYPE};base64,{LOGO_BASE64}"

    @property
    def media_image_remotely_accessible(self) -> bool:
        """Return True if the image URL is remotely accessible."""
        if self.coordinator.data:
            image_url = self.coordinator.data.get("media_image_url")
            if image_url:
                # Check if it's a remote HTTP/HTTPS URL
                url_str = str(image_url).lower()
                return url_str.startswith(("http://", "https://"))
        # Data URIs are not remotely accessible
        return False

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Return media image bytes from Player."""
        # If there's a real media_image_url, let the base class handle fetching it
        if self.coordinator.data and self.coordinator.data.get("media_image_url"):
            return await super().async_get_media_image()
        # Otherwise, return the logo
        try:
            logo_bytes = base64.b64decode(LOGO_BASE64)
            return logo_bytes, LOGO_CONTENT_TYPE
        except Exception:
            return None, None

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Play media from URL or preset with optional queue management."""
        try:
            # Handle preset numbers (presets don't support queue management)
            if media_type == "preset":
                preset_num = int(media_id)
                await self.coordinator.player.client.play_preset(preset_num)
                await self.coordinator.async_request_refresh()
                return

            # Check for enqueue parameter
            enqueue: MediaPlayerEnqueue | None = kwargs.get(ATTR_MEDIA_ENQUEUE)

            # Use queue management if enqueue is specified and UPnP is available
            if enqueue and enqueue != MediaPlayerEnqueue.REPLACE:
                if not self._has_queue_support():
                    raise HomeAssistantError(
                        "Queue management requires UPnP client. "
                        "Ensure UPnP is properly configured and device supports it."
                    )

                # Ensure UPnP is set up
                if not self.coordinator._upnp_setup_attempted:
                    await self.coordinator.async_setup_upnp()

                if not self._has_queue_support():
                    raise HomeAssistantError("Queue management is not available. UPnP client could not be initialized.")

                # Use Player for queue operations
                if enqueue == MediaPlayerEnqueue.ADD:
                    await self.coordinator.player.add_to_queue(media_id)
                elif enqueue == MediaPlayerEnqueue.NEXT:
                    await self.coordinator.player.insert_next(media_id)
                elif enqueue == MediaPlayerEnqueue.PLAY:
                    # Play immediately (use Player method)
                    await self.coordinator.player.play_url(media_id)
            else:
                # Default: replace current (use Player method)
                await self.coordinator.player.play_url(media_id)

            await self.coordinator.async_request_refresh()
        except HomeAssistantError:
            raise
        except Exception as err:
            raise HomeAssistantError(f"Failed to play media: {err}") from err

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement media browsing."""
        # Basic implementation - can be enhanced later
        return BrowseMedia(
            title=self.speaker.name,
            media_class=MediaClass.DIRECTORY,
            media_content_id="",
            media_content_type="",
            can_play=False,
            can_expand=False,
            children=[],
        )

    async def async_clear_playlist(self) -> None:
        """Clear the current playlist."""
        try:
            await self.coordinator.player.client.clear_playlist()
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(f"Failed to clear playlist: {err}") from err

    # ===== GROUPING =====

    @property
    def group_members(self) -> list[str] | None:
        """Return list of entity IDs in the current group."""
        if not self.coordinator.data:
            return None

        # Get role from player (most up-to-date)
        role = self.speaker.role

        # If solo, return None (not in a group)
        if role == "solo":
            return None

        # Only master should show group members in HA UI
        # Slaves should return None (they're part of the group but don't show it)
        if role != "master":
            return None

        multiroom = self.coordinator.data.get("multiroom", {})
        slave_list = multiroom.get("slave_list", [])

        # Build list of entity IDs
        entity_registry = er.async_get(self.hass)
        entity_ids = []

        # Include self (master)
        if self.entity_id:
            entity_ids.append(self.entity_id)

        # Include all slaves
        for slave in slave_list:
            if isinstance(slave, dict):
                slave_uuid = slave.get("uuid") or slave.get("mac")
            else:
                slave_uuid = str(slave)

            if slave_uuid:
                # Find entity ID for this slave
                entity_id = entity_registry.async_get_entity_id("media_player", DOMAIN, slave_uuid)
                if entity_id:
                    entity_ids.append(entity_id)

        return entity_ids if entity_ids else None

    def join_players(self, group_members: list[str]) -> None:
        """Join other players to form a group (sync version - not used)."""
        # This is called by async_join_players in base class, but we override async_join_players
        # so this shouldn't be called. Raise error if it is.
        raise NotImplementedError("Use async_join_players instead")

    async def async_join_players(self, group_members: list[str]) -> None:
        """Join other players to form a group.

        This device becomes the master, and group_members become slaves.
        """
        try:
            # Resolve entity IDs to speakers
            entity_registry = er.async_get(self.hass)
            speakers_to_join = []

            for entity_id in group_members:
                entity_entry = entity_registry.async_get(entity_id)
                if not entity_entry:
                    _LOGGER.warning("Entity %s not found", entity_id)
                    continue

                speaker = find_speaker_by_uuid(self.hass, entity_entry.unique_id)
                if speaker:
                    speakers_to_join.append(speaker)
                else:
                    _LOGGER.warning("Speaker not found for entity %s", entity_id)

            if not speakers_to_join:
                raise HomeAssistantError("No valid speakers to join")

            _LOGGER.info("Joining %d speakers to group with master %s", len(speakers_to_join), self.speaker.name)

            # Create group - pass through to pywiim
            master_ip = self.speaker.ip_address
            await self.coordinator.player.client.create_group()

            # Join slaves - pass through to pywiim
            for speaker in speakers_to_join:
                _LOGGER.debug("Joining slave %s to master %s", speaker.name, self.speaker.name)
                await speaker.coordinator.player.client.join_slave(master_ip)

            # Force immediate refresh of multiroom state for all affected coordinators
            # This ensures the role and group_members are updated immediately
            await self.coordinator.async_force_multiroom_refresh()
            for speaker in speakers_to_join:
                await speaker.coordinator.async_force_multiroom_refresh()

            # Write state immediately to update UI
            self.async_write_ha_state()
            for speaker in speakers_to_join:
                # Find and update the entity for each speaker
                entity_registry = er.async_get(self.hass)
                entity_id = entity_registry.async_get_entity_id("media_player", DOMAIN, speaker.uuid)
                if entity_id:
                    # Get the entity and write its state
                    entity = self.hass.states.get(entity_id)
                    if entity:
                        # Trigger state update via coordinator listener
                        speaker.coordinator.async_update_listeners()

            # Also trigger a full refresh to ensure all data is up-to-date
            await self.coordinator.async_request_refresh()
            for speaker in speakers_to_join:
                await speaker.coordinator.async_request_refresh()

            _LOGGER.info("Group join completed for %s with %d slaves", self.speaker.name, len(speakers_to_join))

        except Exception as err:
            _LOGGER.error("Failed to join group: %s", err, exc_info=True)
            raise HomeAssistantError(f"Failed to join group: {err}") from err

    def unjoin_player(self) -> None:
        """Leave the current group (sync version - not used)."""
        # This is called by async_unjoin_player in base class, but we override async_unjoin_player
        # so this shouldn't be called. Raise error if it is.
        raise NotImplementedError("Use async_unjoin_player instead")

    async def async_unjoin_player(self) -> None:
        """Leave the current group."""
        try:
            _LOGGER.info("Unjoining %s from group", self.speaker.name)

            # Get master info before unjoining (for refreshing master coordinator)
            # Store current role and group info before leaving
            current_role = self.speaker.role
            master_uuid = None
            slave_uuids = []
            if self.coordinator.data:
                multiroom = self.coordinator.data.get("multiroom", {})
                # If we're a slave, master_uuid will be in multiroom data
                if current_role == "slave":
                    master_uuid = multiroom.get("master_uuid")
                # If we're a master, get all slaves to refresh them
                elif current_role == "master":
                    slave_list = multiroom.get("slave_list", [])
                    # Store slave UUIDs for refreshing after unjoin
                    for slave in slave_list:
                        if isinstance(slave, dict):
                            slave_uuid = slave.get("uuid") or slave.get("mac")
                        else:
                            slave_uuid = str(slave)
                        if slave_uuid:
                            slave_uuids.append(slave_uuid)

            # Leave group - pass through to pywiim
            await self.coordinator.player.client.leave_group()

            # Force immediate refresh of multiroom state
            # This ensures the role is updated immediately
            await self.coordinator.async_force_multiroom_refresh()

            # Write state immediately to update UI
            self.async_write_ha_state()

            # If we were a slave, refresh the master coordinator
            # (the master needs to update its slave_list)
            if master_uuid and master_uuid != self.speaker.uuid:
                master_speaker = find_speaker_by_uuid(self.hass, master_uuid)
                if master_speaker:
                    _LOGGER.debug("Refreshing master %s after slave %s left", master_speaker.name, self.speaker.name)
                    await master_speaker.coordinator.async_force_multiroom_refresh()
                    # Update master entity state
                    entity_registry = er.async_get(self.hass)
                    master_entity_id = entity_registry.async_get_entity_id("media_player", DOMAIN, master_uuid)
                    if master_entity_id:
                        master_speaker.coordinator.async_update_listeners()
                    await master_speaker.coordinator.async_request_refresh()

            # If we were a master, refresh all slave coordinators
            # (they need to update their role from slave to solo)
            if current_role == "master" and slave_uuids:
                for slave_uuid in slave_uuids:
                    slave_speaker = find_speaker_by_uuid(self.hass, slave_uuid)
                    if slave_speaker:
                        _LOGGER.debug(
                            "Refreshing slave %s after master %s left group", slave_speaker.name, self.speaker.name
                        )
                        await slave_speaker.coordinator.async_force_multiroom_refresh()
                        # Update slave entity state
                        entity_registry = er.async_get(self.hass)
                        slave_entity_id = entity_registry.async_get_entity_id("media_player", DOMAIN, slave_uuid)
                        if slave_entity_id:
                            slave_speaker.coordinator.async_update_listeners()
                        await slave_speaker.coordinator.async_request_refresh()

            # Also trigger a full refresh to ensure all data is up-to-date
            await self.coordinator.async_request_refresh()

            _LOGGER.info("Unjoin completed for %s", self.speaker.name)

        except Exception as err:
            _LOGGER.error("Failed to unjoin: %s", err, exc_info=True)
            raise HomeAssistantError(f"Failed to unjoin: {err}") from err

    # ===== SHUFFLE & REPEAT =====

    @property
    def shuffle(self) -> bool | None:
        """Return True if shuffle is enabled."""
        if self.coordinator.data:
            shuffle = self.coordinator.data.get("shuffle")
            if shuffle is not None:
                # Convert string to bool
                shuffle_str = str(shuffle).lower()
                return shuffle_str in ("1", "true", "on", "yes", "shuffle")
        return None

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode - pass through to pywiim."""
        try:
            await self.coordinator.player.client.set_shuffle(shuffle)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(f"Failed to set shuffle: {err}") from err

    @property
    def repeat(self) -> RepeatMode | None:
        """Return current repeat mode."""
        if self.coordinator.data:
            repeat = self.coordinator.data.get("repeat")
            if repeat is not None:
                repeat_str = str(repeat).lower()
                if repeat_str in ("1", "one", "track"):
                    return RepeatMode.ONE
                elif repeat_str in ("all", "playlist"):
                    return RepeatMode.ALL
                else:
                    return RepeatMode.OFF
        return None

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode - pass through to pywiim."""
        try:
            await self.coordinator.player.client.set_repeat(repeat.value)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(f"Failed to set repeat: {err}") from err

    # ===== SOUND MODE (EQ) =====

    @property
    def sound_mode(self) -> str | None:
        """Return current sound mode (EQ preset) from Player."""
        if not self._is_eq_supported():
            return None

        if self.coordinator.data:
            eq_preset = self.coordinator.data.get("eq_preset")
            if eq_preset:
                return str(eq_preset)
        return None

    @property
    def sound_mode_list(self) -> list[str] | None:
        """Return list of available sound modes (EQ presets) from pywiim."""
        if not self._is_eq_supported():
            return None

        # Try to get available presets from eq_info dict (pywiim may provide this)
        available_presets = []
        if self.coordinator.data:
            eq_info = self.coordinator.data.get("eq")
            if isinstance(eq_info, dict):
                # Try to get presets from eq_info dict (pywiim may provide this)
                available_presets = eq_info.get("available_presets", eq_info.get("presets", []))

        # Fallback: try to get from Player if available
        if not available_presets:
            player = self.coordinator.data.get("player") if self.coordinator.data else None
            if player:
                available_presets = getattr(player, "available_eq_presets", None) or []
                if not isinstance(available_presets, list):
                    available_presets = []

        # Return list of preset names (convert to strings and title case for display)
        if available_presets:
            return [str(preset).title() for preset in available_presets]

        # If no presets found, return None (Home Assistant will hide the selector)
        return None

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode (EQ preset) - pass through to pywiim."""
        if not self._is_eq_supported():
            raise HomeAssistantError("EQ is not supported on this device")

        try:
            # Normalize to lowercase (pywiim typically expects lowercase preset names)
            # but first try to match against available presets to get the exact name
            sound_mode_normalized = sound_mode.lower()

            # Try to find exact match in available presets (case-insensitive)
            if self.coordinator.data:
                eq_info = self.coordinator.data.get("eq")
                available_presets = []
                if isinstance(eq_info, dict):
                    available_presets = eq_info.get("available_presets", eq_info.get("presets", []))

                if not available_presets:
                    player = self.coordinator.data.get("player")
                    if player:
                        available_presets = getattr(player, "available_eq_presets", None) or []

                # Find case-insensitive match
                for preset in available_presets:
                    if str(preset).lower() == sound_mode_normalized:
                        sound_mode_normalized = str(preset)  # Use exact preset name from device
                        break

            await self.coordinator.player.client.set_eq_preset(sound_mode_normalized)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(f"Failed to select sound mode: {err}") from err

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "device_model": self.speaker.model,
            "firmware_version": self.speaker.firmware,
            "ip_address": self.speaker.ip_address,
            "mac_address": self.speaker.mac_address,
            "group_role": self.speaker.role,
            "is_group_coordinator": self.speaker.role == "master" and bool(self.group_members),
            "music_assistant_compatible": True,
            "integration_purpose": "individual_speaker_control",
        }

        # Add shuffle state (always include for visibility)
        shuffle_state = self.shuffle
        attrs["shuffle"] = shuffle_state if shuffle_state is not None else False

        # Add repeat state (always include for visibility)
        repeat_state = self.repeat
        if repeat_state is not None:
            attrs["repeat"] = repeat_state.value if hasattr(repeat_state, "value") else str(repeat_state)
        else:
            attrs["repeat"] = "off"

        # Add sound mode (EQ) if supported (always include for visibility)
        sound_mode = self.sound_mode
        attrs["sound_mode"] = sound_mode if sound_mode is not None else "Not Available"
        # Note: sound_mode_list is None as presets come from pywiim/device dynamically

        # Add group members if in a group
        group_members = self.group_members
        if group_members:
            attrs["group_members"] = group_members
            # Determine group state
            if self.speaker.role == "master":
                attrs["group_state"] = "coordinator"
            elif self.speaker.role == "slave":
                attrs["group_state"] = "member"
            else:
                attrs["group_state"] = "solo"
        else:
            attrs["group_state"] = "solo"

        return attrs
