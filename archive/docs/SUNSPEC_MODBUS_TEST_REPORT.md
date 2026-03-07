# FranklinWH aGate SunSpec Modbus — Systematic Register Test Report

**Tester:** David (Australian Beta Tester)  
**Date:** 18 February 2026  
**aGate Model:** X Series (Australian market)  
**Firmware:** Current (R06+)  
**Connection:** WiFi (TCP port 502, Unit ID 2)  
**Tool:** pysunspec2 (SunSpec Alliance Python library)  
**Reference:** SunSpec PICS SM-000028 (FranklinWH)

---

## Executive Summary

Systematic testing of all writable (RW) SunSpec registers across Models 702, 704, 712, and 715 was performed on 18 February 2026. The aGate was tested under idle, active charging, and active discharging conditions.

**Key findings:**
- Only **3 registers** accept writes and control battery behavior (`WSetPct`, `WSetEna`, `WSetMod`)
- **9 registers** listed as RW in the SunSpec model are **rejected** by firmware (writes do not persist)
- **4+ registers** return `None` — not implemented in firmware at all
- `LocRemCtl` reports `LOCAL(1)` — the aGate never transitions to `REMOTE(0)` mode
- `ControllerHb` (heartbeat), `OpCtl`, and `AlarmReset` in Model 715 all reject writes
- **Zero alarms, zero faults** triggered across all testing — the aGate handles invalid writes gracefully

---

## Test Environment

| Parameter | Value |
|---|---|
| aGate IP | 192.168.0.110 (WiFi) |
| Modbus Port | 502 |
| Unit ID | 2 |
| Battery SoC at test | 48–49% |
| Solar production | ~200W (early morning, rising) |
| House load | ~200W |
| Test power level | 1500W (30% of 5kW rated max) |
| Settle time per test | 15 seconds |
| Models detected | 1, 502, 701, 702, 703, 704, 705, 706, 707, 708, 709, 710, 711, 712, 713, 714, 715 |

---

## Test Methodology

Each register was tested using the following procedure:

### Standard Register Test (Non-Control Registers)
1. Capture full system snapshot (SoC, DC power, Grid power, inverter state, alarm bitfield)
2. Read current register value
3. Write test value
4. Read back immediately to confirm acceptance
5. Monitor system state for 15 seconds with snapshots every 5 seconds
6. Record any alarms or inverter state changes
7. Reset all control registers to zero

### Active Control Register Test (WSetPct, WSet)
1. Pre-flight: disable `WSetEna=0`, write model
2. Configure: set `WSetMod=0` (absolute mode), set test register, zero the *other* control register to isolate
3. Write configuration to aGate
4. Enable: set `WSetEna=1`, write model
5. Monitor system state for 15 seconds with snapshots every 5 seconds
6. Record DC power change and grid power change
7. Reset all control registers to zero

### Combination Tests
Additional tests were run with registers written *during* active battery control (WSetPct actively charging/discharging) to test whether context-dependent register gating exists.

---

## Results: Model 704 (DERCtlAC)

### Active Power Control

| Addr | Register | Test Value | Readback | Accepted | DC Power Change | Notes |
|---|---|---|---|---|---|---|
| 40324 | **WSetPct** | +300 (30% discharge) | 300 | ✅ Yes | +1300W → DC=1500W | **Primary working control** |
| 40324 | **WSetPct** | -300 (30% charge) | -300 | ✅ Yes | -1700W → DC=-1500W | **Charging works** |
| 40320 | WSet | +1500 (discharge) | 1500 | ⚠️ Accepted | DC=0W, no change | Value stored but has no effect on power |
| 40320 | WSet | -1500 (charge) | -1500 | ⚠️ Accepted | Small transient only | Value stored but has no effect on power |

**Finding:** `WSetPct` is the **only register that controls battery charge/discharge rate**. `WSet` accepts values but the aGate ignores them for power control. Scale factor `WSetPct_SF = -1`, so raw value 300 = 30.0% of rated 5000W = 1500W.

### Power Limiting

| Addr | Register | Test Value | Readback | Accepted | Notes |
|---|---|---|---|---|---|
| 40310 | WMaxLimPctEna | 1 (enable) | 0 | ❌ Rejected | Reverts to 0 immediately |
| 40311 | WMaxLimPct | 300 (30%) | 1000 (100%) | ❌ Rejected | Reverts to default 1000 |

Tested in three contexts:
1. ❌ Idle state — rejected
2. ❌ During active 5kW discharge — rejected
3. ❌ During active 5kW charge — rejected

**PICS SM-000028 lists both as "supported".**

### Ramp Rate

