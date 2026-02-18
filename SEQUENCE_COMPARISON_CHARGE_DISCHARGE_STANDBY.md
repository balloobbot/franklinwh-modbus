# Battery Control Sequence Comparison: Charge vs Discharge vs Standby

**Source:** Kimi's `fhp_battery_ctrl.py` atomic write approach  
**Date:** 2026-02-15

---

## 📊 REGISTER BLOCK COMPARISON

All three modes use the **SAME atomic write** of **14 registers** starting at offset 3.

**Only WSet value changes** - everything else is identical!

---

## 🔋 CHARGE Command (-2000W)

### Input
```python
BatteryCommand(
    mode=ControlMode.SET_W,  # 3
    power=-2000  # NEGATIVE for charge
)
```

### Register Block (14 registers)
```
Offset | Register Name    | Value (Hex)      | Value (Decimal) | Notes
-------|------------------|------------------|-----------------|------------------
3      | CtlMode          | 0x0003           | 3               | SET_W mode
4      | WChaMax (high)   | 0x7FFF           | 32767           | Max charge
5      | WChaMax (low)    | 0xFFFF           | 65535           | = 2147483647W
6      | WDisChaMax (high)| 0x7FFF           | 32767           | Max discharge
7      | WDisChaMax (low) | 0xFFFF           | 65535           | = 2147483647W
8      | WSet (high)      | 0xFFFF           | 65535           | -2000W (high word)
9      | WSet (low)       | 0xF830           | 63536           | -2000W (low word)
10     | VarSet (high)    | 0x8000           | 32768           | NOT_IMPL
11     | VarSet (low)     | 0x0000           | 0               | NOT_IMPL
12     | VaSet (high)     | 0x8000           | 32768           | NOT_IMPL
13     | VaSet (low)      | 0x0000           | 0               | NOT_IMPL
14     | CtlTimeout       | 0x003C           | 60              | 60 seconds
15     | WSetRvrtTms      | 0x0000           | 0               | No reversion
16     | VarSetRvrtTms    | 0x0000           | 0               | Not used
17     | VaSetRvrtTms     | 0x0000           | 0               | Not used
```

### WSet Calculation for -2000W
```python
value = -2000
# Convert to unsigned 32-bit (two's complement)
value = value & 0xFFFFFFFF  # = 0xFFFFF830
# Split into high and low words
high = (value >> 16) & 0xFFFF  # = 0xFFFF
low = value & 0xFFFF            # = 0xF830
```

**Result:** `[0xFFFF, 0xF830]` represents -2000W as int32

---

## 🔌 DISCHARGE Command (+500W)

### Input
```python
BatteryCommand(
    mode=ControlMode.SET_W,  # 3
    power=500  # POSITIVE for discharge
)
```

### Register Block (14 registers)
```
Offset | Register Name    | Value (Hex)      | Value (Decimal) | Notes
-------|------------------|------------------|-----------------|------------------
3      | CtlMode          | 0x0003           | 3               | SET_W mode
4      | WChaMax (high)   | 0x7FFF           | 32767           | Max charge
5      | WChaMax (low)    | 0xFFFF           | 65535           | = 2147483647W
6      | WDisChaMax (high)| 0x7FFF           | 32767           | Max discharge
7      | WDisChaMax (low) | 0xFFFF           | 65535           | = 2147483647W
8      | WSet (high)      | 0x0000           | 0               | 500W (high word)
9      | WSet (low)       | 0x01F4           | 500             | 500W (low word)
10     | VarSet (high)    | 0x8000           | 32768           | NOT_IMPL
11     | VarSet (low)     | 0x0000           | 0               | NOT_IMPL
12     | VaSet (high)     | 0x8000           | 32768           | NOT_IMPL
13     | VaSet (low)      | 0x0000           | 0               | NOT_IMPL
14     | CtlTimeout       | 0x003C           | 60              | 60 seconds
15     | WSetRvrtTms      | 0x0000           | 0               | No reversion
16     | VarSetRvrtTms    | 0x0000           | 0               | Not used
17     | VaSetRvrtTms     | 0x0000           | 0               | Not used
```

### WSet Calculation for +500W
```python
value = 500
# Positive value, no conversion needed
high = (value >> 16) & 0xFFFF  # = 0x0000
low = value & 0xFFFF            # = 0x01F4
```

**Result:** `[0x0000, 0x01F4]` represents +500W as int32

---

## ⏸️ STANDBY Command (0W)

### Input
```python
BatteryCommand(
    mode=ControlMode.SET_W,  # 3
    power=0  # ZERO for standby/idle
)
```

### Register Block (14 registers)
```
Offset | Register Name    | Value (Hex)      | Value (Decimal) | Notes
-------|------------------|------------------|-----------------|------------------
3      | CtlMode          | 0x0003           | 3               | SET_W mode
4      | WChaMax (high)   | 0x7FFF           | 32767           | Max charge
5      | WChaMax (low)    | 0xFFFF           | 65535           | = 2147483647W
6      | WDisChaMax (high)| 0x7FFF           | 32767           | Max discharge
7      | WDisChaMax (low) | 0xFFFF           | 65535           | = 2147483647W
8      | WSet (high)      | 0x0000           | 0               | 0W (high word)
9      | WSet (low)       | 0x0000           | 0               | 0W (low word)
10     | VarSet (high)    | 0x8000           | 32768           | NOT_IMPL
11     | VarSet (low)     | 0x0000           | 0               | NOT_IMPL
12     | VaSet (high)     | 0x8000           | 32768           | NOT_IMPL
13     | VaSet (low)      | 0x0000           | 0               | NOT_IMPL
14     | CtlTimeout       | 0x003C           | 60              | 60 seconds
15     | WSetRvrtTms      | 0x0000           | 0               | No reversion
16     | VarSetRvrtTms    | 0x0000           | 0               | Not used
17     | VaSetRvrtTms     | 0x0000           | 0               | Not used
```

