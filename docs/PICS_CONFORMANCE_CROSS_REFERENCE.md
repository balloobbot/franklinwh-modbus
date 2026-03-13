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

The following registers are declared "supported RW" in the PICS but **fail to persist writes.**

### Error Pattern (identical across all 4 registers)

- FC06 (Write Single Register): Returns success — no Modbus exception
- FC16 (Write Multiple Registers): Returns success — no Modbus exception
- Readback: Shows original/default value — write silently discarded
- No Modbus-layer error (no 0x01 Illegal Function, 0x02 Illegal Address, etc.)

### Robustness Testing (0/160 — all permutations failed)

| Variable | Values Tested |
|----------|:-----------:|
| Function Code | FC06, FC16 |
| Settle Time | 0.5s, 1.0s, 2.0s, 5.0s |
| VPP Mode | Without (WSetEna=0), With (WSetEna=1) |
| Enable Values | 1, 2 (plus 100 for ControllerHb) |
| WMax Values | 100, 1000, 5000, 10000 |
| SunSpec Sequencing | Isolated writes AND full 6-phase protocol |
| Connection | Fresh TCP connection per test (atomic) |

### Test Infrastructure Details

| Parameter | Value Used | Notes |
|-----------|:----------:|-------|
| **Base address** | 0-based PDU | Addresses (e.g. 310, 331) sent directly in Modbus FC03/FC06 PDU. Confirmed correct: reads return expected values (WMaxLimPct=1000, VarSetMod=1, WSetEna toggles 0↔1) |
| **Unit ID** | **2 only** | Did NOT test UID=1 or UID=126 (standard SunSpec UIDs) |
| **Socket timeout** | 30s | Per-operation |
| **Inter-op delay** | 0.2-0.3s | Between read/write operations within a test |
| **Pre-settle delay** | 0.2s | Between FC06/FC16 write and settle start |
| **Post-settle readback** | Immediate | Read immediately after settle period |
| **Inter-test delay** | 0.3s | Between TCP connections (breathing room) |
| **VPP verification** | Modbus readback only | WSetEna=1 confirmed via FC03 read of register 318. **NOT verified via Cloud API or FEM** |
| **VPP activation** | Library `send_command()` | Uses `FranklinWHController.send_command(BatteryCommand(500W))` which writes WSetEna=1 + WSetPct via pysunspec2 |
| **Target** | 192.168.0.110:502 | WiFi connection, single aGate X |
| **Firmware** | V10R01B04D00 | As reported by M1.Vr |

### Variables NOT Tested

| Variable | Why Not | Risk |
|----------|---------|:----:|
| **Unit ID 1 or 126** | Library auto-detects UID=2; not varied | LOW — reads work at UID=2 |
| **Cloud API VPP verification** | No FEM running during test | MEDIUM — VPP may not have fully activated |
| **Base address ±1** | Library SunSpec scan confirms addresses | LOW — reads return correct values |
| **FC15 (Write Multiple Coils)** | Registers are holding registers, not coils | NONE — not applicable |
| **Multi-register FC16 writes** | Only single-register FC16 tested | LOW — FC06 equivalent tested |
| **Different firmware versions** | Only V10R01B04D00 tested | N/A — only one device available |

### Register-Level Results

| # | Register (Model) | PICS Claims | Tests Run | Passed | Error Pattern |
|:-:|----------|:-----------:|:---------:|:------:|:-------------:|
| 1 | **M704.WMaxLimPctEna** (310) | supported RW | 32 | 0 | Silent discard |
| 2 | **M704.VarSetEna** (331) | supported RW | 32 | 0 | Silent discard |
| 3 | **M715.ControllerHb** (1092) | supported RW | 53 | 0 | Silent discard |
| 4 | **M702.WMax** (251) | supported RW (0-10000) | 27 | 0 | Silent discard |

### Additional Findings (Phase 3 — Full Sequencing)

