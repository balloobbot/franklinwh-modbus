# Requirements: SoC Validation & Target Conflict Detection

**Date:** 2026-03-01  
**Status:** Draft for Review  
**Priority:** High - Safety Critical

---

## 1. Scope

This document defines validation requirements for State of Charge (SoC) operations in the FranklinWH Modbus Battery Manager, including:

- Target SoC validation for charge/discharge operations
- Sanity checks against current SoC
- Reserve SoC conflict detection based on OnGridMode
- Safety limits and operational boundaries

---

## 2. Definitions

| Term | Definition |
|------|------------|
| **SoC** | State of Charge - battery charge level (0-100%) |
| **Current SoC** | Actual battery charge level from Model 713 |
| **Target SoC** | Desired SoC to reach during operation |
| **Reserve SoC** | Minimum SoC reserved for backup (per OnGridMode) |
| **Self Reserve** | Reserve % for Self-Consumption mode (reg 15508) |
| **TOU Reserve** | Reserve % for Time-of-Use mode (reg 15509) |
| **OnGridMode** | aGate operating mode (reg 15507): 1=Backup, 2=Self, 3=TOU |
| **WSetEna** | Modbus control enable flag (1=active, 0=cloud) |

---

## 3. Use Cases

### UC-1: Direct Charge with Target SoC
**Actor:** User via CLI (`--charge X --target-soc-auto Y`)  
**Precondition:** Battery at SoC Z, OnGridMode = Self-Consumption  
**Flow:**
1. User requests charge at 3000W until SoC 95%
2. System validates target > current SoC
3. System checks target >= Self Reserve (20%)
4. System starts charging
5. System monitors SoC every 5s
6. System stops when SoC >= 95%

### UC-2: Direct Discharge with Target SoC
**Actor:** User via CLI (`--discharge X --target-soc-auto Y`)  
**Precondition:** Battery at SoC Z, OnGridMode = Self-Consumption  
**Flow:**
1. User requests discharge at 3000W until SoC 30%
2. System validates target < current SoC
3. System checks target >= Self Reserve (20%)
4. System starts discharging
5. System monitors SoC every 5s
6. System stops when SoC <= 30%

### UC-3: Virtual Mode with Target SoC
**Actor:** User via CLI (`--mode self_consumption --target-soc 90`)  
**Precondition:** OnGridMode = Self-Consumption  
**Flow:**
1. User sets self-consumption mode with target 90%
2. System validates target > current SoC
3. System validates target >= Self Reserve (15508 value)
4. System runs mode until target reached or mode changed

### UC-4: Emergency Backup Mode
**Actor:** User via CLI (`--mode emergency_backup --target-soc 95`)  
**Precondition:** OnGridMode = Emergency Backup  
**Flow:**
1. User requests emergency backup with target 95%
2. System validates target > current SoC
3. No reserve check (emergency mode prioritizes backup)
4. System charges to target

---

## 4. Functional Requirements

### FR-1: Target SoC Range Validation
**Priority:** Critical  
**Description:** All target SoC values must be within valid range.

**Rules:**
- Target SoC must be between 10% and 100%
- Target SoC must be numeric (integer or float)
- Target SoC precision: 1 decimal place maximum

**Validation Matrix:**

| Target Value | Valid | Error Message |
|--------------|-------|---------------|
| 0-9% | ❌ | "Target SoC must be >= 10%" |
| 10-100% | ✅ | - |
| 101%+ | ❌ | "Target SoC must be <= 100%" |
| Non-numeric | ❌ | "Target SoC must be a number" |
| Negative | ❌ | "Target SoC must be positive" |

### FR-2: Target vs Current SoC Sanity Check
**Priority:** Critical  
**Description:** Target must be achievable from current SoC.

**Rules:**
- For CHARGE: Target must be > Current SoC
- For DISCHARGE: Target must be < Current SoC
- For STANDBY: No target validation needed

**Validation Matrix:**

| Operation | Current | Target | Valid | Action |
|-----------|---------|--------|-------|--------|
| Charge | 50% | 60% | ✅ | Proceed |
| Charge | 50% | 50% | ⚠️ | Warning: "Already at target" |
| Charge | 50% | 40% | ❌ | Error: "Target < current for charge" |
| Discharge | 50% | 40% | ✅ | Proceed |
| Discharge | 50% | 50% | ⚠️ | Warning: "Already at target" |
| Discharge | 50% | 60% | ❌ | Error: "Target > current for discharge" |

### FR-3: Reserve SoC Conflict Detection ✅ IMPLEMENTED
**Priority:** High  
**Status:** ✅ **IMPLEMENTED** (2026-03-01)  
**Implementation:** `controller.py:get_effective_reserve_level()`, `validate_target_soc()`  
**Description:** Target must respect OnGridMode reserve settings.

