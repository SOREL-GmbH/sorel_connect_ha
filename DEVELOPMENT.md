# Development Guide

This guide provides technical details for developers working on the Sorel Connect Home Assistant integration.

## Repository Structure

```
sorel_connect/                          # Repository root
├── custom_components/
│   └── sorel_connect/                  # Integration code
│       ├── __init__.py                 # Entry point & setup
│       ├── coordinator.py              # Core logic
│       ├── sensor.py                   # Sensor platform
│       ├── binary_sensor.py            # Binary sensor platform
│       ├── config_flow.py              # Configuration UI
│       ├── meta_client.py              # Metadata API client
│       ├── mqtt_gateway.py             # MQTT wrapper
│       ├── topic_parser.py             # Topic parser
│       ├── sensor_types.py             # Sensor type definitions
│       ├── const.py                    # Constants
│       ├── manifest.json               # Integration metadata
│       ├── strings.json                # i18n strings
│       ├── services.yaml               # Service definitions
│       └── translations/               # Translations
├── docker/                              # Development environment
│   ├── docker-compose.yml              # Development stack
│   ├── homeassistant/                  # Home Assistant config
│   └── mosquitto/                      # MQTT broker config
├── tests/                               # Automated tests (TODO)
└── docs/                                # Extended documentation (optional)
```

## Development Environment

### Quick Start

```bash
# Start Home Assistant + MQTT broker
cd docker
docker-compose up -d

# View logs
docker-compose logs -f homeassistant
docker-compose logs -f mosquitto

# Stop everything
docker-compose down
```

Home Assistant will be available at: http://localhost:8123

The integration is mounted read-only into the container at `/config/custom_components/`. After code changes, restart HA:

```bash
docker-compose restart homeassistant
```

See [docker/README.md](docker/README.md) for detailed setup instructions.

### Debug Logging

Debug logging is enabled by default in `docker/homeassistant/config/configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.sorel_connect: debug
    homeassistant.components.mqtt: debug
```

Logs appear in Home Assistant UI under **Settings** → **System** → **Logs**, or via:
```bash
docker-compose logs -f homeassistant
```

### Testing MQTT Messages

The development environment uses **pre-configured MQTT authentication**:
- `ha` / `adg` → For Home Assistant integration
- `device1` / `jmp` → For testing/simulating devices

Publish test messages to Mosquitto:

```bash
# Publish a test datapoint (using device1 credentials)
docker exec -it sorel-dev-mosquitto mosquitto_pub \
  -u device1 -P jmp \
  -t "sorel:0000/device/AA:BB:CC:DD:EE:FF/id/1/controller:5001/dp/1/100" \
  -m '{"value": 2500}'

# Subscribe to all topics (using HA credentials)
docker exec -it sorel-dev-mosquitto mosquitto_sub \
  -u ha -P adg \
  -t '#' -v
```

## Integration Architecture

### Data Flow: MQTT → Sensors

1. **MQTT Gateway** ([mqtt_gateway.py](custom_components/sorel_connect/mqtt_gateway.py)): Paho MQTT client wrapper with async support

2. **Coordinator** ([coordinator.py](custom_components/sorel_connect/coordinator.py)): Central orchestrator that:
   - Subscribes to wildcard MQTT topics: `+/device/+/+/+/+/dp/+/+`
   - Parses topics using `topic_parser.py` into structured `ParsedTopic` objects
   - Discovers new devices and dispatches `SIGNAL_NEW_DEVICE`
   - Accumulates Modbus registers until complete multi-register values can be decoded
   - Decodes datapoints based on metadata types (uint8/16/32, int16/32, float32, bool, string)
   - Dispatches `SIGNAL_DP_UPDATE` when values change

3. **Meta Client** ([meta_client.py](custom_components/sorel_connect/meta_client.py)): Fetches device metadata from Sorel API
   - Caches metadata in `/config/sorel_meta_cache/` to minimize API calls
   - Implements exponential backoff retry (5min, 10min, 30min, 1h)
   - Marks permanently unavailable devices (404 responses)

4. **Sensor Platform** ([sensor.py](custom_components/sorel_connect/sensor.py)): Creates entities dynamically
   - Creates diagnostic sensors per device immediately (Device Type, OEM ID, Network ID, Metadata Status)
   - Creates datapoint sensors lazily on first value arrival
   - Maps units (°C → CELSIUS, W → WATT, etc.) and device classes

5. **Binary Sensor Platform** ([binary_sensor.py](custom_components/sorel_connect/binary_sensor.py)): Creates binary sensors
   - MQTT connection status monitoring
   - Relay state tracking

