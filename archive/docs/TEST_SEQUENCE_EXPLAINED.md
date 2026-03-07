# Test Sequence Explanation + Reversion Timer Documentation

**Date:** 2026-02-15 02:33

---

## 🕐 How WSetRvrtTms (Reversion Timer) Works

### What It Does

**WSetRvrtTms** = "WSet Reversion Time" = Auto-timeout for battery commands

**Register:** Model 704 offset 31-32 (uint32, seconds)

### Behavior

**When you send a command with reversion timer:**

```bash
python3 fhp_battery_ctrl.py -i IP -p 2000W --wset-rvrt 5m
```

**What happens:**

1. **Command sent:**
   - WSetEna = 1 (enabled)
   - WSet = 2000W
   - WSetRvrtTms = 300 seconds (5 minutes)

2. **Battery executes command:**
   - Starts discharging at 2000W
   - Timer counts down: 300...299...298...

3. **When timer reaches 0:**
   - WSetEna automatically changes to 0 (DISABLED)
   - Battery stops following the command
   - Returns to normal operating mode
   - **VPP mode should deactivate**
   - User regains app control

### Why This Matters

**Your question:** "Does re-enable turn it off immediately?"

**Answer:** No! The timer controls when it turns off:

- **WSetRvrtTms = 0:** Command stays active FOREVER (no auto-turnoff)
- **WSetRvrtTms = 300:** Command stays active 5 minutes, then auto-turnoff
- **WSetRvrtTms = 1800:** Command stays active 30 minutes, then auto-turnoff

**The timer prevents getting stuck in VPP mode!** (Remember you hated being stuck for a day)

### Reversion Process

```
Command Active          Timer Expires         After Reversion
--------------          -------------         ---------------
WSetEna = 1      -->    Timer hits 0   -->   WSetEna = 0
WSet = 2000W            (5 min later)         WSet = 0W (or previous)
VPP Mode ON                                   VPP Mode OFF
Battery follows                               Battery returns to
your command                                  normal mode
```

---

## 📋 Test Sequence Step-by-Step Explanation

### STEP 1: Baseline Reading
**What it does:**
```python
# Reads Model 704 registers 321-335
# WSetEna, WSetMod, WSet, WSetRvrtTms, etc.
```

**Why:**
- Document starting state
- See what's currently set
- Establish baseline for comparison

**You check:** 
- Current WSetEna value (should be 0 = disabled)
- Current WSet value (should be 0W)
- FranklinWH app operating mode
- VPP mode status

---

### STEP 2: MAX_CHARGE Command
**Command:**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --unit-id 2 --max-charge --wset-rvrt 5m
```

**What Kimi's code does:**
1. Connects to aGate
2. Writes atomic block of 14 registers starting at offset 3:
   - **CtlMode = 1** (MAX_CHARGE)
   - WChaMax = max (2147483647)
   - WDisChaMax = max (2147483647)
   - WSet = NOT_IMPL (not used in MAX_CHARGE mode)
   - VarSet = NOT_IMPL
   - VaSet = NOT_IMPL
   - CtlTimeout = 60s
   - **WSetRvrtTms = 300s** (5 minute auto-timeout)

**What should happen:**
- Battery receives MAX_CHARGE request
- Might start charging at maximum safe rate
- **HYPOTHESIS: This might trigger VPP mode switch!**

**Why this command:**
- Test if MAX_CHARGE "unlocks" battery control
- See if it triggers VPP mode before sending other commands

**You check after 10s:**
- Did VPP mode activate in FranklinWH app?
- Is battery charging?
- What's the DCW value?

---

### STEP 3: VPP Activation Check
**What you do:**
- Open FranklinWH app
- Check "Run Status" field
- Look for "VPP Mode" text

**What we're testing:**
- **If VPP Mode = YES:** MAX_CHARGE triggered it! (unlock hypothesis confirmed)
- **If VPP Mode = NO:** MAX_CHARGE didn't trigger it (hypothesis wrong)

**Critical question:** Does the unlock happen here?

---

### STEP 4: STANDBY (0W) Command
**Command:**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --unit-id 2 --idle --wset-rvrt 5m
```

**What Kimi's code does:**
1. Writes atomic block:
   - **CtlMode = 3** (SET_W)
   - WChaMax = max
   - WDisChaMax = max
   - **WSet = 0W** (ZERO - standby/idle)
   - WSetRvrtTms = 300s

**What should happen:**
- Battery commanded to 0W
- Battery goes to STANDBY state
- **YOUR THEORY: Home loads forced to grid!**

