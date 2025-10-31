# Test Scripts

This directory contains test scripts for the Sorel Connect integration.

## Current Test Scripts

These are **manual test scripts** (not automated unit tests). They verify specific components of the integration by directly importing and testing the modules.

### test_sensor_types.py

Tests the sensor type logic and sensor name parsing.

**Run:**
```bash
cd tests
python test_sensor_types.py
```

**Tests:**
- CSV loading from sensor_types module
- Sensor name parsing (e.g., "S1", "S2")
- Sensor type register detection
- Sensor configuration retrieval
- Type register address calculation

### test_sensor_types_refactor.py

Quick validation test for the sensor_types.py refactoring.

**Run:**
```bash
cd tests
python test_sensor_types_refactor.py
```

**Tests:**
- Sensor types data loading and structure
- Relay modes data loading
- get_sensor_config() function
- get_relay_mode_name() function

### verify_const_data.py

Verifies the data structures in const.py are correctly formatted.

**Run:**
```bash
cd tests
python verify_const_data.py
```

**Tests:**
- SENSOR_TYPES dictionary structure and field types
- RELAY_MODES dictionary structure and field types
- Data integrity and completeness

## Running All Tests

**Note:** These scripts require Home Assistant dependencies to be installed, as they import from `homeassistant` modules. They are designed to run in a development environment.

From the `tests/` directory:

```bash
# Run all test scripts
python test_sensor_types.py
python test_sensor_types_refactor.py
python verify_const_data.py
```

**Alternative:** Run them inside the Home Assistant Docker container where dependencies are available:

```bash
# From repository root
docker exec -it sorel-dev-ha bash
cd /config/custom_components/sorel_connect
python3 tests/test_sensor_types_refactor.py
```

## Future: Automated Testing

These manual scripts will be replaced/supplemented with proper automated tests using `pytest`:

- Unit tests for individual functions
- Integration tests for component interactions
- Mocking for Home Assistant dependencies
- CI/CD integration with GitHub Actions

**Planned structure:**
```
tests/
├── __init__.py
├── conftest.py           # pytest fixtures
├── test_coordinator.py   # coordinator logic tests
├── test_topic_parser.py  # MQTT topic parsing tests
├── test_meta_client.py   # metadata client tests
├── test_sensor.py        # sensor platform tests
└── test_binary_sensor.py # binary sensor tests
```

## Contributing

When adding new functionality to the integration:

1. Test your changes manually using these scripts
2. Consider adding test cases to the relevant script
3. Eventually, contribute pytest-based unit tests

For more information, see [CONTRIBUTING.md](../CONTRIBUTING.md) and [DEVELOPMENT.md](../DEVELOPMENT.md).
