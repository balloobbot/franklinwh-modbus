# SunSpec 2 Battery Energy Management Modes

## Overview

This guide explains how to achieve common home battery energy management scenarios using **SunSpec 2 models** (802, 124, 704, 123).

**Important Note:** Many energy management modes (self-consumption, load priorities) are handled by the **inverter's internal energy management system**, not directly by Modbus commands. Modbus primarily controls power limits and charging sources.

---

## Required SunSpec 2 Models

| Model | Name | Purpose |
|-------|------|---------|
| **802** | Battery Base | Battery status, connection control |
| **124** | Basic Storage Controls | Charge/discharge rates, grid charging control |
| **123** | Immediate Controls | Power reduction, export limiting |
| **704** | DER AC Controls | DER-level active/reactive power control |

---

## Model 124: Basic Storage Controls - Key Registers

| Point | Offset | Access | Type | Description |
|-------|--------|--------|------|-------------|
| **WChaMax** | 3 | R | uint16 | Max charge power (W) - reference value |
| **StorCtl_Mod** | 6 | RW | bitfield16 | Control mode: Bit 0=charge limit, Bit 1=discharge limit |
| **MinRsvPct** | 8 | RW | uint16 | Minimum reserve SOC (%) |
| **OutWRte** | 13 | RW | int16 | Discharge rate (% of WChaMax) |
| **InWRte** | 14 | RW | int16 | Charge rate (% of WChaMax) |
| **ChaGriSet** | 18 | RW | enum16 | 0=PV only, 1=Grid charging allowed |

**StorCtl_Mod Bit Values:**
- `0` = No limits active (inverter manages)
- `1` = Discharge limit active (Bit 0)
- `2` = Charge limit active (Bit 1)
- `3` = Both limits active (Bits 0+1)

**Scale Factor:** InOutWRte_SF (typically -2, meaning divide by 100)

---

## Scenario 1: Discharge Battery to Power Home Loads (No Grid Export)

### Description
Battery discharges to supply home loads. Excess solar goes to battery. No power exported to grid.

### How It Works
This is the **"Self-Consumption"** mode. The inverter automatically:
1. Measures home load consumption
2. Supplies loads from solar first
3. Uses battery to supplement when solar < loads
4. Prevents grid export (if export limiting is enabled)

### Modbus Configuration

```python
# Step 1: Enable Remote Control (Model 802)
write_register(802, LocRemCtl, 0)   # REMOTE mode

# Step 2: Connect Battery (Model 802)
write_register(802, SetOp, 1)       # CONNECT
write_register(802, SetInvState, 3) # INVERTER_STARTED

# Step 3: Allow discharge, limit as needed (Model 124)
write_register(124, StorCtl_Mod, 1)     # Discharge limit active only
write_register(124, OutWRte, 10000)     # 100% discharge allowed (scaled -2 = 100.00%)

# Step 4: Configure for self-consumption (Model 124)
write_register(124, ChaGriSet, 0)       # PV only (no grid charging)
write_register(124, MinRsvPct, 1000)    # 10% minimum reserve (scaled -2 = 10.00%)

# Step 5: Enable export limiting (Model 123 - if available)
write_register(123, WMaxLimPct, 0)      # 0% export = no grid export
write_register(123, WMaxLimPctEna, 1)   # Enable limit
```

### Alternative: Using DER AC Controls (Model 704)

```python
# Limit active power to prevent export
write_register(704, WMax, 0)            # Max active power = 0W (no export)
# OR
write_register(704, WMaxLimPct, 0)      # 0% of max power
write_register(704, WMaxLimPctEna, 1)   # Enable limit
```

### Verification

| Check | Expected Value |
|-------|----------------|
| Model 802.W | Positive (discharging) when loads > solar |
| Model 802.ChaSt | 3 (DISCHARGING) |
| Model 124.ChaGriSet | 0 (PV only) |
| Grid meter | 0W export (if export limit enabled) |

---

## Scenario 2: Charge Battery from Solar Inverter Only

### Description
Battery charges ONLY from solar PV. No grid charging allowed.

### How It Works
The inverter routes excess solar production to battery. When solar < home loads, battery discharges to supplement.

### Modbus Configuration

```python
# Step 1: Enable Remote Control (Model 802)
write_register(802, LocRemCtl, 0)   # REMOTE mode

# Step 2: Connect Battery (Model 802)
write_register(802, SetOp, 1)       # CONNECT
write_register(802, SetInvState, 3) # INVERTER_STARTED

# Step 3: Allow charging from PV only (Model 124)
write_register(124, ChaGriSet, 0)       # 0 = PV only (grid charging disabled)

# Step 4: Set charge rate (optional - limit max charge)
write_register(124, StorCtl_Mod, 2)     # Charge limit active
write_register(124, InWRte, 10000)      # 100% charge rate allowed

# Step 5: Set discharge parameters (optional)
write_register(124, OutWRte, 10000)     # Allow discharge when needed
```

