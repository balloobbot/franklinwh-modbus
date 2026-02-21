# Audit: Code Analysis - TODOs, Placeholders & Unimplemented Features

> **Audit Date**: 2026-02-21  
> **File**: `franklinwh_control_standalone.py`  
> **Lines of Code**: ~1,690

---

## 🔍 Annotated Code Findings

### 1. Cloud API Integration (Lines 50-56)
```python
# Lines 50-56
# Future cloud integration (v2.0+)
# try:
#     from franklinwh_cloud import FranklinWHCloudClient
#     CLOUD_API_AVAILABLE = True
# except ImportError:
#     CLOUD_API_AVAILABLE = False
CLOUD_API_AVAILABLE = False  # PLANNED for v2.0
```
**Status**: PLACEHOLDER - Entirely commented out  
**Impact**: No cloud functionality available  
**Library Split**: Can remove for v1.0, add back in v2.0

---

### 2. SPAN Extension Write Access (Line 146)
```python
# Line 146
# FranklinWH SPAN extension registers (15500+)
# NOTE: Write access requires installer-enabled "SPAN Modbus" option
```
**Status**: DOCUMENTATION NOTE  
**Impact**: Read-only without installer intervention  
**Action**: Add to documentation, not a code issue

---

### 3. Cloud API Status Placeholder (Line 442)
```python
# Line 442
# 7. Cloud API status (placeholder)
checks['cloud_api'] = {
    'available': CLOUD_API_AVAILABLE,
    'status': 'Not implemented in current release',
    'span_enabled': None,  # Would come from cloud
}
```
**Status**: PLACEHOLDER  
**Impact**: Health check reports "not implemented"  
**Library Split**: Keep as informative placeholder

---

### 4. SPAN Capability Detection (Lines 494-496)
```python
# Lines 494-496
# Note: sunspec2 doesn't expose raw register access easily
# Now handled by read_native_mode() using raw Modbus TCP
result['readable'] = False
result['note'] = 'Use read_native_mode() for native register access'
```
**Status**: WORKAROUND DOCUMENTED  
**Impact**: `_detect_span_capability()` returns False, but `read_native_mode()` works  
**Action**: Consider merging these functions or updating API

---

### 5. M715 Register Limitations (Lines 551-552)
```python
# Lines 551-552
NOTE: M715 registers (OpCtl, ControllerHb) reject writes on current firmware.
NOTE: WSetRvrtTms is unimplemented per PICS SM-000028.
```
**Status**: DOCUMENTED LIMITATION  
**Impact**: Cannot use heartbeat or operational control registers  
**Library Split**: Document in API docs

---

### 6. WSetRvrtTms Unimplemented (Line 691)
```python
# Line 691
# NOTE: WSetRvrtTms is unimplemented per PICS SM-000028.
# Commands persist until explicitly disabled with WSetEna=0.
```
**Status**: HARDWARE LIMITATION (not code issue)  
**Impact**: No auto-timeout on commands  
**Library Split**: Document prominently

---

### 7. CLI Output Notes (Lines 1301, 1308, 1473, 1517)
```python
# Line 1301
print(f"  Note:                 SPAN extensions require installer unlock")

# Line 1308  
print(f"  Note:                 Planned for v2.0 release")

# Line 1473
print(f"  Note:              M713.Sta always reports IDLE (firmware bug)")

# Line 1517
print(f"  Note:              Local mode — advanced registers locked")
```
**Status**: INFORMATIONAL OUTPUT  
**Impact**: None - just user information

---

### 8. SystemExit Handler (Line 1675)
```python
# Lines 1673-1675
except SystemExit:
    # Graceful shutdown handled
    pass
```
**Status**: CORRECT  
**Impact**: None - appropriate handling

---

## 📊 Placeholder Analysis Summary

| Category | Count | Severity | Action |
|----------|-------|----------|--------|
| Cloud API | 2 | LOW | Remove for v1.0 |
| SPAN Extensions | 3 | LOW | Document only |
| M715/M704 Limitations | 3 | MEDIUM | Document prominently |
| Firmware bugs | 1 | INFO | Keep note |
| Correct handling | 1 | N/A | No action |

