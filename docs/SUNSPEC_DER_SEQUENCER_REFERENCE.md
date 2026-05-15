# SunSpec DER Control — Phased Sequencing Reference

> **Source:** Claude Sonnet 4.6 agent analysis of SunSpec Model 123 (Reactive Power).
> Applicable to ALL SunSpec DER control groups (WSet, VarSet, WMaxLimPct, WChaRteMax, etc.)
> **Date:** 2026-03-13

## Core Principle

Every SunSpec DER control group follows a **6-phase protocol**. The Enable register (`*Ena`) is always written **LAST** — it is the "go" trigger. All configuration must be in place before enabling.

## Phase Sequence

```
Phase 0: PRE-FLIGHT READS       ← mandatory, no writes yet
Phase 1: CONFIGURE MODE         ← how the device interprets the setpoint
Phase 2: SAFETY / REVERSION     ← what happens if comms are lost
Phase 3: WRITE SETPOINT         ← the actual target value
Phase 4: ENABLE (commit)        ← *Ena last — this is the "go" trigger
Phase 5: VERIFY READBACK        ← confirm acceptance
```

## Timing Requirements

| Between | Sleep | Reason |
|---------|-------|--------|
| Phase 0 → 1 | 0ms | Reads only, no settling needed |
| Mode registers | 200ms | Allow mode register to settle |
| Phase 1 → 2 | 100ms | General settling |
| Between reversion writes | 100ms | Avoid Modbus buffer overflow |
| Phase 3 → Phase 4 (Enable) | 200ms | Setpoint must be stable before enable |
| After Enable | 500ms | Device ramp initiation / processing |
| Reversion refresh loop | ≤ (RvrtTms - 10s) | Keep alive |

## Applied to Active Power (WSet) — Our Current Implementation

```
Phase 0: Read WSetPct (current state)
Phase 1: WSetEna=0 (disable first), WSetMod=0 (configure mode)
Phase 3: WSetPct=value (setpoint)
Phase 4: WSetEna=1 (enable — "go" trigger)
Phase 5: Read WSetPct (verify)
```

**Confirmed 2026-05-14:** Phase 2 (reversion safety — WSetRvrtTms) is now FULLY FUNCTIONAL when using Unit ID 1 and direct PDU addressing. Countdown works (verified 60s → 55s).

## Applied to Reactive Power (VarSet) — UNTESTED on FranklinWH

```
Phase 0: Read Var_SF (273), VarMaxInj (257), VarMaxAbs (258), VarSetEna (331)
Phase 1: Write VarSetMod=1 (332), VarSetPri=2 (333), sleep(200ms), VarRmp (347)
Phase 2: Write VarSetRvrt (336-337), sleep(100ms), VarSetRvrtTms (341-342), 
         sleep(100ms), VarSetEnaRvrt=1 (340)
Phase 3: Write VarSet (334-335) or VarSetPct (338)
Phase 4: sleep(200ms), VarSetEna=1 (331), sleep(500ms)
Phase 5: Read VarSetEna (331) — confirm = 1
```

## Applied to Max Power Limit (WMaxLimPct) — UNTESTED with proper sequencing

```
Phase 0: Read WMaxLimPct_SF (350), WMaxLimPct (311), WMaxLimPctEna (310)
Phase 1: (no separate mode register)
Phase 2: Write WMaxLimPctRvrt (312), WMaxLimPctRvrtTms (314-315), 
         WMaxLimPctEnaRvrt=1 (313)
Phase 3: Write WMaxLimPct (311) — e.g. 500 = 50.0% with SF=-1
Phase 4: sleep(200ms), WMaxLimPctEna=1 (310), sleep(500ms)
Phase 5: Read WMaxLimPctEna (310) — confirm = 1
```

## Applied to PCS Charge/Discharge Rates (WChaRteMax) — UNTESTED with proper sequencing

**Unknown:** No explicit `*Ena` register exists for this group in M702 DERCapacity. Possible approaches:
1. May require WSetEna=1 (VPP mode) first as the overarching enable
2. May require WMaxLimPctEna=1 as related enable
3. May require a StorCtl_Mod sequence (CtrlModes bit 13 = StorCtl is supported)
4. May simply be unimplemented on FranklinWH firmware

!!! important
    **Past test results used rapid-fire writes without proper phased sequencing.**
    All "non-functional" conclusions for WSetRvrtTms, ControllerHb, WMaxLimPctEna, 
    and WChaRteMax should be re-verified using proper 6-phase protocol with 
    100-500ms settling times between phases.

## Registers Requiring Re-Verification

| Register | Past Result | Test Method | Re-test Needed? |
|----------|------------|-------------|:---------------:|
| WSetRvrtTms (327) | ✅ Functional | Phased sequence | ✅ VERIFIED (2026-05-14) |
| WSetRvrtRem (329) | ✅ Functional | Read after phased write | ✅ VERIFIED (2026-05-14) |
| ControllerHb | "Silently ignored" | Phased write | ✅ YES (still failing) |
| WMaxLimPctEna (310) | "Read-only" | Rapid write | ✅ YES |
| WMaxLimPct (311) | "Read-only" | Rapid write | ✅ YES |
| WChaRteMax (259) | "Not implemented" (0xFFFF) | Rapid write ×7 | ✅ YES |
| WDisChaRteMax (260) | "Not implemented" (0xFFFF) | Rapid write ×7 | ✅ YES |

## Notes

- **Modbus TCP serial heritage:** Protocol designed for 9600-19200 baud serial. TCP wrapping doesn't make endpoints faster.
- **aGate round-trip:** ~98ms average (FEM metrics). Min inter-command delay should be ≥200ms.
- **SunSpec2 documentation gap:** Spec defines register semantics but NOT orchestration timing, sequencing between enables, or vendor-specific delays.
- **int32/uint32 registers:** Must be written as single 2-register write (big-endian). Split writes may cause race conditions.

---

*Reference for future properly-paced DER control testing.*
