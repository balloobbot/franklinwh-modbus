# CLI Command Reference

> **Live output captured:** 2026-03-22 19:25–19:28 AEDT  
> **Device:** aGate X (FW V10R01B04D00, SoC 77%, evening, no solar)  
> **Connection:** WiFi to 192.168.0.110:502

---

## Quick Reference

```bash
CLI="python3 tools/franklinwh_cli.py -i YOUR_AGATE_IP"

$CLI --status                    # Compact status (default)
$CLI --status --verbose          # Full verbose status with debug
$CLI --charge 3000               # Charge battery at 3000W
$CLI --discharge 2000            # Discharge battery at 2000W
$CLI --charge 0                  # Force standby (battery idle, grid powers home)
$CLI --stop                      # Release control → aGate native mode resumes
$CLI --healthcheck               # System health check
$CLI --monitor                   # Interactive TUI dashboard
```

---

## 1. Status — Idle (aGate Native Mode)

Battery discharging 600W to serve 565W home load — normal Self-Consumption behavior.

```
  ⚡ FranklinWH aGate | SoC: 77% | Self-Consumption | Reserve: 12%
  ──────────────────────────────────────────────────────
    Solar:       0W idle          Battery: ↑ DISCHARGING 600W
    Home:      565W consuming     Grid:    ~0W (Grid Following)
  ──────────────────────────────────────────────────────
    LocRemCtl: Local           Available: 10.5/13.6 kWh
    Derived:   Local (aGate, Self-Consumption)
```

**Key observations:**
- `Derived: Local` — aGate is controlling the battery natively
- `Grid: ~0W (Grid Following)` — grid balanced, aGate managing load
- Battery discharges just enough to cover home load (self-consumption)

---

## 2. Charge at 3000W

```bash
$CLI --charge 3000
```

**Pre-command state assessment:**
```
  CURRENT SYSTEM STATE
  Battery:    SoC: 77.0% | Target: 100.0% | ETA: +36min
  Activity:   DISCHARGING (600W, aGate native)
  Home Load:  558W
  Grid:       -2W (balanced)
  WSetEna:    0
  OnGridMode: Self-Consumption

Result: SUCCESS - Command Sent: 3000.0W (-60.0% of 5000W)
✅ Command will PERSIST until you run --stop
```

**Status during charge (30s later):**
```
  ⚡ FranklinWH aGate | SoC: 77% | Self-Consumption | Reserve: 12%
  ──────────────────────────────────────────────────────
    Solar:       0W idle          Battery: ↓ CHARGING 3000W
    Home:      582W consuming     Grid:    ← 3587W importing
  ──────────────────────────────────────────────────────
    LocRemCtl: Local           Available: 10.5/13.6 kWh
    Derived:   Remote (Modbus WSetPct=-60.0%)
```

**Key observations:**
- `Derived: Remote (Modbus WSetPct=-60.0%)` — Modbus has taken control
- Grid imports 3587W to charge battery (3000W) + serve home (582W)
- `LocRemCtl: Local` — aGate SunSpec register still reports Local (LocRemCtl Paradox)

---

## 3. Stop (Release Control)

```bash
$CLI --stop
```

```
Resetting control state to idle...
Before reset: WSetEna=1, WSetPct=-600, WSet=0
✓ Reset successful: WSetEna=0, WSetPct=0
✓ Control released
```

aGate immediately resumes native Self-Consumption mode.

---

## 4. Discharge at 2000W

```bash
$CLI --discharge 2000
```

```
Result: SUCCESS - Command Sent: -2000.0W (40.0% of 5000W)
✅ Command will PERSIST until you run --stop
```

**Status during discharge:**
```
  ⚡ FranklinWH aGate | SoC: 77% | Self-Consumption | Reserve: 12%
  ──────────────────────────────────────────────────────
    Solar:       0W idle          Battery: ↑ DISCHARGING 2000W
    Home:      540W consuming     Grid:    → 1469W exporting
  ──────────────────────────────────────────────────────
    LocRemCtl: Local           Available: 10.5/13.6 kWh
    Derived:   Remote (Modbus WSetPct=40.0%)
```

**Key observations:**
- Battery discharges 2000W → 540W powers home, 1469W **exported to grid**
- This is a VPP dispatch scenario — excess power feeds the grid

---

