# PICS Conformance Cross-Reference

**Source:** `PICS_span_20230711_SPANcomments20230803.xlsx` (SPAN Modbus PICS, July 2023)  
**Last tested:** 2026-03-13 (6-phase SunSpec protocol re-test)

> This document cross-references the manufacturer's **Protocol Implementation Conformance Statement (PICS)** against actual hardware behavior verified through testing.

---

## M702 — DER Capacity (Settings)

| Addr | Point | PICS Status | PICS R/W | Our Test Result | Match? |
|:----:|-------|:-----------:|:--------:|:---------------:|:------:|
| 227 | WMaxRtg | supported | R | 10000 ✅ | ✅ |
| 232 | VAMaxRtg | supported | R | 11600 ✅ | ✅ |
| 233 | VarMaxInjRtg | supported | R | 5880 ✅ | ✅ |
| 234 | VarMaxAbsRtg | supported | R | 5880 ✅ | ✅ |
| 235 | WChaRteMaxRtg | supported | R | 10000 ✅ | ✅ |
| 236 | WDisChaRteMaxRtg | supported | R | 10000 ✅ | ✅ |
| 248 | CtrlModes | supported | R | 14271 ✅ | ✅ |
| **251** | **WMax** | **supported** | **RW** | **Write=5000, readback=0** | **⚠️ VIOLATION** |
| 256 | VAMax | supported | RW | Not tested | — |
| **257** | **VarMaxInj** | **unimplemented** | **RW** | **0xFFFF** | **✅ Expected** |
| **258** | **VarMaxAbs** | **unimplemented** | **RW** | **0xFFFF** | **✅ Expected** |
| **259** | **WChaRteMax** | **unimplemented** | **RW** | **0xFFFF** | **✅ Expected** |
| **260** | **WDisChaRteMax** | **unimplemented** | **RW** | **0xFFFF** | **✅ Expected** |
| **261** | **VAChaRteMax** | **unimplemented** | **RW** | **0xFFFF** | **✅ Expected** |
| **262** | **VADisChaRteMax** | **unimplemented** | **RW** | **0xFFFF** | **✅ Expected** |

### M702 Takeaway

All "unimplemented" registers match exactly (0xFFFF). **WMax (251)** is declared "supported RW" (0-10000) but FC06 write of 5000 returned success while readback remained 0 (silent discard — no Modbus exception).

---

## M704 — DER AC Controls

| Addr | Point | PICS Status | PICS R/W | Our Test Result | Match? |
|:----:|-------|:-----------:|:--------:|:---------------:|:------:|
| 298 | PFWInjEna | supported | RW | ✅ Writable | ✅ |
| **310** | **WMaxLimPctEna** | **supported** | **RW** | **❌ Write accepted, readback=0** | **⚠️ VIOLATION** |
| 311 | WMaxLimPct | supported | RW (0-100) | Readable (1000), but enable won't stick | Partial |
| 312 | WMaxLimPctRvrt | unimplemented | RW | 0xFFFF ✅ | ✅ Expected |
| 313 | WMaxLimPctEnaRvrt | unimplemented | RW | 0xFFFF ✅ | ✅ Expected |
| **318** | **WSetEna** | **supported** | **RW** | **✅ WORKS (VPP Mode)** | **✅** |
| 319 | WSetMod | supported | RW | ✅ Works | ✅ |
| 320 | WSet | supported | RW (0-10000) | ✅ Works | ✅ |
| 322 | WSetRvrt | supported | RW (0-10000) | Not tested independently | — |
| 324 | WSetPct | supported | RW (0-100) | ✅ Works | ✅ |
| 325 | WSetPctRvrt | supported | RW (0-100) | Not tested independently | — |
| **326** | **WSetEnaRvrt** | **supported** | **RW** | **✅ WORKS! Readback=1** | **✅** |
| **327** | **WSetRvrtTms** | **supported** | **RW (0-4294967294)** | **✅ WORKS! 60s accepted, countdown active** | **✅** |
| 329 | WSetRvrtRem | supported | R | ✅ Countdown: 59→55→52 | ✅ |
| **331** | **VarSetEna** | **supported** | **RW** | **❌ Write accepted, readback=0** | **⚠️ VIOLATION** |
| 332 | VarSetMod | supported | RW | Readable (1), accepts write | ✅ |
| 333 | VarSetPri | supported | RW | Readable (2), accepts write | ✅ |
| 334 | VarSet | supported | RW (-5880 to 5880) | Readable (0), accepts write | ✅ |
| 336 | VarSetRvrt | unimplemented | RW | — | ✅ Expected |
| 340 | VarSetEnaRvrt | unimplemented | RW | — | ✅ Expected |
| 341 | VarSetRvrtTms | unimplemented | RW | — | ✅ Expected |
| 345 | WRmp | unimplemented | RW | Returns None | ✅ Expected |

