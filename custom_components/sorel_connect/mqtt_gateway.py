import asyncio
import json
import ssl
import logging
from typing import Callable, Awaitable
import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

class MqttGateway:
    def __init__(self, host, port, username, password, tls_enabled, on_message: Callable[[str, bytes], Awaitable[None]]):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._tls_enabled = tls_enabled
        self._on_message_cb = on_message
        self._client = mqtt.Client(client_id="ha-my-sorel-connect", clean_session=True)
        if username:
            self._client.username_pw_set(username, password)
        if tls_enabled:
            self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self._loop = asyncio.get_running_loop()

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_paho_message
        self._client.on_disconnect = self._on_disconnect

    async def connect(self):
        await self._loop.run_in_executor(None, self._client.connect, self._host, self._port, 60)
        self._client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            _LOGGER.info("Connected to MQTT broker")
        else:
            _LOGGER.error("MQTT connect failed rc=%s", rc)

    def _on_disconnect(self, client, userdata, rc):
        _LOGGER.warning("MQTT disconnected rc=%s", rc)

    def _on_paho_message(self, client, userdata, msg):
        # Übergibt an async Callback
        asyncio.run_coroutine_threadsafe(self._on_message_cb(msg.topic, msg.payload), self._loop)

    def subscribe(self, topic: str, qos: int = 0):
        self._client.subscribe(topic, qos=qos)

    def publish_json(self, topic: str, payload: dict, retain: bool = True, qos: int = 0):
        self._client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    def stop(self):
        self._client.loop_stop()
        self._client.disconnect()
