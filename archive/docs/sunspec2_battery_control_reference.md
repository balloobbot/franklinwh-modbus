# SunSpec 2 Battery Control Reference Guide

## Overview

This guide covers charge/discharge control for Modbus TCP-connected batteries using **SunSpec 2 models only**.

**Critical Finding:** Model 802 (Battery Base Model) alone does NOT provide direct charge/discharge power control. You need additional DER models (704, 713, 715) for full control.

---

## Model 802: Battery Base Model

### What Model 802 CAN Do (Read-Only Monitoring)

| Point | Offset | Type | Description |
|-------|--------|------|-------------|
| **W** | 45 | int16 | Current power (W) - positive = discharging, negative = charging |
| **ChaSt** | 14 | enum16 | Charge status: 1=OFF, 2=EMPTY, 3=DISCHARGING, 4=CHARGING, 5=FULL, 6=HOLDING, 7=TESTING |
| **SoC** | 9 | uint16 | State of Charge (%) |
| **A** | 42 | int16 | DC current (A) - positive = discharge, negative = charge |
| **V** | 32 | uint16 | DC voltage (V) |
| **State** | 20 | enum16 | Battery state: 1=DISCONNECTED, 2=INITIALIZING, 3=CONNECTED, 4=STANDBY, 5=SOC PROTECTION, 6=SUSPENDING, 99=FAULT |
| **WChaRteMax** | 2 | uint16 | Max charge rate (W) - nameplate rating |
| **WDisChaRteMax** | 3 | uint16 | Max discharge rate (W) - nameplate rating |

### What Model 802 CAN Control (Read-Write)

| Point | Offset | Type | Values | Description |
|-------|--------|------|--------|-------------|
| **LocRemCtl** | 15 | enum16 | **0**=REMOTE, **1**=LOCAL | Must be 0 for external Modbus control |
| **SetOp** | 48 | enum16 | **1**=CONNECT, **2**=DISCONNECT | Connect/disconnect battery contactors |
| **SetInvState** | 49 | enum16 | **1**=STOPPED, **2**=STANDBY, **3**=STARTED | Set inverter state |
| **SocRsvMax** | 7 | uint16 | 0-100% | Max reserve SOC - limits discharge |
| **SoCRsvMin** | 8 | uint16 | 0-100% | Min reserve SOC - limits charge |
| **AlmRst** | 18 | uint16 | 1=Reset | Reset latched alarms |
| **CtrlHb** | 17 | uint16 | Incrementing | Controller heartbeat (write every 1-2 sec) |

### Model 802 Control Sequence (Basic Connection)

```
Step 1: Enable Remote Control
  LocRemCtl = 0    (REMOTE mode)

Step 2: Connect Battery
  SetOp = 1        (CONNECT)
  SetInvState = 3  (INVERTER_STARTED)

Step 3: Maintain Heartbeat (every 1-2 seconds)
  CtrlHb = incrementing value
```

---

## Model 704: DER AC Controls

### Description
Provides active and reactive power control for Distributed Energy Resources (DER) including batteries.

### Key Control Points (Read-Write)

| Point | Offset | Type | Description |
|-------|--------|------|-------------|
| **Conn** | varies | enum16 | Connection control: 0=DISCONNECT, 1=CONNECT |
| **WMax** | varies | uint16 | Active power setpoint (W) - limits max power output |
| **WMaxSpt** | varies | int16 | Active power setpoint for charge/discharge control |
| **VArMax** | varies | uint16 | Max reactive power (var) |
| **VArMaxSpt** | varies | int16 | Reactive power setpoint |
| **VArPct_Mod** | varies | enum16 | VAr control mode: 1=NONE, 2=WMAX, 3=VREF, 4=VREF_WMAX |
| **WMaxLimPct** | varies | uint16 | Active power limit as % of WMax |
| **WMaxLimPctEna** | varies | enum16 | Enable power limit: 0=DISABLED, 1=ENABLED |
| **OutPFSet** | varies | int16 | Power factor setpoint |
| **OutPFSetEna** | varies | enum16 | Enable PF control: 0=DISABLED, 1=ENABLED |
| **VArPctEna** | varies | enum16 | Enable VAr control: 0=DISABLED, 1=ENABLED |

### Scale Factors
- All power values use scale factors (typically W_SF, VAr_SF)
- Check the model's scale factor registers for actual values

---

## Model 713: DER Storage Capacity

### Description
Provides storage-specific capacity and rate settings for battery systems.

### Key Points (Read-Only)

| Point | Description |
|-------|-------------|
| **WChaMax** | Max charge capacity (W) |
| **WDisChaMax** | Max discharge capacity (W) |
| **StorCap** | Total storage capacity (Wh) |
| **InBatV** | Battery voltage (V) |
| **InBatA** | Battery current (A) |

