"""Sensor type management for Sorel Connect integration."""
from __future__ import annotations
import csv
import logging
import os
from typing import Dict, Optional
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfPower,
    UnitOfFrequency,
    UnitOfPressure,
    UnitOfVolume,
    UnitOfIrradiance,
)
from homeassistant.components.sensor import SensorDeviceClass

_LOGGER = logging.getLogger(__name__)

# Extended unit map for sensor types
SENSOR_TYPE_UNIT_MAP = {
    "°C": UnitOfTemperature.CELSIUS,
    "°F": UnitOfTemperature.FAHRENHEIT,
    "%": PERCENTAGE,
    "W": UnitOfPower.WATT,
    "Hz": UnitOfFrequency.HERTZ,
    "bar": UnitOfPressure.BAR,
    "hPa": UnitOfPressure.HPA,
    "L/min": "L/min",  # No standard HA unit for this
    "L": UnitOfVolume.LITERS,
    "lux": "lx",  # Light level
    "W/m²": UnitOfIrradiance.WATTS_PER_SQUARE_METER,
    "ppm": "ppm",  # Parts per million (CO2)
}

# Device class map
DEVICE_CLASS_MAP = {
    "temperature": SensorDeviceClass.TEMPERATURE,
    "humidity": SensorDeviceClass.HUMIDITY,
    "illuminance": SensorDeviceClass.ILLUMINANCE,
    "irradiance": SensorDeviceClass.IRRADIANCE,
    "power": SensorDeviceClass.POWER,
    "frequency": SensorDeviceClass.FREQUENCY,
    "pressure": SensorDeviceClass.PRESSURE,
}

# Cache for loaded sensor types
_sensor_types_cache: Optional[Dict[int, dict]] = None


def load_sensor_types() -> Dict[int, dict]:
    """
    Load sensor types from CSV file.

    Returns:
        Dictionary mapping type_id -> {type_name, base_unit, device_class, temp_dependent}
    """
    global _sensor_types_cache

    if _sensor_types_cache is not None:
        _LOGGER.debug(f"Returning cached sensor types ({len(_sensor_types_cache)} types)")
        return _sensor_types_cache

    # Locate CSV file relative to this module
    module_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(module_dir, "sensor_types.csv")

    _LOGGER.info(f"Loading sensor types from: {csv_path}")
    _LOGGER.debug(f"Module directory: {module_dir}")

    if not os.path.exists(csv_path):
        _LOGGER.error(f"Sensor types CSV not found at {csv_path}")
        _LOGGER.error(f"Directory contents: {os.listdir(module_dir) if os.path.exists(module_dir) else 'N/A'}")
        _sensor_types_cache = {}
        return _sensor_types_cache

    sensor_types = {}

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            row_count = 0
            for row in reader:
                row_count += 1
                try:
                    # Defensive parsing: handle None/empty values
                    type_id = int(row.get("type_id", 0))
                    type_name = (row.get("type_name") or "").strip()
                    base_unit = (row.get("base_unit") or "").strip() or None
                    device_class = (row.get("device_class") or "").strip() or None
                    temp_dependent = (row.get("temp_dependent") or "").strip().lower() == "true"

                    if not type_name:
                        _LOGGER.warning(f"Skipping CSV row {row_count}: missing type_name")
                        continue

                    sensor_types[type_id] = {
                        "type_name": type_name,
                        "base_unit": base_unit,
                        "device_class": device_class,
                        "temp_dependent": temp_dependent,
                    }
                    _LOGGER.debug(f"Loaded type {type_id}: {type_name}")
                except (ValueError, KeyError, AttributeError) as e:
                    _LOGGER.warning(f"Skipping invalid CSV row {row_count}: {row}, error: {e}")
                    continue

        _LOGGER.info(f"Successfully loaded {len(sensor_types)} sensor types from CSV (processed {row_count} rows)")
        _sensor_types_cache = sensor_types

    except Exception as e:
        _LOGGER.error(f"Failed to load sensor types CSV from {csv_path}: {e}", exc_info=True)
        _sensor_types_cache = {}

    return _sensor_types_cache


def parse_sensor_name(name: str) -> Optional[int]:
    """
    Parse sensor name to extract sensor number.

    Args:
        name: Sensor name like "S1", "S2", "S15"

    Returns:
        Sensor number (1, 2, 15, etc.) or None if not a sensor

    Examples:
        >>> parse_sensor_name("S1")
        1
        >>> parse_sensor_name("S15")
        15
        >>> parse_sensor_name("Temperature")
        None
    """
    if not name or not isinstance(name, str):
        return None

    name = name.strip()
    if name.startswith("S") and len(name) > 1:
        number_part = name[1:]
        if number_part.isdigit():
            return int(number_part)

    return None


def is_sensor_type_register(dp_name: str) -> Optional[str]:
    """
    Check if datapoint name represents a sensor type register.

    Args:
        dp_name: Datapoint name like "S1 Type", "S2 Type"

    Returns:
        Base sensor name ("S1", "S2") or None if not a type register

    Examples:
        >>> is_sensor_type_register("S1 Type")
        "S1"
        >>> is_sensor_type_register("S15 Type")
        "S15"
        >>> is_sensor_type_register("S1")
        None
    """
    if not dp_name or not isinstance(dp_name, str):
        return None

    dp_name = dp_name.strip()
    if dp_name.endswith(" Type") and dp_name.startswith("S"):
        sensor_name = dp_name[:-5]  # Remove " Type"
        if parse_sensor_name(sensor_name) is not None:
            return sensor_name

    return None


def get_sensor_config(type_id: int, temp_unit: int = 0) -> dict:
    """
    Get sensor configuration based on type ID and temperature unit setting.

    Args:
        type_id: Sensor type ID from device
        temp_unit: Temperature unit setting (0=°C, 1=°F)

    Returns:
        Dictionary with:
            - type_name: Sensor type name
            - unit: Raw unit string
            - mapped_unit: HA unit constant
            - device_class: HA device class
            - temp_dependent: Whether unit depends on temp setting
    """
    sensor_types = load_sensor_types()

    if type_id not in sensor_types:
        _LOGGER.warning(f"Unknown sensor type ID: {type_id}, using generic sensor")
        return {
            "type_name": f"Unknown Type {type_id}",
            "unit": None,
            "mapped_unit": None,
            "device_class": None,
            "temp_dependent": False,
        }

    type_info = sensor_types[type_id]
    base_unit = type_info["base_unit"]

    # Handle temperature-dependent units
    if type_info["temp_dependent"] and base_unit == "°C":
        if temp_unit == 1:
            unit = "°F"
        else:
            unit = "°C"
    else:
        unit = base_unit

    # Map to HA constants
    mapped_unit = SENSOR_TYPE_UNIT_MAP.get(unit, unit) if unit else None
    device_class = DEVICE_CLASS_MAP.get(type_info["device_class"]) if type_info["device_class"] else None

    return {
        "type_name": type_info["type_name"],
        "unit": unit,
        "mapped_unit": mapped_unit,
        "device_class": device_class,
        "temp_dependent": type_info["temp_dependent"],
    }


def get_type_register_address(sensor_address: int) -> int:
    """
    Calculate the type register address for a sensor.

    According to device protocol, the type register is always the next
    register after the sensor value register.

    Args:
        sensor_address: Address of sensor value register (e.g., 43001 for S1)

    Returns:
        Address of type register (e.g., 43002 for S1 Type)

    Examples:
        >>> get_type_register_address(43001)
        43002
    """
    return sensor_address + 1
