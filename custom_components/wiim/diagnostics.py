"""Provide diagnostics for WiiM integration."""

from __future__ import annotations

import logging
from importlib import metadata
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .data import get_all_speakers, get_speaker_from_config_entry

_LOGGER = logging.getLogger(__name__)


def _get_pywiim_version() -> str:
    """Get pywiim package version."""
    try:
        return metadata.version("pywiim")
    except metadata.PackageNotFoundError:
        return "unknown"


# Sensitive data to redact from diagnostics
TO_REDACT = [
    "MAC",
    "mac_address",
    "macaddress",
    "ip_address",
    "host",
    "SSID",
    "ssid",
    "bssid",
    "BSSID",
    "wifi_password",
    "password",
    "token",
    "auth",
    "serial",
    "serialnumber",
    "uuid",  # Partial redaction - keep first few chars
    "deviceid",
    "device_id",
]


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    try:
        # Get speaker for this config entry
        speaker = get_speaker_from_config_entry(hass, entry)
        if not speaker:
            return {
                "error": "Speaker not found for config entry",
                "entry_data": async_redact_data(entry.data, TO_REDACT),
                "entry_options": async_redact_data(entry.options, TO_REDACT),
            }

        # Get all speakers for integration overview
        all_speakers = get_all_speakers(hass)

        # Coordinator data
        coordinator_data = {}
        if speaker.coordinator:
            coordinator_data = {
                "update_interval": (
                    speaker.coordinator.update_interval.total_seconds() if speaker.coordinator.update_interval else None
                ),
                "last_update_success": speaker.coordinator.last_update_success,
                "last_update": (
                    last_update_time.isoformat()
                    if (last_update_time := getattr(speaker.coordinator, "last_update_success_time", None))
                    else None
                ),
                "data_keys": list(speaker.coordinator.data.keys()) if speaker.coordinator.data else [],
                "client_host": (
                    getattr(speaker.coordinator.player, "host", None) if speaker.coordinator.player else None
                ),
                "capabilities": (
                    async_redact_data(speaker.coordinator._capabilities, TO_REDACT)
                    if hasattr(speaker.coordinator, "_capabilities")
                    else {}
                ),
            }

        # Integration overview - use Player properties for role counting
        role_counts = {"solo": 0, "master": 0, "slave": 0}
        for s in all_speakers:
            if s.coordinator and s.coordinator.data:
                player = s.coordinator.data.get("player")
                if player:
                    if player.is_solo:
                        role_counts["solo"] += 1
                    elif player.is_master:
                        role_counts["master"] += 1
                    elif player.is_slave:
                        role_counts["slave"] += 1

        integration_info = {
            "total_speakers": len(all_speakers),
            "available_speakers": sum(1 for s in all_speakers if s.available),
            "roles": role_counts,
            "models": list({s.model for s in all_speakers if s.model}),
            "pywiim_version": _get_pywiim_version(),
        }

        # Get player for group_members_count calculation
        player = speaker.coordinator.data.get("player") if speaker.coordinator.data else None
        group_members_count = 0
        if player and player.is_master and getattr(player, "group", None):
            all_players = getattr(player.group, "all_players", [])
            # Subtract 1 to exclude the master itself
            group_members_count = len(all_players) - 1 if all_players else 0

        return {
            "entry_data": async_redact_data(entry.data, TO_REDACT),
            "entry_options": async_redact_data(entry.options, TO_REDACT),
            "integration_info": integration_info,
            "coordinator": coordinator_data,
            "speaker_basic": {
                "name": speaker.name,
                "model": speaker.model,
                "firmware": speaker.firmware,
                "role": speaker.role,
                "available": speaker.available,
                "group_members_count": group_members_count,
            },
        }

    except Exception as err:
        _LOGGER.exception("Failed to generate config entry diagnostics")
        return {
            "error": f"Failed to generate diagnostics: {err}",
            "entry_data": async_redact_data(entry.data, TO_REDACT),
        }


