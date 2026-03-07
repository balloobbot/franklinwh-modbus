# FranklinWH Battery Manager - Configuration Guide

This guide explains all the ways to configure the FranklinWH Battery Manager application.

---

## 🚀 Quick Start

### Option 1: Interactive Setup Wizard (Recommended for First Time)

```bash
# Run the setup wizard
python3 setup.py
```

This interactive wizard will guide you through:
- Choosing mock or live mode
- Setting up Modbus connection (for live mode)
- Configuring MQTT (optional)
- Web UI preferences

### Option 2: Run with Mock Mode (No Device Required)

```bash
# Method 1: Environment variable
MOCK_MODE=true ./run.sh

# Method 2: Create a minimal config
mkdir -p data && echo '{"mock_mode": true}' > data/config.json
./run.sh
```

### Option 3: Manual Configuration

Create `data/config.json` with your settings (see [Configuration File](#configuration-file) section below).

---

## 🎭 Mock Mode vs Live Mode

### Mock Mode

Mock mode uses a **simulated battery** that generates realistic data without requiring a real device. Perfect for:
- Testing the web UI
- Developing new features
- Demonstrations
- Learning the application

**Mock mode characteristics:**
- Simulated SOC gradually changes based on power flow
- Power values fluctuate realistically
- All 5 operating modes available
- Full WebSocket and MQTT functionality
- No Modbus hardware required

### Live Mode

Live mode connects to your **real FranklinWH battery** via Modbus TCP.

**Requirements:**
- FranklinWH aPower battery or aGate gateway
- Network connectivity to device (TCP port 502)
- Device IP address and unit ID

---

## ⚙️ Configuration Methods

There are **three ways** to configure the application, in order of precedence:

1. **Environment Variables** (highest priority)
2. **Configuration File** (`data/config.json`)
3. **Built-in Defaults** (lowest priority)

### MQTT Connection Behavior

The MQTT connection now works with a **non-blocking, fault-tolerant** design:

| Feature | Behavior |
|---------|----------|
| **Startup** | MQTT starts in `offline` mode, never blocks dashboard |
| **Auto-retry** | Background task retries connection every 30 seconds |
| **First connect** | Once connected, automatically sets up HA entities |
| **Reconnect** | Automatically reconnects if connection drops |
| **Manual control** | Can be enabled/disabled via API at runtime |

**MQTT Status Values:**
- `disabled` - MQTT manually turned off
- `offline` - Not connected, will retry automatically
- `connecting` - Currently attempting connection
- `online` - Connected and publishing
- `failed` - Max retries reached (rare)

**API Endpoints:**
- `GET /api/health` - Shows MQTT status in response
- `GET /api/mqtt/status` - Detailed MQTT connection info
- `POST /api/mqtt/enable` - Enable MQTT (auto-connects in background)
- `POST /api/mqtt/disable` - Disable MQTT (stops all activity)
- `POST /api/mqtt/restart` - Restart MQTT connection

### Method 1: Environment Variables

Environment variables override all other settings. Useful for:
- Docker deployments
- Temporary changes
- Sensitive data (passwords)
- CI/CD pipelines

#### Using `.env` File

Create a `.env` file in the project root:

```bash
# Operation Mode
MOCK_MODE=false

# Modbus Settings
MODBUS_HOST=192.168.1.50
MODBUS_PORT=502
MODBUS_UNIT=2
MODBUS_TIMEOUT=5.0

# MQTT Settings
MQTT_HOST=192.168.1.100
MQTT_PORT=1883
MQTT_USERNAME=mqtt_user
MQTT_PASSWORD=secret_password
MQTT_CLIENT_ID=franklinwh_bridge

# Application Settings
LOG_LEVEL=INFO
```

The `.env` file is automatically loaded when the application starts.

#### Available Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MOCK_MODE` | Enable mock device simulation | `false` |
| `MODBUS_HOST` | Device IP address | `192.168.0.110` |
| `MODBUS_PORT` | Modbus TCP port | `502` |
| `MODBUS_UNIT` | Device unit/slave ID | `2` |
| `MODBUS_BASE_ADDRESS` | Starting register address | `40000` |
| `MODBUS_TIMEOUT` | Connection timeout (seconds) | `5.0` |
| `MQTT_HOST` | MQTT broker IP/hostname | `192.168.0.109` |
| `MQTT_PORT` | MQTT broker port | `1883` |
| `MQTT_USERNAME` | MQTT authentication username | (empty) |
| `MQTT_PASSWORD` | MQTT authentication password | (empty) |
| `MQTT_CLIENT_ID` | MQTT client identifier | `franklinwh_bridge` |
| `MQTT_DISCOVERY_PREFIX` | Home Assistant discovery prefix | `homeassistant` |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |

#### Command Line Examples

```bash
# Run in mock mode
MOCK_MODE=true python -m src.main

# Connect to different device
MODBUS_HOST=192.168.1.50 MODBUS_UNIT=3 ./run.sh

# Enable debug logging
LOG_LEVEL=DEBUG ./run.sh

# Use different MQTT broker
MQTT_HOST=mosquitto.local MQTT_PORT=1883 ./run.sh
```

### Method 2: Configuration File

The configuration file (`data/config.json`) persists your settings between restarts and provides the most comprehensive configuration options.

#### Full Configuration Example

```json
{
  "mock_mode": false,
  "modbus": {
    "host": "192.168.1.50",
    "port": 502,
    "unit_id": 2,
    "base_address": 40000,
    "timeout": 5.0,
    "retry_attempts": 3,
    "retry_delay": 1.0
  },
  "mqtt": {
    "host": "192.168.1.100",
    "port": 1883,
    "username": "",
    "password": "",
    "client_id": "franklinwh_bridge",
    "discovery_prefix": "homeassistant",
    "state_prefix": "franklinwh"
  },
  "theme": {
    "mode": "auto",
    "primary_color": "#3b82f6",
    "secondary_color": "#10b981",
    "accent_color": "#f59e0b",
    "background_color": "#ffffff",
    "surface_color": "#f3f4f6",
    "text_color": "#111827",
    "border_radius": 12,
    "shadow_intensity": "medium"
  },
  "widgets": {
    "battery_metrics": {
      "enabled": true,
      "position": 0,
      "color": "#10b981",
      "refresh_interval": 30,
      "expanded": true
    },
    "inverter_status": {
      "enabled": true,
      "position": 1,
      "color": "#3b82f6",
      "refresh_interval": 30,
      "expanded": true
    },
    "power_flow": {
      "enabled": true,
      "position": 2,
      "color": "#f59e0b",
      "refresh_interval": 30,
      "expanded": true
    }
  },
  "auto_refresh": true,
  "refresh_interval": 30,
  "log_level": "INFO",
  "log_retention_days": 7,
  "enabled_models": [1, 701, 702, 703, 704, 705, 706, 713, 714, 715],
  "last_updated": "2026-02-03T12:00:00"
}
```

#### Configuration Sections

##### `mock_mode` (boolean)

Enable simulated device for testing.

- `true` - Use mock device with simulated data
- `false` - Connect to real Modbus device

##### `modbus` (object)

Modbus TCP connection settings.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `host` | string | `192.168.0.110` | Device IP address |
| `port` | int | `502` | Modbus TCP port |
| `unit_id` | int | `2` | Device unit/slave ID (1-247) |
| `base_address` | int | `40000` | Starting register address |
| `timeout` | float | `5.0` | Connection timeout in seconds |
| `retry_attempts` | int | `3` | Number of connection retries |
| `retry_delay` | float | `1.0` | Delay between retries |

**Finding your device settings:**
- Check your router's DHCP client list for "FranklinWH"
- Default unit ID is usually `2`
- Port is almost always `502` (standard Modbus TCP)

##### `mqtt` (object)

MQTT broker settings for Home Assistant integration.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `host` | string | `192.168.0.109` | Broker IP/hostname |
| `port` | int | `1883` | Broker port (1883 or 8883 for TLS) |
| `username` | string | `""` | Authentication username |
| `password` | string | `""` | Authentication password |
| `client_id` | string | `franklinwh_bridge` | Unique client identifier |
| `discovery_prefix` | string | `homeassistant` | HA discovery topic prefix |
| `state_prefix` | string | `franklinwh` | State topic prefix |

**Home Assistant Setup:**
1. Install MQTT integration in HA
2. Install MQTT broker add-on (Mosquitto) or use external broker
3. Note the broker IP and port
4. Configure credentials if authentication is enabled

##### `theme` (object)

Web UI appearance settings.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | `auto` | Theme: `light`, `dark`, or `auto` |
| `primary_color` | string | `#3b82f6` | Main accent color (blue) |
| `secondary_color` | string | `#10b981` | Secondary color (green) |
| `accent_color` | string | `#f59e0b` | Accent/highlight color (amber) |
| `background_color` | string | `#ffffff` | Page background |
| `surface_color` | string | `#f3f4f6` | Card/widget background |
| `text_color` | string | `#111827` | Primary text color |
| `border_radius` | int | `12` | Corner rounding (pixels) |
| `shadow_intensity` | string | `medium` | Shadow depth: `none`, `low`, `medium`, `high` |

##### `widgets` (object)

Dashboard widget configuration.

Each widget has:
- `enabled` (boolean) - Show/hide widget
- `position` (int) - Display order
- `color` (string) - Widget accent color (hex)
- `refresh_interval` (int) - Data refresh in seconds
- `expanded` (boolean) - Default expanded state

Available widgets: `battery_metrics`, `inverter_status`, `power_flow`, `energy_stats`, `system_health`, `control_panel`

##### Other Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `auto_refresh` | boolean | `true` | Automatically refresh dashboard |
| `refresh_interval` | int | `30` | Seconds between auto-refresh |
| `log_level` | string | `INFO` | Logging verbosity |
| `log_retention_days` | int | `7` | Days to keep log files |
| `enabled_models` | list | `[1,701...715]` | SunSpec models to read |

### Method 3: Web UI Settings

The web interface provides an easy way to modify settings without editing files.

1. Open `http://localhost:8080` in your browser
2. Click the **⚙️ Settings** icon (top right)
3. Modify settings in each section
4. Click **Save**

**Note:** Settings changed via the web UI are saved to `data/config.json` and persist after restart.

### Runtime MQTT Control

You can enable/disable MQTT at any time without restarting the application:

```bash
# Check MQTT status
curl http://localhost:8080/api/mqtt/status

# Enable MQTT (starts auto-connecting in background)
curl -X POST http://localhost:8080/api/mqtt/enable

# Disable MQTT (stops all MQTT activity)
curl -X POST http://localhost:8080/api/mqtt/disable

# Restart MQTT connection
curl -X POST http://localhost:8080/api/mqtt/restart

# Check overall health (includes MQTT status)
curl http://localhost:8080/api/health
```

Example health response:
```json
{
  "status": "ok",
  "modbus_connected": true,
  "mqtt": {
    "enabled": true,
    "status": "online",
    "connected": true,
    "broker": "192.168.1.100:1883"
  }
}
```

---

## 🐳 Docker Configuration

When running in Docker, use environment variables:

```yaml
version: '3.8'
services:
  franklinwh:
    image: franklinwh-ha:latest
    environment:
      - MOCK_MODE=false
      - MODBUS_HOST=192.168.1.50
      - MODBUS_PORT=502
      - MODBUS_UNIT=2
      - MQTT_HOST=192.168.1.100
      - MQTT_PORT=1883
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/data
    ports:
      - "8080:8080"
```

Or use an `.env` file with docker-compose:

```bash
# .env file
MOCK_MODE=false
MODBUS_HOST=192.168.1.50
MQTT_HOST=192.168.1.100
```

```yaml
# docker-compose.yml
services:
  franklinwh:
    image: franklinwh-ha:latest
    env_file: .env
    volumes:
      - ./data:/data
    ports:
      - "8080:8080"
```

---

## 🔧 Troubleshooting

### Configuration Not Loading

1. Check file location: `data/config.json` (relative to project root)
2. Validate JSON syntax: `python3 -m json.tool data/config.json`
3. Check file permissions
4. Review startup logs for errors

### Environment Variables Not Working

1. Verify variable names match exactly (case-sensitive)
2. Check that `.env` file is in project root
3. Export variables explicitly: `export MODBUS_HOST=192.168.1.50`
4. Ensure no spaces around `=` in `.env` file

### Mock Mode Not Activating

1. Check config: `cat data/config.json | grep mock_mode`
2. Try environment variable: `MOCK_MODE=true ./run.sh`
3. Verify the mock module exists: `ls src/mock_modbus_client.py`

### Cannot Connect to Device

1. **Verify network connectivity:**
   ```bash
   ping 192.168.1.50  # Replace with your device IP
   telnet 192.168.1.50 502
   ```

2. **Check unit ID:**
   - Try scanning with `python3 -m src.modbus_scanner` (if available)
   - Common IDs: 1, 2, 3

3. **Verify firewall rules:**
   ```bash
   # Allow Modbus port
   sudo ufw allow 502/tcp
   ```

4. **Enable debug logging:**
   ```bash
   LOG_LEVEL=DEBUG ./run.sh
   ```

---

## 📋 Configuration Checklist

Before running the application, ensure:

- [ ] If using live mode: Device IP is correct and reachable
- [ ] If using live mode: Unit ID matches device configuration
- [ ] If using MQTT: Broker is running and accessible
- [ ] Configuration file is valid JSON (or use setup wizard)
- [ ] Data directory exists and is writable
- [ ] Required Python packages installed

---

## 📝 Example Configurations

### Minimal Mock Mode

```json
{
  "mock_mode": true,
  "modbus": { "host": "mock://localhost", "port": 502, "unit_id": 2 },
  "mqtt": { "host": "localhost", "port": 1883 }
}
```

### Production Live Mode

```json
{
  "mock_mode": false,
  "modbus": {
    "host": "192.168.1.10",
    "port": 502,
    "unit_id": 2,
    "timeout": 10.0,
    "retry_attempts": 5
  },
  "mqtt": {
    "host": "192.168.1.5",
    "port": 1883,
    "username": "franklinwh",
    "password": "secure_password",
    "client_id": "franklinwh_production"
  },
  "log_level": "WARNING",
  "auto_refresh": true,
  "refresh_interval": 60
}
```

---

For more help, see:
- [README.md](readme.md) - Project overview
- [INSTALLATION.md](installation.md) - Installation instructions
- [FUNCTIONALITY.md](functionality.md) - Feature documentation
