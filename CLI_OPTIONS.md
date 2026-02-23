# FranklinWH Control Standalone - CLI Options Reference

> **Version**: 1.2.0  
> **Date**: 2026-02-23  
> **Status**: Added --charge, --discharge, --standby flags

---

## Quick Start

```bash
# Health check
python franklinwh_control_standalone.py -i 192.168.0.110 --healthcheck

# Manual control - CHARGE at 3000W (new explicit flag)
python franklinwh_control_standalone.py -i 192.168.0.110 \
  --reset-on-start --mode manual --charge 3000 \
  --max-charge-soc 95

# Manual control - DISCHARGE at 3000W
python franklinwh_control_standalone.py -i 192.168.0.110 \
  --reset-on-start --mode manual --discharge 3000 \
  --min-discharge-soc 20

# TOU mode with schedule file
python franklinwh_control_standalone.py -i 192.168.0.110 \
  --reset-on-start --mode time_of_use \
  --schedule-file schedules/ausgrid_tou.json
```

---

## Connection Parameters

### `-i, --ip` (Required for hardware operations)
**Type**: String  
**Required**: Yes (except for --validate-schedule, --show-schedule)  
**Example**: `-i 192.168.0.110`

aGate IP address for Modbus TCP connection.

---

### `-p, --port`
**Type**: Integer  
**Default**: `502`  
**Example**: `-p 502`

Modbus TCP port. Standard Modbus TCP port is 502.

---

### `-u, --unit`
**Type**: Integer  
**Default**: `2`  
**Example**: `-u 2`

Modbus unit ID (slave address). FranklinWH aGate default is 2.

---

### `-t, --timeout`
**Type**: Float  
**Default**: `10.0`  
**Example**: `-t 15.0`

Connection timeout in seconds. Increase for slow networks.

---

## Startup Behavior

### `--reset-on-start`
**Type**: Flag  
**Required**: Recommended for virtual modes

Reset control state to idle before operation. Clears any stale WSetEna state.

**When to use**:
- First run of the day
- After previous run crashed
- When health check reports zombie state
- Always for virtual modes

---

### `--assume-clean-state`
**Type**: Flag  
**Use with caution**

Skip health check warnings. Use only when you're certain the state is clean.

---

## Direct Control (Original)

### `--power`
**Type**: Float  
**Unit**: Watts  
**Example**: `--power 3000` (charge), `--power -3000` (discharge)

Direct power control. Positive = charge battery (import from grid), Negative = discharge battery (export to grid).

**⚠️ Legacy**: Use `--charge` or `--discharge` for clarity instead.

**Note**: Actual power may be limited by:
- Device ratings (from Model 702)
- SoC limits (--max-charge-soc, --min-discharge-soc)
- Ramping as SoC approaches limits

---

### `--charge`
**Type**: Float  
**Unit**: Watts  
**Example**: `--charge 3000`

Charge battery at specified watts. Imports power from grid.

**Mutually exclusive with**: `--power`, `--discharge`, `--standby`

---

### `--discharge`
**Type**: Float  
**Unit**: Watts  
**Example**: `--discharge 3000`

Discharge battery at specified watts. Exports power to grid.

**Mutually exclusive with**: `--power`, `--charge`, `--standby`

---

### `--standby`
**Type**: Flag

Set battery to standby (0W). No charging or discharging.

**Mutually exclusive with**: `--power`, `--charge`, `--discharge`

---

### `--idle`
**Type**: Flag

Set battery to idle (0W). Equivalent to `--standby`.

**Deprecated**: Use `--standby` instead.

---

### `--stop`
**Type**: Flag

Release Modbus control (WSetEna=0) and exit. Returns aGate to its configured operating mode (e.g., Self-Consumption).

**Use this**:
- When you're done controlling the battery
- To resume normal aGate operation
- Before switching to a different control method

---

### `--revert`
**Type**: Integer  
**Default**: `0`  
**Unit**: Seconds  
**Example**: `--revert 3600`

