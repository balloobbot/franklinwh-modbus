# Timer History - Did We Use It Before?

**Date:** 2026-02-15 02:38  
**Question:** "Did we have a timer before? Is that new?"

---

## ✅ YES - We Had Timer in battery_ctl.py

### What battery_ctl.py Does

**Line 141-146 in battery_ctl.py:**

```python
print("   2b. Setting WSetRvrtTms=0 (disable auto-revert)...")
# Writes 0 to register 326 (WSetRvrtTms)
```

**OUR TOOL SET TIMER TO 0!**

- WSetRvrtTms = 0
- Register 326 (PDU address)
- **Meaning:** NO auto-reversion, command runs FOREVER

---

## 🆚 Comparison: battery_ctl.py vs fhp_battery_ctrl.py

### battery_ctl.py (Our Sequential Tool)

```bash
python3 battery_ctl.py charge 2000
```

**What it writes:**
- WSetEna = varies (0 then 1)
- WSetMod = 0
- WSet = -2000W
- **WSetRvrtTms = 0** ← NO TIMER!

**Result:**
- Command stays active FOREVER
- No auto-timeout
- Must manually send WSetEna=0 to stop
- **Can get stuck in VPP mode!**

---

### fhp_battery_ctrl.py (Kimi's Tool)

```bash
python3 fhp_battery_ctrl.py -i IP -p -2000W --wset-rvrt 5m
```

**What it writes:**
- CtlMode = 3
- WSet = -2000W
- **WSetRvrtTms = 300** ← 5 MINUTE TIMER!

**Result:**
- Command active for 5 minutes
- Auto-timeout after 300 seconds
- Battery returns to normal automatically
- **Safe from getting stuck!**

---

## 📊 Evidence: What We Actually Used

### battery_ctl.py Test (2026-02-15 earlier today)

**Command used:**
```bash
python3 battery_ctl.py charge 2000 --verbose
```

**What happened:**
✅ Registers wrote successfully  
✅ WSetRvrtTms = 0 (confirmed in logs)  
❌ Battery didn't physically respond  
❌ No VPP mode activation  

**Timer status:** Set to 0 (no reversion)

---

### User's Status Check (2026-02-15 02:11)

**Output showed:**
```
State:              CHARGING (3)
Control Mode:       SET_W (3)
WSetRvrtTms:        300 s     ← 5 MINUTE TIMER!
WSetRvrtRem:        247 s remaining
```

**This means:**
- Kimi's tool was used (not battery_ctl.py)
- Timer WAS set to 300 seconds
- Had 247 seconds remaining when checked
- **Timer is NOT new - it was already being used!**

---

## 🔍 Timeline Reconstruction

### What Actually Happened

**Earlier (unknown time):**
- Someone (you?) ran Kimi's fhp_battery_ctrl.py
- Set WSetRvrtTms = 300s (5 minutes)
- Battery went to CHARGING state
- VPP mode activated

**When you checked (02:11):**
- Timer still running (247s left)
- Battery still in CHARGING state
- Control Mode = SET_W (3)

**~4 minutes later (02:15-ish):**
- Timer expired (hit 0)
- Command auto-disabled
- Battery returned to normal
- VPP mode deactivated

---

## 🎯 Key Findings

### Timer Was ALWAYS Available

**In Model 704 spec:**
- Register 326 (PDU addr) = WSetRvrtTms
- Always existed
- Part of SunSpec 704 standard

### We Just Used It Differently

**battery_ctl.py approach:**
- Set WSetRvrtTms = 0
- "No reversion" mode
- Intentional choice for testing
- Documented in code comments

**fhp_battery_ctrl.py approach:**
- Default WSetRvrtTms = 0
- BUT has `--wset-rvrt` flag to set it
- You used: `--wset-rvrt 5m`
- Set timer to 300 seconds

---

## ❓ When Was Timer Added to battery_ctl.py?

**Looking at battery_ctl.py line 141:**
```python
print("   2b. Setting WSetRvrtTms=0 (disable auto-revert)...")
```

**This was ALWAYS there!**

- It explicitly sets timer to 0
- To disable auto-reversion
- Was intentional design choice
- For persistent control testing

---

## 🆕 What's New in Test Script?

### In test_maxcharge_unlock.sh

**ALL commands use timer:**
```bash
--max-charge --wset-rvrt 5m     # Timer = 300s
--idle --wset-rvrt 5m            # Timer = 300s  
-p -2000W --wset-rvrt 5m         # Timer = 300s
```

**This IS new for our test script!**

**Why:**
- Safety (learned from your bad VPP experience)
- Can test multiple times
- Auto-returns control
- Won't get stuck

---

## 📋 Summary

**Question:** "Did we have a timer before? Is that new?"

**Answer:**

✅ **Timer register existed:** Always (Model 704 standard)  
✅ **battery_ctl.py used it:** YES - set to 0 (no timeout)  
✅ **Kimi's tool supports it:** YES - `--wset-rvrt` flag  
✅ **You used it before:** YES - 300s timer in your CHARGING test  
🆕 **New in test script:** Using timer on EVERY command for safety

**Timer is NOT new - we just chose different values:**
- battery_ctl.py: WSetRvrtTms = 0 (no timeout)
- Test script: WSetRvrtTms = 300 (5 min timeout)
- Your previous test: WSetRvrtTms = 300 (5 min timeout)

**The 5-minute safety timeout is recommended going forward!**
