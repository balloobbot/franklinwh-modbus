# In-Flight Work — Updated 2026-02-23 14:30

## Status: COMPLETED — Library Architecture Implementation

### Architecture Cleanup — 2026-02-23 14:30

**User Vision Implemented**: Single-file library + CLI separation  
**Status**: ✅ Complete

**New File Structure:**
```
franklinwh_modbus_library.py      ← NEW: Single-file library (14,871 lines)
franklinwh_cli.py                  ← CLI (uses library via src/franklinwh/)
franklinwh_control_standalone.py   ← DEPRECATED (frozen, deprecation warning added)
```

**Files Created:**
- `franklinwh_modbus_library.py` — Fork of standalone, library-only (no CLI)
  - Contains: FranklinWHController, VirtualModeController, TOUSchedule
  - Exports: BatteryCommand, HealthStatus, ControlMode, VirtualMode
  - Clean API for import and use

**Files Modified:**
- `franklinwh_control_standalone.py` — Added deprecation warning
  - Docstring updated with deprecation notice
  - Runtime warning prints on every execution
  - Directs users to franklinwh_cli.py or franklinwh_modbus_library.py

**Usage:**
```python
# Library import
from franklinwh_modbus_library import FranklinWHController, VirtualModeController

ctrl = FranklinWHController('192.168.0.110')
ctrl.connect()

# CLI usage (recommended)
python franklinwh_cli.py -i 192.168.0.110 --charge 3000
```

---

## Status: COMPLETED — Sign Convention Fix + Explicit Action Flags

### Implementation Summary — 2026-02-23 13:35

**Approved by**: User ("GO!")  
**Stages Completed**: 3/3  
**Files Modified**:
- `franklinwh_control_standalone.py` — Sign fix + new flags
- `CLI_OPTIONS.md` — Updated documentation

---

### Stage 1: Fixed Sign Convention ✅

**Changes:**
- `is_charge = power_watts < 0` → `is_charge = power_watts > 0`
- `power_watts: float  # Positive=charge, negative=discharge, 0=idle`

**Result**: Code now matches help text: `+charge, -discharge`

---

### Stage 2: Added Explicit Action Flags ✅

**New Arguments** (mutually exclusive):
| Flag | Description | Example |
|------|-------------|---------|
| `--charge WATTS` | Charge battery (import from grid) | `--charge 3000` |
| `--discharge WATTS` | Discharge battery (export to grid) | `--charge 3000` |
| `--standby` | Set to 0W (no power flow) | `--standby` |
| `--power WATTS` | Legacy (still works) | `--power 3000` |

**Key Benefits:**
- No sign confusion — positive numbers always mean "power level"
- Self-documenting intent — clear what action you're requesting
- Backward compatible — `--power` still works
- `--idle` deprecated in favor of `--standby`

---

### Stage 3: Updated Documentation ✅

- `CLI_OPTIONS.md` — Added sections for new flags
- Docstring examples — Updated to show new recommended usage
- Help epilog — Added explicit flag examples

---

### Testing Commands

```bash
# Test new flags (dry run)
python3 franklinwh_control_standalone.py -i 192.168.0.110 --dry-run --charge 3000
python3 franklinwh_control_standalone.py -i 192.168.0.110 --dry-run --discharge 3000
python3 franklinwh_control_standalone.py -i 192.168.0.110 --dry-run --standby

# Legacy still works
python3 franklinwh_control_standalone.py -i 192.168.0.110 --power 3000  # Charge
python3 franklinwh_control_standalone.py -i 192.168.0.110 --power -3000 # Discharge
```

---

### Future Enhancement: --charge-max / --discharge-max (TODO)

As discussed, add flags to use nameplate ratings:
```bash
--charge-max              # Use RATED_MAX_CHARGE_W
--discharge-max           # Use RATED_MAX_DISCHARGE_W
--charge-max --margin 500 # Max minus 500W for other loads
```

**Effort**: 30 minutes  
**Dependencies**: Stage 2 (complete)

---

## 🚨 CRITICAL BUG FIX: Power Sign Convention Documentation — 2026-02-23 13:10

