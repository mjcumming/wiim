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
import os
import ssl
import tempfile
from typing import Any

import aiohttp
import async_timeout
from aiohttp import ClientSession

from .api_constants import AUDIO_PRO_CLIENT_CERT, WIIM_CA_CERT
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
    """Raised when there is an error communicating with the WiiM device.

    Enhanced with context for better debugging and user feedback.
    """

    def __init__(
        self,
        message: str,
        endpoint: str | None = None,
        attempts: int | None = None,
        last_error: Exception | None = None,
        device_info: dict[str, str] | None = None,
        operation_context: str | None = None,
    ) -> None:
        """Initialize request error with enhanced context.

        Args:
            message: The error message
            endpoint: API endpoint that failed
            attempts: Number of retry attempts made
            last_error: The underlying exception that caused this error
            device_info: Device information (firmware, model, etc.)
            operation_context: Context about what operation was being performed
        """
        self.endpoint = endpoint
        self.attempts = attempts
        self.last_error = last_error
        self.device_info = device_info or {}
        self.operation_context = operation_context or "api_call"
        super().__init__(message)

    def __str__(self) -> str:
        """Enhanced string representation with context."""
        context_parts = []

        if self.endpoint:
            context_parts.append(f"endpoint={self.endpoint}")
        if self.attempts:
            context_parts.append(f"attempts={self.attempts}")
        if self.device_info:
            firmware = self.device_info.get("firmware_version", "unknown")
            device_model = self.device_info.get("device_model", "unknown")
            device_type = (
                "WiiM"
                if self.device_info.get("is_wiim_device")
                else "Legacy"
                if self.device_info.get("is_legacy_device")
                else "Unknown"
            )

            device_context = f"{device_type} {device_model} (fw:{firmware})"
            context_parts.append(f"device={device_context}")
        if self.operation_context != "api_call":
            context_parts.append(f"context={self.operation_context}")

        if context_parts:
            return f"{super().__str__()} ({', '.join(context_parts)})"
        return super().__str__()


class WiiMResponseError(WiiMError):
    """Raised when the WiiM device returns an error response."""


class WiiMTimeoutError(WiiMRequestError):
    """Raised when a request to the WiiM device times out.

    Enhanced with context for better debugging and user feedback.
    """


