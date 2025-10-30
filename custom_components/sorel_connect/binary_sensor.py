from __future__ import annotations
import logging
from datetime import datetime
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, SIGNAL_NEW_DEVICE, SIGNAL_MQTT_CONNECTION_STATE, SIGNAL_DP_UPDATE
from .topic_parser import ParsedTopic
from .sensor_types import parse_relay_name, get_relay_config

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up binary sensor platform for Sorel Connect."""

    # Track created binary relay sensors to avoid duplicates
    binary_relay_sensors: dict[str, RelayBinarySensor] = {}

    # Create global MQTT connection status sensor (no device association)
    mqtt_connection_sensor = MqttConnectionStatusBinarySensor(entry)
    async_add_entities([mqtt_connection_sensor], update_before_add=False)

    @callback
    def _on_new_device(pt: ParsedTopic):
        """Create binary sensor when new device is discovered."""
        # Create metadata status binary sensor (problem indicator)
        entities = [
            MetadataStatusBinarySensor(pt),
        ]
        async_add_entities(entities, update_before_add=False)

    @callback
    def _on_dp_update(device_key: str, address: int, value):
        """Handle datapoint update - create binary relay sensors for switched relays."""
        # Get parsed topic from hass data
        parsed_topics = hass.data.get(DOMAIN, {}).get("parsed_topics", {})
        if device_key not in parsed_topics:
            # Store parsed topic if not exists (should be set by coordinator)
            return

        pt = parsed_topics.get(device_key)
        if not pt:
            return

        # Get datapoint metadata
        coordinator = hass.data[DOMAIN]["coordinator"]
        datapoints = coordinator._datapoints.get(device_key, [])

        # Find the datapoint for this address
        dp_meta = None
        for dp in datapoints:
            if int(dp.get("address", -1)) == address:
                dp_meta = dp
                break

        if not dp_meta:
            return  # Skip if no metadata

        sensor_name = dp_meta.get("name", "")

        # Check if this is a relay (R1, R2, etc.)
        relay_num = parse_relay_name(sensor_name)
        if relay_num is None:
            return  # Not a relay

        # Check if relay mode is known and if it's binary
        mode_id = coordinator.get_relay_mode(device_key, sensor_name)
        if mode_id is None:
            _LOGGER.debug("Relay %s mode not yet known for binary sensor creation", sensor_name)
            return  # Mode not known yet

        config = get_relay_config(mode_id)
        if not config['is_binary']:
            return  # Not a binary relay, will be handled by sensor platform

        # Create binary relay sensor
        key = f"{device_key}::{address}"
        if key in binary_relay_sensors:
            return  # Already created

        _LOGGER.info("Creating binary relay sensor: %s (mode=%s) at address %s", sensor_name, config['mode_name'], address)
        sensor = RelayBinarySensor(pt, dp_meta, coordinator, initial_value=value)
        binary_relay_sensors[key] = sensor
        async_add_entities([sensor], update_before_add=False)

    # Listen for new device discoveries
    unsub_new = async_dispatcher_connect(hass, SIGNAL_NEW_DEVICE, _on_new_device)
    entry.async_on_unload(unsub_new)

    # Listen for datapoint updates to create binary relay sensors
    unsub_dp = async_dispatcher_connect(hass, SIGNAL_DP_UPDATE, _on_dp_update)
    entry.async_on_unload(unsub_dp)


class MetadataStatusBinarySensor(BinarySensorEntity):
    """Binary sensor indicating metadata fetch status (problem indicator)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = False
    _attr_name = "Metadata Status"

    def __init__(self, pt: ParsedTopic):
        self._pt = pt
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pt.device_key)},
            name=pt.device_name,
            manufacturer=pt.oem_name,
            model=pt.device_id,
        )
        self._attr_unique_id = f"{pt.device_key}::metadata_status".lower()

    @property
    def is_on(self) -> bool:
        """Return True if there's a problem (metadata unavailable)."""
        coordinator = self.hass.data[DOMAIN]["coordinator"]
        # ON = problem exists (metadata failed)
        # OFF = no problem (metadata OK)
        return not coordinator.is_device_metadata_available(self._pt.device_key)

    @property
    def extra_state_attributes(self):
        """Return detailed status information."""
        coordinator = self.hass.data[DOMAIN]["coordinator"]

        # Get parsed topic to extract device_id
        parsed_topics = self.hass.data.get(DOMAIN, {}).get("parsed_topics", {})
        pt = parsed_topics.get(self._pt.device_key)
        if not pt:
            return {"error": "Device not fully registered"}

        # Get detailed status from meta client
        organization_id = pt.oem_id
        device_enum_id = getattr(pt, "device_id", None)
        if not device_enum_id:
            return {"error": "No device ID available"}

        meta_client = coordinator.meta
        details = meta_client.get_status_details(organization_id, device_enum_id)

        # Format timestamp if present
        attrs = {
            "status": details["status"],
            "message": details["message"],
            "retry_count": details["retry_count"],
        }

        if details["last_error_time"]:
            attrs["last_error"] = datetime.fromtimestamp(details["last_error_time"]).isoformat()

        # Add device identification info
        attrs.update({
            "device_key": self._pt.device_key,
            "device_type": self._pt.device_id,
            "oem_name": self._pt.oem_name,
        })

        return attrs


