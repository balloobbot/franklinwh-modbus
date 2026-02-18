# Timer Reality Check - Does It Actually Work?

**Date:** 2026-02-15 02:47  
**Question:** PICS says "unimplemented" but does timer work anyway?

---

## 📊 Evidence Review

### PICS Document Says:

```
Row 43: (327, 'WSetRvrtTms', None, 'unimplemented', 'RW', None, None, None)
Row 44: (329, 'WSetRvrtRem', None, 'unimplemented', 'R', None, None, None)
```

**Status:** "unimplemented"

---

### User's Actual Observation (2026-02-15 02:11):

```
State:              CHARGING (3)
Control Mode:       SET_W (3)
WSetRvrtTms:        300 s     ← Timer was SET to 5 minutes
WSetRvrtRem:        247 s remaining  ← Timer WAS COUNTING DOWN!
```

**Analysis:**
- Timer set: 300 seconds
- Timer remaining: 247 seconds
- **Elapsed: 53 seconds**
- **WSetRvrtRem was COUNTING DOWN!**

---

## 🤔 What "Unimplemented" Means

### SunSpec PICS Terminology:

**"unimplemented" typically means:**
1. ✅ Register EXISTS at that address
2. ✅ Register CAN be written to
3. ❓ Functionality MAY NOT work as specified
4. ❓ Not officially supported/tested
5. ❓ May work anyway (implementation-specific)

**NOT the same as:**
- ❌ Register doesn't exist
- ❌ Writes fail
- ❌ Can't read value back

---

## 🔍 Three Possible Scenarios

### Scenario 1: Timer Works Despite PICS ✅

**Evidence FOR:**
- WSetRvrtRem was counting down (247s from 300s)
- Timer values can be written and read back
- User saw command expire after time (maybe?)

**If TRUE:**
- Timer is functional
- PICS is conservative/outdated
- FranklinWH implemented but didn't certify
- Safe to use with caution

---

### Scenario 2: Timer Counts But Doesn't Act ⚠️

**Hypothesis:**
- WSetRvrtRem counts down (cosmetic)
- But command doesn't actually disable at 0
- Battery ignores timer expiration
- Runs forever despite countdown

**If TRUE:**
- Countdown is misleading
- Command stays active forever
- Must manually stop
- DANGEROUS if unmonitored

---

### Scenario 3: Partial Implementation 🤷

**Hypothesis:**
- Timer works sometimes
- Depends on other factors (SOC, mode, etc.)
- Unreliable
- Not officially supported

**If TRUE:**
- Can't trust timer
- Must monitor manually
- Unpredictable behavior

---

## 🧪 How To Test Which Scenario Is True

### Simple Timer Test

**Step 1: Set short timer (60s)**
```bash
python3 fhp_battery_ctrl.py -i IP --franklinwh --unit-id 2 -p -500W --wset-rvrt 1m
```

**Step 2: Monitor every 15 seconds**
```bash
# At 0s (immediately)
python3 fhp_battery_ctrl.py -i IP --franklinwh --unit-id 2 --status
# WSetRvrtRem should show ~60s

# At 15s
--status
# WSetRvrtRem should show ~45s

# At 30s
--status
# WSetRvrtRem should show ~30s

# At 45s
--status
# WSetRvrtRem should show ~15s

# At 70s (after expiration)
--status
# Check if WSetEna = 0 (command disabled)
# Check if battery stopped charging
```

**Expected Results:**

**If timer WORKS:**
- WSetRvrtRem counts down: 60→45→30→15→0
- At 60s+: WSetEna automatically becomes 0
- Battery stops responding
- VPP mode deactivates
- ✅ Timer is functional despite PICS

**If timer DOESN'T work:**
- WSetRvrtRem counts down: 60→45→30→15→0
- At 60s+: WSetEna STILL = 1 (enabled)
- Battery KEEPS responding
- VPP mode STAYS active
- ❌ Timer is cosmetic only

---

## 📋 User's Observation Suggests Timer Works

### What We Know:

**From 02:11 status check:**
- Command was active (CHARGING)
- Timer = 300s, Remaining = 247s
- 53 seconds had elapsed

**What happened after?**
- User didn't report battery stuck in CHARGING
- Command presumably expired
- Battery returned to normal?

**If timer didn't work:**
- Battery would still be charging now
- User would be stuck in VPP mode again
- Would have reported this problem

**Inference:**
- Timer probably DID work
- Command probably DID expire at 0s
- PICS "unimplemented" is conservative

---

## ⚖️ Balanced Conclusion

### Most Likely Reality:

**Timer DOES work, BUT:**
- ✅ Countdown happens (observed: 300→247s)
- ✅ Command probably expires (inferred: no stuck report)
- ⚠️ Not officially supported (PICS: unimplemented)
- ⚠️ May not be fully SunSpec compliant
- ⚠️ FranklinWH didn't certify it
- ⚠️ Could have edge cases

### Recommendation:

**USE timer but don't RELY on it:**
- ✅ Keep using `--wset-rvrt 5m`
- ✅ Gives fallback safety
- ⚠️ But manually monitor anyway
- ⚠️ Don't walk away assuming it works
- ⚠️ Be ready to send --idle manually

**Best practice:**
```bash
# Set command with 5-minute safety
python3 fhp_battery_ctrl.py ... -p -2000W --wset-rvrt 5m

# Monitor and manually stop when done
# Don't wait for timer - stop when you want
python3 fhp_battery_ctrl.py ... --idle

# Timer is backup safety, not primary control
```

---

## 🎯 Corrected Understanding

### PICS "Unimplemented" Means:

❌ **NOT:** "Doesn't work at all"  
✅ **YES:** "Works but not officially supported/certified"

### Practical Implications:

**For testing:**
- USE timer for safety (probably works)
- But DON'T rely exclusively on it
- Monitor manually
- Be ready to intervene

**For production:**
- Timer is extra safety layer
- Always have manual monitoring
- Don't trust it for critical timing
- Better safe than sorry

---

## ✅ Action Items

1. **Keep timer in test script** - Probably works, adds safety
2. **Add manual monitoring** - Watch battery, don't trust timer alone
3. **Test timer explicitly** - Do 60s test to verify behavior
4. **Update docs** - Timer works but not guaranteed
5. **Use defensively** - Timer = backup, not primary safety

**Bottom line: USE timer, but VERIFY it works through testing, and DON'T rely on it exclusively.**