Auto-revert time in seconds.

**Note**: FranklinWH firmware does not implement WSetRvrtTms per PICS. The script will wait but the aGate will NOT auto-revert. Always use `--stop` or Ctrl+C to properly release control.

---

## Virtual Modes

### `--mode`
**Type**: Choice  
**Choices**: `self_consumption`, `emergency_backup`, `time_of_use`, `grid_zero`, `peak_shave`, `manual`

Virtual operating mode. Software-implemented battery modes using direct WSetPct control.

| Mode | Description | Key Parameters |
|------|-------------|----------------|
| `manual` | Direct power control | `--charge`, `--discharge` |
| `self_consumption` | Maximize solar self-use | `--reserve` |
| `emergency_backup` | Keep full for outages | `--target-soc` |
| `time_of_use` | Price arbitrage | `--schedule-file` |
| `grid_zero` | Minimize grid import/export | None |
| `peak_shave` | Discharge during high demand | `--threshold` |

---

### `--reserve`
**Type**: Integer  
**Default**: `20`  
**Unit**: Percent  
**Applies to**: `self_consumption` mode

Self-consumption reserve percentage. Battery will not discharge below this SoC.

**Note**: This is the SOFTWARE reserve. The aGate has its own hardware reserve (read automatically). The effective reserve is MAX(software, hardware).

---

### `--target-soc`
**Type**: Integer  
**Default**: `95`  
**Unit**: Percent  
**Applies to**: `emergency_backup` mode

Emergency backup target SoC. Battery will charge to this level using available sources.

---

### `--threshold`
**Type**: Integer  
**Default**: `2000`  
**Unit**: Watts  
**Applies to**: `peak_shave` mode

Peak shave threshold. Battery will discharge when home load exceeds this value.

---

### `--duration`
**Type**: Integer  
**Unit**: Seconds  
**Example**: `--duration 7200` (2 hours)

Mode duration. Script will run for N seconds then exit cleanly.

---

## SoC Limits (NEW)

### `--max-charge-soc`
**Type**: Integer  
**Default**: `100`  
**Unit**: Percent  
**Range**: 1-100

Maximum SoC for charging. Charging will ramp down as SoC approaches this limit.

**Ramping behavior**:
- Full power up to (limit - ramp_window)
- Linear ramp from (limit - ramp_window) to limit
- Zero power at limit

**Example**: `--max-charge-soc 90` with 10% ramp window:
- 0-80%: Full charge power
- 80-90%: Ramping down
- ≥90%: Zero charge power

---

### `--min-discharge-soc`
**Type**: Integer  
**Default**: Read from aGate  
**Unit**: Percent  
**Range**: 1-100

Minimum SoC for discharging. Discharging will ramp down as SoC approaches this limit.

**Important**: This is automatically constrained to be ≥ aGate's reserve SOC (read from registers 15508/15509). You cannot discharge below the aGate's configured reserve.

**Ramping behavior**:
- Full power down to (limit + ramp_window)
- Linear ramp from (limit + ramp_window) to limit
- Zero power at limit

**Example**: `--min-discharge-soc 20` with 10% ramp window:
- 100-30%: Full discharge power
- 30-20%: Ramping down
- ≤20%: Zero discharge power

---

### `--soc-ramp-window`
**Type**: Integer  
**Default**: `10`  
**Unit**: Percent  
**Range**: 1-50

SoC ramping window size. Power reduction starts this percentage before the hard limit.

Larger = smoother transition, more conservative  
Smaller = sharper cutoff, closer to limits

---

### `--force`
**Type**: Flag  
**Use with caution**

Force operation even if SoC limits would normally prevent it.

**Logged**: WARNING level with explicit "user override" message  
**Risk**: May discharge below reserve or charge above safe levels  
**Use case**: Emergency situations only

---

## TOU Schedule

### `--schedule-file`
**Type**: String (filepath)  
**Example**: `--schedule-file schedules/ausgrid_tou.json`

