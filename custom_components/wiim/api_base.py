"""WiiM HTTP API core client.

This trimmed-down variant contains only the networking/transport layer and the
player-status parser that the Home-Assistant coordinator layer depends on.
All high-level helper methods (volume, playback, presets, EQ, multi-room,
maintenance, …) have been removed for a cleaner public surface while we
undertake a larger refactor.
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from typing import Any
from urllib.parse import quote

import aiohttp
import async_timeout
from aiohttp import ClientSession

# Core constants that are still required by the remaining methods.
from .const import (
    API_ENDPOINT_STATUS,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    PLAY_MODE_NORMAL,
    PLAY_MODE_REPEAT_ALL,
    PLAY_MODE_REPEAT_ONE,
    PLAY_MODE_SHUFFLE,
    PLAY_MODE_SHUFFLE_REPEAT_ALL,
)
from .models import DeviceInfo, PlayerStatus

_LOGGER = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# WiiM ships self-signed certificates so we bundle the original CA to improve
# compatibility when `verify_mode` is kept at the default of *CERT_REQUIRED*.
# -----------------------------------------------------------------------------
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

HEADERS: dict[str, str] = {"Connection": "close"}

# -----------------------------------------------------------------------------
# Exceptions (kept as-is so external call-sites don’t break during the trim).
# -----------------------------------------------------------------------------


class WiiMError(Exception):
    """Base exception for all WiiM API errors."""


class WiiMRequestError(WiiMError):
    """Raised when there is an error communicating with the WiiM device."""


class WiiMResponseError(WiiMError):
    """Raised when the WiiM device returns an error response."""


class WiiMTimeoutError(WiiMRequestError):
    """Raised when a request to the WiiM device times out."""


class WiiMConnectionError(WiiMRequestError):
    """Raised on network-level connectivity problems (SSL, unreachable, …)."""


class WiiMInvalidDataError(WiiMError):
    """The device responded with malformed or non-JSON data."""


# -----------------------------------------------------------------------------
# 🚚   WiiM HTTP client – *transport only*  (all high-level helpers removed)
# -----------------------------------------------------------------------------


class WiiMClient:
    """Minimal WiiM HTTP API client – transport & player-status parser only."""

    # ------------------------------------------------------------------
    # Lifecycle ---------------------------------------------------------
    # ------------------------------------------------------------------

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
        ssl_context: ssl.SSLContext | None = None,
        session: ClientSession | None = None,
    ) -> None:
        """Instantiate the client.

        Args:
            host: Device hostname or IP. A trailing ":<port>" is respected.
            port: Optional override when *host* does **not** include a port.
            timeout: Network timeout (seconds).
            ssl_context: Custom SSL context (tests/advanced use-cases only).
            session: Optional shared *aiohttp* session.
        """
        self._discovered_port: bool = False

        if ":" in host and not host.startswith("["):
            # Potential "host:port" **or** bare IPv6 literal – try the former.
            try:
                host_part, port_part = host.rsplit(":", 1)
                self.port = int(port_part)
                self._host = host_part
                self._discovered_port = True
            except (ValueError, TypeError):
                self._host = host
                self.port = port
        else:
            self._host = host
            self.port = port

        # Normalise host for URL contexts (IPv6 needs brackets).
        self._host_url = f"[{self._host}]" if ":" in self._host and not self._host.startswith("[") else self._host

        self.timeout = timeout
        self.ssl_context = ssl_context
        self._session = session

        # Start optimistic with HTTPS.
        self._endpoint = f"https://{self._host_url}:{self.port}"

        # Internal helpers for parser bookkeeping.
        self._last_track: str | None = None
        self._last_play_mode: str | None = None
        self._verify_ssl_default: bool = True

        # Basic mutex to avoid concurrent protocol-probe races.
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # SSL helpers -------------------------------------------------------
    # ------------------------------------------------------------------

    def _get_ssl_context(self) -> ssl.SSLContext:
        """Return a permissive SSL context able to talk to WiiM devices."""
        if self.ssl_context is not None:
            return self.ssl_context

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.minimum_version = ssl.TLSVersion.TLSv1
        ctx.maximum_version = ssl.TLSVersion.TLSv1_3
        ctx.set_ciphers("ALL:@SECLEVEL=0")

        try:
            ctx.load_verify_locations(cadata=WIIM_CA_CERT)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("Failed loading WiiM CA cert: %s", exc)

        self.ssl_context = ctx
        return ctx

    # ------------------------------------------------------------------
    # Low-level request helper -----------------------------------------
    # ------------------------------------------------------------------

    async def _request(self, endpoint: str, method: str = "GET", **kwargs: Any) -> dict[str, Any]:
        """Perform an HTTP(S) request with smart protocol fallback."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))

        kwargs.setdefault("headers", HEADERS)

        # -----------------------------
        # Fast-path: use last endpoint.
        # -----------------------------
        if self._endpoint:
            from urllib.parse import urlsplit

            try:
                p = urlsplit(self._endpoint)
                url = f"{p.scheme}://{p.hostname}:{p.port}{endpoint}"
                if p.scheme == "https":
                    kwargs["ssl"] = self._get_ssl_context()
                else:
                    kwargs.pop("ssl", None)

                async with async_timeout.timeout(self.timeout):
                    async with self._session.request(method, url, **kwargs) as resp:
                        resp.raise_for_status()
                        text = await resp.text()
                        if text.strip() == "OK":
                            return {"raw": "OK"}
                        return json.loads(text)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Fast-path failed: %s", err)

        # -----------------------------
        # Probe list – HTTPS first.
        # -----------------------------
        protocols: list[tuple[str, int, ssl.SSLContext | None]]
        if self._discovered_port:
            protocols = [
                ("https", self.port, self._get_ssl_context()),
                ("http", self.port, None),
            ]
        else:
            protocols = [
                ("https", 443, self._get_ssl_context()),
                ("https", 4443, self._get_ssl_context()),
                ("http", 80, None),
            ]
            if self.port not in (80, 443):
                protocols.insert(0, ("https", self.port, self._get_ssl_context()))
                protocols.insert(1, ("http", self.port, None))

        last_error: Exception | None = None
        tried: list[str] = []

        for scheme, port, ssl_ctx in protocols:
            host_for_url = f"[{self._host}]" if ":" in self._host and not self._host.startswith("[") else self._host
            url = f"{scheme}://{host_for_url}:{port}{endpoint}"
            tried.append(url)

            if scheme == "https":
                kwargs["ssl"] = ssl_ctx
            else:
                kwargs.pop("ssl", None)

            try:
                async with async_timeout.timeout(self.timeout):
                    async with self._session.request(method, url, **kwargs) as resp:
                        resp.raise_for_status()
                        text = await resp.text()
                        self._endpoint = f"{scheme}://{host_for_url}:{port}"
                        if text.strip() == "OK":
                            return {"raw": "OK"}
                        return json.loads(text)
            except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as err:
                last_error = err
                continue
        raise WiiMConnectionError(
            f"Failed to communicate with {self._host} after trying: {', '.join(tried)}\nLast error: {last_error}"
        )

    # ------------------------------------------------------------------
    # Public helpers ----------------------------------------------------
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying *aiohttp* session."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def validate_connection(self) -> bool:
        """Return *True* if *getPlayerStatusEx* answers successfully."""
        try:
            await self.get_player_status()
            return True
        except WiiMError:
            return False

    async def get_device_name(self) -> str:
        """Return device-reported *DeviceName* or the raw IP if unavailable."""
        try:
            status = await self.get_player_status()
            if name := status.get("DeviceName"):
                return name.strip()
            info = await self.get_device_info()
            if name := info.get("DeviceName") or info.get("device_name"):
                return name.strip()
        except WiiMError:
            _LOGGER.debug("Falling back to IP for device name of %s", self._host)
        return self._host

    async def get_status(self) -> dict[str, Any]:
        """Return normalised output of *getStatusEx* (device-level info)."""
        raw = await self._request(API_ENDPOINT_STATUS)
        return self._parse_player_status(raw)

    async def get_device_info(self) -> dict[str, Any]:
        """Lightweight wrapper around *getStatusEx* (raw JSON)."""
        try:
            return await self._request(API_ENDPOINT_STATUS)
        except WiiMError as err:
            _LOGGER.debug("get_device_info failed: %s", err)
            return {}

    async def get_player_status(self) -> dict[str, Any]:
        """Return parsed output of *getPlayerStatusEx*."""
        try:
            raw = await self._request("/httpapi.asp?command=getPlayerStatusEx")
            return self._parse_player_status(raw)
        except WiiMError as err:
            _LOGGER.error("get_player_status failed: %s", err)
            return {}

    # ------------------------------------------------------------------
    # Typed wrappers (Pydantic) ----------------------------------------
    # ------------------------------------------------------------------

    async def get_device_info_model(self) -> DeviceInfo:
        """Return :class:`DeviceInfo` parsed by *pydantic*."""
        return DeviceInfo.model_validate(await self.get_device_info())

    async def get_player_status_model(self) -> PlayerStatus:
        """Return :class:`PlayerStatus` parsed by *pydantic*."""
        return PlayerStatus.model_validate(await self.get_player_status())

    # ------------------------------------------------------------------
    # Misc -----------------------------------------------------------------
    # ------------------------------------------------------------------

    @property
    def base_url(self) -> str:  # noqa: D401 – property, not a method.
        """Base URL used for the last successful request."""
        return self._endpoint

    # ------------------------------------------------------------------
    # Parser ------------------------------------------------------------
    # ------------------------------------------------------------------

    _STATUS_MAP: dict[str, str] = {
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

    _MODE_MAP: dict[str, str] = {
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

    _EQ_NUMERIC_MAP: dict[str, str] = {
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

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # _parse_player_status
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _parse_player_status(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalise *getPlayerStatusEx* / *getStatusEx* responses."""
        data: dict[str, Any] = {}

        play_state_val = raw.get("state") or raw.get("player_state") or raw.get("status")
        if play_state_val is not None:
            data["play_status"] = play_state_val

        # Generic key mapping first.
        for k, v in raw.items():
            if k in ("status", "state", "player_state"):
                continue
            data[self._STATUS_MAP.get(k, k)] = v

        # Hex-encoded strings → UTF-8.
        data["title"] = _hex_to_str(raw.get("Title")) or raw.get("title")
        data["artist"] = _hex_to_str(raw.get("Artist")) or raw.get("artist")
        data["album"] = _hex_to_str(raw.get("Album")) or raw.get("album")

        # Track change detection for debug logging.
        if data.get("title") and data["title"] != "Unknown":
            cur = f"{data.get('artist', 'Unknown')} - {data['title']}"
            if self._last_track != cur:
                _LOGGER.info("🎵 Track changed: %s", cur)
                self._last_track = cur

        # Power state defaults to *True* when missing.
        data.setdefault("power", True)

        # Volume (int percentage) → float 0-1.
        if (vol := raw.get("vol")) is not None:
            try:
                vol_i = int(vol)
                data["volume_level"] = vol_i / 100
                data["volume"] = vol_i
            except ValueError:
                _LOGGER.debug("Invalid volume value: %s", vol)

        # Playback position & duration (ms → s).
        if (pos := raw.get("curpos") or raw.get("offset_pts")) is not None:
            data["position"] = int(pos) // 1_000
            data["position_updated_at"] = asyncio.get_running_loop().time()
        if raw.get("totlen") is not None:
            data["duration"] = int(raw["totlen"]) // 1_000

        # Mute → bool.
        if "mute" in data:
            try:
                data["mute"] = bool(int(data["mute"]))
            except (TypeError, ValueError):  # noqa: PERF203 – clarity > micro perf.
                data["mute"] = bool(data["mute"])

        # Play-mode mapping.
        if "play_mode" not in data and "loop_mode" in data:
            try:
                loop_val = int(data["loop_mode"])
            except (TypeError, ValueError):
                loop_val = 4
            data["play_mode"] = {
                0: PLAY_MODE_REPEAT_ALL,
                1: PLAY_MODE_REPEAT_ONE,
                2: PLAY_MODE_SHUFFLE_REPEAT_ALL,
                3: PLAY_MODE_SHUFFLE,
            }.get(loop_val, PLAY_MODE_NORMAL)

        # Artwork – attempt cache-busting when metadata changes.
        cover = (
            raw.get("cover")
            or raw.get("cover_url")
            or raw.get("albumart")
            or raw.get("albumArtURI")
            or raw.get("albumArtUri")
            or raw.get("albumarturi")
            or raw.get("art_url")
            or raw.get("artwork_url")
            or raw.get("pic_url")
        )
        if cover:
            cache_key = f"{data.get('title', '')}-{data.get('artist', '')}-{data.get('album', '')}"
            if cache_key:
                encoded = quote(cache_key)
                sep = "&" if "?" in cover else "?"
                cover = f"{cover}{sep}cache={encoded}"
            data["entity_picture"] = cover

        # Source mapping from *mode* field.
        if (mode_val := raw.get("mode")) is not None and "source" not in data:
            if str(mode_val) == "99":
                data["source"] = "multiroom"
                data["_multiroom_mode"] = True
            else:
                data["source"] = self._MODE_MAP.get(str(mode_val), "unknown")

        # Vendor override (e.g. Amazon Music).
        vendor_val = raw.get("vendor") or raw.get("Vendor") or raw.get("app")
        if vendor_val:
            vendor_clean = str(vendor_val).strip()
            _VENDOR_MAP = {
                "amazon music": "amazon",
                "amazonmusic": "amazon",
                "prime": "amazon",
                "qobuz": "qobuz",
                "tidal": "tidal",
                "deezer": "deezer",
            }
            if data.get("source") in {None, "wifi", "unknown"}:
                data["source"] = _VENDOR_MAP.get(vendor_clean.lower(), vendor_clean.lower().replace(" ", "_"))
            data["vendor"] = vendor_clean

        # EQ numeric → textual preset.
        eq_raw = data.get("eq_preset")
        if isinstance(eq_raw, int | str) and str(eq_raw).isdigit():
            data["eq_preset"] = self._EQ_NUMERIC_MAP.get(str(eq_raw), eq_raw)

        # Qobuz quirk – always reports *stop* even when playing.
        if (
            data.get("source") == "qobuz"
            and (not data.get("play_status") or str(data["play_status"]).lower() in {"stop", "stopped", "idle", ""})
        ):
            data["play_status"] = "play"

        return data


# -----------------------------------------------------------------------------
# Helper – hex-encoded metadata decoding
# -----------------------------------------------------------------------------

def _hex_to_str(val: str | None) -> str | None:
    """Decode hex-encoded UTF-8 strings as used by LinkPlay."""
    if not val:
        return None
    try:
        return bytes.fromhex(val).decode("utf-8", errors="replace")
    except ValueError:
        return val
