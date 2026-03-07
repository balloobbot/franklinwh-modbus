# franklinwh-modbus

[![Modbus TCP](https://img.shields.io/badge/modbus-tcp-orange.svg)](https://modbus.org)
[![SunSpec](https://img.shields.io/badge/sunspec-2.0-yellow.svg)](https://sunspec.org)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)

A Python library for controlling FranklinWH battery storage systems via Modbus TCP, optimized for the aGate gateway with SunSpec model support and FranklinWH extension registers.

> **Note:** This is the Modbus TCP library (`pip install franklinwh-modbus`).  
> For the Cloud API, see [franklinwh-python](https://pypi.org/project/franklinwh-python/).  
> Python import: `from franklinwh import FranklinWHController`

> **Status:** Core library under active development, targeting PyPi publication.

## Quick Links

- [📖 Library & CLI Usage Guide](./USAGE_GUIDE.md)
- [📚 Documentation](./docs/README.md)
- [🧪 Hardware Test Guide](./docs/HARDWARE_TEST_GUIDE.md)
- [🗺️ Phases & Roadmap](./PHASES_AND_ROADMAP.md)

## ⚠️ Important — Before You Start

### Extension Register Access

FranklinWH extension registers (15507–15509: OnGridMode, SelfReserve, TOUReserve) are **read/write-capable but require provisioning by FranklinWH Support** to enable write access.

**Already qualified:** Owners with **SPAN Panels** or **Lumin Panels** connected to the aGate via Modbus TCP — these systems already have full write access enabled.

**Not yet provisioned?** Contact FranklinWH Support to request Modbus write access for your aGate. Without provisioning, registers are read-only and control commands will fail silently.

### Avoiding Control Conflicts

> [!CAUTION]
> **Do not use the FranklinWH mobile app** to send charge/discharge commands or schedule events while this library is actively controlling the aGate. Conflicting commands will cause unpredictable behavior.

- **Recommended:** Set your aGate to **Emergency Backup** or **Self-Consumption** mode via the mobile app *before* starting library control — this reduces the likelihood of conflicting Cloud API activity.
- **VPP Mode indicator:** While this library is actively controlling or polling the aGate, the FranklinWH mobile app will display the operating mode as **"VPP Mode"** (instead of Self-Consumption, Time-of-Use, or Emergency Backup). This is normal and confirms direct Modbus control is active.
- **On failure or loss of connectivity:** Always release control using `--stop`:

```bash
# Via CLI
python3 franklinwh_cli.py -i 192.168.0.110 --stop

# Via library
ctrl.reset_control_state()
ctrl.disconnect()
```

If control is not released, the aGate may remain in VPP Mode until the Modbus keep-alive times out (typically 60–120 seconds).

## Installation

```bash
git clone git@github.com:david2069/franklinwh-modbus.git
cd franklinwh-modbus
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
```

## Library Usage

```python
from franklinwh import FranklinWHController, VirtualModeController, VirtualMode

# Connect to aGate
ctrl = FranklinWHController('192.168.0.110')
ctrl.connect()

# Read battery status
status = ctrl.read_battery_status()
print(f"SoC: {status['soc']:.1f}%")

# Charge at 3000W
from franklinwh import BatteryCommand
cmd = BatteryCommand(power_watts=3000)
ctrl.send_command(cmd)

# Release control
ctrl.reset_control_state()
ctrl.disconnect()
```

## CLI Quick Start

```bash
# System status
python3 franklinwh_cli.py -i 192.168.0.110 --status

# Health check with conflict detection
python3 franklinwh_cli.py -i 192.168.0.110 --healthcheck

# Charge at 3000W with auto-revert after 2 hours
python3 franklinwh_cli.py -i 192.168.0.110 --charge 3000 --revert 7200

# Self-consumption mode
python3 franklinwh_cli.py -i 192.168.0.110 --mode self_consumption --target-soc 90

# Terminal UI monitor (requires `rich`)
python3 franklinwh_cli.py -i 192.168.0.110 --monitor

# Release control
python3 franklinwh_cli.py -i 192.168.0.110 --stop
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Modbus TCP** | Direct register read/write via pymodbus |
| **SunSpec Models** | Models 1, 701-706, 713-715 |
| **FranklinWH Extensions** | Registers 15507-15509 (OnGridMode, reserves) |
| **Virtual Modes** | Self-Consumption, Emergency Backup, TOU, Peak Shave, Manual |
| **Conflict Detection** | Detects aGate Cloud API activity before taking control |
| **SoC Safety** | Reserve validation, target checking, safety margins |
| **Alarm Monitoring** | System, DC port, battery, solar alarms |
| **Auto-Revert** | Safety timer releases control automatically |

## Project Structure

```
franklinwh-modbus/
├── src/franklinwh/          # Core library (the package)
│   ├── controller.py        # FranklinWHController — Modbus interface
│   ├── modes.py             # VirtualModeController — control modes
│   ├── types.py             # BatteryCommand, VirtualMode, enums
│   ├── schedule.py          # TOUSchedule — time-of-use
│   ├── monitor.py           # CLIMonitor — TUI (optional, needs rich)
│   └── constants.py         # Register addresses, limits
├── franklinwh_cli.py        # CLI tool (consumes the library)
├── tests/                   # Unit + integration + hardware tests
├── docs/                    # Current documentation
├── tools/                   # Utility scripts
├── schedules/               # TOU schedule definitions
└── archive/                 # Historical docs, deprecated code, web app
```

## Supported Hardware

| Model | Status | Notes |
|-------|--------|-------|
| FranklinWH aPower | ✅ Full Support | Battery storage |
| FranklinWH aGate | ✅ Full Support | Communication gateway |

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

## FranklinWH Extension Registers

| Register | Address | Access | Description |
|----------|---------|--------|-------------|
| OnGridMode | 15507 | RW | 0=Backup, 1=TOU, 2=Self-Consumption, 3=Manual |
| Self Reserve SOC | 15508 | RW | Self-consumption reserve percentage (0-100) |
| TOU Reserve SOC | 15509 | RW | Time-of-Use reserve percentage (0-100) |

## License

See [LICENSE](./LICENSE).
