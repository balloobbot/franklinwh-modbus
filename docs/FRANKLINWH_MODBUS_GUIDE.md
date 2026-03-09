# FranklinWH Modbus TCP Implementation Guide

> **Definitive reference** for controlling FranklinWH aGate battery systems via Modbus TCP.
> Last verified: 2026-03-08 on aGate X (FW V10R01B04D00)

---

## 1. Connection

```
Host:    192.168.0.110 (default aGate IP)
Port:    502 (Modbus TCP)
Unit ID: 1 or 2 (both work, DA=1)
Base:    Address 1 (NOT standard 40000 for raw TCP)
Timeout: 10s recommended (WiFi can be slow)
```

```python
from franklinwh import FranklinWHController
ctrl = FranklinWHController('192.168.0.110')
ctrl.connect()  # Scans SunSpec models, probes extension writability
```

**Models discovered:** 1, 502, 701, 702, 703, 704, 705, 706, 707, 708, 709, 710, 711, 712, 713, 714, 715

---

## 2. What You CAN and CANNOT Do

```
┌─────────────────────────────────────────────────────┐
│ ✅ CAN DO (SunSpec M704):     ❌ CANNOT DO:         │
│  • Charge battery at Xw        • Change mode        │
│  • Discharge battery at Xw     • Set reserve %      │
│  • Set idle (standby)          • Switch to Backup   │
│  • Toggle power factor (PF)    • Set max power cap  │
│  • Read ALL registers          • Control ramp rate  │
│  • Auto-revert (software)      • Use heartbeat      │
└─────────────────────────────────────────────────────┘
```

> Extension registers (15507-15509) require **SPAN Modbus** unlock via FranklinWH installer app. Without it, they are read-only.

---

## 3. Complete Writable Register Map

After exhaustive P1-P4 testing, only **5 of 48 M704 registers** accept writes:

| Register | Address | Type | Works? | What It Does |
|----------|---------|------|--------|---|
| `WSetEna` | 40318 | enum16 | ✅ | Enable/disable battery power control |
| `WSetMod` | 40319 | enum16 | ✅ | Power mode (always set to 0) |
| `WSetPct` | 40324 | int16 | ✅ | **Primary control** — charge/discharge % |
| `WSetRvrtTms` | 40327 | uint32 | ⚠️ | Accepts value, countdown never activates |
| `PFWInjEna` | 40298 | enum16 | ✅ | Power factor enable (on by default) |

**Everything else** — WMaxLimPct, VarSet, WRmp, ControllerHb, LocRemCtl — is either read-only (writes silently discarded) or unimplemented (returns `None`).

---

## 4. How to Control the Battery

### Command Sequence (mandatory 4-step)

```
1. STOP:    WSetEna = 0               (disable control)
2. CONFIG:  WSetMod = 0, WSetPct = -X (set mode + power %)
3. ENABLE:  WSetEna = 1               (enable control)
4. VERIFY:  read WSetPct              (confirm value stuck)
```

> **Sign Convention:** `WSetPct` is **inverted** on FranklinWH. Negative = charge, positive = discharge. The library handles this automatically.

### Python API

```python
from franklinwh.types import BatteryCommand, ControlMode

# Charge at 3000W
cmd = BatteryCommand(power_watts=3000, mode=ControlMode.LIMIT_ABS)
success, msg = ctrl.send_command(cmd)

# Charge with auto-revert after 1 hour (software timer)
ctrl.send_command(cmd, duration_s=3600)

# Check timer
ctrl.get_command_timer_status()  # {'active': True, 'interval_s': 3600}

# Stop / release control
ctrl.reset_control_state()
```

### CLI

```bash
# Charge at 3000W (fire and forget — persists after CLI exits)
python3 tools/franklinwh_cli.py -i 192.168.0.110 --charge 3000

# Charge with auto-revert
python3 tools/franklinwh_cli.py -i 192.168.0.110 --charge 3000 --revert 3600

# Check status (won't kill active commands)
python3 tools/franklinwh_cli.py -i 192.168.0.110 --status

# Stop
python3 tools/franklinwh_cli.py -i 192.168.0.110 --stop
```

