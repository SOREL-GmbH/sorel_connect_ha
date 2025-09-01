from __future__ import annotations
import logging
from dataclasses import dataclass
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, SIGNAL_NEW_DEVICE
from .topic_parser import ParsedTopic

_LOGGER = logging.getLogger(__name__)

PLATFORM = "sensor"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    @callback
    def _on_new_device(pt: ParsedTopic):
        # Pro Gerät fügen wir ein paar Diagnose-Sensoren hinzu
        entities = [
            DeviceTypeSensor(pt),
            OemIdSensor(pt),
            NetworkIdSensor(pt),
        ]
        async_add_entities(entities, update_before_add=False)

    unsub = async_dispatcher_connect(hass, SIGNAL_NEW_DEVICE, _on_new_device)
    entry.async_on_unload(unsub)

class BaseDeviceDiagSensor(SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, pt: ParsedTopic):
        self._pt = pt
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pt.device_key)},  # stabil: (mac, network)
            name=pt.device_name,
            manufacturer=pt.oem_name,
            model=pt.device_id,  # menschenlesbar mappst du später via Metadaten
        )
        # Unique-ID pro Entity
        self._attr_unique_id = f"{pt.device_key}::{self.__class__.__name__}".lower()

    @property
    def extra_state_attributes(self):
        # Damit hast du die Metadaten auf einen Blick
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
    # State = 4-stelliges hex device_id
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
