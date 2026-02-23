# FranklinWH Battery Manager

[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://docker.com)
[![Home Assistant](https://img.shields.io/badge/home%20assistant-add--on-green.svg)](https://home-assistant.io)
[![Modbus TCP](https://img.shields.io/badge/modbus-tcp-orange.svg)](https://modbus.org)
[![SunSpec](https://img.shields.io/badge/sunspec-2.0-yellow.svg)](https://sunspec.org)
[![Version](https://img.shields.io/badge/version-1.3.0-blue.svg)]()

A comprehensive battery management system for FranklinWH with **alarm monitoring**, **conflict detection**, and **Cloud API coordination**.

## What's New in v1.3.0

- 🚨 **Alarm Monitoring** - System, DC port, battery, and solar alarm detection
- ⚡ **Conflict Detection** - Prevents fighting with aGate Cloud API control
- 🔄 **Auto-Reconnection** - Survives connection drops automatically
- 🎯 **Target Validation** - Exits if SoC target already reached
- 📊 **SOC Summary** - Single-line status with ETA calculation
- ✅ **Vendor-Matching** - Self-consumption mode charges at full 5000W like vendor app

![Dashboard Mockup](./screenshots/dashboard-preview.png)

## Quick Links

- [📋 Features & Functionality](./FUNCTIONALITY.md)
- [🚀 Installation Guide](./INSTALLATION.md)
- [📖 CLI Options Reference](./CLI_OPTIONS.md)
- [🧪 Test Results (Feb 22, 2026)](./TEST_RESULTS_2026-02-22.md)

## Quick Start - Command Line

```bash
# Check system health and detect conflicts
python3 franklinwh_cli.py -i 192.168.0.110 --healthcheck

# View current status including alarms
python3 franklinwh_cli.py -i 192.168.0.110 --status

# Self-consumption mode (charges at 5000W like vendor app)
python3 franklinwh_cli.py -i 192.168.0.110 --mode self_consumption --target-soc 90

# Emergency backup mode
python3 franklinwh_cli.py -i 192.168.0.110 --mode emergency_backup --target-soc 95

# Manual control (charge at 3000W for 1 hour)
python3 franklinwh_cli.py -i 192.168.0.110 --mode manual --power 3000 --duration 3600

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
| Operating Mode | 15016 | RW | 0=Standby, 1=Normal, 2=Backup, 3=Self-Consume, 4=TOU |
| Reserve SOC | 15017 | RW | Primary reserve percentage (0-100) |
| Reserve SOC 2 | 15040 | RW | Secondary reserve (-128 to 127) |

## Architecture

