# Battery Control Fix - WSetRvrtTms Issue

**Date:** 2026-02-15  
**Issue:** Battery control commands were reverting after ~30 minutes  
**Root Cause:** WSetRvrtTms register defaulted to 1800 seconds (30 min auto-revert)  
**Solution:** Set WSetRvrtTms=0 to disable automatic reversion

## The Problem

Model 704 has a `WSetRvrtTms` register (offset 15, address 40327/PDU 326) that controls automatic reversion:
- **Non-zero value**: Battery reverts to previous state after timeout
- **Zero value**: Command persists indefinitely (until explicitly changed)
- **FranklinWH default**: 1800 seconds (30 minutes)

This caused battery control commands to appear successful but then revert silently after 30 minutes.

## The Fix

Updated `battery_ctl.py` to include step 2b in the write sequence:

```
1. DISABLE (WSetEna = 0)
2. SET MODE (WSetMod = 0)
2b. DISABLE AUTO-REVERT (WSetRvrtTms = 0)  ← NEW!
3. WRITE POWER (WSet = target)
4. ENABLE (WSetEna = 1)
```

## Updated Sequence (Verbose Output)

```bash
$ python3 battery_ctl.py 192.168.0.110 3000 --verbose

🔋 Setting battery power: 3000W
   1. Disabling WSetEna...
      → WSetEna = 65535 (0xFFFF)
   2. Setting WSetMod=0 (Absolute W)...
      → WSetMod = 0
   2b. Setting WSetRvrtTms=0 (disable auto-revert)...  ← CRITICAL!
      → WSetRvrtTms = 0 seconds
   3. Writing WSet=3000W...
      → WSet = 3000W (raw: [0, 3000])
   4. Enabling WSetEna...
      → WSetEna = 65535 (0xFFFF)
   ✅ Write sequence complete
```

## Register Details

| Modbus Addr | PDU Addr | Name | Type | Purpose |
|-------------|----------|------|------|---------|
| 40318 | 317 | WSetEna | enum16 | Enable/Disable |
| 40319 | 318 | WSetMod | enum16 | Mode (0=W) |
| 40320-40321 | 319-320 | WSet | int32 | Power setpoint |
| 40327-40328 | 326-327 | WSetRvrtTms | uint32 | **Auto-revert time** |

## WSetRvrtTms Behavior

| Value | Behavior |
|-------|----------|
| **0** | No automatic reversion (command persists) ✅ |
| **60** | Revert after 60 seconds |
| **300** | Revert after 5 minutes (temporary peak shaving) |
| **1800** | Revert after 30 minutes (FranklinWH default) ⚠️ |
| **3600** | Revert after 1 hour |

## Why This Matters

Without setting WSetRvrtTms=0:
1. User sets battery to discharge at 3000W
2. Registers confirm success
3. Battery appears to be discharging
4. **30 minutes later**: Silently reverts to previous state
5. User wonders why battery control "stopped working"

With WSetRvrtTms=0:
1. User sets battery to discharge at 3000W
2. Registers confirm success
3. Command **persists indefinitely**
4. Only changes when explicitly commanded

## Related Documentation

- `WORKING_BATTERY_CONTROL_SEQUENCE.md` - Original 4-step sequence
- `MODEL_704_TEST_RESULTS.md` - Test validation
- User's SunSpec documentation screenshots - WSetRvrtTms spec

## Code Changes

File: `battery_ctl.py`
- Added `WSET_RVRT_TMS = 326` constant
- Added step 2b to write [0, 0] to register 326-327 (uint32 = 0)
- Updated verbose output to show WSetRvrtTms value

**This fix ensures persistent battery control!**
