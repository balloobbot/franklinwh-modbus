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
