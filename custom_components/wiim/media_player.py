"""WiiM media player platform - minimal integration using pywiim."""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
from collections.abc import Awaitable
from contextlib import suppress
from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_ENQUEUE,
    BrowseError,
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
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from pywiim.exceptions import WiiMError

from .const import DOMAIN
from .data import Speaker, find_speaker_by_uuid, get_speaker_from_config_entry
from .entity import WiimEntity
from .group_media_player import WiiMGroupMediaPlayer
from .logo_data import LOGO_BASE64, LOGO_CONTENT_TYPE

_LOGGER = logging.getLogger(__name__)


def _capitalize_source_name(source: str) -> str:
    """Capitalize source name properly (Amazon, USB, etc.).

    Handles common source names that need special capitalization:
    - amazon -> Amazon
    - usb -> USB
    - bluetooth -> Bluetooth
    - airplay -> AirPlay
    - spotify -> Spotify
    - etc.
    """
    source_lower = source.lower()

    # Special cases for proper capitalization
    special_cases = {
        "amazon": "Amazon",
        "usb": "USB",
        "bluetooth": "Bluetooth",
        "airplay": "AirPlay",
        "spotify": "Spotify",
        "tidal": "Tidal",
        "qobuz": "Qobuz",
        "deezer": "Deezer",
        "pandora": "Pandora",
        "iheartradio": "iHeartRadio",
        "tunein": "TuneIn",
        "chromecast": "Chromecast",
        "dlna": "DLNA",
        "upnp": "UPnP",
        "wifi": "WiFi",
        "coax": "Coax",
        "optical": "Optical",
        "toslink": "TOSLINK",
        "spdif": "S/PDIF",
        "rca": "RCA",
        "aux": "Aux",
        "line": "Line",
        "hdmi": "HDMI",
    }

    # Check for exact match first
    if source_lower in special_cases:
        return special_cases[source_lower]

    # Check for partial matches (e.g., "usb audio" -> "USB Audio")
    for key, value in special_cases.items():
        if source_lower.startswith(key):
            # Replace the matched part with capitalized version
            return value + source[len(key) :].title()

    # Default: title case (first letter of each word capitalized)
    return source.title()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM Media Player platform."""
    speaker = get_speaker_from_config_entry(hass, config_entry)
    # Create both individual media player and virtual group coordinator
    async_add_entities(
        [
            WiiMMediaPlayer(speaker),
            WiiMGroupMediaPlayer(speaker),
        ]
    )


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

    async def _async_call_player(self, description: str, action: Awaitable[Any]) -> None:
        """Execute a Player coroutine and request a refresh."""
        try:
            await action
        except WiiMError as err:
            raise HomeAssistantError(f"{description}: {err}") from err
        await self.coordinator.async_request_refresh()

    async def _ensure_upnp_ready(self) -> None:
        """Ensure UPnP client is available when queue management is requested."""
        if self._has_queue_support():
            return
        await self.coordinator.async_setup_upnp()
        if not self._has_queue_support():
            raise HomeAssistantError(
                "Queue management requires a UPnP client. Ensure the device supports UPnP and try again."
            )

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
        await self._async_call_player("Failed to set volume", self.coordinator.player.set_volume(volume))

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute/unmute volume."""
        await self._async_call_player("Failed to set mute", self.coordinator.player.set_mute(mute))

    # ===== PLAYBACK =====

    async def async_media_play(self) -> None:
        """Start playback."""
        await self._async_call_player("Failed to start playback", self.coordinator.player.play())

    async def async_media_pause(self) -> None:
        """Pause playback."""
        await self._async_call_player("Failed to pause playback", self.coordinator.player.pause())

    async def async_media_stop(self) -> None:
        """Stop playback."""
        await self._async_call_player("Failed to stop playback", self.coordinator.player.stop())

    async def async_media_next_track(self) -> None:
        """Skip to next track."""
        await self._async_call_player("Failed to skip to next track", self.coordinator.player.next_track())

    async def async_media_previous_track(self) -> None:
        """Skip to previous track."""
        await self._async_call_player("Failed to skip to previous track", self.coordinator.player.previous_track())

    async def async_media_seek(self, position: float) -> None:
        """Seek to position."""
        await self._async_call_player("Failed to seek", self.coordinator.player.seek(int(position)))

    # ===== SOURCE =====

    @property
    def source(self) -> str | None:
        """Return current source (properly capitalized for display)."""
        if self.coordinator.data:
            source = self.coordinator.data.get("source")
            if source:
                # Capitalize for display consistency
                return _capitalize_source_name(str(source))
        return None

    @property
    def source_list(self) -> list[str]:
        """Return list of available sources from Player.

        Uses available_sources from pywiim which should filter to only selectable sources.
        """
        if not self.coordinator.data:
            return []

        # Get available_sources from pywiim
        available_sources = self.coordinator.data.get("available_sources")
        if available_sources:
            return [_capitalize_source_name(str(s)) for s in available_sources]

        # Fallback to input_list if available_sources not available
        input_list = self.speaker.input_list
        if input_list:
            return [_capitalize_source_name(str(s)) for s in input_list]

        return []

    async def async_select_source(self, source: str) -> None:
        """Select input source.

        Maps the display name (e.g., "Amazon", "USB") back to the device's
        expected source name (e.g., "amazon", "usb") using available_sources or input_list.
        """
        source_lower = source.lower()
        device_source = None

        # Try available_sources first (smart detection by pywiim)
        if self.coordinator.data:
            available_sources = self.coordinator.data.get("available_sources")
            if available_sources:
                # Create a mapping of lowercase to original
                available_sources_map = {str(s).lower(): str(s) for s in available_sources}
                device_source = available_sources_map.get(source_lower)

        # Fallback to input_list if not found in available_sources
        if device_source is None:
            input_list = self.speaker.input_list
            if input_list:
                # Create a mapping of lowercase to original
                input_list_map = {s.lower(): s for s in input_list}
                device_source = input_list_map.get(source_lower)

        # Final fallback: use lowercase version of display name
        if device_source is None:
            device_source = source_lower
            _LOGGER.warning(
                "Source '%s' not found in available_sources or input_list, using lowercase version: '%s'",
                source,
                device_source,
            )

        try:
            await self.coordinator.player.set_source(device_source)
            await self.coordinator.async_request_refresh()
        except WiiMError as err:
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
        """Return image bytes and content type of current playing media.

        Uses pywiim's fetch_cover_art() method which:
        - Handles SSL certificates for HTTPS URLs automatically
        - Caches images (1 hour TTL, max 10 images per player)
        - Gracefully handles expired URLs
        - More reliable than passing URLs to HA directly
        """
        if not self.coordinator.data:
            # Return logo if no data
            try:
                logo_bytes = base64.b64decode(LOGO_BASE64)
                return logo_bytes, LOGO_CONTENT_TYPE
            except (binascii.Error, ValueError):
                return None, None

        player = self.coordinator.data.get("player")
        if not player:
            # Return logo if no player
            try:
                logo_bytes = base64.b64decode(LOGO_BASE64)
                return logo_bytes, LOGO_CONTENT_TYPE
            except (binascii.Error, ValueError):
                return None, None

        # Use pywiim's fetch_cover_art() - it handles HTTPS/SSL automatically
        result = await player.fetch_cover_art()
        if result:
            return result  # (image_bytes, content_type)

        # Fall back to logo if fetch failed
        try:
            logo_bytes = base64.b64decode(LOGO_BASE64)
            return logo_bytes, LOGO_CONTENT_TYPE
        except (binascii.Error, ValueError):
            return None, None

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Play media from URL or preset with optional queue management."""
        # Handle preset numbers (presets don't support queue management)
        if media_type == "preset":
            preset_num = int(media_id)
            await self._async_call_player("Failed to play preset", self.coordinator.player.play_preset(preset_num))
            return

        # Handle media_source
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(self.hass, media_id, self.entity_id)
            media_id = sourced_media.url
            # Process URL to handle relative paths
            media_id = async_process_play_media_url(self.hass, media_id)

        enqueue: MediaPlayerEnqueue | None = kwargs.get(ATTR_MEDIA_ENQUEUE)
        if enqueue and enqueue != MediaPlayerEnqueue.REPLACE:
            await self._ensure_upnp_ready()
            if enqueue == MediaPlayerEnqueue.ADD:
                await self._async_call_player(
                    "Failed to add media to queue", self.coordinator.player.add_to_queue(media_id)
                )
                return
            if enqueue == MediaPlayerEnqueue.NEXT:
                await self._async_call_player(
                    "Failed to insert media into queue", self.coordinator.player.insert_next(media_id)
                )
                return
            if enqueue == MediaPlayerEnqueue.PLAY:
                await self._async_call_player(
                    "Failed to play media immediately", self.coordinator.player.play_url(media_id)
                )
                return

        await self._async_call_player("Failed to play media", self.coordinator.player.play_url(media_id))

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement media browsing."""
        # Handle media source browsing
        if media_content_id and media_source.is_media_source_id(media_content_id):
            return await media_source.async_browse_media(
                self.hass,
                media_content_id,
                content_filter=lambda item: item.media_content_type.startswith("audio/"),
            )

        # Root level - show Presets directory and media sources
        if media_content_id is None or media_content_id == "":
            # Only show root if we don't have a specific content type
            if not media_content_type or media_content_type == "":
                children: list[BrowseMedia] = [
                    BrowseMedia(
                        title="Presets",
                        media_class=MediaClass.DIRECTORY,
                        media_content_id="",
                        media_content_type="presets",
                        can_play=False,
                        can_expand=True,
                    )
                ]
                # Add Home Assistant media sources
                with suppress(BrowseError):
                    browse = await media_source.async_browse_media(
                        self.hass,
                        None,
                        content_filter=lambda item: item.media_content_type.startswith("audio/"),
                    )
                    # If domain is None, it's an overview of available sources
                    if browse.domain is None and browse.children:
                        children.extend(browse.children)
                    else:
                        children.append(browse)

                # If there's only one child, return it directly (skip root level)
                if len(children) == 1 and children[0].can_expand:
                    return await self.async_browse_media(
                        children[0].media_content_type,
                        children[0].media_content_id,
                    )

                return BrowseMedia(
                    title=self.speaker.name,
                    media_class=MediaClass.DIRECTORY,
                    media_content_id="",
                    media_content_type="",
                    can_play=False,
                    can_expand=True,
                    children=children,
                )

        # Presets directory - show individual presets (1-20)
        if media_content_type == "presets":
            preset_children: list[BrowseMedia] = []
            # Show presets 1-20 (device dependent, but max is 20 per service definition)
            for preset_num in range(1, 21):
                preset_children.append(
                    BrowseMedia(
                        title=f"Preset {preset_num}",
                        media_class=MediaClass.MUSIC,
                        media_content_id=str(preset_num),
                        media_content_type="preset",
                        can_play=True,
                        can_expand=False,
                    )
                )
            return BrowseMedia(
                title="Presets",
                media_class=MediaClass.DIRECTORY,
                media_content_id="",
                media_content_type="presets",
                can_play=False,
                can_expand=True,
                children=preset_children,
            )

        # Unknown content type
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
        await self._async_call_player("Failed to clear playlist", self.coordinator.player.clear_playlist())

    # ===== GROUPING =====

    @property
    def group_members(self) -> list[str] | None:
        """Return list of entity IDs in the current group - using pywiim Player.group."""
        if not self.coordinator.data:
            return None

        player = self.coordinator.data.get("player")
        if not player or not player.group:
            return None

        role = player.role

        # If solo, return None (not in a group)
        if role == "solo":
            return None

        # Get group members from player.group (pywiim provides this)
        # player.group should have members/slaves we can use
        group = player.group
        if not group:
            return None

        # Build list of entity IDs from group members
        entity_registry = er.async_get(self.hass)
        entity_ids = []

        # Include self (master)
        if self.entity_id:
            entity_ids.append(self.entity_id)

        # Get slave UUIDs from player.group (pywiim provides this)
        # Check if group has members/slaves attribute
        group_members = getattr(group, "members", None) or getattr(group, "slaves", None) or []

        for member in group_members:
            # Get UUID from group member (pywiim provides this)
            member_uuid = getattr(member, "uuid", None) or getattr(member, "mac", None)
            if member_uuid:
                # Find entity ID for this member
                entity_id = entity_registry.async_get_entity_id("media_player", DOMAIN, member_uuid)
                if entity_id:
                    entity_ids.append(entity_id)

        return entity_ids if entity_ids else None

    def join_players(self, group_members: list[str]) -> None:
        """Join other players to form a group (sync version - not used)."""
        # This is called by async_join_players in base class, but we override async_join_players
        # so this shouldn't be called. Raise error if it is.
        raise NotImplementedError("Use async_join_players instead")

    async def async_join_players(self, group_members: list[str]) -> None:
        """Join/unjoin players to match the requested group configuration.

        This method handles both adding and removing players from the group by
        comparing the current group state with the requested state.
        """
        entity_registry = er.async_get(self.hass)
        master_player = self.coordinator.player
        if master_player is None:
            raise HomeAssistantError("Master player is not ready")

        # Normalize: ensure self is included in group_members (self is always the master)
        current_entity_id = self.entity_id
        if current_entity_id not in group_members:
            group_members = [current_entity_id] + group_members

        # Get current group members
        current_group = set(self.group_members or [])
        requested_group = set(group_members)

        # Determine which players to add and which to remove
        to_add = requested_group - current_group
        to_remove = current_group - requested_group

        # Remove players that are no longer in the group (deselected in UI)
        # Collect speakers to unjoin
        unjoined_speakers: list[Speaker] = []
        unjoin_tasks = []
        for entity_id in to_remove:
            if entity_id == current_entity_id:
                # Don't unjoin self (master)
                continue

            entity_entry = entity_registry.async_get(entity_id)
            if not entity_entry:
                _LOGGER.warning("Entity %s not found when unjoining from group", entity_id)
                continue

            speaker = find_speaker_by_uuid(self.hass, entity_entry.unique_id)
            if not speaker or not speaker.coordinator.player:
                _LOGGER.warning("Speaker not available for entity %s", entity_id)
                continue

            unjoined_speakers.append(speaker)
            unjoin_tasks.append(speaker.coordinator.player.leave_group())

        # Execute all unjoin operations in parallel
        if unjoin_tasks:
            unjoin_results = await asyncio.gather(*unjoin_tasks, return_exceptions=True)
            for speaker, result in zip(unjoined_speakers, unjoin_results, strict=True):
                if isinstance(result, Exception):
                    _LOGGER.error("Failed to remove %s from group: %s", speaker.name, result)
                else:
                    _LOGGER.debug("Unjoined %s from group", speaker.name)

        # Add players that are newly selected
        # Collect speakers to join
        joined_speakers: list[Speaker] = []
        join_tasks = []
        for entity_id in to_add:
            if entity_id == current_entity_id:
                # Skip self (already the master)
                continue

            entity_entry = entity_registry.async_get(entity_id)
            if not entity_entry:
                _LOGGER.warning("Entity %s not found when joining group", entity_id)
                continue

            speaker = find_speaker_by_uuid(self.hass, entity_entry.unique_id)
            if not speaker or not speaker.coordinator.player:
                _LOGGER.warning("Speaker not available for entity %s", entity_id)
                continue

            joined_speakers.append(speaker)
            join_tasks.append(speaker.coordinator.player.join_group(master_player))

        # Execute all join operations in parallel
        if join_tasks:
            join_results = await asyncio.gather(*join_tasks, return_exceptions=True)
            for speaker, result in zip(joined_speakers, join_results, strict=True):
                if isinstance(result, Exception):
                    raise HomeAssistantError(f"Failed to add {speaker.name} to group: {result}") from result
                _LOGGER.debug("Joined %s to group", speaker.name)

        # Refresh all affected speakers in parallel
        refresh_tasks = [self.coordinator.async_force_multiroom_refresh()]
        for speaker in joined_speakers + unjoined_speakers:
            refresh_tasks.append(speaker.coordinator.async_force_multiroom_refresh())

        if len(refresh_tasks) > 1:  # More than just master
            await asyncio.gather(*refresh_tasks, return_exceptions=True)
        else:
            await self.coordinator.async_force_multiroom_refresh()

    def unjoin_player(self) -> None:
        """Leave the current group (sync version - not used)."""
        # This is called by async_unjoin_player in base class, but we override async_unjoin_player
        # so this shouldn't be called. Raise error if it is.
        raise NotImplementedError("Use async_unjoin_player instead")

    async def async_unjoin_player(self) -> None:
        """Leave the current group."""
        player = self.coordinator.player
        if player is None:
            raise HomeAssistantError("Player is not ready")

        # Check if player is actually in a group before trying to leave
        # Use the same logic as group_members property to determine if in a group
        if not self.coordinator.data:
            raise HomeAssistantError("Player is not in a group")

        player_obj = self.coordinator.data.get("player")
        if not player_obj or not player_obj.group:
            raise HomeAssistantError("Player is not in a group")

        # Check role - if solo, not in a group
        role = getattr(player_obj, "role", None)
        if role == "solo":
            raise HomeAssistantError("Player is not in a group")

        try:
            await player.leave_group()
        except WiiMError as err:
            raise HomeAssistantError(f"Failed to leave group: {err}") from err

        await self.coordinator.async_force_multiroom_refresh()

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
            await self.coordinator.player.set_shuffle(shuffle)
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
            # Use Player API - set_repeat method will be available in pywiim
            await self.coordinator.player.set_repeat(repeat.value)
            await self.coordinator.async_request_refresh()
        except AttributeError as err:
            # Fallback if set_repeat not yet available in pywiim Player
            raise HomeAssistantError(
                f"Repeat mode setting not yet supported. Please update pywiim library: {err}"
            ) from err
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
        """Return list of available sound modes (EQ presets) from pywiim - per HA_INTEGRATION_GUIDE.md."""
        if not self._is_eq_supported():
            return None

        # Use eq_presets from coordinator data (from get_eq_presets()) - per HA_INTEGRATION_GUIDE.md
        if self.coordinator.data:
            eq_presets = self.coordinator.data.get("eq_presets")
            if eq_presets and isinstance(eq_presets, list):
                # Return list of preset names (already strings from pywiim)
                return [str(preset).title() for preset in eq_presets]

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

            await self.coordinator.player.set_eq_preset(sound_mode_normalized)
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
