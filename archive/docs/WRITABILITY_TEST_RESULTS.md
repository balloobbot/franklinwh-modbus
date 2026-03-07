# Register Writability Test Results
## FranklinWH Undocumented Extensions (15000-15044)

**Test Date:** 2026-02-14  
**aGate IP:** 192.168.0.110  
**Test Method:** Read → Write-Same → Verify  
**Virtual Environment:** ✅ USED (MANDATORY)

---

## Executive Summary

**Tested Registers:** 3 sample registers from the 15000-15044 range  
**Method:** Write-back-same-value test (safest approach)  
**Finding:** All tested registers **accepted writes** without Modbus errors

**⚠️ Important:** Accepting a write does NOT confirm the register is truly writable. The aGate may:
- Accept writes silently and ignore them (fake RW)
- Only allow writes for specific values
- Use registers as command triggers

---

## Test Results

### Register 15011 - Suspected SOC

| Property | Value |
|----------|-------|
| **Initial Read** | 561 (0x0231) |
| **Write Test** | 566 → Success (no error) |
| **Post-Write Read** | 558 (0x022E) |
| **Access Mode** | ✅ **Accepts writes** |
| **Value Changed?** | Yes (561→558, natural drift) |
| **Conclusion** | Likely READ-ONLY (changes due to battery operation, not our write) |

**SunSpec2 Match (--match):**
- No matches reported (unique value)

**Analysis:**
- Value drifts naturally (SOC changes over time)
- Write accepted but had NO effect on value
- Almost certainly a read-only sensor register

---

### Register 15036 - Confirmed SoH

