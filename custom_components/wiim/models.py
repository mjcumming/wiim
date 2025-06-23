"""Typed Pydantic models for WiiM API payloads.

- Only fields currently used by the coordinator/business logic are included.
- Additional keys can be added incrementally as needed.
- Field aliases match the WiiM API payload keys for seamless parsing.
- Models are designed for forward compatibility and robust validation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

__all__ = [
    "DeviceInfo",
    "PlayerStatus",
    "SlaveInfo",
    "MultiroomInfo",
    "TrackMetadata",
    "EQInfo",
    "PollingMetrics",
]


class _WiimBase(BaseModel):
    """Base class with permissive extra handling for future-proofing.

    Allows unknown fields (extra="allow") and supports population by field name or alias.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True, underscore_attrs_are_private=True)


class DeviceInfo(_WiimBase):
    """Subset of *getStatusEx* payload required by the integration.

    Field aliases correspond to WiiM API keys (e.g., 'DeviceName', 'MAC').
    Only a subset of fields is included; extend as needed.
    """

    uuid: str | None = None
    name: str | None = Field(None, alias="DeviceName")
    model: str | None = Field(None, alias="project")
    firmware: str | None = None
    mac: str | None = Field(None, alias="MAC")
    ip: str | None = None

    # Extended attributes referenced elsewhere
    release_date: str | None = Field(None, alias="Release")  # Firmware release date
    hardware: str | None = None  # Hardware revision/model
    wmrm_version: str | None = None  # Wiim multiroom version
    mcu_ver: str | None = None  # MCU firmware version
    dsp_ver: str | None = None  # DSP firmware version
    preset_key: int | None = None  # Preset key index
    group: str | None = None  # Group name or ID
    master_uuid: str | None = None  # UUID of group master
    master_ip: str | None = None  # IP of group master
    version_update: str | None = Field(None, alias="VersionUpdate")  # Available update version
    latest_version: str | None = Field(None, alias="NewVer")  # Latest firmware version


class PlayerStatus(_WiimBase):
    """Subset of *getPlayerStatusEx* payload required by the integration.

    Includes playback state, volume, source, position, metadata, and device details.
    Field aliases correspond to WiiM API keys.
    """

    play_state: Literal["play", "pause", "stop", "load"] | None = Field(
        None, alias="status"
    )
    volume: int | None = Field(None, ge=0, le=100, alias="vol")
    mute: bool | None = Field(None, alias="mute")

    # Source / mode
    source: str | None = None  # e.g. "spotify"
    mode: str | None = Field(None, alias="mode")

    # Position / duration
    position: int | None = Field(None, alias="position")  # seconds
    seek: int | None = None  # Some firmwares use "seek"
    duration: int | None = Field(None, alias="duration")  # seconds

    # Metadata & artwork
    title: str | None = Field(None, alias="Title")
    artist: str | None = Field(None, alias="Artist")
    album: str | None = Field(None, alias="Album")

    # Album / track artwork (populated by coordinator)
    entity_picture: str | None = None  # Standard HA key used by media-player
    cover_url: str | None = None  # Alternative field used elsewhere

    # Misc device / stream details
    eq_preset: str | None = Field(None, alias="eq")
    wifi_rssi: int | None = Field(None, alias="RSSI")
    wifi_channel: int | None = Field(None, alias="WifiChannel")
    loop_mode: str | None = Field(None, alias="loop_mode")
    play_mode: str | None = Field(None, alias="play_mode")
    repeat: str | None = None
    shuffle: str | None = None

    # Internal flags – allow underscore alias via extra="allow"
    _multiroom_mode: bool | None = PrivateAttr(default=None)

    # ---------------- Validators ----------------

    # Normalize source to lowercase for consistency
    @field_validator("source", mode="before")
    @classmethod
    def _normalize_source(cls, v: str | None) -> str | None:  # noqa: D401
        return v.lower() if isinstance(v, str) else v

    # Normalize play_state to lowercase for consistency
    @field_validator("play_state", mode="before")
    @classmethod
    def _normalize_play_state(cls, v: str | None) -> str | None:  # noqa: D401
        return v.lower() if isinstance(v, str) else v


class SlaveInfo(BaseModel):
    """Represents a slave device in a multiroom group."""

    uuid: str | None = None
    ip: str  # IP address of the slave device
    name: str  # Display name of the slave device


class MultiroomInfo(BaseModel):
    """Represents multiroom group information and role."""

    role: Literal["master", "slave", "solo"]
    slave_list: list[SlaveInfo] = []


# ---------------------------------------------------------------------------
# NEW helper models introduced as part of Coordinator Refactor (§2-2)
# ---------------------------------------------------------------------------


class TrackMetadata(_WiimBase):
    """Normalized track metadata returned by coordinator_metadata helper."""

    title: str | None = None
    artist: str | None = None
    album: str | None = None
    entity_picture: str | None = None
    cover_url: str | None = None


class EQInfo(_WiimBase):
    """Represents equalizer state & current preset."""

    eq_enabled: bool | None = None
    eq_preset: str | None = None


class PollingMetrics(BaseModel):
    """Diagnostics about the most recent polling cycle."""

    interval: float  # seconds
    is_playing: bool
    api_capabilities: dict[str, bool | None]
