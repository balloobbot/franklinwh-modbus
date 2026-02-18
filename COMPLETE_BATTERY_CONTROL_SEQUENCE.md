# Complete FranklinWH Battery Control Sequence

**Date:** 2026-02-15  
**Status:** 🔬 RESEARCH IN PROGRESS  
**Critical Discovery:** Must set **battery target state** before power commands work

---

## 🎯 The Missing Piece: SetInvState (Model 802)

### What Was Missing

Previous attempts wrote Model 704 registers successfully, but battery didn't physically respond because we **didn't set the target battery state first**.

From Kimi's code and SunSpec documentation:
```python
class BatteryState(IntEnum):
    OFF = 1
    STANDBY = 2        # ← Battery goes idle (VPP Mode screenshot)
    CHARGING = 3       # ← Battery actively charging
    DISCHARGING = 4    # ← Battery actively discharging
    FAULT = 5
```

### Model 802: SetInvState Register

**Purpose:** Controls inverter state which affects battery operation

| Value | State | Description |
|-------|-------|-------------|
| 1 | STOPPED | Inverter off, battery inactive |
| 2 | STANDBY | Battery ready but idle (VPP mode) |
| 3 | STARTED | Inverter running, battery can charge/discharge |

**Register Location:** Model 802, offset 49 (SetInvState)

---

## 📋 Complete Battery Control Sequence

**FranklinWH has NO Model 800 series** - all control is via Model 704 atomic write.

### The Actual Working Sequence (FOUND!)

**From successful test** (line 15018-15070 in "Fixing Battery Writes.md"):

```python
from pymodbus.client import ModbusTcpClient
import time

client = ModbusTcpClient('192.168.0.110', port=502, timeout=5)
client.connect()

# CRITICAL: Model 704 Control Mode Register at address 299
ctrl_addr = 299  # This is CtlMode register (offset 3 from Model 704 base 296)

# Helper function to split int32
def split_int32(value):
    if value < 0:
        value = (1 << 32) + value
    high = (value >> 16) & 0xFFFF
    low = value & 0xFFFF
    return high, low

power_watts = -2000  # Negative = charge, Positive = discharge
w_high, w_low = split_int32(power_watts)

# ATOMIC WRITE: All 12 registers at once
register_block = [
    3,              # [0] ControlMode = SET_W (3)  ← KEY!
    0x7FFF, 0xFFFF, # [1-2] WChaMax (max charge power)
    0x7FFF, 0xFFFF, # [3-4] WDisChaMax (max discharge power)
    w_high, w_low,  # [5-6] WSet (target power)
    0xFFFF, 0xFFFF, # [7-8] VarSet (reactive power - not implemented)
    0xFFFF, 0xFFFF, # [9-10] VaSet (apparent power - not implemented)
    1800            # [11] Timeout (seconds)
]

print(f"Writing {len(register_block)} registers to address {ctrl_addr}")

result = client.write_registers(
    address=ctrl_addr,
    values=register_block,
    device_id=2
)

if not result.isError():
    print("✅ WRITE SUCCESS!")
    time.sleep(2)
    
    # Verify
    verify = client.read_holding_registers(address=ctrl_addr, count=12, device_id=2)
    if not verify.isError():
        print(f"ControlMode = {verify.registers[0]} (expected 3)")
        wset = (verify.registers[5] << 16) | verify.registers[6]
        if wset >= 0x80000000:
            wset -= 0x100000000
        print(f"WSet = {wset}W (expected {power_watts})")
else:
    print(f"❌ WRITE FAILED: {result}")

client.close()
```

---

## 🎯 KEY DISCOVERY: ControlMode = 3

**This is the missing piece!** The successful test wrote:
- **ControlMode = 3** (SET_W mode)
- **NOT** the individual WSetMod register (318)
- **Atomic 12-register write** starting at address 299

### ControlMode Values

| Value | Mode | Description |
|-------|------|-------------|
| 1 | MAX_CHARGE | Maximum charging rate |
| 2 | MAX_DISCHARGE | Maximum discharge rate |
| **3** | **SET_W** | **Absolute power setpoint** ← Used for battery control |
| 4 | SET_VA | Apparent power setpoint |
| 5 | SET_VAR | Reactive power setpoint |

---

