# DCW Sign Convention Validation — 2026-03-12

**Change Under Test:** `controller.py` M714.DCW sign convention fix  
**Commit:** `68b180e` — "Fix M714.DCW sign convention: positive=charging, negative=discharging"  
**Date:** 2026-03-12 21:33–21:36 AEDT  
**Tester:** Agent (Tier 2 pre-approved)  
**Device:** aGate X (SN: 10060006A02F24170091, FW: V10R01B04D00)

---

## Pre-Test State

| Check | Result |
|-------|--------|
| SoC | 74.0% ✅ (in range 10-95%) |
| Grid | Connected ✅ |
| Voltage | 241.6V ✅ (in range 200-270V) |
| Alarms | None ✅ |
| Control Source | Cloud API (Self-Consumption) ✅ |
| Zombie State | OK ✅ |
| Unit Tests | 32 passed, 7 skipped ✅ |

---

## Test 1: Charge at 500W

**Command:** `python3 tools/franklinwh_cli.py -i 192.168.0.110 --charge 500 --revert 30`

**Expected:** M714.DCW positive (power INTO battery), battery_state = CHARGING  
**Actual:**

```
Battery: ↓   500W  CHARGING  (M714.DCW)
Grid: ←  2739W  IMPORTING  (M701.W)
DC Power:         500W  CHARGING  (M714.DCW)
Modbus Control:   ACTIVE (WSet=0W)
```

**Result:** ✅ **PASS** — M714.DCW positive = CHARGING. Grid imported extra power for home load + charge.

---

## Test 2: Discharge at 500W

**Command:** `python3 tools/franklinwh_cli.py -i 192.168.0.110 --discharge 500 --revert 30`

**Expected:** M714.DCW negative (power OUT of battery), battery_state = DISCHARGING  
**Actual:**

```
Battery: ↑   500W  DISCHARGING  (M714.DCW)
Grid: ←  1891W  IMPORTING  (M701.W)
DC Power:         500W  DISCHARGING  (M714.DCW)
Modbus Control:   ACTIVE (WSet=0W)
```

**Result:** ✅ **PASS** — M714.DCW negative = DISCHARGING. Grid import dropped (battery supplementing home load).

---

## Post-Test State

| Check | Result |
|-------|--------|
| Control Released | `--stop` → WSetEna=0, WSetPct=0 ✅ |
| Control Source | Cloud API (aGate native mode) ✅ |
| Zombie State | OK ✅ |
| Health Check | HEALTHY ✅ |
| Battery Resumed | DISCHARGING 800W (Self-Consumption) ✅ |
| Alarms | None ✅ |

---

## Conclusion

**M714.DCW sign convention CONFIRMED:**
- `positive DCW` = power INTO battery = **CHARGING**
- `negative DCW` = power OUT of battery = **DISCHARGING**
- `battery_state` derivation in `controller.py:read_battery_status()` is correct
- `--status` display in `franklinwh_cli.py` accurately reflects battery direction

**Overall:** ✅ **ALL TESTS PASSED**
