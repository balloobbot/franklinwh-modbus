# Verification Baseline — FranklinWH Modbus Library

Reference document for verifying all library methods, CLI tools, and TUI monitor produce correct results against known-good raw register data.

**Device:** FranklinWH aGate X (SN: `10060006A02F24170091`, Firmware: `V10R01B04D00`)  
**Baseline Date:** 2026-03-08  
**aGate Address:** `192.168.0.110:502` (Unit ID: 2 for SunSpec, all units for extensions)

---

## 1. Verification Toolset

### Primary Tools

| Tool | Purpose | Command |
|------|---------|---------|
| `modbus_sunspec2_reader.py` | Raw SunSpec register dump (ground truth) | `python3 tools/modbus_sunspec2_reader.py -i 192.168.0.110 -t 10 -dvalues --vals` |
| Library API | `FranklinWHController` method testing | `from franklinwh_modbus import FranklinWHController` |
| CLI | Formatted status display | `python3 franklinwh_cli.py -i 192.168.0.110 --status` |
| TUI Monitor | Live Rich dashboard | `python3 franklinwh_cli.py -i 192.168.0.110 --monitor` |

### Supplementary Tools

| Tool | Purpose | Command |
|------|---------|---------|
| `modbus_sunspec2_reader.py --raw` | Read arbitrary register ranges | `--raw 15500:14 --match` |
| `modbus_sunspec2_reader.py -dvalues` | Include decoded values with SF applied | `-dvalues --vals` |
| `ping` | aGate reachability check | `ping 192.168.0.110` |

---

## 2. SunSpec Model Register Map

### Model 1 — Common (Device Nameplate)

| Address | Field | Label | Expected Value | Library Method |
|---------|-------|-------|----------------|----------------|
| 40004 | `Mn` | Manufacturer | "FranklinWH Technologies Co., Ltd" | `read_nameplate()['manufacturer']` |
| 40020 | `Md` | Model | "aGate X" | `read_nameplate()['model']` |
| 40044 | `Vr` | Version | "V10R01B04D00" | `read_nameplate()['version']` |
| 40052 | `SN` | Serial Number | "10060006A02F24170091" | `read_nameplate()['serial']` |

### Model 502 — Solar Module

| Address | Field | Label | Units | Library Method |
|---------|-------|-------|-------|----------------|
| 41119 | `OutPw` | Output Power | W | `read_solar_status()['ac_power_w']` |
| 41117 | `OutWh` | Output Energy | Wh (acc32) | Lifetime energy in TUI |

### Model 701 — DER Measure AC (Grid/Inverter)

| Address | Field | Label | Units | SF | Library Method |
|---------|-------|-------|-------|-----|----------------|
| 40080 | `W` | Active Power | W | W_SF (0) | `read_grid_status()['grid_power_w']` |
| 40081 | `VA` | Apparent Power | VA | W_SF (0) | `read_grid_status()['grid_va']` |
| 40082 | `Var` | Reactive Power | Var | W_SF (0) | `read_grid_status()['grid_var']` |
| 40083 | `PF` | Power Factor | — | PF_SF (-3) | `read_grid_status()['power_factor']` |
| 40084 | `A` | Total AC Current | A | A_SF (-1) | `read_grid_status()['current_a']` |
| 40086 | `LNV` | Voltage L-N | V | V_SF (-1) | `read_grid_status()['voltage_v']` |
| 40087 | `Hz` | Frequency | Hz | Hz_SF (-3) | `read_grid_status()['frequency_hz']` |
| 40074 | `InvSt` | Inverter State | enum | — | `read_grid_status()['inverter_state']` |
| 40075 | `ConnSt` | Grid Connection | enum | — | `read_grid_status()['connection_state']` |
| 40078 | `DERMode` | DER Mode | bits | — | `read_grid_status()['grid_mode']` |
| 40105 | `TmpAmb` | Ambient Temp | °C | Tmp_SF (-1) | `read_grid_status()['ambient_temp_c']` |
| 40106 | `TmpCab` | Cabinet Temp | °C | Tmp_SF (-1) | `read_grid_status()['cabinet_temp_c']` |

**Scale Factors (M701):**

| SF Register | Address | Value | Description |
|------------|---------|-------|-------------|
| `A_SF` | 40183 | -1 | Current: raw ÷ 10 |
| `V_SF` | 40184 | -1 | Voltage: raw ÷ 10 |
| `Hz_SF` | 40185 | -3 | Frequency: raw ÷ 1000 |
| `W_SF` | 40186 | 0 | Power: raw × 1 |
| `PF_SF` | 40187 | -3 | Power Factor: raw ÷ 1000 |
| `Tmp_SF` | 40192 | -1 | Temperature: raw ÷ 10 |

### Model 704 — DER Control AC (Battery Control)

| Address | Field | Label | Library Method |
|---------|-------|-------|----------------|
| Various | `WSetEna` | Enable | `read_control_status()['wset_enabled']` |
| Various | `WSetMod` | Mode | `read_control_status()['wset_mode']` |
| Various | `WSet` | Watts | `read_control_status()['wset_watts']` |
| Various | `WSetPct` | Percent | `read_control_status()['wset_pct']` |

