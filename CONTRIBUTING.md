# Contributing to Sorel Connect

Thank you for your interest in contributing to the Sorel Connect Home Assistant integration!

## Quick Start for Contributors

### Prerequisites

- **Docker** and **Docker Compose** installed
- **Git** for version control
- A text editor or IDE (VS Code recommended)

### Setup Development Environment

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/YOUR-USERNAME/sorel_connect.git
   cd sorel_connect
   ```

2. **Start the development stack**:
   ```bash
   cd docker
   docker-compose up -d
   ```

3. **Access Home Assistant** and set up the integration:
   - Open http://localhost:8123
   - **Complete onboarding** (first-time setup):
     - Create admin user (suggested: `admin` / `test123` for dev)
     - Configure your home name and location
   - Go to **Settings** → **Devices & Services** → **+ Add Integration**
   - Search for "Sorel Connect"
   - **Configure MQTT connection**:
     - MQTT Broker Host: `mosquitto`
     - MQTT Port: `1883`
     - MQTT Username: `ha` or none
     - MQTT Password: `adg` or none
   - Leave API settings as default (or customize)

4. **View logs in real-time**:
   ```bash
   docker-compose logs -f homeassistant
   ```

### Making Changes

1. **Edit integration code** in `custom_components/sorel_connect/`

2. **Restart Home Assistant** to load changes:
   ```bash
   docker-compose restart homeassistant
   ```

3. **Check logs** for errors:
   ```bash
   docker-compose logs homeassistant | grep -i error
   ```

4. **Test your changes** by interacting with the integration in Home Assistant

### Testing MQTT Messages

Simulate Sorel device messages using the `device1` test credentials:
If you have access to a real Sorel device or a simulation tool, you can publish actual device messages to test the integration.

**Pre-configured MQTT users:**
- `ha` / `adg` → Used by the Home Assistant integration
- `device1` / `jmp` → Used for testing/simulating device messages

### Submitting Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** and commit:
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```

3. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Open a Pull Request** on GitHub with:
   - Clear description of what you changed
   - Why the change is needed
   - How you tested it

## Development Guidelines

### Code Style

- Follow PEP 8 Python style guidelines
- Use descriptive variable names
- Add docstrings to functions and classes
- Keep functions focused and modular

### Documentation

- Update relevant README sections if you change functionality
- Add comments for complex logic
- Update `DEVELOPMENT.md` if you change architecture

### Testing

- Test your changes with real or simulated MQTT messages
- Verify the integration loads without errors
- Check that sensors appear correctly in Home Assistant
- Test edge cases (missing metadata, malformed messages, etc.)

## Project Structure

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed architecture documentation.

Key files:
- `__init__.py` - Integration initialization
- `coordinator.py` - Core logic (MQTT handling, register decoding)
- `sensor.py` - Sensor platform
- `binary_sensor.py` - Binary sensor platform
- `config_flow.py` - Configuration UI
- `meta_client.py` - Metadata API client
- `mqtt_gateway.py` - MQTT wrapper

## Need Help?

- Check [DEVELOPMENT.md](DEVELOPMENT.md) for architecture details
- Browse [existing issues](https://github.com/SorelHaDev/sorel_connect/issues)
- Open a [new issue](https://github.com/SorelHaDev/sorel_connect/issues/new) if you're stuck

## Code of Conduct

- Be respectful and constructive
- Help others learn and improve
- Focus on the code, not the person
- Welcome newcomers and be patient

## License

By contributing, you agree that your contributions will be licensed under the same MIT License that covers this project.
