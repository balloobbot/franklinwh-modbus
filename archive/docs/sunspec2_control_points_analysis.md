# SunSpec2 Power Control Points Analysis

**Date:** 2026-02-14  
**Models:** 702 (DER Capacity), 704 (DER AC Controls)  
**Source:** `python modbus_sunspec2_reader.py -i 192.168.0.110 -d=full`

---

## Overview

This analysis identifies which SunSpec2 "Max" points can control battery charging/discharging and how they map to the dashboard Power Capacity card.

---

## Point Classification

### 📖 Read-Only Ratings (Hardware Limits)

**Suffix: `Rtg`** - These are **immutable hardware specifications**. Cannot be written.

| Point | Model | Purpose | Value |
|-------|-------|---------|-------|
| `WChaRteMaxRtg` | 702 | **Max charge rate (W)** - Hardware limit | 5000W |
| `WDisChaRteMaxRtg` | 702 | **Max discharge rate (W)** - Hardware limit | 5000W |
| `VAChaRteMaxRtg` | 702 | Max charge rate (VA) | Read-only |
| `VADisChaRteMaxRtg` | 702 | Max discharge rate (VA) | Read-only |
| `WMaxRtg` | 702 | Max active power at unity PF | Read-only |
| `VAMaxRtg` | 702 | Max apparent power | Read-only |

**Dashboard Mapping:** These appear as "Rated Charge: 5 kW" and "Rated Discharge: 5 kW"

---

### ⚙️ Writable Settings (Operational Limits)

**No `Rtg` suffix** - These can be **written** to adjust operational limits below hardware ratings.

| Point | Model | Purpose | Control Capability |
|-------|-------|---------|-------------------|
| `WChaRteMax` | 702 | **Charge rate limit (W)** | ✅ **CAN WRITE** - Limit charging power |
| `WDisChaRteMax` | 702 | **Discharge rate limit (W)** | ✅ **CAN WRITE** - Limit discharging power |
| `VAChaRteMax` | 702 | Charge rate limit (VA) | ✅ Writable (advanced) |
| `VADisChaRteMax` | 702 | Discharge rate limit (VA) | ✅ Writable (advanced) |
| `WMax` | 704 | Active power limit | ✅ Writable (DER control) |
| `VAMax` | 704 | Apparent power limit | ✅ Writable (advanced) |

**Key Finding:** `WChaRteMax` and `WDisChaRteMax` are the **primary controls** for battery charge/discharge power!

---

### 🎛️ Power Limiting Controls (Model 704)

**Purpose:** Enable/disable power limits as percentage of max power

| Point | Access | Purpose | Dashboard Use |
|-------|--------|---------|---------------|
| `WMaxLimPctEna` | **RW** | **Enable power limiting** | ✅ "Controls: Active (Unlimited)" toggle |
| `WMaxLimPct` | **RW** | **Power limit (% of WMax)** | ✅ "% Limit" slider |
| `WMaxLimPctRvrt` | RW | Reversion limit after timeout | Optional safety |
| `WMaxLimPctEnaRvrt` | RW | Enable reversion | Optional safety |
| `WMaxLimPctRvrtTms` | RW | Reversion timeout (seconds) | Optional safety |
| `WMaxLimPctRvrtRem` | R | Time remaining until reversion | Status |

**Scale Factor:** `WMaxLimPct_SF` - Typically -2 (divide by 100 for percentage)

---

## Dashboard "Power Capacity" Card Mapping

### Current Display

```
┌─ Power Capacity ──────────────────┐
│ Rated Charge        5 kW          │  ← WChaRteMaxRtg (read-only)
│ Rated Discharge     5 kW          │  ← WDisChaRteMaxRtg (read-only)
│ Controls            Active (Unlim)│  ← WMaxLimPctEna status
│                                    │
│ [Unlimited] [kW Limit] [% Limit]  │
│                                    │
│ No limits applied                 │
│ System will use rated maximums    │
└────────────────────────────────────┘
```

### What Each Tab Should Control

#### Tab 1: "Unlimited"
**Action:** Disable power limiting  
**SunSpec2 Write:**
```python
model_704.WMaxLimPctEna = 0  # Disable limiting
# Result: System uses full WChaRteMaxRtg / WDisChaRteMaxRtg
```

#### Tab 2: "kW Limit"
**Action:** Set absolute power limit in watts  
**SunSpec2 Write:**
```python
model_702.WChaRteMax = 2500     # Limit charge to 2.5kW
model_702.WDisChaRteMax = 3000  # Limit discharge to 3kW
```

**UI Design:**
```
┌─ kW Limit ────────────────────────┐
│ Charge Limit:    [====----] 2.5kW │
│ Discharge Limit: [=====---] 3.0kW │
│ [Apply Limits]                    │
└────────────────────────────────────┘
```

#### Tab 3: "% Limit"
**Action:** Set power limit as percentage of rated max  
**SunSpec2 Write:**
```python
model_704.WMaxLimPctEna = 1    # Enable limiting
model_704.WMaxLimPct = 5000    # 50% (scale factor -2 = 50.00%)
# Result: Limited to 50% of WMaxRtg (2.5kW if rated is 5kW)
```

**UI Design:**
```
┌─ % Limit ─────────────────────────┐
│ Power Limit:    [=====-----]  50% │
│                                   │
│ Max Power: 2.5kW (of 5kW rated)  │
│ [Apply Limit]                     │
└────────────────────────────────────┘
```

---

## Control Capabilities Analysis

### ✅ CAN Control (Confirmed Writable)

