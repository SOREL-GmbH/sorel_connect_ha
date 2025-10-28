from __future__ import annotations
import logging
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfTemperature, UnitOfPower, UnitOfEnergy, UnitOfElectricPotential, UnitOfElectricCurrent, UnitOfFrequency, UnitOfPressure, UnitOfVolume
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, SIGNAL_NEW_DEVICE, SIGNAL_DP_UPDATE
from .topic_parser import ParsedTopic
from .sensor_types import (
    parse_sensor_name,
    get_sensor_config,
    is_sensor_type_register,
    parse_relay_name,
    is_relay_mode_register,
    get_relay_mode_name,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM = "sensor"

# Optional mapping from raw strings to HA standard units
UNIT_MAP = {
    "°C": UnitOfTemperature.CELSIUS,
    "C": UnitOfTemperature.CELSIUS,
    "K": UnitOfTemperature.KELVIN,
    "°F": UnitOfTemperature.FAHRENHEIT,
    "%": PERCENTAGE,
    "W": UnitOfPower.WATT,
    "kW": UnitOfPower.KILO_WATT,
    "Wh": UnitOfEnergy.WATT_HOUR,
    "kWh": UnitOfEnergy.KILO_WATT_HOUR,
    "V": UnitOfElectricPotential.VOLT,
    "A": UnitOfElectricCurrent.AMPERE,
    "Hz": UnitOfFrequency.HERTZ,
    "bar": UnitOfPressure.BAR,
    "m³": UnitOfVolume.CUBIC_METERS,
    "l": UnitOfVolume.LITERS,
    "L": UnitOfVolume.LITERS,
}

# Mapping for device_class based on (already mapped) unit
DEVICE_CLASS_BY_UNIT = {
    UnitOfTemperature.CELSIUS: SensorDeviceClass.TEMPERATURE,
    UnitOfTemperature.FAHRENHEIT: SensorDeviceClass.TEMPERATURE,
    UnitOfTemperature.KELVIN: SensorDeviceClass.TEMPERATURE,
    UnitOfPower.WATT: SensorDeviceClass.POWER,
    UnitOfPower.KILO_WATT: SensorDeviceClass.POWER,
    UnitOfEnergy.WATT_HOUR: SensorDeviceClass.ENERGY,
    UnitOfEnergy.KILO_WATT_HOUR: SensorDeviceClass.ENERGY,
    UnitOfElectricPotential.VOLT: SensorDeviceClass.VOLTAGE,
    UnitOfElectricCurrent.AMPERE: SensorDeviceClass.CURRENT,
    UnitOfFrequency.HERTZ: SensorDeviceClass.FREQUENCY,
    UnitOfPressure.BAR: SensorDeviceClass.PRESSURE,
    UnitOfVolume.LITERS: SensorDeviceClass.VOLUME,
    UnitOfVolume.CUBIC_METERS: SensorDeviceClass.VOLUME,
}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("meta_datapoints", {})
    # Store ParsedTopic instances and already created datapoint sensors
    hass.data[DOMAIN].setdefault("parsed_topics", {})
    hass.data[DOMAIN].setdefault("dp_sensors", {})  # key: f"{device_key}:{address}" -> Entity

    @callback
    def _on_new_device(pt: ParsedTopic):
        _LOGGER.debug("Received SIGNAL_NEW_DEVICE: device_key=%s, device_name=%s, device_id=%s",
                     pt.device_key, pt.device_name, pt.device_id)
        coordinator = hass.data[DOMAIN]["coordinator"]

        # Get metadata from coordinator (already fetched during discovery)
        datapoints = coordinator._datapoints.get(pt.device_key, [])
        _LOGGER.debug("Device %s has %d datapoints in metadata", pt.device_key, len(datapoints))

        # Store references for later datapoint sensor creation
        hass.data[DOMAIN]["meta_datapoints"][pt.device_key] = datapoints
        hass.data[DOMAIN]["parsed_topics"][pt.device_key] = pt

        # Only create base diagnostic sensors immediately
        entities = [
            DeviceTypeSensor(pt),
            OemIdSensor(pt),
            NetworkIdSensor(pt),
        ]
        _LOGGER.info("Creating %d diagnostic sensors for device %s (%s)", len(entities), pt.device_key, pt.device_name)
        async_add_entities(entities, update_before_add=False)

    # Dispatcher for new devices
    unsub_new = async_dispatcher_connect(hass, SIGNAL_NEW_DEVICE, _on_new_device)
    entry.async_on_unload(unsub_new)

    # One-time dispatcher for DP updates -> creates sensor on first value
    @callback
    def _on_dp_first_value(device_key, address, value):
        _LOGGER.debug("Received SIGNAL_DP_UPDATE: device=%s, address=%s, value=%s", device_key, address, value)
        if value is None:
            _LOGGER.debug("Ignoring DP update with None value for device=%s, address=%s", device_key, address)
            return  # Ignore until real value arrives
        key = f"{device_key}:{address}"
        dp_sensors = hass.data[DOMAIN]["dp_sensors"]
        if key in dp_sensors:
            _LOGGER.debug("Sensor already exists for %s, skipping creation", key)
            return  # Sensor already exists, its own handler will take care of it
        pt = hass.data[DOMAIN]["parsed_topics"].get(device_key)
        if not pt:
            _LOGGER.warning("Device %s not fully registered yet, cannot create sensor for address %s", device_key, address)
            return  # Device not fully registered yet

        # Find metadata for this datapoint
        dps_meta = hass.data[DOMAIN]["meta_datapoints"].get(device_key, [])
        dp_meta = next((d for d in dps_meta if int(d.get("address")) == address), None)
        if dp_meta is None:
            _LOGGER.debug("No metadata found for address %s, skipping sensor creation", address)
            return  # Skip if no metadata

        sensor_name = dp_meta.get("name", "")
        _LOGGER.debug("Found metadata for address %s: %s", address, sensor_name)

        coordinator = hass.data[DOMAIN]["coordinator"]

        # Check if this is a relay mode register (R1 Mode, R2 Mode, etc.)
        relay_name = is_relay_mode_register(sensor_name)
        if relay_name:
            # This is a Mode register - create diagnostic sensor
            _LOGGER.info("Creating diagnostic sensor for Relay Mode: %s (address=%s)", sensor_name, address)
            sensor = RelayModeDiagnosticSensor(pt, dp_meta, coordinator, initial_value=value)
            dp_sensors[key] = sensor
            async_add_entities([sensor], update_before_add=False)
            return

        # Check if this is a sensor type register (S1 Type, S2 Type, etc.)
        base_sensor_name = is_sensor_type_register(sensor_name)
        if base_sensor_name:
            # This is a Type register - create diagnostic sensor
            _LOGGER.info("Creating diagnostic sensor for Type register: %s (address=%s)", sensor_name, address)
            sensor = SensorTypeDiagnosticSensor(pt, dp_meta, coordinator, initial_value=value)
            dp_sensors[key] = sensor
            async_add_entities([sensor], update_before_add=False)
            return

        # Check if this is a sensor input (S1, S2, etc.)
        sensor_num = parse_sensor_name(sensor_name)
        if sensor_num is not None:
            # This is a sensor input - check if we know its type yet
            type_id = coordinator.get_sensor_type(device_key, sensor_name)

            if type_id is None:
                _LOGGER.debug("Sensor %s type not yet known for device %s, skipping creation until next update",
                             sensor_name, device_key)
                return  # Skip creation, will retry on next value arrival

            _LOGGER.info("Sensor %s has type_id=%s, creating sensor with proper configuration",
                        sensor_name, type_id)

        sensor = DatapointSensor(pt, dp_meta, coordinator, initial_value=value)
        dp_sensors[key] = sensor
        _LOGGER.info("Creating datapoint sensor for device=%s, address=%s, name='%s'", device_key, address, sensor_name)
        async_add_entities([sensor], update_before_add=False)

    unsub_dp = async_dispatcher_connect(hass, SIGNAL_DP_UPDATE, _on_dp_first_value)
    entry.async_on_unload(unsub_dp)

class BaseDeviceDiagSensor(SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, pt: ParsedTopic):
        self._pt = pt
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pt.device_key)},
            name=pt.device_name,
            manufacturer=pt.oem_name,
            model=pt.device_id,
        )
        self._attr_unique_id = f"{pt.device_key}::{self.__class__.__name__}".lower()

    @property
    def extra_state_attributes(self):
        return {
            "oem_name": self._pt.oem_name,
            "oem_id": self._pt.oem_id,
            "mac": self._pt.mac,
            "tag": self._pt.tag,
            "network_id": self._pt.network_id,
            "device_name": self._pt.device_name,
            "device_id": self._pt.device_id,
            "unit_id": self._pt.unit_id,
        }

