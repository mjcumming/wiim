"""Provide diagnostics for WiiM integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .data import get_all_speakers, get_speaker_from_config_entry

_LOGGER = logging.getLogger(__name__)

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
                "client_host": speaker.coordinator.client.host,
            }

        # Integration overview
        integration_info = {
            "total_speakers": len(all_speakers),
            "available_speakers": sum(1 for s in all_speakers if s.available),
            "roles": {role: sum(1 for s in all_speakers if s.role == role) for role in ["solo", "master", "slave"]},
            "models": list({s.model for s in all_speakers if s.model}),
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
                "group_members_count": len(speaker.group_members),
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
        if speaker.coordinator and speaker.coordinator.client:
            api_status = {
                "host": speaker.coordinator.client.host,
                "timeout": getattr(speaker.coordinator.client, "timeout", "unknown"),
                "client_type": str(type(speaker.coordinator.client)),
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

        # Group information
        group_info = {
            "role": speaker.role,
            "is_group_coordinator": speaker.is_group_coordinator,
            "group_members_count": len(speaker.group_members),
            "group_member_names": [m.name for m in speaker.group_members],
            "coordinator_name": speaker.coordinator_speaker.name if speaker.coordinator_speaker else None,
        }

        # Media state
        media_info = {
            "playback_state": speaker.get_playback_state(),
            "volume_level": speaker.get_volume_level(),
            "is_muted": speaker.is_volume_muted(),
            "current_source": speaker.get_current_source(),
            "media_title": speaker.get_media_title(),
            "media_artist": speaker.get_media_artist(),
            "media_album": speaker.get_media_album(),
            "media_duration": speaker.get_media_duration(),
            "media_position": speaker.get_media_position(),
            "media_image_url": speaker.get_media_image_url(),
            "shuffle_state": speaker.get_shuffle_state(),
            "repeat_mode": speaker.get_repeat_mode(),
            "sound_mode": speaker.get_sound_mode(),
        }

        # API capability diagnostics (simple flags only)
        api_capabilities = {}
        if speaker.coordinator:
            api_capabilities = {
                "metadata_supported": getattr(speaker.coordinator, "_metadata_supported", None),
                "statusex_supported": getattr(speaker.coordinator, "_statusex_supported", None),
                "eq_supported": getattr(speaker.coordinator, "_eq_supported", None),
                "presets_supported": getattr(speaker.coordinator, "_presets_supported", None),
            }

        # UPnP status diagnostics
        # UPnP is always enabled (Samsung/DLNA pattern) - we always try subscriptions, gracefully fallback to polling
        upnp_info = {}
        if hasattr(speaker, "_upnp_eventer") and speaker._upnp_eventer:
            eventer = speaker._upnp_eventer

            # Check if subscriptions actually exist (have SIDs)
            has_sid_avt = getattr(eventer, "_sid_avt", None) is not None
            has_sid_rcs = getattr(eventer, "_sid_rcs", None) is not None
            has_active_subscriptions = has_sid_avt or has_sid_rcs

            # Subscriptions failed only if eventer exists but has no active subscriptions
            # AND the failure flag is set (indicating setup failed or subscriptions were lost)
            subscription_failed_flag = getattr(speaker, "_subscriptions_failed", False)
            actual_subscription_failed = subscription_failed_flag and not has_active_subscriptions

            # Determine status based on active subscriptions (DLNA DMR pattern - no health checking)
            status = "Active" if has_active_subscriptions else "Not Active"
            status_detail = "Receiving Events" if has_active_subscriptions else "Eventer Running but No Events"

            upnp_info = {
                "status": status,
                "status_detail": status_detail,
                "enabled": True,  # Always enabled - follows Samsung/DLNA pattern
                "subscription_failed": actual_subscription_failed,
                "event_count": getattr(eventer, "_event_count", 0),
                "last_notify": getattr(eventer, "_last_notify_ts", None),
                "subscription_start_time": getattr(eventer, "_subscription_start_time", None),
                "subscription_expires_avt": getattr(eventer, "_sid_avt_expires", None),
                "subscription_expires_rcs": getattr(eventer, "_sid_rcs_expires", None),
                "has_sid_avt": has_sid_avt,
                "has_sid_rcs": has_sid_rcs,
                "retry_count": getattr(eventer, "_retry_count", 0),
            }

            # Add UPnP client info if available
            if hasattr(speaker, "_upnp_client") and speaker._upnp_client:
                upnp_info["upnp_client"] = {
                    "has_dmr_device": hasattr(speaker._upnp_client, "_dmr_device")
                    and speaker._upnp_client._dmr_device is not None,
                    "has_notify_server": hasattr(speaker._upnp_client, "_notify_server")
                    and speaker._upnp_client._notify_server is not None,
                    "description_url": speaker._upnp_client.description_url,
                    "callback_url": getattr(speaker._upnp_client._notify_server, "callback_url", None)
                    if hasattr(speaker._upnp_client, "_notify_server") and speaker._upnp_client._notify_server
                    else None,
                }
        else:
            # No UPnP eventer - either setup never ran or failed completely
            subscription_failed_flag = getattr(speaker, "_subscriptions_failed", False)
            has_upnp_client = hasattr(speaker, "_upnp_client") and speaker._upnp_client is not None

            # Determine status: if subscription_failed is True, setup was attempted but failed
            # If False and no client, setup likely never ran (coordinator error, etc.)
            if subscription_failed_flag and has_upnp_client:
                status_detail = "Subscription Failed (Falling back to HTTP polling)"
            elif subscription_failed_flag and not has_upnp_client:
                status_detail = "Client Creation Failed (Using HTTP polling)"
            elif has_upnp_client:
                status_detail = "Eventer Not Created (Unexpected state)"
            else:
                status_detail = "Not Initialized (Likely disabled)"

            upnp_info = {
                "status": "Not Active",
                "status_detail": status_detail,
                "enabled": True,  # Always enabled - follows Samsung/DLNA pattern
                "subscription_failed": subscription_failed_flag,
                "event_count": 0,
                "last_notify": None,
                "has_upnp_client": has_upnp_client,
                "has_upnp_eventer": False,
                "fallback_mode": "HTTP Polling",
            }

            # Add client info even if eventer failed
            if has_upnp_client:
                upnp_info["upnp_client"] = {
                    "has_dmr_device": hasattr(speaker._upnp_client, "_dmr_device")
                    and speaker._upnp_client._dmr_device is not None,
                    "has_notify_server": hasattr(speaker._upnp_client, "_notify_server")
                    and speaker._upnp_client._notify_server is not None,
                    "description_url": speaker._upnp_client.description_url,
                }

        # Model data (Pydantic models)
        model_data = {}
        if speaker.status_model:
            model_data["status_model"] = async_redact_data(
                speaker.status_model.model_dump(exclude_none=True), TO_REDACT
            )
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
