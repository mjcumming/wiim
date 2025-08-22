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

import aiohttp
import async_timeout
from aiohttp import ClientSession

from .api_constants import WIIM_CA_CERT
from .api_parser import parse_player_status

# Core constants that are still required by the remaining methods.
from .const import (
    API_ENDPOINT_STATUS,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
)
from .models import DeviceInfo, PlayerStatus

_LOGGER = logging.getLogger(__name__)


HEADERS: dict[str, str] = {"Connection": "close"}

# -----------------------------------------------------------------------------
# Exceptions (kept as-is so external call-sites don't break during the trim).
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
        capabilities: dict[str, Any] | None = None,
    ) -> None:
        """Instantiate the client.

        Args:
            host: Device hostname or IP. A trailing ":<port>" is respected.
            port: Optional override when *host* does **not** include a port.
            timeout: Network timeout (seconds).
            ssl_context: Custom SSL context (tests/advanced use-cases only).
            session: Optional shared *aiohttp* session.
            capabilities: Device capabilities for firmware-specific handling.
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

        # Use firmware-specific timeout if provided
        self.timeout = capabilities.get("response_timeout", timeout) if capabilities else timeout
        self.ssl_context = ssl_context
        self._session = session
        self._capabilities = capabilities or {}

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
        """Perform an HTTP(S) request with smart protocol fallback and firmware-specific handling.

        Protocol fallback strategy:
        1. Try established endpoint first (fast-path)
        2. Only do full probe if no established endpoint exists
        3. After successful connection, stick with working protocol/port
        4. Apply firmware-specific error handling and retries
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))

        kwargs.setdefault("headers", HEADERS)

        # Use firmware-specific retry logic
        retry_count = self._capabilities.get("retry_count", 3)
        is_legacy_device = self._capabilities.get("is_legacy_device", False)

        for attempt in range(retry_count):
            try:
                result = await self._request_with_protocol_fallback(endpoint, method, **kwargs)

                # Validate response for legacy firmware
                if is_legacy_device:
                    result = self._validate_legacy_response(result, endpoint)

                return result

            except (aiohttp.ClientError, json.JSONDecodeError) as err:
                if attempt == retry_count - 1:
                    raise WiiMRequestError(f"Request failed after {retry_count} attempts: {err}") from err

                # Exponential backoff for retries (longer for legacy devices)
                backoff_delay = 0.5 * (2**attempt)
                if is_legacy_device:
                    backoff_delay *= 2  # Double delay for legacy devices

                _LOGGER.debug(
                    "Request attempt %d/%d failed for %s, retrying in %.1fs: %s",
                    attempt + 1,
                    retry_count,
                    self._host,
                    backoff_delay,
                    err,
                )
                await asyncio.sleep(backoff_delay)

    async def _request_with_protocol_fallback(
        self, endpoint: str, method: str = "GET", **kwargs: Any
    ) -> dict[str, Any]:
        """Perform HTTP(S) request with protocol fallback (original logic)."""

        # -----------------------------
        # Fast-path: use established endpoint.
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
                _LOGGER.debug("Established endpoint %s failed: %s", self._endpoint, err)
                # Don't immediately fall back to full probe - this could be a temporary network issue
                # Only clear endpoint after multiple consecutive failures or specific error types
                if isinstance(err, aiohttp.ClientConnectorError | aiohttp.ServerDisconnectedError):
                    _LOGGER.warning("Connection lost to %s, will retry with protocol probe", self._host)
                    self._endpoint = None  # Clear to force probe
                else:
                    # For other errors (timeouts, HTTP errors), keep the endpoint and fail fast
                    # This avoids expensive re-probing on temporary issues
                    raise WiiMConnectionError(f"Request to {self._endpoint}{endpoint} failed: {err}") from err

        # -----------------------------
        # Initial probe or connection lost - try all protocols
        # -----------------------------
        _LOGGER.debug("No established endpoint for %s, performing protocol probe", self._host)

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
                        # SUCCESS: Lock in this protocol/port combination
                        self._endpoint = f"{scheme}://{host_for_url}:{port}"
                        _LOGGER.debug("Established endpoint for %s: %s", self._host, self._endpoint)
                        if text.strip() == "OK":
                            return {"raw": "OK"}
                        return json.loads(text)
            except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as err:
                last_error = err
                continue

        raise WiiMConnectionError(
            f"Failed to communicate with {self._host} after trying: {', '.join(tried)}\nLast error: {last_error}"
        )

    def _validate_legacy_response(self, response: dict[str, Any], endpoint: str) -> dict[str, Any]:
        """Handle malformed responses from older firmware.

        Args:
            response: Raw API response
            endpoint: API endpoint that was called

        Returns:
            Validated response with safe defaults if needed
        """
        # Handle empty responses from Audio Pro units
        if not response or response == {}:
            _LOGGER.debug("Empty response from legacy device for %s", endpoint)

            # Return safe defaults based on endpoint
            if "getSlaveList" in endpoint:
                return {"slaves": 0, "slave_list": []}
            elif "getStatus" in endpoint:
                return {"group": "0", "state": "stop"}
            elif "getMetaInfo" in endpoint:
                return {"title": "", "artist": "", "album": ""}
            else:
                return {"raw": "OK"}

        # Handle malformed JSON responses
        if not isinstance(response, dict):
            _LOGGER.debug("Non-dict response from legacy device for %s: %s", endpoint, type(response))
            return {"raw": str(response)}

        return response

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
        parsed, self._last_track = parse_player_status(raw, self._last_track)
        return parsed

    async def get_device_info(self) -> dict[str, Any]:
        """Lightweight wrapper around *getStatusEx* (raw JSON)."""
        try:
            return await self._request(API_ENDPOINT_STATUS)
        except WiiMError as err:
            _LOGGER.debug("get_device_info failed: %s", err)
            return {}

    async def get_player_status(self) -> dict[str, Any]:
        """Return parsed output of *getPlayerStatusEx* with better error handling."""
        try:
            raw = await self._request("/httpapi.asp?command=getPlayerStatusEx")
            parsed, self._last_track = parse_player_status(raw, self._last_track)
            return parsed
        except Exception as err:
            # Log specific error types for debugging
            error_str = str(err).lower()
            if "404" in error_str:
                _LOGGER.debug("getPlayerStatusEx not supported by device at %s", self.host)
            elif "timeout" in error_str:
                _LOGGER.debug("Timeout getting player status from %s", self.host)
            else:
                _LOGGER.debug("get_player_status failed: %s", err)
            raise

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

    @property
    def host(self) -> str:  # noqa: D401 – property, not a method.
        """Host address (IP or hostname)."""
        return self._host
