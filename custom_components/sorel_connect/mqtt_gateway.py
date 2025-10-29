import asyncio
import json
import ssl
import logging
import secrets
from typing import Callable, Awaitable, Optional
import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

# MQTT connection error codes
MQTT_ERR_SUCCESS = 0
MQTT_ERR_UNACCEPTABLE_PROTOCOL_VERSION = 1
MQTT_ERR_IDENTIFIER_REJECTED = 2
MQTT_ERR_SERVER_UNAVAILABLE = 3
MQTT_ERR_BAD_USERNAME_PASSWORD = 4
MQTT_ERR_NOT_AUTHORIZED = 5

MQTT_ERROR_MESSAGES = {
    MQTT_ERR_UNACCEPTABLE_PROTOCOL_VERSION: "Unacceptable protocol version",
    MQTT_ERR_IDENTIFIER_REJECTED: "Identifier rejected",
    MQTT_ERR_SERVER_UNAVAILABLE: "Server unavailable",
    MQTT_ERR_BAD_USERNAME_PASSWORD: "Bad username or password",
    MQTT_ERR_NOT_AUTHORIZED: "Not authorized",
}

class MqttGateway:
    """MQTT Gateway with async support using paho-mqtt."""

    def __init__(
        self,
        host: str,
        port: int,
        username: Optional[str],
        password: Optional[str],
        tls_enabled: bool,
        on_message: Callable[[str, bytes], Awaitable[None]],
        on_connection_change: Optional[Callable[[bool], Awaitable[None]]] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._tls_enabled = tls_enabled
        self._on_message_cb = on_message
        self._on_connection_change_cb = on_connection_change
        # Generate unique client ID to avoid conflicts between multiple instances
        unique_suffix = secrets.token_hex(4)
        self._client = mqtt.Client(client_id=f"ha-sorel-connect-{unique_suffix}", clean_session=True)
        if username:
            self._client.username_pw_set(username, password)
        if tls_enabled:
            self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self._loop = asyncio.get_running_loop()
        self._connect_future: Optional[asyncio.Future] = None
        self._is_connected: bool = False
        self._reconnect_count: int = 0

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_paho_message
        self._client.on_disconnect = self._on_disconnect

    async def connect(self, timeout: float = 10.0) -> None:
        """Connect to MQTT broker with timeout. Raises ConnectionError if connection fails."""
        self._connect_future = self._loop.create_future()

        try:
            await self._loop.run_in_executor(None, self._client.connect, self._host, self._port, 60)
            self._client.loop_start()

            # Wait for connection callback with timeout
            try:
                await asyncio.wait_for(self._connect_future, timeout=timeout)
            except asyncio.TimeoutError:
                self._client.loop_stop()
                raise ConnectionError(f"Connection to MQTT broker {self._host}:{self._port} timed out after {timeout}s")

        except Exception as e:
            if self._connect_future and not self._connect_future.done():
                self._connect_future.cancel()
            self._connect_future = None
            raise

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            was_reconnect = self._reconnect_count > 0
            if was_reconnect:
                _LOGGER.info("Reconnected to MQTT broker (attempt %d)", self._reconnect_count)
                self._reconnect_count = 0
            else:
                _LOGGER.info("Connected to MQTT broker")

            self._is_connected = True

            # Notify about connection state change
            if self._on_connection_change_cb:
                asyncio.run_coroutine_threadsafe(
                    self._on_connection_change_cb(True),
                    self._loop
                )

            if self._connect_future and not self._connect_future.done():
                self._connect_future.set_result(True)
        else:
            error_msg = MQTT_ERROR_MESSAGES.get(rc, f"Unknown error (code {rc})")
            _LOGGER.error("MQTT connect failed rc=%s: %s", rc, error_msg)
            self._is_connected = False
            if self._connect_future and not self._connect_future.done():
                self._connect_future.set_exception(
                    ConnectionError(f"MQTT connection failed: {error_msg} (rc={rc})")
                )

    def _on_disconnect(self, client, userdata, rc):
        was_connected = self._is_connected
        self._is_connected = False

        if rc == 0:
            _LOGGER.info("MQTT disconnected gracefully")
        else:
            _LOGGER.warning("MQTT disconnected unexpectedly (rc=%s), will auto-reconnect", rc)
            self._reconnect_count += 1

        # Notify about connection state change (only if we were actually connected)
        if was_connected and self._on_connection_change_cb:
            asyncio.run_coroutine_threadsafe(
                self._on_connection_change_cb(False),
                self._loop
            )

    def _on_paho_message(self, client, userdata, msg) -> None:
        """Handle incoming MQTT message and pass to async callback."""
        asyncio.run_coroutine_threadsafe(self._on_message_cb(msg.topic, msg.payload), self._loop)

    def subscribe(self, topic: str, qos: int = 0) -> None:
        """Subscribe to an MQTT topic."""
        self._client.subscribe(topic, qos=qos)

    def publish_json(self, topic: str, payload: dict, retain: bool = True, qos: int = 0) -> None:
        """Publish JSON payload to MQTT topic."""
        self._client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    @property
    def is_connected(self) -> bool:
        """Return True if currently connected to MQTT broker."""
        return self._is_connected

    def stop(self) -> None:
        """Stop MQTT client and disconnect."""
        self._client.loop_stop()
        self._client.disconnect()
