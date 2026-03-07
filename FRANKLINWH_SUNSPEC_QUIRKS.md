# FranklinWH aGate SunSpec Implementation Quirks

Documenting non-standard behaviors, missing registers, and implementation-specific issues discovered during development.

---

## Model 714 - Battery DC Measurements

### DCA (DC Current) Register Not Populated
**Issue:** The DCA register in Model 714 returns 0 or is not implemented.

**Standard SunSpec Model 714 Fields:**
- `DCW` - DC Power (W) ✅ **Working**
- `DCV` - DC Voltage (V) ✅ **Working** 
- `DCA` - DC Current (A) ❌ **Not populated (returns 0)**
- `Tmp` - Battery Temperature (°C) ✅ **Working**

**Workaround:** Calculate current from Power/Voltage:
```python
dc_current = dc_power / dc_voltage  # Ohm's Law: I = P/V
```

**Code Location:** `src/franklinwh/monitor.py:_read_model_714()`

**See Also:** `SUNSPEC_TRACEABILITY.md` for complete Model 714 register mapping

---

## Model 701 - Inverter Measurements

### TmpAmb and TmpCab Implementation
**Status:** ✅ **Working as of aGate firmware**

FranklinWH aGate X implements these temperature registers:
- `TmpAmb` (40105) - Ambient temperature
- `TmpCab` (40106) - Cabinet temperature

Earlier firmware versions may not expose these.

---

## Extension Registers (15500-15517)

FranklinWH provides proprietary extension registers beyond standard SunSpec:

| Address | Register | Status | Notes |
|---------|----------|--------|-------|
| 15502-15505 | Solar breakdown | ✅ Working | PV Total, Proximal, Remote 1/2 |
| 15506 | Home Load | ✅ Working | Active load in W |
| 15507 | Operating Mode | ✅ Working | 1=Emergency, 2=Self-Consumption, 3=TOU |
| 15508-15509 | SOC Reserve | ✅ Working | Self/TOU reserve % |
| 15516 | Cabinet Temp | ⚠️ Verify | May duplicate Model 701 |
| 15517 | Ambient Temp | ⚠️ Verify | May duplicate Model 701 |

See: `franklinwh_modbus_extensions.md` for full list.

---

## Model 704 - Battery Control

### WSet vs WSetPct Sign Convention
**Issue:** Hardware uses inverted sign convention for WSetPct.

| Parameter | Software Convention | Hardware Convention |
|-----------|---------------------|---------------------|
| `WSet` | Positive=Charge | Positive=Charge |
| `WSetPct` | Positive=Charge | **Negative=Charge** |

**Workaround:** Always invert WSetPct value when writing:
```python
m704.WSetPct.value = -pct_raw  # Invert for hardware
```

---

## General Notes

- **Scale Factors:** Always read SF registers dynamically - they can change
- **Model Discovery:** aGate implements models 1, 11, 12, 502, 701, 714, 715, 802
- **Write Sequencing:** Model 704 requires specific write sequence (STOP → CONFIG → ENABLE → VERIFY)

---

*Last Updated: 2026-03-01*
*Device Tested: FranklinWH aGate X (SN: 10060006A02F24170091)*
