# FranklinWH Modbus

Unofficial Python library & CLI for controlling **FranklinWH** battery storage systems via Modbus TCP, optimized for the aGate gateway.

!!! note "Related Project"
    For the FranklinWH Cloud API (non-Modbus), see [franklinwh-cloud](https://david2069.github.io/franklinwh-cloud/).

---

## What is Modbus TCP?

**Modbus TCP** is a vendor-agnostic local network protocol that allows direct control of compatible devices over your LAN. Originally a serial protocol (1979), it was extended to TCP/IP and is now the most widely deployed protocol for industrial automation, solar inverters, and battery storage systems.

When combined with **SunSpec** (see below), Modbus TCP provides a standardised way to:

- **Read metrics** — battery state of charge, solar production, grid power, voltages, frequencies, temperatures, lifetime energy accumulators
- **Control devices** — charge/discharge batteries, set power limits, configure grid protection curves
- **Monitor alarms** — system faults, DC port alarms, grid events

### Vendor Implementation Reality

Each vendor must meet a minimum conformance standard, but in practice:

- **Partial implementations are common** — registers may return 0 or `None` even though they appear in the model definition
- **Proprietary extensions** vary between vendors — FranklinWH adds extension registers (15500+ range) for features like work mode switching (Emergency Backup, Self-Consumption, TOU) and remote solar metering via aPBox
- **Implementation quality differs** between a vendor's own models and firmware versions — what works on one model may not work on another

This library documents all known FranklinWH-specific quirks in the [SunSpec Quirks](FRANKLINWH_SUNSPEC_QUIRKS.md) guide.

---

## Modbus TCP vs Cloud API

Both this library and [franklinwh-cloud](https://david2069.github.io/franklinwh-cloud/) control the same hardware — they use different paths to get there.

| Aspect | Modbus TCP (this library) | Cloud API (franklinwh-cloud) |
|--------|--------------------------|------------------------------|
| **Latency** | ~50ms (LAN direct) | ~500ms–2s (internet via CloudFront) |
| **Availability** | Works offline and off-grid | Requires internet + FranklinWH servers |
| **Control path** | Direct register writes to aGate | Cloud-mediated commands via MQTT |
| **Data freshness** | Real-time (configurable poll rate) | ~30s telemetry intervals |
| **Setup** | Requires installer to enable Modbus TCP | Works with standard FranklinWH credentials |
| **Battery control** | ✅ Charge / discharge / standby | ✅ Charge / discharge / standby |
| **TOU schedules** | ⚠️ Read-only (extension registers) | ✅ Full read/write |
| **Mode switching** | ⚠️ Requires SPAN unlock for writes | ✅ Full support |
| **Risk profile** | Direct hardware access — mistakes persist | Cloud-mediated — safer guardrails |

!!! tip "When to use which"
    **Modbus TCP** for real-time monitoring, low-latency VPP/arbitrage control, and offline/off-grid operation. **Cloud API** for TOU schedule management, remote access from outside your LAN, and when Modbus TCP is not enabled on your aGate.

---

## SunSpec Alliance

The [**SunSpec Alliance**](https://sunspec.org) is a non-profit industry alliance that defines open standards for solar, storage, and smart energy interoperability.

- **SunSpec Information Model** — standardised register maps for Distributed Energy Resources (DER). Each "model" defines a block of registers with fixed addresses, data types, and scale factors
- **700-series models** — DER devices (inverters, batteries, grid interfaces). This is what the aGate implements
- **PICS** (Protocol Implementation Conformance Statement) — a vendor's formal declaration of which models and fields they support. FranklinWH's PICS covers Models 1, 701–715
- **Conformance testing** — SunSpec certifies devices against their test suites, but real-world implementations frequently deviate from the specification

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
