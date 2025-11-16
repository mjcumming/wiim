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
                "client_host": speaker.coordinator.player.host,
                "capabilities": async_redact_data(speaker.coordinator._capabilities, TO_REDACT)
                if hasattr(speaker.coordinator, "_capabilities")
                else {},
            }

        # Integration overview
        integration_info = {
            "total_speakers": len(all_speakers),
            "available_speakers": sum(1 for s in all_speakers if s.available),
            "roles": {role: sum(1 for s in all_speakers if s.role == role) for role in ["solo", "master", "slave"]},
            "models": list({s.model for s in all_speakers if s.model}),
            "pywiim_version": _get_pywiim_version(),
        }

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
                "group_members_count": len(speaker.coordinator.data.get("multiroom", {}).get("slave_list", []))
                if speaker.coordinator.data
                else 0,
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
        if coordinator:
            player = coordinator.player
            api_status = {
                "host": player.host,
                "port": player.port,
                "timeout": player.timeout,
                "connection_type": player.connection_type,
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

        # Group information - read directly from coordinator data
        multiroom = speaker.coordinator.data.get("multiroom", {}) if speaker.coordinator.data else {}
        slave_list = multiroom.get("slave_list", [])
        is_coordinator = speaker.role == "master" and len(slave_list) > 0
        group_info = {
            "role": speaker.role,
            "is_group_coordinator": is_coordinator,
            "group_members_count": len(slave_list),
            "group_member_names": [
                slave.get("name", "Unknown") if isinstance(slave, dict) else str(slave) for slave in slave_list
            ],
            "coordinator_name": multiroom.get("master_name") if speaker.role == "slave" else None,
        }

        # Media state - read from coordinator data (Player properties)
        data = speaker.coordinator.data or {}
        media_info = {
            "playback_state": data.get("play_state"),
            "volume_level": data.get("volume_level"),
            "is_muted": data.get("is_muted"),
            "current_source": data.get("source"),
            "media_title": data.get("media_title"),
            "media_artist": data.get("media_artist"),
            "media_album": data.get("media_album"),
            "media_duration": data.get("media_duration"),
            "media_position": data.get("media_position"),
            "media_image_url": data.get("media_image_url"),
            "shuffle_state": data.get("shuffle"),
            "repeat_mode": data.get("repeat"),
            "sound_mode": data.get("eq_preset"),
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
            has_upnp_client = coordinator.upnp_client is not None
            has_player = coordinator.player is not None
            upnp_setup_attempted = getattr(coordinator, "_upnp_setup_attempted", False)

            if has_upnp_client:
                status = "Active"
                status_detail = "UPnP client available (queue management enabled)"
            elif upnp_setup_attempted:
                status = "Not Active"
                status_detail = "UPnP setup attempted but failed (queue management unavailable)"
            else:
                status = "Not Active"
                status_detail = "UPnP setup not attempted (queue management unavailable)"

            upnp_info = {
                "status": status,
                "status_detail": status_detail,
                "has_upnp_client": has_upnp_client,
                "has_player": has_player,
                "upnp_setup_attempted": upnp_setup_attempted,
                "note": "UPnP is used for queue management only. Event subscriptions are not implemented.",
            }

            # Add UPnP client info if available
            if has_upnp_client and coordinator.upnp_client:
                upnp_client = coordinator.upnp_client
                upnp_info["upnp_client"] = {
                    "description_url": getattr(upnp_client, "description_url", None),
                    "host": getattr(upnp_client, "host", None),
                }

        # Model data (from Player and DeviceInfo)
        model_data = {}
        # Build status dict from Player properties (no longer using status_model)
        data = speaker.coordinator.data or {}
        if data:
            status_dict = {
                "play_status": data.get("play_state"),
                "vol": int(data.get("volume_level", 0) * 100) if data.get("volume_level") is not None else None,
                "mute": data.get("is_muted"),
                "source": data.get("source"),
                "position": data.get("media_position"),
                "duration": data.get("media_duration"),
                "Title": data.get("media_title"),
                "Artist": data.get("media_artist"),
                "Album": data.get("media_album"),
                "entity_picture": data.get("media_image_url"),
                "cover_url": data.get("media_image_url"),
                "eq": data.get("eq_preset"),
                "RSSI": data.get("wifi_rssi"),
                "wifi_rssi": data.get("wifi_rssi"),
                "shuffle": data.get("shuffle"),
                "repeat": data.get("repeat"),
            }
            # Remove None values
            status_dict = {k: v for k, v in status_dict.items() if v is not None}
            if status_dict:
                model_data["player_status"] = async_redact_data(status_dict, TO_REDACT)
        if speaker.device_model:
            model_data["device_model"] = async_redact_data(
                speaker.device_model.model_dump(exclude_none=True), TO_REDACT
            )

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
            "raw_coordinator_data": async_redact_data(raw_data, TO_REDACT),
        }

    except Exception as err:
        _LOGGER.exception("Failed to generate device diagnostics")
        return {
            "error": f"Failed to generate device diagnostics: {err}",
            "device_id": device.id,
        }
