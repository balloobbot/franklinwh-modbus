# Undocumented Modbus Address Validation Protocol

> **Purpose:** Establish a formal validation process for undocumented Modbus addresses discovered in FranklinWH systems  
> **Last Updated:** 2026-02-14  
> **Status:** Active Policy

---

## Overview

This document defines the **mandatory validation process** for any Modbus addresses discovered outside the SunSpec2 standard specification. All undocumented addresses **MUST** be verified and documented before inclusion in production code.

---

## Source of Truth

### Primary Documentation

**File:** [`franklinwh_modbus_extensions.md`](file:///home/david/dev/modbus/franklinwh_modbus_extensions.md)

This file is the **single source of truth** for all FranklinWH-specific Modbus extensions. Any address not documented here should be considered:
- Unverified
- Potentially unreliable
- Subject to change without notice

### Verification Tool

**Utility:** [`modbus_sunspec2_reader.py`](file:///home/david/dev/modbus/modbus_sunspec2_reader.py)

All documented addresses **MUST** produce consistent, expected values when read via this utility. Example:

```bash
# Verify address 15507 (Operating Mode)
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15507:1

# Expected output should show valid mode value (1-3)
```

---

## Validation Process

### Phase 1: Discovery

When an undocumented address is discovered:

1. **Document Initial Observation**
   - Create a timestamped observation record
   - Note the discovery method (dump analysis, testing, etc.)
   - Record initial values observed
   - Identify any patterns or correlations

2. **Search for Existing Documentation**
   ```bash
   # Check if address is already documented
   grep -r "15XXX" franklinwh_modbus_extensions.md
   grep -r "15XXX" REGISTER_ANALYSIS_*.md
   ```

3. **Check Address Space**
   - Verify address doesn't conflict with SunSpec2 models
   - Confirm address is in vendor extension range (typically 15000+, 16000+)

### Phase 2: Verification

**⚠️ MANDATORY: All undocumented addresses MUST be verified through at least TWO independent sources:**

#### Option A: Cross-Reference with FranklinWH API

Use the official FranklinWH Python client library:

```python
# File: franklinwh.client.py
from franklinwh.client import FranklinWHClient

client = FranklinWHClient(username="...", password="...")
# Compare API data with Modbus register values
# Document any correlations or discrepancies
```

**Verification Questions:**
- Does the API expose this data point?
- Do the values match between API and Modbus?
- What is the official name/label in the API?

#### Option B: Monitor FranklinWH Mobile App

Use packet capture or app analysis:

```bash
# Monitor app API calls (requires network capture)
# Look for corresponding data fields
# Document field names and value formats
```

**Verification Questions:**
- Does the mobile app display this value?
- What label does the app use?
- How does the app format/interpret the value?

#### Option C: Extended Monitoring

For addresses with dynamic values:

```bash
# Monitor over time to understand behavior
watch -n 5 'python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15XXX:1'

# Cross-reference with known values (SOC, Load, etc.)
# Look for mathematical relationships (e.g., value ÷ 10 = %)
```

**Document:**
- Value range observed (min/max)
- Correlation with other registers
- Units and scale factors
- Update frequency

### Phase 3: Testing

Before accepting an address as valid:

1. **Read Stability Test**
   ```bash
   # Verify address doesn't return random values
   for i in {1..10}; do
     python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15XXX:1
     sleep 2
   done
   ```

2. **Write Safety Test** (RW addresses only)
   ```bash
   # CRITICAL: Test with extreme caution
   # Use test_register_writability.py with --dry-run first
   python test_register_writability.py --host 192.168.0.110 \
     --start 15XXX --count 1 --dry-run
   ```

3. **Cross-Device Validation**
   - If multiple aGate devices available, verify address exists on all
   - Document any device-specific variations

### Phase 4: Documentation

Only after passing validation, document the address:

1. **Update Source of Truth**
   ```markdown
   # franklinwh_modbus_extensions.md
   
   | Address | Register | Access | Description | Verified |
   |---------|----------|--------|-------------|----------|
   | 15XXX   | NewReg   | R/RW   | Description | 2026-02-14 |
   ```

2. **Create Analysis Document** (if significant)
   ```bash
   # For major discoveries (new ranges, critical registers)
   # Create REGISTER_ANALYSIS_XXXXX.md
   ```

3. **Update Code Mappings**
   ```python
   # modbus_sunspec2_reader.py - known_map dictionary
   15XXX: ("RegName", "Description", "units", "R/RW"),
   ```

4. **Git Commit with Evidence**
   ```bash
   git commit -m "Add verified address 15XXX (Description)
   
   Verification:
   - Source: [Discovery method]
   - Correlated with: [API/App field]
   - Testing: [Date, observations]
   - Cross-checked: [Device models]"
   ```

---

## Rejection Criteria

**DO NOT document an address if:**

- ❌ Values are random or unstable
- ❌ Cannot verify with independent source (API/App)
- ❌ Address conflicts with SunSpec2 standard
- ❌ Writing causes system instability
- ❌ Purpose/meaning unclear after testing
- ❌ Values don't correlate with any observable system state

**Action:** Document in `REJECTED_ADDRESSES.md` with rationale

---

## Example: 16000 Range Validation

### Discovery
- **Date:** 2026-02-14
- **Method:** Raw register scan 16000:100
- **Observation:** Addresses 16000-16002 showed non-zero values

### Verification
```bash
# Monitor 16000 alongside known SOC
watch -n 5 '
  echo "16000: $(python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 16000:1 | grep 16000)"
  echo "15011 (SOC): $(python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15011:1 | grep 15011)"
'
```

**Results:**
- 16000 = 542 (when SOC ≈ 54%)
- 16001 = 20 (matches reserve SOC from 15508)
- 16002 = 20 (matches TOU reserve from 15509)

**Correlation:** ✅ Confirmed - 16000 tracks SOC, 16001/16002 mirror reserves

### Documentation
Created: [`REGISTER_ANALYSIS_16000.md`](file:///home/david/dev/modbus/REGISTER_ANALYSIS_16000.md)

**Status:** ✅ VERIFIED - Read-only status registers

---

## Historical Context: 15016/15017 Legacy Issue

### Problem
Addresses 15016/15017 were used in early code but later discovered to be **legacy aliases** for 15507/15508.

### Root Cause
- ❌ No verification process existed
- ❌ Dual addresses caused confusion
- ❌ Comments referenced both old and new addresses

### Resolution
- ✅ Established this validation protocol
- ✅ Documented correct addresses in source of truth
- ✅ Removed all legacy references
- ✅ Commits: 7b50226, 9fb4164

### Lesson Learned
> **Never assume undocumented addresses are stable or correct without verification through independent sources.**

---

## Address Ranges by Status

### ✅ Verified & Documented (Use These)

| Range | Purpose | Documentation |
|-------|---------|---------------|
| 40000-41000 | SunSpec2 Models | Official SunSpec2 spec |
| 15500-15513 | Primary FranklinWH Controls | `franklinwh_modbus_extensions.md` |
| 16000-16002 | SOC/Reserve Status (Read-Only) | `REGISTER_ANALYSIS_16000.md` |

### ⚠️ Observed But Unverified (Investigate)

| Range | Status | Notes |
|-------|--------|-------|
| 15000-15044 | Legacy/Diagnostic | Partially mapped, avoid use |
| 15514-15520 | Unknown | Sparse activity, needs investigation |

### ❌ Rejected (Do Not Use)

| Range | Reason | Date |
|-------|--------|------|
| 15016-15017 | Legacy aliases (use 15507-15508) | 2026-02-14 |

---

## Automation Opportunities

### Future Enhancements

1. **Automated Cross-Reference Script**
   ```bash
   # Compare Modbus values with franklinwh.client API
   # Generate correlation report
   ```

2. **Continuous Validation**
   ```bash
   # Scheduled job to verify documented addresses
   # Alert on unexpected value changes
   ```

3. **Discovery Scanner**
   ```bash
   # Systematic scan of vendor address ranges
   # Flag new non-zero addresses for investigation
   ```

---

## Checklist Template

Use this checklist when validating a new address:

```markdown
## Address: 15XXX Validation

- [ ] Discovery documented with evidence
- [ ] Address doesn't conflict with SunSpec2
- [ ] Cross-referenced with FranklinWH API/App
- [ ] Values stable across multiple reads
- [ ] Correlates with observable system behavior
- [ ] Units/scale factor identified
- [ ] Read/Write access confirmed
- [ ] Testing completed (if RW)
- [ ] Added to franklinwh_modbus_extensions.md
- [ ] Code mapping updated
- [ ] Git commit with verification details
```

---

## Contact & Updates

For questions or to propose updates to this protocol:
- **File Issues:** Document discrepancies in `TODO_*.md` files
- **Propose Changes:** Submit with evidence + testing results

**This is a living document** - update as validation methods improve.

---

*Established 2026-02-14 following the 15016/15017 legacy address confusion incident*