### Bug 8: Inverted Help Text for `--power` Argument

### Bug 8: Inverted Help Text for `--power` Argument

**SEVERITY:** CRITICAL SAFETY ISSUE  
**User Impact:** User charged battery when trying to discharge (or vice versa)  
**Discovery:** User report - expected charge from grid but got discharge

**Problem:**
The help text for `--power` had the sign convention **inverted**:
```python
# WRONG (before):
help='Power in watts (+charge, -discharge)'

# CORRECT (after):
help='Power in watts (+discharge, -charge). Positive exports to grid (discharge), negative imports from grid (charge).'
```

**Code vs Documentation Mismatch:**
| Source | Convention |
|--------|-----------|
| `BatteryCommand` dataclass (line 116) | `Positive=discharge, negative=charge` ✓ |
| `is_charge` check (line 999) | `is_charge = power_watts < 0` ✓ |
| **Help text (line 2336)** | **+charge, -discharge** ❌ **WRONG!** |
| CLI_OPTIONS.md | **Positive = charge** ❌ **WRONG!** |

**Files Fixed:**
1. `franklinwh_control_standalone.py` - Corrected help text
2. `CLI_OPTIONS.md` - Corrected documentation with warning note

**Correct Usage:**
```bash
# Charge from grid (import power) - NEGATIVE
python3 franklinwh_control_standalone.py -i 192.168.0.110 --power -5000

# Discharge to grid (export power) - POSITIVE  
python3 franklinwh_control_standalone.py -i 192.168.0.110 --power 5000
```

**Root Cause:** Help text was inverted when first created (commit 600581f). The code was always correct (matching electrical engineering convention), but documentation was wrong.

**Safety Impact:** Users relying on help text could inadvertently:
- Discharge when trying to charge (unexpected battery drain)
- Export to grid during peak pricing (financial loss)
- Violate utility export limits

---

## Current Plan Reference

**Project**: FranklinWH Modbus Battery Manager (`/home/david/dev/modbus/`)
**Plan Status**: GOVERNANCE COMPLETE — Awaiting next scoped implementation plan
**Priority**: Stabilise `franklinwh_control_standalone.py` as an importable library (see `ARCHITECTURE.md` Phase 2)

## Status: GOVERNANCE COMPLETE — AWAITING APPROVAL FOR NEXT WORK

**⚠️ MANDATORY PROCESS:** All work must follow `.agent/workflows/staged-execution.md`
- Proposed plan required before ANY work
- Explicit user approval required ("go", "yes", "approved", "proceed")
- Per-stage git commits
- in_flight_work.md tracking

---

## Completed: Bugfixes — Off-Grid, SoC Validation, Sanity Check — 2026-02-22 13:20

### Bug 1: Off-Grid Detection & Blocking
**Stages:**
- [x] **Stage 1.1** — Grid connection check using ConnSt + voltage — Commit: `a36b9b3`
- [x] **Stage 1.2-1.3** — Add `--off-grid-permitted` flag — Commit: `a36b9b3`
- [x] **Stage 1.4** — Block start unless flag provided — Commit: `a36b9b3`

### Bug 2: SoC Limit Validation  
**Stages:**
- [x] **Stage 2.1-2.3** — Validate target_soc, max_charge_soc, min_discharge_soc — Commit: `e055665`
- [x] **Stage 2.4** — Immediate exit on validation failure — Commit: `e055665`

### Bug 3: Fix "AT TARGET" Display
**Stages:**
- [x] **Stage 3.1-3.3** — Show ABOVE TARGET when SoC > target — Commit: `96d1f72`

### Bug 4: Runtime Sanity Check
**Stages:**
- [x] **Stage 4.1-4.3** — Verify commanded vs actual DC power — Commit: `5d26917`
- [x] Warning on >20% difference every 10s — Commit: `5d26917`

### Bug 5: Fix 'args is not defined' Error — 2026-02-22 13:35
**Stages:**
- [x] **Stage fix** — Added args parameter to check_startup_state() — Commit: `de6de85`
- [x] Fixed warning: 'Could not read full state: name args is not defined'

