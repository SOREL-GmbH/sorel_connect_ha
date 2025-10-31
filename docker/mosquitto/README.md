# Mosquitto MQTT Broker

This directory contains the configuration for the Eclipse Mosquitto MQTT broker used in development.

## Pre-Configured Authentication

The broker is configured with **authentication required** using two pre-configured users:

| Username | Password | Purpose |
|----------|----------|---------|
| `ha` | `adg` | For Home Assistant Sorel Connect integration |
| `device1` | `jmp` | For testing/simulating Sorel device messages |

These credentials are stored in the `passwords` file (hashed with bcrypt).

## Configuration

### mosquitto.conf

```conf
listener 1883 0.0.0.0        # Listen on all interfaces, port 1883
allow_anonymous false         # Authentication required
password_file /mosquitto/config/passwords  # Pre-configured users
persistence true              # Persist messages to disk
persistence_location /mosquitto/data/
log_dest stdout              # Log to Docker logs
```

## Testing MQTT

### Publish Messages (as Sorel Device)

Use the `device1` credentials to simulate a Sorel device publishing data:

```bash
# Publish a temperature datapoint (2500 = 25.00°C)
docker exec -it sorel-dev-mosquitto mosquitto_pub \
  -u device1 -P jmp \
  -t "sorel:0000/device/AA:BB:CC:DD:EE:FF/id/1/controller:5001/dp/1/100" \
  -m '{"value": 2500}'

# Publish a power reading
docker exec -it sorel-dev-mosquitto mosquitto_pub \
  -u device1 -P jmp \
  -t "sorel:0000/device/AA:BB:CC:DD:EE:FF/id/1/controller:5001/dp/1/200" \
  -m '{"value": 1500}'
```

### Subscribe to Topics

```bash
# Subscribe to all topics (requires authentication)
docker exec -it sorel-dev-mosquitto mosquitto_sub \
  -u ha -P adg \
  -t '#' -v

# Subscribe to specific device
docker exec -it sorel-dev-mosquitto mosquitto_sub \
  -u ha -P adg \
  -t 'sorel:0000/device/AA:BB:CC:DD:EE:FF/#' -v
```

## Adding Additional Users

If you need to add more MQTT users for testing:

```bash
# Add a new user (will prompt for password)
docker exec -it sorel-dev-mosquitto mosquitto_passwd /mosquitto/config/passwords newuser

# Restart the broker to apply changes
docker-compose restart mosquitto
```

## Topic Structure

Topics follow this 9-segment pattern:
```
{oem_name}:{oem_id}/device/{mac}/id/{network_id}/{device_name}:{device_id}/dp/{unit_id}/{address}
```

Example:
```
sorel:0000/device/AA:BB:CC:DD:EE:FF/id/1/controller:5001/dp/1/100
```

See [DEVELOPMENT.md](../../DEVELOPMENT.md) for details on topic parsing.

## Accessing the Container

```bash
# Shell access
docker exec -it sorel-dev-mosquitto sh

# View logs
docker-compose logs -f mosquitto

# Check active connections
docker exec -it sorel-dev-mosquitto sh -c "ps aux | grep mosquitto"
```

## Data Persistence

MQTT messages are persisted to a Docker volume (`mosq-data`) to survive container restarts.

To clear all persisted data:
```bash
docker-compose down -v
docker-compose up -d
```

## Troubleshooting

### Authentication Failures

If you see "Connection Refused: not authorized" errors:

1. Verify credentials are correct: `ha:adg` or `device1:jmp`
2. Check the passwords file exists: `docker exec sorel-dev-mosquitto cat /mosquitto/config/passwords`
3. Review broker logs: `docker-compose logs mosquitto`

### Connection Refused

If unable to connect at all:

1. Check broker is running: `docker-compose ps`
2. Verify port 1883 is accessible: `telnet localhost 1883`
3. Check for errors in logs: `docker-compose logs mosquitto | grep -i error`
