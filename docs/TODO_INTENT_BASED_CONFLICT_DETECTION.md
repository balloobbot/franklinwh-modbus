# TODO: Intent-Based Conflict Detection

**Status:** 🟡 QUEUED - Future Phase  
**Created:** 2026-03-01  
**Depends On:** Virtual Mode Testing Complete (all modes except manual)  
**Selected Option:** Option 2 - Intent-Based Detection  
**Analysis Document:** [CONFLICT_DETECTION_ANALYSIS.md](./CONFLICT_DETECTION_ANALYSIS.md)

---

## Overview

Implement intent-based conflict detection (Option 2 from analysis) to eliminate false positives in conflict detection. Currently, the system flags battery activity as "conflict" without considering whether the activity is natural (serving home load, charging from excess solar) or truly conflicting with user intent.

---

## Prerequisites (MUST COMPLETE FIRST)

### Phase 1: Virtual Mode Testing (BLOCKING)

Before implementing intent-based detection, all virtual modes must be fully tested and stabilized:

| Mode | Status | Test Requirements | Hardware Test Needed |
|------|--------|-------------------|---------------------|
| **Manual** | ✅ Complete | N/A (already stable) | N/A |
| **Self-Consumption** | ⚠️ **NEEDS TESTING** | - Reserve level handling<br>- Night discharge behavior<br>- Solar priority logic | Yes - Full day cycle |
| **Emergency Backup** | ⚠️ **NEEDS TESTING** | - Backup target charging<br>- Reserve enforcement<br>- Grid outage response | Yes - Simulate outage |
| **Time-of-Use** | ⚠️ **NEEDS TESTING** | - Schedule transitions<br>- Rate boundary handling<br>- Reserve respect | Yes - Multi-period test |
| **Peak Shave** | ⚠️ **NEEDS TESTING** | - Threshold triggering<br>- Discharge rate limiting<br>- Grid import prevention | Yes - Peak load event |

**Exit Criteria for Phase 1:**
- [ ] All modes tested on real hardware
- [ ] Mode behavior documented
- [ ] Edge cases identified and handled
- [ ] Bug fixes applied and verified

---

## Implementation Plan

### Phase 2: Energy Context Enhancement (FUTURE)

**Goal:** Add energy flow visualization

**Changes:**
1. Extend `check_state()` to read extension registers:
   - Solar PV production (15502-15505)
   - Home load consumption (15506)
   - Grid import/export (Model 701)

2. Add energy flow display to status output
3. Classify battery activity as:
   - `NATURAL` - Explained by solar/load/grid balance
   - `CONTROLLED` - aGate actively managing via Cloud API

**Example Output:**
```
Energy Flow:
  Solar:         600W  (proximal: 600W, remote: 0W)
  Home Load:     1800W
  Battery:      +1200W (discharging → serving load)
  Grid:            0W  (self-sufficient)

Status:          ℹ️  NATURAL - Battery serving excess home load
```

---

### Phase 3: Intent-Based Conflict Detection (FUTURE)

**Goal:** Eliminate false positives by comparing user intent vs aGate behavior

**Interface Changes:**

```python
# src/franklinwh/controller.py

def check_state(
    self, 
    requested_operation: Optional[str] = None
) -> Dict[str, Any]:
    """Check current system state with optional intent-based conflict detection.
    
    Args:
        requested_operation: User's intended operation
            - 'charge' - User wants to charge battery
            - 'discharge' - User wants to discharge battery  
            - 'idle' - User wants battery idle
            - None - No intent, report all activity (current behavior)
    
    Returns:
        Dict with state info and conflicts (if intent provided)
    """
    
def detect_intent_conflict(
    self,
    requested: str,  # 'charge', 'discharge', 'idle'
    battery_power: float,
    solar: float,
    load: float,
    grid: float,
    soc: float
) -> Tuple[bool, str, dict]:
    """Detect if aGate behavior conflicts with user intent.
    
    Returns:
        (is_conflict, message, context_dict)
    """
```

**CLI Integration:**

```python
# franklinwh_cli.py

# Pass intent to check_state()
if args.charge is not None:
    state = ctrl.check_state(requested_operation='charge')
elif args.discharge is not None:
    state = ctrl.check_state(requested_operation='discharge')
else:
    state = ctrl.check_state()  # No intent, current behavior
```

**Virtual Mode Integration:**

