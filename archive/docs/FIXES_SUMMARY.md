# FranklinWH Control Fixes Summary

**Date:** 2026-02-22  
**Files Modified:** `franklinwh_control_standalone.py`, `src/franklinwh/controller.py`

## Bugs Fixed

### 1. Battery Always Shows "IDLE 0W"
**Problem:** FranklinWH hardware returns 0 for DC power (Model 713), so battery state always shows IDLE.

**Fix:** Derive battery state from WSetPct when DC power is unavailable:
- If `dc_power > 50W`: Use actual DC power
- If `wset_ena == 1` and `actual_power > 50W`: Derive from WSetPct percentage
- Otherwise: Show IDLE

**Code Changes:**
```python
# Calculate actual power from WSetPct (what firmware actually uses)
wset_pct_value = control.get('wset_pct', 0)
rated_max = getattr(self.ctrl, 'RATED_MAX_W', 5000)
if wset_ena == 1:
    actual_power = wset_pct_value / 100.0 * rated_max
else:
    actual_power = battery_power

# Battery state display
if abs(dc_power) > 50:
    # Use actual DC power
elif wset_ena == 1 and abs(actual_power) > 50:
    # Derive from WSetPct
```

### 2. WSetEna Shows as 0 in Telemetry
**Problem:** Wrong key name used - was looking for `'wset_ena'` but dictionary has `'wset_enabled'`.

**Fix:** Changed key lookup:
```python
# Before
wset_ena = control.get('wset_ena', 0)  # Wrong!

# After  
wset_ena = control.get('wset_enabled', 0)  # Correct!
```

### 3. CMD Shows WSetPct=0.0% When Active
**Problem:** `read_control_status()` didn't return `wset_pct`, only `wset_watts`.

**Fix:** Added WSetPct reading to control status:
```python
sf_pct = self._get_scale_factor(m704, 'WSetPct_SF')
return {
    'wset_enabled': m704.WSetEna.value,
    'wset_mode': m704.WSetMod.value,
    'wset_watts': m704.WSet.value * (10 ** sf_w),
    'wset_pct': m704.WSetPct.value * (10 ** sf_pct),  # Added
    'wset_pct_raw': m704.WSetPct.value,  # Added
    ...
}
```

### 4. Battery Inverter Load Shows 0%
**Problem:** Used only `dc_power` which is always 0 from hardware.

**Fix:** Fall back to `actual_power` when DC power unavailable:
```python
# Use actual DC power if available, otherwise derive from command
battery_dc_load = abs(dc_power) if abs(dc_power) > 50 else abs(actual_power)
```

### 5. MODBUS Line Showed Wrong Power
**Problem:** Showed `battery_power` (from WSet) instead of actual command power.

**Fix:** Display `actual_power` derived from WSetPct:
```python
# Before
print(f"  MODBUS:     WSetEna={wset_ena} | Command: {battery_power:.0f}W")

# After
print(f"  MODBUS:     WSetEna={wset_ena} | Command: {actual_power:.0f}W (from WSetPct={wset_pct_value:.1f}%)")
```

### 6. CMD Line Showed Wrong Values
**Problem:** Used unscaled values and wrong power variable.

**Fix:** Use scaled WSetPct and actual_power:
```python
# Before
print(f"  CMD: WSetPct={control.get('wset_pct', 0):.1f}%  ({battery_power:.0f}W)")

# After
print(f"  CMD: WSetPct={wset_pct_value:.1f}%  ({actual_power:.0f}W)")
```

## Bug Fixes (2026-02-23)

### 12. AC Type and Grid State Information
**Problem:** `--status` and `--healthcheck` didn't show AC type (single/split/three-phase), grid connection state, or grid mode (following/forming).

**Fix:** Enhanced `read_grid_status()` in both original and library:
- **AC Type**: Detected from voltage (230V=Single, 120V=Single, 400V=Three)
- **Connection State**: From Model 701 ConnSt (Connected/Disconnected/Fault)
- **Grid Mode**: From DERMode upper bits (Grid Following/Grid Forming)
- **Inverter State**: From Model 701 InvSt (Running/Standby/Fault/etc)

**Example --status output:**
```
  GRID:
    AC Type:      Single-Phase (230V Nominal)
    Voltage:      241.8V
    Frequency:    50.00Hz
    Power:        18W
    Connection:   Connected
    Grid Mode:    Grid Following (default)
    Inv State:    Running
```

### 13. Nameplate Display Cleanup
**Problem:** Nameplate fields showed register prefixes like "Mn: FranklinWH", "Md: aGate X".

**Fix:** Added `clean_value()` helper to strip prefixes (Mn:, Md:, SN:, Vr:, Opt:) from display.

**Before:**
```
Manufacturer: Mn:  FranklinWH Technologies Co., Ltd
Model:        Md:  aGate X
```

**After:**
```
Manufacturer: FranklinWH Technologies Co., Ltd
Model:        aGate X
```

### 14. Zombie State Display Fix
**Problem:** Healthcheck showed `✗ zombie_state: FAIL` when WSetEna=0 (which is actually correct).

**Fix:** Special handling for zombie_state - shows "OK (not in zombie state)" when False, "🚨 ZOMBIE STATE DETECTED" when True.

