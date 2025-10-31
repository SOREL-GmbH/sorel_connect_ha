#!/usr/bin/env python3
"""Quick test to verify sensor_types refactoring works correctly."""

import sys
sys.path.insert(0, '../custom_components/sorel_connect')

from sensor_types import load_sensor_types, load_relay_modes, get_sensor_config, get_relay_mode_name

def test_sensor_types():
    """Test sensor types loading."""
    print("Testing sensor types...")
    sensor_types = load_sensor_types()

    print(f"✓ Loaded {len(sensor_types)} sensor types")

    # Test a few specific types
    assert 2 in sensor_types, "Type 2 (temperature) not found"
    assert sensor_types[2]["type_name"] == "sensorTemperature"
    assert sensor_types[2]["base_unit"] == "°C"
    assert sensor_types[2]["temp_dependent"] == True
    print("✓ Type 2 (sensorTemperature) validated")

    assert 10 in sensor_types, "Type 10 (switchPower) not found"
    assert sensor_types[10]["type_name"] == "switchPower"
    assert sensor_types[10]["base_unit"] == "W"
    print("✓ Type 10 (switchPower) validated")

    # Test get_sensor_config function
    config = get_sensor_config(2, temp_unit=0)
    assert config["type_name"] == "sensorTemperature"
    assert config["unit"] == "°C"
    print("✓ get_sensor_config() works correctly")

    print("✓ All sensor type tests passed!\n")

def test_relay_modes():
    """Test relay modes loading."""
    print("Testing relay modes...")
    relay_modes = load_relay_modes()

    print(f"✓ Loaded {len(relay_modes)} relay modes")

    # Test a few specific modes
    assert 0 in relay_modes, "Mode 0 not found"
    assert relay_modes[0] == "switched"
    print("✓ Mode 0 (switched) validated")

    assert 7 in relay_modes, "Mode 7 not found"
    assert relay_modes[7] == "switched cycle"
    print("✓ Mode 7 (switched cycle) validated")

    assert 15 in relay_modes, "Mode 15 not found"
    assert relay_modes[15] == "error"
    print("✓ Mode 15 (error) validated")

    # Test get_relay_mode_name function
    mode_name = get_relay_mode_name(9)
    assert mode_name == "pwm control"
    print("✓ get_relay_mode_name() works correctly")

    print("✓ All relay mode tests passed!\n")

if __name__ == "__main__":
    print("=" * 60)
    print("Testing sensor_types.py refactoring")
    print("=" * 60 + "\n")

    try:
        test_sensor_types()
        test_relay_modes()
        print("=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
