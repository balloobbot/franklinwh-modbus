# SunSpec2 Traceability Guide

This document maps SunSpec2 Information Models and Points to the API responses and UI displays for traceability.

## Overview

The FranklinWH Battery Manager reads data from multiple sources:
1. **SunSpec2 Models** (standard models 1, 701-706, 713-715)
2. **FranklinWH Extension Registers** (non-standard registers 15000+)

## SunSpec2 Model Mapping

### Model 1: Common (Device Information)

| SunSpec Point | API Field | UI Display | Description |
|--------------|-----------|------------|-------------|
| `Mn` | `device_info.manufacturer` | Device card | Manufacturer name |
| `Md` | `device_info.model` | Device card | Model identifier |
| `Vr` | `device_info.version` | Device card | Firmware version |
| `SN` | `device_info.serial` | Device card | Serial number |
| `DA` | - | - | Device address (unit ID) |

### Model 713: DER Storage Capacity

| SunSpec Point | Scale Factor | API Field | UI Display | Description |
|--------------|--------------|-----------|------------|-------------|
| `WHRtg` | `WH_SF` | `battery.rated_energy_wh` | Battery Metrics | Rated energy capacity (Wh) |
| `WHAvail` | `WH_SF` | `battery.available_energy_wh` | Battery Metrics | Available energy (Wh) |
| `SoC` | `Pct_SF` | `battery.soc` | Dashboard SOC card | State of Charge (%) |
| `SoH` | `Pct_SF` | `battery.soh` | Dashboard SOH card | State of Health (%) |
| `Sta` | - | `battery.status` | Battery Metrics | Status code |

### Model 714: DER Storage Status

| SunSpec Point | Scale Factor | API Field | UI Display | Description |
|--------------|--------------|-----------|------------|-------------|
| `Tmp` | `Tmp_SF` | `battery.temperature` | Battery Metrics | Battery temperature (°C) |
| `CyC` | - | `battery.cycles` | Dashboard SOH card | Cycle count |
| `DCWhInj` | `DCWH_SF` | `battery_lifetime.dc_energy_injected_wh` | Battery Lifetime | Total discharged (Wh) |
| `DCWhAbs` | `DCWH_SF` | `battery_lifetime.dc_energy_absorbed_wh` | Battery Lifetime | Total charged (Wh) |

### Model 701: DER AC Measurement

| SunSpec Point | Scale Factor | API Field | UI Display | Description |
|--------------|--------------|-----------|------------|-------------|
| `W` | `W_SF` | `inverter.power` | Dashboard Power card | AC Power (W) |
| `PhV`/`LNV`/`VL1` | `V_SF` | `inverter.voltage` | Inverter Status | AC Voltage (V) |
| `A` | `A_SF` | `inverter.current` | Inverter Status | AC Current (A) |
| `Hz` | `Hz_SF` | `inverter.frequency` | Inverter Status | Frequency (Hz) |
| `VA` | `VA_SF` | `inverter.apparent_power_va` | - | Apparent power (VA) |
| `VAR` | `VAR_SF` | `inverter.reactive_power_var` | - | Reactive power (VAR) |
| `PF` | `PF_SF` | `inverter.power_factor` | Inverter Status | Power factor |

### Model 703: DER Capacity

| SunSpec Point | Scale Factor | API Field | UI Display | Description |
|--------------|--------------|-----------|------------|-------------|
| `WChaMax` | `WChaMax_SF` | `capacity.max_charge_w` | Power Capacity | Max charge power (W) |
| `WDisChaMax` | `WChaMax_SF` | `capacity.max_discharge_w` | Power Capacity | Max discharge power (W) |
| `VAChaMax` | `VAChaMax_SF` | `capacity.max_charge_va` | - | Max charge VA |
| `VADisChaMax` | `VAChaMax_SF` | `capacity.max_discharge_va` | - | Max discharge VA |

### Model 502: Solar PV (Optional)

| SunSpec Point | Scale Factor | API Field | UI Display | Description |
|--------------|--------------|-----------|------------|-------------|
| `OutPw` | `OutPw_SF` | `solar_pv.output_power_w` | Solar PV widget | Current PV output (W) |
| `OutWh` | `OutWh_SF` | `solar_pv.output_energy_wh` | Solar PV widget | Lifetime PV energy (Wh) |

## FranklinWH Extension Registers

These are non-SunSpec registers specific to FranklinWH hardware:

