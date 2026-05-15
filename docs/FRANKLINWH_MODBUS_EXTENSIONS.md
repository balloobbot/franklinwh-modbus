# FranklinWH Modbus Extensions & Gaps

While FranklinWH adheres to the SunSpec 700-series standards for grid interoperability, the physical architecture of the aGate requires proprietary extensions to manage manufacturer-specific hardware features.

## 1. The Manufacturer Extension Zone (15500+)

Registers in the **15500–15600 range** are proprietary. They provide granular access to hardware actuators and sensors that fall outside the scope of the SunSpec DER Information Model.

### 1.1 Rationale for Extensions
SunSpec models are "Resource-Centric" (e.g., *The Battery*). FranklinWH extensions are "Port-Centric" (e.g., *The L1 Solar Input Relay*). We use these extensions to diagnose *why* a SunSpec model might be reporting a specific state.

## 2. Implementation Scope

### 2.1 Implemented Features (Modbus + SunSpec)
- **Remote Solar (aPbox)**: Integrated into `IM 502` for telemetry, with link-state diagnostics in the `15500` range.
- **Local PV Ports**: Status of the physical AC-coupled ports on the aGate bus.
- **Battery DC Interconnects**: Granular power flow between multiple aPower units.

### 2.2 Unimplemented Features (Cloud-Only / Out of Scope)
The following features are **NOT** currently exposed via the Modbus TCP interface and must be managed via the FranklinWH Cloud API or App:
- **Smart Circuits**: Automated load shedding is restricted to prevent relay fatigue via Modbus loops.
- **Generator Input**: Safety-critical generator handshakes are managed by the internal firmware only.
- **V2L (Vehicle-to-Load)**: Complex vehicle communication is not mirrored in the register map.
- **aPower S MPPTs**: Direct MPPT-level telemetry is encapsulated within the aPower's internal BMS; only aggregate DC flow (IM 714) is exposed.

## 3. Best Practices for Developers
Developers should always prioritize the **SunSpec 700-series** for power orchestration and only "fall back" to the **15500 range** for manufacturer-specific diagnostics or hardware-level relay verification.
