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
        self.refresh_token: Optional[str] = None
        self.base_url = "https://api-eu-cypherstore-prod.zeromotorcycles.com"

    async def async_login(self, mfa_code: str) -> bool:
        """Login met MFA + retries."""
        url = f"{self.base_url}/dev/users/2falogin"
        
        data = {
            "email": self.email,
            "password": self.password,
            "code": mfa_code,
            "deviceType": "iOS",
            "appVersion": "2.13.0",
            "deviceId": "HA-Zero-Integration-v2"
        }

        headers = {
            "User-Agent": "nextgen/2.13.0 (com.zeromotorcycles.nextgen; build:21; iOS 18.0) Alamofire/5.10.2",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
            "Accept-Language": "en-BE,en;q=0.9",
            "Connection": "keep-alive"
        }

        for attempt in range(3):  # 3 pogingen
            try:
                _LOGGER.info(f"🔄 Login poging {attempt+1}/3...")
                
                timeout = aiohttp.ClientTimeout(total=40)
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, data=data, headers=headers) as resp:
                        text = await resp.text()
                        _LOGGER.info(f"Response status: {resp.status}")

                        if resp.status == 200:
                            result: Dict[str, Any] = await resp.json()
                            if result.get("result") == "ok":
                                self.token = result.get("token")
                                self.sid = result.get("sid")
                                self.refresh_token = result.get("refreshToken")
                                _LOGGER.info("✅ MFA Login SUCCESVOL!")
                                return True
                            else:
                                _LOGGER.error("API error: %s", result)
                                raise ZeroApiClientAuthenticationError("Ongeldige MFA-code")

                        elif resp.status == 504:
                            _LOGGER.warning("504 Gateway Timeout - wachten...")
                            await asyncio.sleep(3)
                            continue
                        else:
                            _LOGGER.error("HTTP %s: %s", resp.status, text[:300])
                            raise ZeroApiClientAuthenticationError(f"HTTP {resp.status}")

            except asyncio.TimeoutError:
                _LOGGER.warning(f"Timeout poging {attempt+1}")
                if attempt < 2:
                    await asyncio.sleep(5)
                    continue
                raise ZeroApiClientError("Timeout - Zero reageert niet (probeer over 5 minuten opnieuw)")
            except Exception as e:
                _LOGGER.error("Onverwachte fout: %s", e)
                if attempt < 2:
                    await asyncio.sleep(3)
                    continue
                raise

        raise ZeroApiClientError("Alle login pogingen mislukt")


    async def async_get_units(self) -> Dict:
        return {"units": []}   # tijdelijk dummy

    async def async_get_last_transmit(self, unitnumber: str) -> Dict:
        return {"status": "not_implemented"}  # tijdelijk dummy
