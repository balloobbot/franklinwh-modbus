# Audit: Hardware Requirements for Testing

> **Audit Date**: 2026-02-21  
> **Device**: FranklinWH aGate + aPower battery

---

## 🔌 Hardware Test Categories

### Category 1: Safe Read-Only Tests
**Risk**: None - cannot modify device state  
**Can Run Without**: Battery activity (just reads registers)

| Test | Registers/Models | Safety |
|------|------------------|--------|
| Connection test | TCP handshake | ✅ Safe |
| Model discovery | SunSpec scan (1, 701-706, 713-715) | ✅ Safe |
| Battery status (M713) | SoC, SoH, capacity | ✅ Safe |
| Grid status (M701) | Power, voltage, frequency | ✅ Safe |
| Solar status (M714) | DC power, energy | ✅ Safe |
| Control status (M704) | WSetEna, WSetPct (read-only) | ✅ Safe |
| Extension read (15500+) | Home load, PV output | ✅ Safe |
| Health check | All of above | ✅ Safe |

---

### Category 2: Write Tests (Destructive)
**Risk**: Modifies battery behavior  
**Requires**: Active monitoring, ready to intervene

| Test | What It Does | Risk Level | Rollback Plan |
|------|--------------|------------|---------------|
| WSetEna=0 (stop) | Release control | 🟢 LOW | N/A (safe state) |
| WSetEna=1, WSetPct=0 | Active standby | 🟡 MEDIUM | --stop command |
| WSetPct=10% (500W charge) | Small charge | 🟡 MEDIUM | --idle or --stop |
| WSetPct=-10% (500W discharge) | Small discharge | 🟡 MEDIUM | --idle or --stop |
| Full power commands | Max charge/discharge | 🔴 HIGH | Immediate --stop |
| Virtual modes | Automated control | 🔴 HIGH | Ctrl+C + --stop |

---

### Category 3: State-Dependent Tests
**Requires**: Specific battery/grid conditions

| Condition | Required For | How to Achieve |
|-----------|--------------|----------------|
| SoC < 20% | Low battery safety tests | Discharge or wait |
| SoC > 80% | High battery tests | Charge or wait |
| Solar > 2kW | Self-consumption validation | Sunny day |
| Solar = 0 | Night-time behavior | Evening/night |
| Grid outage | Backup mode test | Actual outage or test mode |
| High home load | Peak shave test | Run appliances |

---

## 🧪 Test Environment Requirements

### Minimum Setup
```yaml
Hardware:
  - FranklinWH aGate (IP: 192.168.0.110)
  - aPower battery (1+ units)
  - Network access to aGate
  
Software:
  - Python 3.10+
  - pysunspec2
  - pymodbus
  
Safety:
  - UPS on controlling computer (recommended)
  - FranklinWH app for monitoring
  - Ability to physically disconnect if needed
```

### Recommended Monitoring
```yaml
During Tests:
  - This script output (verbose)
  - FranklinWH mobile app (real-time status)
  - Home energy dashboard (if available)
  - Grid import/export meter
```

---

## ⚡ Power Command Test Matrix

### Safe Test Sequence (Recommended)
```bash
# 1. Health check (always start here)
python franklinwh_control_standalone.py -i 192.168.0.110 --healthcheck

# 2. Read current status
python franklinwh_control_standalone.py -i 192.168.0.110 --status

# 3. Reset to known state
python franklinwh_control_standalone.py -i 192.168.0.110 --stop

# 4. Small charge test (500W = 10% of 5kW)
python franklinwh_control_standalone.py -i 192.168.0.110 --power 500 --revert 60

# 5. Monitor for 60 seconds, verify in app

# 6. Return to idle
python franklinwh_control_standalone.py -i 192.168.0.110 --stop

# 7. Small discharge test (500W)
python franklinwh_control_standalone.py -i 192.168.0.110 --power -500 --revert 60

# 8. Monitor, then stop
python franklinwh_control_standalone.py -i 192.168.0.110 --stop
```

---

## 🔄 Virtual Mode Test Requirements

### Mode: manual
**Requirements**: None  
**Test**: `--mode manual --power 1500`  
**Verify**: Battery charges at ~1.5kW

### Mode: emergency_backup
**Requirements**: SoC < target (e.g., 90%)  
**Test**: `--mode emergency_backup --target-soc 90`  
**Verify**: Battery charges until SoC reaches 90%

### Mode: self_consumption
**Requirements**: Solar > home load  
**Test**: `--mode self_consumption` during sunny day  
**Verify**: Excess solar charges battery

### Mode: time_of_use
**Requirements**: Peak period (configurable)  
**Test**: `--mode time_of_use` during peak hours  
**Verify**: Battery discharges during peak

### Mode: grid_zero
**Requirements**: Variable solar/home load  
**Test**: `--mode grid_zero`  
**Verify**: Grid import/export minimized

### Mode: peak_shave
**Requirements**: Home load > threshold  
**Test**: `--mode peak_shave --threshold 2000` with high load  
**Verify**: Battery discharges when load > 2kW

---

## 📊 Test Data Collection

### Required Telemetry (Current Gap)
Per DEFECT-002, we need to capture:

```yaml
Per Tick (every 5 seconds):
  timestamp: ISO8601
  mode: current virtual mode
  battery:
    soc: percentage
    power: watts (positive=charge)
  solar:
    pv_power: watts
  home:
    load: watts (calculated or measured)
  grid:
    power: watts (positive=import)
  command:
    wset_pct: percentage
    target_soc: if applicable
    elapsed_time: seconds since mode start
    remaining_time: seconds until duration end
```

### Log Format (Proposed)
```
2026-02-21T14:30:00Z MODE=self_consumption ELAPSED=00:05:32 REMAINING=01:54:28 BAT_SOC=75% BAT_P=+1500W SOLAR=2800W HOME=1500W GRID=-200W TARGET_SOC=20% CMD_WSETPCT=30%
```

---

## 🚨 Emergency Procedures

### If Battery Doesn't Respond to Stop Command
```bash
# Try force reset
python franklinwh_control_standalone.py -i 192.168.0.110 --reset-on-start --stop

# If still stuck, use raw Modbus
python -c "
from pymodbus.client import ModbusTcpClient
c = ModbusTcpClient('192.168.0.110', port=502)
c.connect()
c.write_register(40318, 0, slave=2)  # WSetEna=0
c.close()
"
```

### If Control Script Hangs
1. Ctrl+C to interrupt
2. `atexit` handler should release control
3. Verify with `--status`
4. If still enabled, run `--stop`

### Last Resort
- Use FranklinWH app to change operating mode
- This will override Modbus control

---

## 📝 Hardware Test Checklist

Before any write test:
- [ ] Health check passes
- [ ] SoC within safe range (10-90%)
- [ ] Grid voltage/frequency normal
- [ ] No active alarms in app
- [ ] UPS powering control computer
- [ ] App open for monitoring
- [ ] Someone present to intervene

After any write test:
- [ ] Return to `--stop` or `--idle`
- [ ] Verify WSetEna=0 with `--status`
- [ ] Check battery returns to normal operation
- [ ] Review logs for errors

---

## 🎯 Automated Hardware Test Requirements

For CI/CD with real hardware (future):

```yaml
Requirements:
  dedicated_agate: true
  isolated_test_battery: true  # Don't use production battery
  scheduled_window: "02:00-04:00"  # Low activity period
  automatic_rollback: true
  monitoring_webhook: url_for_alerts
```

---

*End of Hardware Requirements Audit*
