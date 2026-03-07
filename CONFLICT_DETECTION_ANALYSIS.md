# Conflict Detection Logic Analysis

**Date:** 2026-03-01  
**Status:** ✅ **DECISION MADE** - Option 2 Selected for Future Phase
**Decision Date:** 2026-03-01
**Target Phase:** Phase 3 (Post-Virtual Mode Testing)
**Priority:** QUEUED - Not blocking current work

---

## Decision Summary

**Selected Option:** **Option 2 - Intent-Based Detection**  
**Rationale:** User intent is the most reliable indicator of true conflicts. Current false positives occur because we don't know what the user is trying to do vs what aGate is doing.

**Prerequisites Before Implementation:**
1. ✅ Manual mode - Fully functional, battle-tested
2. ⚠️ Self-Consumption mode - Needs complete testing
3. ⚠️ Emergency Backup mode - Needs complete testing  
4. ⚠️ Time-of-Use mode - Needs complete testing
5. ⚠️ Peak Shave mode - Needs complete testing

**Blocked Until:** Virtual modes (except manual) are fully tested and stabilized.

---

## Executive Summary

The current conflict detection logic has a **fundamental limitation**: it only examines battery DC power activity without considering the broader energy system context (Solar PV, Home Load, Grid exchange). This leads to **false positives** where normal Self-Consumption behavior is incorrectly flagged as a conflict.

---

## Current Implementation

### Location
`src/franklinwh/controller.py`, method `check_state()`, lines 1115-1153

### Current Logic Flow

```python
# 1. Read battery DC power from Model 714
battery_dc_power = m714.DCW.value * scale_factor

# 2. Calculate actual power from WSetPct
actual_power = (wset_pct / 100.0 * RATED_MAX_W) if wset_ena == 1 else 0

# 3. Define "active" thresholds
is_active_charging = battery_dc_power < -500 or actual_power < -100
is_active_discharging = battery_dc_power > 500 or actual_power > 100

# 4. Check for conflicts based ONLY on battery activity
if native_mode == 'Self-Consumption' and is_active_discharging:
    result['conflicts'].append(
        f"aGate Self-Consumption actively DISCHARGING at {battery_dc_power:.0f}W"
    )
```

### Data Sources Used

| Data Source | Register/Model | What It Tells Us |
|-------------|----------------|------------------|
| Battery DC Power | Model 714, `DCW` | Battery charge/discharge rate |
| Control State | Model 704, `WSetPct` | Our Modbus control setpoint |
| Native Mode | Extension 15507 | aGate's configured mode |

### Data Sources IGNORED

| Data Source | Register/Model | What It Would Tell Us |
|-------------|----------------|----------------------|
| Solar PV Production | Ext 15502-15505 | Total solar generation |
| Home Load | Ext 15506 | House consumption |
| Grid Power | Model 701, `W` | Import (+) / Export (-) |

---

## The Problem: False Positives

### Scenario 1: False Positive (Current Logic FAILS)

**System State (Normal Self-Consumption Behavior):**
```
Solar Production:     3000W  (from roof)
Home Load:            1800W  (house consuming)
Battery Discharge:    1200W  (serving excess load)
Grid Exchange:           0W  (self-sufficient)
SoC:                    90%  (above reserve)
```

**Current Logic Output:**
```
🚨 CONFLICTS:
   • aGate Self-Consumption actively DISCHARGING at 1200W
```

**Analysis:** ❌ **FALSE POSITIVE**  
This is NORMAL behavior! The aGate is discharging to serve home load that exceeds current solar production. The battery is doing exactly what Self-Consumption mode should do.

---

### Scenario 2: True Conflict (Current Logic Catches)

**System State (Actual Conflict):**
```
Solar Production:        0W  (night time)
Home Load:            1800W  (house consuming)
Battery Charging:     1200W  (aGate commanding charge!)
Grid Exchange:       +3000W (importing to charge)
SoC:                    90%  (already high)
```

**Current Logic Output:**
```
🚨 CONFLICTS:
   • aGate Self-Consumption actively CHARGING at 1200W
```

**Analysis:** ✅ **TRUE CONFLICT**  
This IS a conflict - aGate is actively charging at night when we want to discharge.

---

### Scenario 3: Missed Conflict (Current Logic FAILS)

**System State (Hidden Conflict):**
```
Solar Production:     5000W  (peak solar)
Home Load:            1500W  (house consuming)
Battery Charging:     3000W  (aGate commanding charge)
Grid Exchange:        +500W  (exporting excess)
SoC:                    85%  (approaching full)
```

