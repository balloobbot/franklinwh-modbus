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

All "unimplemented" registers match exactly (0xFFFF). The only surprise is **WMax (251)** which PICS declares as "supported RW" (0-10000) but our write was silently discarded (readback=0). This may need SPAN Modbus unlock.

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

## PICS Conformance Violations Summary

| # | Register | PICS Claims | Actual Behavior | Severity |
|:-:|----------|:-----------:|:---------------:|:--------:|
| 1 | **WMaxLimPctEna (310)** | supported RW | Write silently discarded | **HIGH** — prevents power limit control |
| 2 | **VarSetEna (331)** | supported RW | Write silently discarded | **HIGH** — prevents reactive power control |
| 3 | **ControllerHb (1092)** | supported RW | Write silently discarded | **HIGH** — prevents heartbeat safety |
| 4 | **WMax (251)** | supported RW (0-10000) | Write=5000, readback=0 | **MEDIUM** — may need SPAN unlock |

### Features Correctly Declared as Unimplemented

WChaRteMax, WDisChaRteMax, VAChaRteMax, VADisChaRteMax, VarMaxInj, VarMaxAbs, WMaxLimPctRvrt, WRmp — all return 0xFFFF as expected.

### Features That Match PICS

WSetEna, WSetMod, WSet, WSetPct, WSetEnaRvrt, WSetRvrtTms, WSetRvrtRem, PFWInjEna, VarSetMod, VarSetPri, VarSet — all work as declared.

---

## Implications

1. **PCS rate registers:** We can STOP investigating these — PICS declares them "unimplemented" and our tests confirm. No firmware update will change this without a new PICS.

2. **VarSetEna and WMaxLimPctEna:** File as PICS violations with FranklinWH. The PICS declares them "supported" but they don't work. This may indicate these features require SPAN Modbus unlock or are behind a firmware gate.

3. **ControllerHb:** Same — PICS violation. The heartbeat is declared supported but doesn't function.

4. **WSetRvrtTms is correctly declared and WORKS** — this validates our re-test methodology.

---

*Source file: `~/Downloads/PICS_span_20230711_SPANcomments20230803.xlsx`*  
*Last updated: 2026-03-13 21:52 AEDT*
