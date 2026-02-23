# FranklinWH Control Library - Audit Summary

> **Audit Date**: 2026-02-21  
> **Scope**: `franklinwh_control_standalone.py`  
> **Purpose**: Baseline assessment before library split

---

## 📁 Audit Files

| File | Contents | Key Findings |
|------|----------|--------------|
| [01_working_features.md](./01_working_features.md) | Verified working features | Manual mode ✅, Health check ✅, Virtual modes ⚠️ partial |
| [02_known_defects.md](./02_known_defects.md) | Documented defects | 8 defects identified (2 HIGH, 3 MEDIUM, 3 LOW) |
| [03_code_analysis.md](./03_code_analysis.md) | TODOs & placeholders | 10 placeholders, 1 undefined variable (`self.tou.min_soc`) |
| [04_hardware_required.md](./04_hardware_required.md) | Testing requirements | Read-only tests safe, write tests need monitoring |

---

## 🎯 Executive Summary

### Current State: FUNCTIONAL BUT ROUGH

**The Good**:
- ✅ Core Modbus communication is solid
- ✅ Manual power control works reliably
- ✅ Health check provides good diagnostics
- ✅ Safety mechanisms in place (clamping, bounds checking)

**The Concerns**:
- ⚠️ Virtual modes largely untested/unverified
- ⚠️ CLI output insufficient for operational confidence
- ⚠️ Parameter compatibility unclear (which args work with which modes)
- ⚠️ Code needs cleanup before library split

**The Plan**:
1. **Document** current state ✅ (this audit)
2. **Fix critical defects** before split (DEFECT-001, DEFECT-002) ✅
3. **Add basic telemetry** to CLI output ✅
4. **Split** into library + CLI ← **NEXT**
5. **Add tests** using established patterns

---

## 🔴 Critical Issues (Fix Before Split)

### DEFECT-001: --target-soc Only for emergency_backup ✅ **FIXED**
**Impact**: Users try invalid parameter combinations  
**Fix**: Add validation, document compatible params per mode  
**Status**: Validation added - warns user of incompatible parameters

### DEFECT-002: Insufficient CLI Output ✅ **FIXED**
**Impact**: Cannot verify if modes are working  
**Fix**: Add telemetry display (home load, solar, elapsed time, etc.)  
**Status**: Comprehensive telemetry output added with `_print_telemetry()`

---

## 📊 Risk Assessment for Library Split

| Risk | Level | Mitigation |
|------|-------|------------|
| Breaking working manual mode | HIGH | Preserve code exactly, add tests first |
| Losing health check functionality | MEDIUM | Extract as-is, test thoroughly |
| Virtual mode regressions | LOW | They don't work well now anyway |
| CLI argument changes | MEDIUM | Maintain backward compatibility |
| Import path changes | LOW | Document migration path |

---

## ✅ Pre-Split Checklist

### Must Have
- [x] Document current state (audits complete)
- [x] Fix DEFECT-001 (parameter validation)
- [x] Fix DEFECT-002 (CLI telemetry)
- [x] Fix undefined `self.tou.min_soc` ✅ **FIXED** - Now uses `get_min_soc()` method
- [x] Create minimal pytest infrastructure ✅ **DONE** - pytest.ini, conftest.py, fixtures
- [x] Add one integration test as template ✅ **DONE** - 13 integration tests, 10 unit tests

### Should Have
- [ ] Add explicit error for unsupported arg combinations
- [ ] Document each virtual mode's expected behavior
- [ ] Test manual mode with telemetry output
- [ ] Create migration guide for CLI users

### Nice to Have
- [ ] Test all virtual modes with real aGate
- [ ] Add unit tests for calculation logic
- [ ] Add hardware test suite
- [ ] CI/CD integration

---

## 🚀 Recommended Next Steps

### Option A: Conservative (Recommended)
1. Fix the 2 critical defects
2. Add basic telemetry to CLI
3. Create pytest infrastructure
4. Split library with minimal changes
5. Add comprehensive tests after split

### Option B: Thorough
1. Test every virtual mode with real aGate first
2. Document exact behavior of each mode
3. Fix all defects
4. Add full test coverage
5. Then split library

### Option C: Quick Split
1. Split immediately with no changes
2. Accept potential regressions
3. Fix issues as they're found
4. Add tests incrementally

**Recommendation**: Option A - Fix critical issues, then split with tests to prevent regressions.

---

## 📈 Post-Split Architecture

```
franklinwh_modbus_library.py (importable)
├── FranklinWHController (core hardware interface)
│   ├── connect/disconnect
│   ├── read_battery/grid/solar/control_status
│   ├── send_command (power control)
│   ├── healthcheck
│   └── reset_control_state
├── VirtualModeController (automated modes)
│   ├── set_mode / execute_once / run_continuous
│   ├── calculate_power (per mode)
│   └── read_status (telemetry)
├── TOUSchedule (time-of-use rates)
└── dataclasses: BatteryCommand, HealthStatus

franklinwh_modbus_cli.py (command-line tool)
├── argparse setup
├── main() orchestration
├── status display formatting
└── imports from library
```

---

## 🧪 Testing Strategy Post-Split

| Component | Test Type | Priority |
|-----------|-----------|----------|
| FranklinWHController.connect() | Hardware + Mock | HIGH |
| send_command() 4-step | Hardware + Mock | HIGH |
| healthcheck() | Hardware + Mock | HIGH |
| VirtualModeController._calc_* | Unit tests | MEDIUM |
| VirtualModeController modes | Hardware | MEDIUM |
| CLI argument parsing | Unit tests | HIGH |
| CLI output formatting | Unit tests | MEDIUM |

---

## 📚 Key Files for Library Split

| File | Purpose | Lines | Complexity |
|------|---------|-------|------------|
| `franklinwh_control_standalone.py` | Current monolithic | ~1,690 | HIGH |
| `src/models.py` | Data classes | ~105 | LOW |
| `src/modbus_client.py` | Web app Modbus client | ~400 | MEDIUM |

**Lines to extract for library**: ~800 (controller + virtual modes + support classes)
**Lines for CLI**: ~200 (argparse + output formatting)
**Tests to write**: ~50 unit + 20 integration + 15 hardware

---

## 💡 Key Insights from Audit

1. **Manual mode is the golden path** - It's verified working and should be preserved exactly
2. **Virtual modes need validation** - They're implemented but not verified against real hardware
3. **CLI needs telemetry** - Biggest user pain point is not knowing if it's working
4. **Safety code is good** - The clamping, bounds checking, and reset logic is solid
5. **Documentation gaps** - Users don't know which parameters work with which modes

---

## 📞 Questions for User

1. **Which virtual modes are most important?** (prioritize testing)
2. **Should we fix DEFECT-002 (telemetry) before or after split?**
3. **Do you want to test virtual modes with real aGate before splitting?**
4. **Backward compatibility: Must CLI args stay identical?**
5. **Timeline: Any urgency on the library split?**

---

## 🎬 Immediate Actions Available

I can proceed with any of these:

1. **Fix DEFECT-001** - Add parameter validation
2. **Fix DEFECT-002** - Add telemetry output
3. **Fix `self.tou.min_soc`** - Define or remove
4. **Setup pytest** - Create test infrastructure
5. **Split the library** - Perform the extraction

**What's your priority?**

---

*End of Audit Summary*
