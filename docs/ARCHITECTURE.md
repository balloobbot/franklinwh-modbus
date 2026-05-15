# FranklinWH System Architecture

*Last Updated: 2026-05-15 18:59*

This document clarifies the AC-coupled vs DC-coupled architecture of FranklinWH systems.

## Overview

FranklinWH uses different coupling architectures depending on the product line:

| Product | Coupling | Solar Input | Battery Coupling | Region |
|---------|----------|-------------|------------------|--------|
| **aGate X** | **AC-Coupled** | 2x 63A AC circuits | AC (internal inverter) | AU/US |
| **aPower S** | **Hybrid** | 4x MPPT DC + AC inputs | DC | US |
| **aPower 2** | **DC-Coupled** | MPPT DC inputs | DC | US |
| **aPower X** | **DC-Coupled** | MPPT DC inputs | DC | US |

---

## aGate X (AC-Coupled) - Most Common

### Architecture Diagram
```
Solar Panels → AC Solar Input (63A) →┐
                                     ├→ aGate Inverter → AC Output → Home/Grid
Battery ↔ AC Battery Port ↔ Inverter ┘
```

### Key Characteristics
- **Solar**: Connects via **AC inputs** (not DC MPPT)
- **Battery**: AC-coupled (inverter built into aGate)
- **Remote Solar**: Supported via aPbox or aHub accessories
- **Monitoring**: Model 502 shows solar AC output, Model 714 shows battery DC power

### Why "AC-Coupled"?
1. Solar panels connect to AC inputs (like a regular appliance)
2. Battery stores AC power (converted by internal inverter)
3. No high-voltage DC wiring to battery

### SunSpec Models for aGate X
| Model | Purpose | Notes |
|-------|---------|-------|
| 701 | Grid/AC measurements | Primary AC monitoring |
| 714 | Battery DC status | DC power, voltage, current |
| 502 | Solar AC output | AC-coupled solar production |

---

## aPower S (Hybrid)

### Architecture Diagram
```
Solar Panels → DC MPPT (4x) → DC Bus → Battery
                          ↓
                    Inverter → AC Output → Home/Grid
                          ↑
Solar Panels → AC Input ──┘
```

### Key Characteristics
- **Solar**: BOTH DC MPPT (4x) AND AC inputs
- **Battery**: DC-coupled to DC bus
- **Flexibility**: Can accept both DC and AC solar sources

---

## Common Misconceptions

### "PV" in DERMode Means DC-Coupled? ❌

The SunSpec DERMode register (Model 701) bit 0 is labeled "PV" but this refers to **solar generation**, not DC-coupling. On the aGate X:
- Bit 0 = Solar active (via AC inputs)
- Bit 1 = Battery active
- The "PV" label is misleading for AC-coupled systems

### Model 502 Solar Power is DC? ❌

Model 502 (Solar AC Output) shows **AC power** even though the model name suggests DC. For aGate X:
- Solar panels → AC inputs → Inverter → Model 502 shows AC output
- This is different from MPPT DC measurements on DC-coupled systems

---

## Power Flow Summary (aGate X)

```
                    ┌─────────────────┐
    Solar (AC) ─────┤→   aGate X      ├──→ AC Output → Home
    (2x 63A)        │  (Inverter)     │
                    │                 │
    Battery (AC) ←──┤←── (AC Port)    ├──→ Grid
                    └─────────────────┘
```

### Power Equation (AC-Coupled)
```
Home Load = Solar AC + Battery Discharge - Grid Export
```

Note: All values are AC power measurements. Battery DC power (Model 714) is separate from AC power flow.

---

## Accessories

### aPbox (Remote Solar Receiver)
- **Purpose**: Add remote solar panels to aGate X
- **Connection**: Wireless or wired to aGate
- **Architecture**: Still AC-coupled (aPbox has its own inverter)

### aHub (Solar Aggregator)
- **Purpose**: Connect multiple solar arrays to aPower S
- **Connection**: DC or AC depending on configuration
- **Architecture**: Maintains DC-coupling for aPower S

### Smart Circuits
- **Purpose**: Load management and backup circuits
- **Connection**: AC panel integration

### Generator Module
- **Purpose**: Backup generator integration
- **Connection**: AC input to aGate

---

## Status Display Corrections

### Before (Incorrect)
```
DER Type:          PV+Battery (Hybrid Inverter)
```
This implied DC-coupled hybrid system.

### After (Correct)
```
DER Type:          Battery+Solar (AC-Coupled)
Architecture:      AC-Coupled (aGate X)
Solar Inputs:      2x 63A AC circuits (+ remote via aPbox/aHub)
```

---

## Implications for Control

### AC-Coupled (aGate X)
- **Advantage**: Safer installation (no HV DC)
- **Efficiency**: Double conversion (DC→AC→DC→AC for battery storage)
- **Monitoring**: Model 714 shows battery DC, Model 502 shows solar AC
- **Control**: WSetPct controls battery AC power

### DC-Coupled (aPower S/2)
- **Advantage**: Higher efficiency (single conversion)
- **Installation**: Requires HV DC wiring
- **Monitoring**: Model 714 shows battery DC, MPPT shows solar DC
- **Control**: WSetPct controls battery AC power

---

## References

- [FranklinWH aGate X Datasheet](https://franklinwh.com)
- [FranklinWH aPower S Datasheet](https://franklinwh.com)
- SunSpec Alliance DER Model Specification

