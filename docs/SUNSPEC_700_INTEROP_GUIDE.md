# SunSpec 700-Series Interoperability Guide

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
    subgraph Standard_Interface_SunSpec_700
        M701[701: Grid AC Reality]
        M714[714: Battery DC Flow]
        M704[704: Charging Limits]
        M715[715: System State Master]
    end

    subgraph Proprietary_Interface_15500_Extensions
        EXT_PV[15502: PV DC Total]
        EXT_MODE[15507: Native Mode]
        EXT_LOAD[16000: Home Load]
    end

    subgraph Physical_Hardware
        GRID((Utility Grid))
        PV[Solar PV Arrays]
        BAT[aPower Batteries]
        LOADS[Home Electrical Loads]
    end

    %% Standard Logic
    IM715 -->|Target State| IM704
    IM704 -->|WSetPct| BAT
    IM714 --- BAT
    IM701 --- GRID

    %% Extension Logic
    EXT_PV -->|Yield Data| IM701
    EXT_MODE -->|Sync| IM715
    EXT_LOAD -->|Demand| IM701

    classDef standard fill:#f9f,stroke:#333,stroke-width:2px;
    classDef extension fill:#ffd,stroke:#333,stroke-dasharray: 5 5;
    classDef physical fill:#ddd,stroke:#333;

    class M701,M714,M704,M715 standard;
    class EXT_PV,EXT_MODE,EXT_LOAD extension;
    class GRID,PV,BAT,LOADS physical;
```

## 3. Key Operational Scenarios (IM Interactions)

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

### 3.5 System Alarms
*   **Interaction**: `M1` (Common) and `M715.Alrm` (DER Alarms).
*   **Orchestration**: Read bitfields to detect over-voltage, thermal runaway, or communication loss.