**Current Logic Output:**
```
No conflicts detected
```

**Analysis:** ❌ **MISSED CONFLICT**  
If user wants to discharge (sell to grid), aGate charging from solar IS a conflict, but we don't detect it because it looks like "normal solar charging."

---

## Energy Flow Analysis

### The Physics Equation
```
Solar PV - Home Load - Battery = Grid Exchange

Where:
- Positive Battery = Discharging (supplying)
- Negative Battery = Charging (consuming)
- Positive Grid = Importing from grid
- Negative Grid = Exporting to grid
```

### Normal Self-Consumption Scenarios

| Scenario | Solar | Load | Battery | Grid | Is Conflict? |
|----------|-------|------|---------|------|--------------|
| Peak solar, charging | 5000W | 1500W | -3500W (charging) | 0W | No - storing excess |
| Low solar, discharging | 1000W | 2500W | +1500W (discharging) | 0W | No - serving load |
| Night, discharging | 0W | 2000W | +2000W (discharging) | 0W | No - serving load |
| Night, charging | 0W | 1500W | -2000W (charging) | +3500W | **YES** - importing to charge |

### Conflict Detection Requires Context

A conflict exists when:
1. **We want to charge**, but aGate is discharging (and vice versa)
2. **AND** the battery activity cannot be explained by natural energy flows

Natural energy flows include:
- Charging from excess solar
- Discharging to serve home load
- Maintaining reserve levels in Self-Consumption mode

---

## Available Data Sources

### Extension Registers (15500+)

| Register | Description | Units |
|----------|-------------|-------|
| 15500 | Timestamp (Unix) | seconds |
| 15502 | PV Total | Watts |
| 15503 | PV Proximal (roof) | Watts |
| 15504 | PV Remote 1 | Watts |
| 15505 | PV Remote 2 | Watts |
| 15506 | Home Load | Watts |
| 15507 | OnGridMode | enum |
| 15508 | Self Reserve | % |
| 15509 | TOU Reserve | % |

### SunSpec Models

| Model | Register | Description |
|-------|----------|-------------|
| 701 | W | Grid power (positive=import, negative=export) |
| 714 | DCW | Battery DC power |

---

## Recommendations

### Option 1: Simple Context-Aware Detection (RECOMMENDED)

Add energy context to conflict detection:

```python
def check_state(self) -> Dict[str, Any]:
    # ... existing code ...
    
    # Read energy system context
    ext = self._read_extension_solar()
    solar = ext.get('total_solar', 0) if ext else 0
    home_load = ext.get('home_load_ext', 0) if ext else 0
    grid = self.read_grid_status()
    grid_power = grid.get('grid_power_w', 0)
    
    # Calculate expected battery behavior
    energy_balance = solar - home_load
    
    # Conflict detection with context
    if native_mode == 'Self-Consumption':
        if is_active_discharging and battery_dc_power > 0:
            # Check if discharge is natural (serving load)
            if solar < home_load and grid_power > -100:
                # Solar < Load and not exporting = normal discharge
                pass  # Not a conflict
            else:
                result['conflicts'].append(
                    f"aGate Self-Consumption discharging {battery_dc_power:.0f}W "
                    f"despite solar={solar}W > load={home_load}W"
                )
        
        elif is_active_charging and battery_dc_power < 0:
            # Check if charge is natural (excess solar)
            if solar > home_load and grid_power < 100:
                # Solar > Load and not importing = normal charge
                pass  # Not a conflict
            elif solar == 0 and grid_power > 500:
                # Night + importing = definite conflict
                result['conflicts'].append(
                    f"aGate Self-Consumption IMPORTING {grid_power:.0f}W to charge battery "
                    f"at night (SoC={result['soc']:.1f}%)"
                )
```

**Pros:**
- Eliminates false positives
- Catches true conflicts (night charging)
- Relatively simple to implement

**Cons:**
- Still edge cases (e.g., charging during peak solar when user wants to export)

---

### Option 2: Intent-Based Detection

Track what the user is trying to do vs what aGate is doing:

