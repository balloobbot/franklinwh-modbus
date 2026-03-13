# FranklinWH aGate SunSpec Implementation Quirks

Documenting non-standard behaviors, missing registers, and implementation-specific issues discovered during development.

---

## Model 713 - DER Storage Capacity

### Sta (Status) Register Always 0

**Issue:** The `Sta` register in Model 713 always returns 0 (OFF) regardless of actual battery state.

**SunSpec 2 M713.Sta enum:**
| Value | Meaning |
|-------|---------|
| 0 | OFF |
| 1 | EMPTY |
| 2 | DISCHARGING |
| 3 | CHARGING |
| 4 | FULL |
| 5 | HOLDING |
| 6 | TESTING |

**Observed:** Battery actively charging at -400W (M714.DCW), SoC 79% — M713.Sta remains 0 (OFF).

**Workaround:** Derive battery state from M714 DCW power direction (±50W deadband):
```python
# M714.DCW sign convention (confirmed empirically 2026-03-10):
#   positive = power INTO battery (Charging)
#   negative = power OUT of battery (Discharging)
if dc_power > 50:
    state = 'CHARGING'
elif dc_power < -50:
    state = 'DISCHARGING'
else:
    state = 'IDLE'
```

**Code Location:** `src/franklinwh_modbus/controller.py:read_battery_status()` — returns `battery_state` (derived) and `status_raw` (M713.Sta, always 0)

---

## Model 714 - Battery DC Measurements

### DCA (DC Current) Register Not Populated
**Issue:** The DCA register in Model 714 returns 0 or is not implemented.

**Standard SunSpec Model 714 Fields:**
- `DCW` - DC Power (W) ✅ **Working** — positive=charging (into battery), negative=discharging (out of battery)
- `DCV` - DC Voltage (V) ✅ **Working** 
- `DCA` - DC Current (A) ❌ **Not populated (returns 0)**
- `Tmp` - Battery Temperature (°C) ✅ **Working**
- `DCWhInj` - DC Energy Injected (Wh) ✅ **Working** — lifetime discharged
- `DCWhAbs` - DC Energy Absorbed (Wh) ✅ **Working** — lifetime charged

**Workaround:** Calculate current from Power/Voltage:
```python
dc_current = dc_power / dc_voltage  # Ohm's Law: I = P/V
```

**Code Location:** `src/franklinwh_modbus/controller.py:read_battery_status()` (M714 section)

---

## Model 701 - Inverter Measurements

### TmpAmb and TmpCab Implementation
**Status:** ✅ **Working as of aGate firmware**

FranklinWH aGate X implements these temperature registers:
- `TmpAmb` (40105) - Ambient temperature
- `TmpCab` (40106) - Cabinet temperature

Earlier firmware versions may not expose these.

---

## Extension Registers (15500-15513) — Documented

FranklinWH provides proprietary extension registers beyond standard SunSpec:

| Address | Register | Status | Notes |
|---------|----------|--------|-------|
| 15500-15501 | PV Installed flags | ✅ Working | Not actively used |
| 15502-15505 | Solar breakdown | ✅ Working | PV Total, Proximal, Remote 1/2 (W) |
| 15506 | Home Load | ✅ Working | Active load in W |
| 15507 | Operating Mode | ✅ Working | 0=Emergency, 1=TOU, 2=Self-Consumption, 3=Manual |
| 15508 | Self-Consumption Reserve | ✅ Working | Reserve SOC % |
| 15509 | TOU Reserve | ⚠️ **Known defect** | Always mirrors 15508 — see below |
| 15510-15513 | PV Energy | ✅ Working | Total/Proximal Wh (uint32 high:low pairs) |

> **Note:** Write access to 15507-15509 requires **SPAN Modbus** unlock in FranklinWH installer app.

### SOC Reserve Registers — Known Defect

Registers 15508 (Self-Consumption Reserve) and 15509 (TOU Reserve) **always return the same value**, even when set differently in the FranklinWH app. This is a known firmware defect documented in the SPAN tab of the official SunSpec PICS file.

### Official SunSpec PICS Reference

FranklinWH's SunSpec Alliance certification document is at:
`docs/UPDATED_FranklinWH_Modbus_PICS_SM-000028.xlsx`

This XLSX documents:
- "Unimplemented" info points (using base address 1)
- Extension register definitions (SPAN tab)
- The SOC reserve defect

