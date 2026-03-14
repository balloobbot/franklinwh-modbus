# SPAN Panel Integration — Potential Addon Module

> **Status:** PARKED — Evaluate when deployment sites have SPAN Panels  
> **Source:** [spanio/SPAN-API-Client-Docs](https://github.com/spanio/SPAN-API-Client-Docs)  
> **Evaluated:** 2026-03-15

---

## Overview

SPAN Panel is an intelligent electrical panel that monitors every circuit and manages battery islanding. Its local API (MQTT/Homie on port 8883) provides **grid-side data** that complements this library's **battery-side control**.

```
SPAN API:       Grid side → circuit-level metering, islanding, SoE
FranklinWH:     Battery side → VPP control, charge/discharge, SunSpec
```

---

## What SPAN API Exposes

| MQTT Node | Type | Properties |
|-----------|------|------------|
| **`bess`** | `energy.ebus.device.bess` | `soe` (SoC), `grid-state` (islanding) |
| **`pcs`** | `energy.ebus.device.pcs` | Power conversion system |
| `pv` | `energy.ebus.device.pv` | Solar production |
| `evse` | `energy.ebus.device.evse` | EV charger (SPAN Drive) |
| `circuit` | `energy.ebus.device.circuit` | Per-breaker W, relay control |
| `core` | `energy.ebus.device.distribution-enclosure.core` | Panel metadata |

> **No battery control path.** SPAN API is monitoring/observing only.

---

## Integration Value for FranklinWH

| Use Case | Value | How |
|----------|:-----:|-----|
| **Circuit-level demand response** | HIGH | Subscribe `circuit/#` → optimize VPP dispatch |
| **Grid-aware charging** | HIGH | Use `pv` + load circuits → charge when solar surplus |
| **SoC cross-validation** | MEDIUM | Compare `bess/soe` vs M713.SoC |
| **Independent grid status** | MEDIUM | `bess/grid-state` as backup to M701.ConnSt |
| **Peak shaving** | HIGH | Real-time circuit loads → discharge to offset peaks |

---

## Technical Integration

### Architecture
```
SPAN Panel (MQTT :8883)          FranklinWH aGate (Modbus :502)
         │                                │
         └──────────┬─────────────────────┘
                    ▼
         franklinwh-modbus library
         + span_provider.py addon
```

### Connection Requirements
- **Discovery:** mDNS (`span-{serial}.local`) or IP
- **Auth:** `POST /api/v2/auth/register` with `hopPassphrase` (physical door switch 3x press)
- **Protocol:** MQTTS on port 8883 (Homie v5 / eBus convention)
- **Topics:** `ebus/5/{serial}/bess/soe`, `ebus/5/{serial}/{circuit-id}/#`

### Potential Module Structure
```
src/franklinwh_modbus/
  addons/
    span_provider.py      # SPAN MQTT client
    span_types.py         # Circuit, BESS data classes
```

---

## Constraints

- **Personal/non-commercial use only** — commercial requires SPAN Fleet Manager license
- **SPAN Panel MAIN 32 only** (expanding to MAIN 40, MLO 48, MAIN 16, MLO 24 in H2 2026)
- **Australia availability:** Check SPAN Panel AU distribution
- **v1 REST deprecated:** Sunset 2026-12-31, use MQTT/Homie going forward
- **eBus framework** (`ebus.energy`) — open standard, worth watching for multi-vendor battery integration

---

## Compatible Batteries (via SPAN Panel)

Tesla Powerwall, Enphase IQ, LG RESU, **FranklinWH**, SolarEdge Home Battery, Generac PWRcell. SPAN exposes all as generic `bess` node — no brand-specific data.

---

*Parked: revisit when SPAN Panel presence confirmed at deployment sites.*
