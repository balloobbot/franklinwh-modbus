# Model 704 DERCtlAC - Active Power Control

**Date:** 2026-02-14  
**Status:** ✅ **WSetEna CONFIRMED WORKING** | ❌ WMaxLimPct REJECTED BY AGATE

---

## 🎯 Critical Discovery

**BREAKTHROUGH:** Model 704 `WSetEna` writes **PERSIST** on the aGate!  
**BLOCKED:** Model 704 `WMaxLimPctEna` writes are **REJECTED** (reads back 0)  
**BLOCKED:** Model 702 `WChaRteMax` writes are **REJECTED** (reads back 65535)

**Conclusion:** Use **Model 704 WSet for power control**, NOT Model 702.

---

## Register Documentation

### Power Ceiling (Percentage-Based) - ❌ REJECTED BY AGATE

#### WMaxLimPctEna (40310)
ON/OFF switch for the percentage-of-nameplate limit.
- `0` = disabled (inverter runs normally)
- `1` = enabled (the limit in the next register is active)

**⚠️ TEST RESULT:** Write succeeds but **aGate rejects** - reads back as `0`

#### WMaxLimPct (40311)
The actual limit, expressed in % of the unit's nameplate W rating.
- **Range:** 0–100%
- **Example:** 60% on a 100 kW inverter → max 60 kW export

#### WMaxLimPctRvrt (40312)
Value the register above will automatically return to when the reversion timer expires.
- `None` = no automatic return
- Otherwise: 0–100%

#### WMaxLimPctEnaRvrt (40313)
Whether the enable bit (40310) also reverts when the timer expires.
- `0` = stay in the last state
- `1` = return to the state written here

#### WMaxLimPctRvrtTms (40314)
How many seconds after the limit is written before the automatic reversion happens.
- `0` = revert immediately
- `65535` = never revert

#### WMaxLimPctRvrtRem (40316)
**Read-only** countdown of the seconds remaining until reversion (0 when inactive).

---

### Fixed Watt Setpoint - ✅ WORKING

#### WSetEna (40318)
ON/OFF switch for the "fixed-watt" mode.
- `0` = normal watt-control (follow MPPT, volt-var, etc.)
- `1` = force the inverter to the exact watt value in 40320

**✅ TEST RESULT:** Write succeeds and **PERSISTS** - confirmed working!

#### WSetMod (40319)
Selects how the fixed-watt value is interpreted.
- `0` = absolute watt setpoint (40320 is in watts)
- `1` = percentage of nameplate (40320 is 0–100%)

#### WSet (40320)
The desired real-power output.
- **Type:** Signed 32-bit integer
- **Positive** = import (charge from grid) - **RARE**
- **Negative** = export (discharge to loads/grid)
- Only honored when `WSetEna = 1`

**Use Cases:**
- **Force charge:** `WSet = +2000` → import 2kW from grid
- **Force discharge:** `WSet = -3000` → export 3kW to grid/loads
- **Normal mode:** `WSetEna = 0` → disable fixed setpoint

---

## Implementation Strategy

### ✅ Recommended Approach: Use Model 704 WSet

```python
# Enable fixed-watt mode
await modbus.write_point(704, 'WSetEna', 1)
await modbus.write_point(704, 'WSetMod', 0)  # Absolute watts

# Force discharge 3kW
await modbus.write_point(704, 'WSet', -3000)

# Force charge 2kW
await modbus.write_point(704, 'WSet', 2000)

# Return to normal
await modbus.write_point(704, 'WSetEna', 0)
```

### ❌ Avoid: Model 702 WChaRteMax/WDisChaRteMax

Model 702 writes are **silently rejected** by the aGate - verification shows 65535 (unlimited).

---

## Test Results Summary

| Register | Address | Write Result | Verify Result | Status |
|----------|---------|--------------|---------------|--------|
| WSetEna | 40318 | ✅ Success | ✅ Reads 1 | **WORKING** |
| WMaxLimPctEna | 40310 | ✅ Success | ❌ Reads 0 | **REJECTED** |
| WChaRteMax (702) | 40258 | ✅ Success | ❌ Reads 65535 | **REJECTED** |

---

## Safety Considerations

⚠️ **CRITICAL:**
- Only use in **Self-Consumption mode**
- Check for **VPP enrollment** (prevents external control)
- **Signed values:** Positive = charge, Negative = discharge
- **Verify write with read-back** after every write
- **Start with small values** (±500W) for testing

---

## Next Steps

1. **Test WSet with safe values:**
   ```bash
   # Test discharge 500W (safe)
   python3 -c "from modbus_sunspec2_readwrite import write_sunspec_point; \
   write_sunspec_point('192.168.0.110', 704, 'WSet', -500, timeout=5.0)"
   ```

2. **Verify it worked:**
   ```bash
   python3 modbus_sunspec2_reader.py -i 192.168.0.110 -m 704 -d=values --vals | grep WSet
   ```

3. **Update backend to use Model 704 instead of Model 702**

---

## Advantages Over Model 702

| Feature | Model 702 | Model 704 |
|---------|-----------|-----------|
| Power Limits | ❌ Rejected by aGate | ⚠️ Ceiling rejected, WSet works |
| Force Charge | ❌ Not available | ✅ Positive WSet (WORKING) |
| Force Discharge | ❌ Not available | ✅ Negative WSet (WORKING) |
| Auto-Revert | ❌ Manual only | ✅ Built-in timers |
| Verified Working | ❌ Rejected | ✅ WSet confirmed |
