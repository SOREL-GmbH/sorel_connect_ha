from __future__ import annotations

import asyncio
import logging
import os
import shutil
import socket
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, Platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    CONF_BROKER_TLS,
    CONF_API_SERVER,
    CONF_API_URL,
    DEFAULT_API_SERVER,
    DEFAULT_API_URL,
    SIGNAL_MQTT_CONNECTION_STATE,
)
from .mqtt_gateway import MqttGateway
from .meta_client import MetaClient
from .coordinator import Coordinator
from .sensor_types import load_sensor_types, load_relay_modes

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

_LOGGER = logging.getLogger(__name__)

def clear_metadata_cache(cache_dir: str = "/config/sorel_meta_cache") -> int:
    """
    Clear all cached metadata files.
    Returns the number of files deleted.
    """
    if not os.path.exists(cache_dir):
        _LOGGER.debug("Cache directory does not exist: %s", cache_dir)
        return 0

    try:
        file_count = len([f for f in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, f))])
        shutil.rmtree(cache_dir)
        os.makedirs(cache_dir, exist_ok=True)
        _LOGGER.info("Cleared metadata cache: deleted %d files from %s", file_count, cache_dir)
        return file_count
    except Exception as e:
        _LOGGER.error("Failed to clear metadata cache at %s: %s", cache_dir, e)
        return 0

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Load sensor types CSV early (before any sensors are created)
    sensor_types = load_sensor_types()
    _LOGGER.info("Sensor types loaded: %d types available", len(sensor_types))

    # Load relay modes CSV
    relay_modes = load_relay_modes()
    _LOGGER.info("Relay modes loaded: %d modes available", len(relay_modes))

    data = entry.data
    host = data.get(CONF_HOST)
    port = data.get(CONF_PORT, 1883)
    username = data.get(CONF_USERNAME) or None
    password = data.get(CONF_PASSWORD) or None
    tls = bool(data.get(CONF_BROKER_TLS, False))

    # API settings: check options first, then data (backwards compat), then defaults
    api_server = entry.options.get(
        CONF_API_SERVER,
        data.get(CONF_API_SERVER, DEFAULT_API_SERVER)
    )
    api_url_template = entry.options.get(
        CONF_API_URL,
        data.get(CONF_API_URL, DEFAULT_API_URL)
    )

    _LOGGER.debug("-INIT 0/4: Setting up %s: host=%s port=%s tls=%s api_server=%s api_url=%s",
                  DOMAIN, host, port, tls, api_server, api_url_template)

    # 1) Connect to MQTT broker (with clean retry if offline)
    try:
        async def on_msg(topic: str, payload: bytes):
            await hass.data[DOMAIN]["coordinator"].handle_message(topic, payload)

        async def on_connection_change(is_connected: bool):
            """Notify all listeners about MQTT connection state change."""
            _LOGGER.info("MQTT connection state changed: %s", "connected" if is_connected else "disconnected")
            async_dispatcher_send(hass, SIGNAL_MQTT_CONNECTION_STATE, is_connected)

        gw = MqttGateway(
            host=host,
            port=port,
            username=username,
            password=password,
            tls_enabled=tls,
            on_message=on_msg,
            on_connection_change=on_connection_change
        )
        await gw.connect()  # Raises exception if unreachable

        _LOGGER.debug("-INIT 1/4: MQTT connected")
    except asyncio.TimeoutError:
        _LOGGER.error("-INIT 1/4: MQTT connection timed out for %s:%s", host, port)
        raise ConfigEntryNotReady(f"MQTT broker connection timed out ({host}:{port}). Check if broker is responding.")
    except ConnectionRefusedError:
        _LOGGER.error("-INIT 1/4: MQTT broker refused connection on %s:%s (broker not running or wrong port)", host, port)
        raise ConfigEntryNotReady(f"MQTT connection refused by {host}:{port}. Check if broker is running and port is correct.")
    except socket.gaierror as err:
        _LOGGER.error("-INIT 1/4: Cannot resolve hostname '%s': %s", host, err)
        raise ConfigEntryNotReady(f"Cannot resolve MQTT broker hostname '{host}'. Check if the address is correct.")
    except ConnectionError as err:
        _LOGGER.error("-INIT 1/4: MQTT connection failed: %s", err)
        # Check if it's an authentication error
        if "Bad username or password" in str(err) or "Not authorized" in str(err):
            raise ConfigEntryNotReady(f"MQTT authentication failed for {host}:{port}. Check username/password.")
        else:
            raise ConfigEntryNotReady(f"Failed to connect to MQTT broker {host}:{port}: {err}")
    except OSError as err:
        _LOGGER.error("-INIT 1/4: Network error connecting to %s:%s: %s", host, port, err)
        raise ConfigEntryNotReady(f"Network error connecting to MQTT broker {host}:{port}. Check network/firewall.")
    except Exception as err:
        _LOGGER.exception("-INIT 1/4: Unexpected error connecting to MQTT broker %s:%s", host, port)
        raise ConfigEntryNotReady(f"Unexpected error connecting to MQTT broker {host}:{port}: {err}")

    # 2) Initialize metadata client (use HA session)
    try:
        from homeassistant.helpers import aiohttp_client
        session = aiohttp_client.async_get_clientsession(hass)
        meta = MetaClient(api_server, api_url_template, session)
        _LOGGER.debug("-INIT 2/4: Meta client initialized for %s%s", api_server, api_url_template)
    except Exception as err:
        _LOGGER.exception("-INIT 2/4: Meta client init/healthcheck failed")
        gw.stop()
        raise ConfigEntryNotReady from err

    # 3) Start coordinator
    try:
        coord = Coordinator(
            hass=hass,
            mqtt_gw=gw,
            meta_client=meta,
        )
        await coord.start()
        _LOGGER.debug("-INIT 3/4: Coordinator started")
    except Exception as err:
        _LOGGER.exception("-INIT 3/4: Coordinator start failed")
        gw.stop()
        raise ConfigEntryNotReady from err

    # 4) Store state and support reload
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = {
        "mqtt": gw,
        "coordinator": coord,
        "session": session,
    }
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register service for manual cache clearing
    async def handle_clear_cache(call):
        """Handle the clear_metadata_cache service call."""
        _LOGGER.info("Clear metadata cache service called")
        count = clear_metadata_cache()
        _LOGGER.info("Service cleared %d cached metadata files", count)

    hass.services.async_register(DOMAIN, "clear_metadata_cache", handle_clear_cache)

    _LOGGER.debug("-INIT 4/4: Setup complete")

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data.get(DOMAIN)
    if not data:
        return True
    try:
        data["mqtt"].stop()
    except Exception:  # Defensive
        _LOGGER.debug("mqtt.stop() ignored exception", exc_info=True)
    hass.data.pop(DOMAIN, None)

    # Unregister service
    hass.services.async_remove(DOMAIN, "clear_metadata_cache")

    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