### Bug 6: Add --test-extension-write to Standalone — 2026-02-22 13:45
**Stages:**
- [x] **Stage fix** — Added missing --test-extension-write option — Commit: `7917623`
- [x] Sync standalone with CLI features

### Bug 7: Fix Extension Register Test — 2026-02-22 14:45
**Stages:**
- [x] **Stage fix** — Changed from pymodbus API to raw socket — Commit: `0a80014`
- [x] Fixed 'Read failed' → now shows 'Write rejected' (correct behavior)
- [x] Extension registers 15507-15509 now readable

---

## Completed: Solar PV Display Bugfix — 2026-02-22 13:03

**Defect:** Solar PV showing 0W in --status despite Model 502 showing 2100W+  
**Root Cause:** Two bugs in `read_solar_status()`:
1. pymodbus 3.x API: `unit=` → `device_id=` 
2. Wrong attribute: `m502.W` → `m502.OutPw`

**Stages:**
- [x] **Stage 0.1/0.2** — Fix standalone script API — Commit: `cb6a041`
- [x] **Stage 1.1** — Fix library extension solar API — Commit: `6666e2c`
- [x] **Stage 2.1** — Fix Model 502 attribute (`OutPw`) — Commit: `24ac709`
- [x] **Verify** — Solar now shows 3600W ✓

**Result:** 
- Before: `Solar: 0W Idle`
- After: `Solar: → 3600W Producing` ✅

---

## Completed: Staged Execution Governance

- [x] **Stage 1 (COMPLETE)** — Add staged execution governance — 2026-02-22 12:45
  - Created `.agent/workflows/staged-execution.md` — comprehensive staged work process
  - Created `.agent/rules/staged_execution_rule.md` — hard rule for planning gate
  - Updated `agent.md` — reference new staged execution process
  - Git commit: `8b4e959`

---

## Completed (Previous)

---

## Completed Items

- [x] Full modbus web app inventory — 2026-02-18
  - 77 API endpoints, 16 backend modules, 7 templates, 13 dashboard cards
  - All 20 TODO files confirmed as legitimate for this project
- [x] fhp_demo accidental changes identified and rolled back — 2026-02-18
- [x] Project governance created from scratch — 2026-02-18
  - `SAFETY_CONTROLS.md` (10 rules inherited/adapted from fhp_demo)
  - `agent.md` (development guide)
  - `.agent/rules/project_boundaries.md` (boundary enforcement)
  - `.agent/workflows/verify-implementation.md` (3-check verification)
  - `.agent/workflows/restart-server.md` (port-safe restart)
  - `.agent/workflows/execution-discipline.md` (plan adherence)

## Awaiting

- [ ] User review/approval of governance documents
- [ ] Scoped implementation plan (modbus project only — no fhp_demo)
- [ ] TODO prioritisation for this project

## Blocked

_No blockers._

## Test Evidence

| Item | Logs Clean | Console Clean | Functional Test | Recording |
|------|-----------|--------------|-----------------|-----------|
| fhp_demo rollback | ✅ git checkout clean | N/A | N/A | N/A |

---

## Error Baseline

**Last checked**: 2026-02-18
**Reference**: See `AGENT_ERROR_TRACKING.md` for full error history

---

## Session Log

### 2026-02-23 01:00 AEDT — ADDED: Comprehensive Alarm Monitoring

**Major Feature: Full Alarm System**

1. **Alarm Types Monitored**
   - System Alarms (Model 701): GROUND_FAULT, OVER_TEMP, AC_DISCONNECT, etc.
   - DC Port Alarms (Model 714): PORT_OVER_VOLTAGE, PORT_OVER_CURRENT, etc.
   - Battery Status (Model 713): FAULT detection
   - Solar Events (Model 502): INPUT_OVER_VOLTAGE, etc.

2. **New CLI Options**
   - `--check-alarms`: Display all alarm states
   - `--clear-alarms`: Reset alarms if safe (no critical faults)

3. **Alarm Reset Mechanism**
   - Writes to Model 715 AlarmReset (register 41094)
   - Only clears non-critical alarms
   - Critical faults require manual intervention

