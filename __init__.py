from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, Platform

from .const import (
    DOMAIN,
    CONF_BROKER_TLS,
    CONF_META_BASEURL,
    CONF_TOPIC_PREFIX,
    CONF_AUTO_ONBOARD,
)
from .mqtt_gateway import MqttGateway
from .meta_client import MetaClient
from .coordinator import Coordinator

PLATFORMS = [Platform.SENSOR]  # später LIGHT, SWITCH, NUMBER, ...

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = entry.data
    host = data.get(CONF_HOST)
    port = data.get(CONF_PORT, 1883)
    username = data.get(CONF_USERNAME) or None
    password = data.get(CONF_PASSWORD) or None
    tls = bool(data.get(CONF_BROKER_TLS, False))
    meta_base = data.get(CONF_META_BASEURL)
    topic_prefix = data.get(CONF_TOPIC_PREFIX, "vendor")
    auto_onboard = bool(data.get(CONF_AUTO_ONBOARD, True))

    _LOGGER.debug("-INIT 0/4: Setting up %s: host=%s port=%s tls=%s meta=%s prefix=%s auto=%s",
                  DOMAIN, host, port, tls, meta_base, topic_prefix, auto_onboard)

    # 1) MQTT verbinden (mit sauberem Retry, falls offline)
    try:
        async def on_msg(topic: str, payload: bytes):
            await hass.data[DOMAIN]["coordinator"].handle_message(topic, payload)

        gw = MqttGateway(
            host=host,
            port=port,
            username=username,
            password=password,
            tls_enabled=tls,
            on_message=on_msg
        )
        await gw.connect()  # wirft bei Nichterreichbarkeit

        _LOGGER.debug("-INIT 1/4: MQTT connected")
    except Exception as err:
        _LOGGER.exception("-INIT 1/4: MQTT connect failed to %s:%s", host, port)
        raise ConfigEntryNotReady from err

    # 2) Metadaten-Client (nutze HA-Session)
    try:
        from homeassistant.helpers import aiohttp_client
        session = aiohttp_client.async_get_clientsession(hass)
        meta = MetaClient(meta_base, session)
        # Optional: schnelle Probe, ob Server antwortet:
        # await meta.get_capabilities("ping")  # falls deine API sowas hat
        _LOGGER.debug("-INIT 2/4: Meta client initialized for %s", meta_base)
    except Exception as err:
        _LOGGER.exception("-INIT 2/4: Meta client init/healthcheck failed")
        gw.stop()
        raise ConfigEntryNotReady from err

    # 3) Coordinator starten
    try:
        coord = Coordinator(
            hass=hass,
            mqtt_gw=gw,
            meta_client=meta,
            topic_prefix=topic_prefix,
            auto_onboard=auto_onboard,
        )
        await coord.start()
        _LOGGER.debug("-INIT 3/4: Coordinator started")
    except Exception as err:
        _LOGGER.exception("-INIT 3/4: Coordinator start failed")
        gw.stop()
        raise ConfigEntryNotReady from err

    # 4) State ablegen + Reload unterstützen
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = {
        "mqtt": gw,
        "coordinator": coord,
        "session": session,
    }
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("-INIT 4/4: Setup complete")

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data.get(DOMAIN)
    if not data:
        return True
    try:
        data["mqtt"].stop()
    except Exception:  # defensiv
        _LOGGER.debug("mqtt.stop() ignored exception", exc_info=True)
    hass.data.pop(DOMAIN, None)

    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
