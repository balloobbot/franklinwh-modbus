# Complete VPP Mode Documentation - Extracted from Previous Agent's Conversation

**Source:** "Fixing Battery Writes.md" conversation (2026-02-14)  
**Total VPP References:** 79  
**Status:** CRITICAL FINDING - VPP Mode is Automatic Response

---

## 🎯 PRIMARY DISCOVERY (Lines 11830-11850)

### User's Observation (Line 11832)

> "I saw the battery mode change and the 'Run Status' changed to '**VPP Mode**' - which means a remote app issued it a command :)"

### Agent's Response (Line 11838-11842)

**HARDWARE VALIDATION CONFIRMED!**

The aGate physically responded to Model 704 commands:
- **Battery Mode changed** ✅
- **Run Status → "VPP Mode"** ✅ (Virtual Power Plant = remote control active)

This means API commands didn't just write registers - they **actually controlled the battery hardware!**

---

## 🔑 KEY INSIGHT: VPP Mode OVERRIDE (Lines 12067-12080)

### User's Discovery (Line 12069)

> "Looks like this **OVERIDES** the Operating Mode and changes it to remote **VPP Mode = full control**"

### Agent's Confirmation (Lines 12077-12080)

**EXACTLY! Critical discovery!**

When **WSetEna = 1** (control active):
- ✅ **VPP Mode activates** (Virtual Power Plant = remote control)
- ✅ **Full battery control** override
- ✅ Commands take precedence over normal Operating Mode

---

## 📋 Complete Mechanism (Line 12135)

### How It Works

**Model 704 `WSetEna=1` overrides Operating Mode and activates VPP Mode for full remote control.**

**Setting `WSetEna=0` safely returns to user's configured mode** (Self-Consumption, TOU, etc).

---

## ⚠️ CRITICAL WARNING: Exclusive Control (Lines 12336-12352)

### User's Experience (Line 12338)

> "When in VPP mode - the Mobile App **loses control** - so we have to some timer to release it? Let us wait until we get there. I forgot about that - so that **exclusive control** is there. I was in a VPP for 1 day - **hated it!**"

### Why This Matters (Lines 12347-12352)

- ✅ VPP mode = **exclusive control** (app locked out)
- ❌ Stuck in VPP for 1 day = **terrible UX**
- 🎯 Model 704 has built-in timeout features (`WSetRvrtTms`) that automatically disable VPP mode after X seconds
- 🚨 This is **critical for safety** - not optional!

**Solution:** Use WSetRvrtTms to auto-timeout and return control to user's app

---

## 📊 Test Results from 2026-02-14

### Commands Sent (Lines 11910-11979)

**Test 1: Discharge -3000W**
```bash
curl -X POST http://localhost:8080/api/battery/force_power -d '{"power_watts": -3000}'
```
Result: ✅ Registers wrote, WSet = -3000W

**Test 2: Charge +3000W**
```bash
curl -X POST http://localhost:8080/api/battery/force_power -d '{"power_watts": 3000}'
```
Result: ✅ Registers wrote, WSet = 3000W, **VPP Mode activated**

**Test 3: Idle 0W**
```bash
curl -X POST http://localhost:8080/api/battery/force_power -d '{"power_watts": 0}'
```
Result: ✅ Battery to Standby, **VPP Mode still active**

### FranklinWH App Display (Line 11950)

> "FranklinWH App is in **VPP mode** importing from grid 0.6 home loads - **Standby status**"

This confirms:
- VPP Mode visible in app ✅
- Battery in Standby state ✅
- System responding to commands ✅

---

## 🔬 Technical Details

### What Triggers VPP Mode

**Writing to Model 704 registers:**
1. WSetEna = 1 (enable control)
2. WSetMod = 0 (Absolute W mode)
3. WSet = [high, low] (power setpoint as int32)

**FranklinWH System Response:**
1. Detects Model 704 write
2. **Automatically switches to VPP Mode**
3. Takes exclusive control
4. Executes command
5. Locks out FranklinWH app

