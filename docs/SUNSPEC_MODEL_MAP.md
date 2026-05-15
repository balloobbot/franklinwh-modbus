# SunSpec Model Map & Stakeholder Reference

This document maps the complete SunSpec Information Model as implemented by the FranklinWH aGate (`Firmware V10R01B04D00`). It identifies which models are critical for specific use cases, ranging from Home Automation to Utility Dispatch (VPP).

> [!IMPORTANT]
> For the raw, line-by-line register dump from the latest hardware scan, refer to the **[SunSpec Device Snapshot (Ground Truth)](./SUNSPEC_DEVICE_SNAPSHOT.md)**.

## 1. Identification & Baseline (System Foundation)
*Primary Stakeholders: Support Engineers, Asset Managers*

| Model | Name | Key Data Points | Utility Interest | HA Interest |
|:---|:---|:---|:---:|:---:|
| **1** | Common | Manufacturer, Model, Serial No. | ✅ | ✅ |
| **11** | Ethernet | IP Address, MAC Address | ⚠️ | ✅ |
| **12** | IPv4 | Network Configuration | — | ✅ |
| **701** | DER Info | Device Type, Nominal Ratings | ✅ | ⚠️ |

## 2. Solar & PV Infrastructure (Energy Generation)
*Primary Stakeholders: Solar Installers, Grid Operators*

| Model | Name | Key Data Points | Utility Interest | HA Interest |
|:---|:---|:---|:---:|:---:|
| **703** | Enterance Info | Solar Flag, Grid Flag | ✅ | ✅ |
| **705** | PV Conn | PV Status, Connection state | ✅ | — |
| **706** | PV AC Meas | AC-coupled Solar Power (Watts) | ✅ | ✅ |
| **709** | PV AC Meas 3ph | Detailed Phase Measurements | ✅ | ⚠️ |
| **711** | PV DC Meas | aPBox DC inputs (if applicable) | ✅ | ⚠️ |
| **712** | PV DC Meas 3ph | Advanced DC Telemetry | ⚠️ | — |

## 3. Battery & Storage System (The Core Asset)
*Primary Stakeholders: Homeowners, VPP Operators*

| Model | Name | Key Data Points | Utility Interest | HA Interest |
|:---|:---|:---|:---:|:---:|
| **702** | DER Capacity | Max Charge/Discharge Ratings | ✅ | — |
| **713** | Storage | State of Charge (SoC), Battery State | ✅ | ✅ |
| **714** | Storage AC Meas | Power Flow (Watts), Energy (Wh) | ✅ | ✅ |

## 4. DER Control & Utility Dispatch (Orchestration)
*Primary Stakeholders: Electricity Utilities, VPP Aggregators*

| Model | Name | Key Data Points | Utility Interest | HA Interest |
|:---|:---|:---|:---:|:---:|
| **704** | DER AC Ctl | **WSetPct (Remote Control)** | ✅ ✅ | ⚠️ |
| **707** | DER Volt-Var | Reactive Power Management | ✅ | — |
| **708** | DER Volt-Watt | Frequency/Voltage Response | ✅ | — |
| **710** | DER Heartbeat | Safety Watchdog Registers | ✅ | ✅ |
| **715** | DER Lifecycle | Alarm Reset, Operation Control | ✅ | ⚠️ |

## 5. FranklinWH Proprietary Extensions (Local Management)
*Primary Stakeholders: Home Automation (Home Assistant), Users*

These registers reside in the `15000–16500` range and are used for vendor-specific logic, including the "SPAN" integration.

> [!IMPORTANT]
> For the complete discovered register map and SunSpec correlations, refer to the **[FranklinWH Proprietary Extensions Manifest](./FRANKLINWH_EXTENSIONS_MANIFEST.md)**.

| Addr Range | Group | Key Data Points | Utility Interest | HA Interest |
|:---|:---|:---|:---:|:---:|
| **15507** | Mode | Native Operating Mode (TOU/Self) | ⚠️ | ✅ ✅ |
| **15508** | Backup | Backup Reserve Percentage | — | ✅ ✅ |
| **15510+** | Status | PV Energy & Home Load Telemetry | — | ✅ |

---

### 💡 Stakeholder Summary

*   **Electricity Utilities**: Primarily focused on **Models 704 and 702**. They care about how much power they can "buy" from your battery during a peak event and the safe triggers to enable it.
*   **Home Automation (HA)**: Primarily focused on **Models 713, 714, and the 15500 Extensions**. HA users care about seeing their SoC in a dashboard and adjusting their "Backup Reserve" or "Operating Mode" based on solar forecasts.
*   **Developers**: Use **Model 1** for auto-discovery and **Model 710** to ensure the software-hardware link remains healthy during active orchestration.
