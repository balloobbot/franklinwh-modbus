# SunSpec 700-Series Interoperability Guide

*Last Updated: 2026-05-15 18:57*

**Baseline Reference**: SunSpec DER Information Model Specification V1.2  
**Publication Date**: 2020-03-24  
**Version**: 1.2 (Chapter 7: DER Storage, Chapter 8: DER Monitoring)

## 1. Workarounds & Hardware Deviations

The FranklinWH aGate implementation contains several deviations from the SunSpec DER V1.2 standard. Our implementation compensates for these via the following software-side logic:

| SunSpec Point | aGate Deviation | Software Workaround |
| :--- | :--- | :--- |
| **M713.Sta** | **ALWAYS 0**. Battery state (Charge/Discharge) is not reported in this status register. | **DCW Polarity**: State is derived from `M714.DCW` (Positive=Discharge, Negative=Charge). |
| **M704.WSetRvrtTms**| **COSMETIC**. The hardware countdown runs but does NOT reset `WSetEna` or `WSetPct` at zero. | **Software Watchdog**: A continuous control loop must heartbeat or explicitly call `WSetEna=0`. |
| **M704.WSetPct** | **SCALING**. Uses `WMaxRtg` (1000W AC) as denominator instead of `WChaRteMaxRtg` (5000W DC). | **Denominator Override**: Scaling math uses the direction-aware nameplate rating from `M702`. |

## 2. End-to-End Orchestration Architecture

```mermaid
graph TD
    subgraph Standard_Interface_SunSpec_700 ["&nbsp;&nbsp;&nbsp; Standard Interface (SunSpec 700) &nbsp;&nbsp;&nbsp;"]
        M701["&nbsp;&nbsp;&nbsp; 701: Grid AC Reality &nbsp;&nbsp;&nbsp;"]
        M714["&nbsp;&nbsp;&nbsp; 714: Battery DC Flow &nbsp;&nbsp;&nbsp;"]
        M704["&nbsp;&nbsp;&nbsp; 704: Charging Limits &nbsp;&nbsp;&nbsp;"]
        M715["&nbsp;&nbsp;&nbsp; 715: System State Master &nbsp;&nbsp;&nbsp;"]
        M502["&nbsp;&nbsp;&nbsp; M502 &nbsp;&nbsp;&nbsp;"]
    end

    subgraph Proprietary_Interface_15500_Extensions ["&nbsp;&nbsp;&nbsp; Proprietary Interface (15500 Extensions) &nbsp;&nbsp;&nbsp;"]
        EXT_PV_AC["&nbsp;&nbsp;&nbsp; 15510: Built-in PV AC &nbsp;&nbsp;&nbsp;"]
        EXT_PV_REM["&nbsp;&nbsp;&nbsp; 15512: Remote PV aPBox &nbsp;&nbsp;&nbsp;"]
        EXT_MODE["&nbsp;&nbsp;&nbsp; 15507: Native Mode &nbsp;&nbsp;&nbsp;"]
        EXT_LOAD["&nbsp;&nbsp;&nbsp; 16000: Home Load &nbsp;&nbsp;&nbsp;"]
    end

    subgraph Physical_Hardware ["&nbsp;&nbsp;&nbsp; Physical Hardware &nbsp;&nbsp;&nbsp;"]
        GRID(("&nbsp;&nbsp;&nbsp; Utility Grid &nbsp;&nbsp;&nbsp;"))
        PV_INT["&nbsp;&nbsp;&nbsp; Built-in Solar &nbsp;&nbsp;&nbsp;"]
        PV_EXT["&nbsp;&nbsp;&nbsp; Remote aPBox Solar &nbsp;&nbsp;&nbsp;"]
        BAT["&nbsp;&nbsp;&nbsp; aPower Batteries &nbsp;&nbsp;&nbsp;"]
        LOADS["&nbsp;&nbsp;&nbsp; Home Electrical Loads &nbsp;&nbsp;&nbsp;"]
    end

    %% Standard Logic
    M715 -->|"&nbsp;&nbsp; Target State &nbsp;&nbsp;"| M704
    M704 -->|"&nbsp;&nbsp; WSetPct &nbsp;&nbsp;"| BAT
    M714 --- BAT
    M701 --- GRID
    M502 --- PV_INT
    M502 --- PV_EXT

    %% Extension Logic (Filling the Gaps)
    EXT_PV_AC -->|"&nbsp;&nbsp; Granular Yield &nbsp;&nbsp;"| M502
    EXT_PV_REM -->|"&nbsp;&nbsp; Granular Yield &nbsp;&nbsp;"| M502
    EXT_LOAD -.->|"&nbsp;&nbsp; GAP: No Standard Model &nbsp;&nbsp;"| LOADS
    EXT_MODE -->|"&nbsp;&nbsp; Sync &nbsp;&nbsp;"| M715
    EXT_LOAD -->|"&nbsp;&nbsp; Demand &nbsp;&nbsp;"| M701

    classDef standard fill:#00e5ff26,stroke:#00e5ff,stroke-width:2px;
    classDef extension fill:#ffeb3b26,stroke:#fbc02d,stroke-dasharray:5 5,stroke-width:2px;
    classDef physical fill:#7878780d,stroke:#757575,stroke-width:1px;

    class M701,M714,M704,M715,M502 standard;
    class EXT_PV_AC,EXT_PV_REM,EXT_MODE,EXT_LOAD extension;
    class GRID,PV_INT,PV_EXT,BAT,LOADS physical;
```

## 3. Key Operational Scenarios (M Interactions)

### 3.1 Solar to Home Loads / Grid
*   **Interaction**: `M502.OutWh` (Yield) vs `M701.W` (Grid Power).
*   **Orchestration**: If `M701.W` is negative (Export), solar exceeds load.
*   **Units**: Reported in Watts (W) with Scale Factor `W_SF`.

### 3.2 Battery Charge or Discharging
*   **Interaction**: `M714.DCW` (Current Flow) vs `M704.WSetPct` (Command).
*   **Orchestration**: Set `M704.WSetPct` to -X% for Charge or +X% for Discharge.
*   **Workaround**: Ignore `M713.Sta`; rely strictly on `M714.DCW` polarity.

### 3.3 Grid Import to Home Loads / Battery
*   **Interaction**: `M701.W` (Positive) + `M704.WSetPct` (Negative).
*   **Orchestration**: To charge from grid, `WSetEna` must be 1. Inverted signs (SunSpec standard) apply: Positive Grid = Import.

### 3.4 SOC and SOH Monitoring
*   **Interaction**: `M713.SoC` (State of Charge) and `M713.SoH` (State of Health).
*   **Units**: Percent (%). Scaling: `SoC_SF` (typically 0 or 1).

### 3.5 Native Mode Control
*   **Interaction**: Register `15507` (OnGridMode) vs `M715.St`.
*   **Orchestration**: Direct hardware mode switching. 
    *   `1`: Backup
    *   `2`: Self-Consumption
    *   `3`: TOU
*   **Note**: Requires installer "SPAN Modbus" unlock.

### 3.5 Home Load Monitoring
*   **Interaction**: Register `16000` (HomeLoadHighRes) vs `M701.W`.
*   **Orchestration**: Direct consumption measurement from smart sensor CTs.
*   **Precision**: Use `16000` for 1W resolution (Proprietary Extension). Standard SunSpec calculation (`Solar - Grid - Battery`) is often less precise due to quantization in `M701`.

### 3.6 System Alarms
*   **Interaction**: `M1` (Common) and `M715.Alrm` (DER Alarms).
*   **Orchestration**: Read bitfields to detect over-voltage, thermal runaway, or communication loss.