```python
# src/franklinwh/modes.py

class VirtualModeController:
    def check_mode_conflicts(self) -> List[str]:
        """Check for conflicts specific to current mode."""
        mode_to_intent = {
            VirtualMode.SELF_CONSUMPTION: 'optimize',  # Special handling
            VirtualMode.EMERGENCY_BACKUP: 'charge',    # Always charging to target
            VirtualMode.TIME_OF_USE: 'schedule_based', # Follow TOU schedule
            VirtualMode.PEAK_SHAVE: 'discharge',       # Discharge when peak
            VirtualMode.MANUAL: self.manual_power_w > 0 and 'charge' or 'discharge',
        }
        # ...
```

---

## Conflict Detection Rules

### Natural Activity (NOT a conflict)

| Scenario | Solar | Load | Battery | Grid | Classification |
|----------|-------|------|---------|------|----------------|
| Excess solar charging | 5000W | 1500W | -3500W | 0W | Natural |
| Load serving discharge | 1000W | 2500W | +1500W | 0W | Natural |
| Night load serving | 0W | 2000W | +2000W | 0W | Natural |
| Export from solar | 6000W | 1500W | 0W | -4500W | Natural |

### True Conflicts (IS a conflict)

| Scenario | Solar | Load | Battery | Grid | User Intent | Classification |
|----------|-------|------|---------|------|-------------|----------------|
| Night import charge | 0W | 1500W | -2000W | +3500W | discharge | **CONFLICT** |
| Forced charge at peak | 0W | 5000W | -3000W | +8000W | discharge | **CONFLICT** |
| Discharge while charging | 5000W | 1000W | -4000W | 0W | discharge | **CONFLICT** |
| Charge while discharging | 0W | 500W | +1000W | -500W | charge | **CONFLICT** |

---

## Files to Modify

1. **src/franklinwh/controller.py**
   - `check_state()` - Add `requested_operation` parameter
   - New `detect_intent_conflict()` method
   - New `_is_natural_battery_activity()` helper

2. **franklinwh_cli.py**
   - Pass intent flags to `check_state()`
   - Update conflict display logic

3. **src/franklinwh/modes.py**
   - Pass mode intent to controller
   - Mode-specific conflict detection

4. **src/franklinwh/types.py** (optional)
   - Add `UserIntent` enum
   - Add `EnergyFlow` dataclass

---

## Testing Plan

### Unit Tests

```python
def test_natural_discharge_not_conflict():
    """Battery discharging to serve load should not be conflict."""
    ctrl = FranklinWHController(...)
    is_conflict, msg, _ = ctrl.detect_intent_conflict(
        requested='discharge',
        battery_power=+1500,  # Discharging
        solar=1000,
        load=2500,
        grid=0,
        soc=50
    )
    assert not is_conflict, "Natural load-serving discharge is not a conflict"

def test_night_charge_with_discharge_intent_is_conflict():
    """Charging from grid at night when user wants discharge IS conflict."""
    is_conflict, msg, _ = ctrl.detect_intent_conflict(
        requested='discharge',
        battery_power=-2000,  # Charging
        solar=0,
        load=1500,
        grid=3500,  # Importing
        soc=90
    )
    assert is_conflict, "Night grid charging conflicts with discharge intent"
```

### Hardware Test Scenarios

| Test | Conditions | Expected |
|------|------------|----------|
| Solar noon charge | 5kW solar, 1kW load, charge intent | No conflict |
| Evening discharge | 0W solar, 3kW load, discharge intent | No conflict |
| Night conflict | 0W solar, 2kW load, discharge intent, aGate charging | Conflict detected |
| Peak shave | 0W solar, 5kW load, discharge intent, aGate charging | Conflict detected |

---

## Current Status

### Blocked By
- [ ] Self-Consumption mode testing
- [ ] Emergency Backup mode testing  
- [ ] Time-of-Use mode testing
- [ ] Peak Shave mode testing

### Ready to Start
- [ ] Energy context display (Phase 2) - Can proceed independently

### Not Started
- [ ] Intent detection interface design
- [ ] Unit tests
- [ ] Hardware validation

---

## Notes

- **Priority:** This is a quality-of-life improvement, not blocking current operations
- **Impact:** Will significantly reduce false positive conflicts in status display
- **Risk:** Low - additive feature, doesn't change existing working code
- **Alternative:** Keep current simple detection until Phase 1 complete

---

## Related Documents

- [CONFLICT_DETECTION_ANALYSIS.md](./CONFLICT_DETECTION_ANALYSIS.md) - Full analysis
- [SOC_VALIDATION_IMPLEMENTATION.md](./SOC_VALIDATION_IMPLEMENTATION.md) - Related SoC work
- [VPP_MODE_DISCOVERY.md](./VPP_MODE_DISCOVERY.md) - Virtual mode documentation
