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

## Mobile App Screenshots

### Before Control — Self-Consumption Mode

The aGate is operating normally in Self-Consumption mode, discharging to cover home loads.

![Before control — Self-Consumption mode, Discharging 0.6kW](images/vpp_1_before_self_consumption.png)

### During Control — VPP Mode (Charging)

After `franklinwh-modbus` sends a charge command, the app shows "VPP Mode" and the battery is charging at 5.0kW from the grid.

![During control — VPP Mode, Charging 5.0kW from grid](images/vpp_2_during_charging.png)

### During Control — VPP Mode (Standby)

Between commands or during polling, the app shows "VPP Mode" with the battery in Standby (0.0kW). The mode indicator remains as VPP Mode as long as the Modbus keep-alive is active.

![During control — VPP Mode, Standby 0.0kW](images/vpp_3_during_standby.png)

### During Control — VPP Mode (Discharging/Exporting)

When commanded to discharge, the app shows "VPP Mode" with the battery discharging at 4.9kW and exporting 4.4kW to the grid.

![During control — VPP Mode, Discharging 4.9kW, Exporting 4.4kW](images/vpp_4_during_discharging.png)

### After Control Released — Self-Consumption Restored

After calling `--stop` or `reset_control_state()`, the aGate returns to its previous mode (Self-Consumption). The VPP Mode indicator disappears.

![After control released — Self-Consumption mode restored](images/vpp_5_after_self_consumption.png)

---

## Timeline Summary

```
Self-Consumption (normal)
    ↓ franklinwh-modbus sends charge command
VPP Mode — Charging 5.0kW
    ↓ command completes / standby
VPP Mode — Standby 0.0kW
    ↓ franklinwh-modbus sends discharge command
VPP Mode — Discharging 4.9kW
    ↓ --stop / reset_control_state()
Self-Consumption (restored)
```

## Key Observations

| State | Mode Display | Battery | Grid |
|-------|-------------|---------|------|
| Before | Self-Consumption | Discharging 0.6kW | 0.0kW |
| Charge | **VPP Mode** | Charging 5.0kW | Import 5.6kW |
| Standby | **VPP Mode** | Standby 0.0kW | Import 0.6kW |
| Discharge | **VPP Mode** | Discharging 4.9kW | Export 4.4kW |
| After | Self-Consumption | Discharging 0.6kW | 0.0kW |

---

## Image Placement

Save the mobile app screenshots to this directory as:
```
docs/images/vpp_1_before_self_consumption.png
docs/images/vpp_2_during_charging.png
docs/images/vpp_3_during_standby.png
docs/images/vpp_4_during_discharging.png
docs/images/vpp_5_after_self_consumption.png
```

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
