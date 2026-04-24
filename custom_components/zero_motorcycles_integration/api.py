import aiohttp
import asyncio
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
        self.base_url = "https://api-eu-cypherstore-prod.zeromotorcycles.com"

    async def async_login(self, mfa_code: str) -> bool:
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
        }

        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=data, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    _LOGGER.error("Login failed HTTP %s: %s", resp.status, text[:200])
                    raise ZeroApiClientAuthenticationError("Login mislukt")

                result: Dict[str, Any] = await resp.json()
                if result.get("result") == "ok":
                    self.token = result.get("token")
                    self.sid = result.get("sid")
                    _LOGGER.info("✅ MFA Login succesvol")
                    return True
                else:
                    raise ZeroApiClientAuthenticationError("Ongeldige MFA-code")


class ZeroApiClientAuthenticationError(HomeAssistantError):
    """Authentication error (wrong password or MFA)."""


class ZeroApiClientError(HomeAssistantError):
    """General API error."""