**Rules by OnGridMode:**

#### OnGridMode = 1 (Emergency Backup)
- No reserve enforcement (full capacity available for backup)
- Target can be any value 10-100%
- Warning if target < 20% ("Low backup capacity")

#### OnGridMode = 2 (Self-Consumption)
- Must respect Self Reserve (reg 15508)
- Target must be >= Self Reserve + 5% margin
- Default Self Reserve: 20% if reg 15508 unreadable

#### OnGridMode = 3 (Time-of-Use)
- Must respect TOU Reserve (reg 15509)
- Target must be >= TOU Reserve + 5% margin
- Default TOU Reserve: 20% if reg 15509 unreadable

**Validation Matrix:**

| OnGridMode | Reserve | Target | Valid | Action |
|------------|---------|--------|-------|--------|
| Emergency | N/A | 15% | ⚠️ | Warning: "Low backup capacity" |
| Emergency | N/A | 95% | ✅ | Proceed |
| Self-Con | 20% | 25% | ✅ | Proceed |
| Self-Con | 20% | 22% | ⚠️ | Warning: "Target close to reserve" |
| Self-Con | 20% | 18% | ❌ | Error: "Target < Self Reserve (20%)" |
| TOU | 30% | 35% | ✅ | Proceed |
| TOU | 30% | 28% | ❌ | Error: "Target < TOU Reserve (30%)" |

### FR-4: Safety Margin Enforcement ✅ IMPLEMENTED
**Priority:** High  
**Status:** ✅ **IMPLEMENTED** (2026-03-01)  
**Implementation:** `controller.py:SAFETY_MARGIN_PCT = 5`, `validate_soc_safety()`  
**Description:** Maintain minimum operational margin above reserve.

**Rules:**
- Minimum 5% margin between target and reserve
- Formula: `target >= reserve + 5%`
- Exception: Emergency mode (no reserve)

**Example:**
- Self Reserve = 20%
- Minimum target = 25%
- Target = 22% → Warning (only 2% margin)
- Target = 18% → Error (below reserve)

### FR-5: aGate Native Mode Conflict Detection
**Priority:** High  
**Description:** Detect conflicts with aGate Cloud API control.

**Conflict Scenarios:**

| aGate State | Requested Action | Conflict? | Action |
|-------------|------------------|-----------|--------|
| Self-Con charging | User charge | ✅ Yes | Block or warn |
| Self-Con charging | User discharge | ✅ Yes | Block or warn |
| Self-Con idle | User charge | ⚠️ Maybe | Warn |
| Self-Con idle | User discharge | ⚠️ Maybe | Warn |
| Emergency charging | User charge | ✅ Yes | Block |
| TOU active | Any control | ✅ Yes | Block |
| WSetEna=1 (Modbus) | Any control | ⚠️ Maybe | Warn of override |

**Resolution:**
- Use `--reset-on-start` to force Modbus takeover
- Use `--assume-clean-state` to skip conflict check (advanced)
- User changes OnGridMode via FranklinWH app first

### FR-6: Off-Grid Operation Safety
**Priority:** Critical  
**Description:** Prevent unsafe operations when grid is disconnected.

**Rules:**
- Check grid connection state before any control operation
- Block charge/discharge if grid disconnected
- Allow only with explicit `--off-grid-permitted` flag
- Warning: "Operating off-grid can be unsafe"

**Validation:**
- Grid connected: ConnSt == 'Connected' AND voltage 180-270V
- Grid disconnected: Block unless `--off-grid-permitted`

### FR-7: SoC Monitoring & Auto-Stop
**Priority:** Critical  
**Description:** Continuously monitor SoC during target operations.

**Requirements:**
- Poll SoC every 5 seconds
- Check if target reached
- Stop operation when target reached
- Release control (WSetEna=0)
- Log stop reason

**Stop Conditions:**
1. Target SoC reached (primary)
2. Duration limit reached (if specified)
3. User interrupt (Ctrl+C)
4. Alarm condition (blocking alarm detected)
5. Grid disconnect (unless permitted)

---

## 5. Traceability Matrix

| Req ID | Use Case | CLI Flag | Library Method | Validation Type | Priority |
|--------|----------|----------|----------------|-----------------|----------|
| FR-1 | All | `--target-soc-auto` | `send_command()` | Range check | Critical |
| FR-2 | UC-1, UC-2 | `--charge`, `--discharge` | `check_state()` | Sanity check | Critical |
| FR-3 | UC-1, UC-2, UC-3 | `--target-soc-auto` | `read_native_mode()` | Conflict check | High |
| FR-4 | UC-1, UC-2 | `--target-soc-auto` | `check_state()` | Safety margin | High |
| FR-5 | All | `--mode` | `check_state()` | Conflict detection | High |
| FR-6 | All | `--off-grid-permitted` | `read_grid_status()` | Safety check | Critical |
| FR-7 | UC-1, UC-2 | `--target-soc-auto` | Custom loop | Monitoring | Critical |