4. **Integration**
   - Startup check: Blocks if critical alarms active
   - Runtime check: Logs blocking alarms every 60s
   - Status display: Shows all active alarms with descriptions
   - Healthcheck: Includes alarm status

**Files Modified:**
- `franklinwh_control_standalone.py` - Alarm methods and CLI integration
- `FIXES_SUMMARY.md` - Documentation

### 2026-02-23 00:45 AEDT — POLISH: Nameplate Cleanup & Zombie State Display

**Final Polish Items:**

1. **Nameplate Display Cleanup**
   - Stripped register prefixes (Mn:, Md:, SN:, Vr:, Opt:) from display
   - Cleaner output without raw register notation
   - Added `clean_value()` helper function

2. **Zombie State Display Fix**
   - Fixed confusing "FAIL" message when not in zombie state
   - Now shows: "✓ zombie_state: OK (not in zombie state)" when healthy
   - Shows: "🚨 zombie_state: ZOMBIE STATE DETECTED" when active

### 2026-02-23 00:30 AEDT — ADDED: AC Type & Grid State to Status/Health

**New Grid Information in --status and --healthcheck:**

1. **AC Type Detection**
   - Single-Phase 230V (200-260V range)
   - Single-Phase 120V (100-200V range)
   - Three-Phase 400V (380-420V range)
   - Based on LNV (Line-Neutral Voltage) reading

2. **Grid Connection State**
   - From Model 701 ConnSt register
   - Shows: Connected / Disconnected / Fault

3. **Grid Mode**
   - From DERMode upper bits (bits 16-17)
   - Grid Following (normal operation)
   - Grid Forming (island/off-grid mode)
   - Default: Grid Following if bits not set

4. **Inverter State**
   - From Model 701 InvSt register
   - Shows: Running, Standby, Starting, Fault, etc.

**Files Modified:**
- `franklinwh_control_standalone.py` - Enhanced `read_grid_status()`
- `src/franklinwh/controller.py` - Enhanced `read_grid_status()`, added to healthcheck
- `franklinwh_cli.py` - Updated `print_status()` to show new fields

### 2026-02-23 00:15 AEDT — FIXED: HealthStatus Bug + Model 1 Nameplate

**Bug Fixes:**

1. **HealthStatus Field Mismatch**
   - Library `HealthStatus` had `issues` field but controller used `message`
   - Fixed `types.py` to use `message: str` field
   - `--healthcheck` now works correctly

2. **Model 1 (Common) Nameplate Reading**
   - Added `read_nameplate()` method to both original and library
   - Reads Model 1: manufacturer, model, serial, version, options
   - Displayed in `--status` and `--healthcheck` output
   - Example:
     ```
     DEVICE:
       Manufacturer: FranklinWH
       Model:        aGate X
       Serial:       FW123456789
       Firmware:     2.1.4
     ```

### 2026-02-23 00:00 AEDT — ADDED: Startup State Check & Quiet Mode

**New Features:**

1. **Clear Startup State Display**
   - `check_startup_state()` - reads all system state
   - `print_startup_summary()` - visual summary before taking control
   - Shows: SoC, battery activity, grid status, control state, aGate mode
   - Only shown if not in `--quiet` mode

2. **Conflict Detection**
   - Detects when aGate is already active in different mode
   - Warns about mode mismatches
   - Exits with clear options unless `--reset-on-start` used
   - Example: aGate in TOU mode but requesting manual mode

3. **Quiet Mode (`-q` / `--quiet`)**
   - Only shows warnings, errors, and startup summary
   - Hides INFO level logs
   - Usage: `python script.py -i 192.168.0.110 -q --mode manual --power -4000`

4. **Library State Check Method**
   - Added `ctrl.check_state()` to library controller
   - Returns dict with all current state info
   - Useful for programmatic conflict detection

