# FranklinWH Battery Manager - Feature Documentation

> **Last Updated:** February 2026  
> **Version:** 1.2.0

---

## Table of Contents

1. [Quick Overview](#quick-overview)
2. [Dashboard](#dashboard)
3. [Topology Management](#topology-management)
4. [MQTT Administration](#mqtt-administration)
5. [Configuration System](#configuration-system)
6. [SunSpec2 Integration](#sunspec2-integration)
7. [API Reference](#api-reference)

---

## Quick Overview

The FranklinWH Battery Manager is a comprehensive web-based management interface for FranklinWH battery systems with Home Assistant integration.

### Key Features

| Feature | Status | Description |
|---------|--------|-------------|
| Real-time Monitoring | ✅ | SOC, SOH, power flow, temperature |
| Web Dashboard | ✅ | Modern responsive UI with dark/light themes |
| Topology Management | ✅ | Multi-device aGate discovery and management |
| MQTT Bridge | ✅ | Home Assistant auto-discovery |
| Mock Mode | ✅ | Test without hardware |
| SunSpec2 Support | ✅ | Models 701-706, 713-715 |

---

## Dashboard

### Main View (`/`)

The dashboard provides at-a-glance monitoring of your FranklinWH battery system.

#### Status Cards

| Card | Data Source | Description |
|------|-------------|-------------|
| **State of Charge** | Model 713 (SoC) | Current battery percentage with visual bar |
| **Power** | Model 701 (W) | Current power flow (+ charging, - discharging) |
| **State of Health** | Model 713 (SoH) | Battery health percentage |
| **Operating Mode** | Register 15507 | Current mode (Backup, Self-Consumption, TOU) |

#### Widgets

| Widget | Source | Metrics |
|--------|--------|---------|
| Battery Metrics | Models 713/714 | Rated/available energy, temperature, status |
| Inverter Status | Model 701 | Voltage, current, frequency, power factor |
| Solar PV | Model 502 | Output power, lifetime energy |
| Home Loads | Ext 15500+ | Home consumption, PV output |
| Power Capacity | Model 703 | Max charge/discharge limits |
| Reserve Settings | Ext 15508/15509 | Self-consumption and TOU reserves |
| Power Flow Chart | Real-time | Historical power visualization |

#### Controls Tab

- **Operating Mode Selection**: Switch between modes
- **Reserve SOC Sliders**: Adjust backup reserves
- **Power Limits**: Set charge/discharge limits

---

## Topology Management

### Page: `/topology`

Manage multiple FranklinWH aGate devices on your network.

#### Features

| Feature | Description |
|---------|-------------|
| **Device Discovery** | Automatically detect aGate devices |
| **Manual Addition** | Add devices by IP/hostname |
| **Connection Status** | Real-time online/offline indicators |
| **Auto-Discovery** | Fetches serial, model, firmware on connect |

#### Device Information Stored

```json
{
  "id": "default",
  "name": "Garage aGate",
  "host": "192.168.0.110",
  "port": 502,
  "unit_id": 2,
  "serial_number": "FWH123456789",
  "model": "aPower",
  "manufacturer": "FranklinWH",
  "firmware_version": "1.2.3",
  "last_connected": "2026-02-03T14:30:00",
  "enabled": true
}
```

#### Adding a Device

1. Navigate to **Topology** page
2. Fill in device details:
   - **Name**: Friendly display name
   - **Host**: IP address or hostname
   - **Port**: Usually 502 (Modbus TCP)
   - **Unit ID**: Device address (usually 1-5)
3. Click **Add Device**
4. System attempts connection and auto-discovers device info

> **Note:** Devices are saved even if offline. Connection retries automatically.

---

## MQTT Administration

### Page: `/mqtt-admin`

Full-featured MQTT configuration for Home Assistant integration.

### Connection Settings

| Setting | Default | Description |
|---------|---------|-------------|
| **Enable MQTT** | false | Master switch for MQTT bridge |
| **Broker Host** | localhost | MQTT broker IP/hostname |
| **Port** | 1883 | Broker port (1883 or 8883 for TLS) |
| **QoS** | 0 | Quality of Service level (0/1/2) |
| **Client ID** | franklinwh_bridge | Must be unique across clients |

### Authentication

| Setting | Description |
|---------|-------------|
| **Username** | MQTT broker username (optional) |
| **Password** | MQTT broker password (optional) |

### Home Assistant Discovery

| Setting | Default | Description |
|---------|---------|-------------|
| **Discovery Prefix** | homeassistant | HA MQTT discovery topic prefix |
| **State Topic Prefix** | franklinwh | Base topic for state messages |
| **Device Name** | FranklinWH Battery | Display name in HA |
| **Unique ID Prefix** | franklinwh | Prefix for entity unique IDs |
| **Retain Discovery** | true | Retain discovery messages |

### Entity Selection

Choose which sensors and controls to publish:

| Entity Type | Description |
|-------------|-------------|
| **Battery Sensors** | SOC, SOH, temperature, cycles |
| **Inverter Sensors** | Power, voltage, current, frequency |
| **Solar PV Sensors** | Output power, energy produced |
| **Home Load Sensors** | Home consumption, PV output |
| **Capacity Info** | Max charge/discharge limits |
| **Controls** | Mode select, reserve SOC inputs |

### Actions

| Action | Description |
|--------|-------------|
| **Test Connection** | Verify broker connectivity without saving |
| **Restart MQTT** | Disable and re-enable MQTT bridge |
| **Republish Discovery** | Re-send all discovery messages to HA |

### MQTT Topic Structure

#### Discovery Topics
```
homeassistant/sensor/franklinwh_soc/config
homeassistant/sensor/franklinwh_power/config
homeassistant/select/franklinwh_mode/config
```

#### State Topics
```
franklinwh/battery/soc
franklinwh/inverter/power
franklinwh/mode
```

#### Command Topics
```
franklinwh/mode/set
franklinwh/reserve_soc/set
```

### Unique ID Generation

Entity unique IDs use the format:
```
{unique_id_prefix}_{device_serial}_{entity_name}
```

Example:
```
franklinwh_FWH123456789_soc
franklinwh_FWH123456789_power
```

This ensures:
- No conflicts with existing devices
- Multiple aGate support
- Stable entity IDs across restarts

---

## Configuration System

### File Locations

| Environment | Path |
|-------------|------|
| Standalone | `./data/config.json` |
| Docker | `/data/config.json` (mounted volume) |

### Configuration Structure

```json
{
  "modbus": {
    "host": "192.168.0.110",
    "port": 502,
    "unit_id": 2,
    "base_address": 40000,
    "timeout": 5.0
  },
  "devices": {
    "default": {
      "id": "default",
      "name": "Primary aGate",
      "host": "192.168.0.110",
      "port": 502,
      "unit_id": 2,
      "serial_number": "FWH123456789",
      "model": "aPower",
      "manufacturer": "FranklinWH"
    }
  },
  "mqtt": {
    "enabled": true,
    "host": "192.168.0.109",
    "port": 1883,
    "username": "",
    "password": "",
    "client_id": "franklinwh_bridge",
    "discovery_prefix": "homeassistant",
    "state_prefix": "franklinwh",
    "ha_device_name": "FranklinWH Battery",
    "unique_id_prefix": "franklinwh",
    "publish_battery": true,
    "publish_inverter": true,
    "publish_solar": true,
    "publish_home_loads": true,
    "publish_capacity": true,
    "publish_controls": true,
    "retain_discovery": true,
    "qos": 0
  },
  "theme": {
    "mode": "auto",
    "primary_color": "#3b82f6",
    "secondary_color": "#10b981",
    "accent_color": "#f59e0b"
  },
  "widgets": { ... }
}
```

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MOCK_MODE` | Enable mock device | `true` |
| `MODBUS_HOST` | Device IP | `192.168.0.110` |
| `MODBUS_PORT` | Modbus port | `502` |
| `MODBUS_UNIT` | Device unit ID | `2` |
| `MQTT_HOST` | MQTT broker IP | `192.168.0.109` |
| `MQTT_PORT` | MQTT port | `1883` |
| `LOG_LEVEL` | Logging level | `DEBUG` |

---

## SunSpec2 Integration

### Supported Models

| Model | Description | Read | Write |
|-------|-------------|------|-------|
| 1 | Common (device info) | ✅ | ❌ |
| 501 | Solar PV (Inverter) | ✅ | ❌ |
| 502 | Solar PV (Module) | ✅ | ❌ |
| 701 | DER AC Measurements | ✅ | ❌ |
| 703 | DER Capacity | ✅ | ❌ |
| 704 | DER Enter Service | ✅ | ✅ |
| 705 | DER AC Controls | ✅ | ✅ |
| 713 | Storage Capacity | ✅ | ❌ |
| 714 | Storage Status | ✅ | ❌ |
| 715 | Storage Controls | ✅ | ✅ |

### Scale Factors

SunSpec2 uses power-of-10 scale factors:

```python
# Example: SoC = 2000, Pct_SF = -2
actual_soc = 2000 * (10 ** -2)  # = 20.0%
```

| Scale Factor | Typical Value | Usage |
|--------------|---------------|-------|
| `Pct_SF` | -2 | Percentages (hundredths) |
| `W_SF` | 0 to -3 | Watts |
| `V_SF` | -1 | Volts (tenths) |
| `A_SF` | -3 | Amps (thousandths) |
| `Tmp_SF` | -1 | Temperature (tenths °C) |

### FranklinWH Extension Registers

Non-SunSpec registers specific to FranklinWH:

| Register | Type | Description |
|----------|------|-------------|
| 15011 | uint16 | Raw SOC value |
| 15507 | uint16 | Operating mode (1=Backup, 2=Self-Consumption, 3=TOU) |
| 15508 |uint16 | Reserve SOC (Self-Consumption) |
| 15509 | uint16 | Reserve SOC (TOU) |
| 15036 | uint16 | Raw SOH value |
| 15040 | int16 | Reserve SOC 2 (TOU) |
| 15502 | uint16 | PV output power (W) |
| 15506 | uint16 | Home loads (W) |

### Operating Modes

| Value | Mode | Description |
|-------|------|-------------|
| 0 | Standby | System idle |
| 1 | Normal | Automatic operation |
| 2 | Backup Reserve | Maintain full charge |
| 3 | Self-Consumption | Maximize solar usage |
| 4 | Time-of-Use | Rate-based scheduling |

---

## API Reference

### Dashboard Data

```
GET /api/data
```

Returns complete dataset including battery, inverter, solar, and extension data.

### Extensions

```
GET /api/extensions
```

Returns FranklinWH-specific extension register values with metadata.

### Topology

```
GET /api/topology
POST /api/topology
DELETE /api/topology/{device_id}
```

Manage aGate devices in the network topology.

### MQTT Control

```
GET /api/mqtt/status
POST /api/mqtt/enable
POST /api/mqtt/disable
POST /api/mqtt/restart
POST /api/mqtt/test
POST /api/mqtt/republish
```

### Settings

```
GET /api/settings
POST /api/settings
```

### Health Check

```
GET /api/health
```

Returns system status including:
- `mock_mode`: Boolean
- `modbus_connected`: Boolean
- `mqtt`: Connection status object

---

## Troubleshooting

### MQTT Connection Issues

1. Check broker is running: `telnet <broker_ip> 1883`
2. Verify credentials in MQTT Admin
3. Check firewall rules
4. Use "Test Connection" button before saving

### Device Not Connecting

1. Verify IP address with `ping <device_ip>`
2. Check unit ID (try 1-5)
3. Ensure port 502 is not blocked
4. Check device is powered on

### Missing Data

1. Check `/api/health` for connection status
2. Verify SunSpec models in logs
3. Check raw registers at `/api/raw_registers`

---

## Development Notes

### Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12, FastAPI |
| Frontend | Alpine.js, Tailwind CSS, Chart.js |
| Modbus | pymodbus, sunspec2 |
| MQTT | asyncio-mqtt |
| Templates | Jinja2 |

### Project Structure

```
├── src/
│   ├── main.py                 # Application entry point
│   ├── modbus_client.py        # SunSpec2 client
│   ├── modbus_client_franklinwh.py  # Extension registers
│   ├── mqtt_handler.py         # HA MQTT bridge
│   ├── connection_manager.py   # Multi-device management
│   ├── config_manager.py       # Settings persistence
│   └── web_server.py           # FastAPI routes
├── templates/
│   ├── base.html               # Base layout
│   ├── dashboard.html          # Main dashboard
│   ├── topology.html           # Device topology
│   └── mqtt_admin.html         # MQTT configuration
├── static/
│   ├── js/app.js               # Frontend logic
│   └── css/style.css           # Custom styles
└── data/
    └── config.json             # User configuration
```

---

## Changelog

### v1.2.0 (2026-02-03)

**Added:**
- MQTT Administration page with full configuration
- Device auto-discovery (serial, model, firmware)
- Entity selection (choose what to publish to HA)
- Unique ID prefix configuration
- Connection test button
- Topology management page

**Fixed:**
- LIVE/MOCK badge timing issues
- Reserve SOC slider sync
- Device persistence in topology
- UITheme → ThemeConfig typo

### v1.1.0

**Added:**
- SunSpec2 model support
- MQTT non-blocking connection
- WebSocket real-time updates
- Mock mode for testing

### v1.0.0

- Initial release
- Basic Modbus TCP support
- Web dashboard
- Home Assistant integration

---

## License

MIT License - See `LICENSE` file for details.

---

## Support

For issues, feature requests, or contributions:
- GitHub Issues: [github.com/yourusername/franklinwh-ha](https://github.com/yourusername/franklinwh-ha)
- Documentation: This file

---

*Built with ❤️ for the FranklinWH community*