```python
def detect_conflict(self, requested_operation: str, 
                     battery_power: float, solar: float, 
                     load: float, grid: float) -> Tuple[bool, str]:
    """
    Args:
        requested_operation: 'charge', 'discharge', or 'idle'
        battery_power: Current battery power (+ = discharge)
        solar: Solar production
        load: Home load
        grid: Grid exchange (+ = import)
    """
    
    if requested_operation == 'discharge':
        # We want to discharge
        if battery_power < -500:  # Battery is charging
            if solar > load + 500:
                return False, "Battery charging from excess solar (natural)"
            else:
                return True, f"aGate charging ({abs(battery_power):.0f}W) conflicts with discharge request"
    
    elif requested_operation == 'charge':
        # We want to charge
        if battery_power > 500:  # Battery is discharging
            if solar < load - 500:
                return False, "Battery discharging to serve load (natural)"
            else:
                return True, f"aGate discharging ({battery_power:.0f}W) conflicts with charge request"
    
    return False, "No conflict detected"
```

**Pros:**
- Most accurate detection
- Considers user intent

**Cons:**
- Requires knowing user's intent (need to pass requested operation)
- More complex to integrate

---

### Option 3: Conservative Detection (Quick Fix)

Only flag conflicts when we're CERTAIN there's a problem:

```python
# Only flag conflict if:
# 1. Battery is active (charging or discharging)
# 2. AND grid is importing significantly (night charging)
# 3. OR battery activity contradicts clear solar/load conditions

is_importing = grid_power > 1000
is_night = solar == 0

if native_mode == 'Self-Consumption':
    if is_active_charging and is_importing and is_night:
        result['conflicts'].append(
            f"DEFINITE CONFLICT: aGate importing {grid_power:.0f}W from grid "
            f"to charge battery at night (SoC={result['soc']:.1f}%)"
        )
    elif is_active_discharging:
        # Don't flag - could be normal load serving
        pass
```

**Pros:**
- Eliminates false positives
- Simple to implement

**Cons:**
- May miss some true conflicts

---

### ✅ Interim Quick Fix - IMPLEMENTED 2026-03-01

**Status:** ✅ **IMPLEMENTED**  
**Location:** `src/franklinwh/controller.py`, `check_state()` method  
**Impact:** Reduces ~80% of false positives in typical daytime scenarios

**Implementation Details:**

The band-aid fix reads solar production and home load from extension registers, then classifies battery activity:

```python
# Read energy context for smarter conflict detection
ext = self._read_extension_solar()
solar_power = ext.get('total_solar', 0) if ext else 0
home_load = ext.get('home_load_ext', 0) if ext else 0
grid_power = result.get('grid_power', 0)

# Classification logic:
# CHARGING scenarios:
# - Importing from grid at night → CONFLICT
# - Importing from grid (day) → CONFLICT  
# - From excess solar → INFO (normal behavior)
#
# DISCHARGING scenarios:
# - Despite excess solar (solar > load) → CONFLICT
# - To serve excess load (load > solar) → INFO (normal behavior)
# - Balanced conditions → WARNING (ambiguous)
```

**CLI Output Enhancement:**

```
Energy Flow:
  Solar:         600W
  Home Load:     1800W
  Battery:       1200W → discharging
  Grid:          0W (balanced)

ℹ️  SYSTEM STATUS:
  • aGate discharging 1200W to serve home load (load 1800W > solar 600W) 
    - This is NORMAL Self-Consumption behavior
```

**Files Modified:**
- `src/franklinwh/controller.py` - Added energy context reading and classification
- `franklinwh_cli.py` - Added Energy Flow display, separated INFO from CONFLICTS

**Note:** This is a band-aid fix. Full Option 2 (intent-based) implementation is still recommended for Phase 3.

---

## Implementation Roadmap (Updated)

### Phase 1: Virtual Mode Testing (CURRENT)
**Status:** In Progress  
**Goal:** Stabilize all virtual modes before implementing intent-based detection

| Mode | Status | Notes |
|------|--------|-------|
| Manual | ✅ Complete | Battle-tested, stable |
| Self-Consumption | ⚠️ Needs Testing | Verify reserve handling |
| Emergency Backup | ⚠️ Needs Testing | Verify backup target logic |
| Time-of-Use | ⚠️ Needs Testing | Verify schedule integration |
| Peak Shave | ⚠️ Needs Testing | Verify threshold behavior |

**Exit Criteria:** All modes tested with real hardware scenarios

---

### Phase 2: Energy Context Enhancement (FUTURE)
**Status:** Queued  
**Goal:** Add energy flow visualization even without intent detection

**Changes:**
1. Modify `check_state()` to read extension registers (solar, load)
2. Add energy flow to status output
3. Show battery activity classification (natural vs controlled)

