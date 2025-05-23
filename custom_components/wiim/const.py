"""Constants for the WiiM integration.

This module defines all constants used throughout the WiiM integration,
including configuration keys, default values, service names, and API endpoints.

Configuration:
    - Host configuration and connection settings
    - Polling intervals and timeouts
    - Volume control parameters
    - Device-specific settings

Services:
    - Media playback control services
    - Device management services
    - Group control services
    - Diagnostic services

Attributes:
    - Device information attributes
    - Media playback attributes
    - Group management attributes
    - Diagnostic attributes

API Endpoints:
    - Player control endpoints
    - Status and information endpoints
    - Group management endpoints
    - Device management endpoints
"""

from __future__ import annotations

DOMAIN = "wiim"

# Config keys
CONF_HOST = "host"
CONF_POLL_INTERVAL = "poll_interval"
CONF_VOLUME_STEP = "volume_step"

# Defaults
DEFAULT_PORT = 443  # HTTPS
DEFAULT_TIMEOUT = 10  # seconds
DEFAULT_POLL_INTERVAL = 5  # seconds
DEFAULT_VOLUME_STEP = 0.05  # 5%

# Services
SERVICE_PLAY_PRESET = "play_preset"
SERVICE_TOGGLE_POWER = "toggle_power"
SERVICE_PLAY_URL = "play_url"
SERVICE_PLAY_PLAYLIST = "play_playlist"
SERVICE_SET_EQ = "set_eq"

# Attributes
ATTR_PRESET = "preset"
ATTR_GROUP_MEMBERS = "group_members"
ATTR_GROUP_LEADER = "group_leader"
ATTR_FIRMWARE = "firmware"
ATTR_FIXED_VOLUME = "fixed_volume"
ATTR_DEVICE_MODEL = "device_model"
ATTR_DEVICE_NAME = "device_name"
ATTR_DEVICE_ID = "device_id"
ATTR_EQ_PRESET = "eq_preset"
ATTR_EQ_CUSTOM = "eq_custom"
ATTR_PLAY_MODE = "play_mode"
ATTR_REPEAT_MODE = "repeat_mode"
ATTR_SHUFFLE_MODE = "shuffle_mode"
ATTR_SOURCE = "source"
ATTR_MUTE = "mute"
ATTR_WIFI_RSSI = "wifi_rssi"
ATTR_WIFI_CHANNEL = "wifi_channel"
ATTR_GROUP_ROLE = "group_role"
ATTR_IP_ADDRESS = "ip_address"

# Supported features
SUPPORT_WIIM = (
    "play",
    "pause",
    "stop",
    "next_track",
    "previous_track",
    "volume_set",
    "volume_step",
    "volume_mute",
    "select_source",
    "clear_playlist",
    "play_media",
    "media_position",
    "media_position_updated_at",
    "media_duration",
    "media_title",
    "media_artist",
    "media_album_name",
    "media_playlist",
    "shuffle_set",
    "repeat_set",
    "group_members",
)

# WiiM API endpoints
# Player Controls
API_ENDPOINT_STATUS = "/httpapi.asp?command=getStatusEx"
API_ENDPOINT_PLAYER_STATUS = "/httpapi.asp?command=getPlayerStatus"
API_ENDPOINT_PLAY = "/httpapi.asp?command=setPlayerCmd:play"
API_ENDPOINT_PAUSE = "/httpapi.asp?command=setPlayerCmd:pause"
API_ENDPOINT_STOP = "/httpapi.asp?command=setPlayerCmd:stop"
API_ENDPOINT_NEXT = "/httpapi.asp?command=setPlayerCmd:next"
API_ENDPOINT_PREV = "/httpapi.asp?command=setPlayerCmd:prev"
API_ENDPOINT_VOLUME = "/httpapi.asp?command=setPlayerCmd:vol:"
API_ENDPOINT_MUTE = "/httpapi.asp?command=setPlayerCmd:mute:"
API_ENDPOINT_POWER = "/httpapi.asp?command=setPlayerCmd:power:"
API_ENDPOINT_PRESET = "/httpapi.asp?command=MCUKeyShortClick:"

# Playback Control
API_ENDPOINT_REPEAT = "/httpapi.asp?command=setPlayerCmd:repeat:"
API_ENDPOINT_SHUFFLE = "/httpapi.asp?command=setPlayerCmd:shuffle:"
API_ENDPOINT_SEEK = "/httpapi.asp?command=setPlayerCmd:seek:"
API_ENDPOINT_PLAYLIST = "/httpapi.asp?command=setPlayerCmd:playlist:"
API_ENDPOINT_CLEAR_PLAYLIST = "/httpapi.asp?command=setPlayerCmd:clear_playlist"
API_ENDPOINT_PLAY_URL = "/httpapi.asp?command=setPlayerCmd:play:"
API_ENDPOINT_PLAY_M3U = "/httpapi.asp?command=setPlayerCmd:playlist:"
API_ENDPOINT_PLAY_PROMPT_URL = "/httpapi.asp?command=playPromptUrl:"

# Multiroom Control
API_ENDPOINT_GROUP_JOIN = "/httpapi.asp?command=ConnectMasterAp:JoinGroupMaster:eth{ip}:wifi0.0.0.0"
API_ENDPOINT_GROUP_EXIT = "/httpapi.asp?command=multiroom:Ungroup"
API_ENDPOINT_GROUP_CREATE = "/httpapi.asp?command=setMultiroom:Master"
API_ENDPOINT_GROUP_DELETE = "/httpapi.asp?command=multiroom:Ungroup"
API_ENDPOINT_GROUP_SLAVES = "/httpapi.asp?command=multiroom:getSlaveList"
API_ENDPOINT_GROUP_KICK = "/httpapi.asp?command=multiroom:SlaveKickout:"
API_ENDPOINT_GROUP_SLAVE_MUTE = "/httpapi.asp?command=multiroom:SlaveMute:"
API_ENDPOINT_GROUP_SLAVE_VOLUME = "/httpapi.asp?command=multiroom:SlaveVolume:"

