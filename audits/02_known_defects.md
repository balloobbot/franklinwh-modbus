# Audit: Known Defects in franklinwh_control_standalone.py

> **Audit Date**: 2026-02-21  
> **File**: `franklinwh_control_standalone.py`  
> **Severity**: HIGH / MEDIUM / LOW

---

## 🔴 HIGH SEVERITY

### DEFECT-001: --target-soc Only Works for emergency_backup Mode
**Component**: Virtual Mode Controller  
**Severity**: HIGH  
**Status**: ✅ **FIXED** in commit `tbd`
**Impact**: Users expect target_soc to work across modes, but it only applies to emergency_backup

**Evidence**:
```python
# In VirtualModeController.__init__:
self.backup_target_soc = 95       # Used in _calc_emergency_backup
self.self_reserve_pct = 20        # Different variable for self_consumption
self.manual_power_w = 0           # Manual mode uses this
# NO target_soc for: time_of_use, grid_zero, peak_shave, manual
```

**CLI Help Deception**:
```
--target-soc TARGET_SOC
    Emergency backup target SOC (default: 95)
```
The help says "Emergency backup target SOC" implying it's only for that mode, BUT the examples show:
```bash
# Example implies it might work elsewhere:
--mode manual --power 1500 --duration 7200  # No target_soc mentioned
```

**Expected vs Actual**:
| Mode | --target-soc Expected | --target-soc Actual |
|------|----------------------|---------------------|
| emergency_backup | Target SoC to maintain | ✅ Works (95% default) |
| self_consumption | Minimum reserve SoC | ❌ Uses --reserve (20% default) |
| time_of_use | ? | ❌ Ignored |
| grid_zero | ? | ❌ Ignored |
| peak_shave | ? | ❌ Ignored |
| manual | ? | ❌ Ignored |

**Fix Applied**:
- Added `validate_mode_params()` function that maps parameters to their valid modes
- Validates all mode-specific parameters:
  - `--target-soc` → only `emergency_backup`
  - `--reserve` → only `self_consumption`
  - `--threshold` → only `peak_shave`
  - `--power` → only `manual`
  - `--schedule-file` → only `time_of_use`
- Warns user with helpful message showing:
  - Which parameter is incompatible
  - What mode was selected
  - What parameters ARE valid for that mode
- Non-blocking: script continues but user is informed of ignored parameters

**Validation Output Example**:
```
⚠️  Parameter/Mode Mismatch Warnings:
   • --target-soc=90 is only used by 'emergency_backup' mode, not 'self_consumption'. 
     This parameter will be ignored.

   For mode 'self_consumption', valid parameters are:
   --reserve (reserve percentage)
```

**Recommendation**: 
1. ✅ Document which modes support which parameters — DONE in CLI_OPTIONS.md
2. ✅ Add validation to reject/warn incompatible parameter combinations — DONE
3. Consider unifying target_soc/reserve concepts — Future enhancement

---

### DEFECT-002: Insufficient CLI Output for Operational Verification
**Component**: CLI output / Status reporting  
**Severity**: HIGH  
**Status**: ✅ **FIXED** in commit `1ddeb97`

**Original Issue**: Users could not determine if virtual modes were working without external dashboards

**Fix Applied**:
- Added `_print_telemetry()` method to `VirtualModeController`
- Console output every 5 seconds with:
  - ⏱️ Elapsed time (HH:MM:SS)
  - ⏳ Remaining time (when `--duration` specified)
  - 🎯 Target SoC (mode-dependent display)
  - ☀️ Solar PV production
  - 🏠 Home load estimation
  - ⚡/🔋/💤 Battery state with power
  - ↓/↑/─ Grid import/export/balanced
- Formatted with visual separators and icons
- Added `_format_duration()` and `_get_target_soc_display()` helpers

**New Output Example**:
```
======================================================================
  MODE: SELF_CONSUMPTION
  ────────────────────────────────────────────────────────────────────
  ⏱️  ELAPSED: 00:05:32  |  ⏳ REMAINING: 01:54:28
  🎯 TARGET:   20% reserve
  ────────────────────────────────────────────────────────────────────
  BATTERY:    ⚡ CHARGING        1500W  |  SoC: 75.0%
  SOLAR PV:   ☀️  PRODUCING      2800W  |  
  HOME LOAD:  🏠 CONSUMING      1500W  |  
  GRID:       ↑ EXPORTING         200W
  ────────────────────────────────────────────────────────────────────
  CMD: WSetPct=30.0%  (1500W)
======================================================================
```

**Verification**: See `TELEMETRY_DEMO.md` for full examples

---

## 🟡 MEDIUM SEVERITY

### DEFECT-003: Virtual Mode Calculations Unverified
**Component**: VirtualModeController._calc_* methods  
**Severity**: MEDIUM  
**Impact**: Modes may not behave as documented/intended

**Specific Concerns**:

#### self_consumption Logic
```python
def _calc_self_consumption(self, solar, home, grid, soc):
    excess_solar = solar - home
    # High SOC logic seems inverted?
    if soc > (100 - self.self_reserve_pct):  # > 80% if reserve=20
        if excess_solar > 0:
            return min(excess_solar * 0.5, 1000)  # GENTLE charge?
        else:
            return max(home - solar, -5000)  # Discharge
    # ... more logic
```
**Question**: Should high SOC discharge MORE to make room for solar?