class WiiMConnectionError(WiiMRequestError):
    """Raised on network-level connectivity problems (SSL, unreachable, …).

    Enhanced with context for better debugging and user feedback.
    """


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
            # Check if this is an IPv6 address or "host:port" format
            try:
                # Try to parse as IPv6 address
                import ipaddress

                ipaddress.IPv6Address(host)
                # If successful, it's a pure IPv6 address
                self._host = host
                self.port = port
            except ipaddress.AddressValueError:
                # Not a valid IPv6 address, check if it's "host:port" format
                try:
                    host_part, port_part = host.rsplit(":", 1)
                    self.port = int(port_part)
                    self._host = host_part
                    self._discovered_port = True
                except (ValueError, TypeError):
                    self._host = host
                    self.port = port
        elif host.startswith("[") and "]:" in host:
            # Handle IPv6 address with port in brackets: [2001:db8::1]:8080
            try:
                bracket_end = host.find("]:")
                if bracket_end > 0:
                    ipv6_part = host[1:bracket_end]  # Remove brackets
                    port_part = host[bracket_end + 2 :]  # Skip "]:"
                    self._host = ipv6_part
                    self.port = int(port_part)
                    self._discovered_port = True
                else:
                    self._host = host
                    self.port = port
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
        """Return a permissive SSL context able to talk to WiiM devices.

        For Audio Pro MkII devices, also loads client certificate for mutual TLS authentication.
        """
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

        # Attempt to load client certificate for mutual TLS authentication when supported.
        # Many Audio Pro MkII/W devices accept client auth on 4443; servers that don't
        # require a client certificate will simply ignore it.
        try:
            # Create temporary files from the embedded PEM string since load_cert_chain() requires file paths
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".pem") as cert_file:
                cert_file.write(AUDIO_PRO_CLIENT_CERT)
                cert_temp_path = cert_file.name

            # Load certificate from temporary file
            ctx.load_cert_chain(cert_temp_path)
            _LOGGER.info("✓ Client certificate loaded for mutual TLS authentication (Audio Pro devices)")

            # Clean up temporary file
            try:
                os.unlink(cert_temp_path)
            except Exception:
                pass  # Ignore cleanup errors

        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("✗ Failed to load client certificate for mTLS: %s", exc)
            # Continue without client cert - connection may still work on other ports

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
                    generation = self._capabilities.get("audio_pro_generation", "original")
                    _LOGGER.debug(
                        "Validating response for legacy device %s (generation: %s) on %s",
                        self.host,
                        generation,
                        endpoint,
                    )
                    result = self._validate_legacy_response(result, endpoint)

                return result

            except (aiohttp.ClientError, json.JSONDecodeError) as err:
                if attempt == retry_count - 1:
                    # Get comprehensive device info for enhanced error context
                    device_info = {}
                    try:
                        if hasattr(self, "_capabilities") and self._capabilities:
                            caps = self._capabilities
                            device_info = {
                                "firmware_version": caps.get("firmware_version", "unknown"),
                                "device_model": caps.get("device_type", "unknown"),
                                "device_name": caps.get("device_name", "unknown"),
                                "is_wiim_device": caps.get("is_wiim_device", False),
                                "is_legacy_device": caps.get("is_legacy_device", False),
                                "supports_metadata": caps.get("supports_metadata", False),
                                "supports_audio_output": caps.get("supports_audio_output", False),
                            }
                    except Exception:  # noqa: BLE001
                        pass  # Device info not available, continue without it

                    raise WiiMRequestError(
                        f"Request failed after {retry_count} attempts: {err}",
                        endpoint=endpoint,
                        attempts=retry_count,
                        last_error=err,
                        device_info=device_info,
                    ) from err

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
                # Handle IPv6 addresses properly by adding brackets if needed
                hostname = p.hostname
                if hostname and ":" in hostname and not hostname.startswith("["):
                    hostname = f"[{hostname}]"
                url = f"{p.scheme}://{hostname}:{p.port}{endpoint}"
                if p.scheme == "https":
                    kwargs["ssl"] = self._get_ssl_context()
                else:
                    kwargs.pop("ssl", None)

                async with async_timeout.timeout(self.timeout):
                    resp = await self._session.request(method, url, **kwargs)
                    async with resp:
                        resp.raise_for_status()
                        text = await resp.text()

                        # Handle empty responses gracefully
                        if not text or text.strip() == "":
                            # For certain commands like reboot, empty response is expected
                            if "reboot" in endpoint.lower():
                                _LOGGER.debug("Reboot command sent successfully (empty response expected)")
                                return {"raw": "OK"}
                            else:
                                _LOGGER.debug("Empty response from device for %s", endpoint)
                                return {"raw": ""}

                        if text.strip() == "OK":
                            return {"raw": "OK"}

                        # Try to parse JSON, but handle parsing errors gracefully
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError as json_err:
                            # For certain commands, parsing errors are expected
                            if "reboot" in endpoint.lower():
                                _LOGGER.debug(
                                    "Reboot command sent successfully (parsing error expected): %s",
                                    json_err,
                                )
                                return {"raw": "OK"}
                            else:
                                # Re-raise for other commands
                                raise WiiMConnectionError(
                                    f"Invalid JSON response from {self._endpoint}{endpoint}: {json_err}"
                                ) from json_err

            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Established endpoint %s failed: %s", self._endpoint, err)
                # Don't immediately fall back to full probe - this could be a temporary network issue
                # Only clear endpoint after multiple consecutive failures or specific error types
                if isinstance(err, aiohttp.ClientConnectorError | aiohttp.ServerDisconnectedError):
                    # Only log occasionally to reduce noise - this is normal during network issues
                    if not hasattr(self, "_connection_retry_count"):
                        self._connection_retry_count = 0
                    self._connection_retry_count += 1

                    # Only log the first few connection losses, then throttle
                    if self._connection_retry_count <= 3:
                        _LOGGER.warning(
                            "Connection lost to %s, will retry with protocol probe",
                            self._host,
                        )
                    elif self._connection_retry_count % 5 == 1:  # Every 5th failure
                        _LOGGER.debug(
                            "Connection still failing to %s (attempt %d)",
                            self._host,
                            self._connection_retry_count,
                        )

                    self._endpoint = None  # Clear to force probe
                else:
                    # For other errors (timeouts, HTTP errors), keep the endpoint and fail fast
                    # This avoids expensive re-probing on temporary issues
                    # Get comprehensive device info for enhanced error context
                    device_info = {}
                    try:
                        if hasattr(self, "_capabilities") and self._capabilities:
                            caps = self._capabilities
                            device_info = {
                                "firmware_version": caps.get("firmware_version", "unknown"),
                                "device_model": caps.get("device_type", "unknown"),
                                "device_name": caps.get("device_name", "unknown"),
                                "is_wiim_device": caps.get("is_wiim_device", False),
                                "is_legacy_device": caps.get("is_legacy_device", False),
                                "supports_metadata": caps.get("supports_metadata", False),
                                "supports_audio_output": caps.get("supports_audio_output", False),
                            }
                    except Exception:  # noqa: BLE001
                        pass  # Device info not available, continue without it

                    raise WiiMConnectionError(
                        f"Request to {self._endpoint}{endpoint} failed: {err}",
                        endpoint=f"{self._endpoint}{endpoint}",
                        last_error=err,
                        device_info=device_info,
                    ) from err

        # -----------------------------
        # Initial probe or connection lost - try all protocols
        # -----------------------------
        # Only log protocol probing occasionally to reduce noise during network issues
        if not hasattr(self, "_protocol_probe_count"):
            self._protocol_probe_count = 0
        self._protocol_probe_count += 1

        if self._protocol_probe_count <= 2:
            _LOGGER.info("No established endpoint for %s, performing protocol probe", self._host)
        elif self._protocol_probe_count % 3 == 1:  # Every 3rd probe
            _LOGGER.debug(
                "Protocol probe still needed for %s (attempt %d)",
                self._host,
                self._protocol_probe_count,
            )

        protocols: list[tuple[str, int, ssl.SSLContext | None]]

        # Use protocol priority from capabilities if available
        protocol_priority = self._capabilities.get("protocol_priority", ["https", "http"])
        _LOGGER.debug("Using protocol priority for %s: %s", self._host, protocol_priority)

        if self._discovered_port:
            # Build protocols based on discovered port and priority
            protocols = []
            for scheme in protocol_priority:
                if scheme == "https":
                    protocols.append((scheme, self.port, self._get_ssl_context()))
                else:  # http
                    protocols.append((scheme, self.port, None))
        else:
            # Build protocols based on standard ports and priority
            protocols = []

            # Use preferred ports from capabilities if specified (Audio Pro MkII uses 4443)
            preferred_ports = self._capabilities.get("preferred_ports", [])

            for scheme in protocol_priority:
                if scheme == "https":
                    if preferred_ports:
                        # Audio Pro MkII: Use preferred ports (4443, 8443, 443)
                        for port in preferred_ports:
                            protocols.append((scheme, port, self._get_ssl_context()))
                    else:
                        # Standard devices: Try common HTTPS ports
                        protocols.extend(
                            [
                                (scheme, 443, self._get_ssl_context()),
                                (scheme, 4443, self._get_ssl_context()),
                                (scheme, 8443, self._get_ssl_context()),
                            ]
                        )
                else:  # http
                    protocols.extend(
                        [
                            (scheme, 80, None),
                            (scheme, 8080, None),
                        ]
                    )

            # Add custom port if not standard
            if self.port not in (80, 443, 4443, 8080):
                for scheme in protocol_priority:
                    if scheme == "https":
                        protocols.insert(0, (scheme, self.port, self._get_ssl_context()))
                    else:  # http
                        protocols.insert(0, (scheme, self.port, None))

            # Add Audio Pro MkII specific endpoints as fallback
            # These devices may use different API structures or additional ports
            if self._capabilities.get("audio_pro_generation") in ("mkii", "w_generation"):
                _LOGGER.debug("Adding Audio Pro MkII specific fallback endpoints")
                protocols.extend(
                    [
                        # Re-add common ports with higher priority for Audio Pro
                        ("https", 443, self._get_ssl_context()),
                        ("https", 4443, self._get_ssl_context()),
                        ("https", 8443, self._get_ssl_context()),
                        ("http", 80, None),
                        ("http", 8080, None),
                        # Some Audio Pro devices may use port 8888
                        ("http", 8888, None),
                        ("https", 8888, self._get_ssl_context()),
                    ]
                )

        last_error: Exception | None = None
        tried: list[str] = []

        for scheme, port, ssl_ctx in protocols:
            host_for_url = f"[{self._host}]" if ":" in self._host and not self._host.startswith("[") else self._host

            # Build candidate endpoint paths to try for this scheme/port
            paths_to_try: list[str] = [endpoint]
            if endpoint == API_ENDPOINT_STATUS:
                # Canonical LinkPlay fallbacks
                paths_to_try.extend(
                    [
                        "/httpapi.asp?command=getStatus",
                        "/httpapi.asp?command=getPlayerStatus",
                    ]
                )

                # Audio Pro MkII/W: try a few common REST/CGI variants
                if self._capabilities.get("audio_pro_generation") in ("mkii", "w_generation"):
                    paths_to_try.extend(
                        [
                            "/api/status",
                            "/cgi-bin/status.cgi",
                            "/status",
                            "/api/v1/status",
                            "/device/status",
                        ]
                    )
                    if endpoint.startswith("/httpapi.asp"):
                        paths_to_try.append(endpoint.replace("/httpapi.asp", "", 1))

            # Configure SSL per scheme
            if scheme == "https":
                kwargs["ssl"] = ssl_ctx
            else:
                kwargs.pop("ssl", None)

            # Attempt each candidate path
            for path in paths_to_try:
                url = f"{scheme}://{host_for_url}:{port}{path}"
                tried.append(url)

                try:
                    async with async_timeout.timeout(self.timeout):
                        resp = await self._session.request(method, url, **kwargs)
                        async with resp:
                            resp.raise_for_status()
                            text = await resp.text()

                            # Handle empty responses gracefully
                            if not text or text.strip() == "":
                                if "reboot" in path.lower():
                                    _LOGGER.debug("Reboot command sent successfully (empty response expected)")
                                    self._endpoint = f"{scheme}://{host_for_url}:{port}"
                                    _LOGGER.debug("Established endpoint for %s: %s", self._host, self._endpoint)
                                    return {"raw": "OK"}
                                _LOGGER.debug("Empty response from device for %s", path)
                                self._endpoint = f"{scheme}://{host_for_url}:{port}"
                                _LOGGER.debug("Established endpoint for %s: %s", self._host, self._endpoint)
                                return {"raw": ""}

                            # SUCCESS: Lock in this base endpoint
                            self._endpoint = f"{scheme}://{host_for_url}:{port}"
                            _LOGGER.debug("Established endpoint for %s: %s", self._host, self._endpoint)

                            if text.strip() == "OK":
                                return {"raw": "OK"}

                            # Try to parse JSON, but handle parsing errors gracefully
                            try:
                                return json.loads(text)
                            except json.JSONDecodeError as json_err:
                                if "reboot" in path.lower():
                                    _LOGGER.debug(
                                        "Reboot command sent successfully (parsing error expected): %s", json_err
                                    )
                                    return {"raw": "OK"}
                                # Provide context on invalid JSON
                                device_info = {}
                                try:
                                    if hasattr(self, "_capabilities") and self._capabilities:
                                        device_info = {
                                            "firmware_version": self._capabilities.get("firmware_version", "unknown"),
                                            "device_model": self._capabilities.get("device_model", "unknown"),
                                        }
                                except Exception:  # noqa: BLE001
                                    pass

                                raise WiiMConnectionError(
                                    f"Invalid JSON response from {url}: {json_err}",
                                    endpoint=url,
                                    last_error=json_err,
                                    device_info=device_info,
                                ) from json_err

                except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as err:
                    last_error = err
                    continue

        # Get device info for enhanced error context
        device_info = {}
        try:
            if hasattr(self, "_capabilities") and self._capabilities:
                device_info = {
                    "firmware_version": self._capabilities.get("firmware_version", "unknown"),
                    "device_model": self._capabilities.get("device_model", "unknown"),
                }
        except Exception:  # noqa: BLE001
            pass  # Device info not available, continue without it

        # Count total attempts (protocols tried)
        total_attempts = len(tried)

        raise WiiMConnectionError(
            f"Failed to communicate with {self._host} after trying: {', '.join(tried)}\nLast error: {last_error}",
            endpoint=endpoint,
            attempts=total_attempts,
            last_error=last_error,
            device_info=device_info,
            operation_context="protocol_fallback",
        )

    def _validate_legacy_response(self, response: dict[str, Any], endpoint: str) -> dict[str, Any]:
        """Handle malformed responses from older firmware.

        Args:
            response: Raw API response
            endpoint: API endpoint that was called

        Returns:
            Validated response with safe defaults if needed
        """
        # Enhanced Audio Pro response validation
        return self._validate_audio_pro_response(response, endpoint)

    def _validate_audio_pro_response(self, response: dict[str, Any], endpoint: str) -> dict[str, Any]:
        """Handle Audio Pro specific response variations and legacy firmware issues.

        Args:
            response: Raw API response
            endpoint: API endpoint that was called

        Returns:
            Validated response with safe defaults if needed
        """
        # Handle empty responses from Audio Pro units
        if not response or response == {}:
            generation = (
                self._capabilities.get("audio_pro_generation", "unknown")
                if hasattr(self, "_capabilities") and self._capabilities
                else "unknown"
            )
            _LOGGER.debug(
                "Empty response from Audio Pro/legacy device %s (generation: %s) for %s",
                self.host,
                generation,
                endpoint,
            )
            return self._get_audio_pro_defaults(endpoint)

        # Handle Audio Pro MkII/W-Series string responses
        if isinstance(response, str):
            generation = (
                self._capabilities.get("audio_pro_generation", "unknown")
                if hasattr(self, "_capabilities") and self._capabilities
                else "unknown"
            )
            _LOGGER.debug(
                "String response from Audio Pro device %s (generation: %s) for %s: %s",
                self.host,
                generation,
                endpoint,
                response,
            )
            return self._normalize_audio_pro_string_response(response, endpoint)

        # Handle malformed JSON responses from legacy devices
        if not isinstance(response, dict):
            _LOGGER.debug(
                "Non-dict response from Audio Pro/legacy device for %s: %s",
                endpoint,
                type(response),
            )
            return {"raw": str(response)}

        # Normalize Audio Pro specific field variations
        normalized = self._normalize_audio_pro_fields(response, endpoint)

        # Log field normalization if any mappings were applied
        if normalized != response:
            _LOGGER.debug("Normalized Audio Pro response fields for %s on %s", self.host, endpoint)

        return normalized

    def _normalize_audio_pro_string_response(self, response: str, endpoint: str) -> dict[str, Any]:
        """Normalize Audio Pro string responses to standard dict format."""
        response = response.strip()

        # Common Audio Pro response patterns
        if response == "OK" or response == "ok":
            return {"raw": "OK"}
        elif response.lower() == "error" or response.lower() == "failed":
            return {"error": response}
        elif "error" in response.lower():
            return {"error": response}
        elif "not supported" in response.lower() or "unknown command" in response.lower():
            return {"error": "unsupported_command", "raw": response}
        else:
            # For status endpoints, try to parse as key:value pairs
            if "getPlayerStatus" in endpoint or "getStatus" in endpoint:
                return self._parse_audio_pro_status_string(response)
            else:
                return {"raw": response}

    def _parse_audio_pro_status_string(self, response: str) -> dict[str, Any]:
        """Parse Audio Pro status responses that come as strings instead of JSON."""
        # Audio Pro devices sometimes return status as "key:value" pairs
        result = {}

        # Try to parse common patterns
        if ":" in response:
            parts = response.split(":")
            if len(parts) >= 2:
                key = parts[0].strip().lower()
                value = ":".join(parts[1:]).strip()

                # Map common Audio Pro status fields
                if key in ["state", "status", "player_state"]:
                    result["state"] = value.lower()
                elif key in ["vol", "volume"]:
                    try:
                        result["volume"] = int(value)
                        result["volume_level"] = int(value) / 100
                    except ValueError:
                        result["volume"] = value
                elif key in ["mute", "muted"]:
                    result["mute"] = value.lower() in ["1", "true", "on", "yes"]
                elif key == "title":
                    result["title"] = value
                elif key == "artist":
                    result["artist"] = value
                elif key == "album":
                    result["album"] = value
                else:
                    result[key] = value

        if not result:
            # Fallback: treat as generic status
            result = {"state": "unknown", "raw": response}

        return result

    def _normalize_audio_pro_fields(self, response: dict[str, Any], endpoint: str) -> dict[str, Any]:
        """Normalize Audio Pro specific field names and variations."""
        normalized = response.copy()

        # Audio Pro specific field mappings
        field_mappings = {
            "player_state": "state",
            "play_status": "state",
            "vol": "volume",
            "volume_level": "volume_level",
            "mute": "mute",
            "muted": "mute",
            "title": "title",
            "artist": "artist",
            "album": "album",
            "device_name": "DeviceName",
            "friendly_name": "DeviceName",
        }

        # Apply field mappings
        for audio_pro_field, standard_field in field_mappings.items():
            if audio_pro_field in normalized and standard_field not in normalized:
                normalized[standard_field] = normalized.pop(audio_pro_field)

        # Normalize volume to 0-1 range if it's 0-100
        if "volume" in normalized and isinstance(normalized["volume"], int | float):
            if normalized["volume"] > 1:
                normalized["volume_level"] = normalized["volume"] / 100
            else:
                normalized["volume_level"] = normalized["volume"]

        # Normalize mute to boolean
        if "mute" in normalized:
            mute_value = normalized["mute"]
            if isinstance(mute_value, str):
                normalized["mute"] = mute_value.lower() in ["1", "true", "on", "yes"]
            elif isinstance(mute_value, int | float):
                normalized["mute"] = bool(mute_value)

        return normalized

    def _get_audio_pro_defaults(self, endpoint: str) -> dict[str, Any]:
        """Get Audio Pro specific safe defaults based on endpoint."""
        if "getSlaveList" in endpoint:
            return {"slaves": 0, "slave_list": []}
        elif "getStatus" in endpoint or "getPlayerStatus" in endpoint:
            return {
                "group": "0",
                "state": "stop",
                "volume": 30,
                "volume_level": 0.3,
                "mute": False,
                "title": "Unknown",
                "artist": "Unknown Artist",
            }
        elif "getMetaInfo" in endpoint:
            return {"title": "", "artist": "", "album": ""}
        elif "getDeviceInfo" in endpoint or "getStatusEx" in endpoint:
            return {
                "DeviceName": "Audio Pro Speaker",
                "uuid": "",
                "firmware": "unknown",
                "group": "0",
                "state": "stop",
            }
        else:
            return {"raw": "OK"}

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
        """Return parsed output of getPlayerStatusEx with Audio Pro MkII fallback.

        Audio Pro MkII devices don't support getPlayerStatusEx, so we use getStatusEx instead.
        The capability system automatically selects the right endpoint.
        """
        try:
            # Check if device supports getPlayerStatusEx (most devices do)
            if self._capabilities.get("supports_player_status_ex", True):
                # Standard devices use getPlayerStatusEx
                endpoint = "/httpapi.asp?command=getPlayerStatusEx"
            else:
                # Audio Pro MkII uses getStatusEx instead (from capabilities)
                endpoint = self._capabilities.get("status_endpoint", "/httpapi.asp?command=getStatusEx")
                _LOGGER.debug("Using Audio Pro MkII fallback endpoint: %s", endpoint)

            try:
                raw = await self._request(endpoint)
            except WiiMRequestError as primary_err:
                # If getPlayerStatusEx fails (unsupported on some Audio Pro devices), try getStatusEx
                if endpoint.endswith("getPlayerStatusEx"):
                    fallback_endpoint = "/httpapi.asp?command=getStatusEx"
                    _LOGGER.debug(
                        "Primary status endpoint failed (%s); retrying with fallback %s",
                        endpoint,
                        fallback_endpoint,
                    )
                    raw = await self._request(fallback_endpoint)
                else:
                    raise primary_err

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