## 5. Standby (Force Battery Idle)

```bash
$CLI --charge 0
```

Forces `WSetPct=0` — battery neither charges nor discharges. Grid must supply all home load.

**Status during standby:**
```
  ⚡ FranklinWH aGate | SoC: 77% | Self-Consumption | Reserve: 12%
  ──────────────────────────────────────────────────────
    Solar:       0W idle          Battery: IDLE
    Home:      551W consuming     Grid:    ← 575W importing
  ──────────────────────────────────────────────────────
    LocRemCtl: Local           Available: 10.5/13.6 kWh
    Derived:   Remote (Modbus WSetPct=0.0%)
```

**Key observations:**
- Battery is **IDLE** — neither charging nor discharging
- Grid imports **575W** to power home loads entirely
- `Derived: Remote (Modbus WSetPct=0.0%)` — Modbus still has control, commanding zero power
- This is useful for TOU strategies: hold battery during off-peak, discharge during peak

---

## 6. Healthcheck

```bash
$CLI --healthcheck
```

```
  HEALTH CHECK: HEALTHY

  DEVICE:
    Manufacturer: FranklinWH Technologies Co., Ltd
    Model:        aGate X
    Serial:       10060006A02F24170091
    Firmware:     V10R01B04D00

  Checks:
    ✓ connection: OK
    ✓ model_704: OK
    ✓ model_713: OK
    ✓ model_701: OK
    ✓ zombie_state: OK (not in zombie state)
    soc: 77.0
    ✓ soc_safe: OK
    grid_voltage: 241.8
    grid_frequency: 50.0
    ac_type: Single-Phase (230V Nominal)
    grid_connection: Connected
    grid_mode: Grid Following
    inverter_state: Standby
    ongrid_mode_name: Self-Consumption
    self_reserve_pct: 12
    ℹ extension_readonly: Ongrid Mode, Self Reserve, Tou Reserve

  Recommendations:
    • ℹ Extension registers read-only (requires installer unlock)
```

---

## Command Lifecycle Summary

```
  ┌─────────┐    --charge N    ┌──────────┐    --stop    ┌─────────┐
  │  IDLE   │ ───────────────→ │ CHARGING │ ──────────→  │  IDLE   │
  │ (aGate) │    --discharge N │          │              │ (aGate) │
  │ Local   │ ───────────────→ │DISCHARGING│──────────→  │ Local   │
  │         │    --charge 0    │          │              │         │
  │         │ ───────────────→ │ STANDBY  │ ──────────→  │         │
  └─────────┘                  └──────────┘              └─────────┘
   Derived:                     Derived:                  Derived:
   Local (aGate,                Remote (Modbus            Local (aGate,
   Self-Consumption)            WSetPct=X%)               Self-Consumption)
```

> [!WARNING]
> **Commands persist indefinitely.** The aGate has no hardware timeout (PICS Issue 4). Always use `--stop` to release control, or `--revert N` for automatic software timeout.

> [!CAUTION]
> **WiFi can cause orphaned control.** During this test, `--stop` timed out due to WiFi packet loss, leaving the aGate in Remote Control. The library detected this on next connect (`Active VPP state detected: WSetEna=1`). Use `--stop` again or the library will auto-release with `auto_release_orphan=True`.

---

## Virtual Modes (Not Included)

> [!IMPORTANT]
> **Virtual modes (`--mode self_consumption`, `--mode peak_shave`, etc.) are not covered in this reference.**
>
> These modes use software-calculated power targets within Remote Control (`WSetEna=1`). They are **experimental** and not properly implemented — the aGate's native modes (Self-Consumption, TOU, Emergency Backup) handle these scenarios better.
>
> **Future:** Virtual modes may be removed entirely, pending FranklinWH enabling:
> 1. **LocRemCtl write access** — allowing proper Local/Remote handoff per SunSpec spec
> 2. **Extension register write access** — enabling direct mode/reserve control via Modbus
>
> Until then, the recommended approach is direct power commands (`--charge`, `--discharge`, `--stop`) for VPP dispatch, and the FranklinWH mobile app for mode/reserve changes.

---

*Raw test output: `/tmp/cli_lifecycle_output.txt`*  
*Test script: `/tmp/cli_lifecycle_test.sh`*  
*Last updated: 2026-03-22*