TOU schedule JSON file for `time_of_use` mode.

Schedule defines:
- Time periods with different electricity prices
- Battery strategy per period (charge/discharge/self_consumption/grid_zero/standby)
- Constraint rules (min_soc, max_soc, etc.)

See `schedules/README.md` for format specification.

---

### `--show-schedule`
**Type**: String (filepath)  
**No hardware required**

Display schedule file contents and exit. Useful for verification.

```bash
python franklinwh_control_standalone.py --show-schedule schedules/ausgrid_tou.json
```

---

### `--validate-schedule`
**Type**: String (filepath)  
**No hardware required**

Validate schedule file schema and exit.

```bash
python franklinwh_control_standalone.py --validate-schedule schedules/my_schedule.json
```

---

## Information & Debugging

### `--status`
**Type**: Flag

Read and display comprehensive system status, then exit.

Shows:
- Battery status (SoC, SoH, power, temperature)
- Grid status (voltage, frequency, power flow)
- Solar PV status
- Control state (WSetEna, WSetPct)
- FranklinWH native mode
- Alarms and warnings

---

### `--healthcheck`
**Type**: Flag

Run comprehensive health check and exit.

Checks:
- Modbus connection
- Critical model availability (704, 713, 701)
- Zombie state detection
- SoC safety bounds
- Grid voltage/frequency limits
- SPAN extension availability

Exit code: 0 if healthy, 1 if issues detected

---

### `--dry-run`
**Type**: Flag

Validate configuration without writing to hardware.

Shows what WOULD be sent to the aGate without actually sending it.

---

### `-v, --verbose`
**Type**: Flag

Enable debug logging. All Modbus operations and calculations are logged.

**Without -v**: INFO level logging (startup, shutdown, errors, telemetry)  
**With -v**: DEBUG level logging (all Modbus reads/writes, calculations)

---

## Parameter Compatibility Matrix

| Parameter | manual | self_consumption | emergency_backup | time_of_use | grid_zero | peak_shave |
|-----------|--------|------------------|------------------|-------------|-----------|------------|
| `--power` | ✅ Required | ❌ N/A | ❌ N/A | ❌ N/A | ❌ N/A | ❌ N/A |
| `--reserve` | ❌ N/A | ✅ Used | ❌ N/A | ❌ N/A | ❌ N/A | ❌ N/A |
| `--target-soc` | ❌ N/A | ❌ N/A | ✅ Used | ❌ N/A | ❌ N/A | ❌ N/A |
| `--threshold` | ❌ N/A | ❌ N/A | ❌ N/A | ❌ N/A | ❌ N/A | ✅ Used |
| `--schedule-file` | ❌ N/A | ❌ N/A | ❌ N/A | ✅ Optional | ❌ N/A | ❌ N/A |
| `--max-charge-soc` | ✅ Used | ✅ Used | ✅ Used | ✅ Used | ✅ Used | ✅ Used |
| `--min-discharge-soc` | ✅ Used | ✅ Used | ✅ Used | ✅ Used | ✅ Used | ✅ Used |
| `--soc-ramp-window` | ✅ Used | ✅ Used | ✅ Used | ✅ Used | ✅ Used | ✅ Used |
| `--force` | ✅ Used | ✅ Used | ✅ Used | ✅ Used | ✅ Used | ✅ Used |

**Legend**: ✅ Used | ❌ N/A (ignored) | ✅ Required (must specify)

---

## Safety Hierarchy

When multiple constraints apply, the most restrictive wins:

```
1. Hard limits (always enforced)
   ├── Device max charge/discharge (from Model 702)
   ├── Absolute SoC bounds (0-100%)
   └── Emergency stop (Ctrl+C, errors)

2. SoC limits (enforced, can be overridden with --force)
   ├── --max-charge-soc (with ramping)
   ├── --min-discharge-soc (with ramping)
   │   └── Auto-constrained to ≥ aGate reserve SOC
   └── --soc-ramp-window (defines transition zone)

3. Mode-specific constraints
   ├── --target-soc (emergency_backup target)
   ├── --reserve (self_consumption floor)
   ├── --threshold (peak_shave trigger)
   └── Schedule strategies (time_of_use periods)

4. User override (logged, use with caution)
   └── --force (ignores SoC limits for emergency)
```

