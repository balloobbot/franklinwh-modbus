# In-Flight Work

**Status:** ✅ COMPLETE — All groups tested  
**Date:** 2026-03-13  
**Commit:** `c2e48e4` (initial doc updates), pending commit (final test results)

---

## SunSpec 6-Phase Re-Test Suite — COMPLETE

### Results Summary

| Group | Register | Result | Previous |
|:-----:|----------|:------:|:--------:|
| A | VarSetEna (331) | ❌ Enable silently discarded | ❌ same |
| B | WMaxLimPctEna (310) | ❌ Enable silently discarded | ❌ same |
| **C** | **WSetRvrtTms (327)** | **✅ WORKS!** 60s accepted | ❌ was "non-functional" |
| **C** | **WSetEnaRvrt (326)** | **✅ WORKS!** Readback=1 | untested |
| **C** | **WSetRvrtRem (329)** | **✅ Countdown active** (59→55→52) | ❌ was "never activates" |
| C | ControllerHb (1092) | ❌ Confirmed non-functional | ❌ same |
| D | WChaRteMax (259) | ❌ 0xFFFF, writes discarded | ❌ same |
| D | WDisChaRteMax (260) | ❌ 0xFFFF, writes discarded | ❌ same |
| D | VAChaRteMax (261) | ❌ 0xFFFF, writes discarded | untested |
| D | VADisChaRteMax (262) | ❌ 0xFFFF, writes discarded | untested |
| D | WMax (251) | ❌ Write=5000, readback=0 | untested |

### Open Investigation

WSetRvrtTms countdown was active (59→55→52), but after the 60s timer expired:
- WSetEna was **still 1** (VPP not auto-disabled)
- WSetPct was **-100** (power not reverted?)

Does the countdown actually revert the power setpoint, or is it cosmetic? This needs a dedicated test:
1. Set WSetRvrtTms=30, WSetEnaRvrt=1, WSetPct=-10 (500W charge)
2. Wait 35 seconds
3. Read WSetPct — did it change to the reversion value?
4. Read WSetEna — did VPP mode auto-disable?

### Reference Documents

- [SUNSPEC_DER_SEQUENCING_REFERENCE.md](./SUNSPEC_DER_SEQUENCING_REFERENCE.md) — 6-phase protocol
- [FRANKLINWH_SUNSPEC_QUIRKS.md](./FRANKLINWH_SUNSPEC_QUIRKS.md) — Updated compliance matrix

---

*Last updated: 2026-03-13 21:41 AEDT*
