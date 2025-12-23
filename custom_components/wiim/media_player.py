"""WiiM media player platform - minimal integration using pywiim."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

import voluptuous as vol
from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_ENQUEUE,
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pywiim.exceptions import WiiMError

from .const import CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP, DOMAIN
from .coordinator import WiiMCoordinator
from .entity import WiimEntity
from .group_media_player import WiiMGroupMediaPlayer
from .media_player_base import WiiMMediaPlayerMixin
from .services import register_media_player_services

_LOGGER = logging.getLogger(__name__)


def media_source_filter(item: BrowseMedia) -> bool:
    """Filter media items to include audio and DLNA sources."""
    content_type = item.media_content_type
    # Include audio content types
    if content_type and content_type.startswith("audio/"):
        return True
    # Include DLNA sources (they use MediaType.CHANNEL/CHANNELS)
    if content_type in (MediaType.CHANNEL, MediaType.CHANNELS):
        return True
    return False


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM Media Player platform."""
    from homeassistant.helpers import entity_platform

    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    # Create both individual media player and virtual group coordinator
    async_add_entities(
        [
            WiiMMediaPlayer(coordinator, config_entry),
            WiiMGroupMediaPlayer(coordinator, config_entry),
        ]
    )

    # Register entity services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "play_url",
        {vol.Required("url"): cv.string},
        "async_play_url",
    )
    platform.async_register_entity_service(
        "play_preset",
        {vol.Required("preset"): vol.All(vol.Coerce(int), vol.Range(min=1, max=20))},
        "async_play_preset",
    )
    platform.async_register_entity_service(
        "play_playlist",
        {vol.Required("playlist_url"): cv.string},
        "async_play_playlist",
    )
    platform.async_register_entity_service(
        "set_eq",
        {
            vol.Required("preset"): cv.string,
            vol.Optional("custom_values"): vol.Any(list, dict),
        },
        "async_set_eq",
    )
    platform.async_register_entity_service(
        "play_notification",
        {vol.Required("url"): cv.string},
        "async_play_notification",
    )
    platform.async_register_entity_service(
        "play_queue",
        {vol.Optional("queue_position", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=10000))},
        "async_play_queue",
    )
    platform.async_register_entity_service(
        "remove_from_queue",
        {vol.Optional("queue_position", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=10000))},
        "async_remove_from_queue",
    )
    platform.async_register_entity_service(
        "get_queue",
        schema=None,
        func="async_get_queue",
        supports_response=SupportsResponse.ONLY,
    )

    # Register platform entity services using new EntityServiceDescription pattern
    register_media_player_services()