---

## Logging

### Log Levels

| Level | What Gets Logged |
|-------|------------------|
| ERROR | Failures, connection errors, safety violations |
| WARNING | Clamped values, zombie state, degraded operation |
| INFO | Startup, shutdown, mode changes, telemetry (every 60s) |
| DEBUG | All Modbus operations, calculations, register values (with -v) |

### Log Destinations

1. **Console (stdout)**: Telemetry display (5-second updates in virtual modes)
2. **File**: Full logging to configured log file
3. **Standard error**: Errors and warnings

### Startup Logging

Every startup logs:
- Script version and arguments
- Connection parameters (IP, port, unit)
- Device ratings (from Model 702)
- Initial SoC and health status
- Mode and parameters selected

### Runtime Logging

During operation logs:
- Every command sent (with WSetPct values)
- Mode transitions
- SoC limit activations (ramping events)
- Telemetry summary (every 60 seconds)
- Any errors or warnings

### Shutdown Logging

On exit logs:
- Shutdown reason (duration expiry, signal, error)
- Control release attempt and result
- Final SoC and status
- Duration of operation

---

## Examples

### Example 1: Conservative Discharge with SoC Limit

```bash
python franklinwh_control_standalone.py -i 192.168.0.110 \
  --reset-on-start --mode manual --power -3000 \
  --min-discharge-soc 30 --soc-ramp-window 15
```

- Discharge at 3kW
- Start ramping down at 45% SoC (30 + 15)
- Hard stop at 30% SoC
- Note: If aGate reserve is 20%, effective limit is 30% (user value wins)

---

### Example 2: Charge to 90% Only

```bash
python franklinwh_control_standalone.py -i 192.168.0.110 \
  --reset-on-start --mode manual --power 3000 \
  --max-charge-soc 90
```

- Charge at 3kW
- Start ramping down at 80% SoC (90 - 10)
- Hard stop at 90% SoC

---

### Example 3: TOU with Schedule and Limits

```bash
python franklinwh_control_standalone.py -i 192.168.0.110 \
  --reset-on-start --mode time_of_use \
  --schedule-file schedules/ausgrid_tou.json \
  --min-discharge-soc 15 --max-charge-soc 95 \
  --duration 86400
```

- Run TOU mode for 24 hours
- Use Ausgrid schedule (peak discharge, off-peak charge)
- Never discharge below 15% (or aGate reserve, whichever is higher)
- Never charge above 95%

---

### Example 4: Emergency Discharge (Override)

```bash
python franklinwh_control_standalone.py -i 192.168.0.110 \
  --reset-on-start --mode manual --power -5000 \
  --min-discharge-soc 10 --force
```

- Maximum discharge (5kW)
- Attempt to discharge down to 10% SoC
- ⚠️ WARNING: May violate reserve settings
- ⚠️ Logged: "SoC limit override activated - user assumes risk"

---

## Notes for Library Split

This documentation covers the **monolithic script** (`franklinwh_control_standalone.py`).

After library split:
- CLI options → `franklinwh_modbus_cli.py`
- Core logic → `franklinwh_modbus_lib.py`
- Documentation → separate files per component

---

*End of CLI Options Reference*

---

## Cloud API Coordination

### Understanding OnGridMode

The aGate maintains an `OnGridMode` register (15507) that indicates which operating mode it's in:

| Value | Mode | Reserve Register | Typical Controller |
|-------|------|------------------|-------------------|
| 0 | Emergency Backup | None | Cloud API (manual set) |
| 1 | Self-Consumption | 15508 (Self) | Cloud API or local |
| 2 | Time-of-Use | 15509 (TOU) | Cloud API scheduler |
| 3 | Manual | None | Modbus / Local control |

**Key Point**: Modbus writes to WSetPct work regardless of OnGridMode, but the Cloud API expects to control modes 0-2. Mode 3 (Manual) is intended for external Modbus control.

### Coordination Strategy

When using this script alongside Cloud API:

1. **Check Current Mode First**:
   ```bash
   python franklinwh_control_standalone.py -i 192.168.0.110 --status
   ```
   Look for "OnGridMode" in the output.

2. **Switch to Self-Consumption (Recommended)**:
   The Cloud API handles TOU scheduling in mode 2, but if you want to use this script for specific control:
   - Use FranklinWH app to switch to "Self-Consumption" mode
   - Or switch to "Manual" mode if available

3. **Use `--reset-on-start`**:
   This ensures WSetEna is cleared and we take control via Modbus.

4. **Monitor for Conflicts**:
   The telemetry now shows:
   - `OnGridMode` - what the aGate thinks it's doing
   - `Reserve` - active reserve for that mode
   - `⚠️  CLOUD ACTIVE` - warning if battery active while not in Manual mode

### Conflict Detection

The script detects potential conflicts:

```
MODE: MANUAL ⚠️  CLOUD ACTIVE (OnGridMode=TOU)
```

This means:
- We're trying to run in Manual mode
- But OnGridMode is still TOU (Cloud API scheduler active)
- Battery is charging/discharging (likely from Cloud TOU schedule)
- Our Modbus commands may conflict with Cloud commands

**Resolution**:
1. Stop this script (Ctrl+C)
2. Use FranklinWH app to switch to Self-Consumption or Manual mode
3. Restart script with `--reset-on-start`

### Reserve SOC Coordination

The reserve SOC registers (15508/15509) are **read-only via Modbus** (require SPAN installer unlock to write). However, you can set them via:
- FranklinWH mobile app
- Cloud API (if you have access)

**Important**: The `--min-discharge-soc` parameter is constrained to be ≥ the aGate's reserve SOC. If the aGate reserve is 20%, you cannot discharge below 20% via Modbus (the aGate will enforce its own limit).

### Writing to OnGridMode

**Not possible via standard Modbus** - requires SPAN installer unlock.

This means:
- We cannot switch the aGate from TOU to Manual mode via this script
- You must use the FranklinWH app or Cloud API to change modes
- Our Modbus control works regardless, but Cloud may override

### Best Practices

1. **Before starting control**:
   ```bash
   # Check current state
   python franklinwh_control_standalone.py -i 192.168.0.110 --status
   
   # If OnGridMode is TOU or Backup, consider switching via app first
   # Then run with reset
   python franklinwh_control_standalone.py -i 192.168.0.110 \
     --reset-on-start --mode manual --power -2000
   ```

2. **Monitor telemetry**:
   Watch for `⚠️  CLOUD ACTIVE` warnings which indicate conflicts.

3. **Always release control when done**:
   ```bash
   python franklinwh_control_standalone.py -i 192.168.0.110 --stop
   ```
   This sets WSetEna=0 and allows Cloud API to resume control.

4. **Use Self-Consumption mode for hybrid operation**:
   - Set aGate to Self-Consumption via app
   - Use this script for temporary overrides
   - aGate will return to Self-Consumption when script stops

---

## VPP Mode Detection

**VPP (Virtual Power Plant) Mode** is when the battery is under active dispatch control:

- WSetEna = 1 (active control enabled)
- WSetPct ≠ 0 (power command active)
- OnGridMode may be any value

The telemetry shows:
```
MODBUS:     WSetEna=1 | Command: -2500W
```

If you didn't set this command, another controller (Cloud API, VPP aggregator) is active.

**To take control**:
1. Use `--reset-on-start` to clear WSetEna
2. This forces WSetEna=0, releasing other controllers
3. Then we set our own WSetPct values

**Note**: Some VPP contracts may penalize you for overriding their commands. Check your agreement before using `--reset-on-start` during VPP events.


### Strategy: solar_priority

**Purpose**: Prioritize charging battery from solar, even if home loads need grid power

**Behavior**:
- All solar generation goes to battery charging first
- Home loads are powered from grid (not solar)
- Only when battery is nearly full does solar power the home

**Use case**: 
- Pre-peak charging: Before expensive peak pricing period, maximize battery storage
- Next-day preparation: Store solar for next morning before sun rises
- Grid arbitrage: Accept small grid import now to avoid large grid import later

**Example schedule**:
```json
{
  "periods": [
    {
      "id": "pre_peak",
      "name": "Pre-Peak Charging",
      "hours": [13, 14, 15],
      "price": 0.25,
      "strategy": "solar_priority"
    }
  ]
}
```

**Trade-off**: 
- ⚠️ May increase grid import during this period
- ✅ Maximizes battery storage for later use
- ✅ Better than grid charging (uses free solar)

---

## Device Ratings (M702)

The script automatically reads your aGate's nameplate ratings from SunSpec Model 702:

| Register | Description | Example |
|----------|-------------|---------|
| WMaxRtg | Maximum active power | 5000W |
| WChaRteMaxRtg | Maximum charge rate | 5000W |
| WDisChaRteMaxRtg | Maximum discharge rate | 5000W |

These ratings are:
- Read automatically on connection
- Used to clamp user-specified power values
- Used by virtual modes for maximum calculations
- Displayed in `--status` output

**Asymmetric example**: Some models may have:
- Charge: 3500W
- Discharge: 5000W

The script handles this automatically.


---

## Safety Features

### Automatic Safety Checks

The script performs multiple safety checks every control cycle:

#### 1. Inverter DC Load Limits

**What it does**: Prevents total DC power (solar + battery) from exceeding inverter rating

```
Total DC In = Solar DC + Battery Charging DC
Total DC Out = Battery Discharge DC

If Total DC In > Max Rating → Reduce charging
If Total DC Out > Max Rating → Reduce discharging
```

**Example scenario**:
- Solar: 4000W
- User requests: Charge at 3000W
- Inverter max: 5000W
- **Result**: Charge limited to 1000W (4000 + 1000 = 5000W)

**Logged**: ERROR level with "INVERTER SAFETY" prefix

#### 2. Grid Stability Monitoring

**Grid voltage limits**:
- Normal: 210-250V
- Warning: 200-210V or 250-260V
- **Emergency stop**: <180V or >270V

**Grid frequency limits**:
- Normal: 48-52Hz  
- Warning: 47-48Hz or 52-53Hz
- **Emergency stop**: <45Hz or >55Hz

**Behavior**:
- Warning: Power limited to 50%
- Emergency: Immediate shutdown, control released

#### 3. Battery Temperature Protection

**Overheating**:
- >60°C: Emergency stop
- Prevents thermal damage

**Freezing**:
- <0°C + charging: Emergency stop
- Lithium plating protection

#### 4. SoC Limits with Ramping

