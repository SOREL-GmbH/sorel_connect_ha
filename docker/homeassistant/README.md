# Home Assistant Configuration

This directory contains the Home Assistant configuration for development.

## Configuration Files

### configuration.yaml
Minimal configuration with debug logging enabled for the Sorel Connect integration and MQTT component.

### .gitignore
Excludes runtime files (databases, logs, storage) from version control while keeping the base configuration.yaml.

## Directory Structure

```
config/
├── configuration.yaml       # Committed - base configuration
├── .gitignore              # Committed - excludes runtime files
├── .storage/               # Ignored - HA internal state
├── *.db*                   # Ignored - databases
├── *.log*                  # Ignored - log files
├── sorel_meta_cache/       # Ignored - integration metadata cache
└── custom_components/      # Mounted from parent directory (read-only)
```

## Integration Mount

The integration code is mounted read-only from `../custom_components/` to `/config/custom_components/` inside the container.

After making changes to integration code:
```bash
docker-compose restart homeassistant
```

## Accessing the Container

```bash
# Shell access
docker exec -it sorel-dev-ha bash

# Check integration files
docker exec sorel-dev-ha ls -la /config/custom_components/sorel_connect/

# View logs
docker exec sorel-dev-ha tail -f /config/home-assistant.log
```

## Debug Logging

To change log levels, edit `configuration.yaml`:

```yaml
logger:
  default: warning  # or info, debug
  logs:
    custom_components.sorel_connect: debug  # integration logs
    homeassistant.components.mqtt: debug    # MQTT logs
```

Then restart Home Assistant.
