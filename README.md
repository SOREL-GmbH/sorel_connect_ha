# Sorel Connect

Home Assistant integration for connecting network-enabled Sorel heating/HVAC devices via MQTT.

> **⚠️ EXPERIMENTAL**: This integration is in active development and should be considered experimental. Metadata availability and device support may vary.

## Overview

Sorel Connect is a custom integration for Home Assistant that enables monitoring and control of **Sorel Smart devices** that are compatible with the official **Sorel Connect** system. The integration connects to your devices via MQTT, automatically discovering datapoints and creating appropriate sensors in Home Assistant.

### Device Compatibility

This integration is designed specifically for:
- **Sorel Smart** heating controllers, solar thermal controllers, and HVAC control systems
- Devices that are compatible with the **Sorel Connect** cloud service
- Network-enabled Sorel devices with MQTT support

If your device works with the official Sorel Connect mobile app or web interface, it should be compatible with this integration.

### Features

- **Automatic Device Discovery**: Discovers Sorel devices automatically via MQTT topics
- **Dynamic Sensor Creation**: Automatically creates sensors for all available datapoints
- **Binary Sensors**: MQTT connection status monitoring and relay state tracking
- **Relay Support**: Full relay control with mode configuration, percentage formatting, and diagnostics
- **Sensor Type Management**: Comprehensive sensor type management with diagnostics
- **Metadata-Driven**: Fetches device metadata from Sorel API for proper unit mapping and configuration
- **Smart Caching**: Intelligent metadata caching with retry logic to minimize API calls
- **Cache Management Service**: Built-in service to clear and refresh metadata cache without manual file operations
- **Unit Conversion**: Automatic mapping to Home Assistant standard units (temperature, power, energy, etc.)
- **Long-term Statistics**: Properly configured state classes for energy monitoring and statistics
- **Device Classification**: Automatic device class detection (temperature, power, voltage, etc.)
- **Enhanced Diagnostics**: Detailed metadata status, connection monitoring, and device information

## Requirements

- Home Assistant Core 2023.1 or later
- MQTT broker (e.g., Mosquitto) accessible to your Sorel devices

   **Authentication is required for Sorel devices to connect to the MQTT broker.**
   Make sure to add users for your Sorel devices.

   If using the Mosquitto broker add-on, follow these steps:
   1. Stop the broker if it's running
   2. Go to **Mosquitto broker** → **Konfiguration**
   3. Add a users for your Sorel devices
   4. Add a user for Home Assistant integration if you want to use authentication there
   5. Save the configuration
   6. Start the broker

   If you prefer not to use authentication for the integration, ensure your MQTT broker allows anonymous connections.

   Instead of setting users in the mosquitto add-on, you can also add Homeassistant users. The add-on will automatically use those users.

- Sorel Smart device compatible with Sorel Connect
- **Internet connection required**:
  - **First-time setup**: Internet access is mandatory for initial metadata retrieval from the Sorel Connect metadata API
  - **Ongoing operation**: Metadata is cached locally; internet only needed for new/unknown devices
  - **Offline resilience**: Previously discovered devices continue working with cached metadata even when offline

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add `https://github.com/SorelHaDev/sorel_connect` as repository
5. Select "Integration" as category
6. Click "Add"
8. Click "Install" on the Sorel Connect card
9. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/SorelHaDev/sorel_connect/releases)
2. Extract the `sorel_connect` folder to your `custom_components` directory
3. The directory structure should be:
   ```
   custom_components/
   └── sorel_connect/
       ├── __init__.py
       ├── config_flow.py
       ├── coordinator.py
       ├── manifest.json
       └── ...
   ```
4. Restart Home Assistant

## Configuration

### Add Integration via UI

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Sorel Connect"
4. Follow the configuration steps:

#### MQTT Broker Settings