class DeviceTypeSensor(BaseDeviceDiagSensor):
    _attr_name = "Device Type"
    _attr_icon = "mdi:identifier"
    @property
    def native_value(self):
        return self._pt.device_id

class OemIdSensor(BaseDeviceDiagSensor):
    _attr_name = "OEM ID"
    _attr_icon = "mdi:factory"
    @property
    def native_value(self):
        return self._pt.oem_id

class NetworkIdSensor(BaseDeviceDiagSensor):
    _attr_name = "Network ID"
    _attr_icon = "mdi:lan"
    @property
    def native_value(self):
        return self._pt.network_id

class SensorTypeDiagnosticSensor(SensorEntity):
    """Diagnostic sensor for S<n> Type registers that shows sensor type name."""
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = True

    def __init__(self, pt: ParsedTopic, dp: dict, coordinator, initial_value=None):
        self._pt = pt
        self._dp = dp
        self._coordinator = coordinator
        self._address = int(dp.get("address"))
        self._attr_name = dp.get("name", f"Datapoint {self._address}")
        self._attr_unique_id = f"{pt.device_key}::dp_{self._address}".lower()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pt.device_key)},
            name=pt.device_name,
            manufacturer=pt.oem_name,
            model=pt.device_id,
        )
        self._attr_icon = "mdi:form-select"
        self._value = initial_value
        self._unsub = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        @callback
        def _handle_dp_update(device_key, address, value):
            if device_key == self._pt.device_key and address == self._address:
                self._value = value
                self.async_write_ha_state()

        self._unsub = async_dispatcher_connect(self.hass, SIGNAL_DP_UPDATE, _handle_dp_update)
        # Write initial state
        self.async_write_ha_state()

    @property
    def native_value(self):
        """Format type_id as type name."""
        if isinstance(self._value, (int, float)):
            type_id = int(self._value)
            temp_unit = self._coordinator.get_temp_unit(self._pt.device_key)
            config = get_sensor_config(type_id, temp_unit)
            return config['type_name']
        return str(self._value) if self._value is not None else None

    @property
    def extra_state_attributes(self):
        attrs = dict(self._dp)
        # Add raw type_id value
        if isinstance(self._value, (int, float)):
            attrs['type_id'] = int(self._value)
        return attrs