### ChaGriSet Values

| Value | Mode | Description |
|-------|------|-------------|
| **0** | PV | Charge from solar only |
| **1** | GRID | Allow charging from grid |

### Verification

| Check | Expected Value |
|-------|----------------|
| Model 802.W | Negative (charging) when solar > loads |
| Model 802.ChaSt | 4 (CHARGING) |
| Model 124.ChaGriSet | 0 (PV only) |
| Grid power | Import only when solar+battery < loads |

---

## Scenario 3: Home Loads Priority: Solar → Battery → Grid

### Description
Home loads are supplied first from solar, then from battery if solar insufficient, then from grid if both insufficient.

### How It Works
This is the standard **self-consumption priority** managed by the inverter's energy management system:

```
Priority Order:
1. Solar PV → Home Loads
2. Battery → Home Loads (if solar < loads)
3. Grid → Home Loads (if solar + battery < loads)
```

### Modbus Configuration

```python
# Step 1: Enable Remote Control (Model 802)
write_register(802, LocRemCtl, 0)   # REMOTE mode

# Step 2: Connect Battery (Model 802)
write_register(802, SetOp, 1)       # CONNECT
write_register(802, SetInvState, 3) # INVERTER_STARTED

# Step 3: Enable both charge and discharge (Model 124)
write_register(124, StorCtl_Mod, 3)     # Both limits active
write_register(124, InWRte, 10000)      # 100% charge rate
write_register(124, OutWRte, 10000)     # 100% discharge rate

# Step 4: Configure charging source (Model 124)
write_register(124, ChaGriSet, 0)       # PV only (typical for self-consumption)

# Step 5: Set minimum reserve (Model 124)
write_register(124, MinRsvPct, 1000)    # 10% reserve for emergencies
```

### Power Flow Examples

| Solar | Load | Battery | Grid | Description |
|-------|------|---------|------|-------------|
| 3000W | 2000W | +1000W (charging) | 0W | Excess solar charges battery |
| 2000W | 3000W | -1000W (discharging) | 0W | Battery supplements solar |
| 1000W | 3000W | -2000W (discharging) | 0W | Battery supplies majority |
| 500W | 3000W | -100% (max discharge) | +500W | Grid supplements battery |

### Verification

| Check | Expected Value |
|-------|----------------|
| Model 802.W | Varies: negative (charging) or positive (discharging) |
| Model 802.ChaSt | 3 (DISCHARGING) or 4 (CHARGING) |
| Model 124.StorCtl_Mod | 3 (both limits active) |

---

## Scenario 4: Home Loads from Grid and Solar to Battery (Force Charge)

### Description
Home loads are supplied from grid while solar charges battery. Used for time-of-use optimization.

### How It Works
The inverter:
1. Sends all solar production to battery
2. Supplies home loads from grid
3. Battery charges at max rate from solar

### Modbus Configuration

```python
# Step 1: Enable Remote Control (Model 802)
write_register(802, LocRemCtl, 0)   # REMOTE mode

# Step 2: Connect Battery (Model 802)
write_register(802, SetOp, 1)       # CONNECT
write_register(802, SetInvState, 3) # INVERTER_STARTED

# Step 3: Allow grid charging (Model 124)
write_register(124, ChaGriSet, 1)       # 1 = GRID charging allowed

# Step 4: Force charge mode (Model 124)
# Set discharge limit to negative to force charging only
write_register(124, StorCtl_Mod, 3)     # Both limits active
write_register(124, InWRte, 10000)      # 100% charge rate
write_register(124, OutWRte, -10000)    # -100% = force charge only

# Alternative: Stop discharge completely
write_register(124, StorCtl_Mod, 3)     # Both limits active
write_register(124, InWRte, 10000)      # Max charge
write_register(124, OutWRte, 0)         # 0% discharge = no discharge allowed
```

### Power Window Configurations

| InWRte | OutWRte | StorCtl_Mod | Result | Use Case |
|--------|---------|-------------|--------|----------|
| 10000 | -10000 | 3 | Force charge only [WChaMax, WChaMax] | Off-peak charging |
| 10000 | 0 | 3 | Charge only, no discharge [0, WChaMax] | Preserve battery |
| 5000 | -5000 | 3 | Charge at 50% [1650W, 1650W] | Limited charging |

### Verification

| Check | Expected Value |
|-------|----------------|
| Model 802.W | Negative (charging) |
| Model 802.ChaSt | 4 (CHARGING) |
| Model 124.ChaGriSet | 1 (GRID allowed) |
| Grid power | Importing (supplying home loads) |

