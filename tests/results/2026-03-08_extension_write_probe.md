# Test Results — 2026-03-08 (Extension Register Write-Probe)

**Date:** 2026-03-08 17:17 AEDT  
**Device:** FranklinWH aGate X @ 192.168.0.110  
**Firmware:** V10R01B04D00

---

## Goal

Probe undocumented extension registers 15000-15039 for writable ones that could
unlock additional control capabilities (mode change, reserves, operating parameters).

## Method

1. **Read baseline** — read all 40 registers via raw Modbus TCP (unit 2)
2. **Write-back test** — write current value back to each register
3. **Persistence test** — write (value+1), sleep 0.5s, re-read, restore

## Results

### Phase 1: Baseline Read
All 40 registers readable. Values match previous scans.

### Phase 2: Write-back Test
**ALL 40 registers accepted writes at protocol level** — no Modbus errors returned.
This is the same pattern as ControllerHb (M715) — the aGate accepts writes but silently ignores them.

### Phase 3: Persistence Test

| Result | Count | Registers |
|--------|-------|-----------|
| ❌ Silently ignored | 33 | 15000-15006, 15008-15010, 15012, 15014, 15016-15021, 15023, 15026-15039 |
| ⚠️ Value changed (not to our value) | 7 | 15007, 15011, 15013, 15015, 15022, 15024, 15025 |
| ✅ Sticky (our value persisted) | **0** | None |

### Analysis of ⚠️ Registers

The 7 "changed" registers did NOT change to our written value — they changed because
they are **live measurement registers** fluctuating in real-time:

| Addr | Was | Wrote | Read | Interpretation |
|------|-----|-------|------|----------------|
| 15007 | 65171 | 65172 | 65180 | Signed: -365→-356 (power reading?) |
| 15011 | 551 | 552 | 524 | Power/current reading |
| 15013 | 65417 | 65418 | 65416 | Signed: -119→-120 (PF or small power) |
| 15015 | 4 | 5 | 0 | Counter or state |
| 15022 | 65514 | 65515 | 23 | Signed: -22→23 (AC power fluctuation!) |
| 15024 | 50010 | 50011 | 49969 | Grid frequency (~50.0Hz) |
| 15025 | 2421 | 2422 | 2418 | Grid voltage (~242.1V) |

15024 and 15025 are clearly grid frequency and voltage mirrors of M701 registers.

## Conclusion

**No unlock register found in the 15000-15039 range.**

All 40 registers:
- Accept writes at protocol level (no Modbus errors)
- Silently discard all written values
- Are read-only mirrors of SunSpec model data and live measurements

The aGate's SPAN Modbus unlock mechanism is likely:
1. An entirely different address range (not probed)
2. Controlled by the SPAN panel's network layer (not the aGate firmware)
3. A multi-register authentication handshake (not a single "unlock" register)

## Safety Verification

After probe: Battery state=IDLE, Mode=Self-Consumption, SoC=79%, Reserve=20% — no adverse effects.
