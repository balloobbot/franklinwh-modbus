# KIMI's Complete Battery Control Sequence - DOCUMENTED

**Source:** `fhp_battery_ctrl.py` - `SunSpecBatteryController.send_command()` method  
**Lines:** 415-489  
**Date Analyzed:** 2026-02-15

---

## 🎯 KIMI'S APPROACH: ATOMIC WRITE

### Key Difference from battery_ctl.py

**Kimi:** **ATOMIC WRITE** of 14 registers starting at Model 704 Control Mode block (offset 3)  
**battery_ctl.py:** Sequential writes to individual registers (317-319, 326)

---

## 📋 COMPLETE REGISTER BLOCK (14 registers)

### Starting Address: REG_CTRL_MODE (offset 3)

**For FranklinWH (base address 1, zero-indexed PDU):**
- Effective address: `base_address + offset = 1 + 3 = 4`
- PDU address: `4 - 1 = 3` (0-indexed)
- Protocol address: 40004 (for reference only)

### Register Block Contents (Lines 441-452)

```python
register_block = [
    command.mode.value,              # [0] CtlMode (ControlMode enum)
    max_high, max_low,               # [1-2] WChaMax (int32, max charge)
    max_high, max_low,               # [3-4] WDisChaMax (int32, max discharge)
    w_set_high, w_set_low,           # [5-6] WSet (int32, power setpoint)
    var_set_high, var_set_low,       # [7-8] VarSet (int32, VAR setpoint)
    va_set_high, va_set_low,         # [9-10] VaSet (int32, VA setpoint)
    ctl_timeout,                     # [11] CtlTimeout (uint16, timeout seconds)
    rvrt_config.wset_rvrt_tms,       # [12] WSetRvrtTms (uint16, reversion timer)
    rvrt_config.varset_rvrt_tms,     # [13] VarSetRvrtTms (uint16, VAR reversion)
    rvrt_config.vaset_rvrt_tms,      # [14] VaSetRvrtTms (uint16, VA reversion)
]
```

**Total:** 14 registers (15 values including offset)

---

## 🔍 DETAILED BREAKDOWN

### Register [0]: CtlMode (Command Mode)

**Values (Lines 32-37):**
```python
class ControlMode:
    MAX_CHARGE = 1      # Not used for SetW
    MAX_DISCHARGE = 2   # Not used for SetW
    SET_W = 3           # ✅ Used for watt control
    SET_VA = 4          # Not implemented
    SET_VAR = 5         # Not implemented
```

**For battery control:** `CtlMode = 3` (SET_W)

---

### Registers [1-2]: WChaMax (Max Charge Power, int32)

**Value (Line 428):**
```python
max_high, max_low = 0x7FFF, 0xFFFF
```

**Combined:** `0x7FFFFFFF = 2,147,483,647W` (max int32 positive)

**Purpose:** Maximum charging power limit

---

### Registers [3-4]: WDisChaMax (Max Discharge Power, int32)

**Value (Line 428):**
```python
max_high, max_low = 0x7FFF, 0xFFFF
```

**Combined:** `0x7FFFFFFF = 2,147,483,647W` (max int32 positive)

**Purpose:** Maximum discharging power limit

---

### Registers [5-6]: WSet (Power Setpoint, int32)

**Calculation (Lines 426-427, 434-435):**
```python
power = int(command.power)
power_high, power_low = self._split_int32(power)

if command.mode == ControlMode.SET_W:
    w_set_high, w_set_low = power_high, power_low
```

**For other modes:** `0x8000, 0x0000` (NOT_IMPL marker)