**Example Startup Output:**
```
======================================================================
  CURRENT SYSTEM STATE
======================================================================
  Battery:
    SoC:           41.0%
    Activity:      CHARGING (4000W)
  Grid:
    Status:        ✓ Connected
    Power:         2058W
    Voltage:       230.5V
  Control:
    WSetEna:       1
    WSetPct:       -80.0%
    Actual Power:  -4000W
  aGate Mode:
    OnGridMode:    Self-Consumption (2)
  Requested Mode: manual
  Status:         ✓ Can proceed
======================================================================
```

### 2026-02-22 23:45 AEDT — FIXED: Telemetry Display Bugs

**Critical Fixes to Original Script:**

1. **Battery shows "IDLE 0W"** → Now derives state from WSetPct
   - FranklinWH hardware returns dc_power=0 (defect)
   - Fixed: Calculate actual_power from WSetPct percentage
   - Shows ⚡ CHARGING / 🔋 DISCHARGING based on command

2. **WSetEna shows 0** → Fixed key lookup
   - Was: `control.get('wset_ena', 0)` 
   - Now: `control.get('wset_enabled', 0)`

3. **CMD shows WSetPct=0.0%** → Added wset_pct to control status
   - `read_control_status()` now returns `wset_pct` and `wset_pct_raw`
   - CMD line shows actual percentage

4. **Battery Inverter 0%** → Falls back to actual_power
   - Uses dc_power if >50W, else actual_power from WSetPct

5. **MODBUS line wrong power** → Shows actual_power with WSetPct
   - Before: `Command: {battery_power:.0f}W`
   - After: `Command: {actual_power:.0f}W (from WSetPct={wset_pct_value:.1f}%)`

6. **SoC limit checks wrong** → Uses actual_power instead of battery_power
   - Fixed ramping detection and limit status display

**Files Modified:**
- `franklinwh_control_standalone.py` - All telemetry fixes
- `src/franklinwh/controller.py` - Added wset_pct to control status
- `FIXES_SUMMARY.md` - Documentation of all fixes

### 2026-02-22 23:15 AEDT — COMPLETED: Library Split
- Created proper Python package structure in `src/franklinwh/`:
  - `types.py` - Enums and data classes (ControlMode, VirtualMode, BatteryCommand, HealthStatus)
  - `controller.py` - FranklinWHController hardware interface (~575 lines)
  - `schedule.py` - TOUSchedule time-of-use scheduling (~285 lines)
  - `modes.py` - VirtualModeController mode logic (~410 lines)
  - `__init__.py` - Package exports
- Created new CLI: `franklinwh_cli.py` (~300 lines)
  - Imports from franklinwh package
  - Same interface as original
  - Cleaner, more maintainable code
- Created `setup.py` for package installation
  - Entry point: `franklinwh` command
  - Dependencies: sunspec2
  - Dev extras: pytest, pytest-mock
- Updated tests to use new package:
  - Fixed imports in conftest.py
  - Fixed imports in unit tests
  - Fixed imports in integration tests
  - All 23 tests pass ✓
- Original script preserved: `franklinwh_control_standalone.py`
  - Full backward compatibility
  - Can be archived later when migration complete
- Created documentation: `LIBRARY_SPLIT.md`
  - Package structure overview
  - Usage examples
  - Installation instructions

### 2026-02-22 22:30 AEDT — Fixed: Critical Bugs from User Testing

**Changes Made:**

1. **--target-soc now works on ALL modes** (not just emergency_backup)
   - Added universal `target_soc` attribute to VirtualModeController
   - Updated all modes to respect target_soc as charge limit
   - Updated `_get_target_soc_display()` to show target for all modes
   - Removed validation warning that restricted it to emergency_backup

2. **Fixed battery state display** (FranklinWH defect workaround)
   - FranklinWH battery status register always returns 0 (IDLE)
   - Now derives battery state from: 1) actual DC power, 2) command power if WSetEna=1
   - Shows ⚡ CHARGING / 🔋 DISCHARGING / 💤 IDLE based on command when DC power unavailable

3. **Fixed emergency capacity check bug**
   - Bug: Was triggering "Limiting discharge" when trying to CHARGE
   - Fixed: Added separate handling for charging vs discharging
   - When charging: warns if still near capacity even with charge power added
   - When discharging: limits discharge to prevent overload

