"""Constants for WiiM tests."""

from custom_components.wiim.const import CONF_HOST

MOCK_CONFIG = {CONF_HOST: "192.168.1.100"}

# Mock device data for testing
MOCK_DEVICE_DATA = {
    "uuid": "FF31F09E1A5020113B0A3918",
    "DeviceName": "WiiM Mini",
    "device_name": "WiiM Mini",
    "firmware": "4.6.328252",
    "hardware": "A31",
    "project": "UP2STREAM_MINI_V3",
    "MAC": "00:22:6C:33:D4:AD",
    "ip": "192.168.1.100",
    "vol": "50",
    "mute": "0",
    "status": "stop",
    "mode": "0",
}

# Mock status response
MOCK_STATUS_RESPONSE = {
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
    "device_name": "WiiM Mini",
    "DeviceName": "WiiM Mini",
}