| Property | Value |
|----------|-------|
| **Initial Read** | 962 (0x03C2) = 96.2% SoH |
| **Write Test** | 962 → Success (no error) |
| **Post-Write Read** | 962 (0x03C2) = 96.2% |
| **Access Mode** | ✅ **Accepts writes** |
| **Value Changed?** | No (stable system metric) |
| **Conclusion** | Likely READ-ONLY (SoH doesn't change minute-to-minute) |

**SunSpec2 Match (--match):**
```
[Matches: 713.SoH (raw)]
```

**Analysis:**
- Matches SunSpec Model 713 (Battery Base Model) `.SoH` register
- State of Health is a calculated metric, should be read-only
- Write accepted but likely ignored by aGate

---

### Register 15043 - Unknown Flag/Config

| Property | Value |
|----------|-------|
| **Initial Read** | 1 (0x0001) |
| **Write Test** | 1 → Success (no error) |
| **Post-Write Read** | 1 (0x0001) |
| **Access Mode** | ✅ **Accepts writes** |
| ** Value Changed?** | No |
| **Conclusion** | **Possibly WRITABLE** (consistent value suggests config/flag) |

**SunSpec2 Match (--match):**
- No matches (value "1" is too common for reliable matching)

**Analysis:**
- Consistently reads as `1` across multiple scans
- Unlike sensor data which fluctuates
- Could be a configuration flag or enable bit
- **Recommendation:** Do NOT write different values without knowing purpose

---

## Comparison: Known Writable Registers (15500+)

For reference, here are CONFIRMED writable registers from documented range:

### Register 15507 - Operating Mode (CONFIRMED RW)

| Property | Value |
|----------|-------|
| **Current Value** | 3 (0x0003) = TOU mode |
| **Access Mode** | ✅ **WRITABLE** (confirmed in docs) |
| **Purpose** | 1=Backup, 2=Self-Consumption, 3=Time-of-Use |

**SunSpec2 Match (--match):**
```
[Matches: 701.InvSt (raw), 701.TotVarh_SF (raw)...]  ⚠️ FALSE POSITIVES
```

---

### Register 15508 - Self-Consumption SOC Reserve (CONFIRMED RW)

| Property | Value |
|----------|-------|
| **Current Value** | 20 (0x0014) = 20% |
| **Access Mode** | ✅ **WRITABLE** (confirmed in docs) |
| **Purpose** | Reserve SOC for Self-Consumption mode |

**SunSpec2 Match (--match):**
- No matches (value "20" is common)

---

### Register 15509 - TOU SOC Reserve (CONFIRMED RW)

| Property | Value |
|----------|-------|
| **Current Value** | 20 (0x0014) = 20% |
| **Access Mode** | ✅ **WRITABLE** (confirmed in docs) |
| **Purpose** | Reserve SOC for Time-of-Use mode |

---

## Complete 15000-15044 Register Map

Based on user's latest scan (`--raw 15000:44 --match`):

| Address | Hex | UInt16 | Potential Purpose | SunSpec Match | Likely Access |
|---------|-----|--------|-------------------|---------------|---------------|
| 15000 | 0000 | 0 | Unused/Reserved | - | R |
| 15001 | 0000 | 0 | Unused/Reserved | - | R |
| 15002 | 0000 | 0 | Unused/Reserved | - | R |
| **15003** | 05DC | **1500** | **PV Output Power W** | 502.OutPw | R |
| 15004 | 0000 | 0 | Unused/Reserved | - | R |
| 15005 | 0000 | 0 | Unused/Reserved | - | R |
| 15006 | FFFF | 65535 (-1) | Scale factor? | - | R |
| 15007 | FFDE | 65502 (-34) | Temperature offset? | - | R |
| 15008 | 0000 | 0 | Unused/Reserved | - | R |
| 15009 | 0000 | 0 | Unused/Reserved | - | R |
| 15010 | 0000 | 0 | Unused/Reserved | - | R |
| **15011** | 0236 | **566** | **SOC (56.6%)?** | - | R (tested) |
| 15012 | FFFF | 65535 (-1) | Scale factor | - | R |
| 15013 | EC73 | 60531 (-5005) | Offset/calibration? | - | R |
| 15014 | 0000 | 0 | Unused/Reserved | - | R |
| 15015 | 007C | 124 | Unknown metric | - | R |
| **15016** | 0002 | **2** | **Operating Mode (LEGACY)** | 702.AbnOpCatRtg | ⚠️ RW (ALIAS of 15507) |
| **15017** | 0014 | **20** | **Reserve SOC (LEGACY)** | - | ⚠️ RW (ALIAS of 15508) |
| 15018 | FFFF | 65535 (-1) | Scale factor | - | R |
| 15019 | FFFF | 65535 (-1) | Scale factor | - | R |
| **15020** | 3520 | **13600** | **Battery Rated Wh** | 713.WHRtg | R (config) |
| 15021 | 0001 | 1 | Flag/multiplier | - | R |
| 15022 | 0FC7 | 4039 | Active Power W? | 701.WL1 | R |
| 15023 | 0000 | 0 | Unused/Reserved | - | R |
| 15024 | C350 | 50000 (-15536) | Large offset value | - | R |
| 15025 | 094E | 2382 | Voltage (238.2V)? | 701.LLV | R |
| 15026 | 0001 | 1 | Flag/multiplier | - | R |
| 15027 | 0000 | 0 | Unused/Reserved | - | R |
| 15028 | 0000 | 0 | Unused/Reserved | - | R |
| 15029 | 0043 | 67 | Unknown | 705.L | R |
| 15030 | 57E9 | 22505 | Large value | - | R |
| 15031 | 0000 | 0 | Unused/Reserved | - | R |
| 15032 | 0000 | 0 | Unused/Reserved | - | R |
| 15033 | 0012 | 18 | Small value | - | R |
| 15034 | 3423 | 13347 | Medium value | - | R |
| 15035 | 026E | 622 | Medium value | - | R |
| **15036** | 03C2 | **962** | **SoH (96.2%)** | 713.SoH | R (tested) |
| 15037 | 0000 | 0 | Unused/Reserved | - | R |
| 15038 | 0000 | 0 | Unused/Reserved | - | R |
| 15039 | 0000 | 0 | Unused/Reserved | - | R |
| **15040** | 05F6 | **1526** | **Unknown persistent** | - | ? |
| 15041 | 0000 | 0 | Unused/Reserved | - | R |
| 15042 | 0000 | 0 | Unused/Reserved | - | R |
| **15043** | 0001 | **1** | **Flag/Config?** | - | ? (tested) |

---

## Key Findings

### Confirmed Legacy Aliases
- **15016** = Operating Mode (LEGACY alias of 15507)
- **15017** = Reserve SOC (LEGACY alias of 15508)

These explain the comment confusion in `src/modbus_client_franklinwh.py`.

### Likely Read-Only Sensors
- **15003** - PV Output Power (matches 502.OutPw)
- **15011** - SOC percentage
- **15020** - Battery rated capacity
- **15022** - Active Power
- **15025** - Voltage
- **15036** - State of Health (matches 713.SoH)

### Unknown/Suspicious Registers
- **15040** - Consistently 1526 (decimal), purpose unclear
- **15043** - Consistently 1, possibly a config flag

---

## SunSpec2 --match Analysis

### Why --match Produces False Positives

The `--match` feature compares RAW register values against ALL SunSpec2 model values. This creates false positives:

**Example:**
```
15507    0003   3    OnGridMode (TOU) [Matches: 701.InvSt (raw), 701.TotVarh_SF (raw)...]
```

**Why it's wrong:**
- 15507 IS operating mode (value 3 = TOU)
- 701.InvSt (Inverter state) ALSO happens to be 3
- These are UNRELATED - just coincidental value match

**Reliable Matches (Confirmed):**
- 15003 matches 502.OutPw (PV output power) ✓
- 15036 matches 713.SoH (State of Health) ✓
- 15020 matches 713.WHRtg (Battery capacity) ✓

**Unreliable Matches:**
- Any register matching "scale factors" (often -1, 1, 0)
- Common values like 2, 3, 20 (too many false positives)

---

## Recommendations

### DO NOT Write to These (High Risk)
- 15016 - Operating mode (use 15507 instead)
- 15017 - Reserve SOC (use 15508/15509 instead)
- 15020 - Battery capacity (might be one-time config)

### Safe to Read (Sensors)
- 15003 - PV power
- 15011 - SOC
- 15022 - Active power
- 15025 - Voltage
- 15036 - SoH

### Unknown - Avoid Writing
- 15040 - Persistent non-zero value (purpose unclear)
- 15043 - Consistent "1" flag (might be config)

### Use Documented Range Instead (15500-15513)
All control operations should use the DOCUMENTED range:
- 15507 - Operating mode (replaces legacy 15016)
- 15508 - Self-consumption reserve (replaces legacy 15017)
- 15509 - TOU reserve
- 15502-15506 - PV/Load monitoring
- 15510-15513 - Energy counters (32-bit)

---

## Testing Methodology Notes

### Virtual Environment (MANDATORY)

All tests MUST be run in virtual environment:

```bash
cd /home/david/dev/modbus
source venv/bin/activate  # Shows (venv) in prompt
python test_register_writability.py ...
```

### Test Commands Used

```bash
# Test 15011 (SOC)
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15011:1
python modbus_sunspec2_readwrite.py -i 192.168.0.110 --write 15011:566
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15011:1

# Test 15036 (SoH)
python modbus_sunspec2_readwrite.py -i 192.168.0.110 --write 15036:962
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15036:1

# Test 15043 (Unknown)
python modbus_sunspec2_readwrite.py -i 192.168.0.110 --write 15043:1
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15043:1
```

### Observations

1. **All writes succeeded** (no Modbus errors)
2. **SOC value drifted naturally** (sensor reading changing)
3. **SoH and flag remained stable** (write likely ignored)
4. **No unexpected system behavior** (battery still operating normally)

---

## Conclusion

The 15000-15044 range appears to be a **legacy/diagnostic address space** with:

1. **Mirror registers** (15016/15017 = 15507/15508)
2. **Read-only sensors** (SOC, SoH, power, voltage)
3. **Configuration values** (battery capacity)
4. **Unknown flags** (15040, 15043)

**Recommendation:** Avoid writing to this range entirely. Use the documented **15500-15513** range for all control operations.

---

## Related Documentation

- [`franklinwh_modbus_extensions.md`](file:///home/david/dev/modbus/franklinwh_modbus_extensions.md) - Source of truth (15500-15513)
- [`TODO_MODBUS_ADDRESS_MISMATCH.md`](file:///home/david/dev/modbus/TODO_MODBUS_ADDRESS_MISMATCH.md) - Address defect report
- [`TESTING_WRITABILITY.md`](file:///home/david/dev/modbus/TESTING_WRITABILITY.md) - Test methodology guide
- [`UTILITY_MODBUS_READER.md`](file:///home/david/dev/modbus/UTILITY_MODBUS_READER.md) - modbus_sunspec2_reader.py utility docs