class MqttConnectionStatusBinarySensor(BinarySensorEntity):
    """Binary sensor indicating MQTT broker connection status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_should_poll = False
    _attr_name = "MQTT Connection"
    _attr_icon = "mdi:lan-connect"
    _attr_entity_registry_enabled_default = True  # Enable by default

    def __init__(self, entry: ConfigEntry):
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_mqtt_connection".lower()
        self._is_connected = False
        self._unsub = None

    async def async_added_to_hass(self):
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()

        # Get initial connection state from gateway
        mqtt_gw = self.hass.data.get(DOMAIN, {}).get("mqtt")
        if mqtt_gw:
            self._is_connected = mqtt_gw.is_connected

        # Listen for connection state changes
        @callback
        def _on_connection_state_change(is_connected: bool):
            """Handle MQTT connection state change."""
            self._is_connected = is_connected
            self.async_write_ha_state()

        self._unsub = async_dispatcher_connect(
            self.hass,
            SIGNAL_MQTT_CONNECTION_STATE,
            _on_connection_state_change
        )

        # Write initial state
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return True if connected to MQTT broker."""
        return self._is_connected

    @property
    def extra_state_attributes(self):
        """Return additional connection information."""
        mqtt_gw = self.hass.data.get(DOMAIN, {}).get("mqtt")
        if not mqtt_gw:
            return {"status": "Not initialized"}

        attrs = {
            "broker_host": mqtt_gw._host,
            "broker_port": mqtt_gw._port,
            "tls_enabled": mqtt_gw._tls_enabled,
            "connection_state": "Connected" if self._is_connected else "Disconnected",
        }

        return attrs


class RelayBinarySensor(BinarySensorEntity):
    """Binary sensor for switched/binary relays (on/off control)."""

    _attr_should_poll = False

    def __init__(self, pt: ParsedTopic, dp: dict, coordinator, initial_value):
        """Initialize the relay binary sensor."""
        self._pt = pt
        self._dp = dp
        self._coordinator = coordinator
        self._value = initial_value
        self._unsub = None

        # Set up entity attributes
        self._attr_name = dp.get("name", "Unknown")
        self._attr_unique_id = f"{pt.device_key}::{dp.get('address', 0)}".lower()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pt.device_key)},
            name=pt.device_name,
            manufacturer=pt.oem_name,
            model=pt.device_id,
        )

        # Get relay mode info
        mode_id = coordinator.get_relay_mode(pt.device_key, self._attr_name)
        if mode_id is not None:
            config = get_relay_config(mode_id)
            self._relay_mode_name = config['mode_name']
        else:
            self._relay_mode_name = None

        # Binary sensors for relays could be switches or outlets
        self._attr_device_class = BinarySensorDeviceClass.POWER
        self._attr_icon = "mdi:electric-switch"

    async def async_added_to_hass(self):
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()

        @callback
        def _handle_dp_update(device_key: str, address: int, value):
            """Handle datapoint update signal."""
            if device_key == self._pt.device_key and address == int(self._dp.get("address", -1)):
                self._value = value
                self.async_write_ha_state()

        self._unsub = async_dispatcher_connect(self.hass, SIGNAL_DP_UPDATE, _handle_dp_update)
        # Write initial state (already has value)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return True if relay is on."""
        # Binary relays use string values "on"/"off" after decoding
        if isinstance(self._value, str):
            return self._value.lower() == "on"
        # Fallback: treat non-zero as on
        if isinstance(self._value, (int, float)):
            return self._value != 0
        return False

    @property
    def available(self) -> bool:
        """Return True if relay is available."""
        # Negative values indicate errors
        if isinstance(self._value, (int, float)):
            return self._value >= 0
        return self._value is not None

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        attrs = dict(self._dp)

        # Add relay mode info
        if self._relay_mode_name:
            attrs['relay_mode'] = self._relay_mode_name

        # Add error info for negative values
        if isinstance(self._value, (int, float)) and self._value < 0:
            attrs['error'] = 'Not connected'

        # Add raw value for debugging
        attrs['raw_value'] = self._value

        return attrs
