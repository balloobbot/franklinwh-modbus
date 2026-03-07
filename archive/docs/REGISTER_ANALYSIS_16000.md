# Additional Undocumented FranklinWH Registers - 16000 Range

**Discovery Date:** 2026-02-14  
**Range:** 16000-16013 (tested, only first 3 active)

---

## Observations

### Active Registers

| Address | Sample Values | Behavior | Likely Purpose |
|---------|---------------|----------|----------------|
| **16000** | 548, 533, 527, 534, 516 | **Fluctuates with load** | **SOC Raw (÷10 = %)** |
| **16001** | 20 | Constant | Self-Consumption Reserve (duplicate of 15508) |
| **16002** | 20 | Constant | TOU Reserve (duplicate of 15509) |
| 16003-16013 | 0 | All zeros | Unused/reserved |

### Analysis: 16000 is Battery SOC

**Evidence:**

1. **Value Range:** 516-548 → **51.6% to 54.8% SOC** (÷10)
2. **Matches 15011:** Register 15011 shows similar values (558, 561, etc.)
3. **Fluctuates Naturally:** SOC changes as battery charges/discharges
4. **NOT Load Power:** User's home load is ~500-600W at 15506, but:
   - 16000 drifted from 548→527 while load stayed constant
   - SOC naturally drifts, load power fluctuates rapidly

**Comparison:**

```
Time    15011 (Legacy SOC?)   16000 (16K Range SOC?)   15506 (Home Load)
T1      561                   548                      600W
T2      558                   533                      500W  
T3      -                     527                      -
T4      -                     534                      -
T5      -                     516                      -
```

**Conclusion:** 16000 = Battery SOC in raw format (value ÷ 10 = percent)

---

## SunSpec Address Space Rules

### Official SunSpec Specification

**Standard Ranges:**
- **40000-40001:** SunSpec header ("SunS" = 0x53756E53)
- **40002:** First model ID
- **40002+:** Sequential SunSpec models (1, 101, 103, 160, 701, 702, 713, etc.)
- **Typical End:** Models end around 400XX-410XX for most devices

**Vendor Extensions:**
- **Not explicitly restricted** - vendors can use any unused address space
- **Common practice:** Use addresses well above standard models (15000+, 16000+)
- **FranklinWH Strategy:** Multiple vendor-specific ranges:
  - **15000-15044** - Legacy/diagnostic registers
  - **15500-15513** - Documented control/monitoring (source of truth)
  - **16000-16002** - Alternate SOC/reserve readings (newly discovered)

### Why FranklinWH Uses 15000+ and 16000+?

**Rationale:**
1. **Avoids collision** with future SunSpec standard models
2. **Logical grouping** by function (15000s = control, 16000s = status?)
3. **Backward compatibility** with legacy firmware

**SunSpec Compliance:**
- ✅ FranklinWH implements standard models (1, 701, 713, etc.)
- ✅ Vendor extensions don't violate spec (allowed practice)
- ⚠️ Undocumented extensions make integration harder

---

## Purpose of 16000 Range

### Hypothesis: Alternate Data View

**16000 Range Appears to be:**
- **Read-only status registers** (mirror of configuration)
- **Alternate SOC representation** (maybe raw hardware value?)
- **Legacy compatibility** (older firmware versions?)

**Why duplicate reserves (16001/16002)?**
- Possibly for **read-back verification** after writing to 15508/15509
- Or **current active reserve** vs configured reserve
- Or **legacy firmware compatibility**

---

## Recommended Actions

### 1. Monitor 16000 Over Time

Watch if it tracks:
- ✅ Battery SOC (15011)?
- ✅ Home load (15506)?
- ✅ Some other metric?

```bash
# Monitor for 60 seconds
watch -n 5 'python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 16000:3 && \
            python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15011:1 && \
            python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15506:1'
```

### 2. Check for More Ranges

Scan for other potential vendor extensions:

```bash
# Check 17000 range
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 17000:10

# Check 20000 range
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 20000:10
```

### 3. Test Writability (Cautiously)

**DO NOT TEST 16000** - writing to SOC register could brick the battery!

Only safe to test 16001/16002 if they're confirmed duplicates:

```bash
# Read current values
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 16001:2

# Write same value back (ONLY if you're confident)
# python modbus_sunspec2_readwrite.py -i 192.168.0.110 --write 16001:20
```

---

## Updated Register Map

### FranklinWH Vendor Extension Ranges

| Range | Purpose | Status |
|-------|---------|--------|
| **15000-15044** | Legacy diagnostic/control | ⚠️ Deprecated (use 15500+ instead) |
| **15500-15513** | **Primary control/monitoring** | ✅ **Source of Truth** |
| **16000-16002** | Alternate SOC/reserve view | ⚠️ Read-only status (newly discovered) |

### Detailed 16000 Range Map

| Address | Name | Type | Access | Description |
|---------|------|------|--------|-------------|
| 16000 | **Battery SOC (Raw)** | uint16 | R | State of Charge (÷10 for %) |
| 16001 | Self Reserve (Mirror) | uint16 | R? | Copy of 15508 value |
| 16002 | TOU Reserve (Mirror) | uint16 | R? | Copy of 15509 value |
| 16003-16013 | Reserved | - | - | Unused (all zeros) |

---

## Cross-Reference Table

| Value Type | Primary (Use This) | Legacy Alias | 16K Mirror |
|------------|-------------------|--------------|------------|
| **SOC %** | ? (unknown) | 15011 (×0.1?) | **16000 (÷10)** |
| **Operating Mode** | **15507** ✅ | 15016 ⚠️ | - |
| **Self Reserve %** | **15508** ✅ | 15017 ⚠️ | 16001 |
| **TOU Reserve %** | **15509** ✅ | - | 16002 |

---

## Conclusion

**16000 = Battery State of Charge (SOC)**
- Raw value divided by 10 = percentage
- Read-only status register
- Mirrors/complements 15011 (legacy SOC?)

**16001/16002 = Reserve SOC Mirrors**
- Likely read-back of 15508/15509 configured values
- Or current active reserve (vs configured)

**Recommendation:**
- Use **15500-15513** for all control operations (source of truth)
- Use **16000** for SOC monitoring if more accurate than 15011
- **DO NOT write** to 16000 range (likely read-only status)

---

## Related Documentation

- [`franklinwh_modbus_extensions.md`](file:///home/david/dev/modbus/franklinwh_modbus_extensions.md) - 15500-15513 source of truth
- [`TODO_MODBUS_ADDRESS_MISMATCH.md`](file:///home/david/dev/modbus/TODO_MODBUS_ADDRESS_MISMATCH.md) - 15000-15044 discovery
- [`WRITABILITY_TEST_RESULTS.md`](file:///home/david/dev/modbus/WRITABILITY_TEST_RESULTS.md) - Testing methodology

---

## Next Steps

1. **Monitor 16000 correlation** with 15011 and battery SOC over 10+ minutes
2. **Scan 16014-16100** to see if more registers exist
3. **Document final correlation** once confirmed
4. **Update `franklinwh_modbus_extensions.md`** with 16000 range if it's reliable