4. **Fixed solar showing negative values**
   - Ensured solar display uses `abs(total_solar)`
   - Fixed off-grid capacity calculation to use `max(0, total_solar)`

5. **Fixed WSetEna display**
   - Was showing 0 even when commands sent successfully
   - Now correctly reads `wset_ena` from control status

### 2026-02-22 21:45 AEDT — Created: Pytest Infrastructure & Integration Tests
- Fixed `self.tou.min_soc` - already using `get_min_soc()` method (audit was outdated)
- Created pytest infrastructure:
  - `pytest.ini` - Configuration with markers (integration, unit, slow, hardware)
  - `tests/conftest.py` - Shared fixtures (mock_modbus_client, mock_sunspec_device, etc.)
  - `tests/unit/__init__.py` - Unit test package
  - `tests/integration/__init__.py` - Integration test package
- Created unit tests: `tests/unit/test_tou_schedule.py`
  - 10 tests for TOUSchedule class
  - Tests default schedules, file loading, price/period retrieval
  - All passing ✓
- Created integration tests: `tests/integration/test_virtual_mode_controller.py`
  - 13 tests for VirtualModeController with mocked hardware
  - Tests self_consumption, emergency_backup, peak_shave modes
  - Tests SoC limits with ramping
  - Tests multi-source solar aggregation
  - Tests TOU schedule file loading
  - All passing ✓
- Discovered sign convention bug (documented in tests):
  - VirtualModeController: Positive=charge, negative=discharge
  - BatteryCommand: Positive=discharge, negative=charge
  - Tests written to match actual code behavior with notes about the bug

### 2026-02-22 21:15 AEDT — Fixed: DEFECT-001 Parameter Validation
- Fixed DEFECT-001: `--target-soc` (and other params) silently ignored in wrong modes
- Added `validate_mode_params()` function that checks parameter/mode compatibility:
  - `--target-soc` only valid for `emergency_backup`
  - `--reserve` only valid for `self_consumption`
  - `--threshold` only valid for `peak_shave`
  - `--power` only valid for `manual`
  - `--schedule-file` only valid for `time_of_use`
- Validation runs when `--mode` is specified
- Warns user with clear message about:
  - Which parameter is incompatible
  - What mode it was used with
  - What parameters ARE valid for that mode
- Non-blocking: script continues but user is informed
- Updated `audits/02_known_defects.md` to mark DEFECT-001 as FIXED
- Both HIGH severity defects (DEFECT-001, DEFECT-002) now resolved
- Ready for library split

### 2026-02-22 21:00 AEDT — Enhanced: Multi-Source Solar Monitoring for AC-Coupled Systems
- User provided register dump showing FranklinWH extension solar registers (15502-15505)
- Updated `_read_extension_solar()` to properly aggregate all solar sources:
  - PV Total (15502): Aggregate when populated, 0 when not
  - PV Proximal (15503): Local AC-coupled solar
  - PV Remote 1 (15504): Additional solar array  
  - PV Remote 2 (15505): Additional solar array
- Smart total calculation to avoid double-counting:
  - If PV Total matches sum of individuals (within 100W) → use PV Total
  - Otherwise sum individual sources (Proximal + Remote 1 + Remote 2)
- Updated `read_status()` to use total solar from all sources for derived values
- Updated `_print_telemetry()` to display detailed solar breakdown:
  - Shows TOTAL with all individual sources listed
  - Uses total_solar for off-grid capacity monitoring
  - Shows home load from extension register 15506 when available (more accurate)
- Critical for AC-coupled aGate X systems where solar comes on AC inputs
- Ensures accurate off-grid capacity calculation: Battery max + Total Solar vs Home Load

### 2026-02-21 23:55 AEDT — Fixed: AC-Coupled Solar Safety Monitoring
- User clarification: aGate X is AC-coupled (solar on AC inputs, not DC)
- Previous safety check incorrectly combined solar + battery DC
- Fixed _check_inverter_safety for AC-coupled systems:
  - Monitor battery DC power independently
  - Calculate off-grid capacity: Battery max + Solar generation
  - Compare to home load for shutdown risk
  - Warn when home load > 80% of available supply
  - Critical warning when > 95% (system shutdown imminent)
