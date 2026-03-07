# Hypothesis: MAX_CHARGE Unlock Sequence

**Date:** 2026-02-15 02:26  
**Source:** User speculation based on previous testing

---

## 🤔 User's Hypothesis

> "I will speculate what happened before - due to the large amount of repetitive testing:
> - We set the max charge rate
> - Then we ran the standby option"

**Theory:** Maybe accidentally running `--max-charge` (CtlMode=1) FIRST "unlocked" battery control, then subsequent commands worked?

---

## 📊 Clarification: Standby vs Control Modes

### Battery STATE (Read-Only Result)

The STATE register (offset 2) shows what the battery IS currently doing:
- OFF = 1
- **STANDBY = 2** ← Battery is idle
- CHARGING = 3
- DISCHARGING = 4
- FAULT = 5

### Control MODE (What We Command)

The CtlMode register (offset 3) tells the battery what to DO:
- **MAX_CHARGE = 1** ← Command: charge at max rate
- MAX_DISCHARGE = 2
- **SET_W = 3** ← Command: follow WSet power setpoint
- SET_VA = 4
- SET_VAR = 5

### When You Run "Standby" Command

```bash
python3 fhp_battery_ctrl.py -i IP --idle
```

**What happens:**
1. Sets **CtlMode = 3** (SET_W mode)
2. Sets **WSet = 0W** (zero power)
3. Battery responds by going to **State = 2** (STANDBY)

So "standby" uses **CtlMode = 3**, not CtlMode = 1!

---

## 🎯 The Hypothesis: Did MAX_CHARGE "Unlock" Control?

### Possible Sequence (For Yesterday's Success)

**Step 1:** Ran `--max-charge` first
```bash
python3 fhp_battery_ctrl.py -i IP --franklinwh --max-charge
```
- This sets **CtlMode = 1** (MAX_CHARGE)
- Maybe this "unlocks" or "enables" battery remote control?
- Maybe triggers VPP mode switch?

**Step 2:** Then ran other commands
```bash
python3 fhp_battery_ctrl.py -i IP --franklinwh -p 2000W
```
- Sets **CtlMode = 3** (SET_W)
- Now works because Step 1 unlocked it?

---

## 🔍 Evidence Check

### From Conversation Logs

Searched "Fixing Battery Writes.md" for "max-charge":
- ❌ **No results found**
- No evidence MAX_CHARGE was used

**But:** Doesn't mean it wasn't used - just not in that conversation file.

### From User's Output (2026-02-15 02:11)

```
State:              CHARGING (3)
Control Mode:       SET_W (3)
```

This shows:
- Battery was in CHARGING state
- CtlMode was SET_W (3) at time of reading

**But:** Doesn't tell us what CtlMode was BEFORE that command!

---

## 🧪 How To Test This Hypothesis

### Test Sequence

**Test 1: MAX_CHARGE First (Your Theory)**
```bash
# Step 1: Set MAX_CHARGE mode (unlock?)
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --unit-id 2 --max-charge

# Step 2: Wait 5 seconds
sleep 5

# Step 3: Check if VPP mode activated
# (Check FranklinWH app or read registers)

# Step 4: Now try SET_W command
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --unit-id 2 -p 2000W --wset-rvrt 5m

# Step 5: Check if it works
```

**Test 2: SET_W Directly (Current Failing Approach)**
```bash
# Just send command directly without MAX_CHARGE first
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --unit-id 2 -p 2000W --wset-rvrt 5m
```

**Compare:** Did Test 1 work when Test 2 failed?

---

## 💡 Why This Might Make Sense

### Possible Reasons MAX_CHARGE Could "Unlock" Control

1. **Permission System:** MAX_CHARGE might be a "request permission" command
   - FranklinWH grants permission
   - Switches to VPP mode
   - Then accepts subsequent SET_W commands

2. **Enable Flag:** MAX_CHARGE might set some internal enable flag
   - Like a "remote control active" flag
   - Persists until explicitly disabled

3. **State Machine:** Battery might need to be in MAX_CHARGE mode first
   - Can't jump directly to SET_W mode
   - Must transition through MAX_CHARGE

4. **Model 702 Link:** MAX_CHARGE might write to Model 702
   - Sets WChaRteMax to enable charging
   - Without this, Model 704 commands ignored

---

## ⚠️ Alternative Explanations

### Why Yesterday Might Have Worked

**Not MAX_CHARGE-related:**
1. Different time of day (power availability different)
2. Different SOC level (battery acceptance changes)
3. Different operating mode in FranklinWH app
4. Model 702 rate limits were already set from previous command
5. Some other register was already configured

**The problem:** We don't have complete "before" state from yesterday's success!

---

## 📝 What We Need To Document

### If We Test MAX_CHARGE Theory

**Before test:**
1. Read ALL Model 702 registers
2. Read ALL Model 704 registers
3. Check FranklinWH app state
4. Document timestamp and SOC

**Run MAX_CHARGE command**

**After MAX_CHARGE:**
1. Read ALL Model 702 registers (did CtlMode change?)
2. Read ALL Model 704 registers (anything change?)
3. Check FranklinWH app (VPP mode activate?)
4. Check if WChaRteMax/WDisChaRteMax were set

**Then run SET_W command**

**After SET_W:**
1. Read registers again
2. Check battery response
3. Compare to direct SET_W without MAX_CHARGE first

---

## 🎯 Next Steps

1. **Test the hypothesis** - try MAX_CHARGE first, then SET_W
2. **Document everything** - full register dumps before/after
3. **Compare results** - did it make a difference?

This is testable speculation - good investigative thinking!