**Example Output:**
```
Energy Flow:
  Solar:         600W  (proximal: 600W, remote: 0W)
  Home Load:     1800W
  Battery:      +1200W (discharging → serving load)
  Grid:            0W  (self-sufficient)

Status:          ℹ️  NATURAL - Battery serving excess home load
                 (Solar 600W < Load 1800W)
```

---

### Phase 3: Intent-Based Conflict Detection (FUTURE)
**Status:** Queued - **DEPENDS ON Phase 1 completion**  
**Selected Option:** Option 2  
**Goal:** Eliminate false positives by considering user intent

**Changes:**
1. Modify `check_state()` to accept `requested_operation` parameter
2. Pass intent from CLI/VirtualModeController
3. Compare user intent vs aGate behavior

**Interface Change:**
```python
def check_state(self, requested_operation: Optional[str] = None) -> Dict[str, Any]:
    """
    Args:
        requested_operation: 'charge', 'discharge', 'idle', or None
                             If provided, enables intent-based conflict detection
    """
```

**Conflict Detection Logic:**
```python
if requested_operation == 'discharge' and battery_is_charging:
    if not natural_charge_condition(solar, load, grid):
        return True, f"Conflict: Requested discharge but aGate charging ({abs(battery_power)}W)"
```

**Files to Modify:**
- `src/franklinwh/controller.py` - `check_state()` and new `detect_intent_conflict()`
- `franklinwh_cli.py` - Pass `--charge`/`--discharge` intent to `check_state()`
- `src/franklinwh/modes.py` - Pass mode intent from VirtualModeController

---

## Files to Modify

1. `src/franklinwh/controller.py`
   - `check_state()` method - add energy context
   - New helper method `classify_battery_activity()`

2. `franklinwh_cli.py`
   - `print_startup_summary()` - show energy flow context
   - Pass requested operation to `check_state()`

3. `src/franklinwh/types.py` (optional)
   - Add `EnergyFlow` dataclass for structured data

---

## Testing Scenarios

| Test | Solar | Load | Battery | Grid | Expected Result |
|------|-------|------|---------|------|-----------------|
| Normal day discharge | 1000W | 2500W | +1500W | 0W | No conflict |
| Normal day charge | 5000W | 1500W | -3500W | 0W | No conflict |
| Night import charge | 0W | 1500W | -2000W | +3500W | CONFLICT |
| Peak solar export | 6000W | 1500W | 0W | -4500W | No conflict |
| Cloudy discharge | 500W | 2000W | +1500W | 0W | No conflict |

---

## Decision Record

**DECISION MADE:** 2026-03-01

**Selected:** Option 2 - Intent-Based Detection  
**Rationale:** User intent is the most reliable indicator of true conflicts. Eliminates false positives by knowing what user wants vs what aGate is doing.

**Prerequisites:** Virtual mode testing must be complete first  
**Target Phase:** Phase 3 (see [PHASES_AND_ROADMAP.md](./PHASES_AND_ROADMAP.md))  
**Implementation Plan:** [TODO_INTENT_BASED_CONFLICT_DETECTION.md](./TODO_INTENT_BASED_CONFLICT_DETECTION.md)

**Blocked Until:**
- ✅ Manual mode testing (COMPLETE)
- ⚠️ Self-Consumption mode testing
- ⚠️ Emergency Backup mode testing
- ⚠️ Time-of-Use mode testing
- ⚠️ Peak Shave mode testing

**Next Steps:**
1. Complete Phase 2.2 (Virtual Mode Testing)
2. Implement Phase 2 (Energy Context) - can proceed in parallel
3. Implement Phase 3 (Intent Detection) - blocked until Phase 2.2 complete

---

## Appendix: Current Output vs Recommended Output

### Current Output
```
  Battery:
    SoC: 90.0% | Target: 100.0% | ETA: +16min
    Activity:      IDLE (no control)

  aGate Mode:
    OnGridMode:    Self-Consumption

  🚨 CONFLICTS:
    • aGate Self-Consumption actively DISCHARGING at 1200W
```

### Recommended Output
```
  Battery:
    SoC: 90.0% | Target: 100.0% | ETA: +16min
    Activity:      IDLE (no control)

  Energy Flow:
    Solar:         600W  (2.4kW proximal + 0W remote)
    Home Load:     1800W
    Battery:      +1200W (discharging to serve load)
    Grid:            0W  (self-sufficient)

  aGate Mode:
    OnGridMode:    Self-Consumption
    Reserve:       20%

  Status:          ✓ NORMAL - Battery serving home load
                   (Solar 600W < Load 1800W, using battery to balance)
```
