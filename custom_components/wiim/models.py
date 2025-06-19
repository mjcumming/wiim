"""Typed models for WiiM API payloads (initial subset).

Only the fields currently used by the coordinator/business logic are
included; additional keys can be added incrementally.
"""
from __future__ import annotations

from typing import Literal, Optional, List
from pydantic import BaseModel, Field

__all__ = [
    "DeviceInfo",
    "PlayerStatus",
    "SlaveInfo",
    "MultiroomInfo",
]


class DeviceInfo(BaseModel):
    uuid: str
    name: str = Field(..., alias="DeviceName")
    model: Optional[str] = Field(None, alias="project")
    firmware: Optional[str] = None
    mac: Optional[str] = Field(None, alias="MAC")
    ip: str
    wmrm_version: Optional[str] = None


class PlayerStatus(BaseModel):
    play_state: Literal["play", "pause", "stop", "load"] = Field(..., alias="status")
    volume: int = Field(..., ge=0, le=100, alias="vol")
    mute: bool
    source: Optional[str] = None  # e.g. "spotify"
    position: Optional[int] = Field(None, alias="position")  # seconds
    duration: Optional[int] = Field(None, alias="duration")  # seconds
    title: Optional[str] = Field(None, alias="Title")
    artist: Optional[str] = Field(None, alias="Artist")
    album: Optional[str] = Field(None, alias="Album")


class SlaveInfo(BaseModel):
    uuid: Optional[str] = None
    ip: str
    name: str


class MultiroomInfo(BaseModel):
    role: Literal["master", "slave", "solo"]
    slave_list: List[SlaveInfo] = [] 