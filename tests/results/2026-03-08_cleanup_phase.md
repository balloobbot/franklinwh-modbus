# Test Results — 2026-03-08 (Cleanup Phase)

**Commit:** `e57b306` (develop)  
**Date:** 2026-03-08 16:30 AEDT  
**Device:** FranklinWH aGate X @ 192.168.0.110

---

## 1. Unit/Integration Tests (pytest)

```
32 passed, 7 skipped, 2 warnings in 14.61s
```

### Passed (32)

| Suite | Tests | Result |
|-------|-------|--------|
| `tests/integration/test_battery_control.py` | 12 tests | ✅ All passed |
| `tests/integration/test_virtual_mode_controller.py` | 7 tests (1 skipped) | ✅ All passed |
| `tests/test_package_import.py` | 6 tests | ✅ All passed |
| `tests/unit/test_tou_schedule.py` | 10 tests | ✅ All passed |

### Skipped (7)
- Hardware tests requiring `--run-hardware` flag (6)
- Virtual mode hardware connection test (1)

### Warnings (2)
- `TestResult` has `__init__` constructor (PytestCollectionWarning)
- `TestRecorder` has `__init__` constructor (PytestCollectionWarning)

---

## 2. Live Verification (aGate 192.168.0.110)

### read_battery_status()
```
soc: 79.0
soh: 96.1
wh_rating: 13600
wh_available: 10765
status: 0
battery_power_w: 400        ← M714 DCW (discharging)
battery_current_a: 0        ← DCA not populated, no DCV to calculate from
battery_temp_c: 0           ← M714 Tmp not populated by aGate firmware
```
**Result:** ✅ All fields present. `battery_temp_c` correctly defaults to 0 (aGate M714 has no Tmp data point).

### read_grid_status()
```
grid_power_w: -11           ← Near-zero (balanced)
grid_va: 542
grid_var: -164
voltage_v: 241.9            ← Normal for AU single-phase
frequency_hz: 50.02         ← Normal 50Hz grid
current_a: 2.2              ← From M701.A
power_factor: -0.033        ← From M701.PF
ambient_temp_c: 23.4        ← From M701.TmpAmb
cabinet_temp_c: 32.6        ← From M701.TmpCab
connection_state: Connected
inverter_state: Running
grid_mode: Grid Following (default)
ac_type: Single-Phase (230V Nominal)
```
**Result:** ✅ All 14 fields present and plausible.

### read_solar_status()
```
ac_power_w: 100             ← M502.OutPw (100W solar remaining late afternoon)
dc_power_w: 400             ← M714 battery DC (not solar!)
battery_dc_power_w: 400
extension:
  pv_total: 100
  pv_proximal: 100
  pv_remote1: 0
  pv_remote2: 0
  total_solar: 100
  home_load_ext: 500         ← Home consuming 500W
  ongrid_mode: 2             ← Self-Consumption
  self_reserve: 20
  tou_reserve: 20
total_solar_w: 100
```
**Result:** ✅ Extension solar working via raw socket. Solar = 100W (late afternoon).

### read_nameplate()
```
manufacturer: FranklinWH Technologies Co., Ltd
model: aGate X
serial: 10060006A02F24170091
version: V10R01B04D00
options: Option Name
✅ All values are strings
```
**Result:** ✅ All values resolved to `str` type (not SunSpec point objects).

### read_control_status()
```
wset_enabled: 0             ← No active Modbus command
wset_mode: 0
wset_watts: 0
wset_pct: 0.0
wset_pct_raw: 0
wset_revert_watts: 0
wset_revert_time_s: 0
wset_revert_remain_s: 0
```
**Result:** ✅ Clean state, no commands active.

### read_native_mode()
```
mode_raw: 2                 ← Self-Consumption
mode_name: Self-Consumption
self_reserve_pct: 20
tou_reserve_pct: 20
```
**Result:** ✅ Extension registers readable via raw socket.

### healthcheck()
```
healthy: True
message: HEALTHY
⚠️  ℹ Extension registers read-only: Ongrid Mode, Self Reserve, Tou Reserve (requires installer unlock)
```
**Result:** ✅ Healthy. Extension write test correctly identifies read-only status.

---

## 3. Changes Tested

| Change | Test Type | Result |
|--------|-----------|--------|
| `battery_temp_c` added to controller | Live | ✅ Returns 0 (M714 Tmp not populated) |
| `battery_current_a` from controller | Live | ✅ Returns 0 (DCA not populated, no DCV) |
| Dead TUI methods removed | Unit tests | ✅ 32 passed (no regressions) |
| `fetch_data()` uses enriched API | Unit tests | ✅ No regressions |
| Line 656 syntax fix | Unit tests | ✅ No parse errors |
| Legacy doc register addresses | Manual | ✅ Verified against raw reader output |

---

## 4. Known Limitations

- `battery_temp_c`: aGate firmware V10R01B04D00 does not expose M714.Tmp — always 0
- `battery_current_a`: M714.DCA always 0 and DCV not available — cannot calculate from P/V
- Extension registers (15507-15509): Read-only without SPAN Modbus unlock