**Total Placeholders**: ~10  
**Critical to Address**: 0  
**Documentation Needed**: 6

---

## 🔧 Unimplemented / Partial Methods

### Method: `_detect_span_capability()`
**Location**: Lines 478-505  
**Status**: PARTIAL  
**Issue**: Always returns `readable: False` even though `read_native_mode()` works  
**Recommendation**: Deprecate or integrate with `read_native_mode()`

### Method: `read_native_mode()`
**Location**: Lines 507-540  
**Status**: WORKING BUT ISOLATED  
**Issue**: Uses raw socket access, separate from main API  
**Recommendation**: Consider making primary method, document socket approach

### Virtual Mode: `_calc_time_of_use()`
**Location**: ~Line 950+  
**Status**: USES UNDEFINED ATTRIBUTE  
```python
if soc > self.tou.min_soc:  # ERROR: min_soc doesn't exist!
```
**Recommendation**: Define `min_soc` in TOUSchedule or fix logic

### Virtual Mode: `_calc_peak_shave()`
**Location**: ~Line 1000+  
**Status**: IMPLEMENTED BUT UNTESTED  
**Issue**: Logic present but no validation  
**Recommendation**: Add unit tests

### Virtual Mode: `_calc_grid_zero()`
**Location**: ~Line 980+  
**Status**: IMPLEMENTED BUT UNTESTED  
**Issue**: No efficiency factor in calculation  
**Recommendation**: Test with real aGate

---

## 📋 Hardcoded Values That Should Be Configurable

| Value | Location | Current | Should Be |
|-------|----------|---------|-----------|
| Default timeout | `__init__` | 10.0s | Configurable |
| Rated max W | Class attribute | 5000W | Auto-detected (works) or config |
| Tick interval | VirtualModeController | 5s | Configurable |
| SoC safe bounds | healthcheck | 5-99% | Configurable |
| Grid voltage limits | healthcheck | 220-260V | From M703 or config |
| Grid freq limits | healthcheck | 47-53Hz | From M703 or config |

---

## ⚠️ Code Smells

### 1. Broad Exception Handling
```python
# Lines 631-632
except Exception as e:
    logger.warning(f"Failed to read M702 ratings: {e}; using defaults")
```
**Issue**: Catches everything including syntax errors  
**Fix**: Catch specific exceptions (`ModbusException`, `AttributeError`)

### 2. Mixed Concerns in Main
```python
# Main function ~1500 lines
```
**Issue**: CLI parsing, business logic, and hardware control all mixed  
**Fix**: Split into CLI module + library module (the plan!)

### 3. Global Logger Configuration
```python
# Lines 72-76
logging.basicConfig(...)
logger = logging.getLogger(__name__)
```
**Issue**: Module-level config affects all logging  
**Fix**: Use null handler in library, configure in CLI

---

## ✅ Clean Code Areas

| Area | Quality | Notes |
|------|---------|-------|
| `send_command()` 4-step sequence | ✅ EXCELLENT | Well-documented, verified working |
| `healthcheck()` | ✅ GOOD | Comprehensive checks |
| `reset_control_state()` | ✅ GOOD | Clean idle-on-exit |
| Scale factor handling | ✅ GOOD | Consistent pattern |
| Dataclass models | ✅ GOOD | Type hints, clean |

---

## 🎯 Recommendations for Library Split

### Must Fix Before Split
- [ ] Document M715/M704 limitations in public API docs
- [ ] Fix `self.tou.min_soc` undefined reference
- [ ] Add specific exception handling

### Should Fix During Split
- [ ] Move CLI code to separate module
- [ ] Use null logger in library
- [ ] Extract hardcoded values to constants/dataclass
- [ ] Unify SPAN/native mode reading

### Can Fix After Split
- [ ] Remove cloud API placeholders
- [ ] Add configuration system
- [ ] Improve exception specificity

---

*End of Code Analysis Audit*
