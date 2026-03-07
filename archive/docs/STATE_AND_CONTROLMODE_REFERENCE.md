# Model 702/704 State and Control Mode Reference

**Source:** Kimi's `fhp_battery_ctrl.py` (lines 24-37)  
**Date:** 2026-02-15  
**Purpose:** Complete reference for Battery State and Control Mode registers

---

## 📊 Battery State (Read-Only)

**Register:** Model 702/704 offset 2  
**Type:** uint16 (enum)  
**Access:** Read-Only  
**Purpose:** Current battery operational state

### State Values (from Kimi's BatteryState enum)

```python
class BatteryState(IntEnum):
    OFF = 1          # Battery system is off
    STANDBY = 2      # Battery idle, ready but not active
    CHARGING = 3     # Battery actively charging
    DISCHARGING = 4  # Battery actively discharging
    FAULT = 5        # Battery in fault condition
```

### State Mapping Table

| Value | Name | Meaning | Battery Activity |
|-------|------|---------|------------------|
| 1 | OFF | System off | None |
| 2 | STANDBY | Idle/Ready | Minimal (monitoring only) |
| 3 | CHARGING | Charging active | Importing from grid/solar |
| 4 | DISCHARGING | Discharging active | Exporting to loads/grid |
| 5 | FAULT | Fault state | Error condition |

### When You See Each State

**OFF (1):**
- System powered down
- Battery disconnected
- Safety shutdown

**STANDBY (2):**
- Battery ready but idle
- No charge/discharge activity
- Default state when WSetEna = 0
- User confirmed seeing this with VPP Mode active (2026-02-14 screenshot)

**CHARGING (3):**
- Battery accepting power
- Negative WSet command active (-2000W = charging)
- User confirmed: "State: CHARGING (3)" (2026-02-15 02:11)

**DISCHARGING (4):**
- Battery supplying power
- Positive WSet command active (+500W = discharging)
- Exports to home loads or grid

**FAULT (5):**
- Error detected
- Check fault registers for details
- Battery protection activated

### Evidence We Have

✅ **User confirmed CHARGING state** (2026-02-15 02:11)  
✅ **User saw STANDBY state** in screenshot (2026-02-14 20:30)  
❌ No evidence of OFF or FAULT states yet  
❌ No confirmed DISCHARGING test results

---

## 🎛️ Control Mode (Write/Read)

**Register:** Model 702 offset 3 OR Model 704 offset 3 (different models!)  
**Type:** uint16 (enum)  
**Access:** Read/Write  
**Purpose:** Set battery control mode

### Control Mode Values (from Kimi's ControlMode enum)

```python
class ControlMode(IntEnum):
    MAX_CHARGE = 1       # Request maximum charge rate
    MAX_DISCHARGE = 2    # Request maximum discharge rate
    SET_W = 3            # Set specific watt command
    SET_VA = 4           # Set apparent power (not used)
    SET_VAR = 5          # Set reactive power (not used)
```

### Control Mode Mapping Table

| Value | Name | Purpose | FranklinWH Usage |
|-------|------|---------|------------------|
| 1 | MAX_CHARGE | Charge at max safe rate | ❓ Unknown if supported |
| 2 | MAX_DISCHARGE | Discharge at max safe rate | ❓ Unknown if supported |
| 3 | SET_W | Command specific watts | ✅ Used by Kimi's code |
| 4 | SET_VA | Command apparent power | ❌ Not implemented |
| 5 | SET_VAR | Command reactive power | ❌ Not implemented |

### Which Modes Are Used?

**SET_W (3) - PRIMARY MODE:**
- Used by Kimi's `fhp_battery_ctrl.py`
- Sets specific power value (charge or discharge)
- Charge: negative watts (-2000W)
- Discharge: positive watts (+500W)
- Standby: zero watts (0W)
- **User confirmed working:** "Control Mode: SET_W (3)" (2026-02-15 02:11)

**MAX_CHARGE (1) - UNKNOWN:**
- Kimi's code includes `--max-charge` flag
- Should charge at maximum safe rate
- ❌ **No test evidence** if FranklinWH supports this
- ❌ **Not tested** in our sessions

**MAX_DISCHARGE (2) - UNKNOWN:**
- Kimi's code includes `--max-discharge` flag
- Should discharge at maximum safe rate
- ❌ **No test evidence** if FranklinWH supports this
- ❌ **Not tested** in our sessions

**SET_VA (4) - NOT USED:**
- For apparent power control (VA)
- Kimi's code sets to NOT_IMPL (0x8000, 0x0000)
- Not applicable to FranklinWH battery control

**SET_VAR (5) - NOT USED:**
- For reactive power control (VAR)
- Kimi's code sets to NOT_IMPL (0x8000, 0x0000)
- Not applicable to FranklinWH battery control