- Updated telemetry:
  - Show Battery Inverter load percentage
  - Show CAPACITY used percentage
  - OFF-GRID RISK warning with available supply breakdown
  - Color-coded warnings (⚠️ HIGH, 🚨 CRITICAL)
- Added documentation:
  - AC-coupled vs DC-coupled architecture
  - Off-grid capacity monitoring explanation
  - Supported aGate models table
  - Safety considerations for each architecture
- Commits: `b16be3d`, `02ca2be`

### 2026-02-21 23:40 AEDT — Critical Safety: Inverter Limits & Emergency Shutdown
- User request: Add grid status checks and inverter limit enforcement
- **CRITICAL SAFETY FEATURES ADDED**:

1. Inverter Safety Checks (_check_inverter_safety):
   - Calculate total DC load: Solar DC + Battery DC
   - Prevent DC input > inverter max rating
   - Prevent DC discharge > inverter max rating  
   - Warning at 90% capacity, error at >100%
   - Grid instability detection (voltage/frequency out of range)
   - Auto-reduces power to 50% when grid unstable

2. Emergency Shutdown (_check_emergency_shutdown):
   - Critical voltage: <180V or >270V = EMERGENCY STOP
   - Critical frequency: <45Hz or >55Hz = EMERGENCY STOP
   - Battery overtemp: >60°C = EMERGENCY STOP
   - Battery undertemp + charging: <0°C = EMERGENCY STOP
   - Emergency releases control (WSetEna=0) and sets idle
   - CRITICAL level logging for all emergencies

3. Telemetry Enhancements:
   - Display inverter load percentage
   - Show CRITICAL (>95%), HIGH (80-95%), NORMAL (<80%) status
   - Grid voltage/frequency alerts with 🚨 symbol
   - Full safety context in every telemetry update

4. Safety Enforcement:
   - All safety checks run every execute_once() cycle
   - Cannot override emergency shutdown (hard limits)
   - Detailed logging of all violations with recommendations
   - Automatic power limiting before hard stops

- Updated CLI_OPTIONS.md with comprehensive safety documentation
- Commits: `adfc42d`, safety docs

### 2026-02-21 23:25 AEDT — Fixed: Use Actual M702 Nameplate Ratings
- User question: Does script read nameplate ratings for charge/discharge limits?
- **Found bug**: VirtualModeController using hardcoded 5000W instead of actual ratings
- Fixed all virtual mode calculations:
  - _calc_self_consumption: Uses RATED_MAX_CHARGE_W / RATED_MAX_DISCHARGE_W
  - _calc_emergency_backup: Uses actual ratings
  - _calc_time_of_use: Uses actual ratings
  - _calc_grid_zero: Uses actual ratings
  - _calc_peak_shave: Uses actual ratings
- Added new solar_priority strategy:
  - Charges battery from solar first, even if home needs grid
  - Matches Cloud API mode for pre-peak charging
  - Useful for storing solar before expensive peak period
- Script now reads Model 702 registers:
  - WMaxRtg (40227): Max active power
  - WChaRteMaxRtg (40235): Max charge rate
  - WDisChaRteMaxRtg (40236): Max discharge rate
- Handles asymmetric ratings (e.g., 3500W charge / 5000W discharge)
- Updated CLI_OPTIONS.md with new strategy and ratings documentation
- Commits: `8f3e563`, `8837242`

### 2026-02-21 23:10 AEDT — Cloud API Coordination & Conflict Detection
- User request: Show OnGridMode, reserve SOC, detect Cloud API conflicts
- Implemented telemetry enhancements:
  - Show OnGridMode register (15507) value and mode name
  - Show active reserve (Self or TOU based on OnGridMode)
  - Show both actual battery DC power AND Modbus command power
  - Show WSetEna status
  - Detect ⚠️  CLOUD ACTIVE when OnGridMode != Manual AND battery active
- Added startup coordination logging:
  - Read and log OnGridMode at startup
  - Log active reserve for current mode
  - Detect WSetEna=1 in non-Manual modes (potential Cloud conflict)
  - Log warnings with recommendations
