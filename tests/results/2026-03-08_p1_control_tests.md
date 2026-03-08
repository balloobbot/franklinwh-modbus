# Test Results — 2026-03-08 (P1 Control Tests)

**Commit:** `95a6641` (develop, pre-test baseline)  
**Date:** 2026-03-08 16:40-16:48 AEDT  
**Device:** FranklinWH aGate X @ 192.168.0.110  
**Firmware:** V10R01B04D00  
**SoC at start:** 79%  
**Operating mode:** Self-Consumption (reserve 20%)

---

## 1. Test 1: ControllerHb (M715, addr 1092)

**Goal:** Determine if aGate accepts heartbeat writes and activates DER heartbeat protocol.

### Test 1a — Via sunspec2 model.write()
```
Step 1 — Baseline:        ControllerHb = 0, DERHb = 0
Step 2 — Write(1):        ControllerHb = 0 ← IGNORED
Step 3 — Write(2):        ControllerHb = 0 ← IGNORED
Step 4 — Write(100):      ControllerHb = 0 ← IGNORED
```
**Result:** ❌ Writes via sunspec2 silently ignored (no exception, value unchanged)

### Test 1b — Via raw Modbus TCP (addr 41092)
```
Write at 41092: ERROR: ILLEGAL_DATA_ADDRESS
Read at 41092:  ERROR: ILLEGAL_DATA_ADDRESS
```
**Result:** ❌ Wrong address — M715 not accessible at 40000+ offset via raw TCP

### Test 1c — Via raw Modbus TCP (addr 1092, base-1)
```
Step 0 — M715 readable: ID=715, L=7, LocRemCtl=1, DERHb=0, ControllerHb=0
Step 1 — Write(1) func 16: ok=True
         After: ControllerHb = 0 ← Write ACCEPTED but value DID NOT CHANGE
```
**Result:** ❌ Write accepted (no Modbus error) but value silently ignored by firmware

### Test 1 Verdict
**❌ ControllerHb NOT FUNCTIONAL on FranklinWH aGate.**
- Write accepted at protocol level (no exception, no Modbus error)
- Value stays at 0 regardless of write method (sunspec2 or raw TCP)
- DERHb also stays 0 — DER heartbeat protocol not implemented
- Consistent with LocRemCtl=1 (Local mode) — remote controller features blocked

### Discovery: Address Mapping
| Method | M715 Base Address | Result |
|--------|------------------|--------|
| sunspec2 client | Internal model scan | ✅ Readable, write silently fails |
| Raw TCP @ 41087+ | 40000 + offset | ❌ ILLEGAL_DATA_ADDRESS |
| Raw TCP @ 1087+ | 1 + offset (--base 1) | ✅ Readable, write silently fails |

**New Quirk:** M715 registers are only accessible at base-1 addresses (1087-1095), NOT at base-40000 addresses (41087-41095). This differs from M704 which works at both.

---

## 2. Test 2: WSetRvrtTms (M704, addr 327)

**Goal:** Set a reversion timeout, issue a power command, observe countdown.

### Test 2a — Set timer before send_command()
```
WSetRvrtTms = 60 → ACCEPTED (persisted across reads)
send_command(-200) → ERROR: 'int' object has no attribute 'power_watts'
  (Wrong API — needs BatteryCommand object, not int)
WSetEna stayed 0 → timer never started
```
**Result:** ⚠️ send_command API issue — WSetRvrtTms accepted but test inconclusive

### Test 2b — With correct BatteryCommand
```
WSetRvrtTms = 60 → ACCEPTED
BatteryCommand(-200W) → ok=True, WSetEna=1, WSetPct=40 (4%)
WSetRvrtRem = 0 (immediately after enable)
After 5s:  WSetRvrtRem = 0
After 10s: WSetRvrtRem = 0
Battery power observed: -400W then 200W (charging working)
```
**Result:** ❌ Timer config persisted but countdown never activates

### Test 2c — SunSpec-correct sequencing (CONFIG ALL → ENABLE)
```
Step 1: WSetEna=0 (clean state)
Step 2: Single write: WSetMod=0, WSetPct=40, WSetRvrtTms=60, WSetRvrt=0, WSetPctRvrt=0
Step 3: WSetEna=1
Step 4: WSetRvrtTms=60 ✅, WSetRvrtRem=0 ❌
After 5s:  WSetRvrtRem=0
After 10s: WSetRvrtRem=0
Battery power: -400W (command working) then 200W (discharging after reset)
```
**Result:** ❌ Even with SunSpec-correct sequencing, WSetRvrtRem stays 0

### Test 2 Verdict
**⚠️ WSetRvrtTms PARTIALLY FUNCTIONAL:**
- ✅ WSetRvrtTms value is writable and persists (accepts 0, 60, etc.)
- ❌ WSetRvrtRem countdown NEVER activates (always 0)
- ❌ Reversion behavior not observed (command stays active until manual reset)
- Power commands (WSetPct) work correctly — charging at -400W observed

---

## 3. Root Cause Analysis

Both features (heartbeat + reversion timer) share a common pattern:
- Register accepts writes at the protocol level
- But the **firmware does not implement the behavior**

**Most likely cause:** `LocRemCtl = 1` (Local Control) is **read-only** on the FranklinWH aGate.

Per SunSpec 2 spec, the DER heartbeat and reversion timer are **remote controller lifecycle features** that require `LocRemCtl = 0` (Remote Control). Since the aGate locks this to Local:
- Power commands (WSetEna, WSetPct) work in Local mode ✅
- Remote lifecycle features (heartbeat, reversion countdown) are blocked ❌
- This is consistent with the write access asymmetry documented in FRANKLINWH_SUNSPEC_QUIRKS.md

**Implication for the library:**
- Cannot rely on hardware reversion — must implement **software-side timeout** in the controller
- Cannot rely on heartbeat — must implement **software-side watchdog** for command persistence
- The `healthcheck()` zombie detection (checking WSetRvrtRem) is correct as a safety net but WSetRvrtRem will always be 0

---

## 4. Tests Bypassed

None — all planned tests were executed.

## 5. Additional Discoveries

| Discovery | Details |
|-----------|---------|
| `send_command()` requires `BatteryCommand` | Calling with raw int fails with `'int' object has no attribute 'power_watts'` |
| M715 address mapping | Base-1 addresses (1087+) work for raw TCP, base-40000 (41087+) returns ILLEGAL_DATA_ADDRESS |
| `modbus_sunspec_readwrite.py` | Has batch write capability (untested) — noted for future use |
