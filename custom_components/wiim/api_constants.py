"""WiiM API constants and mappings.

Large constants extracted from api_base.py to keep it under 300 LOC.
"""

from __future__ import annotations

# SSL Certificate for WiiM devices
WIIM_CA_CERT = """-----BEGIN CERTIFICATE-----
MIIDmDCCAoACAQEwDQYJKoZIhvcNAQELBQAwgZExCzAJBgNVBAYTAkNOMREwDwYD
VQQIDAhTaGFuZ2hhaTERMA8GA1UEBwwIU2hhbmdoYWkxETAPBgNVBAoMCExpbmtw
bGF5MQwwCgYDVQQLDANpbmMxGTAXBgNVBAMMEHd3dy5saW5rcGxheS5jb20xIDAe
BgkqhkiG9w0BCQEWEW1haWxAbGlua3BsYXkuY29tMB4XDTE4MTExNTAzMzI1OVoX
DTQ2MDQwMTAzMzI1OVowgZExCzAJBgNVBAYTAkNOMREwDwYDVQQIDAhTaGFuZ2hh
aTERMA8GA1UEBwwIU2hhbmdoYWkxETAPBgNVBAoMCExpbmtwbGF5MQwwCgYDVQQL
DANpbmMxGTAXBgNVBAMMEHd3dy5saW5rcGxheS5jb20xIDAeBgkqhkiG9w0BCQEW
EW1haWxAbGlua3BsYXkuY29tMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKC
AQEApP7trR9C8Ajr/CZqi70HYzQHZMX0gj8K3RzO0k5aucWiRkHtvcnfJIz+4dMB
EZHjv/STutsFBwbtD1iLEv48Cxvht6AFPuwTX45gYQ18hyEUC8wFhG7cW7Ek5HtZ
aLH75UFxrpl6zKn/Vy3SGL2wOd5qfBiJkGyZGgg78JxHVBZLidFuU6H6+fIyanwr
ejj8B5pz+KAui6T7SWA8u69UPbC4AmBLQxMPzIX/pirgtKZ7LedntanHlY7wrlAa
HroZOpKZxG6UnRCmw23RPHD6FUZq49f/zyxTFbTQe5NmjzG9wnKCf3R8Wgl8JPW9
4yAbOgslosTfdgrmjkPfFIP2JQIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQARmy6f
esrifhW5NM9i3xsEVp945iSXhqHgrtIROgrC7F1EIAyoIiBdaOvitZVtsYc7Ivys
QtyVmEGscyjuYTdfigvwTVVj2oCeFv1Xjf+t/kSuk6X3XYzaxPPnFG4nAe2VwghE
rbZG0K5l8iXM7Lm+ZdqQaAYVWsQDBG8lbczgkB9q5ed4zbDPf6Fsrsynxji/+xa4
9ARfyHlkCDBThGNnnl+QITtfOWxm/+eReILUQjhwX+UwbY07q/nUxLlK6yrzyjnn
wi2B2GovofQ/4icVZ3ecTqYK3q9gEtJi72V+dVHM9kSA4Upy28Y0U1v56uoqeWQ6
uc2m8y8O/hXPSfKd
-----END CERTIFICATE-----"""

# Status field mapping for parser
STATUS_MAP: dict[str, str] = {
    "status": "play_status",
    "state": "play_status",
    "player_state": "play_status",
    "vol": "volume",
    "mute": "mute",
    "eq": "eq_preset",
    "EQ": "eq_preset",
    "eq_mode": "eq_preset",
    "loop": "loop_mode",
    "curpos": "position_ms",
    "totlen": "duration_ms",
    "Title": "title_hex",
    "Artist": "artist_hex",
    "Album": "album_hex",
    "DeviceName": "device_name",
    "uuid": "uuid",
    "ssid": "ssid",
    "MAC": "mac_address",
    "firmware": "firmware",
    "project": "project",
    "WifiChannel": "wifi_channel",
    "RSSI": "wifi_rssi",
}

# Mode value mapping
MODE_MAP: dict[str, str] = {
    "0": "idle",
    "1": "airplay",
    "2": "dlna",
    "3": "wifi",
    "4": "line_in",
    "5": "bluetooth",
    "6": "optical",
    "10": "wifi",
    "11": "usb",
    "20": "wifi",
    "31": "spotify",
    "36": "qobuz",
    "40": "line_in",
    "41": "bluetooth",
    "43": "optical",
    "47": "line_in_2",
    "51": "usb",
    "99": "follower",
}

# EQ preset numeric mapping
EQ_NUMERIC_MAP: dict[str, str] = {
    "0": "flat",
    "1": "pop",
    "2": "rock",
    "3": "jazz",
    "4": "classical",
    "5": "bass",
    "6": "treble",
    "7": "vocal",
    "8": "loudness",
    "9": "dance",
    "10": "acoustic",
    "11": "electronic",
    "12": "deep",
}