### 15. Comprehensive Alarm Monitoring
**Problem:** Limited alarm checking - only basic Alrm bitfield checked.

**Fix:** Added full alarm monitoring system:
- **System Alarms** (Model 701): Ground fault, over temp, disconnects, etc.
- **DC Port Alarms** (Model 714): Battery voltage/current faults
- **Battery Status** (Model 713): FAULT state detection
- **Solar Events** (Model 502): PV string faults
- **Blocking Detection**: Critical faults prevent operation

**New CLI Options:**
```bash
# Check all alarms
python franklinwh_control_standalone.py -i 192.168.0.110 --check-alarms

# Clear alarms if safe
python franklinwh_control_standalone.py -i 192.168.0.110 --clear-alarms
```

**Alarm Reset:**
- Register: 41094 (Model 715 AlarmReset)
- Only clears if no critical faults active
- Requires manual intervention for: GROUND_FAULT, MANUAL_SHUTDOWN, BATTERY_FAULT

**Example --status output:**
```
  Alarms & Events
  ────────────────────────────────────────
  ⚠ System Alarms:   0x00000100
                     → OVER_TEMP
  ✓ DC Port Alarms:  None
  ✓ Battery Status:  IDLE
```

### 10. HealthStatus Field Mismatch
**Problem:** Library `HealthStatus` dataclass had `issues` field but controller used `message`.

**Fix:** 
- Updated `types.py` HealthStatus to use `message: str` instead of `issues: list`
- Fields now: `healthy`, `message`, `recommendations`, `details`, `zombie_state`

### 11. Model 1 Nameplate Info
**Problem:** Device manufacturer, model, serial, firmware not displayed.

**Fix:** 
- Added `read_nameplate()` method to read Model 1 (Common)
- Returns: manufacturer, model, serial, version, options
- Added to `--status` output
- Added to `--healthcheck` output

**Example output:**
```
  DEVICE:
    Manufacturer: FranklinWH
    Model:        aGate X
    Serial:       FW123456789
    Firmware:     2.1.4
```

## Additional Improvements

### 7. Clear Startup State Summary
**Problem:** Current state was buried in logs, conflicts not obvious.

**Fix:** Added `check_startup_state()` and `print_startup_summary()` functions:
```bash
# Now shows clear summary at startup:
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

### 8. Conflict Detection
**Problem:** Would try to take control even when aGate already active in conflicting mode.

**Fix:** 
- Detects when aGate is already charging/discharging in different mode
- Warns about mode mismatches (e.g., aGate in TOU but requesting manual)
- Exits with clear options unless `--reset-on-start` used

### 9. Quiet Mode
**Problem:** Too many INFO messages cluttered output.

**Fix:** Added `--quiet` / `-q` flag:
```bash
# Only warnings and errors shown
python franklinwh_control_standalone.py -i 192.168.0.110 -q --mode manual --power -4000
```

## Files Modified

1. **`franklinwh_control_standalone.py`** (original script)
   - `read_control_status()`: Added `wset_pct` and `wset_pct_raw`
   - `_print_telemetry()`: Fixed all display issues
   - `check_startup_state()`: NEW - comprehensive state check
   - `print_startup_summary()`: NEW - clear visual state display
   - `main()`: Added `--quiet` flag, integrated state checking

2. **`src/franklinwh/controller.py`** (library)
   - `read_control_status()`: Added `wset_pct` and `wset_pct_raw`
   - `check_state()`: NEW - state check method for library users

## Testing

### Verify telemetry fixes:
```bash
python franklinwh_control_standalone.py -i 192.168.0.110 --mode manual --power -4000 --reset-on-start --duration 60
```

Expected output:
- BATTERY: ⚡ CHARGING 4000W (not IDLE 0W)
- MODBUS: WSetEna=1 | Command: -4000W (from WSetPct=-80.0%)
- CMD: WSetPct=-80.0% (-4000W)
- BATTERY INVERTER: 80% (4000W / 5000W)

### Test quiet mode:
```bash
python franklinwh_control_standalone.py -i 192.168.0.110 -q --mode manual --power -4000
```

### Test conflict detection:
```bash
# When aGate is already active in different mode
python franklinwh_control_standalone.py -i 192.168.0.110 --mode manual --power -4000
# Should show conflicts and suggest --reset-on-start
```

## Usage Recommendations

### Interactive Use (Original Script)
```bash
# Full telemetry and startup summary
python franklinwh_control_standalone.py -i 192.168.0.110 --mode manual --power -4000 --reset-on-start --duration 60

# Quiet mode (warnings only)
python franklinwh_control_standalone.py -i 192.168.0.110 -q --mode manual --power -4000
```

### Programmatic Use (Library)
```python
from franklinwh import FranklinWHController

ctrl = FranklinWHController('192.168.0.110')
ctrl.connect()

# Check current state
state = ctrl.check_state()
print(f"SoC: {state['soc']}%, Activity: {state['battery_activity']}")

if state['conflicts']:
    print("Conflicts detected:", state['conflicts'])
```

## Note on Library Package

The new CLI (`franklinwh_cli.py`) is simpler and doesn't include full telemetry display. The original script (`franklinwh_control_standalone.py`) is preserved with all fixes and remains the recommended tool for interactive use.
