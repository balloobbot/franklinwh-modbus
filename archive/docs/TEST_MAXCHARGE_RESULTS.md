# MAX_CHARGE Unlock Test - Real-Time Results

**Date:** 2026-02-15 02:49  
**Test Start Time:** _____

---

## Pre-Test Checklist

- [ ] FranklinWH app open
- [ ] VPP mode currently OFF (baseline)
- [ ] No active commands running
- [ ] Test script started: `./test_maxcharge_unlock.sh`

---

## STEP 1: Baseline Reading

**Time:** _____

**Model 704 Registers:**
- WSetEna: _____
- WSetMod: _____
- WSet: _____W

**FranklinWH App:**
- Operating Mode: _____
- VPP Mode Active: _____ (should be NO)
- Battery DCW: _____W
- SOC: _____%

**✅ Ready to proceed** → Press ENTER in terminal

---

## STEP 2: MAX_CHARGE Command Sent

**Time:** _____

**Command output:**
```
[Paste command output here]
```

**Errors?:** _____

**Waiting 10 seconds...**

---

## STEP 3: Check VPP Activation ⚡ CRITICAL

**Time:** _____ (10s after MAX_CHARGE)

**FranklinWH App - Check NOW:**
- Run Status field: _____ (looking for "VPP Mode")
- Battery State: _____ (OFF/Standby/Charging/Discharging?)
- Battery DCW: _____W
- Operating Mode: _____

**❓ DID VPP MODE ACTIVATE?**
- [ ] YES - VPP Mode appeared! ← HYPOTHESIS CONFIRMED!
- [ ] NO - Still in normal mode ← MAX_CHARGE didn't trigger it

**Press ENTER to continue...**

---

## STEP 4: STANDBY Command Sent

**Time:** _____

**Command output:**
```
[Paste output]
```

**Waiting 10 seconds...**

---

## STEP 5: Check Grid Usage 🔌

**Time:** _____ (10s after STANDBY)

**FranklinWH App - Check NOW:**
- Grid Power: _____W (importing?)
- Battery DCW: _____W (should be ~0W)
- Battery State: _____ (should be Standby)
- Home load being supplied by: _____ (Grid? Battery?)

**❓ ARE HOME LOADS FROM GRID?**
- [ ] YES - Grid importing! ← Your theory confirmed!
- [ ] NO - Battery still supplying ← STANDBY didn't force grid

**Enter y/n in terminal...**

---

## STEP 6: CHARGE Command Sent (-2000W)

**Time:** _____

**Command output:**
```
[Paste output]
```

**Waiting 15 seconds for battery response...**

---

## STEP 7: Status Check

**Time:** _____ (15s after CHARGE)

**Command output (`--status`):**
```
[Paste full status output]
```

**Key values:**
- State: _____
- Control Mode: _____
- WSet: _____W
- WSetRvrtTms: _____s
- WSetRvrtRem: _____s

---

## STEP 8: Physical Battery Response ⚡ THE PROOF

**Time:** _____

**FranklinWH App - FINAL CHECK:**
- Battery DCW: _____W (expecting -2000W if success)
- Battery State: _____ (expecting "Charging")
- VPP Mode: _____ (should still be active)
- Operating Mode: _____
- SOC: _____%
- Grid Power: _____W

**🎯 DID BATTERY PHYSICALLY RESPOND?**
- [ ] YES - DCW = -2000W, battery charging! ✅ SUCCESS!
- [ ] NO - DCW = 0W, no response ❌ Failed

---

## Test Results Summary

**Did MAX_CHARGE unlock control?**
- VPP activated after MAX_CHARGE? _____
- Different from previous tests? _____

**Did STANDBY force grid?**
- Grid import started? _____
- Useful intermediate step? _____

**Did final CHARGE work?**
- Battery responded? _____
- DCW showing -2000W? _____

---

## Conclusion

**WORKING SEQUENCE (if test succeeded):**
1. MAX_CHARGE → _____
2. STANDBY → _____
3. CHARGE → _____

**vs Direct approach (previous failure):**
- Just CHARGE → Failed

**Key finding:**
_____

---

## Next Steps

_____