> [!WARNING]
> **We do not fully trust this document.** Our live testing has found discrepancies between what the PICS document claims and actual aGate behavior. Always verify against the live device. Use the PICS as a starting point, not ground truth.

See: `docs/VERIFICATION_BASELINE.md` for full register map and cross-verification.

---

## Extension Registers (15000-15039) — Undocumented

Discovered by accident (typo of 15500). Proprietary registers — likely aPower battery telemetry mirrors. See `docs/VERIFICATION_BASELINE.md` Section 4 for full dump.

Notable high-confidence matches:
- `15020` = 13600 → exact match to `713.WHRtg` (battery energy rating)
- `15036` = 961 → exact match to `713.SoH` raw (96.1%)
- `15024` = ~50010 → grid frequency mirror (~50.0Hz)
- `15025` = ~2420 → grid voltage mirror (~242.0V)

**Write-probe (2026-03-08):** All 40 registers accept writes at protocol level but ALL are silently discarded. No sticky registers found. See `tests/results/2026-03-08_extension_write_probe.md`.

**Unit ID scan:** All unit IDs (1-247 sampled) return the same aGate X device (DA=1). No hidden sub-devices.

> **Caution:** These are undocumented and may change with firmware updates.

> **Future TODO:** Overnight brute-force scan of address ranges 15040-15499 and 16000-20000+ for additional populated register ranges. The 15000 range was found by accident — there may be more. Scan ~5000 addresses at 100ms each ≈ 8 minutes.

---

## Model 704 - Battery Control

### WSet vs WSetPct Sign Convention
**Issue:** Hardware uses inverted sign convention for WSetPct.

| Parameter | Software Convention | Hardware Convention |
|-----------|---------------------|---------------------|
| `WSet` | Positive=Charge | Positive=Charge |
| `WSetPct` | Positive=Charge | **Negative=Charge** |

**Workaround:** Always invert WSetPct value when writing:
```python
m704.WSetPct.value = -pct_raw  # Invert for hardware
```

---

## ⚠️ Write Access Asymmetry & VPP Mode Handoff

> **This is the most significant implementation quirk affecting library design.**

### Control Architecture: VPP Mode Clean Handoff

When `WSetEna=1` is written to M704, the aGate **automatically activates VPP Mode** (exclusive remote control). This is a **clean handoff**, not a split-brain architecture:

1. **`WSetEna=1`** → aGate activates VPP Mode, native mode (Self-Consumption/TOU) is **suspended**
2. **M704 commands** control battery power exclusively while VPP is active
3. **`WSetEna=0`** → VPP deactivates, native mode **cleanly resumes**

See [VPP_MODE_COMPLETE_EXTRACTION.md](../archive/docs/VPP_MODE_COMPLETE_EXTRACTION.md) for the original discovery.

### Write Access Table

| Control Plane | Registers | Read | Write | What It Controls |
|---------------|-----------|------|-------|------------------|
| **SunSpec M704** | 40318-40354 | ✅ | ✅ | Battery power via VPP Mode (WSet, WSetPct, WSetEna) |
| **FranklinWH Extensions** | 15507-15509 | ✅ | ❌ Read-Only* | Operating mode, SoC reserves |
| **M702 Rate Settings** | 40259-40262 | ✅ | ❌ (tested 2026-03-13) | Charge/discharge rate limits |

*Extension write access requires **SPAN Modbus** unlock — enabled by FranklinWH Support for SPAN panel owners.

### What This Means in Practice

```
┌─────────────────────────────────────────────────────────────┐
│ We CAN do (SunSpec M704):              WE CANNOT do:        │
│ ✅ Charge battery at 3000W             ❌ Change mode to TOU │
│ ✅ Discharge battery at 2000W          ❌ Set reserve to 30% │
│ ✅ Set idle (stop charge/discharge)    ❌ Switch to Backup   │
│ ✅ Read all status + extensions        ❌ Change any mode    │
│ ✅ Release control (native resumes)    ❌ Set PCS rate limits│
└─────────────────────────────────────────────────────────────┘
```

### SunSpec2 Compliance Matrix

> See [SUNSPEC_DER_SEQUENCING_REFERENCE.md](./SUNSPEC_DER_SEQUENCING_REFERENCE.md) for proper phased sequencing protocol.