---

## 🔍 Model 702 vs Model 704

### Important Distinction

**Model 702 (DERCapacity):**
- Contains capacity and rating information
- Has CtlMode at offset 3 (**if this model supports control**)
- May or may not be used for control commands

**Model 704 (DERCtlAC):**
- Contains active control registers
- WSetEna, WSetMod, WSet, etc.
- This is where Kimi's code writes

**Question:** Does Model 702 CtlMode need to be set before Model 704 commands work?

❌ **Unknown** - we have not tested this  
❌ **No documentation** on interaction between models  
❌ **Possible blocker** if Model 702 must be configured first

---

## 📋 What We've Used vs What We Haven't

### Battery State (Read-Only) - Evidence

| State | Observed? | Evidence |
|-------|-----------|----------|
| OFF | ❌ No | Never seen |
| STANDBY | ✅ Yes | User screenshot 2026-02-14 20:30 |
| CHARGING | ✅ Yes | User output 2026-02-15 02:11 |
| DISCHARGING | ❌ No | Not confirmed |
| FAULT | ❌ No | Never seen |

### Control Mode (Write) - Evidence

| Mode | Implemented? | Tested? | Works? |
|------|--------------|---------|---------|
| MAX_CHARGE | ✅ In Kimi's code | ❌ No | ❓ Unknown |
| MAX_DISCHARGE | ✅ In Kimi's code | ❌ No | ❓ Unknown |
| SET_W | ✅ In Kimi's code | ✅ Yes | ✅ YES (user confirmed) |
| SET_VA | ❌ Not used | ❌ No | ❌ N/A |
| SET_VAR | ❌ Not used | ❌ No | ❌ N/A |

---

## 🎯 What Commands Actually Do

### Using SET_W Mode (CtlMode = 3)

**Kimi's atomic write sets:**
1. CtlMode = 3 (SET_W)
2. WSet = power value (negative=charge, positive=discharge, zero=standby)
3. WChaMax = max (2147483647)
4. WDisChaMax = max (2147483647)
5. WSetRvrtTms = timeout in seconds (0 = no revert)

**Battery responds by changing State:**
- WSet = -2000W → State becomes CHARGING (3)
- WSet = +500W → State becomes DISCHARGING (4)
- WSet = 0W → State becomes STANDBY (2)

**User confirmed this working on 2026-02-15 02:11.**

### Using MAX_CHARGE Mode (CtlMode = 1)

**What Kimi's code does:**
```bash
python3 fhp_battery_ctrl.py -i IP --franklinwh --max-charge
```

**Should do:**
- Set CtlMode = 1
- Battery charges at maximum safe rate
- Actual rate determined by battery/system

**In reality:**
- ❌ **Not tested** - no evidence it works
- ❌ **Not confirmed** - FranklinWH might not support this
- ❓ **Unknown** - needs testing

### Using MAX_DISCHARGE Mode (CtlMode = 2)

**What Kimi's code does:**
```bash
python3 fhp_battery_ctrl.py -i IP --franklinwh --max-discharge
```

**Should do:**
- Set CtlMode = 2
- Battery discharges at maximum safe rate
- Actual rate determined by battery/system

**In reality:**
- ❌ **Not tested** - no evidence it works
- ❌ **Not confirmed** - FranklinWH might not support this
- ❓ **Unknown** - needs testing

---

## 🔑 Key Takeaways

### What We KNOW (Evidence-Based)

✅ **SET_W mode (3) works** - user confirmed CHARGING state  
✅ **State register reports correctly** - shows CHARGING/STANDBY  
✅ **WSet commands processed** - battery responds to power setpoint

### What We DON'T KNOW

❌ Do MAX_CHARGE (1) or MAX_DISCHARGE (2) work?  
❌ Does Model 702 CtlMode need to be set?  
❌ Are Model 702 rate limits required?  
❌ What's the interaction between Model 702 and 704?

### What We're NOT Using

❌ SET_VA (4) - not applicable to battery control  
❌ SET_VAR (5) - not applicable to battery control  
❌ Any Model 702 CtlMode writes  
❌ Model 702 rate limit configuration

---

## 📚 Reference Code

### From Kimi's fhp_battery_ctrl.py (lines 24-44)

```python
class BatteryState(IntEnum):
    OFF = 1
    STANDBY = 2
    CHARGING = 3
    DISCHARGING = 4
    FAULT = 5

class ControlMode(IntEnum):
    MAX_CHARGE = 1
    MAX_DISCHARGE = 2
    SET_W = 3
    SET_VA = 4
    SET_VAR = 5

@dataclass
class BatteryCommand:
    mode: ControlMode
    power: float
    is_va: bool = False
```

This is the complete enumeration Kimi implemented and we should reference.