### Model 713 — DER Storage Capacity

| Address | Field | Label | Units | SF | Library Method |
|---------|-------|-------|-------|-----|----------------|
| 41035 | `WHRtg` | Energy Rating | Wh | WH_SF (0) | `read_battery_status()['wh_rating']` |
| 41036 | `WHAvail` | Available | Wh | WH_SF (0) | `read_battery_status()['wh_available']` |
| 41037 | `SoC` | State of Charge | % | Pct_SF (-1) | `read_battery_status()['soc']` |
| 41038 | `SoH` | State of Health | % | Pct_SF (-1) | `read_battery_status()['soh']` |
| 41039 | `Sta` | Status | enum | — | `read_battery_status()['status']` |

### Model 714 — DER Measure DC (Battery DC)

| Address | Field | Label | Units | SF | Library Method |
|---------|-------|-------|-------|-----|----------------|
| 41047 | `DCA` | DC Current | A | DCA_SF (0) | ⚠️ **Not populated (returns 0)** |
| 41048 | `DCW` | DC Power | W | DCW_SF (0) | `read_battery_status()['battery_power_w']` |
| 41049 | `DCWhInj` | Energy Injected | Wh (acc64) | DCWH_SF (0) | Lifetime discharged (TUI) |
| 41053 | `DCWhAbs` | Energy Absorbed | Wh (acc64) | DCWH_SF (0) | Lifetime charged (TUI) |

> [!NOTE]
> **DCW sign convention:** Negative = charging, Positive = discharging

### Model 715 — DER Control

| Address | Field | Label | Library Method |
|---------|-------|-------|----------------|
| 41089 | `LocRemCtl` | Control Mode | Not directly exposed |
| 41094 | `AlarmReset` | Alarm Reset | Not directly exposed |

---

## 3. FranklinWH Extension Registers (Documented: 15500–15513)

Proprietary registers outside SunSpec address space. Must be read via **raw Modbus TCP socket** — the SunSpec2 client remaps addresses and returns `Modbus exception 2` on these ranges.

| Address | Name | Label | Units | RW | Library Method |
|---------|------|-------|-------|-----|----------------|
| 15500 | `PVUse` | PV Installed | flag | R | — (not used) |
| 15501 | `apBoxPVUse` | Remote PV Installed | flag | R | — (not used) |
| 15502 | `PVOutputP` | PV Total Power | W | R | `read_solar_status()['extension']['pv_total']` |
| 15503 | `proximalPVOutputP` | PV Proximal Power | W | R | `read_solar_status()['extension']['pv_proximal']` |
| 15504 | `Remote1PV` | PV Remote 1 Power | W | R | `read_solar_status()['extension']['pv_remote1']` |
| 15505 | `Remote2PV` | PV Remote 2 Power | W | R | `read_solar_status()['extension']['pv_remote2']` |
| 15506 | `LoadActiveP` | Home Load | W | R | `read_solar_status()['extension']['home_load_ext']` |
| 15507 | `OnGridMode` | Operating Mode | enum | RW* | `read_native_mode()['mode_name']` |
| 15508 | `SelfReserve` | Self-Consumption Reserve | % | RW* | `read_native_mode()['self_reserve_pct']` |
| 15509 | `TouReserve` | TOU Reserve | % | RW* | `read_native_mode()['tou_reserve_pct']` |
| 15510–15511 | `PVOutputWh` | PV Energy Total | Wh | R | uint32 (high:low) |
| 15512–15513 | `proximalOutputWh` | PV Energy Proximal | Wh | R | uint32 (high:low) |

> [!IMPORTANT] 
> *RW marked with `*` — Write access requires **SPAN Modbus** unlock in FranklinWH installer app settings. Currently **READ-ONLY** on this device.

**OnGridMode enum:**

| Value | Mode |
|-------|------|
| 0 | Emergency Backup |
| 1 | Time of Use |
| 2 | Self-Consumption |
| 3 | Manual |

---

## 4. FranklinWH Extension Registers (Undocumented: 15000–15039)

> [!CAUTION]
> These registers are **undocumented** and were discovered via raw register scanning. Field names are speculative based on value matching against known SunSpec data. They may change with firmware updates.

Discovered via: `python3 tools/modbus_sunspec2_reader.py -i 192.168.0.110 -t 10 --raw 15000:40 --match`

| Address | Raw | Possible Match | Confidence | Notes |
|---------|-----|----------------|------------|-------|
| 15003 | 1200 | `502.OutPw` (Solar AC Power) | Medium | Matches raw OutPw at time of read |
| 15007 | -195 | Grid export? | Low | Negative = exporting? |
| 15011 | 575 | SoC raw? (57.5%) | Low | Close to 590 SoC raw |
| 15013 | -625 | Battery DC power? | Low | Negative = charging? |
| 15015 | 86 | Unknown | — | |
| 15016 | 2 | OnGridMode? | Low | Same value as 15507 |
| 15017 | 20 | Reserve %? | Low | Same value as 15508/15509 |
| 15020 | 13600 | `713.WHRtg` (Battery Rating) | **High** | Exact match |
| 15024 | 50000 | Max power rating? | Low | 5000W × 10? |
| 15025 | 2409 | Voltage raw (240.9V)? | Medium | Close to LNV reading |
| 15035 | 614 | SoC raw? | Low | |
| 15036 | 961 | `713.SoH` (State of Health) | **High** | Exact match (96.1%) |