| Addr | Register | Test Value | Readback | Accepted | Notes |
|---|---|---|---|---|---|
| 40345 | WRmp | 100 (%Max/Sec) | None | ❌ Unimplemented | Returns `None` always |
| 40345 | WRmp | 10 (%Max/Sec) | None | ❌ Unimplemented | Returns `None` always |
| 40346 | WRmpRef | 1 | None | ❌ Unimplemented | Returns `None` always |

### Reversion Timers

| Addr | Register | Current Value | Notes |
|---|---|---|---|
| 40327 | WSetRvrtTms | 0 | **PICS says "unimplemented"** — confirmed |
| 40322 | WSetRvrt | 65236 | Appears to be garbage/uninitialized |
| 40325 | WSetPctRvrt | 0 | ✅ Accepts writes (but no timer to trigger reversion) |

---

## Results: Model 702 (DERCapacity)

| Addr | Register | Test Value | Readback | Accepted | Notes |
|---|---|---|---|---|---|
| 40259 | WChaRteMax | 1500 | None | ❌ Unimplemented | Returns `None` — never initialized |
| 40260 | WDisChaRteMax | 1500 | None | ❌ Unimplemented | Returns `None` — never initialized |
| 40261 | VAChaRteMax | 1500 | None | ❌ Unimplemented | Returns `None` — never initialized |
| 40262 | VADisChaRteMax | 1500 | None | ❌ Unimplemented | Returns `None` — never initialized |

**All M702 rate limit registers return `None` — completely unimplemented.**

---

## Results: Model 715 (DERStorageCtl)

| Addr | Register | Test Value | Readback | Accepted | Notes |
|---|---|---|---|---|---|
| 41092 | ControllerHb | 1, 42, 100, 12345, 0xFFFF | 0 | ❌ Rejected | Multiple values tried, all revert to 0 |
| 41094 | AlarmReset | 1 | 0 | ❌ Rejected | Reverts to 0 |
| 41095 | OpCtl | 1 (External) | 0 | ❌ Rejected | All enum values tested |
| 41095 | OpCtl | 2 (Charge) | 0 | ❌ Rejected | |
| 41095 | OpCtl | 3 (Discharge) | 0 | ❌ Rejected | |

**LocRemCtl Status:**
```
Register: LocRemCtl (Model 715)
Value: 1 (LOCAL)
Type: Read-Only status register
Symbols: {REMOTE: 0, LOCAL: 1}
```

The aGate reports `LOCAL` control mode. Per SunSpec specification, `LOCAL` mode means "manual/maintenance operations — must be explicitly exited for the inverter to be controlled remotely."

### Combination Tests with M715

ControllerHb and OpCtl were re-tested during:
1. ❌ Active WSetPct discharge (DC=1500W) — still rejected
2. ❌ Active WSetPct charge (DC=-1500W) — still rejected
3. ❌ After enabling M712 DER Watt-Var module (Ena=1) — still rejected
4. ❌ Rapid heartbeat increment + OpCtl write sequence — still rejected

---

## Results: Model 712 (DERWattVar)

| Addr | Register | Current | Test | Readback | Accepted | Notes |
|---|---|---|---|---|---|---|
| 40989 | Ena | 0 | 1 | 1 | ✅ | Module enable/disable toggles correctly |

---

## Results: Model 713 (DERStorage)

| Register | Observed Value | Notes |
|---|---|---|
| Sta (Battery Status) | 0 (IDLE) | **Always reports IDLE** — even during active 5kW charge or discharge |
| SoC | 48–49% | Accurate |

**M713 `Sta` does not transition to CHARGING(1) or DISCHARGING(2)** — it remains IDLE(0) regardless of actual battery activity. This may be unimplemented or firmware may use a different state model.

---

## Results: Model 502 (DERMeasureAC)

| Addr | Register | Value | Writable | Notes |
|---|---|---|---|---|
| 41108 | Ctl | None | ❌ | Unimplemented |
| 41109 | CtlVend | None | ❌ | Unimplemented |
| 41111 | CtlVal | None | ❌ | Unimplemented |

---

## Active DER Modules

The following DER protection modules are enabled and functioning:

| Model | Module | Ena | Status |
|---|---|---|---|
| 705 | DER Volt-Var | 1 | ✅ Active |
| 706 | DER Volt-Watt | 1 | ✅ Active |
| 707 | DER Trip LV | 1 | ✅ Active |
| 708 | DER Trip HV | 1 | ✅ Active |
| 709 | DER Trip LF | 1 | ✅ Active |
| 710 | DER Trip HF | 1 | ✅ Active |
| 711 | DER Frequency Droop | 1 | ✅ Active |
| 712 | DER Watt-Var | 0 | Disabled (can be toggled) |

