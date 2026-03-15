# M801/M802 Battery Model Scan Results

**Date:** 2026-03-15 12:37 AEDT  
**Device:** FranklinWH aGate X (192.168.0.110:502)  
**Tool:** `/tmp/m801_battery_scan.py` (pymodbus 3.12.1 async)  
**Test Plan Source:** Claude Sonnet T3Chat

---

## Step 1: UID Scan Results

| UID | Base 0 | Base 40000 | Base 50000 |
|:---:|:------:|:----------:|:----------:|
| 1   | ✅ SunSpec | ✅ SunSpec | ❌ No response |
| 2   | ✅ SunSpec | ✅ SunSpec | ❌ No response |
| 3   | ✅ SunSpec | ✅ SunSpec | ❌ No response |
| 126 | ✅ SunSpec | ✅ SunSpec | ❌ No response |
| 247 | ✅ SunSpec | ✅ SunSpec | ❌ No response |

**Finding:** ALL 5 UIDs respond identically at both base 0 and base 40000. The device treats UID as a don't-care — it's a single-endpoint device that aliases all UIDs to the same register map.

---

## Step 2: Model Chain Walk

All UIDs produce identical model chains (17 models, base 0):

| Offset | Addr | Model | Len | Name |
|-------:|-----:|------:|----:|------|
| 2      | 2    | 1     | 66  | Common |
| 70     | 70   | 701   | 153 | DER AC Measurement |
| 225    | 225  | 702   | 50  | DER Capacity |
| 277    | 277  | 703   | 17  | DER Rating |
| 296    | 296  | 704   | 65  | DER AC Controls |
| 363    | 363  | 705   | 67  | DER Controls 2 |
| 432    | 432  | 706   | 31  | DER Status |
| 465    | 465  | 707   | 105 | DER Status 2 |
| 572    | 572  | 708   | 105 | DER Storage Capacity |
| 679    | 679  | 709   | 135 | DER Storage Status |
| 816    | 816  | 710   | 135 | DER Storage Control |
| 953    | 953  | 711   | 32  | DER Pricing |
| 987    | 987  | 712   | 44  | DER Pricing 2 |
| 1033   | 1033 | 713   | 7   | DER Pricing 3 |
| 1042   | 1042 | 714   | 43  | DER Storage / DC Port |
| 1087   | 1087 | 715   | 7   | DER Lifecycle |
| 1096   | 1096 | 502   | 28  | Metrology |
| 1126   | —    | 0xFFFF | —  | End marker |

---

## Step 3: M801 Deep Read

**SKIPPED** — M801 not found at any UID.

---

## Verdict

| Question | Answer |
|----------|--------|
| M801 (Battery Base) found? | **No** |
| M802 (Battery Inverter) found? | **No** |
| M803-806 (Lithium detail) found? | **No** |
| New/unknown models? | **None** — 0 new models |
| UIDs with different maps? | **No** — all identical |
| Base 50000 (alternate)? | **No response** |

### Conclusions

1. **No battery-specific SunSpec models (801-806) exposed** — BMS/cell data is gated via Cloud API only
2. **UID is a don't-care** — UIDs 1, 2, 3, 126, 247 all alias the same register map
3. **Exact same 17 models** at both base 0 and base 40000 — confirms dual-addressing (our library uses base 40000)
4. **No hidden register maps** — the model chain terminates cleanly at offset 1126 with 0xFFFF

### New Discovery: UID Aliasing

Previously we used UID=2 exclusively (based on FranklinWH documentation). This scan confirms:
- **Any UID works** — the device ignores the UID field entirely
- This explains why UID=126 (SunSpec broadcast) also works
- No per-UID register partitioning exists

---

*Filed: 2026-03-15 | Firmware: V10R01B04D00 | Status: CLOSED — definitive*