class RelayModeDiagnosticSensor(SensorEntity):
    """Diagnostic sensor for R<n> Mode registers that shows relay mode name."""
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = True

    def __init__(self, pt: ParsedTopic, dp: dict, coordinator, initial_value=None):
        self._pt = pt
        self._dp = dp
        self._coordinator = coordinator
        self._address = int(dp.get("address"))
        self._attr_name = dp.get("name", f"Datapoint {self._address}")
        self._attr_unique_id = f"{pt.device_key}::dp_{self._address}".lower()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pt.device_key)},
            name=pt.device_name,
            manufacturer=pt.oem_name,
            model=pt.device_id,
        )
        self._attr_icon = "mdi:electric-switch-closed"
        self._value = initial_value
        self._unsub = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        @callback
        def _handle_dp_update(device_key, address, value):
            if device_key == self._pt.device_key and address == self._address:
                self._value = value
                self.async_write_ha_state()

        self._unsub = async_dispatcher_connect(self.hass, SIGNAL_DP_UPDATE, _handle_dp_update)
        self.async_write_ha_state()

    @property
    def native_value(self):
        """Format mode_id as mode name."""
        if isinstance(self._value, (int, float)):
            mode_id = int(self._value)
            return get_relay_mode_name(mode_id)
        return str(self._value) if self._value is not None else None

    @property
    def extra_state_attributes(self):
        attrs = dict(self._dp)
        # Add raw mode_id value
        if isinstance(self._value, (int, float)):
            attrs['mode_id'] = int(self._value)
        return attrs

