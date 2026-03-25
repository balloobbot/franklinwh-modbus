# FranklinWH Modbus

Unofficial Python library & CLI for controlling **FranklinWH** battery storage systems via Modbus TCP, optimized for the aGate gateway.

!!! note "Related Project"
    For the FranklinWH Cloud API (non-Modbus), see [franklinwh-cloud](https://david2069.github.io/franklinwh-cloud/).

---

## Overview

**FranklinWH Modbus** provides direct, vendor-agnostic local network control over your aGate via the Modbus TCP protocol. Because it communicates directly with the hardware on your LAN, it operates entirely offline, bypasses cloud limits, and offers near-instantaneous response times (≤50ms).

👉 **[Read the complete guide on What Modbus TCP is, its challenges, and how it compares to the Cloud API](WHAT_IS_MODBUS_TCP.md)**

---

## FranklinWH Implementation Coverage

What the **aGate X / aPower S** system implements via Modbus TCP:

### ✅ Working

| Function | Model | Details |
|----------|-------|---------|
| Battery charge / discharge / standby | M704 (WSetPct) | Primary control mechanism — percentage of rated max |
| Battery SoC, SoH, DC power | M713 / M714 | M713.Sta unreliable (always 0) — state derived from M714.DCW |
| Battery lifetime energy | M714 (DCWhInj / DCWhAbs) | Cumulative charge and discharge (Wh) |
| AC grid power, voltage, frequency | M701 | Full implementation including per-phase data |
| Grid lifetime energy | M701 (TotWhInj / TotWhAbs) | Cumulative grid export and import (Wh) |
| Solar AC output power | M502 (OutPw / OutWh) | AC-coupled solar production and lifetime total |
| Grid protection trip curves | M707–M710 | Under/over voltage and frequency (read + write) |
| Volt-Var / Volt-Watt curves | M705 / M706 | Readable; writes untested |
| Frequency droop response | M711 | Readable; writes untested |
| Temperatures | M701 (TmpAmb / TmpCab) | Ambient and cabinet temperature |

### ❌ Not Functional

| Function | Model | Issue |
|----------|-------|-------|
| DER heartbeat | M715 (ControllerHb) | Ignored by aGate — use software timeout instead |
| Hardware reversion timer | M704 (WSetRvrtTms) | Non-functional — software auto-revert used |
| DC battery voltage | M714 (DCV) | Register not populated |
| DC battery current | M714 (DCA) | Always returns 0 — calculate from P/V |
| Solar voltage / current | M502 (OutV / InV) | Not populated |

### ⚠️ Requires SPAN Unlock

| Function | Register | Without SPAN |
|----------|----------|-------------|
| Work mode switching | Ext 15507 (OnGridMode) | Read-only |
| Self-consumption reserve | Ext 15508 | Read-only |
| TOU reserve | Ext 15509 | Read-only (also mirrors 15508 — known defect) |

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
