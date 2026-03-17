# Tools

Command-line utilities for interacting with FranklinWH aGate systems.

## CLI & Control

| Tool | Description |
|------|-------------|
| **[franklinwh_cli.py](franklinwh_cli.py)** | Full-featured CLI — status, charge, discharge, monitor, healthcheck |
| [franklinwh_min_demo.py](franklinwh_min_demo.py) | Minimal demo — connect, read status, charge, stop |
| [franklinwh_control_standalone.py](franklinwh_control_standalone.py) | Standalone control (no pysunspec2 dependency) |

## Diagnostic Utilities

| Tool | Description |
|------|-------------|
| [modbus_sunspec2_reader.py](modbus_sunspec2_reader.py) | SunSpec register reader with value matching |
| [modbus_sunspec2_readwrite.py](modbus_sunspec2_readwrite.py) | Register read/write utility |
| [enum_alarms.py](enum_alarms.py) | Enumerate and decode system alarms |
| [modbus_scan_network.py](modbus_scan_network.py) | Scan LAN for Modbus TCP devices |
| [network_scanner.py](network_scanner.py) | Network device discovery |

## Quick Start

```bash
# System status
python3 tools/franklinwh_cli.py -i YOUR_AGATE_IP --status

# Charge at 2000W with 1-hour timeout
python3 tools/franklinwh_cli.py -i YOUR_AGATE_IP --charge 2000 --revert 3600

# Release control
python3 tools/franklinwh_cli.py -i YOUR_AGATE_IP --stop
```

See the [Usage Guide](../USAGE_GUIDE.md) for comprehensive documentation.
