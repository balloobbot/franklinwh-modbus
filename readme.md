# FranklinWH Battery Manager

[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://docker.com)
[![Home Assistant](https://img.shields.io/badge/home%20assistant-add--on-green.svg)](https://home-assistant.io)
[![Modbus TCP](https://img.shields.io/badge/modbus-tcp-orange.svg)](https://modbus.org)
[![SunSpec](https://img.shields.io/badge/sunspec-2.0-yellow.svg)](https://sunspec.org)
[![Version](https://img.shields.io/badge/version-1.3.0-blue.svg)]()

## Quick Links

- [📚 Documentation](./docs/README.md)
- [📖 CLI & Library Usage Guide](./USAGE_GUIDE.md)
- [🧪 Hardware Test Guide](./docs/HARDWARE_TEST_GUIDE.md)

## Quick Start - Command Line

```bash
# Check system health and detect conflicts
python3 franklinwh_cli.py -i 192.168.0.110 --healthcheck

# View current status including alarms
python3 franklinwh_cli.py -i 192.168.0.110 --status

# Detailed alarm check
python3 franklinwh_cli.py -i 192.168.0.110 --check-alarms

# Self-consumption mode (charges at 5000W like vendor app)
python3 franklinwh_cli.py -i 192.168.0.110 --mode self_consumption --target-soc 90

# Emergency backup mode
python3 franklinwh_cli.py -i 192.168.0.110 --mode emergency_backup --target-soc 95

# Manual control (charge at 3000W for 1 hour)
python3 franklinwh_cli.py -i 192.168.0.110 --mode manual --power 3000 --duration 3600

# Charge with auto-revert (safety timer - releases control after 2 hours)
python3 franklinwh_cli.py -i 192.168.0.110 --charge 3000 --revert 7200

# Stop control and release aGate
python3 franklinwh_cli.py -i 192.168.0.110 --stop

# Clear alarms after resolving faults
python3 franklinwh_cli.py -i 192.168.0.110 --clear-alarms
```

### Conflict Prevention

The CLI automatically detects conflicts with aGate Cloud API:

```
🚨 CONFLICTS DETECTED - aGate is actively controlling:
   • aGate Self-Consumption actively CHARGING at 5000W

⚠️  Use --reset-on-start to force takeover
⚠️  Or change aGate mode in vendor app first
⚠️  Exiting to avoid fighting with aGate control!
```

Use `--reset-on-start` only when you're sure you want to override Cloud API control.

## Overview

FranklinWH Battery Manager provides real-time monitoring and control of FranklinWH battery storage systems using Modbus TCP communication. It bridges the gap between proprietary battery protocols and modern home automation platforms.

### Key Capabilities

| Feature | Description |
|---------|-------------|
| **Real-time Monitoring** | SOC, SOH, power flow, temperature, cycles |
| **Operating Modes** | Standby, Normal, Backup Reserve, Self-Consumption, Time-of-Use |
| **Reserve Management** | Configurable SOC reserves for backup power |
| **Power Control** | Set charge/discharge limits in kW, amps, or percentage |
| **Home Assistant** | Auto-discovery via MQTT with 50+ entities |
| **Web Interface** | Modern, responsive UI with dark/light themes |
| **Raw Register Access** | Explore non-standard FranklinWH extensions |
| **Docker/Add-on** | Run as container or Home Assistant add-on |
| **🚨 Alarm Monitoring** | System, DC port, battery, solar alarm detection |
| **⚡ Conflict Detection** | Prevents fighting with Cloud API/native modes |
| **🔄 Auto-Reconnection** | Survives connection drops with retry logic |
| **🎯 Target Validation** | Exits if target SoC already reached |
| **📊 SOC Summary** | Single-line status: `SoC: 36% | Target: 40% | ETA: +6min` |

## Supported Hardware

| Model | Status | Notes |
|-------|--------|-------|
| FranklinWH aPower | ✅ Full Support | All features |
| FranklinWH aGate | ✅ Full Support | Communication gateway |
| SunSpec Compliant Inverters | ⚠️ Partial | Basic monitoring only |

## SunSpec Model Support

| Model | Description | Read | Write |
|-------|-------------|------|-------|
| 1 | Common | ✅ | ❌ |
| 701 | DER AC Measurements | ✅ | ❌ |
| 702 | DER DC Measurements | ✅ | ❌ |
| 703 | DER Capacity | ✅ | ❌ |
| 704 | DER Enter Service | ✅ | ✅ |
| 705 | DER AC Controls | ✅ | ✅ |
| 706 | DER Volt/Var/Watt | ✅ | ✅ |
| 713 | DER Storage Capacity | ✅ | ❌ |
| 714 | DER Storage Status | ✅ | ❌ |
| 715 | DER Storage Controls | ✅ | ✅ |

## FranklinWH Extensions

| Register | Address | Access | Description |
|----------|---------|--------|-------------|
| OnGridMode | 15507 | RW | 0=Backup, 1=TOU, 2=Self-Consumption, 3=Manual |
| Self Reserve SOC | 15508 | RW | Self-consumption reserve percentage (0-100) |
| TOU Reserve SOC | 15509 | RW | Time-of-Use reserve percentage (0-100) |

## Architecture

See [ARCHITECTURE.md](./docs/ARCHITECTURE.md) for details on AC-coupled vs DC-coupled systems.