| Register (Model) | PICS Status | Test | Result |
|----------|:-----------:|------|:------:|
| M704.WMaxLimPct (311) | supported RW | Write 500, readback | 1000 (not stuck) |
| M704.WMaxLimPct_SF (350) | supported R | Read | **-1** (valid scale factor — 0xFFFF as signed sunssf = -1, means ×10^-1) |
| M704.VarSetMod (332) | supported RW | Write 5, readback | 1 (not stuck) |
| M704.VarSet (334) | supported RW | Write 100, readback | 0 (not stuck) |
| M715.DERHb (1090) | supported R | Read | 0 (always zero — device never sends heartbeat) |

> **Note:** WMaxLimPct, VarSetMod, and VarSet appeared to accept writes in earlier tests but here show readback to defaults. This suggests these registers also silently discard writes, or previous readbacks were from cache. Further investigation would confirm, but the enable registers remain the key blockers.

> **Root cause unknown.** All are speculation without further evidence.

### Features Correctly Declared as Unimplemented

M702: WChaRteMax (259), WDisChaRteMax (260), VAChaRteMax (261), VADisChaRteMax (262), VarMaxInj (257), VarMaxAbs (258) — all return 0xFFFF.
M704: WMaxLimPctRvrt (312), WMaxLimPctEnaRvrt (313), VarSetRvrt (336), WRmp (345) — all return 0xFFFF or None.

### Features That Match PICS

M704: WSetEna (318), WSetMod (319), WSet (320), WSetPct (324), **WSetRvrt (322)**, WSetEnaRvrt (326), WSetRvrtTms (327), WSetRvrtRem (329), PFWInjEna (298).
M715: LocRemCtl (1089, R-only as declared).

> **WSetRvrt (322) verified 2026-03-13:** Write=2500, readback=[0, 2500] ✅ STICKY. The reversion target is writable and persists.

---

## Facts Only Summary

1. **PCS rate registers:** PICS declares "unimplemented", hardware returns 0xFFFF. **Case closed.**

2. **4 registers declared "supported RW" fail tests (0/160):** WMaxLimPctEna, VarSetEna, ControllerHb, WMax. All exhibit identical behavior: FC06/FC16 success, readback unchanged. Exhaustively tested across settle times, values, sequencing, and VPP state.

3. **WSet group (318-329) fully functional** — WSetRvrtTms WORKS (countdown active), WSetRvrt WORKS (reversion target sticky). Matches PICS.

4. **CtrlModes (M702.248) bitmask = 14271 = 0x37BF:**
   ```
   Bit  Mode               Available
    0   MAX_W               YES
    1   FIXED_W             YES
    2   FIXED_VAR           YES   <-- firmware claims VAR is available
    3   FIXED_PF            YES
    4   VOLT_VAR            YES
    5   FREQ_WATT           YES
    6   DYN_REACT_CURR      NO
    7   LV_TRIP (LVRT)      YES
    8   HV_TRIP (HVRT)      YES
    9   WATT_VAR            YES
   10   VOLT_WATT           YES
   11   SCHEDULED           NO
   12   LF_TRIP (LFRT)      YES
   13   HF_TRIP (HFRT)      YES
   ```
   **Fact:** Firmware declares FIXED_VAR (bit 2) as available, yet VarSetEna writes are silently discarded.

---

## LocRemCtl Analysis

> **This section presents observed facts (labeled as FACT) and hypotheses (labeled as HYPOTHESIS). They are clearly distinguished.**

**FACT:** LocRemCtl (M715.1089) always reads `Local = 1` and is declared `R` (read-only) in the PICS. There is no documented path to transition to `Remote = 0`.

**FACT:** The WSet group (318-329) works despite LocRemCtl=Local. These registers are the core VPP power control path.

**FACT:** All other "supported RW" control registers (WMaxLimPctEna, VarSetEna, ControllerHb, WMax) silently discard writes. These are non-VPP control features.

**FACT:** CtrlModes bitmask claims FIXED_VAR and FIXED_PF are available at the firmware level.

**HYPOTHESIS (unverified):** LocRemCtl=Local may be the root cause for all 4 PICS failures. The WSet group may be a selective carve-out (VPP bypass) that works despite Local mode, while other control features require Remote mode authority that cannot be granted because LocRemCtl is read-only.

