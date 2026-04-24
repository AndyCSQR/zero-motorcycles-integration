from homeassistant import config_entries
import voluptuous as vol
from .api import ZeroApiClient, ZeroApiClientAuthenticationError
from .const import DOMAIN

class ZeroConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            email = user_input["email"]
            password = user_input["password"]
            mfa_code = user_input.get("mfa_code", "")

            client = ZeroApiClient(email, password)
            try:
                await client.async_login(mfa_code)
                return self.async_create_entry(
                    title=f"Zero Motorcycles ({email})",
                    data={"email": email, "password": password}
                )
            except ZeroApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception as e:
                _LOGGER.exception(e)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("email"): str,
                vol.Required("password"): str,
                vol.Required("mfa_code"): str,
            }),
            errors=errors,
            description_placeholders={
                "mfa_info": "Vul de code in die je via email van Zero krijgt (open de app even om de code op te vragen)."
            }
        )
