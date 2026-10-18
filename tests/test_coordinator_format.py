"""Regression tests for optional datapoint formats (standard library only)."""

import importlib.util
from pathlib import Path
import sys
import time
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


def load_coordinator():
    """Load the real coordinator with only its unrelated HA imports stubbed."""
    component = (
        Path(__file__).resolve().parents[1]
        / "custom_components" / "sorel_connect"
    )
    package_name = "_sorel_format_tests"
    package = ModuleType(package_name)
    package.__path__ = [str(component)]

    core = ModuleType("homeassistant.core")
    core.HomeAssistant = object
    dispatcher = ModuleType("homeassistant.helpers.dispatcher")
    dispatcher.async_dispatcher_send = Mock()
    sensor_types = ModuleType(f"{package_name}.sensor_types")
    for name in (
        "is_sensor_type_register", "parse_sensor_name",
        "is_relay_mode_register", "decode_relay_value",
    ):
        setattr(sensor_types, name, Mock())

    stubs = {
        package_name: package,
        "homeassistant.core": core,
        "homeassistant.helpers.dispatcher": dispatcher,
        f"{package_name}.sensor_types": sensor_types,
    }
    module_name = f"{package_name}.coordinator"
    spec = importlib.util.spec_from_file_location(
        module_name, component / "coordinator.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {**stubs, module_name: module}):
        spec.loader.exec_module(module)
    return module.Coordinator, module._LOGGER.name


Coordinator, LOGGER = load_coordinator()


class DatapointFormatTests(unittest.TestCase):
    """Decode actual register values and check results and warning behavior."""

    def setUp(self):
        self.coordinator = Coordinator(None, None, None)
        self.coordinator._registers["test"][100] = (125, time.time())

    def decode(self, **metadata):
        datapoint = {
            "name": "Min. flow rate", "type": "uns16", "step": 0.1,
            **metadata,
        }
        return self.coordinator._try_decode_dp("test", datapoint, 100, 1, 2)

    def test_missing_format_preserves_scaled_value_without_warning(self):
        with self.assertNoLogs(LOGGER, level="WARNING"):
            self.assertEqual(self.decode(), 12.5)

    def test_null_format_preserves_scaled_value_without_warning(self):
        with self.assertNoLogs(LOGGER, level="WARNING"):
            self.assertEqual(self.decode(format=None), 12.5)

    def test_empty_format_preserves_scaled_value_without_warning(self):
        with self.assertNoLogs(LOGGER, level="WARNING"):
            self.assertEqual(self.decode(format=""), 12.5)

    def test_mapping_still_uses_scaled_value(self):
        with self.assertNoLogs(LOGGER, level="WARNING"):
            self.assertEqual(self.decode(format='{"12.5": "Low"}'), "Low")

    def test_unmapped_value_remains_numeric(self):
        with self.assertNoLogs(LOGGER, level="WARNING"):
            self.assertEqual(self.decode(format='{"0": "Off"}'), 12.5)

    def test_empty_mapping_preserves_value(self):
        with self.assertNoLogs(LOGGER, level="WARNING"):
            self.assertEqual(self.decode(format="{}"), 12.5)

    def test_malformed_format_still_warns_and_preserves_value(self):
        with self.assertLogs(LOGGER, level="WARNING") as logs:
            self.assertEqual(self.decode(format="invalid JSON"), 12.5)
        self.assertIn("Error applying format", logs.output[0])

    def test_non_dictionary_format_still_warns_and_preserves_value(self):
        with self.assertLogs(LOGGER, level="WARNING") as logs:
            self.assertEqual(self.decode(format="[]"), 12.5)
        self.assertIn("is not a dictionary", logs.output[0])

    def test_sensor_error_codes_bypass_scaling_and_format(self):
        for value in (-32767, -32768):
            with self.subTest(value=value):
                self.coordinator._registers["test"][100] = (
                    value & 0xFFFF, time.time()
                )
                with self.assertNoLogs(LOGGER, level="WARNING"):
                    self.assertEqual(
                        self.decode(type="sig16", format=None), value
                    )


if __name__ == "__main__":
    unittest.main()