> [!NOTE]
> The 15000+ block may be an internal FranklinWH data cache or alternative interface. Registers with **High** confidence matches replicate data available via standard SunSpec models. Further investigation needed to identify unique data points not available elsewhere.

---

## 5. Cross-Verification Matrix

Use this matrix to verify each library method returns data consistent with the raw SunSpec reader.

### How to Run a Cross-Verification

```bash
# 1. Capture raw baseline
python3 tools/modbus_sunspec2_reader.py -i 192.168.0.110 -t 10 -dvalues --vals > /tmp/raw_baseline.txt

# 2. Run library methods (within ~10 seconds of raw read)
python3 -c "
from franklinwh_modbus import FranklinWHController
ctrl = FranklinWHController('192.168.0.110')
ctrl.connect()
print('Battery:', ctrl.read_battery_status())
print('Grid:', ctrl.read_grid_status())
print('Solar:', ctrl.read_solar_status())
print('Nameplate:', ctrl.read_nameplate())
print('Control:', ctrl.read_control_status())
print('NativeMode:', ctrl.read_native_mode())
ctrl.disconnect()
"

# 3. Run CLI
python3 franklinwh_cli.py -i 192.168.0.110 --status
```

### Verification Checklist

| Library Method | Key Fields | Raw Source | Match Rule |
|---------------|------------|-----------|------------|
| `read_battery_status()` | `soc` | M713.SoC × 10^Pct_SF | Within ±1% (time drift) |
| | `soh` | M713.SoH × 10^Pct_SF | Exact (stable value) |
| | `wh_rating` | M713.WHRtg | Exact (13600) |
| | `battery_power_w` | M714.DCW × 10^DCW_SF | Within ±200W (time drift) |
| `read_grid_status()` | `voltage_v` | M701.LNV × 10^V_SF | Within ±2V |
| | `frequency_hz` | M701.Hz × 10^Hz_SF | Within ±0.05Hz |
| | `current_a` | M701.A × 10^A_SF | Within ±1A |
| | `power_factor` | M701.PF × 10^PF_SF | Within ±0.1 |
| | `ambient_temp_c` | M701.TmpAmb × 10^Tmp_SF | Within ±1°C |
| | `cabinet_temp_c` | M701.TmpCab × 10^Tmp_SF | Within ±1°C |
| `read_solar_status()` | `ac_power_w` | M502.OutPw | Within ±500W (time drift) |
| | `extension.pv_total` | Reg 15502 | Exact |
| | `extension.home_load_ext` | Reg 15506 | Within ±100W |
| `read_nameplate()` | All fields | M1 string points | Exact string match |
| | Return type | All values → `str` | `type(v).__name__ == 'str'` |
| `read_native_mode()` | `mode_raw` | Reg 15507 | Exact |
| | `self_reserve_pct` | Reg 15508 | Exact |
| `read_control_status()` | `wset_enabled` | M704.WSetEna | Exact |

### Known Acceptable Differences

- **Power/current values:** Vary ±10% between consecutive reads (real-time measurement)
- **Temperatures:** Drift slowly (±0.5°C between reads)
- **Energy counters:** Monotonically increasing (never decrease)
- **SoC:** Changes with charge/discharge activity (±2% over minutes)
- **SoH:** Stable (changes very slowly over months)

---

## 6. Discovered Models

Full list of SunSpec models on this aGate:

```
Models: [1, 502, 701, 702, 703, 704, 705, 706, 707, 708, 709, 710, 711, 712, 713, 714, 715]
```

| Model | Name | Purpose | Used By Library |
|-------|------|---------|----------------|
| 1 | Common | Nameplate | ✅ `read_nameplate()` |
| 502 | Solar Module | Solar AC power/energy | ✅ `read_solar_status()` |
| 701 | DERMeasureAC | Grid measurements | ✅ `read_grid_status()` |
| 702 | DERCapacity | Rated capacities | Via `connect()` |
| 703 | DEREnterService | Enter service settings | Not used |
| 704 | DERCtlAC | Battery control | ✅ `read_control_status()`, `send_command()` |
| 705–712 | DER curves/trips | Protection settings | Not used |
| 713 | DERStorageCapacity | Battery SoC/SoH/energy | ✅ `read_battery_status()` |
| 714 | DERMeasureDC | Battery DC power | ✅ `read_battery_status()` |
| 715 | DERCtl | DER control | ✅ Alarm checking |

---

*Last Updated: 2026-03-08*  
*Library Version: 0.9.0*  
*Commit: 9968c62 (develop)*