# EQ Controls
API_ENDPOINT_EQ_PRESET = "/httpapi.asp?command=EQLoad:"
API_ENDPOINT_EQ_CUSTOM = "/httpapi.asp?command=setEQ:custom:"
API_ENDPOINT_EQ_GET = "/httpapi.asp?command=getEQ"
API_ENDPOINT_EQ_ON = "/httpapi.asp?command=EQOn"
API_ENDPOINT_EQ_OFF = "/httpapi.asp?command=EQOff"
API_ENDPOINT_EQ_STATUS = "/httpapi.asp?command=EQGetStat"
API_ENDPOINT_EQ_LIST = "/httpapi.asp?command=EQGetList"

# Source Selection
API_ENDPOINT_SOURCE = "/httpapi.asp?command=setPlayerCmd:switchmode:"
API_ENDPOINT_SOURCES = "/httpapi.asp?command=getPlayerCmd:switchmode"

# Device Info
API_ENDPOINT_DEVICE_INFO = "/httpapi.asp?command=getDeviceInfo"
API_ENDPOINT_FIRMWARE = "/httpapi.asp?command=getFirmwareVersion"
API_ENDPOINT_MAC = "/httpapi.asp?command=getMAC"

# LED Control
API_ENDPOINT_LED = "/httpapi.asp?command=setLED:"
API_ENDPOINT_LED_BRIGHTNESS = "/httpapi.asp?command=setLEDBrightness:"

# Play Modes
PLAY_MODE_NORMAL = "normal"
PLAY_MODE_REPEAT_ALL = "repeat_all"
PLAY_MODE_REPEAT_ONE = "repeat_one"
PLAY_MODE_SHUFFLE = "shuffle"
PLAY_MODE_SHUFFLE_REPEAT_ALL = "shuffle_repeat_all"

# EQ Presets
EQ_PRESET_FLAT = "flat"
EQ_PRESET_ACOUSTIC = "acoustic"
EQ_PRESET_BASS = "bass"
EQ_PRESET_BASSBOOST = "bassboost"
EQ_PRESET_BASSREDUCER = "bassreducer"
EQ_PRESET_CLASSICAL = "classical"
EQ_PRESET_DANCE = "dance"
EQ_PRESET_DEEP = "deep"
EQ_PRESET_ELECTRONIC = "electronic"
EQ_PRESET_HIPHOP = "hiphop"
EQ_PRESET_JAZZ = "jazz"
EQ_PRESET_LOUDNESS = "loudness"
EQ_PRESET_POP = "pop"
EQ_PRESET_ROCK = "rock"
EQ_PRESET_TREBLE = "treble"
EQ_PRESET_VOCAL = "vocal"
EQ_PRESET_CUSTOM = "custom"

EQ_PRESET_MAP = {
    EQ_PRESET_FLAT: "Flat",
    EQ_PRESET_ACOUSTIC: "Acoustic",
    EQ_PRESET_BASS: "Bass",
    EQ_PRESET_BASSBOOST: "Bass Booster",
    EQ_PRESET_BASSREDUCER: "Bass Reducer",
    EQ_PRESET_CLASSICAL: "Classical",
    EQ_PRESET_DANCE: "Dance",
    EQ_PRESET_DEEP: "Deep",
    EQ_PRESET_ELECTRONIC: "Electronic",
    EQ_PRESET_HIPHOP: "Hip-Hop",
    EQ_PRESET_JAZZ: "Jazz",
    EQ_PRESET_LOUDNESS: "Loudness",
    EQ_PRESET_POP: "Pop",
    EQ_PRESET_ROCK: "Rock",
    EQ_PRESET_TREBLE: "Treble",
    EQ_PRESET_VOCAL: "Vocal",
    EQ_PRESET_CUSTOM: "Custom",
}

# Sources
SOURCE_AIRPLAY = "airplay"
SOURCE_DLNA = "dlna"
SOURCE_SPOTIFY = "spotify"
SOURCE_TIDAL = "tidal"
SOURCE_AMAZON = "amazon"
SOURCE_QOBUZ = "qobuz"
SOURCE_DEEZER = "deezer"
SOURCE_BLUETOOTH = "bluetooth"
SOURCE_LINE_IN = "line_in"
SOURCE_USB = "usb"
SOURCE_OPTICAL = "optical"
SOURCE_COAXIAL = "coaxial"
SOURCE_NETWORK = "network"
SOURCE_ARC = "arc"
SOURCE_FOLLOWER = "follower"

SOURCE_MAP = {
    "wifi": "WiFi",
    "line_in": "Line In",
    "bluetooth": "Bluetooth",
    "optical": "Optical",
    "coaxial": "Coaxial",
    "arc": "ARC",
    "follower": "Follower",
    "airplay": "AirPlay",
    "dlna": "DLNA",
    "spotify": "Spotify",
    "tidal": "Tidal",
    "amazon": "Amazon Music",
    "qobuz": "Qobuz",
    "deezer": "Deezer",
    "usb": "USB",
    "network": "WiFi",
}

# Services – extended diagnostic helpers
SERVICE_REBOOT = "reboot_device"
SERVICE_SYNC_TIME = "sync_time"