| Register | Type | API Field | UI Display | Description |
|----------|------|-----------|------------|-------------|
| **15507** | **uint16** | `extensions.operatingMode` | Dashboard Mode card | **Operating mode (1-3): 1=Backup, 2=Self-Consumption, 3=TOU** |
| **15508** | **uint16** | `extensions.reserveSoc` | Reserve Settings | **Self-Consumption reserve %** |
| **15509** | **uint16** | `extensions.reserveSoc2` | Reserve Settings | **Time-of-Use reserve %** |
| 15502 | uint16 | `home_loads.pv_output_w` | Home Loads | PV output power (W) |
| 15503 | uint16 | `home_loads.pv_proximal_w` | Home Loads | Proximal PV power (W) |
| 15506 | uint16 | `home_loads.home_loads_w` | Home Loads | Home consumption (W) |
| 15510-15511 | uint32 | `home_loads.pv_output_wh` | Solar PV | PV Energy in Wh (32-bit) |
| 15512-15513 | uint32 | `home_loads.pv_proximal_wh` | Solar PV | Proximal PV Energy in Wh (32-bit) |

> **⚠️ Note:** Legacy addresses 15016/15017/15040 were corrected to 15507/15508/15509 per TODO_MODBUS_ADDRESS_MISMATCH.md (resolved 2026-02-14)

### Operating Mode Values (Register 15507)

| Value | Mode | UI Text |
|-------|------|---------|
| 0 | Standby | Standby |
| 1 | Normal | Normal |
| 2 | Backup Reserve | Backup Reserve |
| 3 | Self-Consumption | Self-Consumption |
| 4 | Time-of-Use | Time-of-Use |

## API Endpoint Mapping

### GET `/api/data`

Returns complete dataset with the following structure:

```json
{
  "timestamp": 1234567890,
  "device_info": { /* Model 1 data */ },
  "battery": { /* Models 713, 714 data */ },
  "inverter": { /* Model 701 data */ },
  "capacity": { /* Model 703 data */ },
  "battery_lifetime": { /* Model 714 DC energy data */ },
  "solar_pv": { /* Model 502 data */ },
  "home_loads": { /* Extension registers 15500+ */ },
  "extensions": { /* Extension registers 15000+ */ }
}
```

### GET `/api/extensions`

Dedicated endpoint for FranklinWH extension registers:

```json
{
  "operatingMode": 3,
  "modeText": "Self-Consumption",
  "reserveSoc": 20,
  "reserveSoc2": 16,
  "reserve_soc_self_consumption": 20,
  "reserve_soc_tou": 16,
  "_meta": {
    "operating_mode_register": 15507,
    "reserve_soc_register": 15508,
    "reserve_soc_2_register": 15509
  }
}
```

## Naming Conventions

### API Field Naming

| Source | Convention | Example |
|--------|------------|---------|
| SunSpec2 models | snake_case | `state_of_charge_percent` |
| Extension registers | camelCase (primary), snake_case (alias) | `reserveSoc` / `reserve_soc` |
| Human-readable aliases | descriptive | `reserve_soc_self_consumption` |

### Frontend Data Structure

The frontend (`static/index.html`) uses camelCase consistently:

```javascript
data: {
    battery: {
        soc: /* from battery.soc */,
        soh: /* from battery.soh */,
        temperature: /* from battery.temperature */,
        // ...
    },
    extensions: {
        operatingMode: /* from extensions.operatingMode */,
        reserveSoc: /* from extensions.reserveSoc */,
        reserveSoc2: /* from extensions.reserveSoc2 */
    }
}
```

## Scale Factors

SunSpec2 uses scale factors (SF) that are powers of 10:

```python
# Example: If SoC = 2000 and Pct_SF = -2
actual_soc = 2000 * (10 ** -2)  # = 20.0%
```

Common scale factors:
- `Pct_SF`: Usually -2 (values are hundredths of percent)
- `W_SF`: Usually 0 or -1 to -3 (watts)
- `V_SF`: Usually -1 (tenths of volts)
- `A_SF`: Usually -3 (thousandths of amps)
- `Tmp_SF`: Usually -1 (tenths of degrees)

## Debugging

To see raw register values:

```bash
curl http://localhost:8080/api/extensions
```

To read arbitrary registers:

```bash
curl -X POST http://localhost:8080/api/raw_registers \
  -H "Content-Type: application/json" \
  -d '{"start_address": 15000, "count": 50}'
```

## References

- [SunSpec Modbus Specification](https://sunspec.org/sunspec-modbus-specifications/)
- [SunSpec Information Models](https://github.com/sunspec/models)
- FranklinWH Modbus documentation (proprietary)
