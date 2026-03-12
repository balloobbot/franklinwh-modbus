# Virtual Mode Specifications & Validation Targets

> **Purpose**: Define exactly what each mode does, how it uses M704 writes, and what we expect to observe during hardware validation.
> **Last Updated**: 2026-03-12

---

## Two Control Layers

The FranklinWH system has **two independent control layers** that run in parallel:

| Layer | Source | Registers | Can We Change? |
|-------|--------|-----------|----------------|
| **aGate Native** | FranklinWH Cloud/App | Ext.15507 (OnGridMode) | ❌ Read-only without SPAN unlock |
| **Virtual (Ours)** | `modes.py` via M704 | WSetEna, WSetPct, WSet | ✅ Always writable |

Our virtual modes **override** the aGate's native behavior by sending M704 power commands every 5 seconds. The native mode keeps running in the background — when we release control (`--stop`), the aGate resumes its native mode immediately.

---

## aGate Native Modes (Ext.15507 — Read Only)

These are what the FranklinWH app sets. We can READ them but not change them (without SPAN Modbus unlock).

| Value | Mode | Behavior |
|-------|------|----------|
| 0 | **Emergency Backup** | Charges battery to reserve %, holds it there. Minimal discharge unless outage. |
| 1 | **Self-Consumption** | Maximizes self-use of solar. Discharges to cover home load, charges from excess solar. |
| 2 | **TOU (Time-of-Use)** | Charges during off-peak, discharges during peak. Schedule-driven. |
| 3 | **Manual** | User-specified behavior (rarely used from app). |

---

## Virtual Modes (Our Library — `modes.py`)

### 1. `self_consumption` — Default Mode

**Intent**: Maximize use of solar/battery, minimize grid import. Behaves like the aGate app's Self-Consumption mode.

**Algorithm** (`_calc_self_consumption`):
```
IF SoC >= target_soc:
    IF solar > home: charge from excess solar
    IF solar < home: discharge to cover shortfall
    IF solar = home: idle (0W)
ELSE (SoC < target):
    FULL POWER CHARGE (to reach target ASAP — matches vendor behavior)
```

**Parameters**:
- `target_soc` (default: 100%) — charge target
- `self_reserve_pct` (default: 20%) — minimum SoC before stopping discharge

**Validation Targets**:
- [ ] Night, SoC < target: should charge at max power from grid
- [ ] Night, SoC >= target: should discharge to cover home load
- [ ] Day with solar, SoC < target: should charge from solar + grid
- [ ] Day with excess solar, SoC >= target: should charge only from excess solar

---

### 2. `emergency_backup` — Keep Battery Full

**Intent**: Keep battery charged for potential outages. Charges to target, then holds.

**Algorithm** (`_calc_emergency_backup`):
```
IF SoC >= target: idle (0W)
ELSE: charge at high power (proportional to gap)
```

**Parameters**:
- `target_soc` (default: 95%) — backup target

**Validation Targets**:
- [ ] SoC < target: should charge at high power
- [ ] SoC >= target: should idle (0W, no discharge)
- [ ] Key difference from self_consumption: does NOT discharge to cover home load

---

### 3. `grid_zero` — Minimize Grid Interaction

**Intent**: Keep grid power near zero. Battery covers any shortfall, absorbs any excess.

**Algorithm** (`_calc_grid_zero`):
```
net_load = home - solar
IF net_load > 0: discharge to cover (battery supplements grid)
IF net_load < 0 AND SoC < target: charge from excess solar
IF net_load < 0 AND SoC >= target: idle
```

**Parameters**:
- `target_soc` (default: 100%)
- `grid_zero_buffer` (default: 100W)

**Validation Targets**:
- [ ] Home > solar: battery should discharge, grid import near 0W
- [ ] Solar > home: battery should charge from excess, grid export near 0W
- [ ] Key metric: `M701.W` (grid power) should stay close to 0W

---

### 4. `peak_shave` — Reduce Peak Grid Demand

**Intent**: Discharge battery only when home load exceeds a threshold. Reduces demand charges.

