# Traceability Matrix: SoC Validation Implementation

**Date:** 2026-03-01  
**Status:** GAP-1, GAP-2 RESOLVED - Reserve SoC Validation Implemented

---

## Implementation vs Requirements Gap Analysis

| Req ID | Requirement | CLI Status | Library Status | Gap | Action Required |
|--------|-------------|------------|----------------|-----|-----------------|
| FR-1 | Range validation (10-100%) | ✅ Implemented | ✅ Implemented | None | - |
| FR-2 | Target vs Current sanity | ⚠️ Partial | ⚠️ Partial | Missing check in VMC modes | Add to modes.py |
| FR-3 | Reserve SoC conflict | ✅ **IMPLEMENTED** | ✅ **IMPLEMENTED** | **RESOLVED** | GAP-1 CLOSED |
| FR-4 | Safety margin (5%) | ✅ **IMPLEMENTED** | ✅ **IMPLEMENTED** | **RESOLVED** | GAP-2 CLOSED |
| FR-5 | aGate conflict detection | ✅ Implemented | ✅ Implemented | None | - |
| FR-6 | Off-grid safety | ✅ Implemented | ✅ Implemented | None | - |
| FR-7 | SoC monitoring & auto-stop | ✅ CLI only | ❌ Not implemented | Library gap | Add to controller |

---

## Resolved Gaps (2026-03-01)

### GAP-1: Reserve SoC Conflict Detection (FR-3) ✅ RESOLVED

**Implementation:** Added to `controller.py`

```python
# In FranklinWHController class:
SAFETY_MARGIN_PCT = 5  # Minimum 5% buffer above reserve level

def get_effective_reserve_level(self) -> Tuple[Optional[int], str]:
    """Get the effective reserve level based on current aGate mode."""
    native = self.read_native_mode()
    mode_raw = native.get('mode_raw', -1)
    
    if mode_raw == 2:  # Self-Consumption
        return native.get('self_reserve_pct', 20), 'self'
    elif mode_raw == 1:  # Time of Use
        return native.get('tou_reserve_pct', 20), 'tou'
    elif mode_raw == 0:  # Emergency Backup
        return native.get('self_reserve_pct', 20), 'self'
    elif mode_raw == 3:  # Manual
        return None, 'none'
    else:
        return None, 'unknown'

def validate_target_soc(self, target_soc: float, operation: str) -> Tuple[bool, str, dict]:
    """Validate target SoC against reserve levels and safety margins."""
    # Checks target >= reserve + SAFETY_MARGIN_PCT for discharge
    # Warns if target < reserve for charge
    # Returns (is_valid, message, details_dict)
```

**CLI Integration:** Validation called before all charge/discharge operations
- Virtual modes: Lines 771-815 in `franklinwh_cli.py`
- Direct power with target-soc-auto: Lines 954-977 in `franklinwh_cli.py`

**Status Display:** Added to `print_startup_summary()` and `check_state()` output

---

### GAP-2: Safety Margin Enforcement (FR-4) ✅ RESOLVED

**Implementation:** Same methods as GAP-1, with `SAFETY_MARGIN_PCT = 5`

```python
# Minimum operational SoC = reserve + SAFETY_MARGIN_PCT
def validate_soc_safety(self, target_soc, current_soc, operation):
    # Combines reserve validation with current SoC sanity checks
    # For discharge: target must be >= reserve + 5%
    # For charge: warns if target < reserve
```

**Error Messages:** Standardized (E001-E008, W001-W005)
- E002: Target conflicts with reserve + safety margin
- W001: Target below configured reserve
- W002: Current SoC close to reserve boundary

---

## Remaining Gaps

---

## Critical Gaps Identified

### GAP-1: Reserve SoC Conflict Detection (FR-3)

**Current State:**
- CLI reads OnGridMode and Self/TOU Reserve
- No validation against target SoC

**Required State:**
- Read registers 15507 (OnGridMode), 15508 (SelfReserve), 15509 (TOUReserve)
- Validate target >= reserve + 5%
- Block operation if target < reserve

**Implementation Needed:**
```python
# In controller.py or validation module
def validate_target_vs_reserve(self, target_soc: float, is_charge: bool) -> Tuple[bool, str]:
    native = self.read_native_mode()
    ongrid_mode = native.get('mode_raw', 0)
    
    if ongrid_mode == 2:  # Self-Consumption
        reserve = native.get('self_reserve_pct', 20)
        if target_soc < reserve:
            return False, f"Target {target_soc}% < Self Reserve {reserve}%"
    elif ongrid_mode == 3:  # TOU
        reserve = native.get('tou_reserve_pct', 20)
        if target_soc < reserve:
            return False, f"Target {target_soc}% < TOU Reserve {reserve}%"
    
    return True, "OK"
```

---

### GAP-2: Safety Margin Enforcement (FR-4)

**Current State:**
- No margin checking

**Required State:**
- Target must be >= reserve + 5%
- Warning if margin < 5%

**Implementation Needed:**
```python
MIN_RESERVE_MARGIN = 5  # percent

def check_safety_margin(target_soc: float, reserve_soc: float) -> Tuple[bool, bool, str]:
    """
    Returns: (can_proceed, is_warning, message)
    """
    margin = target_soc - reserve_soc
    
    if margin < 0:
        return False, False, f"Target {target_soc}% below reserve {reserve_soc}%"
    elif margin < MIN_RESERVE_MARGIN:
        return True, True, f"Target {target_soc}% only {margin:.1f}% above reserve {reserve_soc}%"
    else:
        return True, False, f"Margin OK: {margin:.1f}%"
```

---

### GAP-3: Target vs Current in Virtual Modes (FR-2)