## 🔍 Discovery Process (2026-02-15)

### What We Know:

1. **Model 704 writes work** - Registers accept values and verify correctly
2. **Battery doesn't respond** - DCW stays 0W despite WSet = 2000W
3. **Successful test existed** - Previous agent got battery into "VPP Mode (Standby)"
4. **Kimi's code shows BatteryState enum** - Must set target state

### What We Need to Find:

- ✅ Model 802 exists on FranklinWH? **[CHECKING NOW]**
- ❓ SetInvState register address
- ❓ Current SetInvState value
- ❓ Does changing SetInvState enable battery control?

---

## 🧪 Test Plan

### Test 1: Check Model 802 Availability

```bash
python3 modbus_sunspec2_reader.py -i 192.168.0.110 -u 2 -m 802 --vals
```

**Expected:** Model 802 register listing  
**If not found:** Check for alternative state control methods

### Test 2: Read Current SetInvState

```python
# Read current inverter state
r = client.read_holding_registers(MODEL_802_BASE + 49, count=1, device_id=2)
current_state = r.registers[0]
print(f"Current SetInvState: {current_state}")
```

### Test 3: Set STANDBY Mode (VPP Mode)

```python
# Set to STANDBY (the successful state from screenshot)
client.write_register(MODEL_802_BASE + 49, 2, device_id=2)
time.sleep(1.0)

# Verify
r = client.read_holding_registers(MODEL_802_BASE + 49, count=1, device_id=2)
print(f"New SetInvState: {r.registers[0]}")
```

### Test 4: After State Change, Test Battery Control

```python
# Now try Model 704 discharge command
# Use the 5-step sequence above
# Monitor Model 714 DCW to see if battery responds
```

---

## 📊 Register Map Summary

### Model 802 (Inverter Control)

| Offset | Register | Type | RW | Values |
|--------|----------|------|-----|--------|
| 49 | SetInvState | uint16 | RW | 1=STOPPED, 2=STANDBY, 3=STARTED |

**Purpose:** Controls inverter operational state which gates battery control

### Model 704 (DER Control)

| PDU Addr | Register | Type | RW | Description |
|----------|----------|------|-----|-------------|
| 317 | WSetEna | uint16 | RW | 0=disabled, 1/65535=enabled |
| 318 | WSetMod | uint16 | RW | 0=Absolute W, 1=%WMax, 2=VA |
| 319-320 | WSet | int32 | RW | Power setpoint (W) |
| 326 | WSetRvrtTms | uint16 | RW | Auto-revert timer (0=disabled) |

**Purpose:** Sets desired power flow after state is configured

### Model 714 (Battery Actual State)

| PDU Addr | Register | Type | RW | Description |
|----------|----------|------|-----|-------------|
| 15422 | DCW | int16 | RO | Actual DC power (W) |

**Purpose:** Read actual battery power to verify commands worked

---

## 🚨 Critical Notes

### Why Previous Attempts Failed:

1. ❌ Set Model 704 registers **without setting target state**
2. ❌ Battery couldn't determine desired operational mode
3. ❌ System ignored power commands (safety mechanism)

### The Correct Order:

1. ✅ Set **target state** (Model 802 SetInvState)
2. ✅ Set **power value** (Model 704 WSet)
3. ✅ Enable **control** (Model 704 WSetEna)
4. ✅ Verify **actual power** (Model 714 DCW)

---

## 📝 Implementation Checklist

- [ ] Find Model 802 base address
- [ ] Read current SetInvState value
- [ ] Test writing SetInvState = 2 (STANDBY)
- [ ] Verify state change accepted
- [ ] Test Model 704 power command after state set
- [ ] Monitor Model 714 DCW for physical response
- [ ] Document successful sequence
- [ ] Update battery_ctl.py with complete sequence
- [ ] Test charge/discharge/idle modes

---

## 🎯 Success Criteria

Battery control is working when:

1. ✅ Model 802 SetInvState writes successfully
2. ✅ Model 704 WSet writes successfully
3. ✅ **Model 714 DCW matches commanded power** ← Critical!
4. ✅ Battery physically charges/discharges as commanded
5. ✅ Commands persist without reversion

---

**Next Step:** Find Model 802 and test SetInvState control

**Status:** Actively researching Model 802 availability...
