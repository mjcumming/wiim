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
    "uuid",
    "deviceid",
    "device_id",
]


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry (integration overview)."""
    try:
        coordinator = get_coordinator_from_entry(hass, entry)
        if not coordinator:
            return {
                "error": "Coordinator not found for config entry",
                "entry_data": async_redact_data(entry.data, TO_REDACT),
            }

        # Get all coordinators for integration overview
        all_coordinators = get_all_coordinators(hass)
        all_players = [coord.player for coord in all_coordinators if getattr(coord, "player", None)]

        # Role counts
        role_counts = {"solo": 0, "master": 0, "slave": 0}
        for player in all_players:
            if player.is_solo:
                role_counts["solo"] += 1
            elif player.is_master:
                role_counts["master"] += 1
            elif player.is_slave:
                role_counts["slave"] += 1

        player = coordinator.player
        return {
            "pywiim_version": _get_pywiim_version(),
            "integration_overview": {
                "total_devices": len(all_players),
                "available_devices": sum(1 for p in all_players if p.available),
                "roles": role_counts,
                "models": list({p.model for p in all_players if p.model}),
            },
            "this_device": {
                "name": player.name or entry.title or "WiiM Speaker",
                "model": player.model,
                "firmware": player.firmware,
                "role": player.role,
                "available": coordinator.last_update_success,
            },
            "coordinator": {
                "update_interval_seconds": (
                    coordinator.update_interval.total_seconds() if coordinator.update_interval else None
                ),
                "last_update_success": coordinator.last_update_success,
            },
            "entry_data": async_redact_data(entry.data, TO_REDACT),
            "entry_options": async_redact_data(entry.options, TO_REDACT),
        }

    except Exception as err:
        _LOGGER.exception("Failed to generate config entry diagnostics")
        return {
            "error": f"Failed to generate diagnostics: {err}",
            "entry_data": async_redact_data(entry.data, TO_REDACT),
        }


async def async_get_device_diagnostics(hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry) -> dict[str, Any]:
    """Return diagnostics for a device (detailed debug info)."""
    try:
        coordinator = get_coordinator_from_entry(hass, entry)
        if not coordinator:
            return {"error": "Coordinator not found for device"}

        player = coordinator.player

        # =================================================================
        # DEVICE INFO
        # =================================================================
        mac_address = None
        if player.device_info and hasattr(player.device_info, "mac"):
            mac_address = player.device_info.mac

        device_info = {
            "name": player.name or entry.title or "WiiM Speaker",
            "model": player.model,
            "firmware": player.firmware,
            "ip_address": async_redact_data({"ip": player.host}, ["ip"]),
            "mac_address": async_redact_data({"mac": mac_address}, ["mac"]) if mac_address else None,
            "wifi_rssi": player.wifi_rssi,
            "available": coordinator.last_update_success,
        }

        # =================================================================
        # CAPABILITIES (all flags from pywiim)
        # =================================================================
        capabilities = {
            "supports_eq": getattr(player, "supports_eq", None),
            "supports_presets": getattr(player, "supports_presets", None),
            "supports_audio_output": getattr(player, "supports_audio_output", None),
            "supports_queue_browse": getattr(player, "supports_queue_browse", None),
            "supports_queue_add": getattr(player, "supports_queue_add", None),
            "supports_upnp": getattr(player, "supports_upnp", None),
            "supports_alarms": getattr(player, "supports_alarms", None),
            "supports_sleep_timer": getattr(player, "supports_sleep_timer", None),
            "supports_led_control": getattr(player, "supports_led_control", None),
            "supports_firmware_install": getattr(player, "supports_firmware_install", None),
            "supports_enhanced_grouping": getattr(player, "supports_enhanced_grouping", None),
            "supports_next_track": getattr(player, "supports_next_track", None),
            "supports_metadata": getattr(player, "supports_metadata", None),
        }

        # =================================================================
        # AVAILABLE OPTIONS (critical for debugging source/EQ issues)
        # =================================================================
        available_sources = player.available_sources
        eq_presets = getattr(player, "eq_presets", None)
        available_outputs = getattr(player, "available_outputs", None)
        presets = getattr(player, "presets", None)
        input_list = getattr(player, "input_list", None)

        # Build presets list with details
        presets_list = None
        if presets:
            presets_list = []
            for p in presets:
                preset_info = {"key": getattr(p, "key", None), "name": getattr(p, "name", None)}
                # Include URL if available (redacted)
                if hasattr(p, "url") and p.url:
                    preset_info["url"] = "***redacted***"
                presets_list.append(preset_info)

        available_options = {
            # Sources/Inputs
            "available_sources_raw": list(available_sources) if available_sources else None,
            "available_sources_display": ([str(s) for s in available_sources] if available_sources else None),
            "input_list_from_device": input_list,
            # EQ
            "eq_presets": list(eq_presets) if eq_presets else None,
            "current_eq_preset": player.eq_preset,
            # Audio outputs
            "available_outputs": list(available_outputs) if available_outputs else None,
            "current_output": getattr(player, "audio_output", None),
            # User presets
            "presets": presets_list,
            "presets_full_data_available": bool(getattr(player, "presets_full_data", None)),
        }

        # =================================================================
        # MULTIROOM / GROUP INFO
        # =================================================================
        group_info = {
            "role": player.role,
            "is_master": player.is_master,
            "is_slave": player.is_slave,
            "is_solo": player.is_solo,
        }

        if player.group:
            all_players = player.group.all_players or []
            group_info["group_size"] = len(all_players)
            group_info["group_member_names"] = [p.name for p in all_players if p.uuid != getattr(player, "uuid", None)]
            if player.is_slave and player.group.master:
                group_info["master_name"] = player.group.master.name

        # =================================================================
        # PLAYBACK STATE
        # =================================================================
        playback_state = {
            "play_state": player.play_state,
            "is_playing": player.is_playing,
            "is_paused": getattr(player, "is_paused", None),
            "is_buffering": getattr(player, "is_buffering", None),
            "source": player.source,
            "volume_level": player.volume_level,
            "is_muted": player.is_muted,
            "shuffle": player.shuffle,
            "repeat": player.repeat,
        }

        # =================================================================
        # MEDIA INFO
        # =================================================================
        media_info = {
            "title": player.media_title,
            "artist": player.media_artist,
            "album": player.media_album,
            "duration": player.media_duration,
            "position": player.media_position,
            "image_url": player.media_image_url,
        }

        # =================================================================
        # AUDIO QUALITY (from metadata if available)
        # =================================================================
        audio_quality = {
            "sample_rate": getattr(player, "sample_rate", None),
            "bit_depth": getattr(player, "bit_depth", None),
            "bit_rate": getattr(player, "bit_rate", None),
            "audio_quality": getattr(player, "audio_quality", None),
        }

        # =================================================================
        # FIRMWARE UPDATE STATUS
        # =================================================================
        firmware_update = {
            "update_available": getattr(player, "firmware_update_available", None),
            "latest_version": getattr(player, "latest_firmware_version", None),
            "current_version": player.firmware,
            "supports_api_install": getattr(player, "supports_firmware_install", False),
        }

        # =================================================================
        # CONNECTION INFO
        # =================================================================
        connection_info = {
            "host": async_redact_data({"host": player.host}, ["host"]),
            "port": player.port,
            "timeout": player.timeout,
        }

        # Infer connection type
        if player.port == 443:
            connection_info["connection_type"] = "HTTPS"
        elif player.port == 80:
            connection_info["connection_type"] = "HTTP"
        else:
            connection_info["connection_type"] = f"Port {player.port}"

        # UPnP availability
        upnp_client = getattr(player, "_upnp_client", None)
        connection_info["upnp_available"] = upnp_client is not None

        # =================================================================
        # COORDINATOR INFO
        # =================================================================
        coordinator_info = {
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds() if coordinator.update_interval else None
            ),
            "last_update_success": coordinator.last_update_success,
        }

        # =================================================================
        # RAW DEVICE INFO (from pywiim DeviceInfo model)
        # =================================================================
        raw_device_info = None
        if player.device_info:
            try:
                raw_device_info = async_redact_data(
                    player.device_info.model_dump(by_alias=True, exclude_none=True), TO_REDACT
                )
            except Exception:
                raw_device_info = "Failed to serialize device_info"

        return {
            "pywiim_version": _get_pywiim_version(),
            "device_info": device_info,
            "capabilities": capabilities,
            "available_options": available_options,
            "group_info": group_info,
            "playback_state": playback_state,
            "media_info": media_info,
            "audio_quality": audio_quality,
            "firmware_update": firmware_update,
            "connection_info": connection_info,
            "coordinator_info": coordinator_info,
            "raw_device_info": raw_device_info,
        }

    except Exception as err:
        _LOGGER.exception("Failed to generate device diagnostics")
        return {
            "error": f"Failed to generate device diagnostics: {err}",
            "device_id": device.id,
        }