| Feature | SunSpec2 Spec | FranklinWH Reality | Library Workaround | Vendor Fix? |
|---------|--------------|-------------------|-------------------|-------------|
| LocRemCtl handoff | Remote (0) enables writes | Always Local (1), read-only; yet M704 writes work | None needed — power writes accepted despite Local | Report as spec deviation |
| Controller heartbeat | Client writes ControllerHb; DER monitors | ❌ Confirmed non-functional (write accepted, readback=0) | Not implemented — no alternative | Report as defect |
| Reversion timer (WSetRvrtTms) | DER counts down, auto-reverts power | ✅ **WORKS with proper sequencing!** Timer=60s accepted, countdown active (59→55→52) | Software `threading.Timer` via `duration_s` (may become optional) | N/A — working correctly |
| Reversion enable (WSetEnaRvrt) | Enables reversion behavior | ✅ **WORKS!** Readback=1 after write | N/A | N/A — working correctly |
| Battery state (M713.Sta) | Reflects CHARGING/DISCHARGING/IDLE | Always 0 (OFF) | Derived from M714.DCW ±50W deadband | Report; workaround is robust |
| DC Current (M714.DCA) | Reports battery DC current | Always 0 | Calculated: I = P/V from DCW/DCV | Report; workaround is robust |
| Ramp rate (WRmp) | Smooths power transitions | Returns None (unimplemented) | Software SoC ramp via `--soc-ramp-window` | Report; software ramp is different concept |
| Extension register writes | N/A (vendor-specific) | Read-only without SPAN Modbus unlock | Cloud API bypass (Tier 2) for mode changes | SPAN unlock required; vendor provisioning |
| VPP Mode activation | WSetEna=1 starts remote DER control | ✅ Works — activates VPP Mode (exclusive) | None needed — works as intended | N/A — working correctly |
| Command persistence | WSetRvrtTms reverts after timeout | WSetRvrtTms countdown active; WSetEna persists after timer expiry (partial implementation?) | Software timer + `reset_control_state()` remains recommended | Investigate: does countdown actually revert power? |
| Throttle % (ThrotPct) | Reports inverter power curtailment % | ✅ Readable (40180), always 0% in testing | None — read-only info point | N/A — may activate under thermal/grid stress |
| Throttle source (ThrotSrc) | Bitfield of throttle cause | 0xFFFFFFFF (unimplemented) | Not implemented — no alternative | Report; no workaround possible |
| Grid charge/discharge limits | `WChaRteMax` / `WDisChaRteMax` (RW per spec) | ❌ Confirmed: registers return 0xFFFF, writes silently discarded even with VPP + proper sequencing | Cloud API `setPowerControl` is only path | Report as defect |
| VA charge/discharge limits | `VAChaRteMax` / `VADisChaRteMax` (RW per spec) | ❌ Confirmed: 0xFFFF, writes discarded | Cloud API only | Report as defect |
| Max power limit (WMaxLimPct) | Caps inverter output at % of rated | ❌ **Confirmed non-functional.** WMaxLimPctEna write silently discarded (readback=0). WMaxLimPct readable (1000) but enable never sticks | Not implemented | Report as defect |
| Reactive power enable (VarSetEna) | Enables reactive power control | ❌ **Confirmed non-functional.** Write accepted, readback=0 (silently discarded). VarSetMod/VarSetPri readable but VarMaxInj/Abs=0xFFFF | Not implemented | Report as defect |

> **Test methodology:** All features re-tested 2026-03-13 using proper SunSpec 6-phase protocol (Pre-flight → Mode → Safety → Setpoint → Enable → Verify) with 200-500ms inter-phase settling. See [SUNSPEC_DER_SEQUENCING_REFERENCE.md](./SUNSPEC_DER_SEQUENCING_REFERENCE.md).
>
> **Test evidence:** [2026-03-13_pcs_charge_rate_write_probe.md](../tests/results/2026-03-13_pcs_charge_rate_write_probe.md), [2026-03-08_p1_control_tests.md](../tests/results/2026-03-08_p1_control_tests.md)

### Crash-Orphan Risk

> [!CAUTION]
> If the consumer application crashes while `WSetEna=1`, the aGate remains in VPP Mode indefinitely. There is no hardware timeout to auto-revert (WSetRvrtTms behavior unverified). The library provides `reset_control_state()` for graceful shutdown, but **crash recovery is a consumer responsibility**, not a library concern.

