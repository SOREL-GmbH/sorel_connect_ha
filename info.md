# Sorel Connect

[![GitHub Release](https://img.shields.io/github/release/SOREL-GmbH/sorel_connect_ha.svg?style=flat-square)](https://github.com/SOREL-GmbH/sorel_connect_ha/releases)
[![License](https://img.shields.io/github/license/SOREL-GmbH/sorel_connect_ha.svg?style=flat-square)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://github.com/hacs/integration)

Monitor **Sorel Smart** heating and solar thermal controllers in Home Assistant via MQTT.

> **⚠️ EXPERIMENTAL**: Active development. Metadata availability may vary for different device types.

## What You Need

- **Sorel Smart device** compatible with Sorel Connect (if it works with the Sorel Connect app, it should work here)
- MQTT broker (Mosquitto, etc.) **Make sure to add users for your Sorel devices** by now they need to have a username/password configured
- **Internet connection** for initial device setup (metadata is cached afterward for offline use)
- Home Assistant 2023.1+

## How It Works

- **Automatic discovery**: Devices appear when they publish to MQTT topics
- **Metadata-driven**: Fetches device info from Sorel Connect API to configure sensors properly
- **Dynamic entities**: Creates sensors, binary sensors (connection status, relays), and diagnostics
- **Sensor type management**: Comprehensive sensor type identification with diagnostics
- **Relay support**: Full relay monitoring with mode configuration and percentage display
- **MQTT-driven updates**: Entities update when your device sends data over MQTT
  - **Update frequency depends on your device configuration**, not this integration
  - The integration passively receives and displays whatever your device publishes
- **Smart caching**: Metadata cached in `/config/sorel_meta_cache/` to minimize API calls

## Installation

1. Add this repository to HACS as a custom repository
2. Install "Sorel Connect" via HACS
3. Restart Home Assistant
4. Go to **Settings** → **Devices & Services** → **Add Integration** → "Sorel Connect"
5. Enter your MQTT broker details (default host: `localhost`, port: `1883`)


## Quick Troubleshooting

**No sensors appearing?**

- Check MQTT broker connection
- Verify your Sorel device is online and publishing data
- Ensure internet access for metadata fetch
- Check logs: **Settings** → **System** → **Logs**

**Need to refresh metadata?**

- **Use the service**: **Developer Tools** → **Services** → `sorel_connect.clear_metadata_cache`
- Or manually: Use File Editor to delete files in `/config/sorel_meta_cache/`, then reload the integration

## Full Documentation

For detailed setup and troubleshooting:
**[Read the full documentation on GitHub](https://github.com/SOREL-GmbH/sorel_connect_ha/blob/main/README.md)**

## Support

- [Report Issues](https://github.com/SOREL-GmbH/sorel_connect_ha/issues)
- [GitHub Repository](https://github.com/SOREL-GmbH/sorel_connect_ha)
