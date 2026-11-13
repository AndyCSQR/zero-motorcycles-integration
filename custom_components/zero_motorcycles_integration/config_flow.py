"""Config flow for Zero Motorcycles Integration with MFA support."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    ZeroApiClient,
    ZeroApiClientAuthenticationError,
    ZeroApiClientCommunicationError,
    ZeroApiClientError,
)
from .const import CONF_REFRESH_TOKEN, CONF_SID, CONF_TOKEN, DOMAIN, LOGGER


class ZeroIntegrationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configuration flow implementation with MFA."""

    VERSION = 2  # Bumped for MFA + token storage

    def __init__(self) -> None:
        """Initialize flow with placeholders for MFA step."""
        self._username: str = ""
        self._password: str = ""

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user (username + password)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                client = ZeroApiClient(
                    username=username,
                    password=password,
                    session=async_get_clientsession(self.hass),
                )
                # Step 1: send MFA code
                await client.async_send_code()
            except ZeroApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                errors["base"] = "auth"
            except ZeroApiClientCommunicationError as exception:
                LOGGER.error(exception)
                errors["base"] = "connection"
            except ZeroApiClientError as exception:
                LOGGER.exception(exception)
                errors["base"] = "unknown"
            else:
                # Store credentials for the MFA step
                self._username = username
                self._password = password
                self._async_abort_entries_match({CONF_USERNAME: username})
                return self.async_show_form(
                    step_id="mfa",
                    data_schema=vol.Schema(
                        {
                            vol.Required("mfa_code", default=""): selector.TextSelector(
                                selector.TextSelectorConfig(
                                    type=selector.TextSelectorType.TEXT,
                                    autocomplete="one-time-code",
                                ),
                            ),
                        }
                    ),
                    description_placeholders={
                        "username": username,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.EMAIL,
                        ),
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_mfa(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle MFA code input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mfa_code = user_input["mfa_code"]

            try:
                client = ZeroApiClient(
                    username=self._username,
                    password=self._password,
                    session=async_get_clientsession(self.hass),
                )
                # Step 2: complete login with code
                await client.async_two_fa_login(mfa_code)

                # Save tokens in config entry
                data = {
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_TOKEN: client.token,
                    CONF_SID: client.sid,
                    CONF_REFRESH_TOKEN: client.refresh_token,
                }

                return self.async_create_entry(
                    title=f"Zero Motorcycles ({self._username})",
                    data=data,
                )

            except ZeroApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                errors["base"] = "invalid_code"
            except ZeroApiClientError as exception:
                LOGGER.exception(exception)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="mfa",
            data_schema=vol.Schema(
                {
                    vol.Required("mfa_code", default=""): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                            autocomplete="one-time-code",
                        ),
                    ),
                }
            ),
            description_placeholders={
                "username": self._username,
            },
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: dict,
    ) -> config_entries.FlowResult:
        """Handle reauth when token expires (after ~60 days)."""
        self._username = entry_data.get(CONF_USERNAME, "")
        self._password = entry_data.get(CONF_PASSWORD, "")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Confirm reauth and restart MFA flow."""
        if user_input is not None:
            # Send new MFA code and go to MFA step
            try:
                client = ZeroApiClient(
                    username=self._username,
                    password=self._password,
                    session=async_get_clientsession(self.hass),
                )
                await client.async_send_code()
            except ZeroApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                return self.async_abort(reason="auth_failed")
            except ZeroApiClientError as exception:
                LOGGER.exception(exception)
                return self.async_abort(reason="unknown")

            # Update existing config entry with new tokens after MFA
            return self.async_show_form(
                step_id="mfa_reauth",
                data_schema=vol.Schema(
                    {
                        vol.Required("mfa_code", default=""): selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.TEXT,
                                autocomplete="one-time-code",
                            ),
                        ),
                    }
                ),
                description_placeholders={
                    "username": self._username,
                },
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={
                "username": self._username,
            },
        )

    async def async_step_mfa_reauth(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle MFA code for reauth flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mfa_code = user_input["mfa_code"]

            try:
                client = ZeroApiClient(
                    username=self._username,
                    password=self._password,
                    session=async_get_clientsession(self.hass),
                )
                await client.async_two_fa_login(mfa_code)

                # Update existing config entry with new tokens
                entry = None
                for e in self.hass.config_entries.async_entries(DOMAIN):
                    if e.data.get(CONF_USERNAME) == self._username:
                        entry = e
                        break
                if entry:
                    new_data = {**entry.data}
                    new_data[CONF_TOKEN] = client.token
                    new_data[CONF_SID] = client.sid
                    new_data[CONF_REFRESH_TOKEN] = client.refresh_token
                    self.hass.config_entries.async_update_entry(
                        entry, data=new_data
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            except ZeroApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                errors["base"] = "invalid_code"
            except ZeroApiClientError as exception:
                LOGGER.exception(exception)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="mfa_reauth",
            data_schema=vol.Schema(
                {
                    vol.Required("mfa_code", default=""): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                            autocomplete="one-time-code",
                        ),
                    ),
                }
            ),
            description_placeholders={
                "username": self._username,
            },
            errors=errors,
        )

    async def async_step_import(
        self,
        import_config: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_config)