---

## 6. Implementation Status

| Feature | CLI | Library | Tests | Status |
|---------|-----|---------|-------|--------|
| FR-1: Range validation | ✅ | ✅ | ⚠️ | Partial |
| FR-2: Target vs Current | ✅ | ✅ | ⚠️ | Partial |
| FR-3: Reserve conflict | ❌ | ⚠️ | ❌ | Not implemented |
| FR-4: Safety margin | ❌ | ❌ | ❌ | Not implemented |
| FR-5: aGate conflict | ✅ | ✅ | ⚠️ | Partial |
| FR-6: Off-grid check | ✅ | ✅ | ✅ | Implemented |
| FR-7: Auto-stop | ✅ | ❌ | ⚠️ | CLI only |

**Legend:**
- ✅ Implemented
- ⚠️ Partial implementation
- ❌ Not implemented

---

## 7. Error Messages

Standardized error/warning messages:

### Errors (Block Operation)
```
E001: "Target SoC {target}% is outside valid range (10-100%)"
E002: "Target SoC {target}% < Current SoC {current}% for charge operation"
E003: "Target SoC {target}% > Current SoC {current}% for discharge operation"
E004: "Target SoC {target}% < Self Reserve {reserve}% (OnGridMode=Self-Consumption)"
E005: "Target SoC {target}% < TOU Reserve {reserve}% (OnGridMode=Time-of-Use)"
E006: "Off-grid operation not permitted. Use --off-grid-permitted to override."
E007: "Blocking alarms detected: {alarms}. Cannot proceed."
E008: "aGate Cloud API conflict: {conflict}. Use --reset-on-start to override."
```

### Warnings (Allow with Confirmation)
```
W001: "Target SoC {target}% is close to Reserve {reserve}% (margin < 5%)"
W002: "Already at target SoC {current}%. No operation needed."
W003: "aGate Cloud API conflict detected: {conflict}"
W004: "Off-grid operation permitted via flag. Safety limits apply."
W005: "Target SoC {target}% provides low backup capacity for Emergency mode."
```

---

## 8. Test Cases

### TC-1: Valid Charge Target
```
Given: SoC=50%, OnGridMode=Self-Consumption, Self Reserve=20%
When: --charge 3000 --target-soc-auto 80
Then: Operation proceeds, stops at 80%
```

### TC-2: Invalid Charge Target (Below Current)
```
Given: SoC=50%, OnGridMode=Self-Consumption
When: --charge 3000 --target-soc-auto 40
Then: Error E002, operation blocked
```

### TC-3: Invalid Target (Below Reserve)
```
Given: SoC=50%, OnGridMode=Self-Consumption, Self Reserve=20%
When: --charge 3000 --target-soc-auto 15
Then: Error E004, operation blocked
```

### TC-4: Target Close to Reserve
```
Given: SoC=50%, OnGridMode=Self-Consumption, Self Reserve=20%
When: --charge 3000 --target-soc-auto 22
Then: Warning W001, operation proceeds with warning
```

### TC-5: Conflict with Cloud API
```
Given: aGate actively charging in Self-Con mode
When: --charge 3000 --target-soc-auto 90
Then: Error E008, operation blocked
```

### TC-6: Force Override Conflict
```
Given: aGate actively charging in Self-Con mode
When: --charge 3000 --target-soc-auto 90 --reset-on-start
Then: Warning W003, operation proceeds
```

### TC-7: Off-Grid Blocked
```
Given: Grid disconnected
When: --charge 3000 --target-soc-auto 90
Then: Error E006, operation blocked
```

### TC-8: Off-Grid Permitted
```
Given: Grid disconnected
When: --charge 3000 --target-soc-auto 90 --off-grid-permitted
Then: Warning W004, operation proceeds
```

---

## 9. Open Questions

1. **Q:** Should we allow target = current (no-op) or require target != current?  
   **A:** Allow with warning (W002)

2. **Q:** What margin is appropriate for reserve safety?  
   **A:** 5% minimum (configurable?)

3. **Q:** Should emergency mode enforce any minimum SoC?  
   **A:** Warning only (W005), no enforcement

4. **Q:** How to handle unreadable reserve registers (15508/15509)?  
   **A:** Use default 20%, log warning

5. **Q:** Should target SoC persist across sessions?  
   **A:** No, each operation is independent

---

*Document Version: 1.0-Draft*  
*Next Review: After implementation of FR-3, FR-4*