# SunSpec Orchestration & Implementation Primer

This guide explains how to orchestrate the FranklinWH aGate using the SunSpec Alliance standards. 

> [!IMPORTANT]
> This guide is a simplified primer. The **absolute source of truth** is the official [SunSpec Specification Package (Docs #12041 & 700-Series)](https://sunspec.org/about-sunspec-specifications/). We cite and follow these standards religiously.

## 1. The SunSpec Architecture

To understand SunSpec, you must distinguish between the **Transport Layer** and the **Semantic Layer**:

*   **Modbus TCP (Transport)**: The communication medium that moves raw bits across the wire. It provides the "addresses" but no inherent meaning.
*   **SunSpec (Semantic Layer)**: An interoperable Information Model that provides a standardized map for the data. It ensures that Model 704 always represents DER Control, regardless of the manufacturer.

## 2. Address Mapping Considerations

SunSpec devices typically utilize the **Preferred Base Register 40001** (Wire PDU Offset 40000). The FranklinWH aGate implementation provides two distinct "Address Zones":

*   **The Standard Zone (40000+)**: Contains the official SunSpec Models (1, 701-715). These follow the $Value \times 10^{SF}$ scale factor mathematics.
*   **The Extension Zone (15500+)**: Contains proprietary FranklinWH registers for advanced functions (e.g., native operating modes). 

**Note**: In our library, we refer to these by their **Logical Address** (e.g., 318 for `WSetEna`) while the underlying code handles the PDU offset ($+40000$) automatically.

## 3. The Standard Orchestration Pattern

Controlling a DER device requires a strict state-machine approach. Per **SunSpec Specification #12041**, control must follow an atomic multi-write procedure:

1.  **Telemetry Sync**: Read Models 713 (Battery) and 714 (Storage) to determine hardware readiness.
2.  **Pre-flight Check**: Verify `WSetEna` (318) is `0` (Local Control) and no high-priority alarms are active.
3.  **Setpoint Application**: Write the target power value to `WSetPct` (324) or `WSet` (320).
4.  **Atomic Trigger**: Transition `WSetEna` (318) to `1` (Remote Control) to activate the new setpoints.
5.  **Heartbeat Maintenance**: Continuously refresh the control state within the hardware's timeout window.
6.  **Handover**: Revert `WSetEna` to `0` to return control to the native FranklinWH cloud logic.

## 4. Understanding Non-Compliance

Because firmware implementations frequently deviate from the standard, this project maintains a formal **[Non-Compliance Assessment](./NON_COMPLIANCE_ASSESSMENT.md)**. 

When you see a command "ACK" (acknowledge) but have no physical effect, it is typically classified as **Non-Compliant Write-Ignore behavior**. In these cases, our library uses the **Software Watchdog** to ensure the system remains in a safe, predictable state.

---

### Key Resources
*   [**SunSpec Model Map**](./SUNSPEC_MODEL_MAP.md) — A complete catalog of every implemented model and its relevance to utilities vs. home automation.
*   [**SunSpec Compliance Basis**](./SUNSPEC_COMPLIANCE_BASIS.md) — The technical and legal authority for this library.
*   [**PICS Conformance Cross-Reference**](./PICS_CONFORMANCE_CROSS_REFERENCE.md) — Verified hardware behavior vs. manufacturer claims.
*   [**Non-Compliance Assessment**](./NON_COMPLIANCE_ASSESSMENT.md) — Formal record of identified hardware deviations.
