# Gap Analysis: Library vs CLI vs Standalone Script

**Date:** 2026-03-01  
**Purpose:** Identify functionality gaps between franklinwh_control_standalone.py, franklinwh_cli.py, and the library

---

## Executive Summary

| Component | Lines | CLI Args | Status |
|-----------|-------|----------|--------|
| `franklinwh_control_standalone.py` | 3,471 | 24 | ⚠️ **DEPRECATED** but feature-rich |
| `franklinwh_cli.py` | ~550 | 26 | ✅ Active, but missing features |
| `src/franklinwh/` library | ~3,800 | N/A | ✅ Core functionality |

**Critical Finding:** The deprecated standalone script has **significant functionality** not present in the current CLI, including startup state validation, detailed alarm checking, and off-grid detection.

---

## 1. CLI Arguments Comparison

### Arguments in BOTH (Working)

| Argument | Standalone | CLI | Notes |
|----------|------------|-----|-------|
| `-i/--ip` | ✅ | ✅ | Connection IP |
| `-p/--port` | ✅ | ✅ | Modbus port (502) |
| `-u/--unit` | ✅ | ✅ | Unit ID (2) |
| `-t/--timeout` | ✅ | ✅ | Connection timeout |
| `--power` | ✅ | ✅ | Legacy power control |
| `--charge` | ✅ | ✅ | Explicit charge |
| `--discharge` | ✅ | ✅ | Explicit discharge |
| `--standby` | ✅ | ✅ | 0W standby |
| `--stop` | ✅ | ✅ | Release control |
| `--mode` | ✅ | ✅ | Virtual modes |
| `--reserve` | ✅ | ✅ | Reserve % |
| `--target-soc` | ✅ | ✅ | Target SoC |
| `--threshold` | ✅ | ✅ | Peak shave threshold |
| `--duration` | ✅ | ✅ | Runtime duration |
| `--max-charge-soc` | ✅ | ✅ | Charge limit |
| `--min-discharge-soc` | ✅ | ✅ | Discharge limit |
| `--soc-ramp-window` | ✅ | ✅ | SoC ramping |
| `--force` | ✅ | ✅ | Override limits |
| `--off-grid-permitted` | ✅ | ✅ | Allow off-grid |
| `--schedule-file` | ✅ | ✅ | TOU schedule |
| `--show-schedule` | ✅ | ✅ | Display schedule |
| `--validate-schedule` | ✅ | ✅ | Validate schedule |
| `--status` | ✅ | ✅ | System status |
| `--healthcheck` | ✅ | ✅ | Health check |
| `--clear-alarms` | ✅ | ✅ | Clear alarms |
| `--test-extension-write` | ✅ | ✅ | Test register writes |
| `--dry-run` | ✅ | ✅ | Simulation mode |
| `-v/--verbose` | ✅ | ✅ | Verbose logging |
| `-q/--quiet` | ✅ | ✅ | Quiet mode |

### Arguments MISSING from CLI (Gap #1)

| Argument | Standalone | CLI | Impact |
|----------|------------|-----|--------|
| `--idle` | ✅ | ❌ | **MEDIUM** - Different from standby (idle = no control) |
| `--check-alarms` | ✅ | ✅ | **FIXED** - Detailed alarm status display |
| `--assume-clean-state` | ✅ | ✅ | **FIXED** - Skip startup conflict detection |
| `--reset-on-start` | ✅ | ✅ | **FIXED** - Present and functional |
| `--revert` | ✅ | ✅ | **FIXED** - Auto-revert timer |

### Arguments UNIQUE to CLI (New Features)

| Argument | CLI | Standalone | Notes |
|----------|-----|------------|-------|
| `--max-charge` | ✅ | ❌ | Use rated max charge power |
| `--max-discharge` | ✅ | ❌ | Use rated max discharge power |
| `--monitor` | ✅ | ❌ | TUI dashboard (now parked) |
| `--theme` | ✅ | ❌ | TUI color theme |

---

## 2. Functional Gaps

### Gap #2: Startup State Validation (HIGH PRIORITY)

**Standalone Has:**
```python
# Lines 3171-3184
startup_state = check_startup_state(ctrl, args.mode, args)
print_startup_summary(startup_state, args.mode, args)

if not startup_state['can_proceed'] and not args.reset_on_start:
    print("⚠️  Cannot proceed due to conflicts...")
    sys.exit(1)
```

**Checks performed:**
- Detects if aGate is in conflicting mode
- Checks if battery is already active
- Validates SoC limits before operation
- Detects off-grid conditions

**CLI Missing:** ❌ No startup state validation

**Impact:** Users can issue commands that conflict with aGate native mode, causing errors or unexpected behavior.

---

### Gap #3: Detailed Alarm Checking (HIGH PRIORITY)

**Standalone Has:** `--check-alarms` flag (lines 3257-3289)
```python
alarms = ctrl.read_alarms()
decoded = alarms.get('decoded', {})

print(f"System Alarms: 0x{alarms['system_alrm']:08X}")
for alarm in decoded.get('system', []):
    print(f"  ⚠ {alarm}")

can_operate, blocking = ctrl.check_blocking_alarms()
```

**Output includes:**
- System alarms (decoded with names)
- DC Port alarms (decoded with names)
- Battery status
- Blocking vs non-blocking classification

**CLI Missing:** ❌ Only has `--healthcheck` which is less detailed

---

### Gap #4: Off-Grid Detection (MEDIUM PRIORITY)

**Standalone Has:** (lines 3186-3197)
```python
grid_connected = startup_state['current_state'].get('grid_connected', False)
if not grid_connected and not args.off_grid_permitted:
    print(f"🚨 OFF-GRID DETECTED...")
    sys.exit(1)
```

