# P2-P4 DER Control Test Results

**Date:** 2026-03-08 19:43  
**Test:** Write tests for all untested M704 DER control register groups  
**Device:** FranklinWH aGate X (192.168.0.110, Unit 2)

## Summary

| Register Group | Baseline | Write Test | Result |
|---|---|---|---|
| **WMaxLimPct** (Max Power Limit) | Ena=0, Pct=1000 | Write 500, enable | ❌ **STUCK** — writes silently discarded |
| **PFWInjEna** (Power Factor) | Ena=1 (active default!) | Disable→re-enable | ✅ **WRITABLE** — PF changes from -1 to 3 |
| **VarSet** (Reactive Power) | Ena=0, Var=0, Mod=1, Pri=2 | Write 100 VAR, enable | ❌ **STUCK** — writes silently discarded |
| **WRmp** (Ramp Rate) | None (all unimplemented) | Write 100, set ref | ❌ **STUCK** — None values unwritable |
| **AntiIslEna** | None | Not tested (safety) | ⬜ Skipped |

## Detailed Results

### TEST 1: WMaxLimPct (Max Power Limit) — ❌ NON-FUNCTIONAL

```
Baseline: WMaxLimPctEna=0, WMaxLimPct=1000
Write WMaxLimPct=500: wrote 500, read back 1000 ⚠️ STUCK
Write WMaxLimPctEna=1: wrote 1, read back 0 ⚠️ STUCK
After enable: WMaxLimPctEna=0, WMaxLimPct=1000
```

**Conclusion:** Both WMaxLimPct and WMaxLimPctEna are read-only on FranklinWH. Writes succeed (no Modbus error) but values don't change. Same pattern as LocRemCtl Paradox — silently discarded.

### TEST 2: PFWInjEna (Power Factor) — ✅ WRITABLE

```
Baseline: PFWInjEna=1
Current PF (M701): -1
Write PFWInjEna=0 (disable): wrote 0, read back 0 ✅
PF after disable: 3
Restore PFWInjEna=1: wrote 1, read back 1 ✅
```

**Conclusion:** PFWInjEna is **WRITABLE**. This is the only DER control register (besides WSetPct/WSetEna) that actually accepts writes. Interesting discovery:
- When enabled (=1): PF = -1 (likely means unity PF / 1.000 with SF -3)
- When disabled (=0): PF = 3 (meaning 0.003 — essentially no PF correction)
- **Restored to 1 (enabled) — do not leave disabled**

> **Note:** PF_SF = -3, so raw PF value -1 → -0.001 (near unity). The value 3 when disabled → 0.003. The aGate's default PF correction appears to be applied through PFWInjEna.

### TEST 3: VarSet (Reactive Power) — ❌ NON-FUNCTIONAL

```
Baseline: VarSetEna=0, VarSet=0, VarSetMod=1
Write VarSet=100: wrote 100, read back 0 ⚠️ STUCK
Write VarSetEna=1: wrote 1, read back 0 ⚠️ STUCK
After enable: VarSetEna=0, VarSet=0
```

**Conclusion:** VarSet and VarSetEna are read-only on FranklinWH, despite having sensible default values (Mod=1, Pri=2). Same LocRemCtl Paradox pattern.

### TEST 4: WRmp (Ramp Rate) — ❌ UNIMPLEMENTED

```
Baseline: WRmp=None, WRmpRef=None
Write WRmp=100: wrote 100, read back None ⚠️ STUCK
Write WRmpRef=1: wrote 1, read back None ⚠️ STUCK
```

**Conclusion:** All ramp rate registers return None (unimplemented by FranklinWH). Writes have no effect.

## Baseline Register Values (All M704)

### Power Factor (PFW)
| Register | Value | Notes |
|---|---|---|
| PFWInjEna | **1** | ✅ **Active + writable** |
| PFWInjEnaRvrt | None | Unimplemented |
| PFWInjRvrtTms | None | Unimplemented |
| PFWInjRvrtRem | None | Unimplemented |
| PFWAbsEna | None | Unimplemented |
| PFWAbsEnaRvrt | None | Unimplemented |
| PFWAbsRvrtTms | None | Unimplemented |
| PFWAbsRvrtRem | None | Unimplemented |

### Max Power Limit (WMaxLim)
| Register | Value | Notes |
|---|---|---|
| WMaxLimPctEna | 0 | ❌ Read-only |
| WMaxLimPct | 1000 | ❌ Read-only (100% with SF -1) |
| WMaxLimPctRvrt | None | Unimplemented |
| WMaxLimPctEnaRvrt | None | Unimplemented |
| WMaxLimPctRvrtTms | None | Unimplemented |
| WMaxLimPctRvrtRem | None | Unimplemented |

### Reactive Power (VarSet)
| Register | Value | Notes |
|---|---|---|
| VarSetEna | 0 | ❌ Read-only |
| VarSetMod | 1 | ❌ Read-only (pre-configured) |
| VarSetPri | 2 | ❌ Read-only (pre-configured) |
| VarSet | 0 | ❌ Read-only |
| All Rvrt regs | None | Unimplemented |

### Ramp Rate
| Register | Value | Notes |
|---|---|---|
| WRmp | None | ❌ Unimplemented |
| WRmpRef | None | ❌ Unimplemented |
| VarRmp | None | ❌ Unimplemented |

### Scale Factors
| Register | Value | Applied To |
|---|---|---|
| PF_SF | -3 | Power Factor (÷1000) |
| WMaxLimPct_SF | -1 | Max Power Limit (÷10) |
| WSet_SF | 0 | Active Power (×1) |
| WSetPct_SF | -1 | Active Power % (÷10) |
| VarSet_SF | 0 | Reactive Power (×1) |
| VarSetPct_SF | -1 | Reactive Power % (÷10) |

## Updated Writable Register Summary

After all P1-P4 tests, the **complete list of writable M704 registers** on FranklinWH:

| Register | Status | Notes |
|---|---|---|
| WSetEna | ✅ Writable | Core power enable/disable |
| WSetMod | ✅ Writable | Power mode select |
| WSetPct | ✅ Writable | Power percentage (primary control) |
| WSetRvrtTms | ⚠️ Config-only | Accepts value, never activates |
| PFWInjEna | ✅ Writable | Power factor enable (active by default) |
| **Everything else** | ❌ Read-only | Silently discarded or unimplemented |