---

## Summary: Register Implementation Status

### ✅ Implemented and Working

| Register | Model | Function |
|---|---|---|
| WSetPct | 704 | **Battery charge/discharge rate (% of rated max)** |
| WSetEna | 704 | Enable/disable active power control |
| WSetMod | 704 | Active power mode selection |
| WSet | 704 | Accepts value but has no effect on power |
| WSetPctRvrt | 704 | Accepts value (requires timer for activation) |
| DER Module Ena | 705–712 | Module enable/disable toggles |

### ❌ In Register Map but Rejected by Firmware

| Register | Model | PICS Status | Behavior |
|---|---|---|---|
| WMaxLimPctEna | 704 | "supported" | Reverts to 0 |
| WMaxLimPct | 704 | "supported" | Reverts to 1000 (100%) |
| ControllerHb | 715 | RW | Stays at 0 |
| OpCtl | 715 | RW | Stays at 0 |
| AlarmReset | 715 | RW | Stays at 0 |

### ❌ Unimplemented (Return `None`)

| Register | Model | Notes |
|---|---|---|
| WChaRteMax | 702 | Charge rate limit — never initialized |
| WDisChaRteMax | 702 | Discharge rate limit — never initialized |
| VAChaRteMax | 702 | VA charge rate limit — never initialized |
| VADisChaRteMax | 702 | VA discharge rate limit — never initialized |
| WRmp | 704 | Ramp rate — never initialized |
| WRmpRef | 704 | Ramp rate reference — never initialized |
| WSetRvrtTms | 704 | Reversion timer — **PICS confirms "unimplemented"** |
| Ctl / CtlVend / CtlVal | 502 | DER measurement control — never initialized |

---

## Observations and Questions for FranklinWH

### 1. LocRemCtl = LOCAL — Is REMOTE Mode Available?

The aGate reports `LocRemCtl=1 (LOCAL)`. Per SPAN integration documentation, the installer app has a **Settings → Modbus → SPAN Panel → "Connect to SPAN Panel"** option that enables SunSpec Modbus integration.

**Question:** Can this mode be enabled for the Australian Beta unit to switch `LocRemCtl` to `REMOTE(0)`? This would likely unlock `ControllerHb`, `OpCtl`, and `WMaxLimPct` registers.

### 2. WMaxLimPctEna/WMaxLimPct — PICS vs Firmware

PICS SM-000028 lists `WMaxLimPctEna` and `WMaxLimPct` as **"supported"**, yet they reject all write attempts. 

**Question:** Is this gated behind `LocRemCtl=REMOTE` mode, or is it a firmware limitation in the current Australian Beta release?

### 3. Model 713 Battery Status Always IDLE

`M713.Sta` remains `IDLE(0)` during active 5kW charge and discharge operations. The SunSpec specification defines values for `CHARGING(1)`, `DISCHARGING(2)`, etc.

**Question:** Is the `Sta` register implemented? If so, under what conditions does it transition from IDLE?

### 4. Model 702 Rate Limits Not Initialized

All M702 rate limit registers (`WChaRteMax`, `WDisChaRteMax`, `VAChaRteMax`, `VADisChaRteMax`) return `None` — they appear completely uninitialized.

**Question:** Are these planned for implementation? They would be useful for setting charge/discharge rate limits independently of `WSetPct`.

### 5. Heartbeat and Reversion Timer

`ControllerHb` rejects writes and `WSetRvrtTms` is confirmed unimplemented per PICS. Without either mechanism, there is no automatic safety timeout — commands persist indefinitely until manually disabled.

**Question:** Is a safety timeout mechanism planned? For remote/automated control, a watchdog timer is critical to prevent unintended battery drain in case of communication loss.

### 6. WSetPct Sign Convention

The PICS document lists `WSetPct` with range `0–100`, but the aGate **accepts and responds to negative values** (e.g., -300 raw = -30% = charge at 1500W). Positive values discharge, negative values charge.

**Question:** Is the negative WSetPct behavior officially supported, or is this an undocumented extension? The signed `int16` type suggests it is intentional.

---

## Test Data Files

The following raw test data files are available upon request:

| File | Contents |
|---|---|
| `register_test_20260218_072400.json` | Full systematic test — 13 registers, per-test snapshots |
| `combination_test_results.json` | WMaxLimPct during active charge/discharge |
| `enhanced_test_results.json` | Battery state, ramp rate, and authority sequence tests |
| `rw_register_baseline.json` | Complete RW register baseline snapshot |

---

*Report generated using automated test scripts with pysunspec2 library. All tests conducted on live aGate hardware. Battery SoC remained stable throughout testing (47–49%). No alarms or faults were triggered.*