async def async_get_device_diagnostics(hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry) -> dict[str, Any]:
    """Return diagnostics for a device."""
    try:
        # Find the speaker for this device
        speaker = get_speaker_from_config_entry(hass, entry)
        if not speaker:
            return {"error": "Speaker not found for device"}

        # Get raw coordinator data
        raw_data = {}
        if speaker.coordinator and speaker.coordinator.data:
            raw_data = speaker.coordinator.data.copy()

        # Get API client status
        api_status = {}
        coordinator = speaker.coordinator
        if coordinator and coordinator.player:
            player = coordinator.player
            # Safely access player attributes - may be on player or player.client
            host = getattr(player, "host", None)
            if host is None and hasattr(player, "client"):
                host = getattr(player.client, "host", None)

            port = getattr(player, "port", None)
            if port is None and hasattr(player, "client"):
                port = getattr(player.client, "port", None)

            timeout = getattr(player, "timeout", None)
            if timeout is None and hasattr(player, "client"):
                timeout = getattr(player.client, "timeout", None)

            # Infer connection type from port if not available
            connection_type = getattr(player, "connection_type", None)
            if connection_type is None and port is not None:
                # Infer from port: 443 = HTTPS, 80 = HTTP
                if port == 443:
                    connection_type = "HTTPS"
                elif port == 80:
                    connection_type = "HTTP"
                else:
                    connection_type = f"Port {port}"
            elif connection_type is None:
                connection_type = "Unknown"

            api_status = {
                "host": host,
                "port": port,
                "timeout": timeout,
                "connection_type": connection_type,
            }

        # Device-specific information
        device_info = {
            "speaker_uuid": speaker.uuid,
            "name": speaker.name,
            "model": speaker.model,
            "firmware": speaker.firmware,
            "role": speaker.role,
            "available": speaker.available,
            "ip_address": async_redact_data({"ip": speaker.ip_address}, ["ip"]),
            "mac_address": async_redact_data({"mac": speaker.mac_address}, ["mac"]) if speaker.mac_address else None,
        }

        # Group information - use Player properties
        player = speaker.coordinator.data.get("player") if speaker.coordinator.data else None
        group_info = {
            "role": speaker.role,
            "is_group_coordinator": False,
            "group_members_count": 0,
            "group_member_names": [],
            "coordinator_name": None,
        }

        if player:
            group_info["is_group_coordinator"] = player.is_master
            group_info["role"] = getattr(player, "role", "unknown")
            # Note: group.all_players may be empty even if device has slaves
            # Use player.role as source of truth for group state
            if player.group:
                # Try to get member info from group object (may be empty)
                all_players = getattr(player.group, "all_players", [])
                if all_players:
                    group_info["group_members_count"] = len(all_players) - 1
                    group_info["group_member_names"] = [
                        getattr(p, "name", "Unknown")
                        for p in all_players
                        if getattr(p, "uuid", None) != getattr(player, "uuid", None)
                    ]
                if player.is_slave and player.group.master:
                    group_info["coordinator_name"] = getattr(player.group.master, "name", None)

        # Media state - read from Player properties directly
        player = speaker.coordinator.data.get("player") if speaker.coordinator.data else None
        media_info = {}
        if player:
            media_info = {
                "playback_state": player.play_state,
                "volume_level": player.volume_level,
                "is_muted": player.is_muted,
                "current_source": player.source,
                "media_title": player.media_title,
                "media_artist": player.media_artist,
                "media_album": player.media_album,
                "media_duration": player.media_duration,
                "media_position": player.media_position,
                "media_image_url": player.media_image_url,
                "shuffle_state": getattr(player, "shuffle", None),
                "repeat_mode": getattr(player, "repeat", None),
                "sound_mode": getattr(player, "eq_preset", None),
            }

        # API capability diagnostics (from coordinator capabilities)
        api_capabilities = {}
        if coordinator and hasattr(coordinator, "_capabilities"):
            caps = coordinator._capabilities
            api_capabilities = {
                "metadata_supported": caps.get("metadata", None),
                "supports_eq": caps.get("supports_eq", None),
                "supports_audio_output": caps.get("supports_audio_output", None),
                "device_type": caps.get("device_type", None),
            }

        # HTTP Polling Statistics
        # Note: pywiim handles polling internally - we only show coordinator-level info
        http_stats = {}
        if coordinator:
            http_stats = {
                "current_interval_seconds": (
                    coordinator.update_interval.total_seconds() if coordinator.update_interval else None
                ),
                "last_update_success": coordinator.last_update_success,
                "note": "Detailed polling statistics are handled internally by pywiim library",
            }

        # Command Statistics
        # Note: pywiim handles command execution internally - no statistics tracked at coordinator level
        command_stats = {
            "note": "Command statistics are handled internally by pywiim library",
        }

        # UPnP status diagnostics
        # Note: UPnP is used for queue management only, not event subscriptions
        upnp_info = {}
        if coordinator:
            has_player = coordinator.player is not None
            # UPnP client is on the player object, not the coordinator
            has_upnp_client = False
            upnp_client = None
            if has_player:
                upnp_client = getattr(coordinator.player, "_upnp_client", None)
                has_upnp_client = upnp_client is not None

            if has_upnp_client:
                status = "Active"
                status_detail = "UPnP client available (queue management enabled)"
            else:
                status = "Not Active"
                status_detail = "UPnP client not available (queue management unavailable)"

            upnp_info = {
                "status": status,
                "status_detail": status_detail,
                "has_upnp_client": has_upnp_client,
                "has_player": has_player,
                "note": "UPnP is used for queue management only. Event subscriptions are not implemented.",
            }

            # Add UPnP client info if available
            if has_upnp_client and upnp_client:
                upnp_info["upnp_client"] = {
                    "description_url": getattr(upnp_client, "description_url", None),
                    "host": getattr(upnp_client, "host", None),
                }

        # Model data (from Player and DeviceInfo)
        model_data = {}
        # Build status dict from Player properties directly
        player = speaker.coordinator.data.get("player") if speaker.coordinator.data else None
        if player:
            status_dict = {
                "play_status": player.play_state,
                "vol": int(player.volume_level * 100) if player.volume_level is not None else None,
                "mute": player.is_muted,
                "source": player.source,
                "position": player.media_position,
                "duration": player.media_duration,
                "Title": player.media_title,
                "Artist": player.media_artist,
                "Album": player.media_album,
                "entity_picture": player.media_image_url,
                "cover_url": player.media_image_url,
                "eq": getattr(player, "eq_preset", None),
                "RSSI": getattr(player, "wifi_rssi", None),
                "wifi_rssi": getattr(player, "wifi_rssi", None),
                "shuffle": getattr(player, "shuffle", None),
                "repeat": getattr(player, "repeat", None),
            }
            # Remove None values
            status_dict = {k: v for k, v in status_dict.items() if v is not None}
            if status_dict:
                model_data["player_status"] = async_redact_data(status_dict, TO_REDACT)
        if speaker.device_model:
            model_data["device_model"] = async_redact_data(
                speaker.device_model.model_dump(exclude_none=True), TO_REDACT
            )

        # Source list diagnostics - helps debug input source issues
        source_diagnostics = {}
        if coordinator and coordinator.player:
            player = coordinator.player
            # Get available_sources from pywiim Player
            available_sources = getattr(player, "available_sources", None)
            source_diagnostics["available_sources_from_pywiim"] = list(available_sources) if available_sources else None
            # Get input_list from device_info
            input_list = speaker.input_list
            source_diagnostics["input_list_from_device_info"] = input_list
            # Show what the media player would display
            if coordinator.data:
                media_player = coordinator.data.get("player")
                if media_player:
                    # This is what source_list property would return
                    from .media_player import _capitalize_source_name

                    if available_sources:
                        source_diagnostics["displayed_source_list"] = [
                            _capitalize_source_name(str(s)) for s in available_sources
                        ]
                    elif input_list:
                        source_diagnostics["displayed_source_list"] = [
                            _capitalize_source_name(str(s)) for s in input_list
                        ]
                    else:
                        source_diagnostics["displayed_source_list"] = []

        return {
            "device_info": device_info,
            "group_info": group_info,
            "media_info": media_info,
            "api_capabilities": api_capabilities,
            "upnp_status": upnp_info,
            "http_polling_statistics": http_stats,
            "command_statistics": command_stats,
            "api_status": async_redact_data(api_status, TO_REDACT),
            "model_data": model_data,
            "source_list_diagnostics": source_diagnostics,
            "raw_coordinator_data": async_redact_data(raw_data, TO_REDACT),
        }

    except Exception as err:
        _LOGGER.exception("Failed to generate device diagnostics")
        return {
            "error": f"Failed to generate device diagnostics: {err}",
            "device_id": device.id,
        }
