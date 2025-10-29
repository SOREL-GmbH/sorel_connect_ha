from __future__ import annotations

import asyncio
import logging
import socket
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback
from .const import (
    DOMAIN,
    CONF_BROKER_TLS,
    CONF_API_SERVER,
    CONF_API_URL,
    DEFAULT_PORT,
    DEFAULT_API_SERVER,
    DEFAULT_API_URL,
)
from .mqtt_gateway import MqttGateway

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


async def validate_mqtt_connection(host: str, port: int, username: str | None, password: str | None, tls: bool) -> None:
    """
    Test MQTT connection with provided credentials.
    Raises ConnectionError if connection fails.
    """
    # Dummy callback for testing
    async def dummy_callback(topic: str, payload: bytes):
        pass

    gateway = MqttGateway(
        host=host,
        port=port,
        username=username,
        password=password,
        tls_enabled=tls,
        on_message=dummy_callback
    )

    try:
        # Test connection with 10 second timeout
        await gateway.connect(timeout=10.0)
        _LOGGER.debug("MQTT connection test successful for %s:%s", host, port)
    finally:
        # Always clean up
        try:
            gateway.stop()
        except Exception as e:
            _LOGGER.debug("Error stopping test MQTT gateway: %s", e)


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
                # Convert empty strings to None for optional credentials
                username = user_input.get(CONF_USERNAME) or None
                password = user_input.get(CONF_PASSWORD) or None
                tls = bool(user_input.get(CONF_BROKER_TLS, False))

                # Test MQTT connection before creating entry
                try:
                    await validate_mqtt_connection(
                        host=user_input[CONF_HOST],
                        port=user_input[CONF_PORT],
                        username=username,
                        password=password,
                        tls=tls
                    )

                    # Connection successful, create entry
                    return self.async_create_entry(
                        title=f"Sorel Connect ({user_input[CONF_HOST]}:{user_input[CONF_PORT]})",
                        data=user_input,
                    )

                except asyncio.TimeoutError:
                    _LOGGER.error("MQTT connection test timed out for %s:%s", user_input[CONF_HOST], user_input[CONF_PORT])
                    errors["base"] = "timeout"
                except ConnectionRefusedError:
                    _LOGGER.error("MQTT broker refused connection on %s:%s (broker not running or wrong port)",
                                 user_input[CONF_HOST], user_input[CONF_PORT])
                    errors["base"] = "connection_refused"
                except socket.gaierror as e:
                    _LOGGER.error("Cannot resolve hostname '%s': %s", user_input[CONF_HOST], e)
                    errors["base"] = "cannot_resolve_host"
                except ConnectionError as e:
                    _LOGGER.error("MQTT connection test failed: %s", e)
                    # Check if it's an authentication error
                    if "Bad username or password" in str(e) or "Not authorized" in str(e):
                        errors["base"] = "invalid_auth"
                    else:
                        errors["base"] = "cannot_connect"
                except OSError as e:
                    # Catch other network-related errors (unreachable, etc.)
                    _LOGGER.error("Network error connecting to %s:%s: %s", user_input[CONF_HOST], user_input[CONF_PORT], e)
                    errors["base"] = "network_error"
                except Exception as e:
                    _LOGGER.exception("Unexpected error during MQTT connection test")
                    errors["base"] = "unknown"

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
                # Use hass config path for cache directory
                cache_dir = self.hass.config.path("sorel_meta_cache")
                count = clear_metadata_cache(cache_dir)
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
