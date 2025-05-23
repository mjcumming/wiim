"""WiiM HTTP API client.

This module provides a client for interacting with WiiM devices through their HTTP API.
It implements all necessary functionality for controlling WiiM audio devices, including:

- Basic playback controls (play, pause, stop, next/previous track)
- Volume and mute control
- Power management
- Playback mode settings (repeat, shuffle)
- Multiroom group management
- Equalizer controls
- Source selection
- Device information retrieval

The client is designed to be used with Home Assistant's async architecture and provides
a clean, type-hinted interface for all device operations.

All API calls are made over HTTPS to the device's HTTP API endpoint at
``https://<ip>/httpapi.asp?command=...``. The client handles SSL certificate
verification and request/response parsing.
"""

from __future__ import annotations

import asyncio
import json
import logging
from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import aiohttp
import async_timeout
from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientError
import ssl

from .const import (
    API_ENDPOINT_CLEAR_PLAYLIST,
    API_ENDPOINT_DEVICE_INFO,
    API_ENDPOINT_EQ_CUSTOM,
    API_ENDPOINT_EQ_GET,
    API_ENDPOINT_EQ_PRESET,
    API_ENDPOINT_FIRMWARE,
    API_ENDPOINT_GROUP_CREATE,
    API_ENDPOINT_GROUP_DELETE,
    API_ENDPOINT_GROUP_EXIT,
    API_ENDPOINT_GROUP_JOIN,
    API_ENDPOINT_LED,
    API_ENDPOINT_LED_BRIGHTNESS,
    API_ENDPOINT_MAC,
    API_ENDPOINT_MUTE,
    API_ENDPOINT_NEXT,
    API_ENDPOINT_PAUSE,
    API_ENDPOINT_PLAY,
    API_ENDPOINT_POWER,
    API_ENDPOINT_PREV,
    API_ENDPOINT_PRESET,
    API_ENDPOINT_REPEAT,
    API_ENDPOINT_SEEK,
    API_ENDPOINT_SHUFFLE,
    API_ENDPOINT_SOURCE,
    API_ENDPOINT_SOURCES,
    API_ENDPOINT_STATUS,
    API_ENDPOINT_STOP,
    API_ENDPOINT_VOLUME,
    API_ENDPOINT_PLAY_URL,
    API_ENDPOINT_PLAY_M3U,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    PLAY_MODE_NORMAL,
    PLAY_MODE_REPEAT_ALL,
    PLAY_MODE_REPEAT_ONE,
    PLAY_MODE_SHUFFLE,
    PLAY_MODE_SHUFFLE_REPEAT_ALL,
    API_ENDPOINT_GROUP_SLAVES,
    API_ENDPOINT_GROUP_KICK,
    API_ENDPOINT_GROUP_SLAVE_MUTE,
    EQ_PRESET_MAP,
    API_ENDPOINT_EQ_ON,
    API_ENDPOINT_EQ_OFF,
    API_ENDPOINT_EQ_STATUS,
    API_ENDPOINT_EQ_LIST,
)

_LOGGER = logging.getLogger(__name__)

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

HEADERS = {"Connection": "close"}


class WiiMError(Exception):
    """Base exception for all WiiM API errors."""


class WiiMRequestError(WiiMError):
    """Raised when there is an error communicating with the WiiM device.

    This includes network errors, timeouts, and invalid responses.
    """


class WiiMResponseError(WiiMError):
    """Raised when the WiiM device returns an error response.

    This includes invalid commands, unsupported operations, and device-specific errors.
    """


class WiiMTimeoutError(WiiMRequestError):
    """Raised when a request to the WiiM device times out."""


class WiiMConnectionError(WiiMRequestError):
    """Raised when there is a connection error with the WiiM device.

    This includes SSL errors, network unreachability, and connection refused errors.
    """


class WiiMInvalidDataError(WiiMError):
    """The device responded with malformed or non-JSON data."""


