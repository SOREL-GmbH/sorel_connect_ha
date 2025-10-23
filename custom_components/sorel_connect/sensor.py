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
    async def _on_new_device(pt: ParsedTopic):
        coordinator = hass.data[DOMAIN]["coordinator"]

        # Get metadata from coordinator (already fetched during discovery)
        datapoints = coordinator._datapoints.get(pt.device_key, [])

        # Store references for later datapoint sensor creation
        hass.data[DOMAIN]["meta_datapoints"][pt.device_key] = datapoints
        hass.data[DOMAIN]["parsed_topics"][pt.device_key] = pt

        # Only create base diagnostic sensors immediately
        entities = [
            DeviceTypeSensor(pt),
            OemIdSensor(pt),
            NetworkIdSensor(pt),
        ]
        async_add_entities(entities, update_before_add=False)

    # Dispatcher for new devices
    unsub_new = async_dispatcher_connect(hass, SIGNAL_NEW_DEVICE, _on_new_device)
    entry.async_on_unload(unsub_new)

    # One-time dispatcher for DP updates -> creates sensor on first value
    @callback
    def _on_dp_first_value(device_key, address, value):
        if value is None:
            return  # Ignore until real value arrives
        key = f"{device_key}:{address}"
        dp_sensors = hass.data[DOMAIN]["dp_sensors"]
        if key in dp_sensors:
            return  # Sensor already exists, its own handler will take care of it
        pt = hass.data[DOMAIN]["parsed_topics"].get(device_key)
        if not pt:
            return  # Device not fully registered yet

        # Find metadata for this datapoint
        dps_meta = hass.data[DOMAIN]["meta_datapoints"].get(device_key, [])
        dp_meta = next((d for d in dps_meta if int(d.get("address")) == address), None)
        if dp_meta is None:
            dp_meta = {"address": address, "name": f"Datapoint {address}"}

        sensor = DatapointSensor(pt, dp_meta, initial_value=value)
        dp_sensors[key] = sensor
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

class DatapointSensor(SensorEntity):
    _attr_should_poll = False
    _attr_entity_registry_enabled_default = True

    def __init__(self, pt: ParsedTopic, dp: dict, initial_value=None):
        self._pt = pt
        self._dp = dp
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
        return self._value

    @property
    def extra_state_attributes(self):
        return self._dp