### The LocRemCtl Paradox (Model 715) — TESTED 2026-03-08

Model 715 `LocRemCtl` (addr 1089 base-1) reports `1` = **Local Control** and is **read-only**.

**Per SunSpec 2 spec:**
- `LocRemCtl = 1` (Local) → DER should **reject ALL** Modbus client writes
- `LocRemCtl = 0` (Remote) → DER accepts write commands from Modbus clients

**FranklinWH violates this fundamentally.** The aGate:
- ✅ Accepts M704 power writes (WSetEna, WSetPct, WSetMod) despite being in Local mode
- ❌ Ignores M715 lifecycle writes (ControllerHb — **confirmed non-functional** even with proper sequencing)
- ✅ **WSetRvrtTms WORKS** with proper sequencing (countdown active, 59→55→52)

This creates a **selective-write hybrid** that is non-standard:

| Feature | SunSpec 2 Expectation (Local) | FranklinWH Actual |
|---------|-------------------------------|-------------------|
| Power writes (WSetPct) | ❌ Reject | ✅ Accepts |
| Power enable (WSetEna) | ❌ Reject | ✅ Accepts |
| Reversion config (WSetRvrtTms) | ❌ Reject | ✅ Accepts value |
| Reversion countdown (WSetRvrtRem) | N/A | ✅ **Active!** Counts down correctly (59→55→52) |
| Controller heartbeat (ControllerHb) | ❌ Reject | ❌ **Confirmed non-functional** (write accepted, readback=0) |
| DER heartbeat (DERHb) | N/A | ❌ Always 0 |
| LocRemCtl write | Allow | ❌ Read-only |

**Test evidence:** See `tests/results/2026-03-08_p1_control_tests.md`

### Design Implications

1. **VPP Mode provides clean control handoff:** When `WSetEna=1`, the aGate suspends native mode and grants exclusive Modbus control. This is cooperative, not conflicting.

2. **Hardware reversion timer available:** WSetRvrtTms **works** — the aGate counts down and (potentially) reverts the power setpoint. However, WSetEna may persist after timer expiry. Further investigation needed on whether power actually reverts or just the countdown is cosmetic.

3. **ControllerHb remains non-functional:** Even with proper sequencing, heartbeat writes are silently discarded. Software watchdog (`duration_s` / `--revert`) remains the primary safety mechanism.

4. **Virtual modes operate within VPP Mode:** Our virtual Self-Consumption/TOU/Peak-Shave modes work by calculating power targets and issuing M704 commands while VPP Mode is active.

