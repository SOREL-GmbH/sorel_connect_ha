# Development Environment

This directory contains a Docker Compose setup for developing and testing the Sorel Connect integration locally.

## Quick Start

1. **Start the development stack**:
   ```bash
   cd docker
   docker-compose up -d
   ```

2. **Access Home Assistant** and complete onboarding:
   - Open http://localhost:8123
   - **Create your admin user** (required on first start)
     - Suggested for dev: username `admin`, password `test123`
     - Name your home: "Dev Environment" (or anything)
     - Set location or skip
     - Choose analytics preference

3. **Configure Sorel Connect integration**:
   - Go to **Settings** → **Devices & Services**
   - Click **+ Add Integration**
   - Search for "Sorel Connect"
   - **MQTT Broker Configuration**:
     - Host: `mosquitto`
     - Port: `1883`
     - Username: `ha`
     - Password: `adg`
   - **API Settings**: Use defaults (or customize as needed)

4. **View logs**:
   ```bash
   docker-compose logs -f homeassistant
   docker-compose logs -f mosquitto
   ```

5. **Restart after code changes**:
   ```bash
   docker-compose restart homeassistant
   ```

6. **Stop everything**:
   ```bash
   docker-compose down
   ```

## Components

### Home Assistant
- **Container**: `sorel-dev-ha`
- **Port**: 8123
- **Config**: `./homeassistant/config/`
- **Integration mounted read-only**: `../custom_components/` → `/config/custom_components/`

See [homeassistant/README.md](homeassistant/README.md) for details.

### Mosquitto MQTT Broker
- **Container**: `sorel-dev-mosquitto`
- **Port**: 1883
- **Config**: `./mosquitto/mosquitto.conf`
- **Authentication**: Required (pre-configured users)
  - `ha` / `adg` → For HA integration
  - `device1` / `jmp` → For testing/simulating devices

See [mosquitto/README.md](mosquitto/README.md) for details.

## Testing MQTT Messages

Publish test datapoints to verify integration behavior using the `device1` credentials:

```bash
# Publish a temperature value (2500 = 25.00°C)
docker exec -it sorel-dev-mosquitto mosquitto_pub \
  -u device1 -P jmp \
  -t "sorel:0000/device/AA:BB:CC:DD:EE:FF/id/1/controller:5001/dp/1/100" \
  -m '{"value": 2500}'

# Publish a power reading
docker exec -it sorel-dev-mosquitto mosquitto_pub \
  -u device1 -P jmp \
  -t "sorel:0000/device/AA:BB:CC:DD:EE:FF/id/1/controller:5001/dp/1/200" \
  -m '{"value": 1500}'

# Subscribe to all topics to see what's happening
docker exec -it sorel-dev-mosquitto mosquitto_sub \
  -u ha -P adg \
  -t '#' -v
```

## Debug Logging

Debug logging is enabled by default in `homeassistant/config/configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.sorel_connect: debug
    homeassistant.components.mqtt: debug
```

Logs are available:
- Home Assistant UI: **Settings** → **System** → **Logs**
- Docker logs: `docker-compose logs -f homeassistant`

## Troubleshooting

### Integration not loading
1. Check logs: `docker-compose logs homeassistant`
2. Verify integration is mounted: `docker exec sorel-dev-ha ls -la /config/custom_components/sorel_connect/`
3. Restart HA: `docker-compose restart homeassistant`

### MQTT connection issues
1. Check broker is running: `docker-compose ps`
2. Verify port 1883 is accessible: `telnet localhost 1883`
3. Check broker logs: `docker-compose logs mosquitto`

### Database locked errors
Stop containers and remove database:
```bash
docker-compose down
rm homeassistant/config/home-assistant_v2.db*
docker-compose up -d
```

## Clean Slate

To completely reset the environment:

```bash
docker-compose down -v
rm -rf homeassistant/config/.storage homeassistant/config/*.db*
docker-compose up -d
```

**Note**: This will delete all Home Assistant configuration and data.