**Examples:**
- Charge 2000W: `power = -2000` → `[0xFFFF, 0xF830]` (two's complement)
- Discharge 500W: `power = 500` → `[0x0000, 0x01F4]`
- Idle: `power = 0` → `[0x0000, 0x0000]`

---

### Registers [7-8]: VarSet (VAR Setpoint, int32)

**Default (Lines 430, 432):**
```python
var_set_high, var_set_low = self.NOT_IMPL_HIGH, self.NOT_IMPL_LOW
# = 0x8000, 0x0000
```

**Purpose:** Not implemented for FranklinWH (set to "not implemented" marker)

---

### Registers [9-10]: VaSet (VA Setpoint, int32)

**Default (Lines 431, 432):**
```python
va_set_high, va_set_low = self.NOT_IMPL_HIGH, self.NOT_IMPL_LOW  
# = 0x8000, 0x0000
```

**Purpose:** Not implemented for FranklinWH (set to "not implemented" marker)

---

### Register [11]: CtlTimeout (Command Timeout, uint16)

**Default (Line 418):**
```python
ctl_timeout: int = 60  # 60 seconds
```

**Purpose:** How long command remains active before timeout

---

### Register [12]: WSetRvrtTms (WSet Reversion Timer, uint16)

**Default (Lines 421-422, 47-51):**
```python
if rvrt_config is None:
    rvrt_config = ReversionConfig()

class ReversionConfig:
    wset_rvrt_tms: int = 0  # ✅ DEFAULT IS 0 (NO REVERSION)
```

**Purpose:** Auto-revert timer for WSet  
**0 = No automatic reversion** (command persists)  
**>0 = Reverts after N seconds**

---

### Register [13]: VarSetRvrtTms (VarSet Reversion Timer, uint16)

**Default:** `0` (not used)

---

### Register [14]: VaSetRvrtTms (VaSet Reversion Timer, uint16)

**Default:** `0` (not used)

---

## 📊 EXAMPLE: Charge at 2000W

### Input Command
```python
command = BatteryCommand(
    mode=ControlMode.SET_W,  # 3
    power=-2000  # Negative for charge
)
ctl_timeout = 60
rvrt_config = ReversionConfig()  # wset_rvrt_tms = 0
```

### Resulting Register Block (14 registers)

```python
[
    3,                    # [0] CtlMode = SET_W
    0x7FFF, 0xFFFF,      # [1-2] WChaMax = max
    0x7FFF, 0xFFFF,      # [3-4] WDisChaMax = max
    0xFFFF, 0xF830,      # [5-6] WSet = -2000W
    0x8000, 0x0000,      # [7-8] VarSet = NOT_IMPL
    0x8000, 0x0000,      # [9-10] VaSet = NOT_IMPL
    60,                   # [11] CtlTimeout = 60s
    0,                    # [12] WSetRvrtTms = 0 (no revert)
    0,                    # [13] VarSetRvrtTms = 0
    0                     # [14] VaSetRvrtTms = 0
]
```

### Write Operation (Lines 466-471)

```python
result = self.verified_write(
    offset=self.REG_CTRL_MODE,  # offset 3
    values=register_block,       # 14 registers
    register_name="CtlMode",
    description=f"Control: mode=SET_W, power=-2000"
)
```

**SINGLE ATOMIC WRITE of 14 registers starting at offset 3**

---

## 🔑 KEY DIFFERENCE vs battery_ctl.py

### Kimi's Approach (fhp_battery_ctrl.py)

**Method:** ATOMIC WRITE  
**Registers:** 14 at once (offset 3-16)  
**Includes:**
- CtlMode = 3 (SET_W)
- WChaMax = max
- WDisChaMax = max
- WSet = power value
- VarSet = NOT_IMPL
- VaSet = NOT_IMPL
- CtlTimeout = 60s
- WSetRvrtTms = 0
- VarSetRvrtTms = 0
- VaSetRvrtTms = 0

### battery_ctl.py Approach

**Method:** SEQUENTIAL WRITES  
**Registers:** Individual writes to:
1. WSetEna (317) = 0 (disable first)
2. WSetMod (318) = 0 (Absolute W mode)
3. WSetRvrtTms (326) = 0 (no revert)
4. WSet (319-320) = power value (int32)
5. WSetEna (317) = 1 (enable if power ≠ 0)

---

## ⚠️ CRITICAL OBSERVATIONS

### 1. Kimi Does NOT Touch WSetEna

**Kimi's atomic write:**
- Starts at offset 3 (CtlMode)
- Ends at offset 16
- **Does NOT include WSetEna** (which is at offset 17)

**WSetEna location in Model 704:**
- Offset: 17
- Address: 40318 (protocol)
- PDU: 317 (0-indexed)

**Kimi's write stops BEFORE WSetEna!**

### 2. Uses CtlMode = 3 (SET_W)

**Kimi sets Control Mode = 3** at the beginning of the block

**battery_ctl.py DOES NOT use CtlMode** - it uses WSetMod (offset 18) instead

---

## 🎯 WHAT THIS MEANS

### Kimi's Sequence

1. Write CtlMode = 3 (SET_W)
2. Write WChaMax = max
3. Write WDisChaMax = max
4. Write WSet = power value
5. Write VarSet/VaSet = NOT_IMPL
6. Write timeouts and reversion timers

**Does NOT enable via WSetEna** - relies on CtlMode=3 for activation

### Is This Why It Might Work?

**Hypothesis:** CtlMode = 3 (SET_W) might be the trigger that activates VPP mode, NOT WSetEna!

**Previous understanding:** WSetEna = 1 triggers VPP mode  
**New possibility:** CtlMode = 3 triggers VPP mode

---

## 📝 COMPLETE MODBUS WRITE

### For 2000W Charge Command

**Single write operation:**
```
Address: Offset 3 (effective address depends on base_address)
Count: 14 registers
Values: [3, 0x7FFF, 0xFFFF, 0x7FFF, 0xFFFF, 0xFFFF, 0xF830, 0x8000, 0x0000, 0x8000, 0x0000, 60, 0, 0, 0]
```

**Breakdown:**
- CtlMode = 3
- WChaMax = 2147483647
- WDisChaMax = 2147483647
- WSet = -2000
- VarSet = NOT_IMPL
- VaSet = NOT_IMPL
- CtlTimeout = 60
- WSetRvrtTms = 0
- VarSetRvrtTms = 0
- VaSetRvrtTms = 0

---

## 🚨 CRITICAL FINDING

**KIMI'S APPROACH IS FUNDAMENTALLY DIFFERENT:**

1. ✅ Uses **CtlMode register** (offset 3)
2. ✅ Writes **14 registers atomically**
3. ✅ Sets **WChaMax/WDisChaMax** to max
4. ✅ Sets **WSetRvrtTms = 0** (no reversion)
5. ❌ **DOES NOT touch WSetEna** (offset 17)

**battery_ctl.py approach:**
1. ❌ Does NOT use CtlMode
2. ❌ Writes registers sequentially
3. ❌ Does NOT set WChaMax/WDisChaMax  
4. ✅ Sets WSetRvrtTms = 0
5. ✅ Uses WSetEna to enable/disable

---

## 🎯 NEXT TEST

Try Kimi's atomic write approach with CtlMode = 3 to see if THIS is what triggers VPP mode!