### WSet Calculation for 0W
```python
value = 0
high = (value >> 16) & 0xFFFF  # = 0x0000
low = value & 0xFFFF            # = 0x0000
```

**Result:** `[0x0000, 0x0000]` represents 0W as int32

---

## 🔍 SIDE-BY-SIDE COMPARISON

### Only WSet Changes!

| Command | Power  | WSet High | WSet Low | Combined Value | Battery Action |
|---------|--------|-----------|----------|----------------|----------------|
| CHARGE  | -2000W | 0xFFFF    | 0xF830   | -2000 (int32)  | Charging       |
| DISCHARGE | +500W | 0x0000    | 0x01F4   | 500 (int32)    | Discharging    |
| STANDBY | 0W     | 0x0000    | 0x0000   | 0 (int32)      | Idle/Standby   |

### All Other Registers IDENTICAL

**Same for all three:**
- ✅ CtlMode = 3 (SET_W)
- ✅ WChaMax = 2147483647W
- ✅ WDisChaMax = 2147483647W
- ✅ VarSet = NOT_IMPL
- ✅ VaSet = NOT_IMPL
- ✅ CtlTimeout = 60s
- ✅ WSetRvrtTms = 0 (no auto-revert)
- ✅ VarSetRvrtTms = 0
- ✅ VaSetRvrtTms = 0

---

## 💻 PYTHON CODE EXAMPLES

### Charge at 2000W
```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('192.168.0.110', port=502, timeout=10)
client.connect()

# Atomic write of 14 registers starting at offset 3
charge_block = [
    3,                  # CtlMode = SET_W
    0x7FFF, 0xFFFF,    # WChaMax = max
    0x7FFF, 0xFFFF,    # WDisChaMax = max
    0xFFFF, 0xF830,    # WSet = -2000W (CHARGE)
    0x8000, 0x0000,    # VarSet = NOT_IMPL
    0x8000, 0x0000,    # VaSet = NOT_IMPL
    60,                 # CtlTimeout = 60s
    0,                  # WSetRvrtTms = 0
    0,                  # VarSetRvrtTms = 0
    0                   # VaSetRvrtTms = 0
]

result = client.write_registers(3, charge_block, device_id=2)
print(f"Charge command: {result}")
client.close()
```

### Discharge at 500W
```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('192.168.0.110', port=502, timeout=10)
client.connect()

# Only WSet changes - everything else identical
discharge_block = [
    3,                  # CtlMode = SET_W
    0x7FFF, 0xFFFF,    # WChaMax = max
    0x7FFF, 0xFFFF,    # WDisChaMax = max
    0x0000, 0x01F4,    # WSet = 500W (DISCHARGE)
    0x8000, 0x0000,    # VarSet = NOT_IMPL
    0x8000, 0x0000,    # VaSet = NOT_IMPL
    60,                 # CtlTimeout = 60s
    0,                  # WSetRvrtTms = 0
    0,                  # VarSetRvrtTms = 0
    0                   # VaSetRvrtTms = 0
]

result = client.write_registers(3, discharge_block, device_id=2)
print(f"Discharge command: {result}")
client.close()
```

### Standby (0W)
```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('192.168.0.110', port=502, timeout=10)
client.connect()

# Only WSet changes to 0
standby_block = [
    3,                  # CtlMode = SET_W
    0x7FFF, 0xFFFF,    # WChaMax = max
    0x7FFF, 0xFFFF,    # WDisChaMax = max
    0x0000, 0x0000,    # WSet = 0W (STANDBY)
    0x8000, 0x0000,    # VarSet = NOT_IMPL
    0x8000, 0x0000,    # VaSet = NOT_IMPL
    60,                 # CtlTimeout = 60s
    0,                  # WSetRvrtTms = 0
    0,                  # VarSetRvrtTms = 0
    0                   # VaSetRvrtTms = 0
]

result = client.write_registers(3, standby_block, device_id=2)
print(f"Standby command: {result}")
client.close()
```

---

## 📝 BATTERY STATE vs CONTROL MODE

### Battery State (Read-Only)

**Model 704 Offset 2 (State register):**

```python
class BatteryState:
    OFF = 1
    STANDBY = 2
    CHARGING = 3
    DISCHARGING = 4
    FAULT = 5
```

**This is RESULT of the command**, not what we set.

### Control Mode (Write)

**Model 704 Offset 3 (CtlMode register):**

```python
class ControlMode:
    MAX_CHARGE = 1      # Set max charge rate
    MAX_DISCHARGE = 2   # Set max discharge rate
    SET_W = 3           # ✅ Set watt command
    SET_VA = 4          # Set VA (not used)
    SET_VAR = 5         # Set VAR (not used)
```

**We SET CtlMode = 3**, battery RESPONDS with State = 2/3/4

---

## 🎯 SUMMARY

**For Kimi's atomic write approach:**

1. **All three commands (charge/discharge/standby) use IDENTICAL register block structure**
2. **ONLY WSet value differs:**
   - Charge: WSet = negative value
   - Discharge: WSet = positive value
   - Standby: WSet = 0
3. **CtlMode is ALWAYS 3 (SET_W)**
4. **WChaMax/WDisChaMax are ALWAYS set to max**
5. **WSetRvrtTms is ALWAYS 0 (no reversion)**

**The battery decides its State (CHARGING/DISCHARGING/STANDBY) based on the WSet value we command.**