4. **Library vs consumer boundary:** The library exposes `send_command()` and `reset_control_state()`. Crash recovery, watchdog timers, and session lifecycle are **consumer responsibilities** (e.g. FEM's `ModbusControlService`).

5. **SPAN Modbus Unlock Changes Everything:** If write access to extensions is enabled, the library could fully control the aGate — changing modes, setting reserves, etc. This is a fundamentally different operating mode that the library should detect and adapt to.

### Detection of Write Capability

```python
# The library tests write capability during connect()
# by attempting a write to extension registers
def _probe_extension_writable(self):
    """Test if extension registers accept writes."""
    try:
        # Read current value, write it back, verify
        current = read_register(15508)  # SelfReserve
        write_register(15508, current)  # Write same value
        return True  # SPAN Modbus unlock is active
    except:
        return False  # Standard read-only
```

### Related

- [SUNSPEC_DER_SEQUENCING_REFERENCE.md](./SUNSPEC_DER_SEQUENCING_REFERENCE.md) — Proper 6-phase SunSpec control protocol
- [TODO_INTENT_BASED_CONFLICT_DETECTION.md](./TODO_INTENT_BASED_CONFLICT_DETECTION.md) — Re-scoped with VPP handoff model
- [VPP_MODE_COMPLETE_EXTRACTION.md](../archive/docs/VPP_MODE_COMPLETE_EXTRACTION.md) — Original VPP Mode discovery

---

## SunSpec2 Client — Address Remapping

**Issue:** The SunSpec2 Python library (`sunspec2.modbus.client.ModbusClientTCP`) remaps register addresses internally. The `client.read()` method adjusts addresses based on SunSpec model base offsets, causing "Modbus exception 2" (illegal address) when attempting to read FranklinWH proprietary extension registers (15000+ and 15500+).

The SunSpec2 client also does **not** expose `read_holding_registers()` — it has only `read()` and `_read()`.

**Workaround:** Use raw Modbus TCP socket for all extension register reads:
```python
import struct
client = self.dev.client
sock = client.socket
req = struct.pack('>HHHBBHH', 0, 0, 6, unit_id, 3, start_addr, count)
sock.settimeout(self.timeout)  # Important for WiFi networks
sock.sendall(req)
resp = sock.recv(256)
```

**Code Location:** `src/franklinwh_modbus/controller.py:_read_extension_solar()`, `read_native_mode()`

---

## M715 Address Space — Base-1 Only (TESTED 2026-03-08)

**Issue:** M715 (DERCtl) registers are ONLY accessible at base-1 addresses via raw Modbus TCP, NOT at the standard 40000+ offsets.

| Method | Address for ControllerHb | Result |
|--------|-------------------------|--------|
| sunspec2 model read | Internal mapping | ✅ Works |
| Raw TCP @ 41092 (base 40000) | 41092 | ❌ ILLEGAL_DATA_ADDRESS |
| Raw TCP @ 1092 (base 1) | 1092 | ✅ Readable |

The FranklinWH SunSpec XLSX file also confirms base address = 1.

---

## Model 502 — Power Rounding (Scale Factor Quantization)

**Discovered:** 2026-03-12 · **Severity:** Low (cosmetic) · **Reported to:** FranklinWH Support

FranklinWH aGate SunSpec registers round power values to coarse resolution (~100W steps) due to integer registers with limited scale factors. Small power flows are quantized upward, making them appear much larger than actual.

**Example:** Enphase Envoy S Metered standby draw (~50-100W parasitic load on the PV circuit at night) appears as **500-600W of "solar generation"** in both Modbus (`M502.OutPw`) and Cloud API readings. The aGate is the source of truth for both, so the coarse value propagates everywhere.

**Impact:**
- Solar power entities show non-zero values at night (confusing but not harmful)
- `--status` shows `Solar: 500W Producing` when actual solar generation is 0W
- Home load calculation (`(calc)`) is inflated by the phantom solar component
- Energy totals may include phantom solar contribution from parasitic loads

**No software fix possible** — the quantization happens in aGate firmware before the registers are read. The Cloud API mirrors the same coarse values since both originate from the aGate's internal metering.

**Possible future mitigation:** Time-based solar gating (zero solar output between sunset and sunrise) or a configurable dead-band threshold. Neither is implemented yet.

---

## Serial Number Structure

FranklinWH serial numbers encode device type, hardware revision, and unique ID:

```
10060006A02F24170091
│       │  │        │
│       │  │        └── Unique serial (last 8 chars)
│       │  └─────────── Hardware revision (3 chars, e.g. "A02")
│       └────────────── Device type prefix
└────────────────────── Full serial (20 chars)
```

**Why this matters:**
- Hardware revision determines capabilities — some revs have more/fewer functions
- Extract rev from serial: `serial[8:11]` (e.g. `"A02"`)
- Example: aGate `A02` vs `A03` may differ in supported Modbus registers
- Available from `M1.SN` (Model 1 Common, address 40052)

---

## General Notes

- **Scale Factors:** Always read SF registers dynamically — they can change
- **Model Discovery:** aGate implements models 1, 502, 701, 702, 703, 704, 705, 706, 707, 708, 709, 710, 711, 712, 713, 714, 715
- **Write Sequencing:** All SunSpec DER control groups require proper phased sequencing (Phase 0-5). See [SUNSPEC_DER_SEQUENCING_REFERENCE.md](./SUNSPEC_DER_SEQUENCING_REFERENCE.md)
- **Timing:** Minimum 100-500ms inter-phase settling. aGate round-trip ~98ms average. Do not rapid-fire writes.
- **Timeout:** WiFi networks to the aGate can be slow; always use configurable timeout (default 10s)
- **Addressing:** M715 registers accessible only at base-1 addresses. M704 works at both base-1 and base-40000.

---

*Last Updated: 2026-03-13 (VPP Mode handoff architecture, SunSpec2 Compliance Matrix, PCS write-probe results, SunSpec sequencing reference)*  
*Device Tested: FranklinWH aGate X (SN: 10060006A02F24170091, FW: V10R01B04D00)*