- **Host**: MQTT broker hostname or IP (default: `localhost`)
- **Port**: MQTT broker port (default: `1883`)
- **Username**: MQTT username (optional)
- **Password**: MQTT password (optional)
- **Use TLS**: Enable TLS/SSL encryption (optional)

#### API Settings

- **API Server**: Sorel metadata API server (default: pre-configured)
- **API URL Template**: API endpoint template (default: pre-configured)

### MQTT Topic Structure

The integration expects MQTT topics in the following format:

```
{oem_name}:{oem_id}/device/{mac}/id/{network_id}/{device_name}:{device_id}/dp/{unit_id}/{address}
```

Example:
```
sorel:0000/device/AA:BB:CC:DD:EE:FF/id/1/controller:5001/dp/1/100
```

### Payload Format

The integration supports multiple payload formats:


1. **JSON with value** (address from topic):
   ```json
   {"value": 2500}
   ```


2. **Plain number** (address from topic):
   ```
   2500
   ```

## Entities Created

### Binary Sensors

- **MQTT Connection Status**: Monitors the connection status to the MQTT broker
- **Relay States**: Binary sensors for each relay showing on/off state

### Diagnostic Sensors (per device)

For each discovered device, the following diagnostic sensors are created:

- **Device Type**: The device type identifier
- **OEM ID**: Organization/manufacturer identifier
- **Network ID**: Network identifier for the device
- **Metadata Status**: Shows metadata fetch status and detailed debugging information

### Datapoint Sensors (dynamic)

For each datapoint discovered via MQTT, a sensor entity is created with:

- **Name**: From device metadata
- **Unit**: Automatically mapped to HA standard units (°C → Celsius, W → Watt, etc.)
- **Device Class**: Auto-detected (temperature, power, energy, voltage, etc.)
- **State Class**: Configured for long-term statistics
  - `measurement` for instantaneous values
  - `total_increasing` for energy counters

### Relay Sensors

Relay datapoints are automatically formatted with:

- **Percentage display**: Values shown as percentages (0-100%)
- **Mode configuration**: Relay operating modes with diagnostics
- **Binary sensor support**: On/off state tracking

## Supported Units

The integration automatically maps the following units:

| Raw Unit | HA Unit | Device Class |
|----------|---------|--------------|
| °C, C | Celsius | Temperature |
| K | Kelvin | Temperature |
| °F | Fahrenheit | Temperature |
| W | Watt | Power |
| kW | Kilowatt | Power |
| Wh | Watt-hour | Energy |
| kWh | Kilowatt-hour | Energy |
| V | Volt | Voltage |
| A | Ampere | Current |
| Hz | Hertz | Frequency |
| bar | Bar | Pressure |
| l, L | Liters | Volume |
| m³ | Cubic meters | Volume |
| % | Percentage | - |

## Data Types Supported

The integration can decode the following Modbus register data types:

- `uint8`, `uns8`: Unsigned 8-bit integer
- `uint16`, `uns16`: Unsigned 16-bit integer
- `int16`, `sig16`: Signed 16-bit integer
- `uint32`, `uns32`: Unsigned 32-bit integer
- `int32`, `sig32`: Signed 32-bit integer
- `float32`, `float`: 32-bit floating point
- `bool`, `boolean`: Boolean value
- `str`, `char`: String/character data

## Metadata Caching

The integration **depends on the Sorel Connect metadata API** to understand device capabilities, datapoint names, units, and types. This is essential for proper sensor configuration.

### How Metadata Works

1. **First Discovery**: When a new device is discovered via MQTT, the integration contacts the Sorel Connect metadata API to fetch device information
2. **Local Caching**: Retrieved metadata is cached in `/config/sorel_meta_cache/` as JSON files
3. **Subsequent Restarts**: Cached metadata is used immediately; no API call needed
4. **New Devices Only**: API calls only occur for previously unknown device types
5. **Retry Logic**: Failed API requests retry with exponential backoff (5min, 10min, 30min, 1h)
6. **Permanent Failures**: Devices returning 404 errors are marked as permanently unavailable

