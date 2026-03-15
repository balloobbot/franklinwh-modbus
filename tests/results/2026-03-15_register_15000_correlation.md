# Register 15000–15043 Summary Block — Correlation Results

**Date:** 2026-03-15 14:50 AEDT  
**Conditions:** Solar 2400W generating, SoC ~96%, Self-Consumption mode  
**Tool:** Raw TCP temporal correlation (11 samples @ 2s intervals)

---

## Confirmed Mappings

| Register | Match Confidence | Maps To | Evidence |
|:--------:|:----------------:|---------|----------|
| **15003** | 🟢 EXACT | Solar AC Power (W) | = M502.OutPw every sample (2400W) |
| **15007** | 🟢 STRONG | Grid Power (W, signed) | Negative when exporting (-324 to -346W) |
| **15011** | 🟢 EXACT | Home Load (W, high-res) | = Register 16000 every sample (3605-3680W) |
| **15013** | 🟡 LIKELY | Battery Power (W) | 1171-1218W when charging (unsigned?) |
| **15016** | 🟢 EXACT | OnGridMode | = 2 (Self-Consumption) |
| **15017** | 🟢 EXACT | Reserve % | = 20 (SelfReserve) |
| **15020** | 🟢 EXACT | Battery Capacity (Wh) | = 13600 (M713.WHRtg) |
| **15025** | 🟢 EXACT | Grid Voltage (raw) | = 2437 → 243.7V (M701.LNV) |
| **15035** | 🟢 HIGH-RES | SoC Unrounded | 956-957 → 95.6-95.7% |
| **15036** | 🟢 QUANTIZED | SoC Rounded | 960 → 96.0% (= M713.SoC) |

## Temporal Correlation Data

```
    Time |  15003   M502 |  15007   M701 |  15013   M714 |  15011  16000  15506 | 15035 15036
         |  solar  solar |   grid   grid |   batt   batt |      ? homeHR  homeQ |  SoC1  SoC2
--------------------------------------------------------------------------------------------------------------
14:50:14 |   2400   2400 |   -337      ? |   1199      ? |   3652   3652   3700 |   957   960
14:50:16 |   2400   2400 |   -328      ? |   1185      ? |   3635   3635   3600 |   957   960
14:50:18 |   2400   2400 |   -342      ? |   1203      ? |   3648   3648   3600 |   957   960
14:50:20 |   2400   2400 |   -333      ? |   1185      ? |   3644   3644   3600 |   957   960
14:50:22 |   2400   2400 |   -335      ? |   1171      ? |   3605   3605   3600 |   957   960
14:50:24 |   2400   2400 |   -331      ? |   1185      ? |   3620   3620   3600 |   956   960
14:50:26 |   2400   2400 |   -346      ? |   1196      ? |   3623   3623   3600 |   956   960
14:50:28 |   2400   2400 |   -340      ? |   1218      ? |   3680   3680   3700 |   956   960
14:50:31 |   2400   2400 |   -329      ? |   1201      ? |   3661   3661   3700 |   956   960
14:50:33 |   2400   2400 |   -324      ? |   1188      ? |   3628   3628   3600 |   956   960
14:50:35 |   2400   2400 |   -327      ? |   1186      ? |   3620   3620   3600 |   956   960
```

## Key Discoveries

### 1. Register 15011 = 16000 (EXACT MATCH)
Register 15011 matched register 16000 **on every single sample** — they are the same source.
This means `15011` is the canonical location and `16000` is just another alias.

### 2. High-Resolution SoC at 15035
Register 15035 shows **unrounded SoC** (95.6-95.7%) while 15036 shows the rounded value (96.0%).
This provides ~0.1% precision vs 1% steps from M713.

### 3. Signed Grid Power at 15007
Shows negative values when exporting (-324 to -346W). Matches expected behavior:
Solar (2400W) - Battery charging (~1200W) - Home load (~3600W) = grid import.
Wait: 2400 - 1200 - 3600 = -2400, but grid shows -334W. This means 15013 is NOT
simple battery charge. The power balance needs more investigation.

### 4. Power Balance Analysis
```
Solar:       2400W (15003) — producing
Home Load:  ~3640W (15011) — consuming  
Grid:       ~-335W (15007) — exporting 335W
Battery:    ~1190W (15013) — unclear sign convention
```
Expected: Solar + Grid + Battery = Home Load → 2400 + (-335) + Battery = 3640
→ Battery = 3640 - 2400 + 335 = 1575W (but register shows ~1190W)

The mismatch suggests either: 15013 has a scale factor, or there are unmeasured
loads, or the values are sampled at slightly different times.

## Unresolved Registers

| Register | Raw | Hypothesis | Notes |
|:--------:|----:|------------|-------|
| 15006 | 0xFFFF | Sentinel/unused | Always -1 |
| 15012 | 0xFFFF | Sentinel/unused | Always -1 |
| 15014 | 0xFFFF | Sentinel/unused | Always -1 |
| 15015 | -547 | Unknown power? | Signed, varies |
| 15021 | 1 | Battery count? | Constant |
| 15022 | -42 | Unknown | Signed |
| 15024 | -15526 | 32-bit pair? | Large signed |
| 15029 | 67 | Unknown | Small |
| 15033 | 19 | Temperature? | 19°C plausible |
| 15034 | -26261 | Unknown | Large signed |
| 15040 | 2467 | Unknown | ~voltage? |
| 15043 | 1 | Unknown | Constant |

---

*Filed: 2026-03-15 | Firmware: V10R01B04D00 | Status: OPEN — needs nighttime/discharge correlation*