---

## 5. Key Hardware Quirks

### 5.1 The LocRemCtl Paradox

M715 `LocRemCtl` (addr 1089) is **read-only, always "Local" (1)**. Per SunSpec 2, this should mean the DER rejects ALL writes. FranklinWH violates this — it **selectively** accepts power writes while ignoring lifecycle features:

| Feature | SunSpec 2 Expects | FranklinWH Does |
|---------|-------------------|-----------------|
| Power writes (WSetPct) | ❌ Reject | ✅ Accepts |
| Reversion countdown | N/A | ❌ Never activates |
| Controller heartbeat | ❌ Reject | ❌ Silently ignores |
| LocRemCtl write | Allow | ❌ Read-only |

**Impact:** All lifecycle features (heartbeat, reversion timer) must be implemented in **software**.

### 5.2 Command Persistence

Commands **persist indefinitely** after disconnect. The aGate holds the last WSetPct value until:
- Another `send_command()` overwrites it
- `reset_control_state()` sets WSetEna=0
- The aGate is power-cycled

There is **no automatic timeout** — hardware reversion (`WSetRvrtTms`) accepts values but never executes. Use the library's software timer (`duration_s` parameter).

### 5.3 Battery State Register Unreliable

M713 `Sta` is **always 0 (OFF)** regardless of actual state. Derive battery state from M714 `DCW`:

```python
if dc_power < -50:   state = 'CHARGING'
elif dc_power > 50:  state = 'DISCHARGING'
else:                state = 'IDLE'
```

### 5.4 Sign Convention

| Register | Software | Hardware |
|----------|----------|----------|
| `WSet` | Positive = Charge | Positive = Charge |
| `WSetPct` | Positive = Charge | **Negative = Charge** |

The library automatically inverts: `m704.WSetPct.value = -pct_raw`

### 5.5 WSet vs WSetPct Conflict

Writing to `WSet` (absolute watts) alongside `WSetPct` causes **mode flickering** on the aGate. The library uses **only WSetPct**. `WSet` is zeroed during `reset_control_state()`.

### 5.6 Extension Registers & SPAN Modbus Unlock

| Address | Name | Access | Notes |
|---------|------|--------|-------|
| 15507 | OnGridMode | R (RW with SPAN) | 0=Backup, 1=TOU, 2=Self-Consumption, 3=Manual |
| 15508 | SelfReserve | R (RW with SPAN) | Reserve SOC % |
| 15509 | TouReserve | R (RW with SPAN) | ⚠️ **Always mirrors 15508** (firmware defect) |

Write access to these registers requires the **SPAN Modbus** unlock — enabled by FranklinWH support for owners of SPAN Smart Panels. The aGate's Ethernet port passes through the SPAN Panel, which controls Modbus access.

#### Detecting SPAN Configuration

**1. Network Scanner** — detect SPAN Panel on the local network:
```bash
python3 tools/network_scanner.py --type span
```
If a SPAN Panel is found alongside the aGate on the same network, extension registers are **likely writable**.

**2. FranklinWH Cloud API** — check `spanFlag` directly:
```bash
curl "https://energy.franklinwh.com/hes-gateway/terminal/span/getSpanSetting?gatewayId=YOUR_GATEWAY_ID"
```
```json
{"code": 200, "result": {"spanFlag": 0}, "success": true}
```
- `spanFlag: 0` → SPAN **not configured** (extensions read-only)
- `spanFlag: 1` → SPAN **configured** (extensions likely writable)

**3. Library auto-detection** — the controller probes on `connect()`:
```python
ctrl.connect()
# Logs: "Extension registers: READ-ONLY (requires installer unlock for SPAN Modbus)"
# or:   "Extension registers: WRITABLE (SPAN Modbus enabled)"
```

> [!NOTE]
> **Community testing needed:** We need a user with both SPAN Panel + aGate configured to verify that `spanFlag: 1` enables write access to 15507-15509 via Modbus TCP.