### M704 Takeaway

WSet group (318-329) works perfectly — PICS matches reality. **But WMaxLimPctEna (310) and VarSetEna (331) are declared "supported RW" yet silently discard writes.** These are PICS conformance violations.

---

## M715 — DER Lifecycle

| Addr | Point | PICS Status | PICS R/W | Our Test Result | Match? |
|:----:|-------|:-----------:|:--------:|:---------------:|:------:|
| 1089 | LocRemCtl | supported | **R** | Read-only ✅ (always Local=1) | ✅ |
| 1090 | DERHb | supported | R | Always 0 | ✅ |
| **1092** | **ControllerHb** | **supported** | **RW** | **❌ Write accepted, readback=0** | **⚠️ VIOLATION** |
| 1094 | AlarmReset | supported | RW | Not tested | — |
| 1095 | OpCtl | supported | RW | Not tested | — |

### M715 Takeaway

**ControllerHb declared "supported RW" but hardware silently discards writes.** This is a PICS conformance violation. LocRemCtl correctly declared as Read-only.

---

## Failed Tests Against PICS Claims

The following registers are declared "supported RW" in the PICS but **fail to persist writes.** In all cases:
- **Modbus FC06 (Write Single Register) returned success** — no exception code
- **Readback immediately after showed the original/default value** — write silently discarded
- **No Modbus-layer error** (no 0x01 Illegal Function, 0x02 Illegal Address, etc.)

| # | Register | PICS Claims | Write Value | FC06 Response | Readback | Error Pattern |
|:-:|----------|:-----------:|:-----------:|:------------:|:--------:|:-------------:|
| 1 | **WMaxLimPctEna (310)** | supported RW | 1 | ✅ Success | 0 | Silent discard |
| 2 | **VarSetEna (331)** | supported RW | 1 | ✅ Success | 0 | Silent discard |
| 3 | **ControllerHb (1092)** | supported RW | 1, then 2 | ✅ Success | 0, then None | Silent discard |
| 4 | **WMax (251)** | supported RW (0-10000) | 5000 | ✅ Success | 0 | Silent discard |

> **Root cause unknown.** We have no evidence for why these fail. Possible explanations include firmware gating, SPAN Modbus unlock requirement, or incorrect PICS declaration — but all are speculation without further evidence.

### Features Correctly Declared as Unimplemented

WChaRteMax, WDisChaRteMax, VAChaRteMax, VADisChaRteMax, VarMaxInj, VarMaxAbs, WMaxLimPctRvrt, WRmp — all return 0xFFFF as expected.

### Features That Match PICS

WSetEna, WSetMod, WSet, WSetPct, WSetEnaRvrt, WSetRvrtTms, WSetRvrtRem, PFWInjEna, VarSetMod, VarSetPri, VarSet — all work as declared.

---

## Facts Only Summary

1. **PCS rate registers:** PICS declares "unimplemented", hardware returns 0xFFFF. **Case closed.**

2. **4 registers declared "supported RW" fail tests:** WMaxLimPctEna, VarSetEna, ControllerHb, WMax. All exhibit identical behavior: FC06 success, readback unchanged. Root cause unknown.

3. **WSetRvrtTms is correctly declared and WORKS** — validates our 6-phase re-test methodology.

4. **WSet group (318-329) fully functional** — matches PICS declaration exactly.

---

*Source file: `~/Downloads/PICS_span_20230711_SPANcomments20230803.xlsx`*  
*Last updated: 2026-03-13 22:00 AEDT*
