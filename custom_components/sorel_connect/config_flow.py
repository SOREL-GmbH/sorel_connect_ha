from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback
from .const import (
    DOMAIN,
    CONF_MODE,
    CONF_BROKER_TLS,
    CONF_TOPIC_PREFIX,
    CONF_AUTO_ONBOARD,
    CONF_API_SERVER,
    CONF_API_URL,
    DEFAULT_PORT,
    DEFAULT_PREFIX,
    DEFAULT_API_SERVER,
    DEFAULT_API_URL,
)

# User configuration schema
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="mosquitto"): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME, default=""): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
        vol.Optional(CONF_BROKER_TLS, default=False): bool,
        vol.Required(CONF_TOPIC_PREFIX, default=DEFAULT_PREFIX): str,
        vol.Required(CONF_AUTO_ONBOARD, default=True): bool,
        vol.Required(CONF_API_SERVER, default=DEFAULT_API_SERVER): str,
        vol.Required(CONF_API_URL, default=DEFAULT_API_URL): str,
    }
)


class SorelConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            # Basic validation: broker host must not be empty
            if not user_input[CONF_HOST]:
                errors["base"] = "invalid_host"
            else:
                # Create config entry if validation passes
                return self.async_create_entry(
                    title=f"Sorel Connect ({user_input[CONF_HOST]}:{user_input[CONF_PORT]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SorelConnectOptionsFlowHandler(config_entry)


class SorelConnectOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for adjusting settings."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_TOPIC_PREFIX,
                    default=self.config_entry.data.get(CONF_TOPIC_PREFIX, DEFAULT_PREFIX),
                ): str,
                vol.Required(
                    CONF_AUTO_ONBOARD,
                    default=self.config_entry.data.get(CONF_AUTO_ONBOARD, True),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )
