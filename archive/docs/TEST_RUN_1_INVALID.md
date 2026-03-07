# Test Run #1 - INVALID (Script Error)

**Date:** 2026-02-15 02:49-02:51  
**Result:** TEST INVALID - Commands didn't execute

---

## What Happened

**Script bug:** `test_maxcharge_unlock.sh` didn't activate venv properly  
**Error:** "pysunspec2 not installed" on every command  
**Reality:** Commands never actually sent to battery

---

## User Observations (All Baseline - No Changes)

**Step 3 - After "MAX_CHARGE":**
- VPP Mode active? **NO**
- (But command didn't execute)

**Step 5 - After "STANDBY":**
- Grid supplying loads? **NO**  
- (But command didn't execute)

**Step 8 - After "CHARGE":**
- Battery DCW: Probably 0W (unchanged)
- Battery State: Self-Consumption (unchanged)
- VPP Mode: OFF (unchanged)

---

## Conclusion

❌ Test invalid - need to fix script and re-run  
✅ Baseline verified: System in clean state  
⚠️ Need proper venv activation in script

---

## Next: Fix Script

Script needs to use venv python explicitly
