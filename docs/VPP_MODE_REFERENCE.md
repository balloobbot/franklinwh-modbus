# VPP Mode — Visual Reference

## What is VPP Mode?

When any remote client takes direct control of the FranklinWH aGate — whether via **Modbus TCP** (this library) or the **FranklinWH Cloud API** (used by VPP providers) — the mobile app displays the operating mode as **"VPP Mode"** (Virtual Power Plant).

This is a built-in FranklinWH indicator that confirms external control is active. It applies to:

- `franklinwh-modbus` library (Modbus TCP direct control)
- FranklinWH Cloud API for VPP providers
- Any third-party integration using direct Modbus register control
- Polling/keep-alive connections that maintain active control

### Network Topology & Latency

The mobile app does **not** connect directly to the aGate — it polls via the FranklinWH Cloud API. This means there is inherent latency between a Modbus command and the app reflecting the change:

```
Modbus Client (this library)
    ↓  LAN (WiFi or Ethernet) — ~1-5ms
aGate (local)
    ↓  WiFi/LAN → Internet — variable
FranklinWH Cloud API
    ↓  Internet → 4G/WiFi — variable
FranklinWH Mobile App
```

The mobile app polls the Cloud API frequently, but the round-trip latency can be significant. **Don't rely on the mobile app for real-time feedback** — use the library's direct Modbus reads or the CLI `--status` command instead.

> **Note:** Only one aGate is displayed at a time in the mobile app. The VPP Mode indicator appears for the currently selected aGate.

---

## Mobile App — VPP Mode Lifecycle

The diagrams below show what the FranklinWH mobile app displays at each stage of Modbus control.

```mermaid
stateDiagram-v2
    [*] --> SelfConsumption: Normal operation
    SelfConsumption --> VPPCharging: CLI --charge 5000
    VPPCharging --> VPPStandby: CLI --standby
    VPPStandby --> VPPDischarging: CLI --discharge 5000
    VPPDischarging --> SelfConsumption: CLI --stop

    state SelfConsumption {
        direction LR
        note right of SelfConsumption: Mode: Self-Consumption\nBattery: Discharging 0.6kW\nGrid: 0.0kW (balanced)
    }
    state VPPCharging {
        direction LR
        note right of VPPCharging: Mode: VPP Mode ⚡\nBattery: Charging 5.0kW\nGrid: Importing 5.6kW
    }
    state VPPStandby {
        direction LR
        note right of VPPStandby: Mode: VPP Mode ⏸️\nBattery: Standby 0.0kW\nGrid: Importing 0.6kW
    }
    state VPPDischarging {
        direction LR
        note right of VPPDischarging: Mode: VPP Mode 🔋\nBattery: Discharging 4.9kW\nGrid: Exporting 4.4kW
    }
```

### State Details

#### 1. Before Control — Self-Consumption Mode
The aGate operates normally in Self-Consumption mode, discharging to cover home loads.

!!! info "Mobile App Display"
    **Mode:** Self-Consumption · **Battery:** Discharging 0.6kW · **Grid:** 0.0kW

#### 2. During Control — VPP Mode (Charging)
After `franklinwh-modbus` sends a charge command, the app shows "VPP Mode" and the battery charges from the grid.

!!! example "Mobile App Display"
    **Mode:** VPP Mode · **Battery:** Charging 5.0kW · **Grid:** Importing 5.6kW

#### 3. During Control — VPP Mode (Standby)
Between commands, the app shows "VPP Mode" with the battery idle. The VPP indicator remains as long as Modbus control is active.

!!! example "Mobile App Display"
    **Mode:** VPP Mode · **Battery:** Standby 0.0kW · **Grid:** Importing 0.6kW

#### 4. During Control — VPP Mode (Discharging/Exporting)
When commanded to discharge, the battery discharges and excess power exports to the grid.

!!! example "Mobile App Display"
    **Mode:** VPP Mode · **Battery:** Discharging 4.9kW · **Grid:** Exporting 4.4kW

#### 5. After Control Released — Self-Consumption Restored
After `--stop` or `reset_control_state()`, the aGate returns to its previous mode. The VPP Mode indicator disappears.

!!! success "Mobile App Display"
    **Mode:** Self-Consumption · **Battery:** Discharging 0.6kW · **Grid:** 0.0kW

---

## VPP Capability Summary (PICS Conformance — 2026-03-13)

```
WHAT WORKS:    Active power dispatch via WSet/WSetPct.
               Accepts any value — software MUST clamp to valid range.
WHAT DOESN'T:  Reactive power (all paths exhausted, final).
               PF control. Curtailment ceiling. Hardware reversion.
               Heartbeat. Input validation.
SAFETY (x2):  1. Hardware dead-man is cosmetic — no self-recovery.
              2. No input validation — software is range enforcement.
              Both must be addressed before unattended deployment.
```

### Register Functional Status

| Register | Status | Notes |
|----------|:------:|-------|
| WSetEna (318) | ✅ | VPP enable — works |
| WSet (320) | ✅ | Power setpoint — no clamping! |
| WSetPct (324) | ✅ | Percentage setpoint — no clamping! |
| WSetRvrtTms (327) | ⚠️ | Countdown cosmetic — **does not revert** |
| WMaxLimPctEna (310) | ❌ | Silently discards writes |
| VarSetEna (331) | ❌ | Silently discards writes |
| ControllerHb (1092) | ❌ | Silently discards writes |
| PFWInjEna (298) | ⚠️ | Writable but gates nothing |

**Full Details:** [`PICS_CONFORMANCE_CROSS_REFERENCE.md`](./PICS_CONFORMANCE_CROSS_REFERENCE.md)