---

## Advanced: Time-of-Use (TOU) Control

### Schedule Charging During Off-Peak Hours

```python
# Off-peak hours: Force charge from grid + solar
if current_time in off_peak_window:
    write_register(124, ChaGriSet, 1)       # Allow grid charging
    write_register(124, StorCtl_Mod, 3)     # Both limits active
    write_register(124, InWRte, 10000)      # Max charge rate
    write_register(124, OutWRte, -10000)    # Force charge only

# Peak hours: Discharge to home loads, no grid export
elif current_time in peak_window:
    write_register(124, ChaGriSet, 0)       # PV only
    write_register(124, StorCtl_Mod, 3)     # Both limits active
    write_register(124, InWRte, 0)          # No charging
    write_register(124, OutWRte, 10000)     # Max discharge

# Normal hours: Self-consumption mode
else:
    write_register(124, ChaGriSet, 0)       # PV only
    write_register(124, StorCtl_Mod, 3)     # Both limits active
    write_register(124, InWRte, 10000)      # Normal charge
    write_register(124, OutWRte, 10000)     # Normal discharge
```

---

## Safety Checks & Validation

### Before Writing Control Values

```python
# 1. Check battery state (Model 802)
state = read_register(802, State)
if state != 3:  # CONNECTED
    print("Battery not ready. State:", state)
    return

# 2. Check for alarms (Model 802)
evt1 = read_register(802, Evt1)
evt2 = read_register(802, Evt2)
if evt1 != 0 or evt2 != 0:
    print("Active alarms detected!")
    return

# 3. Check SOC limits
soc = read_register(802, SoC)
soc_min = read_register(802, SoCMin)
soc_max = read_register(802, SoCMax)
if soc < soc_min or soc > soc_max:
    print("SOC out of safe range!")
    return

# 4. Validate power window (Model 124)
stor_ctl_mod = read_register(124, StorCtl_Mod)
in_wrte = read_register(124, InWRte)
out_wrte = read_register(124, OutWRte)

# Invalid condition: StorCtl_Mod == 3 AND (-1 * InWRte > OutWRte)
if stor_ctl_mod == 3 and (-1 * in_wrte > out_wrte):
    print("Invalid power window! Will cause Modbus Exception 3")
    return
```

### Heartbeat Maintenance

```python
# Must write CtrlHb every 1-2 seconds or battery disconnects
heartbeat = 0
while controlling:
    write_register(802, CtrlHb, heartbeat)
    heartbeat = (heartbeat + 1) % 65536
    time.sleep(1)
```

---

## Troubleshooting

### Modbus Exception 3 (ILLEGAL DATA VALUE)

**Cause:** Invalid power window configuration

**Check:**
- `StorCtl_Mod == 3` AND `(-1 * InWRte > OutWRte)` = INVALID
- Example: `InWRte = -5000`, `OutWRte = -3000`, `StorCtl_Mod = 3` → INVALID

**Fix:** Ensure power window is valid:
- For charge only: `InWRte = 10000`, `OutWRte = -10000` or `0`
- For discharge only: `InWRte = -10000` or `0`, `OutWRte = 10000`
- For bidirectional: `InWRte = 10000`, `OutWRte = 10000`

### Battery Disconnects Unexpectedly

**Cause:** Heartbeat timeout

**Fix:** Ensure `CtrlHb` is written every 1-2 seconds

### No Grid Export Despite Settings

**Cause:** Export limiting not enabled

**Fix:** Check Model 123 or 704 for export limit configuration

---

## Summary Table

| Scenario | ChaGriSet | InWRte | OutWRte | StorCtl_Mod | Notes |
|----------|-----------|--------|---------|-------------|-------|
| Self-consumption | 0 | 10000 | 10000 | 3 | Standard mode |
| PV-only charging | 0 | 10000 | 10000 | 2 or 3 | No grid charge |
| Force charge (off-peak) | 1 | 10000 | -10000 or 0 | 3 | Grid + solar → battery |
| Force discharge (peak) | 0 | 0 or -10000 | 10000 | 3 | Battery → home |
| Stop all | 0 | 0 | 0 | 3 | No charge/discharge |

---

## References

1. SunSpec Model 802 - Battery Base Model
2. SunSpec Model 124 - Basic Storage Controls
3. SunSpec Model 123 - Immediate Controls
4. SunSpec Model 704 - DER AC Controls
5. Fronius Datamanager Modbus TCP & RTU Documentation
6. SolarEdge Power Control Protocol

---

## Document Version

Created: 2026-02-12
Models Covered: 802, 124, 123, 704 (SunSpec 2)