#### time_of_use Logic
```python
def _calc_time_of_use(self, solar, home, grid, soc):
    period = self.get_current_period()
    if period == "peak":
        if soc > self.tou.min_soc:  # min_soc not defined anywhere!
            return -5000  # Discharge
    # ...
```
**Question**: `self.tou.min_soc` doesn't exist - where does this come from?

#### grid_zero Logic
```python
def _calc_grid_zero(self, solar, home, grid, soc):
    # Calculates target battery power to zero grid
    target_battery = solar - home + grid
    # But doesn't account for battery efficiency?
```

**Recommendation**: Each mode needs:
1. Formal specification of expected behavior
2. Unit tests with known inputs/outputs
3. Real-world validation against aGate

---

### DEFECT-004: --duration Parameter Implementation Unclear
**Component**: CLI argument parsing + VirtualModeController  
**Severity**: MEDIUM  
**Impact**: Users specify duration but behavior is undefined

**Code Analysis**:
```python
# In main() - duration is parsed:
parser.add_argument('--duration', type=int, default=None,
                    help='Mode duration in seconds (default: indefinite)')

# But in VirtualModeController:
def run_continuous(self):
    """Run mode controller continuously."""
    while not self._shutdown_requested:
        # No duration check!
        self.tick()
        time.sleep(self.tick_interval)
```

**Questions**:
- Does `--duration 7200` mean "run for 2 hours then stop"?
- Does it mean "revert after 2 hours"?
- Is it even implemented?

**Example shows**:
```bash
--mode manual --power 1500 --duration 7200
```

**Recommendation**: Document or implement the duration behavior.

---

### DEFECT-005: Inconsistent Parameter Naming Across Modes
**Component**: VirtualModeController  
**Severity**: MEDIUM  
**Impact**: Confusing API

**Inconsistencies**:
| Mode | Reserve Parameter | Target Parameter |
|------|-------------------|------------------|
| emergency_backup | N/A | `backup_target_soc` |
| self_consumption | `self_reserve_pct` | N/A (uses reserve) |
| time_of_use | ? | ? |
| grid_zero | N/A | N/A |
| peak_shave | N/A | `peak_shave_threshold` |
| manual | N/A | `manual_power_w` |

**CLI Arguments**:
```bash
--reserve RESERVE              # Self-consumption reserve %
--target-soc TARGET_SOC        # Emergency backup target
--threshold THRESHOLD          # Peak shave threshold
```

**Recommendation**: Unify naming or clarify which args apply to which modes.

---

## 🟢 LOW SEVERITY

### DEFECT-006: --revert Flag Behavior Mismatch with Documentation
**Component**: send_command()  
**Severity**: LOW  
**Impact**: User confusion about auto-revert

**Code Comment**:
```python
# NOTE: WSetRvrtTms is unimplemented per PICS SM-000028.
# Commands persist until explicitly disabled with WSetEna=0.
```

**CLI Help**:
```
--revert REVERT       Auto-revert time in seconds
```

**Mismatch**: Help implies it works, code says it's unimplemented.

---

### DEFECT-007: SPAN Extension Detection Incomplete
**Component**: _detect_span_capability()  
**Severity**: LOW  
**Impact**: Cannot read/write FranklinWH native registers (15507-15509)

**Code**:
```python
def _detect_span_capability(self) -> dict:
    # ...
    result['readable'] = False
    result['note'] = 'Use read_native_mode() for native register access'
```

**Note**: There's a separate `read_native_mode()` that uses raw Modbus, but it's not integrated into the main flow.

---

### DEFECT-008: Exception Handling Too Broad in Some Areas
**Component**: Various try/except blocks  
**Severity**: LOW  
**Impact**: May mask real errors

**Example**:
```python
try:
    m702.read()
    # ...
except Exception as e:
    logger.warning(f"Failed to read M702 ratings: {e}; using defaults")
    # Falls back to hardcoded 5000W
```

**Question**: Should connection errors be treated the same as parse errors?

---

## 📋 Summary Table

| ID | Defect | Severity | Status |
|----|--------|----------|--------|
| DEFECT-001 | --target-soc only for emergency_backup | 🔴 HIGH | ✅ **FIXED** |
| DEFECT-002 | Insufficient CLI output | 🔴 HIGH | ✅ **FIXED** |
| DEFECT-003 | Virtual mode calculations unverified | 🟡 MEDIUM | Test/Verify |
| DEFECT-004 | --duration unclear | 🟡 MEDIUM | Document/Implement |
| DEFECT-005 | Inconsistent parameter naming | 🟡 MEDIUM | Refactor |
| DEFECT-006 | --revert mismatch | 🟢 LOW | Fix docs |
| DEFECT-007 | SPAN detection incomplete | 🟢 LOW | Future work |
| DEFECT-008 | Broad exception handling | 🟢 LOW | Code review |

---

## Recommendations for Library Split

**Before splitting**:
1. ✅ Fix DEFECT-001 (document parameter compatibility)
2. ✅ Fix DEFECT-002 (add telemetry output)
3. ⏸️ Document DEFECT-003 (mode behavior specs)
4. ⏸️ Document DEFECT-004 (duration behavior)

**During split**:
- Preserve working code paths exactly
- Add tests for each defect to prevent regression
- Mark known issues with TODO/FIXME comments

---

*End of Known Defects Audit*