class WiiMClient:
    """WiiM HTTP API client.

    This class provides a comprehensive interface for interacting with WiiM devices through their HTTP API.
    It handles all communication with the device, including authentication, request/response handling,
    and error management.

    Key Features:
    - Asynchronous HTTP communication with WiiM devices
    - Automatic SSL/TLS handling with fallback to insecure mode
    - Comprehensive error handling and logging
    - Support for device grouping and multiroom functionality
    - Volume and playback control
    - Device status monitoring and diagnostics

    Attributes:
        host (str): The IP address or hostname of the WiiM device
        port (int): The port number for the HTTP API (default: 443)
        timeout (float): Request timeout in seconds (default: 10.0)
        ssl_context (ssl.SSLContext | None): SSL context for HTTPS connections
        session (ClientSession | None): Optional aiohttp ClientSession for requests

    Error Handling:
        The client implements a robust error handling system with specific exception types:
        - WiiMRequestError: General request/communication errors
        - WiiMResponseError: Invalid or error responses from device
        - WiiMTimeoutError: Request timeout errors
        - WiiMConnectionError: Network/connection issues
        - WiiMInvalidDataError: Malformed response data

    Security:
        - Uses HTTPS by default (port 443)
        - Handles device-specific SSL certificates
        - Falls back to insecure mode only after verification failure
        - Maintains session security and proper cleanup
    """

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
        ssl_context: ssl.SSLContext | None = None,
        session: ClientSession | None = None,
    ) -> None:
        """Initialize the WiiM client.

        Args:
            host: The IP address or hostname of the WiiM device.
            port: The port number for the HTTP API (default: 443).
            timeout: Request timeout in seconds (default: 10.0).
            ssl_context: SSL context for HTTPS connections.
            session: Optional aiohttp ClientSession to use for requests.
        """
        self._host = host
        self.port = port
        self.timeout = timeout
        self.ssl_context = ssl_context
        self._session = session
        # Choose scheme based on port (80 = http, everything else = https)
        scheme = "http" if port == 80 else "https"
        self._endpoint = f"{scheme}://{host}:{port}"
        self._lock = asyncio.Lock()
        self._base_url = self._endpoint
        self._group_master: str | None = None
        self._group_slaves: list[str] = []
        # Some firmwares ship a *device-unique* self-signed certificate.  We
        # start optimistic (verify on) and permanently fall back to
        # *insecure* mode after the first verification failure to avoid the
        # noisy SSL errors on every poll.
        self._verify_ssl_default: bool = True

    @property
    def host(self) -> str:
        """Return the host address."""
        return self._host

    def _get_ssl_context(self) -> ssl.SSLContext:
        """Return (and lazily create) the SSL context.

        Home Assistant considers `ssl.create_default_context()` a blocking
        operation because it tries to load the system trust store from disk.
        To stay fully async-safe we instead create a bare `SSLContext` and
        explicitly load **only** the pinned WiiM root certificate. If loading
        the certificate fails for any reason (e.g. corrupted PEM), we fall
        back to an *unverified* context so the request code can still proceed
        and rely on the existing retry-with-insecure logic.
        """
        if self.ssl_context is not None:
            return self.ssl_context

        # Start with a minimal TLS client context (no file-system access)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False  # Device uses self-signed cert with host-mismatch
        ctx.verify_mode = ssl.CERT_NONE  # Don't verify cert since it's self-signed

        try:
            # Load the WiiM CA certificate for reference
            ctx.load_verify_locations(cadata=WIIM_CA_CERT)
            _LOGGER.debug("Successfully loaded WiiM CA certificate for %s", self.host)
        except Exception as e:
            _LOGGER.warning(
                "Failed to load WiiM CA certificate for %s: %s. This may indicate a device with a self-signed certificate.",
                self.host,
                e
            )

        self.ssl_context = ctx
        return self.ssl_context

    async def _request(
        self,
        endpoint: str,
        method: str = "GET",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make a request to the WiiM device with retry on SSL errors.

        Args:
            endpoint: The API endpoint to call.
            method: The HTTP method to use (default: GET).
            **kwargs: Additional arguments to pass to the request.

        Returns:
            The parsed JSON response from the device.

        Raises:
            WiiMRequestError: If there is an error communicating with the device.
            WiiMResponseError: If the device returns an error response.
        """
        if self._session is None:
            # aiohttp>=3.9 requires a ClientTimeout object
            timeout_obj = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout_obj)

        kwargs.setdefault("headers", HEADERS)
        kwargs.setdefault("ssl", self._get_ssl_context())

        # Try both ports (443 and 80) with and without SSL verification
        ports_to_try = [(self.port, False), (80, False)]  # Always use unverified SSL
        tried: list[str] = []
        last_error: Exception | None = None

        for port, verify_ssl in ports_to_try:
            url = f"https://{self.host}:{port}{endpoint}"
            tried.append(f"{url} (verify={verify_ssl})")

            try:
                _LOGGER.debug("Making request to %s", url)
                async with async_timeout.timeout(self.timeout):
                    async with self._session.request(method, url, **kwargs) as response:
                        response.raise_for_status()
                        text = await response.text()
                        _LOGGER.debug("Response from %s: %s", url, text)
                        if text.strip() == "OK":
                            return {"raw": text.strip()}
                        return json.loads(text)
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                last_error = err
                _LOGGER.debug(
                    "Connection error for %s: %s. Will try next configuration.",
                    url,
                    err
                )
                if verify_ssl:
                    continue
                raise WiiMConnectionError(f"Failed to connect to WiiM device: {err}") from err
            except json.JSONDecodeError:
                # Most control endpoints return plain "OK". Treat any
                # non-JSON body as a successful raw response instead of an
                # error so caller logic doesn't break on a volume/power/etc.
                _LOGGER.debug("Non-JSON response from %s: %s", url, text)
                return {"raw": text.strip()}

        # If we get here, all attempts failed
        error_msg = f"Failed to communicate with WiiM device after trying: {', '.join(tried)}"
        if last_error:
            error_msg += f"\nLast error: {last_error}"
        raise WiiMRequestError(error_msg)

    async def close(self) -> None:
        """Close the client session.

        This should be called when the client is no longer needed to properly
        clean up resources.
        """
        if self._session:
            await self._session.close()
            self._session = None

    async def get_status(self) -> dict[str, Any]:
        """Get the current status of the WiiM device.

        Returns:
            A dictionary containing the device's current status, including:
            - volume: Current volume level (0-1)
            - mute: Current mute state
            - power: Current power state
            - play_status: Current playback state
            - play_mode: Current play mode
            - position: Current playback position in seconds
            - duration: Total duration of current track in seconds
            - source: Current audio source
            - title: Current track title
            - artist: Current track artist
            - album: Current track album
            - wifi_rssi: Current WiFi signal strength
            - wifi_channel: Current WiFi channel
            - device_model: Device model name
            - device_name: Device friendly name
            - device_id: Device unique identifier
            - firmware: Current firmware version
        """
        raw = await self._request(API_ENDPOINT_STATUS)
        return self._parse_player_status(raw)

    async def play(self) -> None:
        """Start or resume playback of the current track."""
        await self._request(API_ENDPOINT_PLAY)

    async def pause(self) -> None:
        """Pause playback of the current track."""
        await self._request(API_ENDPOINT_PAUSE)

    async def stop(self) -> None:
        """Stop playback and clear the current track."""
        await self._request(API_ENDPOINT_STOP)

    async def next_track(self) -> None:
        """Skip to the next track in the playlist."""
        await self._request(API_ENDPOINT_NEXT)

    async def previous_track(self) -> None:
        """Return to the previous track in the playlist."""
        await self._request(API_ENDPOINT_PREV)

    async def set_volume(self, volume: float) -> None:
        """Set the volume level.

        Args:
            volume: Volume level between 0 and 1.
        """
        volume_pct = int(volume * 100)
        await self._request(f"{API_ENDPOINT_VOLUME}{volume_pct}")

    async def set_mute(self, mute: bool) -> None:
        """Set the mute state.

        Args:
            mute: True to mute, False to unmute.
        """
        await self._request(f"{API_ENDPOINT_MUTE}{1 if mute else 0}")

    async def set_power(self, power: bool) -> None:
        """Set the power state.

        Args:
            power: True to turn on, False to turn off.
        """
        await self._request(f"{API_ENDPOINT_POWER}{1 if power else 0}")

    async def set_repeat_mode(self, mode: str) -> None:
        """Set the repeat mode.

        Args:
            mode: One of PLAY_MODE_NORMAL, PLAY_MODE_REPEAT_ALL, or PLAY_MODE_REPEAT_ONE.

        Raises:
            ValueError: If an invalid repeat mode is specified.
        """
        if mode not in (PLAY_MODE_NORMAL, PLAY_MODE_REPEAT_ALL, PLAY_MODE_REPEAT_ONE):
            raise ValueError(f"Invalid repeat mode: {mode}")
        await self._request(f"{API_ENDPOINT_REPEAT}{mode}")

    async def set_shuffle_mode(self, mode: str) -> None:
        """Set the shuffle mode.

        Args:
            mode: One of PLAY_MODE_NORMAL, PLAY_MODE_SHUFFLE, or PLAY_MODE_SHUFFLE_REPEAT_ALL.

        Raises:
            ValueError: If an invalid shuffle mode is specified.
        """
        if mode not in (
            PLAY_MODE_NORMAL,
            PLAY_MODE_SHUFFLE,
            PLAY_MODE_SHUFFLE_REPEAT_ALL,
        ):
            raise ValueError(f"Invalid shuffle mode: {mode}")
        await self._request(f"{API_ENDPOINT_SHUFFLE}{mode}")

    async def seek(self, position: int) -> None:
        """Seek to a specific position in the current track.

        Args:
            position: Position in seconds from the start of the track.
        """
        await self._request(f"{API_ENDPOINT_SEEK}{position}")

    async def clear_playlist(self) -> None:
        """Clear the current playlist."""
        await self._request(API_ENDPOINT_CLEAR_PLAYLIST)

    # Multiroom
    async def get_multiroom_status(self) -> dict[str, Any]:
        """Get multiroom status including master/slave relationships."""
        status = await self.get_status()
        multiroom = status.get("multiroom", {})

        # Update internal state
        self._group_master = multiroom.get("master")
        self._group_slaves = multiroom.get("slaves", [])

        return multiroom

    async def create_group(self) -> None:
        """Create a multiroom group and become the master.

        The original (legacy) LinkPlay command for turning the *current* device
        into a master of a new multi-room group is::

            /httpapi.asp?command=setMultiroom:Master

        Recent LinkPlay firmware builds (4.8+, WiiM 2024.
        xx) deprecated that endpoint and replaced it with the symmetrical
        ``ConnectMasterAp:CreateGroupMaster`` variant that mirrors the
        *join* syntax.  Unfortunately not all firmwares expose **both**
        commands which means we have to try the new one first and gracefully
        fall back to the legacy one.

        After sending the command we *verify* that the device actually became
        a master by polling the multi-room status.  If the verification fails
        we raise :class:`WiiMError` so callers can abort the join flow instead
        of continuing with a half-created group (which ultimately led to the
        "Could not find coordinator" warnings seen in the logs).
        """

        _LOGGER.debug("[WiiM] Creating multiroom group on %s", self.host)

        # 1) Preferred modern endpoint (firmware ≥ 4.8)
        cmd_modern = (
            f"/httpapi.asp?command=ConnectMasterAp:CreateGroupMaster:eth{self.host}:wifi0.0.0.0"
        )

        # 2) Legacy endpoint kept for backwards compatibility
        cmd_legacy = API_ENDPOINT_GROUP_CREATE  # setMultiroom:Master

        errors: list[str] = []

        for cmd in (cmd_modern, cmd_legacy):
            try:
                resp = await self._request(cmd)
                raw_resp = resp.get("raw") if isinstance(resp, dict) else None
                # A lot of firmwares respond with plain text.  Treat *anything*
                # that isn't an explicit "OK" as a failure so we try the next
                # variant.
                if raw_resp is not None and raw_resp.strip().upper() != "OK":
                    raise WiiMError(f"Device answered {raw_resp!r}")

                # Give the speaker a brief moment to switch roles then verify
                await asyncio.sleep(0.1)

                # Consider the command successful if we received the expected
                # 'OK' reply.  We still update our internal bookkeeping so
                # higher-level helpers treat us as master from now on.
                self._group_master = self.host
                self._group_slaves = []
                _LOGGER.debug(
                    "[WiiM] Group successfully created on %s using %s", self.host, cmd
                )
                return
            except Exception as err:  # noqa: BLE001 – broad on purpose, we'll raise later
                _LOGGER.debug(
                    "[WiiM] Failed to create group on %s using %s: %s", self.host, cmd, err
                )
                errors.append(f"{cmd} → {err}")

        # If we reach this point every attempt failed
        error_msg = (
            "Unable to create multi-room group. Tried the following commands: "
            + "; ".join(errors)
        )
        raise WiiMError(error_msg)

    async def delete_group(self) -> None:
        """Delete the current multiroom group."""
        if not self._group_master:
            raise WiiMError("Not part of a multiroom group")
        _LOGGER.debug("[WiiM] Deleting multiroom group on %s", self.host)
        await self._request(API_ENDPOINT_GROUP_DELETE)
        self._group_master = None
        self._group_slaves = []

    async def join_group(self, master_ip: str) -> None:
        """Join a multiroom group as a slave."""
        # Check actual device state before raising error
        multiroom = await self.get_multiroom_info()
        if str(multiroom.get("type")) == "1" or self._group_master:
            # Try to leave group first
            try:
                await self.leave_group()
            except Exception:
                pass  # Ignore errors, try to join anyway
        _LOGGER.debug("[WiiM] %s joining group with master %s", self.host, master_ip)
        endpoint = API_ENDPOINT_GROUP_JOIN.format(ip=master_ip)
        await self._request(endpoint)
        self._group_master = master_ip
        self._group_slaves = []

    async def leave_group(self) -> None:
        """Leave the current multiroom group."""
        _LOGGER.debug("[WiiM] %s leaving group", self.host)
        await self._request(API_ENDPOINT_GROUP_EXIT)
        self._group_master = None
        self._group_slaves = []

    @property
    def is_master(self) -> bool:
        """Return whether this device is a multiroom master."""
        return self._group_master == self.host

    @property
    def is_slave(self) -> bool:
        """Return whether this device is a multiroom slave."""
        return self._group_master is not None and not self.is_master

    @property
    def group_master(self) -> str | None:
        """Return the IP of the group master if part of a group."""
        return self._group_master

    @property
    def group_slaves(self) -> list[str]:
        """Return list of slave IPs if this device is a master."""
        return self._group_slaves if self.is_master else []

    # EQ Controls
    async def set_eq_preset(self, preset: str) -> None:
        """Set EQ preset.

        The LinkPlay firmware expects the **human-readable** preset label
        (e.g. ``EQLoad:Flat``) while our Home-Assistant code traditionally
        works with the lower-case *key* (``flat``).  Convert the key to the
        label before sending the request so the command succeeds on all
        firmware builds.
        """

        if preset not in EQ_PRESET_MAP:
            raise ValueError(f"Invalid EQ preset: {preset}")

        # Convert internal key → device label ("flat" → "Flat")
        api_value = EQ_PRESET_MAP[preset]

        await self._request(f"{API_ENDPOINT_EQ_PRESET}{api_value}")

    async def set_eq_custom(self, eq_values: list[int]) -> None:
        """Set custom EQ values (10 bands)."""
        if len(eq_values) != 10:
            raise ValueError("EQ must have exactly 10 bands")
        eq_str = ",".join(str(v) for v in eq_values)
        await self._request(f"{API_ENDPOINT_EQ_CUSTOM}{eq_str}")

    async def get_eq(self) -> dict[str, Any]:
        """Get current EQ settings."""
        return await self._request(API_ENDPOINT_EQ_GET)

    async def set_eq_enabled(self, enabled: bool) -> None:
        """Enable or disable EQ."""
        endpoint = API_ENDPOINT_EQ_ON if enabled else API_ENDPOINT_EQ_OFF
        await self._request(endpoint)

    async def get_eq_status(self) -> bool:
        """Return *True* if the device reports that EQ is enabled.

        Not all firmware builds implement ``EQGetStat`` – many return the
        generic ``{"status":"Failed"}`` payload instead.  In that case we
        fall back to calling ``getEQ``: if the speaker answers *anything*
        other than *unknown command* we assume that EQ support is present
        and therefore enabled.
        """

        try:
            response = await self._request(API_ENDPOINT_EQ_STATUS)

            # Normal, spec-compliant reply → {"EQStat":"On"|"Off"}
            if "EQStat" in response:
                return str(response["EQStat"]).lower() == "on"

            # Some firmwares return {"status":"Failed"} for unsupported
            # commands – treat this as *unknown* and use a heuristic.
            if str(response.get("status", "")).lower() == "failed":
                # If /getEQ succeeds we take that as evidence that the EQ
                # subsystem is operational which implies it is *enabled*.
                try:
                    await self._request(API_ENDPOINT_EQ_GET)
                    return True
                except WiiMError:
                    return False

            # Fallback – any other structure counts as EQ disabled.
            return False

        except WiiMError:
            # On explicit request errors assume EQ disabled so callers can
            # still proceed without raising.
            return False

    async def get_eq_presets(self) -> list[str]:
        """Get list of available EQ presets."""
        response = await self._request(API_ENDPOINT_EQ_LIST)
        return response if isinstance(response, list) else []

    # Source Selection
    async def set_source(self, source: str) -> None:
        """Set input source."""
        await self._request(f"{API_ENDPOINT_SOURCE}{source}")

    async def get_sources(self) -> list[str]:
        """Fetch available input sources from the device."""
        response = await self._request(API_ENDPOINT_SOURCES)
        _LOGGER.debug("[WiiM] get_sources response: %s", response)
        sources = response.get("sources", [])
        _LOGGER.debug("[WiiM] parsed sources: %s", sources)
        return sources

    # Device Info
    async def get_device_info(self) -> dict[str, Any]:
        """Get device information."""
        return await self._request(API_ENDPOINT_DEVICE_INFO)

    async def get_firmware_version(self) -> str:
        """Get firmware version."""
        response = await self._request(API_ENDPOINT_FIRMWARE)
        return response.get("firmware", "")

    async def get_mac_address(self) -> str:
        """Get MAC address."""
        response = await self._request(API_ENDPOINT_MAC)
        return response.get("mac", "")

    # LED Control
    async def set_led(self, enabled: bool) -> None:
        """Set LED state."""
        await self._request(f"{API_ENDPOINT_LED}{1 if enabled else 0}")

    async def set_led_brightness(self, brightness: int) -> None:
        """Set LED brightness (0-100)."""
        if not 0 <= brightness <= 100:
            raise ValueError("Brightness must be between 0 and 100")
        await self._request(f"{API_ENDPOINT_LED_BRIGHTNESS}{brightness}")

    async def play_preset(self, preset: int) -> None:
        """Play a preset (1-6)."""
        if not 1 <= preset <= 6:
            raise ValueError("Preset must be between 1 and 6")
        await self._request(f"{API_ENDPOINT_PRESET}{preset}")

    async def toggle_power(self) -> None:
        """Toggle power state."""
        status = await self.get_status()
        power = status.get("power", False)
        await self.set_power(not power)

    # ---------------------------------------------------------------------
    # Extended helpers -----------------------------------------------------
    # ---------------------------------------------------------------------

    async def get_player_status(self) -> dict[str, Any]:
        """Return a **normalised** status dict.

        This method fetches the current player status using the getPlayerStatus endpoint.
        The raw payload is converted to a stable schema so the rest of the
        integration can rely on consistent keys.

        Returns:
            A dictionary containing normalized player status including:
            - play_status: Current playback state (play/pause/stop)
            - volume: Current volume level (0-100)
            - mute: Current mute state
            - position: Current playback position in seconds
            - duration: Total duration of current track in seconds
            - title: Current track title
            - artist: Current track artist
            - album: Current track album
            - source: Current audio source
            - play_mode: Current play mode (normal/repeat/shuffle)
        """
        from .const import API_ENDPOINT_PLAYER_STATUS

        try:
            raw: dict[str, Any] = await self._request(API_ENDPOINT_PLAYER_STATUS)
        except WiiMError:
            # Fallback to basic status if player status fails
            raw = await self._request(API_ENDPOINT_STATUS)

        return self._parse_player_status(raw)

    # Normalisation table for the *player-status* endpoint.  Keys on the left
    # are raw HTTP-API field names, values are our canonical attribute names
    # used throughout the integration.
    _STATUS_MAP: dict[str, str] = {
        "status": "play_status",
        "vol": "volume",
        "mute": "mute",
        "eq": "eq_preset",
        "EQ": "eq_preset",        # Some firmwares use upper-case EQ
        "eq_mode": "eq_preset",   # Seen on recent builds (e.g. W281)
        "loop": "loop_mode",
        "curpos": "position_ms",
        "totlen": "duration_ms",
        "Title": "title_hex",
        "Artist": "artist_hex",
        "Album": "album_hex",
        "DeviceName": "device_name",
        # Wi-Fi (only present in fallback)
        "WifiChannel": "wifi_channel",
        "RSSI": "wifi_rssi",
    }

    # Mapping of ``mode`` codes → canonical source names.
    _MODE_MAP: dict[str, str] = {
        "0": "idle",        # idle/unknown
        "1": "airplay",
        "2": "dlna",
        "3": "wifi",        # network / built-in streamer / vTuner etc.
        "4": "line_in",
        "5": "bluetooth",
        "6": "optical",
        "10": "wifi",       # many firmwares report 10 for NET/Streamer
        "11": "usb",        # local U-Disk playback
        "20": "wifi",       # HTTPAPI initiated play
        "31": "spotify",    # Spotify Connect session active
        "40": "line_in",
        "41": "bluetooth",
        "43": "optical",
        "47": "line_in_2",
        "51": "usb",        # USB-DAC on WiiM Pro Plus
        "99": "follower",   # guest/relay in multiroom
    }

    # Map numeric EQ codes → canonical preset strings understood by the
    # rest of the integration.
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

    def _parse_player_status(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Parse the raw player status response into a normalized format.

        Args:
            raw: The raw response from the device.

        Returns:
            A dictionary containing normalized player status.
        """
        _LOGGER.debug("Parsing raw player status: %s", raw)

        data: dict[str, Any] = {}

        # Map raw keys to normalized keys
        for k, v in raw.items():
            key = self._STATUS_MAP.get(k, k)
            data[key] = v

        # Decode hex-encoded metadata
        data["title"] = _hex_to_str(raw.get("Title")) or raw.get("title")
        data["artist"] = _hex_to_str(raw.get("Artist")) or raw.get("artist")
        data["album"] = _hex_to_str(raw.get("Album")) or raw.get("album")

        # Power state (default to ON if not specified)
        data.setdefault("power", True)

        # Wi-Fi diagnostics
        if "wifi_channel" not in data and raw.get("wifi_channel"):
            data["wifi_channel"] = raw["wifi_channel"]
        if "wifi_rssi" not in data and raw.get("wifi_rssi"):
            data["wifi_rssi"] = raw["wifi_rssi"]

        # Volume normalization (0-1 float)
        if (vol := raw.get("vol")) is not None:
            try:
                vol_int = int(vol)
                data["volume_level"] = vol_int / 100
                data["volume"] = vol_int
            except ValueError:
                _LOGGER.warning("Invalid volume value: %s", vol)

        # Position and duration in seconds
        if raw.get("curpos"):
            data["position"] = int(raw["curpos"]) // 1_000
            data["position_updated_at"] = asyncio.get_running_loop().time()
        if raw.get("totlen"):
            data["duration"] = int(raw["totlen"]) // 1_000

        # Convert mute state to boolean
        if "mute" in data:
            try:
                data["mute"] = bool(int(data["mute"]))
            except (TypeError, ValueError):
                data["mute"] = bool(data["mute"])

        # Map play mode from LinkPlay loop code
        if "play_mode" not in data and "loop_mode" in data:
            try:
                loop_val = int(data["loop_mode"])
            except (TypeError, ValueError):
                loop_val = 4  # default = normal

            if loop_val == 0:
                data["play_mode"] = PLAY_MODE_REPEAT_ALL
            elif loop_val == 1:
                data["play_mode"] = PLAY_MODE_REPEAT_ONE
            elif loop_val == 2:
                data["play_mode"] = PLAY_MODE_SHUFFLE_REPEAT_ALL
            elif loop_val == 3:
                data["play_mode"] = PLAY_MODE_SHUFFLE
            else:
                data["play_mode"] = PLAY_MODE_NORMAL

        # Artwork URL – vendors use a **lot** of different keys.  Try the
        # known variants in priority order so the first *non-empty* match wins.
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
            data["entity_picture"] = cover

        # ---------------------------------------------------------------
        # Current *input* source – derived from ``mode`` field.  Not all
        # firmwares expose ``source`` directly; adding it here enables the
        # media-player UI to show e.g. "AirPlay" when streaming from iOS.
        # ---------------------------------------------------------------
        mode_val = raw.get("mode")
        if mode_val is not None and "source" not in data:
            data["source"] = self._MODE_MAP.get(str(mode_val), "unknown")

        # ---------------------------------------------------------------
        # EQ preset – convert **numeric** codes to their textual alias so
        # the frontend can display a meaningful name and the service
        # calls keep working with the usual strings.
        # ---------------------------------------------------------------
        eq_raw = data.get("eq_preset")
        if isinstance(eq_raw, (int, str)) and str(eq_raw).isdigit():
            data["eq_preset"] = self._EQ_NUMERIC_MAP.get(str(eq_raw), eq_raw)

        _LOGGER.debug("Parsed player status: %s", data)
        return data

    async def get_multiroom_info(self) -> dict[str, Any]:
        """Get multiroom status."""
        response = await self._request(API_ENDPOINT_GROUP_SLAVES)
        _LOGGER.debug("[WiiM] get_multiroom_info response for %s: %s", self.host, response)
        # Try to set group_master for slave
        if "master" in response:
            self._group_master = response["master"]
            _LOGGER.debug("[WiiM] %s: Set group_master from 'master' field: %s", self.host, self._group_master)
        elif "master_ip" in response:
            self._group_master = response["master_ip"]
            _LOGGER.debug("[WiiM] %s: Set group_master from 'master_ip' field: %s", self.host, self._group_master)
        elif "master_uuid" in response:
            self._group_master = response["master_uuid"]
            _LOGGER.debug("[WiiM] %s: Set group_master from 'master_uuid' field: %s", self.host, self._group_master)
        else:
            self._group_master = None
            _LOGGER.debug("[WiiM] %s: No master info found in group info response.", self.host)
        return response

    async def kick_slave(self, slave_ip: str) -> None:
        """Remove a slave device from the group."""
        if not self.is_master:
            raise WiiMError("Not a group master")
        _LOGGER.debug("[WiiM] Kicking slave %s from group", slave_ip)
        await self._request(f"{API_ENDPOINT_GROUP_KICK}{slave_ip}")

    async def mute_slave(self, slave_ip: str, mute: bool) -> None:
        """Mute/unmute a slave device."""
        if not self.is_master:
            raise WiiMError("Not a group master")
        _LOGGER.debug("[WiiM] Setting mute=%s for slave %s", mute, slave_ip)
        await self._request(f"{API_ENDPOINT_GROUP_SLAVE_MUTE}{slave_ip}:{1 if mute else 0}")

    # ---------------------------------------------------------------------
    # Diagnostic / maintenance helpers
    # ---------------------------------------------------------------------

    async def reboot(self) -> None:
        """Reboot the device via HTTP API."""
        await self._request("/httpapi.asp?command=reboot")

    async def sync_time(self, ts: int | None = None) -> None:
        """Synchronise device RTC with Unix timestamp (defaults to *now*)."""
        if ts is None:
            ts = int(asyncio.get_running_loop().time())
        await self._request(f"/httpapi.asp?command=timeSync:{ts}")

    async def get_meta_info(self) -> dict[str, Any]:
        """Get current track metadata including album art."""
        try:
            response = await self._request("/httpapi.asp?command=getMetaInfo")
            return response.get("metaData", {})
        except Exception as e:
            # Devices with older firmware return plain "OK" instead of JSON.
            # Treat this as an expected condition rather than an error.
            _LOGGER.debug("get_meta_info not supported on %s: %s", self.host, e)
            return {}

    async def play_url(self, url: str) -> None:
        """Play a URL."""
        encoded_url = quote(url)
        await self._request(f"{API_ENDPOINT_PLAY_URL}{encoded_url}")

    async def play_playlist(self, playlist_url: str) -> None:
        """Play an M3U playlist."""
        encoded_url = quote(playlist_url)
        await self._request(f"{API_ENDPOINT_PLAY_M3U}{encoded_url}")

    async def play_notification(self, url: str) -> None:
        """Play a notification sound (lowers volume, plays, then restores)."""
        from .const import API_ENDPOINT_PLAY_PROMPT_URL
        from urllib.parse import quote
        encoded_url = quote(url, safe="")
        await self._request(f"{API_ENDPOINT_PLAY_PROMPT_URL}{encoded_url}")

    @property
    def base_url(self) -> str:  # noqa: D401 – simple property helper
        """Return the base URL for the device (scheme://host:port)."""
        return self._base_url


# ---------------------------------------------------------------------------
# --- low-level helpers (adapted from python-linkplay, MIT) ------------------
# ---------------------------------------------------------------------------

# The WiiM integration interacts with the speaker exclusively through the
# HTTP API exposed on ``https://<ip>/httpapi.asp?command=...``.  The three
# convenience helpers below replicate the tiny helper layer that the
# *python-linkplay* library offers so that our high-level code remains compact
# and easy to unit-test.  They purposefully depend **only** on ``aiohttp`` and
# the Python standard library.


async def _ensure_session(base_ssl_ctx: ssl.SSLContext | None) -> ClientSession:  # type: ignore
    """Create a throw-away :class:`aiohttp.ClientSession` with our SSL context.

    Helper for users that do not provide a session; we open one and make sure
    the connector uses the given SSL context (or default verification disabled
    if *None*).  The caller is responsible for closing it.
    """

    if base_ssl_ctx is None:
        connector = aiohttp.TCPConnector(ssl=False)
    else:
        connector = aiohttp.TCPConnector(ssl=base_ssl_ctx)

    return aiohttp.ClientSession(connector=connector)


async def session_call_api(endpoint: str, session: ClientSession, command: str) -> str:
    """Perform a **single GET** to the LinkPlay HTTP API and return raw text.

    Parameters
    ----------
    endpoint
        Base URL including scheme/host/port, *without* trailing slash, e.g.
        ``https://192.168.1.10:443``.
    session
        An *aiohttp* :class:`ClientSession` instance.
    command
        The command part of the API call, for example ``getStatusEx``.
    """

    url = f"{endpoint}/httpapi.asp?command={command}"

    try:
        async with async_timeout.timeout(DEFAULT_TIMEOUT):
            response = await session.get(url, headers=HEADERS)
    except (asyncio.TimeoutError, ClientError, asyncio.CancelledError) as err:
        raise WiiMRequestError(f"{err} error requesting data from '{url}'") from err

    if response.status != HTTPStatus.OK:
        raise WiiMRequestError(
            f"Unexpected HTTP status {response.status} received from '{url}'"
        )

    return await response.text()


async def session_call_api_json(
    endpoint: str, session: ClientSession, command: str
) -> dict[str, str]:
    """Call the API and JSON-decode the response."""

    raw = await session_call_api(endpoint, session, command)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WiiMInvalidDataError(
            f"Unexpected JSON ({raw[:80]}…) received from '{endpoint}'"
        ) from exc


async def session_call_api_ok(endpoint: str, session: ClientSession, command: str) -> None:
    """Call the API and assert the speaker answers exactly 'OK'."""

    result = await session_call_api(endpoint, session, command)
    if result.strip() != "OK":
        raise WiiMRequestError(
            f"Didn't receive expected 'OK' from {endpoint} (got {result!r})"
        )


def _hex_to_str(val: str | None) -> str | None:
    """Decode hex‐encoded UTF-8 strings used by LinkPlay for metadata."""
    if not val:
        return None
    try:
        return bytes.fromhex(val).decode("utf-8", errors="replace")
    except ValueError:
        return val  # already plain