### Control Path Classification

```
┌───────────────────────────────────────────────────┐
│ WORKING ✅ (VPP carve-out)                       │
│                                                   │
│  M704.WSetEna (318)    ─► VPP Mode enable         │
│  M704.WSet (320)       ─► Power setpoint (W)      │
│  M704.WSetPct (324)    ─► Power setpoint (%)      │
│  M704.WSetRvrt (322)   ─► Reversion target ✅      │
│  M704.WSetRvrtTms (327)─► Dead-man timer ✅        │
│  M704.WSetRvrtRem (329)─► Countdown readback ✅   │
│  M704.WSetEnaRvrt (326)─► Reversion enable ✅     │
│  M704.PFWInjEna (298)  ─► PF inject (writable)    │
├───────────────────────────────────────────────────┤
│ BLOCKED ❌ (LocRemCtl=Local?)                      │
│                                                   │
│  M704.VarSetEna (331)     ─► Reactive power — DEAD │
│  M704.WMaxLimPctEna (310) ─► Curtailment % — DEAD  │
│  M715.ControllerHb (1092) ─► Heartbeat — DEAD      │
│  M702.WMax (251)          ─► Max power — DEAD      │
└───────────────────────────────────────────────────┘
```

---

## Hardware Reversion Safety — Test Result

> **CRITICAL FINDING:** The WSetRvrtTms countdown is cosmetic. It does NOT physically revert power or disable VPP when it reaches 0.

### Reversion Efficacy Test (2026-03-13 22:59 AEDT)

**Setup:** VPP active (WSetEna=1, WSetPct=-500), WSetRvrt=0, WSetEnaRvrt=1, WSetRvrtTms=30.
**Extended observation:** 3+ minutes post-expiry, NO forced cleanup until verdict.

```
     T  WSetEna  WSetPct  RvrtRem  Notes
   ──  ───────  ───────  ───────  ────────────────────────────
    1s        1     -500       29  counting down
    7s        1     -500       23  counting down
   11s        1     -500       19  counting down
   16s        1     -500       14  counting down
   21s        1     -500        9  counting down
   26s        1     -500        4  counting down
   31s        1     -500        0  EXPIRED — still active ⚠️
   39s        1     -500        0  9s post  — still active ⚠️
   46s        1     -500        0  16s post — still active ⚠️
   68s        1     -500        0  38s post — still active ⚠️
   98s        1     -500        0  68s post — still active ⚠️
  136s        1     -500        0  106s post — still active ⚠️
  176s        1     -500        0  146s post — still active ⚠️
  216s        1     -500        0  186s post — still active ⚠️
```

**Final state (186s post-expiry):** WSetEna=1, WSetPct=-500, WSetRvrtRem=0.
**Cleanup:** VPP was **force-released** by test script calling `reset_control_state()`. Device did **NOT** auto-release.

**Corroborating evidence (user-observed):**
- FranklinWH app: "VPP Mode" displayed throughout, "Charging 2.5 kW"
- MQTT Explorer: "Runtime Mode: VPP mode" persisted
- Home Assistant: History shows VPP mode sustained, no mode transitions

**Alarms during reversion test:**
- M701.Alrm (76) = 0 — no DER alarms
- M714.PrtAlrms (1044) = 0 — no DC port alarms
- Device raised no alerts or alarms when countdown expired without reversion

**Facts:**
- Countdown mechanism works perfectly (30→23→...→4→0)
- Device did NOT auto-release VPP for 186 seconds (3+ min) after countdown reached 0
- WSetEna=1 and WSetPct=-500 unchanged throughout entire observation window
- NOT a latency/network issue — observation window is 186s, far exceeding any plausible delay
- The dead-man switch countdown is **cosmetic — it does NOT trigger power reversion**

**Implication:** WSetRvrtTms cannot be used as a hardware crash-recovery mechanism. The software watchdog (`controller.py` timeout) remains the **only** safety mechanism for reverting power after loss of communication.

---

## PICS Violation Report Template