class DatapointSensor(SensorEntity):
    _attr_should_poll = False
    _attr_entity_registry_enabled_default = True

    def __init__(self, pt: ParsedTopic, dp: dict, coordinator, initial_value=None):
        self._pt = pt
        self._dp = dp
        self._coordinator = coordinator
        self._address = int(dp.get("address"))
        self._attr_name = dp.get("name", f"Datapoint {self._address}")
        self._attr_unique_id = f"{pt.device_key}::dp_{self._address}".lower()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pt.device_key)},
            name=pt.device_name,
            manufacturer=pt.oem_name,
            model=pt.device_id,
        )
        self._attr_icon = "mdi:chart-line"
        self._sensor_type_name = None  # Will be set for S<n> sensors
        self._is_relay = False  # Will be set for R<n> relays

        # Check if this is a relay (R1, R2, etc.)
        relay_num = parse_relay_name(self._attr_name)
        if relay_num is not None:
            # This is a relay - configure for percentage display
            self._is_relay = True
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_icon = "mdi:electric-switch"
            # No device_class for relays (generic percentage)
            # No state_class needed for relays
            _LOGGER.debug("Configured relay sensor %s for percentage display", self._attr_name)

        # Check if this is a sensor input (S1, S2, etc.)
        sensor_num = parse_sensor_name(self._attr_name)
        sensor_type_applied = False

        if sensor_num is not None and not self._is_relay:  # Don't apply sensor logic to relays
            # This is a sensor input - get type configuration
            try:
                type_id = coordinator.get_sensor_type(pt.device_key, self._attr_name)
                temp_unit = coordinator.get_temp_unit(pt.device_key)

                if type_id is not None:
                    config = get_sensor_config(type_id, temp_unit)
                    self._sensor_type_name = config['type_name']

                    # Override unit and device class from sensor type
                    if config['mapped_unit']:
                        self._attr_native_unit_of_measurement = config['mapped_unit']
                    if config['device_class']:
                        self._attr_device_class = config['device_class']
                        self._attr_state_class = SensorStateClass.MEASUREMENT

                    sensor_type_applied = True
                    _LOGGER.debug("Applied sensor type config for %s: type=%s, unit=%s, device_class=%s",
                                 self._attr_name, config['type_name'], config['unit'], config['device_class'])
            except Exception as e:
                _LOGGER.warning(f"Error applying sensor type configuration for '{self._attr_name}': {e}")

        # Fallback to metadata unit if sensor type wasn't applied
        if not sensor_type_applied:
            try:
                raw_unit = dp.get("unit")
                if raw_unit:
                    unit = UNIT_MAP.get(raw_unit, raw_unit)
                    self._attr_native_unit_of_measurement = unit

                    # Determine device_class
                    device_class = DEVICE_CLASS_BY_UNIT.get(unit)
                    if device_class:
                        self._attr_device_class = device_class

                        # state_class logic:
                        if device_class == SensorDeviceClass.ENERGY:
                            # Counter increases (if applicable) -> TOTAL_INCREASING
                            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
                        else:
                            # Normal measurement value
                            self._attr_state_class = SensorStateClass.MEASUREMENT
                    else:
                        # Fallback for numeric values without known unit
                        self._attr_state_class = SensorStateClass.MEASUREMENT
                else:
                    # No unit -> no long-term statistics
                    pass
            except Exception as e:
                _LOGGER.warning(f"Error processing unit '{raw_unit}' for DP '{self._attr_name}': {e}")

        self._value = initial_value
        self._unsub = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        @callback
        def _handle_dp_update(device_key, address, value):
            if device_key == self._pt.device_key and address == self._address:
                self._value = value
                self.async_write_ha_state()

        self._unsub = async_dispatcher_connect(self.hass, SIGNAL_DP_UPDATE, _handle_dp_update)
        # Write initial state (already has value)
        self.async_write_ha_state()

    @property
    def native_value(self):
        # Handle relay values first (R1, R2, etc.)
        if self._is_relay:
            if isinstance(self._value, (int, float)):
                if self._value < 0:
                    return None  # Negative value = error → unavailable
                # Scale to percentage: divide by 10 (0-1000 → 0-100%)
                return self._value / 10
            return self._value

        # Handle sensor error codes (S1, S2, etc.)
        if isinstance(self._value, (int, float)):
            if self._value == -32767:
                return None  # Sensor not connected → unavailable
            if self._value == -32768:
                return None  # Sensor error → unavailable
        return self._value

    @property
    def available(self) -> bool:
        """Mark sensor unavailable if error value received."""
        # Check relay error (negative values)
        if self._is_relay:
            if isinstance(self._value, (int, float)):
                return self._value >= 0  # Negative = not available
            return self._value is not None

        # Check sensor error codes
        if isinstance(self._value, (int, float)):
            return self._value not in (-32767, -32768)
        return self._value is not None

    @property
    def extra_state_attributes(self):
        attrs = dict(self._dp)

        # Add relay error info
        if self._is_relay:
            if isinstance(self._value, (int, float)) and self._value < 0:
                attrs['error'] = 'Not connected'

        # Add sensor type if applicable
        if self._sensor_type_name:
            attrs['sensor_type'] = self._sensor_type_name

        # Add sensor error state info
        if not self._is_relay and isinstance(self._value, (int, float)):
            if self._value == -32767:
                attrs['error'] = 'Not connected'
            elif self._value == -32768:
                attrs['error'] = 'Sensor error'

        return attrs