### 5.7 PFWInjEna (Power Factor)

`PFWInjEna` (40298) is **enabled by default (=1)** and **writable**:
- Enabled (=1): PF ≈ unity (-1 raw, SF -3)
- Disabled (=0): PF = 0.003 (essentially no correction)
- **Do not leave disabled** — it controls the aGate's default PF correction

### 5.8 SunSpec2 Library Quirks

The `sunspec2` Python client remaps addresses internally. Extension registers (15000+, 15500+) must be read via **raw Modbus TCP socket**, not `sunspec2.client.read()`:

```python
import struct
sock = ctrl.dev.client.socket
req = struct.pack('>HHHBBHH', 0, 0, 6, unit_id, 3, addr, count)
sock.sendall(req)
resp = sock.recv(256)
```

### 5.9 M715 Address Space

M715 registers are **only accessible at base-1 addresses** via raw TCP. Base-40000 addresses (41087+) return `ILLEGAL_DATA_ADDRESS`.

---

## 6. Software vs Hardware Features

| Feature | Hardware | Software (Library) |
|---------|----------|-------------------|
| Charge/Discharge | ✅ M704 WSetPct | ✅ `send_command()` |
| Auto-Revert Timer | ❌ WSetRvrtTms broken | ✅ `duration_s` param |
| Heartbeat | ❌ ControllerHb ignored | ❌ Not implemented |
| SoC Ramp | ❌ WRmp unimplemented | ✅ `--soc-ramp-window` |
| Battery State | ❌ M713.Sta always 0 | ✅ Derived from M714 DCW |
| Conflict Detection | N/A | ✅ `check_state()` |
| Mode Control | ❌ Extensions read-only | ⚠️ Virtual modes (power-only) |

---

## 7. Reading System State

```python
# Battery
bat = ctrl.read_battery_status()
# → soc, dc_power, dc_voltage, temperature, battery_state

# Solar + Grid + Load
solar = ctrl.read_solar_production()
grid  = ctrl.read_grid_status()

# Control status
ctl = ctrl.read_control_status()
# → wset_enabled, wset_pct, wset_watts

# Native mode (aGate's cloud setting)
mode = ctrl.read_native_mode()
# → mode_name, self_reserve_pct, tou_reserve_pct

# Health check (zombie state detection)
h = ctrl.healthcheck()
# → healthy, message, recommendations
```

---

## 8. Related Documentation

| Document | What It Covers |
|----------|---------------|
| [DER_CONTROL_REFERENCE.md](./DER_CONTROL_REFERENCE.md) | Full register map — all 48 M704 + 6 M715 fields |
| [FRANKLINWH_SUNSPEC_QUIRKS.md](./FRANKLINWH_SUNSPEC_QUIRKS.md) | Detailed quirk analysis (LocRemCtl, M713, extensions) |
| [ORCHESTRATION_AND_CONTROL.md](./ORCHESTRATION_AND_CONTROL.md) | Command sequences, SoC ramping, entry points |
| [VERIFICATION_BASELINE.md](./VERIFICATION_BASELINE.md) | Full register dump + cross-verification |

### Test Evidence

| Test | Result | Evidence |
|------|--------|----------|
| P1: Heartbeat + Reversion | ❌ Non-functional | [2026-03-08_p1_control_tests.md](../tests/results/2026-03-08_p1_control_tests.md) |
| P2: WMaxLimPct | ❌ Read-only | [2026-03-08_p2p4_control_tests.md](../tests/results/2026-03-08_p2p4_control_tests.md) |
| P3: VarSet | ❌ Read-only | Same file |
| P4: WRmp | ❌ Unimplemented | Same file |
| PFWInjEna | ✅ Writable | Same file |
| Extension write-probe | ❌ Read-only | [2026-03-08_extension_write_probe.md](../tests/results/2026-03-08_extension_write_probe.md) |

---

*Device: FranklinWH aGate X (SN: 10060006A02F24170091, FW: V10R01B04D00)*
*Last Updated: 2026-03-09*