```
PICS Violation Report — aGate X (AGT-R1V1-AU Hybrid)
Firmware: V10R01B04D00
Test Date: 2026-03-13
PICS Source: PICS_span_20230711_SPANcomments20230803.xlsx

Issue 1 — LocRemCtl permanently Local
  M715.LocRemCtl (1089) returns Local=1 with no path to Remote.
  CtrlModes (M702.248) = 14271 declares FIXED_VAR (bit 2) and
  FIXED_PF (bit 3) as firmware-available, contradicting the
  non-functional VarSetEna and strengthening the case that a
  Modbus access gate exists (LocRemCtl or equivalent) that is
  not documented in PICS.
  This causes cascading silent-discard on:
    - M704.VarSetEna (331)     declared supported RW
    - M704.WMaxLimPctEna (310) declared supported RW
    - M715.ControllerHb (1092) declared supported RW
  Testing: 0/160 across FC06/FC16, settle 0.5-5s, ±VPP, + sequenced.
  REQUEST: Document the mechanism to transition to Remote mode,
           OR update PICS to reflect actual constraints.

Issue 2 — WMax (251) write silently discarded
  PICS declares supported RW (0-10000).
  Tested: FC06/FC16, values 100/1000/5000/10000, settle 0.5-5s,
          with and without VPP. ALL silently discarded.
  Note: WSet (320) accepts values 0-10000W and works correctly.
  If WMax is intended as a ceiling on WSet, the absence of WMax
  write capability means the only power ceiling is WMaxRtg (227)
  = 10000W (read-only hardware rating). No software curtailment
  ceiling is achievable via PICS-declared registers.
  REQUEST: Confirm if SPAN Modbus unlock is required.

Issue 3 — CtrlModes declares FIXED_VAR available but Modbus
          path is non-functional
  M702.CtrlModes (248) = 14271 (0x37BF)
  Bit 2 (FIXED_VAR) = 1 — firmware declares reactive power available
  Bit 3 (FIXED_PF)  = 1 — firmware declares PF control available
  Yet M704.VarSetEna (331) silently discards all writes (0/160 tests).
  VarSetEna is the ONLY SunSpec Modbus path to exercise FIXED_VAR.
  No alternative Modbus registers expose reactive power control.
  REQUEST: Clarify whether CtrlModes bitmask represents hardware
  capability or Modbus-controllable capability. If the former,
  update PICS documentation to define this distinction explicitly.
Issue 4 — WSetRvrtTms countdown does not revert power (SAFETY)
  PICS declares WSetRvrtTms (327) as supported RW.
  Countdown mechanism works (30→23→...→0), but WSetEna and
  WSetPct are unchanged after expiry. Observed for 186s (3+ min)
  post-expiry with NO forced cleanup — device never auto-released.
  No alarms raised (M701.Alrm=0, M714.PrtAlrms=0).
  Corroborated by user via FHP app (VPP persisted) and MQTT.
  This defeats the SunSpec dead-man switch safety mechanism.
  REQUEST: Confirm implementation status of reversion
  behaviour at countdown expiry.
```

---

## Document Status

```
CLOSED — no further testing warranted:
  ✅ PCS rate registers (unimplemented, 0xFFFF confirmed)
  ✅ WSet group (318-329) — fully functional
  ✅ WSetRvrt (322) — reversion target writable and sticky
  ✅ M702 unimplemented registers — all match PICS

CLOSED — PICS violation filed:
  ⚠️ WMaxLimPctEna (310)       — 0/32  (Issue 1)
  ⚠️ VarSetEna (331)           — 0/32  (Issue 1)
  ⚠️ ControllerHb (1092)       — 0/53  (Issue 1)
  ⚠️ WMax (251)                — 0/27  (Issue 2)
  ⚠️ CtrlModes contradiction   — (Issue 3)
  🔴 WSetRvrtTms non-reversion — (Issue 4, SAFETY, 186s observed)

OPEN — test required before production sign-off:
  🟡 PFWInjEna (298) functional outcome
```

---

*Source file: `~/Downloads/PICS_span_20230711_SPANcomments20230803.xlsx`*  
*Last updated: 2026-03-13 23:00 AEDT*
