#!/usr/bin/env python3
"""Test script for sensor type logic."""

import sys
sys.path.insert(0, '../custom_components/sorel_connect')

from sensor_types import (
    load_sensor_types,
    parse_sensor_name,
    is_sensor_type_register,
    get_sensor_config,
    get_type_register_address,
)

def test_load_sensor_types():
    """Test loading sensor types from CSV."""
    print("\n=== Testing CSV Loading ===")
    types = load_sensor_types()
    print(f"Loaded {len(types)} sensor types")

    # Test a few known types
    if 2 in types:
        print(f"Type 2 (Temperature): {types[2]}")
    if 3 in types:
        print(f"Type 3 (Humidity): {types[3]}")
    if 23 in types:
        print(f"Type 23 (Flow): {types[23]}")

def test_parse_sensor_name():
    """Test parsing sensor names."""
    print("\n=== Testing Sensor Name Parsing ===")
    test_cases = [
        ("S1", 1),
        ("S2", 2),
        ("S15", 15),
        ("Temperature", None),
        ("S1 Type", None),  # This should not parse as a sensor number
    ]

    for name, expected in test_cases:
        result = parse_sensor_name(name)
        status = "✓" if result == expected else "✗"
        print(f"{status} parse_sensor_name('{name}') = {result} (expected {expected})")

def test_is_sensor_type_register():
    """Test detecting sensor type registers."""
    print("\n=== Testing Sensor Type Register Detection ===")
    test_cases = [
        ("S1 Type", "S1"),
        ("S2 Type", "S2"),
        ("S15 Type", "S15"),
        ("S1", None),
        ("Temperature", None),
    ]

    for name, expected in test_cases:
        result = is_sensor_type_register(name)
        status = "✓" if result == expected else "✗"
        print(f"{status} is_sensor_type_register('{name}') = {result} (expected {expected})")

def test_get_sensor_config():
    """Test getting sensor configuration."""
    print("\n=== Testing Sensor Configuration ===")

    # Test temperature sensor with °C
    print("\nTemperature sensor (type_id=2, temp_unit=0 for °C):")
    config = get_sensor_config(2, 0)
    print(f"  Type: {config['type_name']}")
    print(f"  Unit: {config['unit']}")
    print(f"  Mapped Unit: {config['mapped_unit']}")
    print(f"  Device Class: {config['device_class']}")

    # Test temperature sensor with °F
    print("\nTemperature sensor (type_id=2, temp_unit=1 for °F):")
    config = get_sensor_config(2, 1)
    print(f"  Type: {config['type_name']}")
    print(f"  Unit: {config['unit']}")
    print(f"  Mapped Unit: {config['mapped_unit']}")
    print(f"  Device Class: {config['device_class']}")

    # Test humidity sensor
    print("\nHumidity sensor (type_id=3):")
    config = get_sensor_config(3, 0)
    print(f"  Type: {config['type_name']}")
    print(f"  Unit: {config['unit']}")
    print(f"  Mapped Unit: {config['mapped_unit']}")
    print(f"  Device Class: {config['device_class']}")

    # Test flow sensor
    print("\nFlow sensor (type_id=23):")
    config = get_sensor_config(23, 0)
    print(f"  Type: {config['type_name']}")
    print(f"  Unit: {config['unit']}")
    print(f"  Mapped Unit: {config['mapped_unit']}")
    print(f"  Device Class: {config['device_class']}")

    # Test unknown type
    print("\nUnknown sensor (type_id=999):")
    config = get_sensor_config(999, 0)
    print(f"  Type: {config['type_name']}")
    print(f"  Unit: {config['unit']}")

def test_get_type_register_address():
    """Test calculating type register addresses."""
    print("\n=== Testing Type Register Address Calculation ===")
    test_cases = [
        (43001, 43002),  # S1 -> S1 Type
        (43003, 43004),  # S2 -> S2 Type
        (521, 522),
    ]

    for sensor_addr, expected in test_cases:
        result = get_type_register_address(sensor_addr)
        status = "✓" if result == expected else "✗"
        print(f"{status} get_type_register_address({sensor_addr}) = {result} (expected {expected})")

if __name__ == "__main__":
    print("=" * 60)
    print("Sensor Type Logic Test Suite")
    print("=" * 60)

    try:
        test_load_sensor_types()
        test_parse_sensor_name()
        test_is_sensor_type_register()
        test_get_sensor_config()
        test_get_type_register_address()

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
