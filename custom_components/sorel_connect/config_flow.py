from __future__ import annotations

import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback
from .const import (
    DOMAIN,
    CONF_MODE,
    CONF_BROKER_TLS,
    CONF_API_SERVER,
    CONF_API_URL,
    DEFAULT_PORT,
    DEFAULT_API_SERVER,
    DEFAULT_API_URL,
)

_LOGGER = logging.getLogger(__name__)

# User configuration schema - only MQTT settings for initial setup
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="localhost"): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME, default=""): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
        vol.Optional(CONF_BROKER_TLS, default=False): bool,
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

        # Get current values from options (if set), otherwise from data, otherwise defaults
        current_api_server = self.config_entry.options.get(
            CONF_API_SERVER,
            self.config_entry.data.get(CONF_API_SERVER, DEFAULT_API_SERVER)
        )
        current_api_url = self.config_entry.options.get(
            CONF_API_URL,
            self.config_entry.data.get(CONF_API_URL, DEFAULT_API_URL)
        )

        if user_input is not None:
            # Check if API settings changed
            new_api_server = user_input.get(CONF_API_SERVER)
            new_api_url = user_input.get(CONF_API_URL)

            if new_api_server != current_api_server or new_api_url != current_api_url:
                _LOGGER.info("API settings changed, clearing metadata cache")
                # Import here to avoid circular dependency
                from . import clear_metadata_cache
                count = clear_metadata_cache()
                _LOGGER.info("Cleared %d cached metadata files due to API settings change", count)

            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Required(CONF_API_SERVER, default=current_api_server): str,
                vol.Required(CONF_API_URL, default=current_api_url): str,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )
