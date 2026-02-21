# FranklinWH Control Standalone - CLI Options Reference

> **Version**: 1.1.0  
> **Date**: 2026-02-21  
> **Status**: Pre-library-split (monolithic script)

---

## Quick Start

```bash
# Health check
python franklinwh_control_standalone.py -i 192.168.0.110 --healthcheck

# Manual control with SoC limits
python franklinwh_control_standalone.py -i 192.168.0.110 \
  --reset-on-start --mode manual --power -3000 \
  --min-discharge-soc 20 --max-charge-soc 95

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

Direct power control. Positive = charge battery, Negative = discharge battery.

**Note**: Actual power may be limited by:
- Device ratings (from Model 702)
- SoC limits (--max-charge-soc, --min-discharge-soc)
- Ramping as SoC approaches limits

---

### `--idle`
**Type**: Flag

Set battery to idle (0W). Equivalent to `--power 0`.

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
| `manual` | Direct power control | `--power` |
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