**Algorithm** (`_calc_peak_shave`):
```
IF home > peak_shave_threshold AND SoC > min_discharge + 5%:
    discharge to cover excess above threshold
ELSE: idle (0W)
```

**Parameters**:
- `peak_shave_threshold` (default: 2000W) — discharge only above this load
- `min_discharge_soc` — minimum SoC

**Validation Targets**:
- [ ] Home < 2000W: battery should idle
- [ ] Home > 2000W: battery should discharge just enough to bring grid below threshold
- [ ] SoC near min_discharge: should stop discharging

---

### 5. `time_of_use` — Schedule-Based Arbitrage

**Intent**: Charge during off-peak hours, discharge during peak hours. Uses a TOU schedule definition.

**Algorithm** (`_calc_time_of_use`):
```
strategy = schedule.get_strategy()  # "charge", "discharge", "grid_zero", "solar_priority"

IF strategy == "charge":
    charge at max power (add solar if available)
IF strategy == "discharge":
    discharge to cover home load
IF strategy == "grid_zero":
    → delegates to grid_zero algorithm
IF strategy == "solar_priority":
    charge only from solar, else self_consumption
```

**Parameters**:
- TOU schedule (JSON/YAML with time periods and strategies)
- `target_soc` — charge limit
- `min_soc` / `max_soc` from schedule

**Validation Targets**:
- [ ] During "charge" period: battery should charge
- [ ] During "discharge" period: battery should discharge
- [ ] Period transitions: should switch behavior at boundary
- [ ] SoC limits: should respect min/max per period

---

### 6. `manual` — Direct Power Control

**Intent**: User specifies exact power. Simplest mode.

**Algorithm** (`_calc_manual`):
```
RETURN manual_power_w  # Whatever the user set
```

**Parameters**:
- `manual_power_w` — power in watts (positive=charge, negative=discharge)

**Validation Targets**:
- [x] Positive value → battery charges (**validated 2026-03-12**)
- [x] Negative value → battery discharges (**validated 2026-03-12**)
- [ ] Zero → battery idles

---

## Safety Systems (All Modes)

Applied after every mode calculation:

| Safety | Trigger | Action |
|--------|---------|--------|
| **SoC Hard Limit** | SoC ≥ 99.5% (charge) or ≤ 0.5% (discharge) | Block command entirely |
| **SoC Ramp** | Within `soc_ramp_window` (10%) of limit | Linearly reduce power |
| **Inverter Limit** | Power > 5000W | Cap at rated maximum |
| **Load Safety** | Home load > 90% of capacity | Reduce discharge to prevent overload |
| **Alarm Check** | Blocking alarms active | Stop operation (if safety checks enabled) |

---

## Hardware Validation Plan

### Tier 2 Tests (Pre-Approved, ≤500W, ≤30s)

| # | Test | Mode | Expects | Verify |
|---|------|------|---------|--------|
| 1 | Manual charge | `--charge 500` | CHARGING 500W | M714.DCW positive ✅ |
| 2 | Manual discharge | `--discharge 500` | DISCHARGING 500W | M714.DCW negative ✅ |
| 3 | Manual idle | `--mode manual --power 0` | IDLE 0W | M714.DCW ~0W |
| 4 | Self-consumption (SoC < target) | `--mode self_consumption --target-soc 99` | CHARGING at max | Grid importing |
| 5 | Self-consumption (SoC > target) | `--mode self_consumption --target-soc 50` | DISCHARGING | Grid power reduced |
| 6 | Emergency backup (SoC < target) | `--mode emergency_backup --target-soc 99` | CHARGING | Grid importing |
| 7 | Emergency backup (SoC > target) | `--mode emergency_backup --target-soc 50` | IDLE (0W) | No discharge |
| 8 | Grid zero | `--mode grid_zero` | Varies | M701.W near 0W |
| 9 | Peak shave (below threshold) | `--mode peak_shave` | IDLE | No battery activity |

### Post-Each-Test (Mandatory)
```bash
python3 tools/franklinwh_cli.py -i 192.168.0.110 --stop
python3 tools/franklinwh_cli.py -i 192.168.0.110 --healthcheck | grep zombie_state
```
