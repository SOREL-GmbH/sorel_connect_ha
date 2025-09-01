from __future__ import annotations
import logging
from typing import Dict, Set
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .const import DOMAIN, SIGNAL_NEW_DEVICE
from .topic_parser import parse_topic, ParsedTopic

_LOGGER = logging.getLogger(__name__)

class Coordinator:
    def __init__(self, hass: HomeAssistant, mqtt_gw, meta_client, topic_prefix: str, auto_onboard: bool):
        self.hass = hass
        self.mqtt = mqtt_gw
        self.meta = meta_client
        self.prefix = topic_prefix
        self.auto = auto_onboard
        self._known_devices: Set[str] = set()  # device_key

    async def start(self):
        # wildcard passt zu deiner Struktur
        self.mqtt.subscribe("+/device/+/+/+/+/dp/+/+")
        _LOGGER.debug("Subscribed to topic wildcard for device datapoints")

    async def handle_message(self, topic: str, payload: bytes):
        pt = parse_topic(topic)
        if not pt:
            _LOGGER.debug("Ignored topic (no match): %s", topic)
            return
        # _LOGGER.debug("Received message on topic: %s", topic)
        
        # 1) neues Gerät?
        if pt.device_key not in self._known_devices:
            self._known_devices.add(pt.device_key)
            _LOGGER.info("Discovered new device: %s (%s:%s)", pt.device_key, pt.oem_name, pt.device_name)
            # Geräte-Anlage auslösen (Entities registrieren)
            async_dispatcher_send(self.hass, SIGNAL_NEW_DEVICE, pt)

        # 2) Hier später: Werteverarbeitung (address/unit_id → Entitäten updaten)
        #    z.B. self._route_datapoint(pt, payload)
