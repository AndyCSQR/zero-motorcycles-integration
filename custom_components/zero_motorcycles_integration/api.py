import aiohttp
import logging
from typing import Optional, Dict, Any
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

class ZeroApiClient:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.token: Optional[str] = None
        self.sid: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.base_url = "https://api-eu-cypherstore-prod.zeromotorcycles.com"

    async def async_login(self, mfa_code: str) -> bool:
        """Login met MFA (2FA via email)."""
        url = f"{self.base_url}/dev/users/2falogin"
        data = {
            "email": self.email,
            "password": self.password,
            "code": mfa_code,
            "deviceType": "iOS",
            "appVersion": "2.13.0"
        }

        headers = {
            "User-Agent": "nextgen/2.13.0 (com.zeromotorcycles.nextgen; build:21; iOS 18.0) Alamofire/5.10.2",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    _LOGGER.error("Login HTTP %s: %s", resp.status, text)
                    raise ZeroApiClientAuthenticationError("Login mislukt (HTTP error)")

                result: Dict[str, Any] = await resp.json()
                if result.get("result") != "ok":
                    _LOGGER.error("Login API error: %s", result)
                    raise ZeroApiClientAuthenticationError("Ongeldige MFA-code of credentials")

                self.token = result.get("token")
                self.sid = result.get("sid")
                self.refresh_token = result.get("refreshToken")
                _LOGGER.info("✅ Zero login succesvol - token ontvangen")
                return True

    async def async_get_units(self) -> Dict:
        return await self._starcom_call({"command": "get_units"})

    async def async_get_last_transmit(self, unitnumber: str) -> Dict:
        return await self._starcom_call({
            "command": "get_last_transmit",
            "unitnumber": unitnumber
        })

    async def _starcom_call(self, command_payload: Dict) -> Dict:
        """Placeholder voor encrypted calls."""
        if not self.token:
            raise ZeroApiClientAuthenticationError("Geen token aanwezig")

        url = f"{self.base_url}/starcom/v1"

        payload = {
            "token": self.token,
            "sid": self.sid,
            **command_payload
        }

        headers = {
            "User-Agent": "nextgen/2.13.0 (com.zeromotorcycles.nextgen; build:21; iOS 18.0) Alamofire/5.10.2",
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                text = await resp.text()
                _LOGGER.debug("Starcom response: %s", text[:800])

                if resp.status == 200:
                    try:
                        return await resp.json()
                    except Exception:
                        return {"raw": text}
                else:
                    raise ZeroApiClientError(f"Starcom error {resp.status}: {text[:300]}")


class ZeroApiClientAuthenticationError(HomeAssistantError):
    """Invalid auth or MFA."""


class ZeroApiClientError(HomeAssistantError):
    """General API error."""
