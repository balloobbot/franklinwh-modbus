# FranklinWH Battery Manager

[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://docker.com)
[![Home Assistant](https://img.shields.io/badge/home%20assistant-add--on-green.svg)](https://home-assistant.io)
[![Modbus TCP](https://img.shields.io/badge/modbus-tcp-orange.svg)](https://modbus.org)
[![SunSpec](https://img.shields.io/badge/sunspec-2.0-yellow.svg)](https://sunspec.org)

A comprehensive, web-based management interface for FranklinWH battery systems with Home Assistant integration via MQTT.

![Dashboard Mockup](./screenshots/dashboard-preview.png)

## Quick Links

- [📋 Features & Functionality](./FUNCTIONALITY.md)
- [🚀 Installation Guide](./INSTALLATION.md)
- [📖 User Guide](./USER_GUIDE.md)

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

