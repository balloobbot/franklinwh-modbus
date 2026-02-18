# Battery Control CLI Tool - Quick Reference

## Tool: `battery_ctl.py`

**Purpose:** Simple command-line battery control for FranklinWH without UI complexity

### ✅ Features
- Shows CURRENT state before changes
- Shows TARGET value
- Writes battery control registers
- VERIFIES with read-back confirmation
- Clear success/failure indication

---

## Quick Examples

### 1. View Current Status (No Changes)
```bash
python3 battery_ctl.py 192.168.0.110 --status
```

### 2. Charge Battery at 2000W
```bash
# Negative value = charge (import from grid)
python3 battery_ctl.py 192.168.0.110 -2000
```

### 3. Discharge Battery at 3000W  
```bash
# Positive value = discharge (export to loads)
python3 battery_ctl.py 192.168.0.110 3000
```

### 4. Set Idle (Disable Control)
```bash
python3 battery_ctl.py 192.168.0.110 0
```

---

## Output Format

```
🔌 Connecting to 192.168.0.110:502...
✅ Connected!

📊 Reading current state...
📊 CURRENT STATE:
   Enable: DISABLED
   Mode:   Absolute W
   Power:  IDLE

🔋 Setting battery power: -2000W
   Mode: CHARGE at 2000W
   1. Disabling WSetEna...
   2. Setting WSetMod=0 (Absolute W)...
   3. Writing WSet=-2000W...
   4. Enabling WSetEna...
   ✅ Write sequence complete

🔍 VERIFYING...
📊 Reading current state...
✅ NEW STATE:
   Enable: ENABLED
   Mode:   Absolute W
   Power:  CHARGING at 2000W

🎉 SUCCESS! Battery control updated.
```

---

## Power Value Sign Convention

| Value | Effect | Description |
|-------|--------|-------------|
| **-2000** | Charge | Import 2000W from grid to battery |
| **+3000** | Discharge | Export 3000W from battery to loads |
| **0** | Idle | Disable battery control |

---

## Command-Line Options

```
usage: battery_ctl.py [-h] [--status] [-u UNIT] [-p PORT] [-t TIMEOUT] host [power]

positional arguments:
  host                  FranklinWH aGate IP address
  power                 Power in watts (+ discharge, - charge, 0 idle)

options:
  -h, --help            show this help message and exit
  --status              Only show current status, don't change
  -u UNIT, --unit UNIT  Unit ID (default: 2 for aGate)
  -p PORT, --port PORT  Modbus port (default: 502)
  -t TIMEOUT, --timeout TIMEOUT
                        Timeout in seconds (default: 5)
```

---

## Setup Requirements

### ✅ Already Installed
- Python 3 ✅
- pymodbus 3.11.4 ✅
- Network access to FranklinWH ✅

### 🎯 Zero Additional Setup Required
The tool is ready to use immediately!

---

## Technical Details

### Registers Used (0-indexed PDU)
- `317` (WSET_ENA) - Enable/Disable
- `318` (WSET_MOD) - Mode (0=Absolute W)  
- `319-320` (WSET) - Power setpoint (int32)

### Write Sequence (Critical!)
1. **Disable** WSetEna (clears stuck state)
2. **Set Mode** to 0 (Absolute W)
3. **Write Power** value (signed int32)
4. **Enable** WSetEna (activates setpoint)

### Addressing
Uses **correct FranklinWH addresses** (from `WORKING_BATTERY_CONTROL_SEQUENCE.md`):
- NOT s704_ctl.py offsets (which are wrong for FranklinWH)
- Direct register addresses 317-319
- No offset calculations needed

---

## Troubleshooting

### Connection Failed
```bash
# Check IP address
ping 192.168.0.110

# Check firewall/port
telnet 192.168.0.110 502
```

### Verification Failed  
If readback doesn't match target:
1. Check for other control systems (UI, automation)
2. Verify battery is not in safety mode
3. Check Cloud API isn't overriding local control

### Permission Denied
```bash
# Make executable
chmod +x battery_ctl.py
```

---

## Comparison: battery_ctl.py vs s704_ctl.py

| Feature | battery_ctl.py | s704_ctl.py |
|---------|---------------|-------------|
| **Addressing** | ✅ Correct (317-319) | ❌ Wrong offsets (50-52) |
| **FranklinWH** | ✅ Tested | ❌ Not tested |
| **Current/Target Display** | ✅ Yes | ❌ No |
| **Verification** | ✅ Read-back check | ❌ No verification |
| **User-Friendly** | ✅ Clear output | ⚠️ Minimal output |

**Recommendation:** Use `battery_ctl.py` for FranklinWH systems

---

## Safety Notes

⚠️ **Battery Control Safety:**
- Start with small values (e.g., ±500W) to test
- Monitor battery temperature and SOC
- Be aware of grid limitations
- Have a way to restore unlimited control

See `BATTERY_CONTROL_SAFETY_USAGE.md` for comprehensive safety guidelines.

---

## Related Documentation

- `WORKING_BATTERY_CONTROL_SEQUENCE.md` - Complete technical reference
- `MODEL_704_TEST_RESULTS.md` - Test validation
- `FRANKLINWH_NATIVE_ADDRESSING.md` - Addressing explanation
- `BATTERY_CONTROL_SAFETY_USAGE.md` - Safety guidelines
