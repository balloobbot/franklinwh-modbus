# SunSpec 700-Series Interoperability Guide

This document defines how the FranklinWH aGate orchestrates complex energy use cases by interlinking multiple SunSpec Alliance Information Models (IM). 

## 1. Use Case to Model Mapping

| Use Case | Primary Model(s) | Role |
| :--- | :--- | :--- |
| **Islanding / Grid State** | **IM 701** | Monitors `ConnSt` to detect Utility Outage vs. Connected states. |
| **Solar Harvesting** | **IM 502** | Authoritative for PV DC generation and module-level health. |
| **Battery Management** | **IM 713 / 714** | `SoC`, `SoH`, and real-time DC power flow. |
| **Active Power Control** | **IM 704 / 715** | Orchestrates charging/discharging limits and DER operational modes. |
| **System Diagnostics** | **IM 1 / 715** | Aggregates `Alrm` bitfields and `St` (Status) enumerations. |

## 2. End-to-End Orchestration Architecture

This diagram illustrates the relationship between the Public Standard (SunSpec) and Private Manufacturer (15500 Extensions) layers.

```mermaid
graph TD
    subgraph Standard_Interface_SunSpec_700
        IM701[701: Grid AC Reality]
        IM714[714: Battery DC Flow]
        IM704[704: Charging Limits]
        IM715[715: System State Master]
    end

    subgraph Proprietary_Interface_15500_Extensions
        EXT_PV[Local PV Port Relays]
        EXT_AP[aPbox Link Status]
        EXT_BMS[Unit-Level Diagnostics]
    end

    subgraph Physical_Hardware
        GRID((Utility Grid))
        PV[Solar PV Arrays]
        BAT[aPower Batteries]
        LOADS[Home Electrical Loads]
    end

    %% Standard Logic
    IM715 -->|Target State| IM704
    IM704 -->|Current/Watt Limits| BAT
    IM714 --- BAT
    IM701 --- GRID

    %% Extension Logic
    EXT_PV -->|Gatekeeper| PV
    EXT_AP -->|Data Integrity| PV
    EXT_BMS --- BAT

    %% Inter-Layer Dependency
    EXT_PV -.->|If Relay Open| IM701
    EXT_AP -.->|If Link Down| IM701
    IM701 --- LOADS
    IM714 --- LOADS

    classDef standard fill:#f9f,stroke:#333,stroke-width:2px;
    classDef extension fill:#ffd,stroke:#333,stroke-dasharray: 5 5;
    classDef physical fill:#ddd,stroke:#333;

    class IM701,IM714,IM704,IM715 standard;
    class EXT_PV,EXT_AP,EXT_BMS extension;
    class GRID,PV,BAT,LOADS physical;
```

## 3. Key Operational Scenarios

### 3.1 Solar Sponge (Charge from Excess PV)
- **Monitoring**: Read `IM 502` (PV Watts) and `IM 701` (Grid Watts).
- **Logic**: If `IM 701` W > 0 (Exporting), increase charge limit in `IM 704`.
- **Validation**: Confirm `IM 714` (Battery DC) shows increasing negative Watts (Charging).

---
**Baseline Reference**: SunSpec DER Information Model Specification V1.2
**Implementation Context**: FranklinWH aGate Firmware V10R01+
