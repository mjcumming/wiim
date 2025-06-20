"""WiiM HTTP API client.

Provides asynchronous methods for controlling WiiM and LinkPlay speakers.
Handles multiple communication protocols and device variations defensively.

Features:
    - Multi-protocol auto-detection with HTTPS preference
    - Device capability probing and graceful fallbacks
    - Rich data normalization and consistent response formatting
    - Comprehensive error handling and recovery strategies

Security:
    - Tries HTTPS first (ports 443, 4443), then HTTP (port 80) as fallback
    - Handles device-specific SSL certificates with permissive context
    - Maintains session security and proper cleanup

Reliability:
    - Automatic protocol and port detection across device variations
    - Defensive capability detection for enhanced features
    - Graceful degradation when advanced endpoints are unavailable
    - Rich error context for integration-level troubleshooting

Usage:
    async with WiiMClient("192.168.1.100") as client:
        status = await client.get_player_status()
        await client.play()
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

from .const import (
    API_ENDPOINT_CLEAR_PLAYLIST,
    API_ENDPOINT_EQ_CUSTOM,
    API_ENDPOINT_EQ_GET,
    API_ENDPOINT_EQ_LIST,
    API_ENDPOINT_EQ_OFF,
    API_ENDPOINT_EQ_ON,
    API_ENDPOINT_EQ_PRESET,
    API_ENDPOINT_EQ_STATUS,
    API_ENDPOINT_FIRMWARE,
    API_ENDPOINT_GROUP_EXIT,
    API_ENDPOINT_GROUP_KICK,
    API_ENDPOINT_GROUP_SLAVE_MUTE,
    API_ENDPOINT_GROUP_SLAVES,
    API_ENDPOINT_LED,
    API_ENDPOINT_LED_BRIGHTNESS,
    API_ENDPOINT_MAC,
    API_ENDPOINT_MUTE,
    API_ENDPOINT_NEXT,
    API_ENDPOINT_PAUSE,
    API_ENDPOINT_PLAY,
    API_ENDPOINT_PLAY_M3U,
    API_ENDPOINT_PLAY_PROMPT_URL,
    API_ENDPOINT_PLAY_URL,
    API_ENDPOINT_POWER,
    API_ENDPOINT_PRESET,
    API_ENDPOINT_PREV,
    API_ENDPOINT_REPEAT,
    API_ENDPOINT_SEEK,
    API_ENDPOINT_SHUFFLE,
    API_ENDPOINT_SOURCE,
    API_ENDPOINT_SOURCES,
    API_ENDPOINT_STATUS,
    API_ENDPOINT_STOP,
    API_ENDPOINT_VOLUME,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    EQ_PRESET_MAP,
    PLAY_MODE_NORMAL,
    PLAY_MODE_REPEAT_ALL,
    PLAY_MODE_REPEAT_ONE,
    PLAY_MODE_SHUFFLE,
    PLAY_MODE_SHUFFLE_REPEAT_ALL,
)

# Pydantic models (optional validation layer)
from pydantic import ValidationError

from .models import PlayerStatus, DeviceInfo

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
    - Automatic protocol detection (HTTP/HTTPS) with smart fallback
    - Comprehensive error handling and logging
    - Support for device grouping and multiroom functionality
    - Volume and playback control
    - Device status monitoring and diagnostics

    Attributes:
        host (str): The IP address or hostname of the WiiM device
        port (int): The port number for the HTTP API (default: 443 for HTTPS)
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
        - Tries HTTPS first (ports 443, 4443), then HTTP (port 80) as fallback
        - Handles device-specific SSL certificates with permissive context
        - Maintains session security and proper cleanup
    """

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,  # Default to HTTPS like python-linkplay
        timeout: float = DEFAULT_TIMEOUT,
        ssl_context: ssl.SSLContext | None = None,
        session: ClientSession | None = None,
    ) -> None:
        """Initialize the WiiM client.

        Args:
            host: The IP address or hostname of the WiiM device, optionally with port (e.g., "192.168.1.100:49152").
            port: The port number for the HTTP API (default: 443 for HTTPS). Ignored if host contains port.
            timeout: Request timeout in seconds (default: 10.0).
            ssl_context: SSL context for HTTPS connections.
            session: Optional aiohttp ClientSession to use for requests.
        """
        # -------------------------------------------------------------
        # Host / port parsing with proper IPv6 support
        # -------------------------------------------------------------
        # We keep two internal representations:
        #   1. _host        – the raw host *without* brackets (for logging)
        #   2. _host_url    – host normalised for use inside URLs (IPv6 → [addr])

        self._discovered_port: bool = False

        if ":" in host and not host.startswith("["):
            # Could be "ip:port" *or* an un-bracketed IPv6 literal. We first try the
            # ip:port parse and fall back to treating it as pure host on failure.
            try:
                parsed_host, parsed_port_str = host.rsplit(":", 1)
                self.port = int(parsed_port_str)
                self._host = parsed_host
                self._discovered_port = True
                _LOGGER.debug("Parsed host '%s' into host='%s', port=%d", host, parsed_host, self.port)
            except (ValueError, TypeError):
                # Not a valid "host:port" → treat the full string as host (IPv6 literal)
                self._host = host
                self.port = port
                _LOGGER.debug("Host '%s' looks like IPv6 literal – using default port %d", host, port)
        else:
            # Already bracketed IPv6 or simple hostname/IPv4
            self._host = host
            self.port = port

        # Normalise host for URL usage – wrap bare IPv6 literals in [brackets]
        if ":" in self._host and not self._host.startswith("["):
            self._host_url = f"[{self._host}]"
        else:
            self._host_url = self._host

        self.timeout = timeout
        self.ssl_context = ssl_context
        self._session = session

        # Start with HTTPS endpoint, will auto-detect if fallback is needed
        self._endpoint = f"https://{self._host_url}:{self.port}"
        self._lock = asyncio.Lock()
        self._group_master: str | None = None
        self._group_slaves: list[str] = []
        # Track/play-mode change detection helpers
        self._last_track: str | None = None
        self._last_play_mode: str | None = None
        # Some firmwares ship a *device-unique* self-signed certificate.  We
        # start optimistic (verify on) and permanently fall back to
        # *insecure* mode after the first verification failure to avoid the
        # noisy SSL errors on every poll.
        self._verify_ssl_default: bool = True

    @property
    def host(self) -> str:
        """Return the host address (without port)."""
        return self._host

    def _get_ssl_context(self) -> ssl.SSLContext:
        """Return (and lazily create) a permissive SSL context for WiiM devices.

        WiiM devices often use self-signed certificates, older TLS versions,
        and weaker cipher suites. This creates a permissive context that
        can handle these older devices while still providing some security.
        """
        if self.ssl_context is not None:
            return self.ssl_context

        # Create a permissive TLS context for older devices
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        # Disable hostname and certificate verification (self-signed certs)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # Allow older TLS versions that some devices might need
        ctx.minimum_version = ssl.TLSVersion.TLSv1
        ctx.maximum_version = ssl.TLSVersion.TLSv1_3

        # Set permissive cipher suites for compatibility
        ctx.set_ciphers("ALL:@SECLEVEL=0")  # Allow weaker ciphers for compatibility

        try:
            # Still try to load the WiiM CA certificate for reference
            ctx.load_verify_locations(cadata=WIIM_CA_CERT)
            _LOGGER.debug("Loaded WiiM CA certificate for %s", self.host)
        except Exception as e:
            _LOGGER.debug(
                "Failed to load WiiM CA certificate for %s: %s (continuing with permissive context)",
                self.host,
                e,
            )

        self.ssl_context = ctx
        return self.ssl_context

    async def _request(
        self,
        endpoint: str,
        method: str = "GET",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make a request to the WiiM device with smart protocol detection.

        Tries HTTPS first (ports 443, 4443), then HTTP (port 80) as fallback.
        WiiM devices typically support HTTPS with self-signed certificates.
        If a specific port was discovered (e.g., from SSDP/Zeroconf), that port
        takes priority over default ports.

        Args:
            endpoint: API endpoint path (e.g., "/httpapi.asp?command=getPlayerStatus")
            method: HTTP method ("GET" or "POST")
            **kwargs: Additional arguments passed to aiohttp

        Returns:
            Parsed JSON response from the device

        Raises:
            WiiMRequestError: Network/HTTP errors during request
            WiiMError: Invalid response or parsing errors
        """
        if self._session is None or self._session.closed:
            # aiohttp>=3.9 requires a ClientTimeout object
            timeout_obj = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout_obj)

        kwargs.setdefault("headers", HEADERS)

        # -----------------------------------------------------------------
        # FAST PATH: reuse last known-good endpoint to skip expensive probes
        # -----------------------------------------------------------------
        if hasattr(self, "_endpoint") and self._endpoint:
            from urllib.parse import urlsplit

            try:
                parsed = urlsplit(self._endpoint)
                scheme = parsed.scheme
                host_only = parsed.hostname or ""
                port_num = parsed.port or self.port

                # Re-add brackets for IPv6 when building the URL
                host_for_url = f"[{host_only}]" if ":" in host_only and not host_only.startswith("[") else host_only

                fast_url = f"{scheme}://{host_for_url}:{port_num}{endpoint}"
                _LOGGER.debug("Fast-path %s request to %s", method, fast_url)

                # SSL context only for https scheme
                if scheme == "https":
                    ssl_ctx_fast = self._get_ssl_context()
                    kwargs["ssl"] = ssl_ctx_fast
                else:
                    kwargs.pop("ssl", None)

                async with async_timeout.timeout(self.timeout):
                    async with self._session.request(method, fast_url, **kwargs) as response:
                        response.raise_for_status()
                        text = await response.text()
                        _LOGGER.debug("Fast-path response from %s: %s", fast_url, text[:200])

                        if text.strip() == "OK":
                            return {"raw": text.strip()}
                        return json.loads(text)
            except Exception as err:
                _LOGGER.debug("Fast-path attempt failed (%s), falling back to probe list", err)

        # If we have a discovered port, prioritize that
        if self._discovered_port:
            # For discovered ports, try both HTTPS and HTTP on the same port
            protocols_to_try = [
                ("https", self.port, self._get_ssl_context()),  # Discovered port with HTTPS
                ("http", self.port, None),  # Discovered port with HTTP
            ]
            _LOGGER.debug("Using discovered port %d for %s", self.port, self._host)
        else:
            # Standard probing order: try secure HTTPS ports first, then fall
            # back to *plain* HTTP on port 80 as a last resort so older
            # LinkPlay builds without TLS still work.  This adds one extra
            # connection attempt only when the secure ones failed, keeping
            # the log noise minimal while regaining compatibility.

            protocols_to_try = [
                ("https", 443, self._get_ssl_context()),  # HTTPS primary
                ("https", 4443, self._get_ssl_context()),  # HTTPS alternate
                ("http", 80, None),  # HTTP fallback (legacy)
            ]

            # If user specified a custom port, try that with both protocols first
            if self.port not in (80, 443):
                protocols_to_try.insert(0, ("https", self.port, self._get_ssl_context()))
                protocols_to_try.insert(1, ("http", self.port, None))

        tried: list[str] = []
        last_error: Exception | None = None

        for scheme, port, ssl_context in protocols_to_try:
            host_for_url_loop = f"[{self._host}]" if ":" in self._host and not self._host.startswith("[") else self._host
            url = f"{scheme}://{host_for_url_loop}:{port}{endpoint}"
            tried.append(url)

            # Set SSL context for HTTPS requests only
            if scheme == "https":
                kwargs["ssl"] = ssl_context
            else:
                kwargs.pop("ssl", None)  # Remove SSL for HTTP requests

            try:
                _LOGGER.debug("Making %s request to %s", method, url)
                async with async_timeout.timeout(self.timeout):
                    async with self._session.request(method, url, **kwargs) as response:
                        response.raise_for_status()
                        text = await response.text()
                        _LOGGER.debug("Response from %s: %s", url, text[:200])

                        # Success! Update our endpoint for future requests (store in URL form)
                        self._endpoint = f"{scheme}://{host_for_url_loop}:{port}"

                        if text.strip() == "OK":
                            return {"raw": text.strip()}
                        return json.loads(text)

            except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as err:
                last_error = err
                _LOGGER.debug("Failed %s request to %s: %s", method, url, err)

                # For JSON decode errors, treat as successful raw response
                if isinstance(err, json.JSONDecodeError):
                    _LOGGER.debug("Non-JSON response from %s: %s", url, text[:200])
                    self._endpoint = f"{scheme}://{host_for_url_loop}:{port}"
                    return {"raw": text.strip()}

                # Continue to next protocol/port
                continue

            except RuntimeError as err:
                # Handle session closed errors gracefully
                if "session is closed" in str(err).lower():
                    _LOGGER.debug("Session closed for %s, recreating session", self._host)
                    try:
                        if self._session and not self._session.closed:
                            await self._session.close()
                    except Exception:
                        pass  # Ignore errors when closing

                    # Retry once with new session
                    timeout_obj = aiohttp.ClientTimeout(total=self.timeout)
                    self._session = aiohttp.ClientSession(timeout=timeout_obj)

                    try:
                        if scheme == "https":
                            kwargs["ssl"] = ssl_context
                        else:
                            kwargs.pop("ssl", None)

                        async with async_timeout.timeout(self.timeout):
                            async with self._session.request(method, url, **kwargs) as response:
                                response.raise_for_status()
                                text = await response.text()
                                _LOGGER.debug("Retry response from %s: %s", url, text[:200])

                                self._endpoint = f"{scheme}://{host_for_url_loop}:{port}"

                                if text.strip() == "OK":
                                    return {"raw": text.strip()}
                                return json.loads(text)
                    except Exception as retry_err:
                        last_error = retry_err
                        _LOGGER.debug("Retry failed for %s: %s", url, retry_err)
                        continue
                else:
                    last_error = err
                    continue

        # If we get here, all attempts failed
        error_msg = "Failed to communicate with WiiM device at {} after trying: {}".format(self._host, ", ".join(tried))
        if last_error:
            error_msg += f"\nLast error: {last_error}"
        raise WiiMConnectionError(error_msg)

    async def close(self) -> None:
        """Close the client session.

        This should be called when the client is no longer needed to properly
        clean up resources.
        """
        if self._session:
            try:
                if not self._session.closed:
                    await self._session.close()
            except Exception as e:
                _LOGGER.debug("Error closing session for %s: %s", self.host, e)
            finally:
                self._session = None

    async def validate_connection(self) -> bool:
        """Simple connection validation for discovery/config flow.

        Returns:
            True if device responds to basic API call, False otherwise.
        """
        try:
            await self.get_player_status()
            return True
        except WiiMError:
            return False

    async def get_device_name(self) -> str:
        """Get device name for discovery/config flow.

        Simple method that tries to get device name from DeviceName field,
        falling back to IP address. No complex multiroom status or multiple
        API endpoint attempts - keeps config flow fast and simple.

        Returns:
            Device name or IP address as fallback.
        """
        try:
            # Try player status first (fastest)
            status = await self.get_player_status()
            if name := status.get("DeviceName"):
                return name.strip()

            # Try device info as fallback
            info = await self.get_device_info()
            if name := info.get("DeviceName") or info.get("device_name"):
                return name.strip()

        except WiiMError:
            _LOGGER.debug("Failed to get device name for %s, using IP", self.host)

        # Always fallback to IP
        return self.host

    async def get_status(self) -> dict[str, Any]:
        """Get the current device status using getStatusEx.

        This method provides comprehensive device and group information but may have
        limited playback details compared to get_player_status(). Use get_player_status()
        for complete track information and playback state.

        Returns:
            A dictionary containing normalized device status including:
            - volume: Current volume level (0-1)
            - mute: Current mute state
            - power: Current power state (may be unreliable)
            - device_name: Device friendly name
            - uuid: Device unique identifier
            - firmware: Current firmware version
            - project: Device model name
            - group: Group membership info (critical for multiroom)
            - master_uuid: Master device UUID (if slave)
            - wifi_rssi: Current WiFi signal strength
            - wifi_channel: Current WiFi channel

            Note: For complete playbook information (title, artist, album, position,
            duration, etc.), use get_player_status() instead.
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

        ⚠️ WARNING: Power control is unreliable and intentionally excluded from the WiiM integration.

        This method is deprecated and should not be used because:
        - WiiM devices have inconsistent power control across models/firmware
        - Power states are often incorrectly reported
        - Network connectivity conflicts with true "off" states
        - Physical power buttons and auto-sleep vary significantly between models

        Alternative: Use physical power buttons, auto-sleep features, or smart switches.

        Args:
            power: True to turn on, False to turn off.
        """
        _LOGGER.warning(
            "Power control is deprecated and unreliable on WiiM devices. "
            "Use physical power buttons or smart switches instead. Host: %s",
            self.host,
        )
        await self._request(f"{API_ENDPOINT_POWER}{1 if power else 0}")

    async def set_repeat_mode(self, mode: str) -> None:
        """Set the repeat mode.

        Args:
            mode: One of PLAY_MODE_NORMAL, PLAY_MODE_REPEAT_ALL, or PLAY_MODE_REPEAT_ONE.

        Raises:
            ValueError: If an invalid repeat mode is specified.
        """
        _LOGGER.debug("🔁 API set_repeat_mode called with mode='%s' for %s", mode, self.host)
        _LOGGER.debug("🔁 Valid modes are: %s", (PLAY_MODE_NORMAL, PLAY_MODE_REPEAT_ALL, PLAY_MODE_REPEAT_ONE))

        if mode not in (PLAY_MODE_NORMAL, PLAY_MODE_REPEAT_ALL, PLAY_MODE_REPEAT_ONE):
            _LOGGER.error("🔁 Invalid repeat mode validation failed: mode='%s'", mode)
            raise ValueError(f"Invalid repeat mode: {mode}")

        endpoint_url = f"{API_ENDPOINT_REPEAT}{mode}"
        _LOGGER.debug("🔁 Constructed endpoint URL: '%s'", endpoint_url)
        _LOGGER.debug("🔁 About to send HTTP request for repeat mode")

        try:
            result = await self._request(endpoint_url)
            _LOGGER.info("🔁 ✅ Repeat mode set successfully: %s -> %s (result: %s)", self.host, mode, result)

            # Check if the change actually took effect by getting current status
            try:
                await asyncio.sleep(0.5)  # Give device time to update
                status = await self.get_player_status()
                loop_val = status.get("loop_mode") or status.get("loop")
                _LOGGER.info("🔁 Status check after repeat mode change: loop_mode=%s", loop_val)
            except Exception as check_err:
                _LOGGER.debug("🔁 Could not check status after repeat mode change: %s", check_err)

        except Exception as err:
            _LOGGER.error("🔁 ❌ HTTP request failed for repeat mode: %s", err)
            _LOGGER.error("🔁 Failed endpoint URL was: '%s'", endpoint_url)
            raise

    async def set_shuffle_mode(self, mode: str) -> None:
        """Set the shuffle mode.

        Args:
            mode: One of PLAY_MODE_NORMAL, PLAY_MODE_SHUFFLE, or PLAY_MODE_SHUFFLE_REPEAT_ALL.

        Raises:
            ValueError: If an invalid shuffle mode is specified.
        """
        _LOGGER.debug("🔀 API set_shuffle_mode called with mode='%s' for %s", mode, self.host)
        _LOGGER.debug("🔀 Valid modes are: %s", (PLAY_MODE_NORMAL, PLAY_MODE_SHUFFLE, PLAY_MODE_SHUFFLE_REPEAT_ALL))

        if mode not in (
            PLAY_MODE_NORMAL,
            PLAY_MODE_SHUFFLE,
            PLAY_MODE_SHUFFLE_REPEAT_ALL,
        ):
            _LOGGER.error("🔀 Invalid shuffle mode validation failed: mode='%s'", mode)
            raise ValueError(f"Invalid shuffle mode: {mode}")

        endpoint_url = f"{API_ENDPOINT_SHUFFLE}{mode}"
        _LOGGER.debug("🔀 Constructed endpoint URL: '%s'", endpoint_url)
        _LOGGER.debug("🔀 About to send HTTP request for shuffle mode")

        try:
            result = await self._request(endpoint_url)
            _LOGGER.info("🔀 ✅ Shuffle mode set successfully: %s -> %s (result: %s)", self.host, mode, result)

            # Check if the change actually took effect by getting current status
            try:
                await asyncio.sleep(0.5)  # Give device time to update
                status = await self.get_player_status()
                loop_val = status.get("loop_mode") or status.get("loop")
                _LOGGER.info("🔀 Status check after shuffle mode change: loop_mode=%s", loop_val)
            except Exception as check_err:
                _LOGGER.debug("🔀 Could not check status after shuffle mode change: %s", check_err)

        except Exception as err:
            _LOGGER.error("🔀 ❌ HTTP request failed for shuffle mode: %s", err)
            _LOGGER.error("🔀 Failed endpoint URL was: '%s'", endpoint_url)
            raise

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
        """Prepare device to become a multiroom master.

        NOTE: In LinkPlay/WiiM, there is no explicit "create master" command.
        A device becomes a master automatically when other devices join it using
        the ConnectMasterAp:JoinGroupMaster command.

        This method simply prepares the internal state - the actual group creation
        happens when slave devices call join_slave() targeting this device.
        """
        _LOGGER.debug("[WiiM] Preparing %s to become multiroom master (no API command needed)", self.host)

        # Update internal state optimistically - device will become master when slaves join
        self._group_master = self.host  # Set to own IP when becoming master
        self._group_slaves = []  # Will be populated when slaves actually join

        _LOGGER.debug("[WiiM] %s prepared as potential multiroom master", self.host)

    async def delete_group(self) -> None:
        """Delete the current multiroom group."""
        if not self._group_master:
            raise WiiMError("Not part of a multiroom group")
        _LOGGER.debug("[WiiM] Deleting multiroom group on %s", self.host)
        await self._request(API_ENDPOINT_GROUP_EXIT)
        self._group_master = None
        self._group_slaves = []

    async def join_slave(self, master_ip: str) -> None:
        """Join this device as a slave to a master device.

        Uses the documented ConnectMasterAp:JoinGroupMaster command.

        Args:
            master_ip: IP address of the master device to join
        """
        _LOGGER.debug("[WiiM] %s joining as slave to master %s", self.host, master_ip)

        # Use the documented ConnectMasterAp command format
        command = f"ConnectMasterAp:JoinGroupMaster:eth{master_ip}:wifi0.0.0.0"
        endpoint = f"/httpapi.asp?command={command}"

        _LOGGER.debug("[WiiM] Sending join command: %s", command)

        try:
            response = await self._request(endpoint)
            _LOGGER.debug("[WiiM] Join response: %s", response)

            # Update internal state
            self._group_master = master_ip
            self._group_slaves = []
            _LOGGER.info("[WiiM] Successfully joined %s as slave to master %s", self.host, master_ip)

        except Exception as err:
            _LOGGER.error("[WiiM] Failed to join %s as slave to master %s: %s", self.host, master_ip, err)
            _LOGGER.error("[WiiM] Failed command was: %s", command)
            raise

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
        """Get device information including UUID using getStatusEx.

        According to the WiiM API guide, getStatusEx is the proper endpoint
        for retrieving comprehensive device information including the UUID,
        device name, firmware, model, and other metadata.
        """
        _LOGGER.debug("=== API get_device_info START for %s ===", self.host)

        try:
            _LOGGER.debug("Calling getStatusEx endpoint for %s", self.host)
            # Use getStatusEx endpoint which provides comprehensive device info including UUID
            device_info = await self._request(API_ENDPOINT_STATUS)
            _LOGGER.debug("Raw getStatusEx response for %s: %s", self.host, device_info)

            # Optional Pydantic validation
            try:
                model_obj: DeviceInfo | None = DeviceInfo.model_validate(device_info)
            except ValidationError as err:
                _LOGGER.debug("DeviceInfo validation failed on %s: %s", self.host, err.errors())
                model_obj = None

            device_info["_model"] = model_obj

            # Extract key group-related fields for debugging
            group_field = device_info.get("group")
            uuid_field = device_info.get("uuid")
            master_uuid = device_info.get("master_uuid")
            master_ip = device_info.get("master_ip")
            device_name = device_info.get("DeviceName") or device_info.get("device_name")

            _LOGGER.debug(
                "Group detection fields from getStatusEx for %s: group='%s', uuid='%s', master_uuid='%s', master_ip='%s', device_name='%s'",
                self.host,
                group_field,
                uuid_field,
                master_uuid,
                master_ip,
                device_name,
            )

            _LOGGER.debug("Retrieved device info from getStatusEx for %s: %s", self.host, device_info)
            _LOGGER.debug("=== API get_device_info SUCCESS for %s ===", self.host)
            return device_info

        except Exception as err:
            _LOGGER.error("=== API get_device_info FAILED for %s ===", self.host)
            _LOGGER.error("get_device_info (getStatusEx) failed for %s: %s", self.host, err)
            _LOGGER.error("Error type: %s", type(err).__name__)
            # Return empty dict so coordinator doesn't crash
            return {}

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
        """Play a preset.

        The WiiM HTTP API uses the ``MCUKeyShortClick:<n>`` command where
        *n* is the preset number starting at **1**.  Modern devices expose
        the total number of preset slots via the ``preset_key`` attribute of
        *getStatusEx* so callers are expected to validate against that.  We
        therefore only enforce that the value is a **positive** integer here.
        """
        if preset < 1:
            raise ValueError("Preset number must be 1 or higher")
        await self._request(f"{API_ENDPOINT_PRESET}{preset}")

    # ------------------------------------------------------------------
    # Preset list (for media-browser)
    # ------------------------------------------------------------------

    async def get_presets(self) -> list[dict[str, Any]]:
        """Return a list of preset entries from getPresetInfo.

        Each entry contains at least:
          {"number": 1, "name": "Radio Paradise", "url": "...", "picurl": "..."}
        On older firmware the endpoint may be missing – in that case we raise
        WiiMError so the caller can mark the capability unsupported.
        """

        try:
            from .const import API_ENDPOINT_PRESET_INFO

            payload = await self._request(API_ENDPOINT_PRESET_INFO)
            if not isinstance(payload, dict):
                raise WiiMResponseError("Invalid preset info response")

            return payload.get("preset_list", [])

        except WiiMError:
            raise  # propagate so coordinator can disable capability

    async def toggle_power(self) -> None:
        """Toggle power state.

        ⚠️ WARNING: Power control is deprecated and unreliable on WiiM devices.

        This method should not be used due to inconsistent power control implementation
        across different WiiM models and firmware versions. See set_power() for details.

        Alternative: Use physical power buttons, auto-sleep features, or smart switches.
        """
        _LOGGER.warning(
            "Power toggle is deprecated and unreliable on WiiM devices. "
            "Use physical power buttons or smart switches instead. Host: %s",
            self.host,
        )
        status = await self.get_status()
        power = status.get("power", False)
        await self.set_power(not power)

    # ---------------------------------------------------------------------
    # Extended helpers -----------------------------------------------------
    # ---------------------------------------------------------------------

    async def get_player_status(self) -> dict[str, Any]:
        """Get the current player status using getPlayerStatusEx.

        This method provides complete track information and playback state.
        Use get_status() for device and group information.

        Returns:
            A dictionary containing normalized player status information.
        """
        try:
            # Use absolute endpoint path so URL joins correctly
            raw = await self._request("/httpapi.asp?command=getPlayerStatusEx")
            _LOGGER.debug("Raw getPlayerStatusEx response: %s", raw)

            # Optional: validate with Pydantic – failures are non-fatal in beta
            try:
                model_obj: PlayerStatus | None = PlayerStatus.model_validate(raw)
            except ValidationError as err:
                _LOGGER.debug("PlayerStatus validation failed on %s: %s", self.host, err.errors())
                model_obj = None

            parsed = self._parse_player_status(raw)
            parsed["_model"] = model_obj  # expose for typed callers
            return parsed
        except WiiMError as e:
            _LOGGER.error("Failed to get player status: %s", e)
            return {}

    # Normalisation table for the *player-status* endpoint.  Keys on the left
    # are raw HTTP-API field names, values are our canonical attribute names
    # used throughout the integration.
    _STATUS_MAP: dict[str, str] = {
        "status": "play_status",
        "state": "play_status",
        "player_state": "play_status",
        "vol": "volume",
        "mute": "mute",
        "eq": "eq_preset",
        "EQ": "eq_preset",  # Some firmwares use upper-case EQ
        "eq_mode": "eq_preset",  # Seen on recent builds (e.g. W281)
        "loop": "loop_mode",
        "curpos": "position_ms",
        "totlen": "duration_ms",
        "Title": "title_hex",
        "Artist": "artist_hex",
        "Album": "album_hex",
        "DeviceName": "device_name",
        # Device identification
        "uuid": "uuid",  # Unique device identifier
        "ssid": "ssid",  # Device SSID/hotspot name
        "MAC": "mac_address",  # MAC address
        "firmware": "firmware",  # Firmware version
        "project": "project",  # Device model/project name
        # Wi-Fi (only present in fallback)
        "WifiChannel": "wifi_channel",
        "RSSI": "wifi_rssi",
    }

    # Mapping of ``mode`` codes → canonical source names.
    _MODE_MAP: dict[str, str] = {
        "0": "idle",  # idle/unknown
        "1": "airplay",
        "2": "dlna",
        "3": "wifi",  # network / built-in streamer / vTuner etc.
        "4": "line_in",
        "5": "bluetooth",
        "6": "optical",
        "10": "wifi",  # additional NET/Streamer mode (variant)
        "11": "usb",  # local U-Disk / WiiMu Local
        "20": "wifi",  # HTTPAPI initiated play
        "31": "spotify",  # Spotify Connect session active
        "36": "qobuz",  # Qobuz streaming
        "40": "line_in",
        "41": "bluetooth",
        "43": "optical",
        "47": "line_in_2",
        "51": "usb",  # USB-DAC on WiiM Pro Plus
        "99": "follower",  # guest/relay in multiroom
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

        # ---- Playback state (prefer newer fields) ----
        play_state_val = raw.get("state") or raw.get("player_state") or raw.get("status")
        if play_state_val is not None:
            data["play_status"] = play_state_val
            _LOGGER.debug("Raw play state value: %s, final play_status: %s", play_state_val, data["play_status"])
        else:
            # Log when we don't have loop_mode data
            if "play_mode" not in data:
                _LOGGER.debug("🔁🔀 No loop_mode field found for %s, no play_status set", self.host)

        # Map raw keys to normalized keys
        for k, v in raw.items():
            # Skip the fields we already handled above to prevent overwriting
            if k in ("status", "state", "player_state"):
                continue
            key = self._STATUS_MAP.get(k, k)
            data[key] = v

        # Decode hex-encoded metadata
        data["title"] = _hex_to_str(raw.get("Title")) or raw.get("title")
        data["artist"] = _hex_to_str(raw.get("Artist")) or raw.get("artist")
        data["album"] = _hex_to_str(raw.get("Album")) or raw.get("album")

        # Log track changes for debugging
        if data.get("title") and data["title"] != "Unknown":
            current_track = f"{data.get('artist', 'Unknown')} - {data['title']}"
            if self._last_track != current_track:
                _LOGGER.info("🎵 Track changed for %s: %s", self.host, current_track)
                self._last_track = current_track

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
        curpos_val = raw.get("curpos") or raw.get("offset_pts")
        if curpos_val is not None:
            data["position"] = int(curpos_val) // 1_000
            data["position_updated_at"] = asyncio.get_running_loop().time()

        if raw.get("totlen") is not None:
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
                _LOGGER.debug(
                    "🔁🔀 Parsing play mode for %s: loop_mode=%s (raw: %s)", self.host, loop_val, data["loop_mode"]
                )
            except (TypeError, ValueError):
                loop_val = 4  # default = normal
                _LOGGER.debug("🔁🔀 Invalid loop_mode for %s, defaulting to normal: %s", self.host, data["loop_mode"])

            # Map loop_val to play_mode
            if loop_val == 0:
                new_play_mode = PLAY_MODE_REPEAT_ALL
            elif loop_val == 1:
                new_play_mode = PLAY_MODE_REPEAT_ONE
            elif loop_val == 2:
                new_play_mode = PLAY_MODE_SHUFFLE_REPEAT_ALL
            elif loop_val == 3:
                new_play_mode = PLAY_MODE_SHUFFLE
            else:
                new_play_mode = PLAY_MODE_NORMAL

            # Only log when play mode actually changes
            if self._last_play_mode != new_play_mode:
                _LOGGER.info("🔁🔀 Set play_mode for %s: %s (loop_val=%s)", self.host, new_play_mode, loop_val)
                self._last_play_mode = new_play_mode

            data["play_mode"] = new_play_mode
        else:
            # Log when we don't have loop_mode data
            if "play_mode" not in data:
                _LOGGER.debug("🔁🔀 No loop_mode field found for %s, no play_mode set", self.host)

        # ---------------------------------------------------------------
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
            # Use a combination of title, artist, and album for cache-busting
            title = data.get("title") or ""
            artist = data.get("artist") or ""
            album = data.get("album") or ""
            cache_key = f"{title}-{artist}-{album}"

            if cache_key:
                from urllib.parse import quote

                encoded_key = quote(cache_key)
                if "?" in cover:
                    # URL already has parameters – append with &
                    cover = f"{cover}&cache={encoded_key}"
                else:
                    cover = f"{cover}?cache={encoded_key}"
            _LOGGER.debug("Setting entity_picture: %s (cache_key: %s)", cover, cache_key)
            data["entity_picture"] = cover

        # ---------------------------------------------------------------
        # Current *input* source – derived from ``mode`` field.  Not all
        # firmwares expose ``source`` directly; adding it here enables the
        # media-player UI to show e.g. "AirPlay" when streaming from iOS.
        #
        # SPECIAL CASE: mode="99" means multiroom participant – coordinator will decide how to
        # treat it based on current playback state and role detection.
        # ---------------------------------------------------------------
        mode_val = raw.get("mode")
        if mode_val is not None and "source" not in data:
            if str(mode_val) == "99":
                # Mode 99 = multiroom participant – coordinator will decide how to
                # treat it based on current playback state and role detection.
                data["source"] = "multiroom"  # Temporary – resolved by coordinator
                data["_multiroom_mode"] = True  # Flag for coordinator processing
            else:
                data["source"] = self._MODE_MAP.get(str(mode_val), "unknown")

        # ---------------------------------------------------------------
        # Vendor specific override – some services (e.g. Amazon Music)
        # report a generic mode (3 = wifi/NET) but include a more
        # descriptive *vendor* field.  Use that to replace the generic
        # "wifi" source so the UI shows the actual streaming service.
        # ---------------------------------------------------------------
        vendor_val = raw.get("vendor") or raw.get("Vendor") or raw.get("app")
        if vendor_val:
            vendor_val_clean = str(vendor_val).strip()

            # Common vendor → source normalisation table.  Keys are **case-insensitive**
            # vendor strings as reported by the firmware, values are the canonical
            # source string we want to expose to Home Assistant.
            _VENDOR_SOURCE_MAP = {
                "amazon music": "amazon",
                "amazonmusic": "amazon",
                "prime": "amazon",  # Amazon Prime Music
                "qobuz": "qobuz",
                "tidal": "tidal",
                "deezer": "deezer",
            }

            # Normalise lookup key to lower-case without surrounding whitespace
            map_key = vendor_val_clean.lower().strip()
            mapped_source = _VENDOR_SOURCE_MAP.get(map_key)

            # Only override when the current source is the generic
            # network streamer variants ("wifi"/"unknown") to avoid
            # clobbering explicit sources like "spotify" (mode 31).
            if data.get("source") in (None, "wifi", "unknown"):
                if mapped_source:
                    # Preferred mapping when we recognise the vendor
                    data["source"] = mapped_source
                else:
                    # Fallback: simple slug-ification
                    data["source"] = vendor_val_clean.lower().replace(" ", "_")
            # Expose human-readable vendor name as separate attribute
            data["vendor"] = vendor_val_clean

        # ---------------------------------------------------------------
        # EQ preset – convert **numeric** codes to their textual alias so
        # the frontend can display a meaningful name and the service
        # calls keep working with the usual strings.
        # ---------------------------------------------------------------
        eq_raw = data.get("eq_preset")
        if isinstance(eq_raw, int | str) and str(eq_raw).isdigit():
            data["eq_preset"] = self._EQ_NUMERIC_MAP.get(str(eq_raw), eq_raw)

        # ---------------------------------------------------------------
        # FINAL FALLBACK – Qobuz "always playing" quirk (placement AFTER
        # source/vendor mapping so we know which source was detected).
        # ---------------------------------------------------------------
        if (
            data.get("source") == "qobuz"
            and (not data.get("play_status") or str(data["play_status"]).lower() in {"stop", "stopped", "idle", ""})
        ):
            data["play_status"] = "play"
            _LOGGER.debug("Qobuz fallback applied – forcing play_status='play'")

        _LOGGER.debug("Parsed player status: %s", data)
        return data

    async def get_multiroom_info(self) -> dict[str, Any]:
        """Get multiroom information including master/slave status."""
        _LOGGER.debug("=== API get_multiroom_info START for %s ===", self.host)

        try:
            _LOGGER.debug("Calling getSlaveList endpoint for %s", self.host)
            response = await self._request(API_ENDPOINT_GROUP_SLAVES)
            _LOGGER.debug("Raw getSlaveList response for %s: %s", self.host, response)

            # CORRECT PARSING according to WiiM API specification:
            # - "slaves": integer count (always present)
            # - "slave_list": array of slave objects (present when slaves > 0)
            slaves_count = response.get("slaves", 0)
            slave_list = response.get("slave_list", [])

            _LOGGER.debug(
                "Parsed getSlaveList for %s: slaves_count=%d, slave_list=%s", self.host, slaves_count, slave_list
            )

            # Validate the response format
            if not isinstance(slaves_count, int):
                _LOGGER.warning("Unexpected slaves count format for %s: %s (expected integer)", self.host, slaves_count)
                slaves_count = 0

            if not isinstance(slave_list, list):
                _LOGGER.warning("Unexpected slave_list format for %s: %s (expected list)", self.host, slave_list)
                slave_list = []

            # Check for consistency between count and list
            if slaves_count > 0 and len(slave_list) == 0:
                _LOGGER.warning(
                    "MULTIROOM INCONSISTENCY: %s reports %d slaves but slave_list is empty - master may have slaves that aren't responding",
                    self.host,
                    slaves_count,
                )
            elif slaves_count == 0 and len(slave_list) > 0:
                _LOGGER.warning(
                    "MULTIROOM INCONSISTENCY: %s reports 0 slaves but slave_list has %d entries",
                    self.host,
                    len(slave_list),
                )
            elif slaves_count != len(slave_list):
                _LOGGER.warning(
                    "MULTIROOM INCONSISTENCY: %s reports %d slaves but slave_list has %d entries",
                    self.host,
                    slaves_count,
                    len(slave_list),
                )

            # Log detailed slave information for debugging
            if slave_list:
                _LOGGER.debug("Slave details for master %s:", self.host)
                for i, slave in enumerate(slave_list):
                    slave_name = slave.get("name", "Unknown")
                    slave_ip = slave.get("ip", "Unknown")
                    slave_uuid = slave.get("uuid", "Unknown")
                    _LOGGER.debug("  Slave %d: name='%s', ip='%s', uuid='%s'", i, slave_name, slave_ip, slave_uuid)

            result = {
                "slave_count": slaves_count,
                "slaves": slave_list,  # Use the actual slave list, not the count
                "slave_list": slave_list,  # Also provide under the API field name for compatibility
            }

            _LOGGER.debug("Final multiroom info for %s: %s", self.host, result)
            _LOGGER.debug("=== API get_multiroom_info SUCCESS for %s ===", self.host)
            return result

        except WiiMError as err:
            # Device doesn't support multiroom or not a master
            _LOGGER.debug("=== API get_multiroom_info FAILED for %s ===", self.host)
            _LOGGER.debug(
                "getSlaveList failed for %s: %s (likely not a master or no multiroom support)", self.host, err
            )
            return {"slaves": [], "slave_count": 0, "slave_list": []}

    async def get_slaves(self) -> list[str]:
        """Get list of slave device IPs.

        Returns empty list if device is not a master or doesn't support multiroom.
        """
        try:
            response = await self._request(API_ENDPOINT_GROUP_SLAVES)
            slaves_data = response.get("slaves", [])

            if isinstance(slaves_data, list):
                # Extract IP addresses from slave list
                slave_ips = []
                for slave in slaves_data:
                    if isinstance(slave, dict) and "ip" in slave:
                        slave_ips.append(slave["ip"])
                    elif isinstance(slave, str):
                        slave_ips.append(slave)
                return slave_ips
            else:
                # slaves_data is an integer count or other type - no actual IPs available
                return []
        except WiiMError:
            # Device doesn't support multiroom or is not a master
            return []

    async def kick_slave(self, slave_ip: str) -> None:
        """Remove a slave device from the group."""
        _LOGGER.debug(
            "[WiiM] Kick slave request: host=%s, is_master=%s, _group_master=%s, slave_ip=%s",
            self.host,
            self.is_master,
            self._group_master,
            slave_ip,
        )

        if not self.is_master:
            _LOGGER.error(
                "[WiiM] Cannot kick slave %s from %s: Not a group master (is_master=%s, _group_master=%s)",
                slave_ip,
                self.host,
                self.is_master,
                self._group_master,
            )
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
        """Sync device time with provided timestamp or current time."""
        import time

        if ts is None:
            ts = int(time.time())

        await self._request(f"/httpapi.asp?command=timeSync:{ts}")

    async def get_meta_info(self) -> dict[str, Any]:
        """Get current track metadata including album art."""
        _LOGGER.debug("Attempting getMetaInfo for %s", self.host)
        try:
            response = await self._request("/httpapi.asp?command=getMetaInfo")
            _LOGGER.debug("getMetaInfo raw response for %s: %s", self.host, response)

            # Check for "unknown command" response (older LinkPlay devices)
            if "raw" in response and str(response["raw"]).lower().startswith("unknown command"):
                _LOGGER.debug("Device %s responded 'unknown command' to getMetaInfo - not supported", self.host)
                return {}

            if response and "metaData" in response:
                metadata = response["metaData"]
                _LOGGER.debug("Extracted metaData for %s: %s", self.host, metadata)
                return {"metaData": metadata}  # Return in expected format
            else:
                _LOGGER.debug("getMetaInfo response missing metaData for %s", self.host)
                return {}

        except Exception as e:
            # Devices with older firmware return plain "OK" or "unknown command" instead of JSON.
            # Treat this as an expected condition rather than an error.
            _LOGGER.debug("get_meta_info not supported on %s: %s", self.host, e)
            return {}

    async def play_url(self, url: str) -> None:
        """Play a URL."""
        # Preserve the URI scheme ("http://", "https://") and common
        # delimiter characters so the LinkPlay firmware receives a *readable*
        # URL.  Devices fail to play when the colon after the scheme or the
        # query separators are percent-encoded.  Encode only characters that
        # are truly unsafe in an HTTP context.
        encoded_url = quote(url, safe=":/?&=#%")
        await self._request(f"{API_ENDPOINT_PLAY_URL}{encoded_url}")

    async def play_playlist(self, playlist_url: str) -> None:
        """Play an M3U playlist."""
        # Preserve the URI scheme ("http://", "https://") and common
        # delimiter characters so the LinkPlay firmware receives a *readable*
        # URL.  Devices fail to play when the colon after the scheme or the
        # query separators are percent-encoded.  Encode only characters that
        # are truly unsafe in an HTTP context.
        encoded_url = quote(playlist_url, safe=":/?&=#%")
        await self._request(f"{API_ENDPOINT_PLAY_M3U}{encoded_url}")

    async def play_notification(self, url: str) -> None:
        """Play a notification sound (lowers volume, plays, then restores)."""
        from urllib.parse import quote

        encoded_url = quote(url, safe="")
        await self._request(f"{API_ENDPOINT_PLAY_PROMPT_URL}{encoded_url}")

    async def send_command(self, command: str) -> dict[str, Any]:
        """Send an arbitrary LinkPlay API command.

        This method provides direct access to the LinkPlay HTTP API for
        commands that don't have dedicated methods. Used primarily for
        group management operations.

        Args:
            command: The LinkPlay command to send (e.g., "multiroom:Ungroup" or "setMultiroom:Master")

        Returns:
            The parsed response from the device

        Example:
            await client.send_command("multiroom:Ungroup")
            await client.send_command("setMultiroom:Master")
        """
        endpoint = f"/httpapi.asp?command={quote(command)}"
        return await self._request(endpoint)

    @property
    def base_url(self) -> str:
        """Return the base URL for the device (scheme://host:port).

        This reflects the most recently successful communication endpoint.
        """
        return self._endpoint


def _hex_to_str(val: str | None) -> str | None:
    """Decode hex‐encoded UTF-8 strings used by LinkPlay for metadata."""
    if not val:
        return None
    try:
        return bytes.fromhex(val).decode("utf-8", errors="replace")
    except ValueError:
        return val  # already plain