See [--max-charge-soc](#--max-charge-soc) and [--min-discharge-soc](#--min-discharge-soc)

### Emergency Shutdown Behavior

When emergency conditions detected:

1. **Log CRITICAL message** with full details
2. **Release Modbus control** (WSetEna=0)
3. **Set battery idle** (0W)
4. **Set shutdown flag** (stops run_continuous)
5. **Exit with error code** (if possible)

**Recovery**:
- Check and resolve grid/battery issues
- Restart script manually
- Review logs for root cause

### Telemetry Safety Display

```
⚠️  INVERTER LOAD: 95% (4750W / 5000W) - CRITICAL!
```

Inverter load colors:
- **Normal** (<80%): No warning
- **⚠️ HIGH** (80-95%): Yellow warning
- **⚠️ CRITICAL** (>95%): Red warning, may trigger limiting

```
🚨 GRID ALERT: ⚠️ VOLTAGE 195.5V ⚠️ FREQUENCY 47.2Hz
```

Grid alert appears when:
- Voltage outside 210-250V
- Frequency outside 48-52Hz

### Safety Hierarchy

```
1. ABSOLUTE EMERGENCY (immediate stop)
   ├── Grid voltage <180V or >270V
   ├── Grid frequency <45Hz or >55Hz
   ├── Battery temperature >60°C
   └── Battery <0°C + charging attempted

2. INVERTER PROTECTION (power limiting)
   ├── DC input > rated max
   ├── DC output > rated max
   └── Grid unstable (reduce power 50%)

3. SoC PROTECTION (ramping + limits)
   ├── Max charge SoC reached
   ├── Min discharge SoC reached
   └── Reserve SoC enforcement

4. USER LIMITS (clamp to requested)
   ├── --power value
   └── Mode calculations
```

### Best Practices for Safe Operation

1. **Monitor telemetry** for warnings
2. **Don't ignore** ⚠️ and 🚨 symbols
3. **Check logs** after any safety event
4. **Use --status first** to verify grid health
5. **Start conservative** with power limits
6. **Have --stop ready** for quick shutdown


---

## AC-Coupled vs DC-Coupled Systems

### aGate X (AC-Coupled)

**Architecture**:
- Solar panels → AC solar inputs (2x 63A circuits)
- AC solar → Internal rectifier → DC bus
- Battery ↔ DC bus ↔ Inverter → AC output
- Grid ↔ AC output

**Monitoring**:
- **Model 714**: Battery DC power only (not solar!)
- **Model 502**: Solar AC output
- **Model 701**: Grid/AC power

**Safety Considerations**:
- Battery inverter is separate from solar AC inputs
- Total home load can be: Battery discharge + Solar AC - Grid export
- Off-grid risk: If home load > (Battery max + Solar), system shuts down

### aPower S (DC-Coupled with AC inputs)

**Architecture**:
- Solar panels → MPPT DC inputs (4x)
- MPPT → DC bus
- Battery ↔ DC bus ↔ Inverter → AC output
- Grid ↔ AC output
- **Also has**: 2x AC solar inputs (like aGate X)

**Monitoring**:
- **Model 714**: Battery DC power
- **Model 502**: Solar (AC + DC combined?)
- **Model 701**: Grid/AC power

### Off-Grid Capacity Monitoring

The script monitors this critical calculation:

```
AVAILABLE SUPPLY:
  Battery Max Discharge: 5000W (from M702 rating)
  + Solar Generation:    3000W (from Model 502)
  = Total Available:     8000W

REQUIRED:
  Home Load:             7500W

CAPACITY USED: 7500/8000 = 94% ⚠️  HIGH
SAFETY MARGIN: 500W
```

**Warnings**:
- **80-95%**: ⚠️  CAPACITY warning (yellow)
- **>95%**: 🚨 OFF-GRID RISK (red) - System may shutdown!

**Telemetry Display**:
```
BATTERY INVERTER: 45% (2250W / 5000W)
CAPACITY: 94% (7500W / 8000W available)
⚠️  OFF-GRID RISK: Home load 7500W at 94% of supply capacity!
   Available: Battery 5000W + Solar 3000W = 8000W
   ⚠️  System may shutdown if load exceeds supply!
```

### Supported aGate Models

| Model | aPower | Capacity | DC Solar | AC Solar | Peak AC | Continuous |
|-------|--------|----------|----------|----------|---------|------------|
| aGate 12 | aPower | 10.2-40.8 kWh | 30A | - | 12 kW | 10 kW |
| aGate 15 | aPower S | 12.6-50.4 kWh | 35A | 30A | 15 kW | 12 kW |
| aGate 20 | aPower X | 15.3-61.2 kWh | 40A | - | 20 kW | 16 kW |
| aGate 20 | aPower 2 | 18.4-73.6 kWh | 45A | - | 20 kW | 16 kW |

**Note**: The script auto-detects ratings from M702 registers. Models with higher continuous AC ratings (16kW) will show different limits than 5kW base models.

