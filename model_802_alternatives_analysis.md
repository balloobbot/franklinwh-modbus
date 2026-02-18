# Model 802 Alternative Control Points Analysis

**Date:** 2026-02-14  
**Question:** Do Model 704/703 "Set" points serve as alternatives to Model 802's battery connection controls?

---

## Model 802 Missing Controls (What We Need)

From SunSpec2 standard, Model 802 provides:

| Point | Access | Values | Purpose |
|-------|--------|--------|---------|
| **SetOp** | RW | 1=CONNECT, 2=DISCONNECT | **Battery contactor control** |
| **SetInvState** | RW | 1=STOPPED, 2=STANDBY, 3=STARTED | **Inverter state control** |

**Key Question:** Are these **enable/allow** (permission) or **command** (execution)?

**Answer:** These are **COMMAND** registers:
- `SetOp = 1` → **Closes battery contactors** (physical connection)
- `SetInvState = 3` → **Starts inverter** (begins power conversion)

Without these, standard SunSpec2 sequences cannot connect/disconnect the battery.

---

## Found Control Points Analysis

### Current Values (Read from FranklinWH)

| Model | Point | Current Value | Type |
|-------|-------|---------------|------|
| 704 | `WSetEna` | **0** | Enable flag |
| 704 | `WSetMod` | **0** | Mode enum |
| 703 | `ES` | **1** (Unknown) | Enter Service enum |

---

## Point-by-Point Analysis

### 1. Model 704: Active Power Setpoint Controls

#### `WSetEna` - Set Active Power Enable

**Purpose:** Enable/disable active power setpoint control

| Value | Meaning | Similar to Model 802? |
|-------|---------|----------------------|
| 0 | Power setpoint disabled | ❌ NOT similar to SetOp |
| 1 | Power setpoint enabled | Uses `WSet` or `WSetPct` |

**Current:** `0` (disabled)

**Verdict:** ❌ **NOT equivalent to SetOp**
- This enables the `WSet` (active power setpoint) feature
- Does NOT connect/disconnect battery contactors
- Does NOT control inverter state

**Use Case:**
```python
# Enable active power setpoint control
model_704.WSetEna = 1     # Enable
model_704.WSet = 3000     # Set 3kW active power
# Battery will target 3kW output (if discharging) or input (if charging)
```

#### `WSetMod` - Set Active Power Mode

**Purpose:** Define how active power setpoint is interpreted

| Value | Mode | Description |
|-------|------|-------------|
| 0 | None | No setpoint active |
| 1 | Watts (W) | Use `WSet` (absolute watts) |
| 2 | Percent | Use `WSetPct` (% of max power) |

**Current:** `0` (None)

**Verdict:** ❌ **NOT equivalent to SetOp or SetInvState**
- Selects interpretation mode for power setpoint
- Does NOT control battery connection or inverter state

---

### 2. Model 703: Enter Service

#### `ES` - Enter Service State

**Purpose:** Grid connection state for DER (Distributed Energy Resource)

| Value | State | Description |
|-------|-------|-------------|
| 1 | Disconnected | DER not connected to grid |
| 2 | Initializing | Starting connection sequence |
| 3 | Connected | DER connected and operational |
| 4 | Standby | Connected but not transferring power |

**Current:** `1` (Unknown - likely Disconnected)

**Verdict:** 🟡 **POSSIBLY similar to SetOp, but for GRID connection, not battery**

**Key Difference:**
- Model 802 `SetOp` = Battery connection to inverter
- Model 703 `ES` = DER/inverter connection to grid

**Testing Required:**
```python
# Hypothesis: ES=3 might enable grid connection
model_703.ES = 3  # CONNECTED

# But this likely controls grid connection, NOT battery connection
# Battery may already be connected internally
```

---

### 3. Model 704: Reactive Power Setpoint Controls

#### `VarSetEna` / `VarSetMod` / `VarSet`

**Purpose:** Control reactive power (VAR) for power factor management

**Verdict:** ❌ **NOT related to battery connection**
- These control reactive power (VAr), not battery contactors
- Used for voltage regulation and power factor correction

---

### 4. Other "Set" Points

**These are all SETTINGS, not CONNECTION CONTROLS:**

| Point Pattern | Purpose | Model 802 Equivalent? |
|---------------|---------|----------------------|
| `*Max` Settings | Operational limits | ❌ No - just limits |
| `WSetPct` | Power setpoint % | ❌ No - power control |
| `*RvrtTms` | Reversion timeouts | ❌ No - safety timers |

---

## Critical Finding

### ⚠️ NO Model 802 Equivalent Found

**None of the "Set" points serve as direct replacements for:**
- ❌ `SetOp` (battery contactor connect/disconnect)
- ❌ `SetInvState` (inverter start/stop/standby)

**Why This Matters:**

Standard SunSpec2 battery control sequences assume you can:
1. Connect battery (`SetOp = 1`)
2. Start inverter (`SetInvState = 3`)
3. Apply charge/discharge commands
4. Maintain heartbeat (`CtrlHb`)

**Without Model 802, we cannot execute steps 1, 2, and 4.**

---

## FranklinWH's Unique Behavior

### What We've Discovered

1. ✅ Battery appears **always connected** (internal logic handles this)
2. ✅ Inverter appears **always started** when aGate is online
3. ✅ No `LocRemCtl = 0` (REMOTE mode) required for writes
4. ✅ No `CtrlHb` heartbeat required
5. ✅ Can write directly to Model 702/704 control points

**Theory:** FranklinWH handles battery connection and inverter state **internally**, bypassing SunSpec2 Model 802 sequence.

---

## Implications for Control Strategy

### What This Means

