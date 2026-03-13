# Test Results — 2026-03-13 (PCS Charge/Discharge Rate Write-Probe)

**Date:** 2026-03-13 20:15 AEDT  
**Device:** FranklinWH aGate X @ 192.168.0.110 (Unit ID: 2)  
**Firmware:** V10R01B04D00

---

## Goal

Determine if `WChaRteMax` / `WDisChaRteMax` (addresses 259-262 base-1) accept writes.
These are the SunSpec equivalents of the Cloud API `setPowerControl` (globalGridChargeMax / globalGridDischargeMax).

## Target Registers

| Address (base-1) | Address (base-40000) | Point | Type | SunSpec Access | Unit |
|:-:|:-:|---|---|:-:|---|
| 235 | 40235 | `WChaRteMaxRtg` | uint16 | R | W |
| 236 | 40236 | `WDisChaRteMaxRtg` | uint16 | R | W |
| 237 | 40237 | `VAChaRteMaxRtg` | uint16 | R | VA |
| 238 | 40238 | `VADisChaRteMaxRtg` | uint16 | R | VA |
| **259** | **40259** | **`WChaRteMax`** | uint16 | **RW** | W |
| **260** | **40260** | **`WDisChaRteMax`** | uint16 | **RW** | W |
| **261** | **40261** | **`VAChaRteMax`** | uint16 | **RW** | VA |
| **262** | **40262** | **`VADisChaRteMax`** | uint16 | **RW** | VA |

## Method

Safe values used: 5000W (= WChaRteMaxRtg nameplate) / 5800VA (= VAChaRteMaxRtg nameplate).
Even if writes were accepted, no actual limit change would occur.

5-phase test:
1. **Baseline read** via sunspec2 model access
2. **Write-back** via sunspec2 model
3. **Write via raw TCP** at base-1 addresses
4. **Write via raw TCP** at base-40000 addresses
5. **Safety verification**

## Results

### Phase 1: Baseline Read (sunspec2)
- W_SF scale factor: 0
- **All nameplate ratings returned `None`** (sunspec2 reports `None` for 0xFFFF)
- **All RW settings returned `None`** (sunspec2 reports `None` for 0xFFFF)

> **Note:** sunspec2 reader `--vals` shows these as readable with values (5000W, 5800VA) but the model `.read()` returns `None`. This is because sunspec2 applies the SunSpec "not implemented" filter (0xFFFF for uint16 = "not implemented").

### Phase 2: Write via sunspec2 Model
**All 4 points: ❌ "Point not found in model"**

The sunspec2 library does not expose `WChaRteMax` / `WDisChaRteMax` as writable points on Model 703. These points may be defined on a different model in the sunspec2 data definitions.

### Phase 3: Write via Raw TCP (base-1 addresses)

| Register | Addr | Read Before | Wrote | Read After | Sticky? |
|----------|:----:|:-----------:|:-----:|:----------:|:-------:|
| WChaRteMax | 259 | 65535 (0xFFFF) | 5000 | 65535 | ❌ NO |
| WDisChaRteMax | 260 | 65535 (0xFFFF) | 5000 | 65535 | ❌ NO |
| VAChaRteMax | 261 | 65535 (0xFFFF) | 5800 | 65535 | ❌ NO |
| VADisChaRteMax | 262 | 65535 (0xFFFF) | 5800 | 65535 | ❌ NO |

- All writes **accepted at protocol level** (no Modbus exception)
- All writes **silently discarded** (values revert to 0xFFFF)
- 0xFFFF = SunSpec "not implemented" sentinel for uint16

### Phase 4: Write via Raw TCP (base-40000 addresses)

| Register | Addr | Read Before | Wrote | Result |
|----------|:----:|:-----------:|:-----:|:------:|
| WChaRteMax | 40259 | None | 5000 | ❌ **Modbus exception 2** (ILLEGAL_DATA_ADDRESS) |
| WDisChaRteMax | 40260 | None | 5000 | ❌ **Modbus exception 2** |
| VAChaRteMax | 40261 | None | 5800 | ❌ **Modbus exception 2** |
| VADisChaRteMax | 40262 | None | 5800 | ❌ **Modbus exception 2** |

- **Base-40000 addressing does NOT work for writes** to these registers
- The aGate rejects writes at 40000+ offsets but accepts (and discards) at base-1

### Phase 5: Safety Verification ✅

