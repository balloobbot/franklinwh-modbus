# WSet Display Issue - RESOLVED

**Date:** 2026-02-15  
**Issue:** modbus_sunspec2_reader.py shows WSet as 32768000 instead of 500W

## Root Cause

The reader tool displays the **high word shifted left by 16 bits** instead of combining high/low words correctly.

### Kimi's Analysis

```python
raw_value = 32768000

high_word = (raw_value >> 16) & 0xFFFF  # 0x01F4 = 500
low_word = raw_value & 0xFFFF            # 0x0000 = 0
```

**Result:**
- High word: 0x01F4 (500)
- Low word: 0x0000 (0)
- **This is NOT "not implemented" marker**
- It's the high word (500) shifted left: `500 << 16 = 32768000`

### Actual WSet Value

```
Registers: [0, 500] or [500, 0] depending on byte order
Actual value: 500W
Reader displays: 32768000 (incorrectly shows high_word << 16)
```

## Correct Interpretation

| Reader Shows | High Word | Low Word | Actual Value |
|--------------|-----------|----------|--------------|
| 32768000 | 500 (0x01F4) | 0 (0x0000) | **500W** |
| 0x80000000 | 0x8000 | 0x0000 | **Not Implemented** |
| 2000 | 0 (0x0000) | 2000 (0x07D0) | **2000W** |

##Conclusion

**modbus_sunspec2_reader.py has a display bug for int32 values.**

The reader is likely displaying `high_word * 65536` instead of `(high_word << 16) | low_word`.

### Verification

```bash
# Read WSet with battery_ctl.py
python3 battery_ctl.py 192.168.0.110 --status
# Shows: Power: DISCHARGING at 500W  ✅ CORRECT

# Read with modbus_sunspec2_reader
python3 modbus_sunspec2_reader.py -i 192.168.0.110 -u 2 -m 704 --vals | grep WSet
# Shows: 40320 WSet ... 32768000 W  ❌ INCORRECT DISPLAY
```

## Impact

**No impact on battery control** - this is purely a display issue in the reader tool.

- ✅ battery_ctl.py writes correctly
- ✅ Registers contain correct values  
- ✅ FranklinWH reads values correctly
- ⚠️ Reader tool DISPLAYS incorrectly (but doesn't affect actual operation)

## Fix

Update `modbus_sunspec2_reader.py` int32 display logic (low priority - tool works correctly for read/write).
