#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify const.py data structure is correct."""

import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '../custom_components/sorel_connect')

from const import SENSOR_TYPES, RELAY_MODES

def verify_sensor_types():
    """Verify sensor types structure."""
    print("Verifying SENSOR_TYPES structure...")

    assert isinstance(SENSOR_TYPES, dict), "SENSOR_TYPES must be a dict"
    print(f"✓ SENSOR_TYPES is a dict with {len(SENSOR_TYPES)} entries")

    # Verify each entry has required fields
    required_fields = {"type_name", "base_unit", "device_class", "temp_dependent"}

    for type_id, info in SENSOR_TYPES.items():
        assert isinstance(type_id, int), f"Type ID must be int, got {type(type_id)}"
        assert isinstance(info, dict), f"Type info must be dict for ID {type_id}"

        missing = required_fields - set(info.keys())
        assert not missing, f"Type {type_id} missing fields: {missing}"

        # Verify field types
        assert isinstance(info["type_name"], str), f"type_name must be str for ID {type_id}"
        assert info["base_unit"] is None or isinstance(info["base_unit"], str), \
            f"base_unit must be str or None for ID {type_id}"
        assert info["device_class"] is None or isinstance(info["device_class"], str), \
            f"device_class must be str or None for ID {type_id}"
        assert isinstance(info["temp_dependent"], bool), \
            f"temp_dependent must be bool for ID {type_id}"

    print(f"✓ All {len(SENSOR_TYPES)} sensor types have correct structure")

    # Show some examples
    print("\nExample sensor types:")
    for type_id in [2, 10, 23]:
        if type_id in SENSOR_TYPES:
            info = SENSOR_TYPES[type_id]
            print(f"  {type_id}: {info['type_name']} ({info['base_unit']})")

    print()

def verify_relay_modes():
    """Verify relay modes structure."""
    print("Verifying RELAY_MODES structure...")

    assert isinstance(RELAY_MODES, dict), "RELAY_MODES must be a dict"
    print(f"✓ RELAY_MODES is a dict with {len(RELAY_MODES)} entries")

    # Verify each entry
    for mode_id, mode_name in RELAY_MODES.items():
        assert isinstance(mode_id, int), f"Mode ID must be int, got {type(mode_id)}"
        assert isinstance(mode_name, str), f"Mode name must be str for ID {mode_id}"

    print(f"✓ All {len(RELAY_MODES)} relay modes have correct structure")

    # Show some examples
    print("\nExample relay modes:")
    for mode_id in [0, 7, 9, 15]:
        if mode_id in RELAY_MODES:
            print(f"  {mode_id}: {RELAY_MODES[mode_id]}")

    print()

if __name__ == "__main__":
    print("=" * 60)
    print("Verifying const.py data structures")
    print("=" * 60 + "\n")

    try:
        verify_sensor_types()
        verify_relay_modes()
        print("=" * 60)
        print("✓ ALL VERIFICATIONS PASSED!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ VERIFICATION FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
