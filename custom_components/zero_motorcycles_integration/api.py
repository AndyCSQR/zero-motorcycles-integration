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
        """Login met MFA - maximale kans op succes."""
        url = f"{self.base_url}/dev/users/2falogin"
        
        data = {
            "email": self.email,
            "password": self.password,
            "code": mfa_code.strip(),
            "deviceType": "iOS",
            "appVersion": "2.13.0",
            "deviceId": "HA-Zero-2026"
        }

        headers = {
            "User-Agent": "nextgen/2.13.0 (com.zeromotorcycles.nextgen; build:21; iOS 18.0) Alamofire/5.10.2",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
            "Accept-Language": "en-BE,en;q=0.9",
        }

        _LOGGER.info("🔄 Zero login poging gestart...")

        for attempt in range(1, 4):
            try:
                timeout = aiohttp.ClientTimeout(total=60)  # 60 seconden geduld
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, data=data, headers=headers) as resp:
                        text = await resp.text()
                        
                        _LOGGER.info(f"Poging {attempt}: HTTP {resp.status}")

                        if resp.status == 200:
                            result: Dict[str, Any] = await resp.json()
                            if result.get("result") == "ok":
                                self.token = result.get("token")
                                self.sid = result.get("sid")
                                _LOGGER.info("✅ MFA Login SUCCESVOL!")
                                return True
                            else:
                                _LOGGER.error("API weigerde: %s", result)
                                raise ZeroApiClientAuthenticationError("Ongeldige code")

                        elif resp.status == 504:
                            _LOGGER.warning("504 Timeout van Zero server")
                        else:
                            _LOGGER.error("HTTP %s: %s", resp.status, text[:300])

            except asyncio.TimeoutError:
                _LOGGER.warning(f"Timeout poging {attempt}")
            except Exception as e:
                _LOGGER.error("Fout poging %s: %s", attempt, e)

            if attempt < 3:
                await asyncio.sleep(4)  # even wachten tussen pogingen

        raise ZeroApiClientError("Zero reageert niet (timeout). Probeer over 5-10 minuten opnieuw met een verse code.")
