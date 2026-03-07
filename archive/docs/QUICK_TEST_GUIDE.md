# Quick Test Guide - MAX_CHARGE Unlock Hypothesis

**Date:** 2026-02-15 02:33

---

## 🎯 Quick Answer: What This Test Does

**We're testing if there's a SECRET UNLOCK SEQUENCE:**

```
1. MAX_CHARGE command    → Unlocks battery control (triggers VPP mode?)
2. STANDBY (0W) command  → Forces grid connection
3. CHARGE command        → NOW works because unlocked!
```

**vs what we tried before (failed):**

```
Just send CHARGE command directly → Failed, no response
```

---

## ⏱️ Quick Answer: Reversion Timer

**Question:** "Does re-enable turn it off immediately?"

**Answer:** NO! The timer controls when it turns off.

```
Send command with --wset-rvrt 5m
  ↓
Command ACTIVE for 5 minutes
  ↓
Timer counts down: 300...299...298...
  ↓
Timer hits 0
  ↓
Command AUTO-DISABLES
  ↓
Battery returns to normal mode
VPP mode turns OFF
You get app control back
```

**Without timer (WSetRvrtTms = 0):**
- Command runs FOREVER ❌
- Stuck in VPP mode ❌
- You hated this! ❌

**With 5m timer:**
- Command auto-expires ✅
- Safe testing ✅
- Can run again ✅

---

## 📋 Step-by-Step (What Each Command Does)

### STEP 1: Baseline
**What:** Read current register values  
**Why:** Know starting state  
**You do:** Check FranklinWH app mode

---

### STEP 2: Send MAX_CHARGE
**Command:** `--max-charge --wset-rvrt 5m`

**What it writes:**
- CtlMode = 1 (MAX_CHARGE mode)
- WChaMax = maximum
- WSetRvrtTms = 300s (5 min timer)

**Theory:** This unlocks control & triggers VPP mode  
**Wait:** 10 seconds  
**You check:** Did VPP mode activate in app?

---

### STEP 3: Check if VPP Activated
**You check FranklinWH app:**
- Run Status shows "VPP Mode"? ← THE KEY!
- Battery charging?
- DCW value?

**If YES:** Unlock hypothesis looking good!  
**If NO:** MAX_CHARGE didn't unlock

---

### STEP 4: Send STANDBY (0W)
**Command:** `--idle --wset-rvrt 5m`

**What it writes:**
- CtlMode = 3 (SET_W mode)
- WSet = 0W (zero power)
- WSetRvrtTms = 300s

**Your theory:** Forces home loads from grid  
**Wait:** 10 seconds  
**You check:** Is grid importing power?

---

### STEP 5: Check Grid Usage
**You check FranklinWH app:**
- Grid importing? ← YOUR THEORY!
- Battery DCW = 0W?
- Home loads from grid?

**If YES:** STANDBY forced grid connection!  
**If NO:** Doesn't force grid

---

### STEP 6: Send CHARGE -2000W
**Command:** `-p -2000W --wset-rvrt 5m`

**What it writes:**
- CtlMode = 3 (SET_W mode)
- WSet = -2000W (charge)
- WSetRvrtTms = 300s

**This is THE TEST!**  
**Wait:** 15 seconds  
**You check:** Is battery actually charging?

---

### STEP 7: Read Final Status
**Command:** `--status`

**Shows:**
- Battery State (CHARGING?)
- Control Mode (SET_W?)
- WSet value (-2000W?)
- Timer remaining

---

### STEP 8: Check Physical Response
**You check FranklinWH app:**

**SUCCESS looks like:**
- ✅ DCW = -2000W (charging!)
- ✅ State = "Charging"
- ✅ VPP Mode still active
- ✅ SOC increasing

**FAILURE looks like:**
- ❌ DCW = 0W (no response)
- ❌ State = "Standby"
- ❌ Nothing changed

---

## 🎯 What We Learn

### If Test SUCCEEDS:
**The secret sequence is:**
1. MAX_CHARGE unlocks control
2. STANDBY forces grid
3. Then other commands work!

**Going forward:**
- Always use this sequence
- Document as required unlock pattern

### If Test FAILS:
**Problem is something else:**
- Not the command sequence
- Maybe Model 702 rate limits?
- Maybe other unknown registers?
- Need different approach

---

## ⏰ Safety: Auto-Timeout

**Every command has 5-minute timer:**

| Time | What's Happening |
|------|------------------|
| 0:00 | Command sent, battery responds |
| 2:30 | Still active, battery following command |
| 5:00 | Timer expires, command auto-STOPS |
| 5:01 | Battery returns to normal, VPP deactivates |

**You regain control after 5 minutes even if we made a mistake!**

---

## Ready to Run?

```bash
cd /home/david/dev/modbus
./test_maxcharge_unlock.sh
```

Script will pause at checkpoints for you to verify app state!