### Topic Structure

Topics follow this 9-segment pattern:
```
{oem_name}:{oem_id}/device/{mac}/id/{network_id}/{device_name}:{device_id}/dp/{unit_id}/{address}
```

Example: `sorel:0000/device/AA:BB:CC:DD:EE:FF/id/1/controller:5001/dp/1/100`

The [topic_parser.py](custom_components/sorel_connect/topic_parser.py) validates this structure and extracts all components into a `ParsedTopic` dataclass. The `device_key` property (`mac::network_id`) uniquely identifies physical devices.

### Register Decoding Strategy

The coordinator uses a **register accumulation** approach:

1. Individual MQTT messages carry single 16-bit register values at specific addresses
2. Registers are stored with timestamps in `_registers[device_key][address]`
3. When a register arrives, the coordinator checks all datapoints to see if enough consecutive registers exist
4. Multi-register values (uint32, float32) are only decoded if all registers are fresh (< 10 seconds old)
5. Decoded values are cached in `_dp_value_cache` and dispatched via signals

### Hardcoded Limitation

**Organization ID is currently hardcoded to "0000"** in [coordinator.py:47](custom_components/sorel_connect/coordinator.py#L47). This affects metadata fetching. Future improvement: make this configurable or extract from MQTT topics.

## Modifying the Integration

### Adding Support for New Data Types

Edit [coordinator.py](custom_components/sorel_connect/coordinator.py) in the `_try_decode_dp()` method. The type string comes from metadata's `"type"` field.

### Adding New Unit Mappings

Edit [sensor.py](custom_components/sorel_connect/sensor.py):
- Add to `UNIT_MAP` for unit conversion
- Add to `DEVICE_CLASS_BY_UNIT` for device class detection

### Changing Metadata API Behavior

Edit [meta_client.py](custom_components/sorel_connect/meta_client.py):
- Retry intervals: `_retry_intervals`
- Cache directory: `_cache_dir` parameter
- Permanent failure detection: `_fetch_metadata_direct()`

## Home Assistant Integration Standards

This integration follows HA best practices:

- **Config Flow**: UI-based setup in `config_flow.py` (no YAML configuration)
- **i18n Support**: `strings.json` and `translations/en.json` for UI text
- **HACS Compatible**: `hacs.json` and `info.md` for HACS distribution
- **Platform Pattern**: Implements `async_setup_entry()` for sensor platform
- **Signals**: Uses `async_dispatcher_send/connect` for decoupled communication between coordinator and entities
- **State Classes**: Properly configured for long-term statistics (energy sensors use `TOTAL_INCREASING`)

## Key Files

- [\_\_init\_\_.py](custom_components/sorel_connect/__init__.py): 4-step initialization (MQTT → Meta Client → Coordinator → Platform setup)
- [config_flow.py](custom_components/sorel_connect/config_flow.py): User configuration UI and options flow
- [coordinator.py](custom_components/sorel_connect/coordinator.py): Core logic (device discovery, register decoding, value dispatch)
- [sensor.py](custom_components/sorel_connect/sensor.py): Entity platform (creates diagnostic + datapoint sensors)
- [binary_sensor.py](custom_components/sorel_connect/binary_sensor.py): Binary sensor platform
- [meta_client.py](custom_components/sorel_connect/meta_client.py): Metadata API client with caching and retry logic
- [mqtt_gateway.py](custom_components/sorel_connect/mqtt_gateway.py): Async MQTT wrapper around paho-mqtt
- [topic_parser.py](custom_components/sorel_connect/topic_parser.py): MQTT topic structure parser
- [sensor_types.py](custom_components/sorel_connect/sensor_types.py): Sensor type definitions and mappings
- [const.py](custom_components/sorel_connect/const.py): Constants and configuration
- [manifest.json](custom_components/sorel_connect/manifest.json): Integration metadata (version, dependencies, documentation URLs)
- [strings.json](custom_components/sorel_connect/strings.json) + [translations/en.json](custom_components/sorel_connect/translations/en.json): UI text for config flow
- [services.yaml](custom_components/sorel_connect/services.yaml): Service definitions

## Dependencies

From `manifest.json`:
- `paho-mqtt>=1.6.1`: MQTT client library
- `aiofiles`: Async file I/O for metadata caching

## Known Issues & Limitations

- No automated tests yet
- Device cleanup/removal not implemented
- Organization ID hardcoded to "0000"

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and contribution guidelines.
