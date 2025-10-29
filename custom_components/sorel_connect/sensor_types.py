"""Sensor type management for Sorel Connect integration."""
from __future__ import annotations
import logging
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

from .const import SENSOR_TYPES, RELAY_MODES

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

# Cache for loaded relay modes
_relay_modes_cache: Optional[Dict[int, str]] = None


def load_sensor_types() -> Dict[int, dict]:
    """
    Load sensor types from const.py.

    Returns:
        Dictionary mapping type_id -> {type_name, base_unit, device_class, temp_dependent}
    """
    global _sensor_types_cache

    if _sensor_types_cache is not None:
        _LOGGER.debug(f"Returning cached sensor types ({len(_sensor_types_cache)} types)")
        return _sensor_types_cache

    _LOGGER.info(f"Loading sensor types from const.py")

    # Use sensor types from const.py
    _sensor_types_cache = SENSOR_TYPES.copy()

    _LOGGER.info(f"Successfully loaded {len(_sensor_types_cache)} sensor types from const.py")

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


def parse_relay_name(name: str) -> Optional[int]:
    """
    Parse relay name to extract relay number.

    Args:
        name: Relay name like "R1", "R2", "R15"

    Returns:
        Relay number (1, 2, 15, etc.) or None if not a relay

    Examples:
        >>> parse_relay_name("R1")
        1
        >>> parse_relay_name("R15")
        15
        >>> parse_relay_name("Temperature")
        None
    """
    if not name or not isinstance(name, str):
        return None

    name = name.strip()
    if name.startswith("R") and len(name) > 1:
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


# ============================================================================
# Relay Mode Functions
# ============================================================================

def load_relay_modes() -> Dict[int, str]:
    """
    Load relay modes from const.py.

    Returns:
        Dictionary mapping mode_id -> mode_name
    """
    global _relay_modes_cache

    if _relay_modes_cache is not None:
        _LOGGER.debug(f"Returning cached relay modes ({len(_relay_modes_cache)} modes)")
        return _relay_modes_cache

    _LOGGER.info(f"Loading relay modes from const.py")

    # Use relay modes from const.py
    _relay_modes_cache = RELAY_MODES.copy()

    _LOGGER.info(f"Successfully loaded {len(_relay_modes_cache)} relay modes from const.py")

    return _relay_modes_cache


def is_relay_mode_register(dp_name: str) -> Optional[str]:
    """
    Check if datapoint represents a relay mode register.

    Args:
        dp_name: Datapoint name like "R1 Mode", "R2 Mode"

    Returns:
        Base relay name ("R1", "R2") or None if not a mode register

    Examples:
        >>> is_relay_mode_register("R1 Mode")
        "R1"
        >>> is_relay_mode_register("R15 Mode")
        "R15"
        >>> is_relay_mode_register("R1")
        None
    """
    if not dp_name or not isinstance(dp_name, str):
        return None

    dp_name = dp_name.strip()
    if dp_name.endswith(" Mode") and dp_name.startswith("R"):
        relay_name = dp_name[:-5]  # Remove " Mode"
        if parse_relay_name(relay_name) is not None:
            return relay_name

    return None


def get_relay_mode_name(mode_id: int) -> str:
    """
    Get relay mode name from mode_id.

    Args:
        mode_id: Relay mode ID (0-5)

    Returns:
        Relay mode name or "Unknown Mode X" if not found

    Examples:
        >>> get_relay_mode_name(0)
        "relay"
        >>> get_relay_mode_name(2)
        "PWM"
        >>> get_relay_mode_name(999)
        "Unknown Mode 999"
    """
    relay_modes = load_relay_modes()
    return relay_modes.get(mode_id, f"Unknown Mode {mode_id}")