**Current State:**
- CLI checks for direct power control
- VirtualModeController doesn't check target vs current

**Required State:**
- All modes validate target is achievable
- Self-Con: target > current for charge
- Emergency: target > current
- Peak Shave: target < current for discharge

**Implementation Needed:**
```python
# In modes.py VirtualModeController.set_mode()
def set_mode(self, mode: VirtualMode, **kwargs):
    # ... existing code ...
    
    if 'target_soc' in kwargs:
        target = kwargs['target_soc']
        current = self.ctrl.read_battery_status().get('soc', 0)
        
        # Direction check
        if mode in [VirtualMode.SELF_CONSUMPTION, VirtualMode.EMERGENCY_BACKUP]:
            if target <= current:
                raise ValueError(f"Target {target}% must be > current {current}% for charge mode")
        elif mode == VirtualMode.PEAK_SHAVE:
            # Discharge mode
            if target >= current:
                raise ValueError(f"Target {target}% must be < current {current}% for discharge mode")
```

---

### GAP-4: Library Auto-Stop (FR-7)

**Current State:**
- Only CLI has target SoC auto-stop implementation
- Library users must implement their own monitoring

**Required State:**
- Controller provides `run_until_soc()` method
- Built-in monitoring and auto-stop

**Implementation Needed:**
```python
# In controller.py

def run_until_soc(self, target_soc: float, power_watts: int, 
                  check_interval: int = 5, 
                  timeout: Optional[int] = None) -> Dict:
    """
    Run control operation until target SoC reached.
    
    Args:
        target_soc: Target SoC percentage
        power_watts: Power to apply (+charge, -discharge)
        check_interval: Seconds between SoC checks
        timeout: Maximum seconds to run (None = unlimited)
    
    Returns:
        Dict with 'success', 'final_soc', 'reason', 'duration'
    """
    import time
    start_time = time.time()
    
    # Validate target vs current
    current = self.read_battery_status().get('soc', 0)
    is_charge = power_watts > 0
    
    if is_charge and current >= target_soc:
        return {'success': False, 'reason': 'already_at_target', 'final_soc': current}
    if not is_charge and current <= target_soc:
        return {'success': False, 'reason': 'already_at_target', 'final_soc': current}
    
    # Send command
    from .types import BatteryCommand
    cmd = BatteryCommand(power_watts=power_watts)
    success, msg = self.send_command(cmd)
    
    if not success:
        return {'success': False, 'reason': 'command_failed', 'message': msg}
    
    # Monitor loop
    try:
        while True:
            # Check timeout
            if timeout and (time.time() - start_time) >= timeout:
                self.reset_control_state()
                return {'success': False, 'reason': 'timeout'}
            
            # Check SoC
            status = self.read_battery_status()
            current = status.get('soc', 0)
            
            # Check target reached
            if is_charge and current >= target_soc:
                self.reset_control_state()
                return {
                    'success': True,
                    'reason': 'target_reached',
                    'final_soc': current,
                    'duration': time.time() - start_time
                }
            elif not is_charge and current <= target_soc:
                self.reset_control_state()
                return {
                    'success': True,
                    'reason': 'target_reached',
                    'final_soc': current,
                    'duration': time.time() - start_time
                }
            
            time.sleep(check_interval)
    
    except KeyboardInterrupt:
        self.reset_control_state()
        return {'success': False, 'reason': 'user_interrupt'}
```

---

## Priority Order for Implementation

### P0: Critical (Must Have)
1. **GAP-1: Reserve SoC Conflict Detection**
   - Safety critical - prevents draining below reserve
   - Affects all target SoC operations
   - Estimated effort: 2 hours

2. **GAP-2: Safety Margin Enforcement**
   - Related to GAP-1
   - Estimated effort: 1 hour

### P1: High (Should Have)
3. **GAP-3: Target vs Current in Virtual Modes**
   - Affects mode-based operations
   - Estimated effort: 2 hours

### P2: Medium (Nice to Have)
4. **GAP-4: Library Auto-Stop**
   - Library convenience feature
   - CLI already has implementation
   - Estimated effort: 3 hours

---

## Test Coverage Gap

| Test Case | Implemented | Test File | Status |
|-----------|-------------|-----------|--------|
| TC-1: Valid charge | ✅ | Manual | Needs automated |
| TC-2: Invalid charge (below current) | ⚠️ | None | Not tested |
| TC-3: Invalid (below reserve) | ❌ | None | **Not implemented** |
| TC-4: Target close to reserve | ❌ | None | **Not implemented** |
| TC-5: Cloud conflict | ✅ | Manual | Needs automated |
| TC-6: Force override | ✅ | Manual | Needs automated |
| TC-7: Off-grid block | ✅ | Manual | Needs automated |
| TC-8: Off-grid permit | ✅ | Manual | Needs automated |

**New Tests Needed:**
1. `tests/test_soc_validation.py` - Unit tests for validation logic
2. `tests/test_reserve_conflict.py` - Reserve-based conflict tests
3. Hardware tests for reserve scenarios

---

## Recommendation

**Immediate Action:**
Implement GAP-1 and GAP-2 (Reserve SoC conflict detection + safety margin) before any further target SoC operations are used in production.

**Rationale:**
- Prevents safety-critical scenario: discharging below reserve
- Required for compliance with FranklinWH operational modes
- Relatively small implementation effort (3 hours total)
- High impact on system safety

**After P0:**
- Complete P1 (Virtual mode target validation)
- Add comprehensive test suite
- Then consider P2 (Library auto-stop)

---

*Gap Analysis Complete: 2026-03-01*  
*Next Action: Implement GAP-1 (Reserve SoC Conflict Detection)*