### Important Notes

- **Internet Required for First Setup**: Initial configuration of any device type requires internet connectivity
- **Metadata Availability**: Not all device types may have metadata available in the API (experimental feature)
- **Cache Location**: All metadata is stored in `/config/sorel_meta_cache/` directory
- **Offline Operation**: Once cached, devices work without internet access

## Services

### Clear Metadata Cache

The integration provides a service to clear cached metadata and force a refresh from the Sorel Connect API.

**Service name**: `sorel_connect.clear_metadata_cache`

**How to use**:

1. Go to **Developer Tools** → **Services**
2. Select `sorel_connect.clear_metadata_cache`
3. Click **Call Service**

This will:

- Delete all cached metadata files from `/config/sorel_meta_cache/`
- Force the integration to fetch fresh metadata from the API for all devices
- Automatically reload device configurations

**Note**: Internet connection is required for the integration to fetch fresh metadata after clearing the cache.

## Options

You can modify integration settings after setup:

1. Go to **Settings** → **Devices & Services**
2. Find "Sorel Connect"
3. Click **Configure**

Available options:

- **API Server**: Change the Sorel metadata API server URL
- **API URL Template**: Modify the API endpoint template for metadata requests

## Troubleshooting

### No devices discovered

1. Verify your MQTT broker is running and accessible
2. Check that your Sorel device is publishing to the correct topics
3. Enable debug logging (see below)
4. Verify the topic prefix matches your device configuration

### Missing sensors

1. Check that metadata is available for your device type
2. Look in `/config/sorel_meta_cache/` for cached metadata files
3. Verify MQTT messages are being received (check MQTT broker logs)
4. Check Home Assistant logs for metadata fetch errors

### Clearing Metadata Cache

If you encounter issues with stale or incorrect metadata, you can clear the cache and force a refresh from the API.

#### Using the Built-in Service (Recommended)

1. Go to **Developer Tools** → **Services**
2. Select `sorel_connect.clear_metadata_cache`
3. Click **Call Service**

The integration will automatically delete all cached metadata and fetch fresh data from the Sorel Connect API.

#### Manual Method (Alternative)

If you prefer to manually manage cache files or need to clear specific device metadata:

**Using File Editor Add-on:**

1. Install the **File Editor** add-on from the Add-on Store (if not already installed)
2. Open File Editor from the sidebar
3. Navigate to `/sorel_meta_cache`
4. Delete the problematic metadata files (named like `0000_5001.json` where format is `{oem_id}_{device_id}.json`)
   - To clear all metadata: delete all `.json` files in the directory
   - To clear specific device: delete only that device's file
5. Go to **Settings** → **Devices & Services**
6. Find "Sorel Connect" and click the three dots → **Reload**

**Note**: After clearing the cache, the integration will automatically fetch fresh metadata from the Sorel Connect API when devices are next discovered. **Internet connection is required** for this to work.

### Enable Debug Logging

Add to your `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.sorel_connect: debug
    homeassistant.components.mqtt: debug
```

Then restart Home Assistant and check the logs under **Settings** → **System** → **Logs**.

## Known Limitations

- **Metadata availability varies**: Not all Sorel Smart device types have metadata available in the API yet (experimental)
- No device removal/cleanup functionality yet

## Planned Features (TODO)

- [ ] Device removal/cleanup functionality
- [ ] Improved metadata availability and fallback handling for devices without API metadata
- [ ] Optional forwarding of raw MQTT messages to enable users to also use the default Sorel Connect app alongside this integration
- [ ] Add language selection to setup to fetch translated metadata where available

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

- [Report Issues](https://github.com/SorelHaDev/sorel_connect/issues)
- [GitHub Repository](https://github.com/SorelHaDev/sorel_connect)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Credits

Developed for the Home Assistant community to enable integration with Sorel heating and HVAC control systems.