**CLI Missing:** ❌ No grid connection validation before operation

---

### Gap #5: SoC Pre-Validation (MEDIUM PRIORITY)

**Standalone Has:** (lines 3198-3232)
- Validates target_soc before charge
- Validates max_charge_soc before charge  
- Validates min_discharge_soc before discharge
- Exits gracefully with helpful message if limits would be violated

**CLI Missing:** ❌ Only validates during operation, not before

---

### Gap #6: Auto-Revert Timer (HIGH PRIORITY)

**Standalone Has:** `--revert SECONDS` (line 2367)
```python
parser.add_argument('--revert', type=int, default=0,
                   help='Auto-revert to cloud control after N seconds')
```

**CLI Missing:** ❌ No auto-revert functionality

**Impact:** Users must manually release control. Risk of leaving battery in Modbus control indefinitely.

---

### Gap #7: Idle vs Standby Distinction (LOW PRIORITY)

**Standalone Has:** `--idle` flag (line 2362)
```python
power_group.add_argument('--idle', action='store_true',
                        help='Set battery to idle (no control, release to cloud)')
```

**Difference:**
- `--standby`: 0W with Modbus control active
- `--idle`: Release to cloud API (same as `--stop`)

**CLI Missing:** ❌ Only has `--stop` (equivalent to idle)

---

### Gap #8: Startup Summary Display (LOW PRIORITY)

**Standalone Has:** `print_startup_summary()` function
- Shows current aGate mode
- Shows battery state
- Shows grid connection
- Shows detected conflicts

**CLI Missing:** ❌ No startup context display

---

### Gap #9: Schedule Display Output (LOW PRIORITY)

**Standalone Has:** Enhanced schedule display (lines 3126-3141)
```python
print(f"Schedule: {schedule.get_schedule_name()}")
print(f"Current period: {schedule.get_current_period()}")
print(f"Current price: ${schedule.get_current_price():.2f}/kWh")
print(f"Current strategy: {schedule.get_strategy()}")
print(f"Rules: {schedule.get_rules()}")
```

**CLI Missing:** ❌ Basic validation only

---

## 3. Output Format Gaps

### Gap #10: Status Output Detail

| Feature | Standalone | CLI |
|---------|------------|-----|
| Power Flow arrows | ✅ Detailed | ✅ Detailed |
| Battery DC power | ✅ Shows | ✅ Shows |
| Home load calculation | ✅ Shows | ✅ Shows |
| Extension writability test | ✅ Detailed table | ✅ Basic |
| Control source indication | ✅ Shows | ✅ Shows |
| Temperature | ✅ Shows | ✅ Shows |

**Both are similar** - no major gap here.

---

## 4. Library API Gaps

### Gap #11: Library Functions Not Exposed in CLI

**Library Has:**
```python
# From controller.py
ctrl.read_alarms()              # ✅ Exposed via --healthcheck
ctrl.clear_alarms()             # ✅ Exposed via --clear-alarms
ctrl.check_blocking_alarms()    # ❌ NOT EXPOSED
ctrl.reset_control_state()      # ✅ Exposed via --stop
ctrl.send_command()             # ✅ Core function
ctrl.read_native_mode()         # ✅ Used internally
ctrl.read_extension_registers() # ✅ Used internally

# From modes.py
VirtualModeController.set_mode()  # ✅ Exposed via --mode
VirtualModeController.read_status()  # ❌ NOT EXPOSED

# Missing from Library (in standalone only):
- check_startup_state()          # ❌ NOT IN LIBRARY
- print_startup_summary()        # ❌ NOT IN LIBRARY
- validate_mode_params()         # ❌ NOT IN LIBRARY
```

---

## 5. Critical Safety Gaps

### Gap #12: No Pre-Flight Safety Check

**Standalone:** Validates before executing
**CLI:** Executes and fails during operation

**Risk:** CLI may leave system in partial state if validation fails mid-operation.

---

### Gap #13: Missing Conflict Detection

**Standalone:** Detects if aGate mode conflicts with requested operation
**CLI:** Does not check, assumes user knows what they're doing

---

## Recommendations

### Immediate (Critical)

1. **~~Add `--revert` to CLI~~** ✅ **FIXED** - Auto-revert timer implemented
2. **~~Add `--check-alarms` to CLI~~** ✅ **FIXED** - Detailed alarm checking implemented  
3. **~~Add startup state validation~~** ✅ **FIXED** - Conflict detection with `--assume-clean-state` option

### Short Term (High Value)

4. **Add off-grid detection** - Simple check before operation
5. **Add SoC pre-validation** - Fail fast before sending commands
6. **Add `--assume-clean-state`** - For advanced users

### Medium Term (Polish)

7. **Enhance schedule display** - Better output for `--show-schedule`
8. **Add startup summary** - Context before operation
9. **Unify `--idle` and `--stop`** - Document that they are equivalent

---

## Implementation Priority

| Priority | Feature | File | Effort |
|----------|---------|------|--------|
| 🔴 P0 | `--check-alarms` | CLI | 1h |
| 🔴 P0 | `--revert` | CLI | 2h |
| 🔴 P0 | Startup state validation | Library + CLI | 3h |
| 🟡 P1 | Off-grid detection | CLI | 30m |
| 🟡 P1 | SoC pre-validation | CLI | 1h |
| 🟢 P2 | Enhanced schedule display | CLI | 1h |
| 🟢 P2 | Startup summary | CLI | 1h |

---

## Files to Modify

1. `franklinwh_cli.py` - Add missing arguments and logic
2. `src/franklinwh/controller.py` - Add startup state checking
3. `src/franklinwh/health.py` (new) - Consolidate health checking logic

---

*Analysis completed: 2026-03-01*
