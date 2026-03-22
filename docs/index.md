# FranklinWH Modbus

Unofficial Python library & CLI for controlling **FranklinWH** battery storage systems via Modbus TCP, optimized for the aGate gateway.

!!! note "Related Project"
    For the FranklinWH Cloud API (non-Modbus), see [franklinwh-cloud](https://david2069.github.io/franklinwh-cloud/).

## Features

- **Modbus TCP** — Direct register read/write via pymodbus + SunSpec 2.0
- **SunSpec Models** — Models 1, 701–706, 713–715
- **FranklinWH Extensions** — Registers 15507–15509 (OnGridMode, reserves)
- **CLI Tool** — `franklinwh_cli.py` with charge, discharge, standby, healthcheck, TUI monitor
- **Virtual Modes** — Self-Consumption, Emergency Backup, TOU, Peak Shave, Manual
- **Safety Controls** — SoC validation, alarm monitoring, conflict detection, auto-revert
- **Target SoC** — Charge/discharge to specific SoC with auto-stop

## Quick Start

```bash
git clone git@github.com:david2069/franklinwh-modbus.git
cd franklinwh-modbus
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
```

## CLI

```bash
CLI="python3 tools/franklinwh_cli.py -i YOUR_AGATE_IP"

$CLI --status                    # Compact status
$CLI --healthcheck               # System health check
$CLI --charge 3000               # Charge at 3000W
$CLI --discharge 2000            # Discharge at 2000W
$CLI --standby                   # Force battery idle
$CLI --charge 3000 --target-soc-auto 80 --loop  # Charge to 80%
$CLI --stop                      # Release control
$CLI --monitor                   # Interactive TUI dashboard
```

## Library

```python
from franklinwh_modbus import FranklinWHController, BatteryCommand

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

# Read battery status
status = ctrl.read_battery_status()
print(f"SoC: {status['soc']:.1f}%  State: {status['battery_state']}")

# Charge at 3000W with 1-hour auto-revert
cmd = BatteryCommand(power_watts=3000, mode='charge')
ctrl.send_command(cmd, duration_s=3600)

# Release control
ctrl.reset_control_state()
ctrl.disconnect()
```

## SunSpec Model Support

| Model | Description | Read | Write | Notes |
|-------|-------------|:----:|:-----:|-------|
| 1 | Common | ✅ | ❌ | |
| 701 | DER AC Measurements | ✅ | ❌ | DERMode: Grid Following, Grid Forming, PV Clipped |
| 702 | DER DC Measurements | ✅ | ❌ | |
| 703 | DER Capacity | ✅ | ❌ | |
| 704 | DER AC Battery Control | ✅ | ✅ | WSetPct/WSetEna confirmed working |
| 713 | DER Storage Capacity | ✅ | ❌ | ⚠️ Sta always 0 (unreliable) |
| 714 | DER Storage Status | ✅ | ❌ | DCW used for battery state derivation |
| 715 | DER Storage Controls | ✅ | ❌ | LocRemCtl read-only, heartbeat non-functional |

## Documentation

Explore the sidebar for detailed guides on:

- **[Modbus Guide](FRANKLINWH_MODBUS_GUIDE.md)** — Start here: definitive implementation guide
- **[CLI Command Reference](CLI_COMMAND_REFERENCE.md)** — All switches tested with live output
- **[SunSpec Quirks](FRANKLINWH_SUNSPEC_QUIRKS.md)** — Hardware-specific quirks and workarounds
- **[DER Control Reference](DER_CONTROL_REFERENCE.md)** — Complete M704/M715 register map
- **[Safety Controls](SAFETY_CONTROLS.md)** — 10 safety rules for development