| Metric | Value |
|--------|-------|
| Battery SoC | 87.0% |
| Battery State | CHARGING |
| Native Mode | Self-Consumption |
| WSetEna | 0 (no active control) |

No adverse effects observed.

### Phase 6: Re-Probe WITH VPP Mode Active (WSetEna=1)

**Hypothesis:** User speculated that writes may only be accepted when the aGate has been placed under active Modbus control (VPP Mode).

**Method:** Sent `send_command(0W)` (standby, safe) → confirmed `WSetEna=1` → re-probed writes at base-1 addresses.

| Register | Addr | VPP Active? | Read Before | Wrote | Read After | Sticky? |
|----------|:----:|:-----------:|:-----------:|:-----:|:----------:|:-------:|
| WChaRteMax | 259 | ✅ WSetEna=1 | 65535 | 5000 | 65535 | ❌ NO |
| WDisChaRteMax | 260 | ✅ WSetEna=1 | 65535 | 5000 | 65535 | ❌ NO |
| VAChaRteMax | 261 | ✅ WSetEna=1 | 65535 | 5800 | 65535 | ❌ NO |
| VADisChaRteMax | 262 | ✅ WSetEna=1 | 65535 | 5800 | 65535 | ❌ NO |

**Result:** ❌ **Hypothesis ruled out.** VPP Mode does not unlock these registers.

Post-release safety check: SoC=87%, IDLE, Self-Consumption, WSetEna=0 ✅

### Phase 7: Re-Probe WITH Real 500W Charge (VPP Forced)

**Hypothesis (refined):** User observed FEM API shows `controlSource: "Cloud API"` even with WSetEna=1 — 0W standby may not trigger real VPP Mode. Used 500W charge to force actual battery response.

**Method:** Sent `send_command(500W charge)` → waited 8s → confirmed `WSetEna=1`, `WSetPct=-10.0%`, battery state changed → probed writes.

**Confirmation VPP engaged:**
- WSetEna = 1 ✅
- WSetPct = -10.0% (500W charge = 10% of 5000W nameplate) ✅
- Battery state changed from pre-check state ✅

| Register | Addr | VPP Active? | Read Before | Wrote | Read After | Sticky? |
|----------|:----:|:-----------:|:-----------:|:-----:|:----------:|:-------:|
| WChaRteMax | 259 | ✅ WSetEna=1, charging | 65535 | 5000 | 65535 | ❌ NO |
| WDisChaRteMax | 260 | ✅ WSetEna=1, charging | 65535 | 5000 | 65535 | ❌ NO |
| VAChaRteMax | 261 | ✅ WSetEna=1, charging | 65535 | 5800 | 65535 | ❌ NO |
| VADisChaRteMax | 262 | ✅ WSetEna=1, charging | 65535 | 5800 | 65535 | ❌ NO |

**Result:** ❌ **PCS registers definitively NOT writable**, even with active VPP Mode and battery responding to commands.

Post-release safety check: SoC=87%, CHARGING, Self-Consumption, WSetEna=0 ✅

## Key Findings

1. **WChaRteMax / WDisChaRteMax are NOT writable** — writes silently discarded (same pattern as WMaxLimPct, extension registers).
2. **Raw values are 0xFFFF** — SunSpec "not implemented" sentinel, matching the "None" display in sunspec2.
3. **Addressing asymmetry confirmed**: base-1 accepts writes (silently), base-40000 returns ILLEGAL_DATA_ADDRESS for writes. This is consistent with the prior M715 finding.
4. **Cloud API remains the only path** for PCS charge/discharge rate limiting (globalGridChargeMax / globalGridDischargeMax).
5. **sunspec2 model access** doesn't expose these points as part of M703 — they may be on a different model or need explicit model registration.

## Addressing Quirk Summary (Updated)

| Operation | Base-1 | Base-40000 |
|-----------|:------:|:----------:|
| **Read** these registers | ✅ Returns 0xFFFF | ✅ Returns None (via sunspec2) |
| **Write** these registers | ⚠️ Accepted, silently ignored | ❌ Modbus exception 2 |
| **Read** M715 registers | ✅ Works | ❌ ILLEGAL_DATA_ADDRESS |
| **Write** M704 WSetPct | ✅ Works | ✅ Works (via sunspec2) |

---

*Test script: `/tmp/pcs_write_probe.py`*  
*Raw results: `/tmp/pcs_write_probe_results.json`*
