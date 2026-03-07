# Enum Validation Notes

## State and CtlMode Enum Values

**Source:** Extracted from Kimi's working `fhp_battery_ctrl.py`

### Battery State (Read-Only)
```
1 = OFF
2 = STANDBY  
3 = CHARGING
4 = DISCHARGING
5 = FAULT
```

### Control Mode (CtlMode)
```
1 = MAX_CHARGE
2 = MAX_DISCHARGE
3 = SET_W
4 = SET_VA
5 = SET_VAR
```

---

## Evidence These Are Correct

**User confirmed observation (2026-02-15 02:11):**
```
State:              CHARGING (3)
Control Mode:       SET_W (3)
WSetRvrtTms:        300 s
WSetRvrtRem:        247 s remaining
```

At that time:
- Battery was physically charging ✅
- Timer was counting down ✅
- VPP mode was active ✅

**This proves the enum values work when system is functioning**

---

## Current Problem

**Reading State/CtlMode now returns:**
```
State:    65535 (0xFFFF)
CtlMode:  65535 (0xFFFF)
```

**65535 (0xFFFF) is NOT in the enum!**

### What 0xFFFF Could Mean

1. **"Not Implemented" marker** (common in SunSpec standard)
2. **Wrong address** - reading from uninitialized/wrong location
3. **Battery locked** - refusing to report state
4. **Firmware issue** - register not supported in this version

---

## How To Verify Correct Address

**Earlier mistake example:**

Reading from address 0 returned ASCII:
```
Offset 0: 21365 (0x5375) = 'S' 'u'
Offset 1: 28243 (0x6E53) = 'n' 'S'
This is "SunS" - the SunSpec header!
```

**Correct addresses (verified working earlier):**
```
Model 704 base: PDU 299
State:          PDU 301 (base + 2)
CtlMode:        PDU 302 (base + 3)
WSetEna:        PDU 321 (base + 22)
WSet:           PDU 323-324 (base + 24-25)
```

---

## Action Items

1. **Verify we're reading correct address**
   - Should be PDU 301 (not 0, not 40301)
   
2. **Check if address changed**
   - Re-scan with modbus_sunspec2_reader.py
   - Verify Model 704 still at base 299
   
3. **Compare with working state**
   - What was different at 02:11 when it worked?
   - App operating mode?
   - Other register values?

---

## Reference

**Working read at 02:11 showed:**
- State = 3 (valid)
- CtlMode = 3 (valid)
- Battery responding to commands

**Current read shows:**
- State = 65535 (invalid)
- CtlMode = 65535 (invalid)  
- Battery NOT responding to commands

**Something changed between 02:11 and 03:08**
