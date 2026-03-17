# franklinwh-modbus

[![Modbus TCP](https://img.shields.io/badge/modbus-tcp-orange.svg)](https://modbus.org)
[![SunSpec](https://img.shields.io/badge/sunspec-2.0-yellow.svg)](https://sunspec.org)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)

A Python library for controlling FranklinWH battery storage systems via Modbus TCP, optimized for the aGate gateway with SunSpec model support and FranklinWH extension registers.

> **Note:** This is the Modbus TCP library (`pip install franklinwh-modbus`).  
> For the Cloud API, see [franklinwh-python](https://pypi.org/project/franklinwh-python/).  
> Python import: `from franklinwh_modbus import FranklinWHController`

> **Status:** Core library under active development, targeting PyPi publication.

## Quick Links

- [📖 Library & CLI Usage Guide](./USAGE_GUIDE.md)
- [📚 Documentation](./docs/README.md)
- [🧪 Hardware Test Guide](./docs/HARDWARE_TEST_GUIDE.md)
- [📝 Changelog](./CHANGELOG.md)

## ⚠️ Important — Before You Start

### Network Requirements

- **Fixed IP address required** — the aGate must have a static/reserved IP on your LAN.
- **LAN Ethernet strongly preferred** — wired connection for reliable Modbus TCP control.
- ⚠️ **WiFi is highly undesirable** — latency and packet loss can cause missed keep-alive cycles, leaving the aGate stuck in VPP Mode.

### Extension Register Access

**Read operations always work** — battery status, grid power, solar production (proximal and remote), system alarms, and all SunSpec model data are readable by any Modbus TCP client without provisioning. The CLI `--status`, `--healthcheck`, and TUI monitor all work out of the box.

**Write access to extension registers (15507–15509: OnGridMode, SelfReserve, TOUReserve) requires "SPAN Modbus" unlock in FranklinWH installer settings.**

**Already qualified:** Owners with **SPAN Panels** or **Lumin Panels** connected to the aGate via Modbus TCP — these systems already have full write access enabled.

**Not yet provisioned?** Contact FranklinWH Support to request Modbus write access for your aGate. Without provisioning, extension registers are read-only (writes fail silently). **Note:** Standard SunSpec M704 power commands (charge/discharge) work regardless of SPAN unlock status.

### Avoiding Control Conflicts

> [!CAUTION]
> **Do not use the FranklinWH mobile app** to send charge/discharge commands or schedule events while this library is actively controlling the aGate. Conflicting commands will cause unpredictable behavior.

- **Recommended:** Set your aGate to **Emergency Backup** or **Self-Consumption** mode via the mobile app *before* starting library control — this reduces the likelihood of conflicting Cloud API activity.
- **VPP Mode indicator:** While any remote client API is actively controlling the aGate — Modbus TCP (this library) or the FranklinWH Cloud API (VPP providers) — the mobile app displays **"VPP Mode"**. This is normal and confirms direct control is active. See [VPP Mode Visual Reference](./docs/VPP_MODE_REFERENCE.md) for mobile app screenshots.
- **On failure or loss of connectivity:** Always release control using `--stop`:

```bash
# Via CLI
python3 franklinwh_cli.py -i YOUR_AGATE_IP --stop

# Via library
ctrl.reset_control_state()
ctrl.disconnect()
```

> [!WARNING]
> If control is not released, the aGate **persists the last command indefinitely**. Hardware heartbeat (`ControllerHb`) and reversion timer (`WSetRvrtTms`) do not work on FranklinWH — use `--revert N` or `send_command(cmd, duration_s=N)` for software-side auto-revert.

## Installation

```bash
git clone git@github.com:david2069/franklinwh-modbus.git
cd franklinwh-modbus
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
```

## Library Usage

```python
from franklinwh_modbus import FranklinWHController, BatteryCommand

# Connect to aGate
ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

# Read battery status (battery_state derived from DC power, not unreliable M713.Sta)
status = ctrl.read_battery_status()
print(f"SoC: {status['soc']:.1f}%  State: {status['battery_state']}")

# Charge at 3000W with 1-hour software timeout (auto-reverts to cloud control)
cmd = BatteryCommand(power_watts=3000, mode='charge')
ctrl.send_command(cmd, duration_s=3600)

# Release control (or let timeout handle it)
ctrl.reset_control_state()
ctrl.disconnect()
```

## CLI Quick Start

```bash
# System status
python3 franklinwh_cli.py -i YOUR_AGATE_IP --status

# Health check with conflict detection
python3 franklinwh_cli.py -i YOUR_AGATE_IP --healthcheck

# Charge at 3000W with auto-revert after 2 hours
python3 franklinwh_cli.py -i YOUR_AGATE_IP --charge 3000 --revert 7200

# Self-consumption mode
python3 franklinwh_cli.py -i YOUR_AGATE_IP --mode self_consumption --target-soc 90

# Terminal UI monitor (requires `rich`)
python3 franklinwh_cli.py -i YOUR_AGATE_IP --monitor

# Release control
python3 franklinwh_cli.py -i YOUR_AGATE_IP --stop
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
| **Auto-Revert** | Software timeout (hardware reversion non-functional on FranklinWH) |

## Project Structure

```
franklinwh-modbus/
├── src/franklinwh_modbus/          # Core library (the package)
│   ├── controller.py        # FranklinWHController — Modbus interface
│   ├── modes.py             # VirtualModeController — control modes
│   ├── types.py             # BatteryCommand, VirtualMode, enums
│   ├── schedule.py          # TOUSchedule — time-of-use
│   ├── monitor.py           # CLIMonitor — TUI (optional, needs rich)
│   └── constants.py         # Register addresses, limits
├── tools/franklinwh_cli.py   # CLI tool (consumes the library)
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

> **Note:** aGate uses base address **1** (not standard 40000). Unit ID **1** or **2** both work (DA=1).

| Model | Description | Read | Write | Notes |
|-------|-------------|------|-------|-------|
| 1 | Common | ✅ | ❌ | |
| 701 | DER AC Measurements | ✅ | ❌ | |
| 702 | DER DC Measurements | ✅ | ❌ | |
| 703 | DER Capacity | ✅ | ❌ | |
| 704 | DER AC Battery Control | ✅ | ✅ | WSetPct/WSetEna confirmed working |
| 705 | DER AC Controls | ✅ | ⚠️ | Untested |
| 706 | DER Volt/Var/Watt | ✅ | ⚠️ | Untested |
| 713 | DER Storage Capacity | ✅ | ❌ | ⚠️ Sta always 0 (unreliable) |
| 714 | DER Storage Status | ✅ | ❌ | DCW used for battery state derivation |
| 715 | DER Storage Controls | ✅ | ❌ | LocRemCtl read-only, heartbeat non-functional |

## FranklinWH Extension Registers

| Register | Address | Access | Description |
|----------|---------|--------|-------------|
| OnGridMode | 15507 | R (RW with SPAN) | 0=Backup, 1=TOU, 2=Self-Consumption, 3=Manual |
| Self Reserve SOC | 15508 | R (RW with SPAN) | Self-consumption reserve percentage (0-100) |
| TOU Reserve SOC | 15509 | R (RW with SPAN) | ⚠️ Known defect: always mirrors 15508 |

See [FRANKLINWH_SUNSPEC_QUIRKS.md](./docs/FRANKLINWH_SUNSPEC_QUIRKS.md) for all documented hardware quirks.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup and guidelines.

## License

MIT License — see [LICENSE](./LICENSE) for details.

## Support

- 🐛 [Report a Bug](https://github.com/david2069/franklinwh-modbus/issues/new?template=bug_report.md)
- 💡 [Request a Feature](https://github.com/david2069/franklinwh-modbus/issues/new?template=feature_request.md)
- 📖 [Documentation](./docs/README.md)