class WiiMMediaPlayer(WiiMMediaPlayerMixin, WiimEntity, MediaPlayerEntity):
    """WiiM media player entity - minimal integration using pywiim."""

    def __init__(self, coordinator: WiiMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the media player."""
        super().__init__(coordinator, config_entry)
        # Use player's UUID if available (authoritative source), fallback to config entry unique_id or host
        # This handles cases where manually added devices might have IP as unique_id
        player_uuid = getattr(coordinator.player, "uuid", None) or getattr(coordinator.player, "mac", None)
        self._attr_unique_id = player_uuid or config_entry.unique_id or coordinator.player.host
        self._attr_name = None  # Use device name

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.player.name or self._config_entry.title or "WiiM Speaker"

    def _seek_supported(self) -> bool:
        """Check if seeking is supported - query from pywiim Player.

        Delegates to pywiim's supports_seek property, which handles all source-aware
        capability detection internally.
        """
        return self._get_player().supports_seek

    def _update_supported_features(self) -> None:
        """Update supported features based on current state (LinkPlay pattern)."""
        # Check if player is a slave in a multiroom group
        is_slave = self._get_player().is_slave

        # Base features available to all players (including slaves)
        # Volume is device-specific, playback commands route to master automatically
        features = (
            MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
        )

        # Features only available to non-slaves (master or solo players)
        # These don't make sense for slaves: source selection, media initiation, browsing
        if not is_slave:
            features |= (
                MediaPlayerEntityFeature.SELECT_SOURCE
                | MediaPlayerEntityFeature.PLAY_MEDIA
                | MediaPlayerEntityFeature.BROWSE_MEDIA
                | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
                | MediaPlayerEntityFeature.CLEAR_PLAYLIST
            )

        # Track controls work for slaves - pywiim routes commands to master automatically
        if self._next_track_supported():
            features |= MediaPlayerEntityFeature.NEXT_TRACK
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK

        # Always include grouping feature so players appear in join dialog
        # Slaves can be joined by masters, but cannot initiate joins themselves
        # The role check is enforced in async_join_players() to prevent slaves from initiating joins
        features |= MediaPlayerEntityFeature.GROUPING

        # Shuffle/repeat - pywiim handles source-aware capability detection and routes
        # commands to master automatically for slaves
        if self._shuffle_supported():
            features |= MediaPlayerEntityFeature.SHUFFLE_SET
        if self._repeat_supported():
            features |= MediaPlayerEntityFeature.REPEAT_SET

        # EQ is device-specific - each speaker has its own EQ settings
        if self._is_eq_supported():
            features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE

        # Seek works for slaves - pywiim routes commands to master automatically
        if self._seek_supported():
            features |= MediaPlayerEntityFeature.SEEK

        # Queue management only for non-slaves (slaves shouldn't modify queue)
        if not is_slave and self._has_queue_support():
            features |= MediaPlayerEntityFeature.MEDIA_ENQUEUE

        self._attr_supported_features = features

    def _is_eq_supported(self) -> bool:
        """Check if device supports EQ - query from pywiim Player.

        pywiim exposes EQ support as a boolean property on the Player class.
        """
        return self._get_player().supports_eq

    def _has_queue_support(self) -> bool:
        """Check if queue management is available - query from Player.

        Uses pywiim's supports_queue_add property to check if items can be added to queue.
        """
        return self._get_player().supports_queue_add

    async def _ensure_upnp_ready(self) -> None:
        """Ensure UPnP client is available when queue management is requested."""
        # Check if UPnP is supported (required for queue management)
        if not self._get_player().supports_upnp:
            raise HomeAssistantError(
                "Queue management not available. The device may not support UPnP or it may not be initialized yet."
            )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    # ===== STATE =====

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state."""
        if self._attr_state is not None:
            return self._attr_state

        player = self._get_player()
        return self._derive_state_from_player(player)

    # ===== VOLUME =====

    @property
    def volume_level(self) -> float | None:
        """Return volume level 0..1 (already converted by Player)."""
        return self._get_player().volume_level

    @property
    def volume_step(self) -> float:
        """Return the step to be used by the volume_up and volume_down services.

        Reads the configured volume step from the config entry options.
        Defaults to 5% (0.05) if not configured.
        """
        volume_step = self._config_entry.options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP)
        return float(volume_step)

    @property
    def is_volume_muted(self) -> bool | None:
        """Return True if muted."""
        return self._get_player().is_muted

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level 0..1."""
        async with self.wiim_command("set volume"):
            await self.coordinator.player.set_volume(volume)
            # State updates automatically via callback - no manual refresh needed

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute/unmute volume."""
        async with self.wiim_command("set mute"):
            await self.coordinator.player.set_mute(mute)
            # State updates automatically via callback - no manual refresh needed

    # ===== PLAYBACK =====

    async def async_media_play(self) -> None:
        """Start playback."""
        async with self.wiim_command("start playback"):
            await self.coordinator.player.play()
            # State updates automatically via callback - no manual refresh needed

    async def async_media_pause(self) -> None:
        """Pause playback."""
        async with self.wiim_command("pause playback"):
            await self.coordinator.player.pause()
            # State updates automatically via callback - no manual refresh needed

    async def async_media_play_pause(self) -> None:
        """Toggle play/pause."""
        async with self.wiim_command("toggle play/pause"):
            await self.coordinator.player.media_play_pause()
            # State updates automatically via callback - no manual refresh needed

    async def async_media_stop(self) -> None:
        """Stop playback.

        For web radio streams, uses pause instead of stop as stop doesn't work reliably
        due to device firmware behavior.
        """
        async with self.wiim_command("stop playback"):
            await self._get_player().stop()
            # State updates automatically via callback - no manual refresh needed

    async def async_media_next_track(self) -> None:
        """Skip to next track."""
        async with self.wiim_command("skip to next track"):
            await self.coordinator.player.next_track()
            # State updates automatically via callback - no manual refresh needed

    async def async_media_previous_track(self) -> None:
        """Skip to previous track."""
        async with self.wiim_command("skip to previous track"):
            await self.coordinator.player.previous_track()
            # State updates automatically via callback - no manual refresh needed

    async def async_media_seek(self, position: float) -> None:
        """Seek to position in seconds."""
        _LOGGER.debug(
            "%s: Seeking to position %s (duration=%s, supported_features has SEEK=%s)",
            self.name,
            position,
            self._attr_media_duration,
            bool(self._attr_supported_features & MediaPlayerEntityFeature.SEEK),
        )
        async with self.wiim_command("seek"):
            await self.coordinator.player.seek(int(position))
            # State updates automatically via callback - no manual refresh needed

    # ===== SOURCE =====

    @property
    def source(self) -> str | None:
        """Return current source (properly capitalized for display).

        Ensures the returned source matches an item in source_list so the dropdown
        can correctly show the selected source. If the current source from pywiim
        doesn't match any selectable source, returns None.
        """
        player = self._get_player()
        if not player or not player.source:
            return None

        current_source = str(player.source)

        # Only consider sources that pywiim says are available/selectable.
        available_sources = player.available_sources
        if available_sources:
            display_sources = [str(s) for s in available_sources]
            if current_source in display_sources:
                return current_source
            # Case-insensitive match for UI friendliness
            current_lower = current_source.lower()
            for s in display_sources:
                if s.lower() == current_lower:
                    return s

        # If current source doesn't match any selectable source, log a warning
        # This might indicate a pywiim issue where source doesn't match available_sources
        _LOGGER.debug(
            "[%s] Current source '%s' from pywiim doesn't match any selectable source in source_list. "
            "This might indicate a pywiim issue. available_sources=%s",
            self.name,
            current_source,
            available_sources,
        )
        # Return None so dropdown doesn't show incorrect selection
        return None

    @property
    def source_list(self) -> list[str]:
        """Return list of available sources from Player.

        Uses available_sources from pywiim which filters to only selectable sources.
        """
        player = self._get_player()
        if player.available_sources:
            return [str(s) for s in player.available_sources]
        _LOGGER.warning(
            "[%s] source_list: No sources available - available_sources=%s", self.name, player.available_sources
        )
        return []

    async def async_select_source(self, source: str) -> None:
        """Select input source.

        Uses pywiim's set_source which handles normalization of Title Case
        and variations back to the API format.
        """
        player = self._get_player()
        available_sources = player.available_sources
        if not available_sources:
            raise HomeAssistantError("No sources available")

        # Validate against the available list (case-insensitive)
        source_lower = source.lower()
        if not any(str(s).lower() == source_lower for s in available_sources):
            raise HomeAssistantError(f"Source '{source}' is not available for this device")

        async with self.wiim_command(f"select source '{source}'"):
            await self.coordinator.player.set_source(source)
            # State updates automatically via callback - no manual refresh needed
            # State updates automatically via callback - no manual refresh needed

    # ===== MEDIA =====

    @property
    def media_content_type(self) -> MediaType:
        """Return content type."""
        return MediaType.MUSIC

    @property
    def media_content_id(self) -> str | None:
        """Return the content ID (URL) of currently playing media.

        This is used by Home Assistant for scene restoration. When a URL is played
        via play_url(), pywiim tracks it and exposes it here.

        Returns the URL if playing URL-based media and in PLAYING or PAUSED state.
        Returns None for other sources (Spotify, Bluetooth, etc.) or when idle.
        """
        # Only return URL if we're in a state where media could be playing
        if self.state not in (MediaPlayerState.PLAYING, MediaPlayerState.PAUSED):
            return None

        # Use pywiim's tracked URL (set when play_url() is called)
        return self._get_metadata_player().media_content_id

    @property
    def media_title(self) -> str | None:
        """Return media title."""
        return self._get_metadata_player().media_title

    @property
    def media_artist(self) -> str | None:
        """Return media artist."""
        return self._get_metadata_player().media_artist

    @property
    def media_album_name(self) -> str | None:
        """Return media album."""
        return self._get_metadata_player().media_album

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_position_from_coordinator()
        super()._handle_coordinator_update()

    # Properties now use _attr values set during coordinator update
    # No mutation in property getters - following LinkPlay pattern

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Play media from URL or preset with optional queue management."""
        # Validate media_id is not empty
        if not media_id:
            raise HomeAssistantError("media_id cannot be empty")

        # Check for announce parameter - uses device's built-in playPromptUrl endpoint
        # The device firmware automatically:
        # - Lowers current playback volume
        # - Plays the notification audio
        # - Restores volume after completion
        # No state management needed - device handles it all
        announce = kwargs.get(ATTR_MEDIA_ANNOUNCE, False)
        if announce:
            # Handle media_source resolution for announcements
            if media_source.is_media_source_id(media_id):
                original_media_id = media_id
                try:
                    sourced_media = await media_source.async_resolve_media(self.hass, media_id, self.entity_id)
                    media_id = sourced_media.url
                    if not media_id:
                        raise HomeAssistantError(f"Media source resolved to empty URL: {original_media_id}")
                    media_id = async_process_play_media_url(self.hass, media_id)
                except Exception as err:
                    _LOGGER.error("Failed to resolve media source for announcement: %s", err, exc_info=True)
                    raise HomeAssistantError(f"Failed to resolve media source: {err}") from err

            # Use device's built-in notification endpoint (playPromptUrl)
            # Device automatically handles volume ducking and restoration
            _LOGGER.debug("[%s] Playing notification via device firmware: %s", self.name, media_id)
            async with self.wiim_command("play notification"):
                await self.coordinator.player.play_notification(media_id)
                # State updates automatically via callback - no manual refresh needed
            return

        # Handle preset numbers (presets don't support queue management)
        if media_type == "preset":
            preset_num = int(media_id)
            async with self.wiim_command("play preset"):
                await self.coordinator.player.play_preset(preset_num)
                # State updates automatically via callback - no manual refresh needed
            return

        # Handle media_source
        if media_source.is_media_source_id(media_id):
            original_media_id = media_id
            _LOGGER.debug("Resolving media source: %s", original_media_id)
            try:
                sourced_media = await media_source.async_resolve_media(self.hass, media_id, self.entity_id)
                _LOGGER.debug(
                    "Resolved media source - url: %s, mime_type: %s", sourced_media.url, sourced_media.mime_type
                )
                media_id = sourced_media.url
                # Validate that we have a valid URL before processing
                if not media_id:
                    _LOGGER.error(
                        "Media source resolved to empty URL. Original media_id: %s, mime_type: %s",
                        original_media_id,
                        sourced_media.mime_type,
                    )
                    raise HomeAssistantError(
                        f"Media source resolved to empty URL for: {original_media_id}. "
                        f"This may indicate the media source is not playable or not properly configured."
                    )
                # Process URL to handle relative paths
                media_id = async_process_play_media_url(self.hass, media_id)
            except Exception as err:
                _LOGGER.error(
                    "Failed to resolve media source %s: %s",
                    original_media_id,
                    err,
                    exc_info=True,
                )
                raise HomeAssistantError(f"Failed to resolve media source: {err}") from err

        enqueue: MediaPlayerEnqueue | None = kwargs.get(ATTR_MEDIA_ENQUEUE)
        if enqueue and enqueue != MediaPlayerEnqueue.REPLACE:
            await self._ensure_upnp_ready()
            if enqueue == MediaPlayerEnqueue.ADD:
                async with self.wiim_command("add media to queue"):
                    await self.coordinator.player.add_to_queue(media_id)
                return
            if enqueue == MediaPlayerEnqueue.NEXT:
                async with self.wiim_command("insert media into queue"):
                    await self.coordinator.player.insert_next(media_id)
                return
            if enqueue == MediaPlayerEnqueue.PLAY:
                async with self.wiim_command("play media immediately"):
                    await self.coordinator.player.play_url(media_id)
                    # State updates automatically via callback - no manual refresh needed
                return

        async with self.wiim_command("play media"):
            await self.coordinator.player.play_url(media_id)
            # State updates automatically via callback - no manual refresh needed

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
                content_filter=media_source_filter,
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
                # Add Home Assistant media sources (including DLNA if configured)
                with suppress(BrowseError):
                    browse = await media_source.async_browse_media(
                        self.hass,
                        None,
                        content_filter=media_source_filter,
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

                device_name = self.player.name or self._config_entry.title or "WiiM Speaker"
                return BrowseMedia(
                    title=device_name,
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
            player = self._get_player()

            # Get preset names from pywiim
            # Only available if presets_full_data is True (WiiM devices, not LinkPlay)
            preset_names: dict[int, str] = {}
            if player.supports_presets and player.presets_full_data and player.presets:
                for preset in player.presets:
                    if isinstance(preset, dict) and "name" in preset:
                        preset_num = preset.get("number")
                        if preset_num and 1 <= int(preset_num) <= 20:
                            preset_names[int(preset_num)] = preset["name"]

            # Show presets 1-20 (device dependent, but max is 20 per service definition)
            for preset_num in range(1, 21):
                # Use actual preset name if available, otherwise fallback to "Preset N"
                preset_title = preset_names.get(preset_num, f"Preset {preset_num}")
                preset_children.append(
                    BrowseMedia(
                        title=preset_title,
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
        device_name = self.player.name or self._config_entry.title or "WiiM Speaker"
        return BrowseMedia(
            title=device_name,
            media_class=MediaClass.DIRECTORY,
            media_content_id="",
            media_content_type="",
            can_play=False,
            can_expand=False,
            children=[],
        )

    async def async_clear_playlist(self) -> None:
        """Clear the current playlist and UPnP queue (if available)."""
        async with self.wiim_command("clear playlist"):
            await self.coordinator.player.clear_playlist()
            if self._get_player().supports_upnp:
                await self.coordinator.player.clear_queue()

    # ===== GROUPING =====

    @property
    def group_members(self) -> list[str] | None:
        """Return list of entity IDs in the current group - using pywiim Player.group.

        For slaves, this ensures the master is always included so Home Assistant's
        join dialog correctly shows the current master as selected (not OFF).
        """
        player = self._get_player()
        # If solo, return None (not in a group)
        if player.is_solo:
            return None

        # Use PyWiim's group object - it already knows all the players
        group = player.group
        if not group:
            return None

        entity_registry = er.async_get(self.hass)
        members: list[str] = []

        # First, try to use group.all_players (populated when player_finder is provided)
        if group.all_players:
            for group_player in group.all_players:
                entity_id = self._entity_id_from_player(group_player, entity_registry)
                if entity_id and entity_id not in members:
                    members.append(entity_id)

        # Ensure master is always included for slaves (critical for join dialog to show correct state)
        # This handles cases where all_players might be empty or incomplete
        if player.is_slave and group.master:
            master_entity_id = self._entity_id_from_player(group.master, entity_registry)
            if master_entity_id and master_entity_id not in members:
                members.append(master_entity_id)
            elif not master_entity_id:
                _LOGGER.warning(
                    "[%s] Failed to resolve master entity ID. Master name: %s, Master UUID: %s, Master host: %s",
                    self.name,
                    getattr(group.master, "name", None),
                    getattr(group.master, "uuid", None),
                    getattr(group.master, "host", None),
                )

        # Ensure self is always included
        self_entity_id = self.entity_id
        if self_entity_id and self_entity_id not in members:
            members.append(self_entity_id)

        result = members if members else None
        if player.is_slave:
            _LOGGER.debug(
                "[%s] group_members for slave: %s (all_players=%s, master=%s, self=%s)",
                self.name,
                result,
                bool(group.all_players),
                bool(group.master),
                self.entity_id,
            )
        return result

    def _get_metadata_player(self):
        """Return the player that should be used for metadata display."""
        player = self._get_player()
        # Slaves should use master's metadata - PyWiim's group.master has it
        if player.is_slave and player.group:
            master = getattr(player.group, "master", None)
            if master:
                return master
        return player

    @staticmethod
    def _entity_id_from_player(player_obj: Any, entity_registry: er.EntityRegistry) -> str | None:
        """Resolve entity_id for a pywiim Player object.

        Tries multiple lookup methods since unique_id might be UUID, MAC, or IP address
        depending on how the config entry was created.
        """
        if not player_obj:
            return None

        # Try UUID first (most common case)
        member_uuid = getattr(player_obj, "uuid", None) or getattr(player_obj, "mac", None)
        if member_uuid:
            entity_id = entity_registry.async_get_entity_id("media_player", DOMAIN, member_uuid)
            if entity_id:
                return entity_id

        # Fallback: try host/IP address (some config entries use IP as unique_id)
        member_host = getattr(player_obj, "host", None)
        if member_host:
            entity_id = entity_registry.async_get_entity_id("media_player", DOMAIN, member_host)
            if entity_id:
                return entity_id

        return None

    def join_players(self, group_members: list[str]) -> None:
        """Join other players to form a group (sync version - not used)."""
        # This is called by async_join_players in base class, but we override async_join_players
        # so this shouldn't be called. Raise error if it is.
        raise NotImplementedError("Use async_join_players instead")

    async def async_join_players(self, group_members: list[str]) -> None:
        """Join/unjoin players to match the requested group configuration.

        Delegates to pywiim to handle all group management - pywiim manages
        state changes, role updates, and group membership automatically.

        Note: pywiim 2.1.26+ automatically detects firmware version and selects
        the appropriate grouping mode (Wi-Fi Direct for Gen1 devices with firmware
        < v4.2.8020, Router mode for newer devices). Audio Pro Gen1 devices
        (A26, C10, C5a) are now supported.
        """
        from .data import get_coordinator_from_entry

        entity_registry = er.async_get(self.hass)
        master_player = self.coordinator.player
        if master_player is None:
            raise HomeAssistantError("Master player is not ready")

        # Normalize: ensure self is included in group_members (self is always the master)
        current_entity_id = self.entity_id
        if current_entity_id not in group_members:
            group_members = [current_entity_id] + group_members

        # Get current group members from master's perspective
        current_group = set(self.group_members or [])
        requested_group = set(group_members)

        # Determine which players to add and which to remove
        # Note: to_add might include players that are already in the group due to timing
        # We'll verify each player's actual state before calling join_group
        to_add = requested_group - current_group
        to_remove = current_group - requested_group

        # Remove players that are no longer in the group (deselected in UI)
        # pywiim handles all state management via callbacks
        unjoin_tasks = []
        for entity_id in to_remove:
            if entity_id == current_entity_id:
                # Don't unjoin self (master)
                continue

            entity_entry = entity_registry.async_get(entity_id)
            if not entity_entry:
                _LOGGER.warning("Entity %s not found when unjoining from group", entity_id)
                continue

            # Look up coordinator by config_entry_id (most reliable method)
            # This avoids issues where entity unique_id (UUID) doesn't match config entry unique_id (IP)
            if not entity_entry.config_entry_id:
                _LOGGER.warning("Entity %s has no config_entry_id", entity_id)
                continue

            config_entry = self.hass.config_entries.async_get_entry(entity_entry.config_entry_id)
            if not config_entry:
                _LOGGER.warning("Config entry not found for entity %s", entity_id)
                continue

            try:
                coordinator = get_coordinator_from_entry(self.hass, config_entry)
            except RuntimeError:
                _LOGGER.warning("Coordinator not available for entity %s", entity_id)
                continue

            if not coordinator.player:
                _LOGGER.warning("Coordinator player not available for entity %s", entity_id)
                continue

            # pywiim handles leaving groups and updating state automatically
            unjoin_tasks.append(coordinator.player.leave_group())

        # Execute all unjoin operations in parallel
        if unjoin_tasks:
            unjoin_results = await asyncio.gather(*unjoin_tasks, return_exceptions=True)
            for result in unjoin_results:
                if isinstance(result, Exception):
                    _LOGGER.error("Failed to remove player from group: %s", result)

        # Add players that are newly selected
        # We check each player's actual state before calling join_group to avoid unnecessary API calls
        # and errors. pywiim should ideally handle "already in group" gracefully, but we check first
        # to be more efficient and avoid the error entirely.
        async def _join_single_player(entity_id: str, coordinator: WiiMCoordinator) -> None:
            """Join a single player to the group.

            Checks player's actual state before calling join_group to avoid unnecessary API calls.
            If player is already in the target group, we skip the call (no-op).
            If player is in a different group, pywiim will handle leaving and rejoining.
            """
            player = coordinator.player

            # Check if player is already in the target group before making API call
            # This avoids unnecessary network traffic and errors
            if player.group and player.group.master == master_player:
                _LOGGER.debug(
                    "Player %s is already in the target group (master: %s), skipping join",
                    player.name or entity_id,
                    master_player.name or master_player.host,
                )
                return

            # Player is not in target group - call join_group
            # pywiim will handle leaving current group if needed
            async with self.wiim_command("join group"):
                await player.join_group(master_player)

        join_tasks = []
        for entity_id in to_add:
            if entity_id == current_entity_id:
                # Skip self (already the master)
                continue

            entity_entry = entity_registry.async_get(entity_id)
            if not entity_entry:
                _LOGGER.warning("Entity %s not found when joining group", entity_id)
                continue

            # Look up coordinator by config_entry_id (most reliable method)
            # This avoids issues where entity unique_id (UUID) doesn't match config entry unique_id (IP)
            if not entity_entry.config_entry_id:
                _LOGGER.warning("Entity %s has no config_entry_id", entity_id)
                continue

            config_entry = self.hass.config_entries.async_get_entry(entity_entry.config_entry_id)
            if not config_entry:
                _LOGGER.warning("Config entry not found for entity %s", entity_id)
                continue

            try:
                coordinator = get_coordinator_from_entry(self.hass, config_entry)
            except RuntimeError:
                _LOGGER.warning("Coordinator not available for entity %s", entity_id)
                continue

            if not coordinator.player:
                _LOGGER.warning("Coordinator player not available for entity %s", entity_id)
                continue

            # pywiim handles joining groups, including slaves leaving their current group
            # and becoming masters if needed - all state updates happen via callbacks
            join_tasks.append(_join_single_player(entity_id, coordinator))

        # Execute all join operations in parallel
        # Use return_exceptions=True to handle individual failures gracefully
        if join_tasks:
            join_results = await asyncio.gather(*join_tasks, return_exceptions=True)
            for result in join_results:
                if isinstance(result, Exception):
                    # Log but don't fail the entire operation - some players may have succeeded
                    _LOGGER.warning("Failed to join player to group: %s", result)

    def unjoin_player(self) -> None:
        """Leave the current group (sync version - not used)."""
        # This is called by async_unjoin_player in base class, but we override async_unjoin_player
        # so this shouldn't be called. Raise error if it is.
        raise NotImplementedError("Use async_unjoin_player instead")

    async def async_unjoin_player(self) -> None:
        """Leave the current group.

        Calls pywiim's leave_group() regardless of player role (master/slave/solo).
        PyWiim handles the complexity of what that means for each role.
        """
        async with self.wiim_command("leave group"):
            await self._get_player().leave_group()

    # ===== SHUFFLE & REPEAT =====

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode - pass through to pywiim."""
        async with self.wiim_command("set shuffle"):
            await self.coordinator.player.set_shuffle(shuffle)
            # State updates automatically via callback - no manual refresh needed

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode - pass through to pywiim."""
        async with self.wiim_command("set repeat"):
            await self.coordinator.player.set_repeat(repeat.value)
            # State updates automatically via callback - no manual refresh needed

    # ===== SOUND MODE (EQ) =====

    @property
    def sound_mode(self) -> str | None:
        """Return current sound mode (EQ preset) from Player."""
        if not self._is_eq_supported():
            return None
        eq_preset = self._get_player().eq_preset
        return str(eq_preset) if eq_preset else None

    @property
    def sound_mode_list(self) -> list[str] | None:
        """Return list of available sound modes (EQ presets) from Player."""
        if not self._is_eq_supported():
            return None
        eq_presets = self._get_player().eq_presets
        return [str(preset) for preset in eq_presets] if eq_presets else None

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode (EQ preset) - pass through to pywiim."""
        if not self._is_eq_supported():
            raise HomeAssistantError("EQ is not supported on this device")

        # pywiim requires lowercase for set_eq_preset() even in 2.1.42+
        # (normalization only applies to reading eq_preset, not setting)
        async with self.wiim_command("select sound mode"):
            await self.coordinator.player.set_eq_preset(sound_mode.lower())
            # State updates automatically via callback - no manual refresh needed

    # ===== SERVICE HANDLERS =====

    async def async_play_url(self, url: str) -> None:
        """Handle play_url service call."""
        await self.async_play_media(MediaType.MUSIC, url)

    async def async_play_preset(self, preset: int) -> None:
        """Handle play_preset service call."""
        await self.async_play_media("preset", str(preset))

    async def async_play_playlist(self, playlist_url: str) -> None:
        """Handle play_playlist service call."""
        await self.async_play_media(MediaType.PLAYLIST, playlist_url)

    async def async_set_eq(self, preset: str, custom_values: list[float] | dict[str, Any] | None = None) -> None:
        """Handle set_eq service call."""
        if not self._is_eq_supported():
            raise HomeAssistantError("EQ is not supported on this device")

        if preset.lower() == "custom":
            if not custom_values:
                raise HomeAssistantError("custom_values is required when preset is 'custom'")
            # Convert dict to list if needed, or use list directly
            if isinstance(custom_values, dict):
                # If dict, extract values in order (assuming keys are band indices)
                eq_list = [custom_values.get(str(i), 0.0) for i in range(10)]
            else:
                # Already a list
                eq_list = custom_values
            # Set custom EQ values (10-band: 31.5Hz to 16kHz)
            async with self.wiim_command("set custom EQ"):
                await self.coordinator.player.set_eq_custom(eq_list)
        else:
            # Set EQ preset
            # pywiim requires lowercase for set_eq_preset() even in 2.1.42+
            # (normalization only applies to reading eq_preset, not setting)
            async with self.wiim_command("set EQ preset"):
                await self.coordinator.player.set_eq_preset(preset.lower())
        # State updates automatically via callback - no manual refresh needed

    async def async_play_notification(self, url: str) -> None:
        """Handle play_notification service call."""
        await self.async_play_media(MediaType.MUSIC, url, announce=True)

    async def async_play_queue(self, queue_position: int = 0) -> None:
        """Handle play_queue service call."""
        if not self._get_player().supports_queue_add:
            raise HomeAssistantError(
                "Queue playback not available. The device may not support UPnP or it may not be initialized yet."
            )
        async with self.wiim_command("play queue"):
            await self.coordinator.player.play_queue(queue_position)
            # State updates automatically via callback - no manual refresh needed

    async def async_remove_from_queue(self, queue_position: int = 0) -> None:
        """Handle remove_from_queue service call."""
        if not self._get_player().supports_queue_add:
            raise HomeAssistantError(
                "Queue management not available. The device may not support UPnP or it may not be initialized yet."
            )
        async with self.wiim_command("remove from queue"):
            await self.coordinator.player.remove_from_queue(queue_position)
            # State updates automatically via callback - no manual refresh needed

    async def async_get_queue(self) -> ServiceResponse:
        """Handle get_queue service call - returns queue contents."""
        # get_queue requires supports_queue_browse (full queue retrieval via ContentDirectory)
        if not self._get_player().supports_queue_browse:
            raise HomeAssistantError(
                "Queue browsing not available. This feature requires UPnP ContentDirectory support (WiiM Amp/Ultra + USB only)."
            )
        async with self.wiim_command("get queue"):
            queue = await self.coordinator.player.get_queue()
            # Return queue items in Home Assistant service response format
            return {"queue": queue}

    # ===== SLEEP TIMER & ALARMS =====

    async def set_sleep_timer(self, sleep_time: int) -> None:
        """Set the sleep timer on the player."""
        async with self.wiim_command("set sleep timer"):
            await self.coordinator.player.set_sleep_timer(sleep_time)

    async def clear_sleep_timer(self) -> None:
        """Clear the sleep timer on the player."""
        async with self.wiim_command("clear sleep timer"):
            await self.coordinator.player.cancel_sleep_timer()

    async def set_alarm(
        self,
        alarm_id: int,
        time: str | None = None,
        trigger: str | None = None,
        operation: str | None = None,
    ) -> None:
        """Set or update an alarm on the player.

        Args:
            alarm_id: Alarm slot ID (0-2)
            time: Alarm time in UTC format (HHMMSS, e.g., "070000" for 7:00 AM)
            trigger: Alarm trigger type (e.g., "daily", "2" for ALARM_TRIGGER_DAILY)
            operation: Alarm operation type (e.g., "playback", "1" for ALARM_OP_PLAYBACK)
        """
        from pywiim import ALARM_OP_PLAYBACK, ALARM_TRIGGER_DAILY

        # Get existing alarm if it exists
        try:
            existing_alarm = await self.coordinator.player.get_alarm(alarm_id)
        except Exception:
            existing_alarm = None

        # Parse trigger - accept string names or numeric values
        trigger_value = None
        if trigger is not None:
            trigger_lower = trigger.lower()
            if trigger_lower == "daily":
                trigger_value = ALARM_TRIGGER_DAILY
            elif trigger.isdigit():
                trigger_value = int(trigger)
            else:
                # Try to find matching constant
                try:
                    from pywiim import ALARM_TRIGGER_ONCE

                    if trigger_lower == "once":
                        trigger_value = ALARM_TRIGGER_ONCE
                except ImportError:
                    pass
                if trigger_value is None:
                    raise HomeAssistantError(f"Unknown trigger type: {trigger}")
        elif existing_alarm:
            # Use existing trigger if not provided (Alarm is a Pydantic model)
            trigger_value = existing_alarm.trigger if existing_alarm.trigger is not None else ALARM_TRIGGER_DAILY
        else:
            # Default to daily if creating new alarm
            trigger_value = ALARM_TRIGGER_DAILY

        # Parse operation - accept string names or numeric values
        operation_value = None
        if operation is not None:
            operation_lower = operation.lower()
            if operation_lower == "playback":
                operation_value = ALARM_OP_PLAYBACK
            elif operation.isdigit():
                operation_value = int(operation)
            else:
                raise HomeAssistantError(f"Unknown operation type: {operation}")
        elif existing_alarm:
            # Use existing operation if not provided (Alarm is a Pydantic model)
            operation_value = existing_alarm.operation if existing_alarm.operation is not None else ALARM_OP_PLAYBACK
        else:
            # Default to playback if creating new alarm
            operation_value = ALARM_OP_PLAYBACK

        # Parse time - convert HH:MM:SS or HHMMSS format to HHMMSS
        time_str = None
        if time is not None:
            # Remove colons if present
            time_str = time.replace(":", "")
            # Validate format (should be 6 digits)
            if not time_str.isdigit() or len(time_str) != 6:
                raise HomeAssistantError(
                    f"Invalid time format: {time}. Expected HH:MM:SS or HHMMSS (e.g., '07:00:00' or '070000')"
                )
        elif existing_alarm:
            # Use existing time if not provided (Alarm is a Pydantic model)
            existing_time = existing_alarm.time
            if existing_time is not None:
                # Convert existing time to string format if needed
                if isinstance(existing_time, str):
                    time_str = existing_time.replace(":", "")
                else:
                    raise HomeAssistantError("Cannot update alarm: time format not supported")
        else:
            raise HomeAssistantError("Time is required when creating a new alarm")

        # Set the alarm using the player object
        # For daily alarms, pass empty strings for day and url parameters
        # (device firmware requires them even though they're optional in the API)
        async with self.wiim_command("set alarm"):
            if trigger_value == ALARM_TRIGGER_DAILY:
                await self.coordinator.player.set_alarm(
                    alarm_id=alarm_id,
                    trigger=trigger_value,
                    operation=operation_value,
                    time=time_str,
                    day="",
                    url="",
                )
            else:
                await self.coordinator.player.set_alarm(
                    alarm_id=alarm_id,
                    trigger=trigger_value,
                    operation=operation_value,
                    time=time_str,
                )

        _LOGGER.debug("Alarm %d set successfully", alarm_id)

    # ===== DEVICE MANAGEMENT =====

    async def async_reboot_device(self) -> None:
        """Reboot the WiiM device."""
        device_name = self.player.name or self._config_entry.title or "WiiM Speaker"
        try:
            await self.coordinator.player.reboot()
            _LOGGER.info("Reboot command sent to %s", device_name)
        except WiiMError as err:
            # Reboot may cause connection issues - this is expected
            _LOGGER.info(
                "Reboot command sent to %s (device may not respond): %s",
                device_name,
                err,
            )

    async def async_sync_time(self) -> None:
        """Synchronize device time with Home Assistant (pywiim v2.1.37+)."""
        async with self.wiim_command("sync time"):
            await self.coordinator.player.sync_time()
            _LOGGER.info("Time sync command sent to %s", self.name)

    # ===== UNOFFICIAL API ACTIONS =====

    async def async_scan_bluetooth(self, duration: int = 5) -> None:
        """Scan for nearby Bluetooth devices.

        WARNING: This uses unofficial API endpoints and may not work on all firmware versions.

        Args:
            duration: Scan duration in seconds (3-10 recommended)
        """
        try:
            async with self.wiim_command("scan for Bluetooth devices"):
                await self.coordinator.player.scan_for_bluetooth_devices(duration=duration)
                _LOGGER.info("Bluetooth scan started on %s (duration: %ds)", self.name, duration)
        except AttributeError as exc:
            raise HomeAssistantError(
                "Bluetooth scanning not available. This may require a newer version of pywiim."
            ) from exc

    async def async_set_channel_balance(self, balance: float) -> None:
        """Adjust left/right channel balance.

        WARNING: This uses unofficial API endpoints and may not work on all firmware versions.

        Args:
            balance: Balance from -1.0 (full left) to 1.0 (full right). 0.0 is center.
        """
        try:
            async with self.wiim_command("set channel balance"):
                await self.coordinator.player.set_channel_balance(balance)
                _LOGGER.debug("Channel balance set to %s on %s", balance, self.name)
        except AttributeError as exc:
            raise HomeAssistantError(
                "Channel balance control not available. This may require a newer version of pywiim."
            ) from exc

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        player = self.player
        mac_address = None
        if player.device_info and hasattr(player.device_info, "mac"):
            mac_address = player.device_info.mac

        attrs = {
            "device_model": player.model or "WiiM Speaker",
            "firmware_version": player.firmware,
            "ip_address": player.host,
            "mac_address": mac_address,
            "group_role": player.role,
            "is_group_coordinator": self._get_player().is_master if self._get_player() else False,
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
        player = self._get_player()
        if group_members:
            attrs["group_members"] = group_members
            # Determine group state
            if player.is_master:
                attrs["group_state"] = "coordinator"
            elif player.is_slave:
                attrs["group_state"] = "member"
            else:
                attrs["group_state"] = "solo"
        else:
            attrs["group_state"] = "solo"

        # Add capability flags for debugging/automations
        attrs["capabilities"] = {
            "eq": player.supports_eq,
            "presets": player.supports_presets,
            "audio_output": player.supports_audio_output,
            "queue_browse": player.supports_queue_browse,
            "queue_add": player.supports_queue_add,
            "alarms": player.supports_alarms,
            "sleep_timer": player.supports_sleep_timer,
            "upnp": player.supports_upnp,
        }

        # Add playback state attributes for debugging/automations
        # These match what _derive_state_from_player uses internally
        attrs["is_playing"] = player.is_playing if hasattr(player, "is_playing") else None
        attrs["is_paused"] = player.is_paused if hasattr(player, "is_paused") else None
        attrs["is_buffering"] = player.is_buffering if hasattr(player, "is_buffering") else None
        attrs["play_state"] = player.play_state if hasattr(player, "play_state") else None

        return attrs
