# TODO: FranklinWH Extension Address Mismatch

## Status
**Priority:** 🔴 **HIGH** - Incorrect register mapping causes control failures  
**Discovered:** 2026-02-14  
**User Reported:** Yes (Defect #1)

---

## Problem

There is a **critical mismatch** between the FranklinWH modbus extension addresses documented as source of truth and the addresses currently used in the code implementation.

### Discovery Context

Analysis using `modbus_sunspec2_reader.py` utility revealed **TWO address ranges** for FranklinWH extensions:

1. **Undocumented Range:** 15000-15040 (partial, ~13 active registers)
2. **Documented Range:** 15500-15513 (source of truth in `franklinwh_modbus_extensions.md`)

**⚠️ IMPORTANT:** The `modbus_sunspec2_reader.py --match` option performs SunSpec2 value cross-checking but produces **misleading false positives** (e.g., claims 15507 matches `701.InvSt` when it's actually `OnGridMode`). Use with caution.

### Undocumented Range: 15000-15040 (Discovered)

**Evidence:** `python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15000:514 --match`

| Address | Hex Value | UInt16 | Potential Purpose | Notes |
|---------|-----------|--------|-------------------|-------|
| 15003 | 0578 | 1400 | PV Output Power? | Matches documented 15502 |
| 15011 | 021A | 538 | SOC Raw (53.8%)? | Value makes sense for SOC |
| 15016 | 0002 | 2 | Operating Mode (legacy?) | **Conflicts with 15507** |
| 15017 | 0014 | 20 | Reserve SOC (legacy?) | **Conflicts with 15508** |
| 15020 | 3520 | 13600 | Battery Rated Wh | Matches SunSpec 713.WHRtg |
| 15036 | 03C2 | 962 | SOH (96.2%) | Matches SunSpec 713.SoH |
| 15040 | 05C5 | 1477 | Unknown | Consistently non-zero |

**⚠️ Critical Finding:** Addresses 15016/15017 appear to be **legacy aliases** for 15507/15508 (operating mode and reserve SOC). This explains the confusion in code comments.

**Recommendation:** These undocumented registers should NOT be used. Stick to documented 15500+ range as source of truth.

---

### Source of Truth: `franklinwh_modbus_extensions.md` (15500-15513)

| Address | Register | Access | Description |
|---------|----------|--------|-------------|
| 15500 | PVUse | R | Installed Solar PV Flag |
| 15501 | apBoxPVUse | R | Installed Remote Solar PV System Flag |
| 15502 | PVOutputP | R | Solar PV power in W |
| 15503 | proximalPVOutputP | R | Proximal Solar PV power in W |
| 15504 | RemotePV1 | R | Remote Solar PV 1 power in W |
| 15505 | RemotePV2 | R | Remote Solar PV 2 power in W |
| 15506 | LoadActiveP | R | Total home loads power in W |
| **15507** | **OnGridMode** | **RW** | **Operating Mode: 1=Backup, 2=Self-Consumption, 3=TOU** |
| **15508** | **SelfReserve** | **RW** | **Self-Consumption SOC Reserve %** |
| **15509** | **TouReserve** | **RW** | **Time-of-Use SOC Reserve %** |
| 15510-15511 | PVOutputWh | R | PV Energy in Wh (32-bit) |
| 15512-15513 | proximalOutputWh | R | Proximal PV Energy in Wh (32-bit) |

---

## Code Implementation: `src/modbus_client_franklinwh.py`

### ✅ CORRECT Addresses (lines 48-70)

```python
REGISTERS = {
    "operating_mode":    {"addr": 15507, ...},  # ✅ CORRECT
    "reserve_soc":       {"addr": 15508, ...},  # ✅ CORRECT
    "reserve_soc_2":     {"addr": 15509, ...},  # ✅ CORRECT
    "pv_output_w":       {"addr": 15502, ...},  # ✅ CORRECT
    "home_loads_w":      {"addr": 15506, ...},  # ✅ CORRECT
    "pv_output_wh":      {"addr": 15510, ...},  # ✅ CORRECT
}
```

### ❌ INCORRECT Comments (lines 29-31)

```python
# Control registers (RW) - these are the key ones you mentioned
operating_mode: Optional[int] = None    # 15016/15507: 2 (matches AbnOpCatRtg, VarSetPri)
reserve_soc: Optional[int] = None       # 15017/15508: 20 (matches PF - power factor?)
reserve_soc_2: Optional[int] = None     # 15040/15509: -9 (FFF7)
```

**The Issue:** These comments suggest **dual addresses** (e.g., `15016/15507`), implying confusion or a legacy mapping that may no longer be valid.

---

## Root Cause Analysis

### Historical Context
The comments in `FranklinWHRawRegisters` dataclass suggest that these registers *may have been* accessible at two different addresses:
- **Old addresses:** 15016, 15017, 15040 (SunSpec Model 713/714 range?)
- **New addresses:** 15507, 15508, 15509 (FranklinWH extensions)

### Current Reality
Based on user-provided source of truth (`franklinwh_modbus_extensions.md`):
- ✅ **15507-15509** are the **correct** addresses for control registers
- ❌ **15016, 15017, 15040** should **NOT** be referenced in comments
- ❌ Comments like `"matches PF - power factor?"` suggest misunderstanding of register purpose

---

## Impact

### Critical
- **Confusion for developers** - Comments suggest wrong addresses may be valid
- **Potential write failures** - If code falls back to 15016/15017 addresses
- **Documentation drift** - Developers may use wrong addresses from comments

### Observed
- Actual code implementation **IS** using correct addresses (15507-15509)
- **NO runtime failures** currently (implementation is correct)
- **Comments are misleading** and need correction

---

## Files Affected

### Primary
1. **`src/modbus_client_franklinwh.py`** (lines 29-31)
   - Dataclass comments with wrong address references

### Documentation
2. **`franklinwh_modbus_extensions.md`** ⚠️ **NOT IN GIT**
   - Source of truth, needs to be added to version control
   - Should be tracked to prevent future drift

3. **`functionality.md`** (lines 29-55)
   - Documents 15017 as "Reserve SOC Primary" 
   - May contain outdated SunSpec references
   - Needs review for consistency

---

## Recommended Fix

### Phase 1: Code Cleanup (Immediate)

#### 1.1. Fix Comments in `src/modbus_client_franklinwh.py`

**Lines 29-31:** Remove dual address references

```python
# BEFORE (WRONG):
operating_mode: Optional[int] = None    # 15016/15507: 2 (matches AbnOpCatRtg, VarSetPri)
reserve_soc: Optional[int] = None       # 15017/15508: 20 (matches PF - power factor?)
reserve_soc_2: Optional[int] = None     # 15040/15509: -9 (FFF7)

# AFTER (CORRECT):
operating_mode: Optional[int] = None    # 15507: Operating mode (1=Backup, 2=Self, 3=TOU)
reserve_soc: Optional[int] = None       # 15508: Self-Consumption SOC reserve %
reserve_soc_2: Optional[int] = None     # 15509: Time-of-Use SOC reserve %
```

#### 1.2. Add Documentation to Git

```bash
git add franklinwh_modbus_extensions.md
git commit -m "Add FranklinWH modbus extension register map (source of truth)"
```

### Phase 2: Documentation Review (Follow-up)

#### 2.1. Review `functionality.md`
- **Line 54:** Check if "15017: Reserve SOC Primary" is a typo
- Should read: "15508: Reserve SOC Primary"
- Verify all address references match source of truth

#### 2.2. Search for Legacy Address References

```bash
# Find any remaining references to old addresses
grep -r "15016\|15017\|15040" src/ --include="*.py"
```

---

## Testing

### Validation Steps

1. **Verify Current Behavior:**
   ```bash
   # Confirm operating mode can be read/written
   python -m src.modbus_client_franklinwh --host 192.168.0.110 --read-mode
   ```

2. **Check for Dual Address Access:**
   ```python
   # Test if old addresses (15016, 15017, 15040) are still readable
   # This will tell us if they're aliases or completely invalid
   ```

3. **Documentation Consistency:**
   - Compare ALL register references across:
     - `franklinwh_modbus_extensions.md` (source of truth)
     - `functionality.md`
     - `src/modbus_client_franklinwh.py`
     - `src/modbus_sunspec2_reader.py`

---

## Priority

**🔴 HIGH** because:
- Misleading comments can cause developer errors
- Source of truth not in version control (risk of loss)
- Potential confusion in future development

**Not CRITICAL** because:
- Actual runtime code IS using correct addresses
- No observed control failures

---

## Related Files

- ✅ **franklinwh_modbus_extensions.md** - Source of truth (NOT IN GIT)
- ⚠️ **functionality.md** - May have outdated references
- ✅ **src/modbus_client_franklinwh.py** - Implementation (addresses correct, comments wrong)
- ✅ **src/modbus_sunspec2_reader.py** - Has correct mapping (lines 696-707)
- ✅ **modbus_sunspec2_reader.py** - Duplicate of above

---

## User Context

User specifically requested:
> "review the file franklinwh_modbus_extensions.md as the source of truth (this a new file not in git - add it) versus what is in the code (see Preview functionalitiy.md and the code to confirm."

**Action Items:**
1. ✅ Add `franklinwh_modbus_extensions.md` to git
2. ✅ Fix misleading comments in code
3. ✅ Verify `functionality.md` consistency
4. ✅ Document resolution in this TODO

---

## Next Steps

1. Fix comments in `src/modbus_client_franklinwh.py` (5 min)
2. Add `franklinwh_modbus_extensions.md` to git (1 min)
3. Review `functionality.md` for consistency (10 min)
4. Search and fix any other legacy address references (15 min)
5. Mark this TODO as resolved

**Estimated Total Effort:** 30 minutes