| Control | SunSpec2 Point | Model | Use Case |
|---------|---------------|-------|----------|
| **Limit charge power** | `WChaRteMax` | 702 | Slow charging during cheap power hours |
| **Limit discharge power** | `WDisChaRteMax` | 702 | Prevent high discharge during peak pricing |
| **Enable/disable limits** | `WMaxLimPctEna` | 704 | Quick toggle for unlimited mode |
| **Percentage limiting** | `WMaxLimPct` | 704 | Set % of max power (e.g., 50% = 2.5kW) |

### 🟡 MAYBE Control (Needs Testing)

| Control | Uncertainty | Risk |
|---------|-------------|------|
| **Charge vs Discharge direction** | Unclear if `WMaxLimPct` applies bidirectionally or only to discharge | Test required |
| **Interaction with operating mode** | Does limiting override Self-Consumption/TOU modes? | Could conflict |

### ❌ CANNOT Control (Missing Points)

| Control | Reason |
|---------|--------|
| **Force charge from grid** | No `ChaGriSet` equivalent (requires Model 124) |
| **Solar-only restriction** | No grid charging disable flag |
| **Standby/disconnect** | No battery connection control (requires Model 802) |

---

## Implementation Recommendations

### Phase 1: Power Capacity Card Enhancement (LOW RISK)

**Implement the three tabs showing in UI:**

1. **Unlimited Tab** (Current state)
   - Write `WMaxLimPctEna = 0`
   - Display: "No limits applied"

2. **kW Limit Tab** (NEW)
   - UI: Two sliders (charge, discharge)
   - Write: `WChaRteMax` and `WDisChaRteMax`
   - Range: 0 - WChaRteMaxRtg (5000W)

3. **% Limit Tab** (NEW)
   - UI: Single slider (applies to both)
   - Write: `WMaxLimPctEna = 1` and `WMaxLimPct = value * 100`
   - Range: 0-100%

**API Endpoints:**
```python
POST /api/power/limits
{
  "mode": "kw",  # or "percent" or "unlimited"
  "charge_limit_w": 2500,
  "discharge_limit_w": 3000
}

POST /api/power/limits/percent
{
  "limit_pct": 50  # 0-100
}

DELETE /api/power/limits  # Disable (unlimited mode)
```

### Phase 2: Test Write Operations (MEDIUM RISK)

**Test sequence (non-production system):**

```python
# Step 1: Read current values
model_702 = client.get_model(702)
current_charge_limit = model_702.WChaRteMax.value
current_discharge_limit = model_702.WDisChaRteMax.value

# Step 2: Write test (50% limit)
model_702.WChaRteMax.value = 2500    # 2.5kW
model_702.WDisChaRteMax.value = 2500  # 2.5kW
model_702.write()

# Step 3: Monitor actual power (Model 714)
model_714 = client.get_model(714)
actual_power = model_714.W.value  # Should not exceed 2500W

# Step 4: Revert to unlimited
model_704 = client.get_model(704)
model_704.WMaxLimPctEna.value = 0
model_704.write()
```

**Safety Checks:**
1. Read before write (confirm current state)
2. Validate limits are within `WChaRteMaxRtg` / `WDisChaRteMaxRtg`
3. Monitor actual power flow after write
4. Implement rollback on unexpected behavior

### Phase 3: MQTT HA Integration

**New entities:**

```python
# Power Limit Mode Select
"select.franklinwh_power_limit_mode":
    options: ["Unlimited", "kW Limit", "Percent Limit"]
    
# Charge Limit Number (kW mode)
"number.franklinwh_charge_limit_kw":
    min: 0, max: 5, step: 0.1, unit: "kW"
    
# Discharge Limit Number (kW mode)
"number.franklinwh_discharge_limit_kw":
    min: 0, max: 5, step: 0.1, unit: "kW"
    
# Percent Limit Number (% mode)  
"number.franklinwh_power_limit_percent":
    min: 0, max: 100, step: 1, unit: "%"
```

---

## Risk Assessment

| Operation | Risk | Mitigation |
|-----------|------|------------|
| Writing `WChaRteMax` / `WDisChaRteMax` | 🟡 MEDIUM | Test on non-production, validate within Rtg limits |
| Writing `WMaxLimPct` | 🟡 MEDIUM | Test with high value first (90%), then reduce |
| Conflict with operating mode | 🔴 HIGH | Monitor for mode changes, document interaction |
| Invalid limit values | 🟢 LOW | Validate against Rtg values before write |

---

## Open Questions

1. **Does `WMaxLimPct` control charge AND discharge, or only discharge?**
   - Test required: Apply limit, force charging, verify if limit applies

2. **What happens if `WMaxLimPct` conflicts with `WChaRteMax`?**
   - Which takes precedence? Or does firmware error?

3. **Do limits persist across power cycles?**
   - Test: Apply limit, restart inverter, check if still active

4. **Can we set charge and discharge independently with `WMaxLimPct`?**
   - Or does it apply symmetrically?

---

## Next Steps

1. ✅ Document Model 702/704 point capabilities (this document)
2. 🔲 Test write operations on non-production aGate
3. 🔲 Implement Power Capacity card tabs (Unlimited/kW/%)
4. 🔲 Add API endpoints for power limiting
5. 🔲 Create MQTT entities for HA integration
6. 🔲 Update implementation plan with confirmed capabilities

---

## References

- [Implementation Plan](/home/david/.gemini/antigravity/brain/a17c20ae-bda9-47cd-b5ca-89f4d9f6b5bc/implementation_plan.md)
- SunSpec Model 702: DER Capacity
- SunSpec Model 704: DER AC Controls
