# Test Result - Battery Accepts But Doesn't Respond

**Date:** 2026-02-15 03:07  
**Test:** Direct pymodbus charge command

---

## What Happened

### ✅ Command Sent Successfully
```
WSet = -2000W (high=65535, low=63536)
```

### ✅ Registers Updated
```
WSetEna: 1 (ENABLED)
WSet: -2000W (command accepted)
```

### ❌ Battery Did NOT Respond
- **Battery State:** UNKNOWN (invalid value)
- **Battery DCW:** 0W (not -2000W)
- **Physical action:** None
- **VPP Mode:** Not activated

---

## Analysis

**Registers accept writes** ✅
**Battery ignores commands** ❌

This confirms the core problem: **Something is blocking the battery from executing commands** even though the registers accept the values.

---

## Possible Causes

1. **Battery State invalid** - Not in a state that accepts commands
2. **Missing unlock sequence** - Needs specific command first
3. **Model 702 limits not set** - WChaRteMax/WDisChaRteMax = None
4. **Hardware protection** - SOC, temperature, or other safety blocks
5. **Permission/mode issue** - Operating mode prevents external control

---

## What We Know Works
- ✅ Modbus communication
- ✅ Register writes succeed
- ✅ Values persist in registers

## What Doesn't Work
- ❌ Battery physical response
- ❌ VPP mode activation
- ❌ State transition to CHARGING

**Next:** Investigate actual State value and what's blocking execution
