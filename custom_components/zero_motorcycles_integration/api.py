"""Zero Motorcycles API client with MFA support.

Implements the API flow reverse-engineered from the Zero app (APK v2.13.0):

1. Login (requires email OTP):
   - POST /dev/users/sendcode   (FormUrlEncoded, AES-encrypted user/pass)
   - POST /dev/users/2falogin   (FormUrlEncoded, AES-encrypted user/pass/code)
     -> returns JWT token (valid 60 days), sid, refreshToken

2. Data retrieval (uses JWT token in Authorization header):
   - POST /starcom/v1 with JSON body {"data": AES-encrypted command JSON}
     Commands: get_units, get_last_transmit, etc.

All encryption uses CryptoJS-compatible AES (see crypto.py).
"""
from __future__ import annotations

import asyncio
import json
import socket
from datetime import datetime, timezone

import aiohttp
import async_timeout

from .const import (
    APP_CODE,
    APP_VERSION,
    BASE_URL,
    ENCRYPTION_KEY,
    LANG,
    LOGGER,
    SOURCE,
)
from .crypto import cryptojs_encrypt


class ZeroApiClientError(Exception):
    """Exception to indicate a general API error."""


class ZeroApiClientCommunicationError(ZeroApiClientError):
    """Exception to indicate a communication error."""


class ZeroApiClientAuthenticationError(ZeroApiClientError):
    """Exception to indicate an authentication error."""


class ZeroApiClientMfaRequiredError(ZeroApiClientError):
    """Exception to indicate MFA code is required for login."""


def _make_headers() -> dict[str, str]:
    """Build headers matching the Zero mobile app."""
    return {
        "User-Agent": f"okhttp/4.9.3 zeromotorcycles.app/{APP_VERSION}",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "X-App-Code": APP_CODE,
        "X-App-Version": APP_VERSION,
        "X-Device-Id": "unknown",
        "X-Device-Type": "android",
        "X-Device-Name": "zero-integration",
    }


