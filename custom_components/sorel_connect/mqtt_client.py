"""Abstract MQTT client interface with two implementations:
1. HaMqttClient - uses Home Assistant's built-in MQTT integration
2. CustomMqttClient - uses custom paho-mqtt gateway for external brokers
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.components import mqtt as ha_mqtt
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .mqtt_gateway import MqttGateway
from .const import SIGNAL_MQTT_CONNECTION_STATE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MqttClient(ABC):
    """Abstract MQTT client interface."""

    @abstractmethod
    async def connect(self) -> None:
        """Connect to MQTT broker. Raises ConnectionError if connection fails."""
        pass

    @abstractmethod
    def subscribe(self, topic: str, qos: int = 0) -> None:
        """Subscribe to an MQTT topic."""
        pass

    @abstractmethod
    def publish_json(self, topic: str, payload: dict, retain: bool = True, qos: int = 0) -> None:
        """Publish JSON payload to MQTT topic."""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if currently connected to MQTT broker."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop MQTT client and disconnect."""
        pass


class HaMqttClient(MqttClient):
    """MQTT client using Home Assistant's built-in MQTT integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        on_message: Callable[[str, bytes], Awaitable[None]],
        on_connection_change: Optional[Callable[[bool], Awaitable[None]]] = None,
    ) -> None:
        """Initialize HA MQTT client.

        Args:
            hass: Home Assistant instance
            on_message: Async callback for incoming messages (topic, payload)
            on_connection_change: Optional async callback for connection state changes (connected: bool)
        """
        self._hass = hass
        self._on_message_cb = on_message
        self._on_connection_change_cb = on_connection_change
        self._subscribed_topics: list[str] = []
        self._unsubscribe_callbacks: list[Callable[[], None]] = []
        self._is_ready = False

    async def connect(self) -> None:
        """Verify MQTT integration is available and ready."""
        try:
            # Wait for MQTT integration to be ready (with 10 second timeout)
            ready = await asyncio.wait_for(
                ha_mqtt.async_wait_for_mqtt_client(self._hass),
                timeout=10.0
            )

            if not ready:
                raise ConnectionError("MQTT integration is not configured in Home Assistant")

            self._is_ready = True
            _LOGGER.info("Using Home Assistant MQTT integration")

            # Notify connection established
            if self._on_connection_change_cb:
                await self._on_connection_change_cb(True)

        except asyncio.TimeoutError:
            raise ConnectionError("Timeout waiting for Home Assistant MQTT integration to be ready")
        except Exception as e:
            _LOGGER.error("Failed to connect to HA MQTT integration: %s", e)
            raise ConnectionError(f"Failed to connect to HA MQTT integration: {e}")

    @callback
    def _ha_mqtt_message_received(self, msg) -> None:
        """Handle incoming MQTT message from HA MQTT integration."""
        topic = msg.topic
        payload = msg.payload

        # HA MQTT provides payload as string, but our interface expects bytes
        # Convert to bytes to match paho-mqtt behavior
        if isinstance(payload, str):
            payload = payload.encode('utf-8')

        # Schedule the async callback
        asyncio.create_task(self._on_message_cb(topic, payload))

    def subscribe(self, topic: str, qos: int = 0) -> None:
        """Subscribe to an MQTT topic using HA MQTT integration."""
        if not self._is_ready:
            _LOGGER.warning("Cannot subscribe to %s: MQTT not ready", topic)
            return

        _LOGGER.debug("Subscribing to topic: %s (QoS %d)", topic, qos)

        # Schedule the async subscription
        asyncio.create_task(self._async_subscribe(topic, qos))

    async def _async_subscribe(self, topic: str, qos: int = 0) -> None:
        """Async helper for subscribing to topics."""
        try:
            unsubscribe = await ha_mqtt.async_subscribe(
                self._hass,
                topic,
                self._ha_mqtt_message_received,
                qos=qos
            )
            self._subscribed_topics.append(topic)
            self._unsubscribe_callbacks.append(unsubscribe)
            _LOGGER.info("Subscribed to MQTT topic: %s", topic)
        except Exception as e:
            _LOGGER.error("Failed to subscribe to topic %s: %s", topic, e)

    def publish_json(self, topic: str, payload: dict, retain: bool = True, qos: int = 0) -> None:
        """Publish JSON payload to MQTT topic using HA MQTT integration."""
        if not self._is_ready:
            _LOGGER.warning("Cannot publish to %s: MQTT not ready", topic)
            return

        # Schedule the async publish
        asyncio.create_task(self._async_publish_json(topic, payload, retain, qos))

    async def _async_publish_json(self, topic: str, payload: dict, retain: bool = True, qos: int = 0) -> None:
        """Async helper for publishing JSON."""
        try:
            await ha_mqtt.async_publish(
                self._hass,
                topic,
                json.dumps(payload),
                qos=qos,
                retain=retain
            )
        except Exception as e:
            _LOGGER.error("Failed to publish to topic %s: %s", topic, e)

    @property
    def is_connected(self) -> bool:
        """Return True if HA MQTT integration is ready."""
        return self._is_ready

    def stop(self) -> None:
        """Unsubscribe from all topics and clean up."""
        _LOGGER.debug("Stopping HA MQTT client, unsubscribing from %d topics", len(self._unsubscribe_callbacks))

        # Call all unsubscribe callbacks
        for unsubscribe in self._unsubscribe_callbacks:
            try:
                unsubscribe()
            except Exception as e:
                _LOGGER.error("Error unsubscribing: %s", e)

        self._unsubscribe_callbacks.clear()
        self._subscribed_topics.clear()
        self._is_ready = False

        # Notify disconnection
        if self._on_connection_change_cb:
            asyncio.create_task(self._on_connection_change_cb(False))


class CustomMqttClient(MqttClient):
    """MQTT client using custom paho-mqtt gateway for external brokers."""

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
        """Initialize custom MQTT client.

        Args:
            host: MQTT broker hostname
            port: MQTT broker port
            username: Optional MQTT username
            password: Optional MQTT password
            tls_enabled: Whether to use TLS
            on_message: Async callback for incoming messages (topic, payload)
            on_connection_change: Optional async callback for connection state changes (connected: bool)
        """
        self._gateway = MqttGateway(
            host=host,
            port=port,
            username=username,
            password=password,
            tls_enabled=tls_enabled,
            on_message=on_message,
            on_connection_change=on_connection_change,
        )

    async def connect(self) -> None:
        """Connect to MQTT broker via custom gateway."""
        await self._gateway.connect()

    def subscribe(self, topic: str, qos: int = 0) -> None:
        """Subscribe to an MQTT topic via custom gateway."""
        self._gateway.subscribe(topic, qos=qos)

    def publish_json(self, topic: str, payload: dict, retain: bool = True, qos: int = 0) -> None:
        """Publish JSON payload to MQTT topic via custom gateway."""
        self._gateway.publish_json(topic, payload, retain=retain, qos=qos)

    @property
    def is_connected(self) -> bool:
        """Return connection status from custom gateway."""
        return self._gateway.is_connected

    def stop(self) -> None:
        """Stop custom gateway and disconnect."""
        self._gateway.stop()