### Key Control Points (Read-Write)

| Point | Description |
|-------|-------------|
| **ChaGriSet** | Charge from grid setting |
| **WChaMaxSpt** | Charge power setpoint |
| **WDisChaMaxSpt** | Discharge power setpoint |

---

## Model 715: DER Control

### Description
Provides basic control modes and settings for DER devices.

### Key Control Points (Read-Write)

| Point | Offset | Type | Values | Description |
|-------|--------|------|--------|-------------|
| **DERMode** | varies | enum16 | 1=OFF, 2=STANDBY, 3=ON | Basic DER mode control |
| **DERSt** | varies | enum16 | Status enum | DER state |
| **SetGradW** | varies | uint16 | %/second | Power ramp rate |

---

## Control Sequences for Charge/Discharge

### Sequence 1: Using Model 704 (DER AC Controls) + Model 802

**Prerequisites:**
- Model 802: Battery connected and in REMOTE mode
- Model 704: Available for power control

#### Force Charging (Battery absorbs power from grid)

```
Step 1: Enable Remote Control (Model 802)
  LocRemCtl = 0

Step 2: Connect Battery (Model 802)
  SetOp = 1
  SetInvState = 3

Step 3: Enable Power Limit (Model 704)
  WMaxLimPctEna = 1

Step 4: Set Charge Power Limit (Model 704)
  WMaxLimPct = 0    (0% = no discharge allowed)
  OR
  WMaxSpt = negative value for charge power

Step 5: Maintain Control
  Write CtrlHb (Model 802) every 1-2 seconds
  Monitor W (Model 802) to verify negative power (charging)
```

#### Force Discharging (Battery exports power to grid)

```
Step 1: Enable Remote Control (Model 802)
  LocRemCtl = 0

Step 2: Connect Battery (Model 802)
  SetOp = 1
  SetInvState = 3

Step 3: Enable Power Limit (Model 704)
  WMaxLimPctEna = 1

Step 4: Set Discharge Power (Model 704)
  WMaxLimPct = 5000   (50% of max power)
  OR
  WMaxSpt = positive value for discharge power

Step 5: Maintain Control
  Write CtrlHb (Model 802) every 1-2 seconds
  Monitor W (Model 802) to verify positive power (discharging)
```

#### Stop All Power Flow

```
Model 704:
  WMaxLimPct = 0
  WMaxLimPctEna = 1
  
OR

  DERMode = 2 (STANDBY)
```

### Sequence 2: Using Model 713 (DER Storage Capacity) + Model 802

**Prerequisites:**
- Model 802: Battery connected and in REMOTE mode
- Model 713: Available for storage-specific control

#### Force Charging

```
Step 1: Enable Remote Control (Model 802)
  LocRemCtl = 0

Step 2: Connect Battery (Model 802)
  SetOp = 1
  SetInvState = 3

Step 3: Set Charge Power (Model 713)
  WChaMaxSpt = desired charge power (W)
  ChaGriSet = 1 (allow grid charging if needed)

Step 4: Monitor
  Read W (Model 802) - should be negative
  Read ChaSt (Model 802) - should be 4 (CHARGING)
```

#### Force Discharging

```
Step 1: Enable Remote Control (Model 802)
  LocRemCtl = 0

Step 2: Connect Battery (Model 802)
  SetOp = 1
  SetInvState = 3

Step 3: Set Discharge Power (Model 713)
  WDisChaMaxSpt = desired discharge power (W)

Step 4: Monitor
  Read W (Model 802) - should be positive
  Read ChaSt (Model 802) - should be 3 (DISCHARGING)
```

---

## How to Check Available Models

### Step 1: Read Model 1 (Common Model)

Model 1 contains device information and is always present.

| Point | Offset | Description |
|-------|--------|-------------|
| **SID** | varies | SunSpec ID (should be 0x53756E53 = "SunS") |

### Step 2: Scan for Model IDs

Read consecutive registers starting from base address to find model headers:

```
Model Header Format:
  - 2 bytes: Model ID
  - 2 bytes: Model Length (in 16-bit registers)
```

**Look for these model IDs:**
- 1 = Common
- 802 = Battery Base
- 803 = Battery Lithium-Ion
- 804 = Battery Lithium-Ion String
- 805 = Battery Lithium-Ion Module
- 704 = DER AC Controls
- 713 = DER Storage Capacity
- 715 = DER Control

### Example Scan Results

```
Address 40000: Model ID = 1 (Common), Length = 66
Address 40066: Model ID = 802 (Battery Base), Length = 62
Address 40128: Model ID = 704 (DER AC Controls), Length = XX
```

---

## Important Notes

### Scale Factors
- All power values in SunSpec use scale factors
- Example: W_SF = -2 means divide raw value by 100
- Always read the scale factor register first

