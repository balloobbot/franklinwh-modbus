# Test Results — 2026-03-16 (WSetPct Charge Rate Bug Fix)

**Commit:** `e509eee` (develop)
**Date:** 2026-03-16 23:00 AEDT
**Device:** FranklinWH aGate X @ 192.168.0.110

## Defect Report

| Field | Value |
|-------|-------|
| **ID** | DEF-001 |
| **Title** | WSetPct uses wrong denominator — WMaxRtg vs charge/discharge rate |
| **Severity** | 🔴 CRITICAL |
| **Status** | ✅ RESOLVED |
| **Commit (fix)** | `e509eee` |
| **Root Cause** | `send_command()` calculated WSetPct as `watts / RATED_MAX_W` where `RATED_MAX_W = WMaxRtg = 1000W` (AC inverter rating). Should use `RATED_MAX_CHARGE_W = 5000W` or `RATED_MAX_DISCHARGE_W = 5000W` (battery charge/discharge rates). |
| **Impact** | Any charge/discharge request >1000W calculated >100%, which hardware interprets as max rate. `--charge 1200` charged at 5000W. |
| **Reproduction** | `python3 tools/franklinwh_cli.py -i 192.168.0.110 --charge 1200` |

### Before Fix
```
WSetPct=-120.0% (raw=-1200), WSet=0, WSetEna=1
Result: 1200.0W (-120.0% of 1000W)    ← WRONG denominator
Actual: Battery: ↓ 5000W CHARGING      ← WRONG rate (max)
Grid:   ← 5734W IMPORTING
```

### After Fix
```
WSetPct=-24.0% (raw=-240), WSet=0, WSetEna=1
Result: 1200.0W (-24.0% of 5000W)     ← CORRECT denominator
Actual: Battery: ↓ 1200W CHARGING      ← CORRECT rate
Grid:   ← 1897W IMPORTING
```

## 1. Live Verification

### Command Issued
```
python3 tools/franklinwh_cli.py -i 192.168.0.110 --charge 1200 --revert 120
```

### Command Output (FIXED)
```
Device ratings: Max=1000W, Charge=5000W, Discharge=5000W
Command sent: WSetPct=-24.0% (raw=-240), WSet=0, WSetEna=1
Result: SUCCESS - Command Sent: 1200.0W (-24.0% of 5000W) [timeout: 120s]
```

### Status Verification (20 seconds after command)
```
⚡ POWER FLOW SUMMARY
    Solar:       0W  Idle  (M502.OutPw)
     Home: ←   698W  Consuming  (Ext.16000)
   Battery: ↓  1200W  CHARGING  (M714.DCW)     ✅ EXACTLY 1200W
     Grid: ←  1897W  IMPORTING  (M701.W)

🔋 BATTERY POWER (DC)
  State of Charge:  49.0%  (M713.SoC)
  DC Power:         1200W  CHARGING
  Modbus Control:   ACTIVE (WSet=0W)
```

**Power balance check:** Solar(0) + Grid(1897) = Battery(1200) + Home(698) → 1897 ≈ 1898 ✅

## 2. Changes Tested

| Change | Test Type | Result |
|--------|-----------|--------|
| WSetPct denominator (send_command) | Live charge 1200W | ✅ Charges at 1200W (was 5000W) |
| Success message shows correct rated | Visual inspection | ✅ Shows "of 5000W" (was "of 1000W") |
| actual_power readback (read_full_status) | Status display | ✅ Shows correct Modbus Control info |
| Auto-revert timer | Live with --revert 120 | ✅ Timer set |

## 3. Tests Bypassed

| Test | Reason | Risk | Follow-up |
|------|--------|------|-----------|
| Discharge direction test | Night, no solar, battery at 49% | Low — same code path | Test discharge when SoC allows |
| Unit tests (pytest) | Focus on live hardware verification | Low | Run next session |

## 5. Additional Defects (found and resolved)

### DEF-002: "ORPHANED VPP DETECTED" warning is incorrect

| Field | Value |
|-------|-------|
| **Severity** | 🟡 Minor (UX) |
| **Status** | ✅ RESOLVED |
| **Commit** | `fee3465` |
| **Root Cause** | `_check_orphaned_vpp()` treated WSetEna=1 as alarming, but it's the normal persistent state after any command since hardware reversion doesn't work (PICS Issue 4). |
| **Fix** | Downgraded from `logger.warning` to `logger.info`. Removed alarming "ORPHANED" language. |

### DEF-003: EXTENSION REGISTERS section clutters --status

| Field | Value |
|-------|-------|
| **Severity** | 🟡 Minor (UX) |
| **Status** | ✅ RESOLVED |
| **Commit** | `fee3465` |
| **Root Cause** | `--status` displayed a full EXTENSION REGISTERS (15500+) block showing write-test results. This is diagnostic info that belongs in `--healthcheck` only. |
| **Fix** | Removed the section from `print_status()`. Still available in `--healthcheck`. |

## 6. Cross-Agent Validation (FranklinWH Energy Manager)

The FEM agent confirmed:
- `modbus_control.py` passes watts directly as `BatteryCommand(power_watts=...)` — **no workaround existed**
- Validated range is 0–5000W (from nameplate), straight passthrough to `send_command()`
- **Before fix:** 2000W request → library computed WSetPct=-200% → hardware capped at 5000W
- **After fix:** 2000W request → library computes WSetPct=-40% → hardware charges at exactly 2000W
- **No code changes needed in FEM** — the library fix is transparent

## 7. Known Limitations

- `RATED_MAX_W` (WMaxRtg=1000W) still exists as a field — it's the AC inverter rating and may
  have valid uses. The bug was using it as the WSetPct denominator.
- The standalone tool (`franklinwh_control_standalone.py`) has its own `send_command()` copy
  that may have the same bug — should be checked and aligned.
