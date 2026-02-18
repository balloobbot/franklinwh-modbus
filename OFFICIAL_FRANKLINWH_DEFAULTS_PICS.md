# Official FranklinWH Model 704 Defaults (PICS SM-000028)

**Source:** UPDATED_FranklinWH_Modbus_PICS_SM-000028.xlsx  
**Date Extracted:** 2026-02-15  
**Authority:** SunSpec Alliance - FranklinWH aGate Certification

---

## 🎯 KEY FINDING: WSetRvrtTms UNIMPLEMENTED!

**CRITICAL:** According to official PICS document:

```
Row 43: (327, 'WSetRvrtTms', None, 'unimplemented', 'RW', None, None, None)
Row 44: (329, 'WSetRvrtRem', None, 'unimplemented', 'R', None, None, None)
```

**WSetRvrtTms is marked "unimplemented"!**

**This means:**
- ❌ Reversion timer may not work as expected
- ❌ Setting WSetRvrtTms might be ignored by FranklinWH
- ⚠️  Commands might run forever regardless of timer value
- ⚠️  This explains why you got stuck in VPP mode!

---

## 📋 Model 704 Register Support Summary

### WSet Control Registers (THE ONES WE USE)

| Address | Register | Support Status | R/W | Min | Max | Notes |
|---------|----------|----------------|-----|-----|-----|-------|
| 318 | **WSetEna** | ✅ supported | RW | - | - | DISABLED/ENABLED |
| 319 | **WSetMod** | ✅ supported | RW | - | - | W_MAX_PCT/WATTS |
| 320 | **WSet** | ✅ supported | RW | 0 | 10000 | **0-10kW range!** |
| 322 | WSetRvrt | ❌ unimplemented | RW | - | - | Not used |
| 324 | WSetPct | ✅ supported | RW | 0 | 100 | Percentage mode |
| 325 | WSetPctRvrt | ✅ supported | RW | 0 | 100 | Pct reversion |
| 326 | WSetEnaRvrt | ❌ unimplemented | RW | - | - | Not used |
| **327** | **WSetRvrtTms** | **❌ unimplemented** | **RW** | **-** | **-** | **TIMER DOESN'T WORK!** |
| 329 | WSetRvrtRem | ❌ unimplemented | R | - | - | Can't read remaining |

---

## ⚠️  CRITICAL IMPLICATIONS

### What This Means For Our Testing

**WSetRvrtTms = unimplemented:**

1. **Setting timer to 300s might be IGNORED**
   - FranklinWH doesn't implement this feature
   - Timer writes succeed but don't actually work
   - Commands run indefinitely

2. **Getting stuck in VPP mode makes sense**
   - If timer doesn't work, commands never expire
   - Must manually disable with WSetEna=0
   - Explains your 1-day VPP mode experience

3. **Our --wset-rvrt flag might be useless**
   - Kimi's code sets the timer
   - But FranklinWH ignores it
   - False sense of security

---

## 📊 Other Registers of Interest

### Power Factor

| Address | Register | Status |
|---------|----------|--------|
| 298 | PFWInjEna | ✅ supported |
| 299 | PFWInjEnaRvrt | ❌ unimplemented |
| 300 | PFWInjRvrtTms | ❌ unimplemented |

### Power Limiting

| Address | Register | Status | Range |
|---------|----------|--------|-------|
| 310 | WMaxLimPctEna | ✅ supported | - |
| 311 | WMaxLimPct | ✅ supported | 0-100 |
| 312-316 | Reversion registers | ❌ unimplemented | - |

### Reactive Power

| Address | Register | Status |
|---------|----------|--------|
| 331 | VarSetEna | ✅ supported |
| 332 | VarSetMod | ✅ supported |
| 334 | VarSet | ✅ supported |
| 341 | VarSetRvrtTms | ❌ unimplemented |

**Pattern:** All reversion timers are unimplemented!

---

## ✅ What IS Supported

**These registers work:**
- ✅ WSetEna (enable/disable)
- ✅ WSetMod (mode selection)
- ✅ WSet (power value, 0-10000W range)
- ✅ WSetPct (percentage mode)
- ✅ WMaxLimPctEna (power limiting)
- ✅ WMaxLimPct (limit percentage)
- ✅ VarSetEna, VarSetMod, VarSet (reactive power)

---

## ❌ What Is NOT Supported

**These are unimplemented:**
- ❌ **WSetRvrtTms** (our safety timer!)
- ❌ WSetRvrt (power reversion value)
- ❌ WSetEnaRvrt (enable reversion)
- ❌ WSetRvrtRem (can't read time remaining)
- ❌ All power factor reversion
- ❌ All power limit reversion
- ❌ All reactive power reversion

**Key insight:** FranklinWH doesn't support auto-reversion at all!

---

## 🎯 Corrected Understanding

### How To Stop Commands

**What we thought:**
```python
# Set command with 5-minute timer
--wset-rvrt 5m  # Timer expires, command stops automatically
```

**Reality:**
```python
# Set command
--wset-rvrt 5m  # Timer is IGNORED by FranklinWH

# Command runs FOREVER until you manually stop it:
--idle  # Must explicitly disable with WSetEna=0
```

---

## 📝 Default Values Summary

**Per PICS document, expected defaults:**

```
WSetEna:      DISABLED (0)
WSetMod:      WATTS (0) or W_MAX_PCT (1) - both supported
WSet:         0W (valid range: 0-10000W)
WSetRvrtTms:  N/A (unimplemented, any value ignored)
VarSetEna:    DISABLED (0)
```

**Current system state matches these defaults!**

---

## 🔧 Revised Test Approach

### Problem With Current Test Script

**Our test uses:**
```bash
--max-charge --wset-rvrt 5m
--idle --wset-rvrt 5m  
-p -2000W --wset-rvrt 5m
```

**But WSetRvrtTms doesn't work!**

### Corrected Approach

**Must manually stop each command:**

```bash
# Step 1: MAX_CHARGE
python3 fhp_battery_ctrl.py ... --max-charge
# Check effect
# Then manually stop:
python3 fhp_battery_ctrl.py ... --idle

# Step 2: STANDBY  
python3 fhp_battery_ctrl.py ... --idle
# Already idle, check effect

# Step 3: CHARGE
python3 fhp_battery_ctrl.py ... -p -2000W
# Let it run, check battery
# Then manually stop:
python3 fhp_battery_ctrl.py ... --idle
```

**No automatic timeout - must manually disable each command!**

---

## 🚨 SAFETY IMPLICATIONS

**Previous understanding (WRONG):**
- Set timer, walk away
- Command auto-expires
- Safe

**Reality (CORRECT):**
- Timer doesn't work
- Command runs forever
- Must manually monitor and stop
- **Very easy to drain/overcharge battery if left running!**

---

## 📚 References

**Document:** UPDATED_FranklinWH_Modbus_PICS_SM-000028.xlsx  
**Sheet:** 704  
**Rows 1-50:** Extracted full Model 704 register support matrix

**Key rows:**
- Row 30-32: WSetEna = supported
- Row 33-35: WSetMod = supported (WATTS mode)
- Row 36: WSet = supported (0-10000W range)
- Row 43: **WSetRvrtTms = UNIMPLEMENTED** ⚠️
- Row 44: WSetRvrtRem = unimplemented

---

## ✅ Action Items

1. **Update test script** - Remove reliance on timer
2. **Add manual stop steps** - Explicitly --idle after each command
3. **Update documentation** - Correct timer behavior everywhere
4. **Warn user** - Timer doesn't work, must manually monitor
5. **Set alarms** - Don't walk away from running commands

**The timer is a FALSE SAFETY NET!**