### Safety Requirements
1. **Heartbeat:** Write CtrlHb every 1-2 seconds or battery may disconnect
2. **State Validation:** Check State (Model 802) = 3 (CONNECTED) before control
3. **Alarm Check:** Read Evt1/Evt2 before control to ensure no active faults
4. **SOC Limits:** Respect SoCMin and SoCMax to prevent battery damage

### Communication Loss Behavior
- If heartbeat stops, battery typically disconnects automatically
- SetOp may revert to DISCONNECT (2)
- Inverter may stop for safety

### Invalid Control Combinations
- Some model combinations return Modbus Exception 3 (ILLEGAL DATA VALUE)
- Ensure power setpoints are within WChaRteMax and WDisChaRteMax limits

---

## Quick Reference: Model 802 Register Map

| Point | Offset | Access | Type | Units | Mandatory |
|-------|--------|--------|------|-------|-----------|
| AHRtg | 0 | R | uint16 | Ah | Yes |
| WHRtg | 1 | R | uint16 | Wh | Yes |
| WChaRteMax | 2 | R | uint16 | W | Yes |
| WDisChaRteMax | 3 | R | uint16 | W | Yes |
| DisChaRte | 4 | R | uint16 | %WHRtg | No |
| SoCMax | 5 | R | uint16 | %WHRtg | No |
| SoCMin | 6 | R | uint16 | %WHRtg | No |
| SocRsvMax | 7 | RW | uint16 | %WHRtg | No |
| SoCRsvMin | 8 | RW | uint16 | %WHRtg | No |
| SoC | 9 | R | uint16 | %WHRtg | Yes |
| DoD | 10 | R | uint16 | % | No |
| SoH | 11 | R | uint16 | % | No |
| NCyc | 12 | R | uint32 | - | No |
| ChaSt | 14 | R | enum16 | - | No |
| LocRemCtl | 15 | R | enum16 | - | Yes |
| Hb | 16 | R | uint16 | - | No |
| CtrlHb | 17 | RW | uint16 | - | No |
| AlmRst | 18 | RW | uint16 | - | Yes |
| Typ | 19 | R | enum16 | - | Yes |
| State | 20 | R | enum16 | - | Yes |
| StateVnd | 21 | R | enum16 | - | No |
| WarrDt | 22 | R | uint32 | days | No |
| Evt1 | 24 | R | bitfield32 | - | Yes |
| Evt2 | 26 | R | bitfield32 | - | Yes |
| EvtVnd1 | 28 | R | bitfield32 | - | Yes |
| EvtVnd2 | 30 | R | bitfield32 | - | Yes |
| V | 32 | R | uint16 | V | Yes |
| VMax | 33 | R | uint16 | V | No |
| VMin | 34 | R | uint16 | V | No |
| CellVMax | 35 | R | uint16 | V | No |
| CellVMaxStr | 36 | R | uint16 | - | No |
| CellVMaxMod | 37 | R | uint16 | - | No |
| CellVMin | 38 | R | uint16 | V | No |
| CellVMinStr | 39 | R | uint16 | - | No |
| CellVMinMod | 40 | R | uint16 | - | No |
| CellVAvg | 41 | R | uint16 | V | No |
| A | 42 | R | int16 | A | Yes |
| AChaMax | 43 | R | uint16 | A | No |
| ADisChaMax | 44 | R | uint16 | A | No |
| W | 45 | R | int16 | W | Yes |
| ReqInvState | 46 | R | enum16 | - | No |
| ReqW | 47 | R | int16 | W | No |
| SetOp | 48 | RW | enum16 | - | Yes |
| SetInvState | 49 | RW | enum16 | - | Yes |
| AHRtg_SF | 50 | R | sunssf | - | Yes |
| WHRtg_SF | 51 | R | sunssf | - | Yes |
| WChaDisChaMax_SF | 52 | R | sunssf | - | Yes |
| DisChaRte_SF | 53 | R | sunssf | - | No |
| SoC_SF | 54 | R | sunssf | - | Yes |
| DoD_SF | 55 | R | sunssf | - | No |
| SoH_SF | 56 | R | sunssf | - | No |
| V_SF | 57 | R | sunssf | - | Yes |
| CellV_SF | 58 | R | sunssf | - | Yes |
| A_SF | 59 | R | sunssf | - | Yes |
| AMax_SF | 60 | R | sunssf | - | Yes |
| W_SF | 61 | R | sunssf | - | No |

**Total Length:** 62 registers (0-61)

---

## References

1. SunSpec Alliance - Model 802 Battery Base Model
2. Socomec SunSpec Implementation Guide (Models 702-715)
3. Nuvation Energy BMS Modbus Manual
4. SunSpec DER Information Models

---

## Document Version

Created: 2026-02-12
Models Covered: 802, 704, 713, 715 (SunSpec 2)