class ZeroApiClient:
    """Starcom API used by Zero Motorcycles for sharing data."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize with credentials.

        Args:
            username: Zero account email.
            password: Zero account password.
            session: Optional aiohttp session (defaults to HA's session).
        """
        self._username = username
        self._password = password
        self._session = session
        self._token: str | None = None
        self._sid: str | None = None
        self._refresh_token: str | None = None

    @property
    def token(self) -> str | None:
        """Return current JWT token."""
        return self._token

    @property
    def sid(self) -> str | None:
        """Return current session ID."""
        return self._sid

    @property
    def refresh_token(self) -> str | None:
        """Return current refresh token."""
        return self._refresh_token

    def restore_tokens(self, token: str, sid: str, refresh_token: str) -> None:
        """Restore tokens from stored configuration."""
        self._token = token
        self._sid = sid
        self._refresh_token = refresh_token
        LOGGER.debug("Restored stored tokens")

    async def async_send_code(self) -> dict:
        """Step 1 of login: request OTP code via email.

        Returns response dict. On success contains zerocode indicating
        the code was sent.
        """
        url = f"{BASE_URL}/dev/users/sendcode"
        headers = _make_headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        enc_user = cryptojs_encrypt(self._username, ENCRYPTION_KEY)
        enc_pass = cryptojs_encrypt(self._password, ENCRYPTION_KEY)

        payload = {
            "user": enc_user,
            "pass": enc_pass,
            "source": SOURCE,
            "lang": LANG,
            "format": "json",
            "commandname": "session_create",
        }

        response = await self._api_wrapper(
            method="post",
            url=url,
            data=payload,
            headers=headers,
        )

        if not isinstance(response, dict):
            raise ZeroApiClientError(f"Unexpected response type: {type(response)}")

        zerocode = response.get("zerocode")
        if zerocode == 805:
            raise ZeroApiClientAuthenticationError(
                "User is not registered (check email address)"
            )
        if zerocode not in (811,):  # 811 = code sent
            raise ZeroApiClientError(
                f"sendcode failed: zerocode={zerocode}, "
                f"status={response.get('zerostatus', 'unknown')}"
            )

        LOGGER.info("MFA code sent to %s", self._username)
        return response

    async def async_two_fa_login(self, code: str) -> dict:
        """Step 2 of login: complete login with OTP code.

        Args:
            code: 6-digit code received via email.

        Returns:
            Login response dict with token, sid, refreshToken.
        """
        url = f"{BASE_URL}/dev/users/2falogin"
        headers = _make_headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        enc_user = cryptojs_encrypt(self._username, ENCRYPTION_KEY)
        enc_pass = cryptojs_encrypt(self._password, ENCRYPTION_KEY)
        enc_code = cryptojs_encrypt(code, ENCRYPTION_KEY)

        payload = {
            "user": enc_user,
            "pass": enc_pass,
            "code": enc_code,
            "source": SOURCE,
            "lang": LANG,
            "is_conscented": "1",
            "format": "json",
            "commandname": "session_create",
        }

        response = await self._api_wrapper(
            method="post",
            url=url,
            data=payload,
            headers=headers,
        )

        if not isinstance(response, dict):
            raise ZeroApiClientError(f"Unexpected response type: {type(response)}")

        if response.get("result") != "ok":
            raise ZeroApiClientAuthenticationError(
                f"Login failed: {response.get('zerostatus', 'unknown error')}"
            )

        self._token = response.get("token")
        self._sid = response.get("sid")
        self._refresh_token = response.get("refreshToken")

        LOGGER.info("Login successful, token obtained")
        return response

    async def async_get_units(self) -> list[dict]:
        """Get available units for the logged-in user.

        Returns list of unit dicts with unitnumber, name, etc.
        """
        self._ensure_auth()
        command_data = {
            "user": self._username,
            "pass": self._password,
            "source": SOURCE,
            "format": "json",
            "commandname": "get_units",
        }
        return await self._starcom_request(command_data)

    async def async_get_last_transmit(self, unitnumber: str) -> list[dict]:
        """Get latest telemetry data for a specific unit.

        Args:
            unitnumber: The unit number from get_units.

        Returns:
            List with one dict containing telemetry data.
        """
        self._ensure_auth()
        command_data = {
            "user": self._username,
            "pass": self._password,
            "unitnumber": unitnumber,
            "source": SOURCE,
            "format": "json",
            "commandname": "get_last_transmit",
        }
        return await self._starcom_request(command_data)

    def _ensure_auth(self) -> None:
        """Raise if not authenticated."""
        if not self._token:
            raise ZeroApiClientAuthenticationError(
                "Not authenticated. Call async_login_with_code() first."
            )

    async def _starcom_request(self, command_data: dict) -> list[dict]:
        """Make a Starcom API request with encrypted command data.

        Args:
            command_data: Command parameters (user, pass, commandname, etc.)

        Returns:
            Parsed JSON response (usually a list).
        """
        url = f"{BASE_URL}/starcom/v1"
        headers = _make_headers()
        headers["Authorization"] = f"Bearer {self._token}"
        headers["Content-Type"] = "application/json; charset=utf-8"

        # Encrypt the entire command JSON object
        encrypted_data = cryptojs_encrypt(
            json.dumps(command_data, separators=(",", ":")),
            ENCRYPTION_KEY,
        )

        body = {"data": encrypted_data}

        response = await self._api_wrapper(
            method="post",
            url=url,
            json_data=body,
            headers=headers,
        )

        # Starcom returns either a list or a dict with zerocode
        if isinstance(response, dict) and "zerocode" in response:
            zerocode = response.get("zerocode")
            if zerocode in (401, 601, 602):
                raise ZeroApiClientAuthenticationError(
                    f"Starcom auth error: zerocode={zerocode}"
                )
            raise ZeroApiClientError(
                f"Starcom error: zerocode={zerocode}, "
                f"status={response.get('zerostatus', 'unknown')}"
            )

        return response

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        json_data: dict | None = None,
        headers: dict | None = None,
    ) -> any:
        """Execute an API request with error handling.

        Args:
            method: HTTP method (get/post).
            url: Full URL.
            data: Form-encoded data (sent as x-www-form-urlencoded).
            json_data: JSON body (sent as application/json).
            headers: Additional headers.

        Returns:
            Parsed JSON response.
        """
        try:
            async with async_timeout.timeout(30):
                response = await self._session.request(
                    method=method.upper(),
                    url=url,
                    data=data,
                    json=json_data,
                    headers=headers or _make_headers(),
                )

                if response.status in (401, 403):
                    raise ZeroApiClientAuthenticationError(
                        f"HTTP {response.status}: authentication failed"
                    )

                if response.status >= 400:
                    text = await response.text()
                    raise ZeroApiClientError(
                        f"HTTP {response.status}: {text[:200]}"
                    )

                try:
                    return await response.json()
                except (aiohttp.ContentTypeError, ValueError) as e:
                    text = await response.text()
                    raise ZeroApiClientError(
                        f"Invalid JSON response: {text[:200]}"
                    ) from e

        except asyncio.TimeoutError as exception:
            raise ZeroApiClientCommunicationError(
                "Timeout error fetching information"
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise ZeroApiClientCommunicationError(
                "Error fetching information"
            ) from exception
        except ZeroApiClientError:
            raise
        except Exception as exception:  # pylint: disable=broad-except
            raise ZeroApiClientError("Something really wrong happened!") from exception