| Scenario | Standard SunSpec2 | FranklinWH Behavior |
|----------|-------------------|---------------------|
| **Connect Battery** | Write `SetOp = 1` | ✅ Already connected |
| **Start Inverter** | Write `SetInvState = 3` | ✅ Already started |
| **Enable Control** | Write `LocRemCtl = 0` | ⚠️ Not required |
| **Maintain Heartbeat** | Write `CtrlHb` every 1-2s | ⚠️ Not required |
| **Apply Limits** | Write after connection | ✅ Can write directly |

### Recommended Testing Sequence

```python
# Test 1: Write control WITHOUT SetOp/SetInvState
# (This is what we've been doing successfully)
model_702 = client.get_model(702)
model_702.WChaRteMax.value = 2500  # 2.5kW charge limit
model_702.write()
# Expected: SUCCESS (already confirmed in previous tests)

# Test 2: Try Model 703 Enter Service
model_703 = client.get_model(703)
current_es = model_703.ES.value  # Currently 1
print(f"Current ES: {current_es}")

# Attempt to set ES = 3 (CONNECTED)
# CAUTION: This might affect grid connection!
# model_703.ES.value = 3
# model_703.write()

# Test 3: Try WSetEna / WSet for power setpoint
model_704 = client.get_model(704)
model_704.WSetEna.value = 1     # Enable setpoint
model_704.WSetMod.value = 1     # Watts mode
model_704.WSet.value = 3000     # 3kW setpoint
model_704.write()
# Monitor: Does battery target 3kW?
```

---

## Recommendations

### 1. ✅ Proceed with Direct Control (No SetOp/SetInvState Needed)

**Evidence:**
- You've already written to FranklinWH extension registers (15507-15509) successfully
- No connection/inverter start sequence required
- Battery responds to control writes immediately

**Action:** Continue implementing power limits using Model 702/704 WITHOUT worrying about Model 802 connection sequence.

### 2. 🟡 Test Model 703.ES (Grid Connection)

**Hypothesis:** `ES` controls grid connection, not battery connection

**Test Plan:**
1. Read current `ES` value (currently 1)
2. Document current inverter/grid state
3. On non-production system: Write `ES = 3` (CONNECTED)
4. Monitor grid connection status
5. Revert if unexpected behavior

**Risk:** MEDIUM - might trigger grid connection sequence

### 3. 🟡 Test Model 704.WSet (Active Power Setpoint)

**Hypothesis:** `WSetEna` + `WSet` might provide alternative charge/discharge control

**Test Plan:**
1. Enable: `WSetEna = 1`, `WSetMod = 1`
2. Set discharge target: `WSet = 2000` (2kW)
3. Monitor: Does battery discharge at 2kW?
4. Compare with `WDisChaRteMax` approach

**Risk:** LOW - setpoint control should be safe

### 4. ❌ Do NOT Look for Model 802 Equivalents

**Conclusion:** Model 802 functionality is **not exposed** and **not required** for FranklinWH control.

**Instead:** Rely on:
- Model 702: `WChaRteMax`, `WDisChaRteMax` (charge/discharge limits)
- Model 704: `WMaxLimPct`, `WMaxLimPctEna` (percentage limiting)
- Model 704: `WSetEna`, `WSet` (active power setpoint) - needs testing
- FranklinWH Extensions: 15507-15509 (operating mode, reserves)

---

## Updated Control Architecture

```
┌─ FranklinWH Internal Logic ───────────┐
│  • Battery always connected           │
│  • Inverter auto-starts on boot       │
│  • No LocRemCtl requirement           │
│  • No CtrlHb heartbeat required       │
└────────────────────────────────────────┘
                    ↓
┌─ Available SunSpec2 Controls ─────────┐
│                                        │
│  Model 702 (Capacity):                │
│  • WChaRteMax (charge limit)          │
│  • WDisChaRteMax (discharge limit)    │
│                                        │
│  Model 704 (DER AC Controls):         │
│  • WMaxLimPctEna (enable % limit)     │
│  • WMaxLimPct (% limit value)         │
│  • WSetEna (enable setpoint)?         │
│  • WSet (power setpoint)?             │
│                                        │
│  FranklinWH Extensions:                │
│  • 15507 (operating mode)             │
│  • 15508 (self-consumption reserve)   │
│  • 15509 (TOU reserve)                │
└────────────────────────────────────────┘
```

---

## Summary

### Model 802 SetOp/SetInvState Alternatives: ❌ NONE FOUND

| Model 802 Function | Alternative Point | Status |
|-------------------|-------------------|--------|
| `SetOp` (battery connect) | Model 703.ES | 🟡 For grid, not battery |
| `SetInvState` (inverter start) | None found | ❌ Not available |
| `LocRemCtl` (remote enable) | None needed | ✅ Not required |
| `CtrlHb` (heartbeat) | None needed | ✅ Not required |

### Control Strategy: ✅ DIRECT WRITES

**Use Model 702/704 controls directly WITHOUT Model 802 sequence.**

FranklinWH's firmware handles battery connection and inverter state internally, allowing immediate control writes to charge/discharge limits.

---

## Next Steps

1. ✅ Document that Model 802 equivalents are NOT needed for FranklinWH
2. 🔲 Test Model 704.WSetEna + WSet for power setpoint control
3. 🔲 Test Model 703.ES for grid connection behavior (low priority)
4. 🔲 Implement power limiting UI using confirmed working points
5. 🔲 Proceed with heartbeat monitoring (application-level, not SunSpec2)

---

## References

- [Implementation Plan](implementation_plan.md)
- [SunSpec2 Control Points Analysis](sunspec2_control_points_analysis.md)
- SunSpec Model 802 Specification
- SunSpec Model 704 DER AC Controls
- SunSpec Model 703 DER Enter Service