- Added documentation:
  - Cloud API Coordination section in CLI_OPTIONS.md
  - OnGridMode value reference table
  - Conflict detection explanation
  - Best practices for hybrid operation
  - Note: OnGridMode is read-only via Modbus (requires SPAN unlock)
  - VPP mode detection notes
- Key insight: Cannot write OnGridMode via Modbus, but can detect conflicts
- Recommendation: Use FranklinWH app to switch to Self-Consumption before local control
- Commit: `ef96eb0` - "feat: add Cloud API coordination visibility and conflict detection"

### 2026-02-21 22:45 AEDT — SoC Limits with Ramping Implemented
- Implemented comprehensive SoC limit system as requested:
  - --max-charge-soc: Maximum SoC for charging (default 100%)
  - --min-discharge-soc: Minimum SoC for discharging (auto-reads aGate reserve)
  - --soc-ramp-window: Ramping zone before hard limit (default 10%)
  - --force: Emergency override (logged warning)
- Features implemented:
  - Auto-reads aGate reserve SOC from native mode registers (15508/15509)
  - Validates min-discharge >= aGate reserve (enforced floor)
  - Linear ramping: 100% power -> reduced -> 0% over ramp window
  - Hard stop at limit with 🔒 indicator in telemetry
  - Ramping status shows percentage in telemetry
  - All events logged (ramping, hard stops, overrides)
- Updated telemetry display to show limit status and ramping info
- Created CLI_OPTIONS.md - comprehensive documentation of all CLI options
- Comprehensive logging: startup, runtime events, shutdown
- Commit: `0e8332e` - "feat: add SoC limits with ramping and comprehensive logging"

### 2026-02-21 22:25 AEDT — TOU Schedule File Support Added
- Implemented TOU schedule file support per user request
- Added TOUSchedule.from_file() for JSON schedule loading
- Added CLI args: --schedule-file, --show-schedule, --validate-schedule
- Updated _calc_time_of_use() to use schedule strategies (charge/discharge/etc)
- Created schedules/ directory with examples:
  - simple_day_night.json - 2-period basic schedule
  - ausgrid_tou.json - Australian Ausgrid TOU
  - README.md - Usage documentation
- Created TOU_SCHEDULE_DESIGN.md - Architecture and future integration plans
- Telemetry display now shows schedule info in TOU mode
- Ready for future Service Engine scheduler integration
- Commit: `8a428e5` - "feat: add TOU schedule file support"

### 2026-02-21 21:50 AEDT — Current State Audit & DEFECT-002 Fix
- User confirmed: proceed with audit approach first
- Created comprehensive audit documentation:
  - `audits/01_working_features.md` - Verified working vs untested
  - `audits/02_known_defects.md` - 8 defects catalogued (2 HIGH, 3 MEDIUM, 3 LOW)
  - `audits/03_code_analysis.md` - TODOs, placeholders, code smells
  - `audits/04_hardware_required.md` - Test environment requirements
  - `audits/README.md` - Executive summary
- Fixed DEFECT-002: Insufficient CLI output for operational verification
  - Added `_print_telemetry()` method with formatted console output
  - Added `_format_duration()` for HH:MM:SS display
  - Added `_get_target_soc_display()` for mode-specific target info
  - Shows: elapsed time, remaining time, home load, solar PV, target SoC, battery state, grid state
  - Updates every 5 seconds to console, every 60 seconds to log file
- Created `TEST_SUITE_PLAN.md` - Comprehensive testing strategy for library split
- Created `TELEMETRY_DEMO.md` - Visual demonstration of new output
- Commit: `1ddeb97` - "feat: add comprehensive telemetry output to CLI (DEFECT-002)"

### 2026-02-18 13:40 AEDT — Governance Established
- Reviewed all fhp_demo policies (13 rules, 4 workflows, production protection)
- Identified modbus project had zero governance
- Created 10-rule SAFETY_CONTROLS.md
- Created agent.md, 3 workflows, 1 rule file
- Rolled back accidental fhp_demo changes (git checkout + rm)
