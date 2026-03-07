# ⚡ CRITICAL: Model 704 Battery Control Write Sequence

## ❌ Common Mistake: Writing Only WSet

**THIS WILL FAIL SILENTLY:**
```python
model.WSet = -2000  # Battery ignores this!
model.write()       # Returns success, but value doesn't persist
```

**After write, WSet reads back as 0** - the aGate rejected it.

---

## ✅ Correct Write Sequence

**Mandatory 3-step sequence for Model 704 DER Storage Control:**

### Register Map (Base: 40000 + offset)
```
Address  Point Name   Description                        Access  Type
40318    WSetEna      Set Active Power Enable            RW      enum16
40319    WSetMod      Set Active Power Mode              RW      enum16  
40320    WSet         Active Power Setpoint (W)          RW      int32
40322    WSetRvrt     Reversion Active Power (W)         RW      int32
```

### Write Orchestration

**STEP 1: Enable the setpoint control**
```python
model.WSetEna = 1  # 0 = disabled, 1 = enabled
```
**Without this, WSet is completely ignored by the aGate!**

**STEP 2: Set the control mode** *(if required)*
```python
model.WSetMod = 1  # Mode: TBD (need to verify valid values)
```

**STEP 3: Set the power setpoint**
```python
model.WSet = -2000  # Negative = discharge, Positive = charge
```

**STEP 4: Write as atomic block**
```python
await asyncio.get_event_loop().run_in_executor(None, model.write)
```

**STEP 5: Verify**
```python
await asyncio.sleep(1.0)
model.read()
assert model.WSet == -2000, "Write verification failed"
```

---

## 🔴 To Disable/Return to Auto

```python
model.WSetEna = 0    # Disable setpoint control
model.WSet = 0       # Clear setpoint
model.write()
```

---

## Implementation Reference

**File:** `src/modbus_client.py`  
**Method:** `write_model704_battery_control()`  
**Line:** ~1360

```python
# Read current state
await asyncio.get_event_loop().run_in_executor(None, model.read)

# CRITICAL: Enable flags FIRST
if hasattr(model, 'WSetEna'):
    model.WSetEna = 1 if power_watts != 0 else 0

if hasattr(model, 'WSetMod'):
    model.WSetMod = 1

# Then set power
model.WSet = power_watts

# Write all together
await asyncio.get_event_loop().run_in_executor(None, model.write)
```

---

## Logging Pattern

**All writes MUST log the complete sequence:**
```
INFO: WSetEna = 1 (enabled)
INFO: WSetMod = 1  
INFO: WSet = -2000
INFO: ✅ Battery power set to -2000W
WARNING: 📡 Operating Mode AFTER: 4 (VPP Mode)
```

---

## Side Effects

**Setting WSet with WSetEna=1 activates VPP Mode:**
- Operating Mode register (15507) changes to **4** (VPP Mode)
- FranklinWH app shows "VPP" mode
- Auto-timeout after 30 minutes (if WSetCtl_WinStop supported)

**To return to normal:**
- Set WSetEna=0 and WSet=0
- Operating Mode returns to previous value (0=Self-Consumption, 3=TOU, etc)
