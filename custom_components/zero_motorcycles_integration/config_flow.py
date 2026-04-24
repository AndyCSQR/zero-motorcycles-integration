from homeassistant import config_entries
import voluptuous as vol
import logging

from .api import ZeroApiClient, ZeroApiClientAuthenticationError, ZeroApiClientError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class ZeroConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            email = user_input["email"]
            password = user_input["password"]
            mfa_code = user_input["mfa_code"]

            client = ZeroApiClient(email, password)

            try:
                await client.async_login(mfa_code)
                return self.async_create_entry(
                    title=f"Zero Motorcycles ({email})",
                    data={"email": email, "password": password}
                )

            except ZeroApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except ZeroApiClientError:
                errors["base"] = "cannot_connect"
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
            description_placeholders={"mfa_info": "Verse code uit je email (via Zero app)."}
        )
