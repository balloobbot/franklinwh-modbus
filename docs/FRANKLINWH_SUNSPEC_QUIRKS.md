# FranklinWH aGate SunSpec Implementation Quirks

Documenting non-standard behaviors, missing registers, and implementation-specific issues discovered during development.

---

## Model 714 - Battery DC Measurements

### DCA (DC Current) Register Not Populated
**Issue:** The DCA register in Model 714 returns 0 or is not implemented.

**Standard SunSpec Model 714 Fields:**
- `DCW` - DC Power (W) ✅ **Working** — negative=charging, positive=discharging
- `DCV` - DC Voltage (V) ✅ **Working** 
- `DCA` - DC Current (A) ❌ **Not populated (returns 0)**
- `Tmp` - Battery Temperature (°C) ✅ **Working**
- `DCWhInj` - DC Energy Injected (Wh) ✅ **Working** — lifetime discharged
- `DCWhAbs` - DC Energy Absorbed (Wh) ✅ **Working** — lifetime charged

**Workaround:** Calculate current from Power/Voltage:
```python
dc_current = dc_power / dc_voltage  # Ohm's Law: I = P/V
```

**Code Location:** `src/franklinwh/controller.py:read_battery_status()` (M714 section)

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
| 15508-15509 | SOC Reserve | ✅ Working | Self/TOU reserve % |
| 15510-15513 | PV Energy | ✅ Working | Total/Proximal Wh (uint32 high:low pairs) |

> **Note:** Write access to 15507-15509 requires **SPAN Modbus** unlock in FranklinWH installer app.

See: `docs/VERIFICATION_BASELINE.md` for full register map and cross-verification.

---

## Extension Registers (15000-15039) — Undocumented

Additional proprietary registers discovered via raw scanning. See `docs/VERIFICATION_BASELINE.md` Section 4 for full dump with tentative field matching.

Notable high-confidence matches:
- `15020` = 13600 → exact match to `713.WHRtg` (battery energy rating)
- `15036` = 961 → exact match to `713.SoH` raw (96.1%)

> **Caution:** These are undocumented and may change with firmware updates.

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

## ⚠️ Write Access Asymmetry — The Core FranklinWH Quirk

> **This is the most significant implementation quirk affecting library design.**

### The Problem

FranklinWH creates a **split-brain control architecture** where two independent control planes exist with different write access:

| Control Plane | Registers | Read | Write | What It Controls |
|---------------|-----------|------|-------|------------------|
| **SunSpec Standard** | M704 (40xxx) | ✅ | ✅ | Battery power (WSet, WSetPct, WSetEna) |
| **FranklinWH Extensions** | 15507-15509 | ✅ | ❌ Read-Only* | Operating mode, SoC reserves |

*Write access requires **SPAN Modbus** unlock — enabled by FranklinWH Support for owners of SPAN electrical panels. The aGate's Ethernet port passes through the SPAN Panel, which controls Modbus access.

### What This Means in Practice

```
┌─────────────────────────────────────────────────────────────┐
│ We CAN do (SunSpec M704):              WE CANNOT do:        │
│ ✅ Charge battery at 3000W             ❌ Change mode to TOU │
│ ✅ Discharge battery at 2000W          ❌ Set reserve to 30% │
│ ✅ Set idle (stop charge/discharge)    ❌ Switch to Backup   │
│ ✅ Read all status + extensions        ❌ Change any mode    │
└─────────────────────────────────────────────────────────────┘
```

### The LocRemCtl Conflict (Model 715)

Model 715 `LocRemCtl` (41089) reports `1` = **Local Control**. In standard SunSpec, a remote client (like this library) should:

1. Write `LocRemCtl = 0` (Remote) to signal it wants to take control
2. The DER device acknowledges by accepting write commands
3. The remote client writes M704 to control the battery
4. On disconnect, write `LocRemCtl = 1` (Local) to release control

**FranklinWH does NOT support this handoff.** `LocRemCtl` appears to be read-only. Despite this, M704 writes work without the LocRemCtl handoff — FranklinWH allows "side-channel" power control while the aGate simultaneously runs its own mode (Self-Consumption, TOU, etc.).

### Design Implications

1. **Conflicting Control Sources:** The aGate's Cloud API mode continues running while Modbus power commands override battery behavior. This creates a tug-of-war: Modbus commands expire (via `WSetRvrtTms`), and the aGate resumes its native mode.

2. **Virtual Modes Are Illusions:** Our "virtual" Self-Consumption/TOU/Peak-Shave modes cannot actually change the aGate's operating mode — they can only fight against it using M704 power commands.

3. **Intent-Based Conflict Detection Must Account for This:** The conflict detection system (see `TODO_INTENT_BASED_CONFLICT_DETECTION.md`) must understand that the aGate's native mode (read from extension 15507) will always be exerting its own intent in parallel. True conflicts are when the aGate's native mode AND user Modbus commands work against each other.

4. **SPAN Modbus Unlock Changes Everything:** If write access to extensions is enabled, the library could fully control the aGate — changing modes, setting reserves, etc. This is a fundamentally different operating mode that the library should detect and adapt to.

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

- `docs/TODO_INTENT_BASED_CONFLICT_DETECTION.md` — Must be re-evaluated given this asymmetry
- `docs/VERIFICATION_BASELINE.md` — Extension register access table

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

**Code Location:** `src/franklinwh/controller.py:_read_extension_solar()`, `read_native_mode()`

---

## General Notes

- **Scale Factors:** Always read SF registers dynamically — they can change
- **Model Discovery:** aGate implements models 1, 502, 701, 702, 703, 704, 705, 706, 707, 708, 709, 710, 711, 712, 713, 714, 715
- **Write Sequencing:** Model 704 requires specific write sequence (STOP → CONFIG → ENABLE → VERIFY)
- **Timeout:** WiFi networks to the aGate can be slow; always use configurable timeout (default 10s)

---

*Last Updated: 2026-03-08*  
*Device Tested: FranklinWH aGate X (SN: 10060006A02F24170091, FW: V10R01B04D00)*