### What Returns to Normal Mode

**Writing WSetEna = 0:**
- Disables remote control
- **VPP Mode deactivates**
- Returns to user's configured Operating Mode
- Restores FranklinWH app control

### Auto-Timeout (WSetRvrtTms)

**Purpose:** Prevent getting stuck in VPP mode

**Recommended:** 1800 seconds (30 minutes)

**What happens:**
- VPP mode activates when command sent
- Timer counts down
- After timeout: **auto-returns to normal mode**
- User regains app control

---

## 🎯 Complete Sequence

### Successful Battery Control (2026-02-14)

```
1. Initial State: Self-Consumption mode
2. Send Model 704 command (WSetEna=1, WSet=3000W)
3. FranklinWH detects write
4. ✅ VPP Mode AUTO-ACTIVATES
5. Battery executes command
6. App shows "VPP Mode" + command executing
7. Send WSetEna=0 to return control
8. ✅ VPP Mode DEACTIVATES
9. Returns to Self-Consumption mode
10. User regains app control
```

---

## 📝 Summary of Agent's Findings (Line 12027-12042, 12117-12135)

### What Was Proven

✅ **Model 704 WSet registers accept commands** (all values persisted)  
✅ **API endpoint works** (POST `/api/battery/force_power`)  
✅ **aGate recognizes commands** (switched to VPP mode)  
✅ **VPP Mode activates** when WSetEna=1 (remote control)  
✅ **Battery returned to standby** (safe state)  
✅ **Hardware validated** (VPP mode activated, then returned to normal)

### Key Mechanism Discovered

**Model 704 `WSetEna=1` overrides Operating Mode and activates VPP Mode for full remote control.**

- VPP Mode = Virtual Power Plant = **exclusive remote control**
- Locks out FranklinWH mobile app
- Requires WSetRvrtTms timeout for safety
- WSetEna=0 returns control to user

---

## 🚨 WHY TODAY'S TESTS FAIL (2026-02-15)

### Yesterday (SUCCESS)
- Registers wrote ✅
- **VPP Mode AUTO-ACTIVATED** ✅
- Battery responded ✅

### Today (FAIL)
- Registers wrote ✅
- **VPP Mode DID NOT ACTIVATE** ❌
- Battery not responding ❌

### Hypothesis

**Something is blocking the automatic VPP mode switch:**

Possible causes:
1. Different system state preventing mode transition
2. Missing WSetRvrtTms value (system refusing control without timeout?)
3. Model 702 rate limits blocking operation
4. Safety lock preventing VPP mode activation
5. Time-based restriction

**The registers write successfully - the problem is VPP mode not activating automatically.**

---

## 📚 All VPP References from Conversation

**Total:** 79 occurrences

**Critical lines:**
- 11832: User sees VPP Mode activate
- 11840: Run Status → VPP Mode confirmed
- 11950: App shows VPP mode + Standby
- 11996: aGate switched to VPP mode
- 12027: VPP Mode activates with WSetEna=1
- 12069: **USER DISCOVERS: Overrides Operating Mode**
- 12078: VPP = Virtual Power Plant = remote control
- 12103: Full command with VPP override
- 12135: **KEY MECHANISM DOCUMENTED**
- 12338: **USER WARNING: App loses control in VPP**
- 12352: WSetRvrtTms critical for  safety

---

## 🎯 FINAL ANSWER

**Question:** How do we control the battery?

**Answer:** 
1. Write Model 704 registers (WSetEna=1, WSetMod=0, WSet=power)
2. FranklinWH **automatically switches to VPP Mode**
3. Battery executes command
4. Use WSetRvrtTms for auto-timeout (safety)
5. Write WSetEna=0 to return control

**The VPP mode switch isNOT manual - it's FranklinWH's automatic response to Model 704 writes.**

**Current Problem:** VPP mode not auto-activating on 2026-02-15 tests - need to identify what's different from yesterday's successful tests.
