"""Provide diagnostics for WiiM integration."""

from __future__ import annotations

import logging
from importlib import metadata
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .data import get_all_coordinators, get_coordinator_from_entry

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
        # Get coordinator for this config entry
        coordinator = get_coordinator_from_entry(hass, entry)
        if not coordinator:
            return {
                "error": "Coordinator not found for config entry",
                "entry_data": async_redact_data(entry.data, TO_REDACT),
                "entry_options": async_redact_data(entry.options, TO_REDACT),
            }

        # Get all coordinators for integration overview
        all_coordinators = get_all_coordinators(hass)

        # Coordinator data
        coordinator_data = {
            "update_interval": (coordinator.update_interval.total_seconds() if coordinator.update_interval else None),
            "last_update_success": coordinator.last_update_success,
            "last_update": (
                last_update_time.isoformat()
                if (last_update_time := getattr(coordinator, "last_update_success_time", None))
                else None
            ),
            "data_keys": list(coordinator.data.keys()) if coordinator.data else [],
            "client_host": (getattr(coordinator.player, "host", None) if coordinator.player else None),
            "capabilities": (
                async_redact_data(coordinator._capabilities, TO_REDACT) if hasattr(coordinator, "_capabilities") else {}
            ),
        }

        # Integration overview - use Player properties for role counting
        # Extract all players from coordinators
        all_speakers = []
        for coord in all_coordinators:
            player = getattr(coord, "player", None) or (coord.data.get("player") if coord.data else None)
            if player:
                all_speakers.append(player)

        role_counts = {"solo": 0, "master": 0, "slave": 0}
        for player in all_speakers:
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
        player = coordinator.player
        group_members_count = 0
        if player.is_master and player.group:
            all_players = player.group.all_players or []
            # Subtract 1 to exclude the master itself
            group_members_count = len(all_players) - 1 if all_players else 0

        return {
            "entry_data": async_redact_data(entry.data, TO_REDACT),
            "entry_options": async_redact_data(entry.options, TO_REDACT),
            "integration_info": integration_info,
            "coordinator": coordinator_data,
            "device_basic": {
                "name": player.name or entry.title or "WiiM Speaker",
                "model": player.model or "WiiM Speaker",
                "firmware": player.firmware,
                "role": player.role,
                "available": coordinator.last_update_success,
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
        # Find the coordinator for this device
        coordinator = get_coordinator_from_entry(hass, entry)
        if not coordinator:
            return {"error": "Coordinator not found for device"}

        # Get raw coordinator data
        raw_data = {}
        if coordinator.data:
            raw_data = coordinator.data.copy()

        # Get API client status
        api_status = {}
        if coordinator and coordinator.player:
            player = coordinator.player
            host = player.host
            port = player.port
            timeout = player.timeout

            # Infer connection type from port
            if port == 443:
                connection_type = "HTTPS"
            elif port == 80:
                connection_type = "HTTP"
            else:
                connection_type = f"Port {port}"

            api_status = {
                "host": host,
                "port": port,
                "timeout": timeout,
                "connection_type": connection_type,
            }

        # Device-specific information
        player = coordinator.player
        uuid = entry.unique_id or player.host
        mac_address = None
        if player.device_info and hasattr(player.device_info, "mac"):
            mac_address = player.device_info.mac

        device_info = {
            "device_uuid": uuid,
            "name": player.name or entry.title or "WiiM Speaker",
            "model": player.model or "WiiM Speaker",
            "firmware": player.firmware,
            "role": player.role,
            "available": coordinator.last_update_success,
            "ip_address": async_redact_data({"ip": player.host}, ["ip"]),
            "mac_address": async_redact_data({"mac": mac_address}, ["mac"]) if mac_address else None,
        }

        # Group information - use Player properties
        player_data = coordinator.data.get("player") if coordinator.data else None
        group_info = {
            "role": player.role,
            "is_group_coordinator": False,
            "group_members_count": 0,
            "group_member_names": [],
            "coordinator_name": None,
        }

        if player_data:
            group_info["is_group_coordinator"] = player_data.is_master
            group_info["role"] = player_data.role
            # Note: group.all_players may be empty even if device has slaves
            # Use player.role as source of truth for group state
            if player_data.group:
                all_players = player_data.group.all_players or []
                if all_players:
                    group_info["group_members_count"] = len(all_players) - 1
                    group_info["group_member_names"] = [p.name for p in all_players if p.uuid != player_data.uuid]
                if player_data.is_slave and player_data.group.master:
                    group_info["coordinator_name"] = player_data.group.master.name

        # Media state - read from Player properties directly
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
            "shuffle_state": player.shuffle,
            "repeat_mode": player.repeat,
            "sound_mode": player.eq_preset,
        }

        # Capability diagnostics (prefer pywiim Player properties)
        api_capabilities = {
            "supports_eq": getattr(player, "supports_eq", None),
            "supports_presets": getattr(player, "supports_presets", None),
            "presets_full_data": getattr(player, "presets_full_data", None),
            "supports_audio_output": getattr(player, "supports_audio_output", None),
            "supports_metadata": getattr(player, "supports_metadata", None),
            "supports_alarms": getattr(player, "supports_alarms", None),
            "supports_sleep_timer": getattr(player, "supports_sleep_timer", None),
            "supports_led_control": getattr(player, "supports_led_control", None),
            "supports_enhanced_grouping": getattr(player, "supports_enhanced_grouping", None),
            "supports_firmware_install": getattr(player, "supports_firmware_install", None),
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
        player_data = coordinator.data.get("player") if coordinator.data else None
        if player_data:
            status_dict = {
                "play_status": player_data.play_state,
                "vol": int(player_data.volume_level * 100) if player_data.volume_level is not None else None,
                "mute": player_data.is_muted,
                "source": player_data.source,
                "position": player_data.media_position,
                "duration": player_data.media_duration,
                "Title": player_data.media_title,
                "Artist": player_data.media_artist,
                "Album": player_data.media_album,
                "entity_picture": player_data.media_image_url,
                "cover_url": player_data.media_image_url,
                "eq": player_data.eq_preset,
                "RSSI": player_data.wifi_rssi,
                "wifi_rssi": player_data.wifi_rssi,
                "shuffle": player_data.shuffle,
                "repeat": player_data.repeat,
            }
            # Remove None values
            status_dict = {k: v for k, v in status_dict.items() if v is not None}
            if status_dict:
                model_data["player_status"] = async_redact_data(status_dict, TO_REDACT)
        if player.device_info:
            model_data["device_model"] = async_redact_data(
                player.device_info.model_dump(by_alias=True, exclude_none=True), TO_REDACT
            )

        # Source list diagnostics - helps debug input source issues
        source_diagnostics = {}
        if coordinator and coordinator.player:
            player_for_sources = coordinator.player
            available_sources = player_for_sources.available_sources
            input_list = player_for_sources.input_list
            source_diagnostics["available_sources_from_pywiim"] = list(available_sources) if available_sources else None
            source_diagnostics["input_list_from_device_info"] = input_list

            # Show what the media player would display
            from .utils import capitalize_source_name

            if available_sources:
                source_diagnostics["displayed_source_list"] = [
                    capitalize_source_name(str(s)) for s in available_sources
                ]
            elif input_list:
                source_diagnostics["displayed_source_list"] = [capitalize_source_name(str(s)) for s in input_list]
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
