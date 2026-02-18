# Battery Control Write Approaches - Comparison Summary

## Overview
Comprehensive comparison of all Model 704 battery control write attempts during this session. **All approaches report "success" but registers read back as 0.**

---

## Script Comparison Table

| Script/Approach | Write Method | Infopoint Used? | Register Sequence | Base Address | Result | Verified Write? |
|----------------|--------------|-----------------|-------------------|--------------|--------|----------------|
| **battery_control.py** (Kimi's pysunspec2) | `verified_write()` with infopoint fallback | ✅ YES (fallback) | Atomic 12-register block @ REG_CTRL_MODE (offset 3) | Unknown (uses pysunspec2 discovery) | ❌ Not tested (import errors) | N/A |
| **s704_ctl.py** (Kimi's pymodbus utility) | 4 sequential `write_register()` calls | ❌ NO (direct register) | 1. Disable WSetEna<br>2. Set WSetMod<br>3. Set WSet (int32)<br>4. Enable WSetEna | 40296 (Model 704 base) | ✅ "SUCCESS" but **all regs = 0** | ❌ NO - Registers = 0 |
| **s704_ctl.py** (with base=40318) | Same as above | ❌ NO | Same sequence | 40318 (WSetEna address) | ✅ "idle 0W" but **all regs = 0** | ❌ NO - Registers = 0 |
| **modbus_client.py** (our implementation v1) | SunSpec `model.write()` | ✅ YES (via SunSpec API) | Set model points then `model.write()` | 296 (model_addr from SunSpec) | ❌ FAILED - Model 704 write not supported | N/A |
| **modbus_client.py** (our implementation v2) | Atomic 12-register `write_registers()` | ❌ NO (direct) | Full control block (ControlMode, WChaMax, WDisChaMax, WSet, VarSet, VaSet, Timeout) | 299 (296 + 3) | ✅ "SUCCESS" but **all regs = 0** | ❌ NO - Registers = 0 |
| **Direct pymodbus test** (inline Python) | Single `write_registers()` call | ❌ NO | Same 12-register atomic block | 299 | ⏳ No output (still running) | ❌ NO - Registers = 0 |

---

## Detailed Breakdown

### `battery_control.py` (Kimi's Full Implementation)
**File:** `/home/david/dev/modbus/battery_control.py`

**Write Method:**
```python
def verified_write(self, offset, values, register_name="", description=""):
    # Try direct write first
    try:
        self._write_registers_direct(offset, values)
        write_method = "direct"
    except Exception as direct_error:
        # Fall back to infopoint if available
        if register_name and self._write_via_infopoint(register_name, values):
            used_infopoint = True
            write_method = "infopoint"
```

**Register Block:** 12 registers starting at REG_CTRL_MODE (offset 3)
```python
register_block = [
    command.mode.value,       # ControlMode (3 = SET_W)
    max_high, max_low,        # WChaMax
    max_high, max_low,        # WDisChaMax  
    w_set_high, w_set_low,    # WSet
    var_set_high, var_set_low,# VarSet
    va_set_high, va_set_low,  # VaSet
    ctl_timeout               # Timeout (1800s)
]
```

**Infopoint Usage:** YES - Has `_write_via_infopoint()` fallback method

**Result:** ❌ Not tested (pysunspec2 import issues in venv)

---

### `s704_ctl.py` (Kimi's Utility Script)
**File:** `/home/david/dev/modbus/s704_ctl.py`

**Write Method:** 4 sequential writes (DISABLE → SET MODE → SET VALUE → ENABLE)
```python
def set_power(self, direction, value, unit):
    # 1. DISABLE first
    self.write_reg(REG_W_SET_ENA, ENA_DISABLED)  
    
    # 2. Set mode
    self.write_reg(REG_W_SET_MOD, mode)  # 0=absolute W, 1=%WMax, 2=VA
    
    # 3. Set power (int32 split into 2 registers)
    self.write_s32(REG_W_SET, raw)  # high, low = split value
    
    # 4. ENABLE
    self.write_reg(REG_W_SET_ENA, ena)
```

**Register Offsets (relative to model base):**
- `REG_W_SET_ENA = 50` 
- `REG_W_SET_MOD = 51`
- `REG_W_SET = 52` (int32 = 2 registers)

**Infopoint Usage:** NO - Direct register writes via pymodbus

**Results:**
- **Test 1** (base=40296): Returned "charge 10W" but all registers = 0
- **Test 2** (base=40318): Returned "idle 0W" but all registers = 0

**Problem:** Offset calculation mismatch
```
Script writes to: 40346-40348 (base 40296 + offset 50-52)
Actual registers: 40318-40320 (from modbus_sunspec2_reader)
```

---

### `modbus_client.py` (Our Implementation - Attempt 1)
**File:** `/home/david/dev/modbus/src/modbus_client.py` (earlier version)

**Write Method:** SunSpec API
```python
model.WSetEna = 1 if power_watts != 0 else 0
model.WSetMod = 3  # SET_W mode
model.WSet = power_watts

await asyncio.get_event_loop().run_in_executor(None, model.write)
```

**Infopoint Usage:** YES (via SunSpec2 library internals)

**Result:** ❌ FAILED - SunSpec `model.write()` doesn't work for Model 704

---

### `modbus_client.py` (Our Implementation - Attempt 2)
**File:** `/home/david/dev/modbus/src/modbus_client.py` (current version)

**Write Method:** Direct atomic block write
```python
ctrl_addr = model_704.model_addr + 3  # 296 + 3 = 299

register_block = [
    3,  # ControlMode = SET_W
    0x7FFF, 0xFFFF,  # WChaMax
    0x7FFF, 0xFFFF,  # WDisChaMax
    w_set_high, w_set_low,  # WSet
    0xFFFF, 0xFFFF,  # VarSet
    0xFFFF, 0xFFFF,  # VaSet
    1800  # Timeout
]

result = await asyncio.get_event_loop().run_in_executor(
    None,
    lambda: self._client.write_registers(
        address=ctrl_addr,
        values=register_block,
        device_id=self.unit_id
    )
)
```

**Infopoint Usage:** NO - Direct pymodbus `write_registers()`

**Result:** ✅ Write returns "success" but **verification shows all registers = 0**

---

## Key Discoveries

### ✅ What We Learned
1. **Model 704 Base Address:** 296 (from `model.model_addr`)
2. **Control Register Start:** Address 299 (base + 3)
3. **Actual Register Addresses:**
   - 40318 = WSetEna
   - 40319 = WSetMod  
   - 40320 = WSet (int32, 2 registers)
4. **VPP Mode Indicator:** RUN_STATUS = 9 (not Operating Mode = 4)
5. **Pymodbus API:** Uses `device_id=` parameter (not `slave=` or `unit=`)
6. **Write Sequence:** DISABLE → SET MODE → SET VALUE → ENABLE

### ❌ What Doesn't Work
1. **SunSpec `model.write()`** - Not supported for Model 704
2. **Atomic block writes** - Accepted but values don't persist
3. **Sequential writes** - Accepted but values don't persist  
4. **All base addresses tried** - 40296, 40300, 40318

### 🔍 Persistent Mystery
**Every write approach returns "success" but registers always read back as 0.**

Possible causes:
- Firmware safety limits rejecting writes
- Wrong operating mode required before writes accepted
- Missing prerequisite register configuration
- Hardware doesn't support external battery control
- Infopoint write required (but no access to SunSpec infopoint mechanism)

---

## Register Address Analysis

### Expected vs Actual

| Register | Script Offset | Calculated Address | Actual Address | Delta |
|----------|--------------|-------------------|----------------|-------|
| WSetEna | 50 | 40346 (40296+50) | 40318 | -28 |
| WSetMod | 51 | 40347 (40296+51) | 40319 | -28 |
| WSet | 52 | 40348 (40296+52) | 40320 | -28 |

**Conclusion:** Script offsets are relative to a different base than we're using. The -28 delta suggests:
- Script expects base 40290 (40318 - 28 = 40290)
- OR offsets are from different model section

---

## Recommendations

1. **Investigate firmware state** - Check if writes require specific operating mode
2. **Test with Cloud API** - Verify hardware supports battery control at all
3. **Examine Kimi's infopoint method** - May be required for Model 704
4. **Contact FranklinWH** - Ask if external Model 704 control is supported

## Files Modified This Session

- [src/modbus_client.py](file:///home/david/dev/modbus/src/modbus_client.py#L1320-1500)
- [src/web_server.py](file:///home/david/dev/modbus/src/web_server.py) 
- [templates/dashboard.html](file:///home/david/dev/modbus/templates/dashboard.html)
- [static/js/app.js](file:///home/david/dev/modbus/static/js/app.js)
