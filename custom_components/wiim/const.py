"""Constants for the WiiM integration.

This module defines all constants used throughout the WiiM integration,
including configuration keys, default values, service names, and API endpoints.

Configuration:
    - Host configuration and connection settings
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

# Integration metadata
NAME = "WiiM"
VERSION = "0.1.44"
ATTRIBUTION = "Integration created by Michael Cumming @mjcumming"

# Config keys
CONF_HOST = "host"
CONF_VOLUME_STEP = "volume_step"
CONF_POLL_INTERVAL = "poll_interval"

# User-friendly option names (for UI)
CONF_STATUS_UPDATE_INTERVAL = "status_update_interval"
CONF_VOLUME_STEP_PERCENT = "volume_step_percent"
CONF_ENABLE_GROUP_ENTITY = "enable_group_entity"
CONF_DEBUG_LOGGING = "debug_logging"

# Entity filtering options
CONF_ENABLE_DIAGNOSTIC_ENTITIES = "enable_diagnostic_entities"
CONF_ENABLE_MAINTENANCE_BUTTONS = "enable_maintenance_buttons"
CONF_ENABLE_NETWORK_MONITORING = "enable_network_monitoring"
CONF_ENABLE_EQ_CONTROLS = "enable_eq_controls"

# Defaults
DEFAULT_PORT = 443  # HTTPS - like python-linkplay
DEFAULT_TIMEOUT = 3  # seconds - reduced for better HA asyncio performance
DEFAULT_POLL_INTERVAL = 5  # seconds - for config options
# Fixed polling interval - HA compliant, easily changeable
FIXED_POLL_INTERVAL = 5  # seconds - hard-coded 5s polling for all devices
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
API_ENDPOINT_LOOPMODE = "/httpapi.asp?command=setPlayerCmd:loopmode:"
API_ENDPOINT_SEEK = "/httpapi.asp?command=setPlayerCmd:seek:"
API_ENDPOINT_PLAYLIST = "/httpapi.asp?command=setPlayerCmd:playlist:"
API_ENDPOINT_CLEAR_PLAYLIST = "/httpapi.asp?command=setPlayerCmd:clear_playlist"
API_ENDPOINT_PLAY_URL = "/httpapi.asp?command=setPlayerCmd:play:"
API_ENDPOINT_PLAY_M3U = "/httpapi.asp?command=setPlayerCmd:playlist:"
API_ENDPOINT_PLAY_PROMPT_URL = "/httpapi.asp?command=playPromptUrl:"

# Multiroom Control
API_ENDPOINT_GROUP_EXIT = "/httpapi.asp?command=multiroom:Ungroup"
# No separate create command - devices become masters when others join them
# Note: Both group exit (leave) and delete (disband) use the same multiroom:Ungroup command
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

# Audio Output Control
API_ENDPOINT_AUDIO_OUTPUT_STATUS = "/httpapi.asp?command=getNewAudioOutputHardwareMode"
API_ENDPOINT_AUDIO_OUTPUT_SET = "/httpapi.asp?command=setAudioOutputHardwareMode:"

# Audio Output Modes
# Based on API documentation: 1=SPDIF, 2=AUX, 3=COAX
# WiiM Amp has 4 options: Line Out, Optical Out, Coax Out, BT Out
# Mode 0 likely = Line Out, Mode 4 likely = Bluetooth Out
AUDIO_OUTPUT_MODES = {
    "1": "Optical Out",  # SPDIF/Optical Out
    "2": "Line Out",  # AUX/Analog Out (shows as Line Out in WiiM app)
    "3": "Coax Out",  # Coaxial Out
    "4": "Bluetooth Out",  # Bluetooth Out
}

# Selectable output modes (hardware only - Bluetooth is firmware-controlled)
SELECTABLE_OUTPUT_MODES = ["Line Out", "Optical Out", "Coax Out", "Bluetooth Out"]

# Device Info
API_ENDPOINT_DEVICE_INFO = "/httpapi.asp?command=getDeviceInfo"
API_ENDPOINT_FIRMWARE = "/httpapi.asp?command=getFirmwareVersion"
API_ENDPOINT_MAC = "/httpapi.asp?command=getMAC"

# LED Control
API_ENDPOINT_LED = "/httpapi.asp?command=setLED:"
API_ENDPOINT_LED_BRIGHTNESS = "/httpapi.asp?command=setLEDBrightness:"

# Arylic-specific LED commands (experimental - based on user research)
# User reported: UART command "MCU+PAS+RAKOIT:LED:0" works
# TCP API commands below are experimental and may need adjustment
# Documentation: https://github.com/mjcumming/wiim/issues/55
API_ENDPOINT_ARYLIC_LED = "/httpapi.asp?command=MCU+PAS+RAKOIT:LED:"
API_ENDPOINT_ARYLIC_LED_BRIGHTNESS = "/httpapi.asp?command=MCU+PAS+RAKOIT:LEDBRIGHTNESS:"

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

# Map internal API source names to user-friendly display names
# Note: We prioritize showing the actual streaming service name over generic "Ethernet"
SOURCE_MAP = {
    "wifi": "Network",  # Generic network connection - fallback only
    "ethernet": "Network",  # Generic network connection - fallback only
    "line_in": "Line In",
    "bluetooth": "Bluetooth",
    "optical": "Optical",
    "coaxial": "Coaxial",
    "arc": "ARC",
    "follower": "Follower",
    "airplay": "AirPlay",  # Show actual service name
    "dlna": "DLNA",  # Show actual service name
    "spotify": "Spotify",  # Show actual service name
    "spotify connect": "Spotify Connect",  # Show actual service name
    "tidal": "Tidal",  # Show actual service name
    "amazon": "Amazon Music",  # Show actual service name
    "apple_music": "Apple Music",  # Show actual service name
    "qobuz": "Qobuz",  # Show actual service name
    "deezer": "Deezer",  # Show actual service name
    "usb": "USB",
    "network": "Network",  # Generic network status - fallback only
    "idle": "Idle",
    "multiroom": "Multiroom",
    "usb dac": "USB DAC",
    "line in 2": "Line In 2",
    # Handle "Following [name]" sources from slaves
    "following": "Following",  # Partial match for slave sources
}

# Selectable sources only - physical inputs that users can manually switch to
# These are the actual sources that work with the switchmode API command
# Network-based streaming services (Spotify, AirPlay, etc.) are handled automatically
SELECTABLE_SOURCES = [
    "Bluetooth",  # Bluetooth input
    "Line In",  # Analog input
    "Optical",  # Digital optical input
    "Coaxial",  # Digital coaxial input (if supported)
    "HDMI",  # HDMI input (if supported)
    "ARC",  # HDMI ARC input (if supported)
    "USB",  # USB input (if supported)
    "Line In 2",  # Second analog input (if supported)
]

# Status-only sources that should be displayed but not selectable
# These are either status indicators or generic network modes
STATUS_ONLY_SOURCES = [
    "Idle",
    "Multiroom",
    "Follower",
    "Following",
    "Network",  # Generic network mode (fallback when specific service unknown)
    "Ethernet",  # Legacy network mode name (fallback)
    "USB DAC",  # May be a status rather than selectable input
]

# Services – extended diagnostic helpers
SERVICE_REBOOT = "reboot_device"
SERVICE_SYNC_TIME = "sync_time"

# ===== Diagnostic keys (getStatusEx) =====
FIRMWARE_KEY = "firmware"
FIRMWARE_DATE_KEY = "firmware_date"
HARDWARE_KEY = "hardware"
MCU_VERSION_KEY = "mcu_ver"
DSP_VERSION_KEY = "dsp_ver"
PRESET_SLOTS_KEY = "preset_slots"
WMRM_VERSION_KEY = "wmrm_version"
UPDATE_AVAILABLE_KEY = "update_available"
LATEST_VERSION_KEY = "latest_version"

PROJECT_KEY = "project"

API_ENDPOINT_PRESET_INFO = "/httpapi.asp?command=getPresetInfo"

# ===== UNOFFICIAL API ENDPOINTS =====
# These endpoints are not officially documented and may change in future firmware updates


# Bluetooth Operations (Unofficial)
API_ENDPOINT_START_BT_DISCOVERY = "/httpapi.asp?command=startbtdiscovery:"
API_ENDPOINT_GET_BT_DISCOVERY_RESULT = "/httpapi.asp?command=getbtdiscoveryresult"

# Audio Settings (Unofficial)
API_ENDPOINT_GET_SPDIF_SAMPLE_RATE = "/httpapi.asp?command=getSpdifOutSampleRate"
API_ENDPOINT_SET_SPDIF_SWITCH_DELAY = "/httpapi.asp?command=setSpdifOutSwitchDelayMs:"
API_ENDPOINT_GET_CHANNEL_BALANCE = "/httpapi.asp?command=getChannelBalance"
API_ENDPOINT_SET_CHANNEL_BALANCE = "/httpapi.asp?command=setChannelBalance:"

# Squeezelite/LMS Integration (Unofficial)
API_ENDPOINT_SQUEEZELITE_STATE = "/httpapi.asp?command=Squeezelite:getState"
API_ENDPOINT_SQUEEZELITE_DISCOVER = "/httpapi.asp?command=Squeezelite:discover"
API_ENDPOINT_SQUEEZELITE_AUTO_CONNECT = "/httpapi.asp?command=Squeezelite:autoConnectEnable:"
API_ENDPOINT_SQUEEZELITE_CONNECT_SERVER = "/httpapi.asp?command=Squeezelite:connectServer:"

# Miscellaneous Operations (Unofficial)
API_ENDPOINT_SET_LED = "/httpapi.asp?command=LED_SWITCH_SET:"
API_ENDPOINT_SET_BUTTONS = "/httpapi.asp?command=Button_Enable_SET:"
