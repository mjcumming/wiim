"""Constants for WiiM tests."""

from custom_components.wiim.const import CONF_HOST
from custom_components.wiim.models import DeviceInfo, PlayerStatus

MOCK_CONFIG = {CONF_HOST: "192.168.1.100"}

# Mock device data for testing
_RAW_DEVICE_INFO = {
    "uuid": "FF31F09E1A5020113B0A3918",
    "DeviceName": "WiiM Mini",
    "device_name": "WiiM Mini",
    "firmware": "4.6.328252",
    "hardware": "A31",
    "project": "UP2STREAM_MINI_V3",
    "MAC": "00:22:6C:33:D4:AD",
    "ip": "192.168.1.100",
    "wmrm_version": "1.32",
}

_RAW_STATUS = {
    "type": "0",
    "ch": "0",
    "mode": "0",
    "loop": "0",
    "eq": "0",
    "status": "stop",
    "curpos": "0",
    "totlen": "0",
    "Title": "",
    "Artist": "",
    "Album": "",
    "vol": "50",
    "mute": "0",
    "DeviceName": "WiiM Mini",
}

# Expose typed model instances for tests
MOCK_DEVICE_MODEL: DeviceInfo = DeviceInfo.model_validate(_RAW_DEVICE_INFO)
MOCK_STATUS_MODEL: PlayerStatus = PlayerStatus.model_validate(_RAW_STATUS)

# Keep raw dicts for fixtures that still need them temporarily
MOCK_DEVICE_DATA = _RAW_DEVICE_INFO
MOCK_STATUS_RESPONSE = _RAW_STATUS