**Why this command:**
- Test if 0W command forces grid connection
- Might be necessary intermediate step
- Establishes grid connection before charging?

**You check after 10s:**
- Are home loads being supplied from grid?
- What's grid import power?
- Battery DCW should be ~0W

---

### STEP 5: Grid Usage Check
**What you do:**
- Check FranklinWH app
- Look at grid power indicator
- Is it importing from grid?

**What we're testing:**
- **If grid importing:** STANDBY forced grid usage! (your theory confirmed)
- **If battery still supplying:** STANDBY didn't force grid (theory wrong)

**Why this matters:**
- Might establish connection needed for charging
- Could be prerequisite for battery control

---

### STEP 6: CHARGE Command (After Unlock Sequence)
**Command:**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --unit-id 2 -p -2000W --wset-rvrt 5m
```

**What Kimi's code does:**
1. Writes atomic block:
   - **CtlMode = 3** (SET_W)
   - WChaMax = max
   - WDisChaMax = max
   - **WSet = -2000W** (negative = CHARGE)
   - WSetRvrtTms = 300s

**What should happen:**
- Battery receives charge command
- **If unlock worked:** Battery charges at 2000W
- **If unlock didn't work:** No response (like before)

**Why this command:**
- This is the actual test!
- Did Steps 2-5 unlock/enable battery control?
- Same command that failed before - will it work now?

**You check after 15s:**
- Is battery charging?
- DCW showing -2000W?
- VPP mode still active?

---

### STEP 7: Final Status Read
**What it does:**
```bash
python3 fhp_battery_ctrl.py -i IP --status
```

**Reads and displays:**
- Battery State (CHARGING/DISCHARGING/STANDBY/etc)
- Control Mode (SET_W/MAX_CHARGE/etc)
- WSet value
- WSetRvrtTms value
- WSetRvrtRem (time remaining on timer)

**Why:**
- Confirm registers were written
- See current command status
- Check timer countdown

---

### STEP 8: Physical Response Check
**What you do:**
- Open FranklinWH app
- Document everything you see

**What to check:**
1. **Battery DCW:** Should show -2000W if charging
2. **Battery State:** Should show "Charging"
3. **VPP Mode:** Should still be active
4. **Operating Mode:** What does it say?
5. **SOC:** Current charge level
6. **Grid Power:** Should be importing to charge battery

**THIS IS THE PROOF:**
- If DCW = -2000W → **Test SUCCESS! Unlock worked!**
- If DCW = 0W → Test failed, still blocked

---

## 🎯 Summary: What Each Command Does

| Step | Command | CtlMode | WSet | Purpose |
|------|---------|---------|------|---------|
| 2 | `--max-charge` | 1 | N/A | Try to unlock/trigger VPP |
| 4 | `--idle` | 3 | 0W | Force grid, establish connection |
| 6 | `-p -2000W` | 3 | -2000W | Actual charge command (the test) |

**The Theory:**
- Step 2 unlocks control (VPP mode activates)
- Step 4 establishes grid connection
- Step 6 works because Steps 2-4 prepared the system

**vs Previous Attempts:**
- We jumped straight to Step 6
- No unlock (Step 2)
- No grid forcing (Step 4)
- Failed!

---

## ⏱️ About Reversion Timers

### All Commands Use 5-Minute Timer

**Why `--wset-rvrt 5m` on every command?**

**Safety!** Each command auto-expires after 5 minutes:

1. **MAX_CHARGE runs for 5 min** → auto-stops
2. **STANDBY runs for 5 min** → auto-stops
3. **CHARGE runs for 5 min** → auto-stops

**Without timer (WSetRvrtTms = 0):**
- Commands run FOREVER
- Get stuck in VPP mode
- Lose app control (you hated this!)

**With 5-minute timer:**
- Safe testing
- Auto-returns to normal
- Can always run test again

---

## 🔑 What We're Looking For

### Success Criteria

✅ **MAX_CHARGE triggers VPP mode** (Step 3)  
✅ **STANDBY forces grid usage** (Step 5)  
✅ **CHARGE command makes battery charge** (Step 8)  

### If This Works

**We learned:**
1. MAX_CHARGE is the "unlock" command
2. STANDBY is a necessary intermediate step
3. Correct sequence: MAX_CHARGE → STANDBY → actual command

### If This Fails

**We learned:**
1. MAX_CHARGE doesn't unlock control
2. Problem is elsewhere (Model 702 limits? Other registers?)
3. Need different approach

Either way, we get valuable data!
