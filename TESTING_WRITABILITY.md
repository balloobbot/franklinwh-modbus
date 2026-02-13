# Safe Register Writability Testing Guide

## ⚠️ MANDATORY: Virtual Environment Required

**ALL Python scripts in this project MUST be run inside a virtual environment.**

This is required to:
- Avoid PEP 668 externally-managed-environment errors
- Ensure dependency isolation
- Prevent system-level Python conflicts

### Setup Virtual Environment (One-Time)

```bash
cd /home/david/dev/modbus

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install pymodbus
```

### Activate Before Every Use

```bash
cd /home/david/dev/modbus
source venv/bin/activate  # Always activate before running scripts
```

**Indicator:** Your prompt should show `(venv)` when activated.

---

## Purpose

Discover which registers in the **undocumented 15000-15044 range** are writable (RW) vs read-only (R) by safely testing write operations.

## The Safe Method

**Read → Write-Back-Same → Verify**

1. Read current value from register
2. Write the EXACT same value back
3. Verify the value didn't change unexpectedly

This minimizes risk since we're not changing anything (in theory).

---

## ⚠️ Safety Warnings

### Even "Safe" Testing Has Risks

**Writing the same value back can still trigger:**
- State machine transitions
- Command execution (if register is a "trigger")
- Watchdog resets
- Unexpected hardware behavior

**Example Dangerous Registers:**
- **15016:** Operating mode (writing 2 might restart battery controller)
- **15017:** Reserve SOC (might trigger recalibration)
- **Unknown registers:** Could be write-only commands

### Recommended Exclusions

**DO NOT TEST the following (known to be critical):**
- `15016` - Operating mode (legacy alias of 15507)
- `15017` - Reserve SOC (legacy alias of 15508)
- `15020` - Battery rated Wh (likely configuration)
- `15040` - Unknown but consistently non-zero (possible state)

---

## Using the Test Script

### Installation & Virtual Environment Setup

```bash
cd /home/david/dev/modbus

# MANDATORY: Activate virtual environment
source venv/bin/activate

# Verify activation (should show (venv) in prompt)
# Install pymodbus if not already installed
pip install pymodbus

# Make script executable
chmod +x test_register_writability.py
```

### Basic Usage

#### 1. Dry Run (Safest - No Writes)
```bash
# MANDATORY: Activate venv first
source venv/bin/activate

# See what WOULD be tested without actually writing
python test_register_writability.py -i 192.168.0.110 --range 15000:15044 --dry-run
```

#### 2. Test Single Register
```bash
# Test one register at a time
python test_register_writability.py -i 192.168.0.110 --test 15011
```

**Output:**
```
✅ Connected to 192.168.0.110:502

🔍 Testing 15011:
   📖 Read: 566 (0x0236)
   ✍️  Writing back: 566...
   ❌ READ-ONLY

Result: READ_ONLY
🔒 Register 15011 is READ-ONLY
```

#### 3. Test Range with Exclusions (Recommended)
```bash
# Test 15000-15044, skip dangerous ones
python test_register_writability.py -i 192.168.0.110 \
    --range 15000:15044 \
    --exclude 15016,15017,15020,15040
```

**Output:**
```
======================================================================
Testing Registers: 15000 to 15044
Excluding: [15016, 15017, 15020, 15040]
Mode: LIVE TEST
======================================================================

🔍 Testing 15000:
   📖 Read: 0 (0x0000)
   ✍️  Writing back: 0...
   🔒 READ-ONLY
   
🔍 Testing 15001:
   📖 Read: 0 (0x0000)
   ✍️  Writing back: 0...
   🔒 READ-ONLY

... (continues for all registers)

======================================================================
SUMMARY
======================================================================
Writable:   2
Read-Only:  38
Errors:     0
======================================================================

📝 WRITABLE REGISTERS:
==================================================
  15016 = 2 (0x0002)  [SKIPPED - excluded]
  15043 = 1 (0x0001)
==================================================
```

---

## Interpretation Guide

### Test Results

| Status | Meaning | Next Steps |
|--------|---------|------------|
| **WRITABLE** | Write succeeded, value unchanged | Register is RW - use with caution |
| **READ-ONLY** | Write failed (Modbus error) | Register is R - safe to ignore |
| **CHANGED** | Write succeeded but value changed! | **DANGER** - Register is command/trigger |
| **READ_ERROR** | Can't read register | Register doesn't exist or protected |
| **WRITE_ERROR** | Read OK, write failed badly | Unexpected error - investigate |

### Expected Results for Known Registers

Based on your scan:

| Address | Expected | Value | Notes |
|---------|----------|-------|-------|
| 15011 | READ-ONLY | 566 | SOC? (56.6%) - should be read-only |
| 15016 | WRITABLE | 2 | Operating mode (EXCLUDED - dangerous) |
| 15017 | WRITABLE | 20 | Reserve SOC (EXCLUDED - dangerous) |
| 15036 | READ-ONLY | 962 | SoH (96.2%) - should be read-only |
| 15043 | Unknown | 1 | Consistently 1 - maybe flag/config? |

---

## Recommended Testing Plan

### Phase 1: Reconnaissance (Dry Run)
```bash
# No actual writes - just verify script works
python test_register_writability.py -i 192.168.0.110 \
    --range 15000:15044 --dry-run
```

### Phase 2: Safe Registers Only (Read-Only Values)
Test registers that appear to be sensor readings (should all be READ-ONLY):

```bash
# Test registers that look like sensor data
python test_register_writability.py -i 192.168.0.110 --test 15011  # SOC?
python test_register_writability.py -i 192.168.0.110 --test 15036  # SoH
python test_register_writability.py -i 192.168.0.110 --test 15003  # PV Power?
```

**Expected:** All should be READ-ONLY

### Phase 3: Unknown Registers (Cautious)
Test registers with unknown purpose:

```bash
# Test unknowns one at a time
python test_register_writability.py -i 192.168.0.110 --test 15000
python test_register_writability.py -i 192.168.0.110 --test 15043
```

**Watch for:** CHANGED status (indicates command/trigger)

### Phase 4: Full Scan (Production System - SKIP)
```bash
# DO NOT RUN on production unless you're ready for consequences
python test_register_writability.py -i 192.168.0.110 \
    --range 15000:15044 \
    --exclude 15016,15017,15020,15040
```

---

## Safety Checklist

Before testing:
- [ ] Confirm aGate is NOT in critical operation (e.g., during power outage)
- [ ] Verify battery SOC > 80% (in case write triggers unexpected behavior)
- [ ] Note current operating mode and reserve SOC
- [ ] Have ability to restart aGate if needed
- [ ] Start with **dry run** mode
- [ ] Test **one register at a time** on first pass
- [ ] Exclude known critical registers (15016, 15017)

After testing:
- [ ] Verify battery still operates normally
- [ ] Check operating mode hasn't changed
- [ ] Verify reserve SOC is still correct
- [ ] Monitor for unexpected behavior over next hour

---

## What to Do If Something Goes Wrong

### Symptom: Operating Mode Changed
```bash
# Read current mode
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15507:1

# If wrong, set back to TOU (3) or Self-Consumption (2)
python modbus_sunspec2_readwrite.py -i 192.168.0.110 --write 15507:3
```

### Symptom: Reserve SOC Changed
```bash
# Read current reserve
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15508:2

# If wrong, set back to desired % (e.g., 20%)
python modbus_sunspec2_readwrite.py -i 192.168.0.110 --write 15508:20
python modbus_sunspec2_readwrite.py -i 192.168.0.110 --write 15509:20
```

### Symptom: Battery Not Responding
1. Wait 2 minutes (may be rebooting)
2. Power cycle aGate (if safe to do so)
3. Contact FranklinWH support if still unresponsive

---

## Expected Findings

Based on register analysis, we expect:

**Likely READ-ONLY (sensor data):**
- 15003 - PV output power
- 15011 - SOC
- 15020 - Battery rated Wh
- 15036 - SoH
- All zero-value registers (15000-15002, 15004-15010, etc.)

**Likely WRITABLE (configuration):**
- 15016 - Operating mode ⚠️
- 15017 - Reserve SOC ⚠️
- 15043 - Unknown flag/config?

**Unknown:**
- 15040 - Consistently 1526 (decimal) - purpose unclear

---

## Documentation After Testing

After completing tests, update **`TODO_MODBUS_ADDRESS_MISMATCH.md`** with:

1. **Confirmed writable registers** and their ranges
2. **Confirmed read-only registers**
3. **Any unexpected behavior** observed
4. **Recommended safe/unsafe register lists**

This will help future development distinguish between:
- Safe monitoring registers (read-only)
- Control registers (writable, requires validation)
- Dangerous registers (exclusion list)

---

## Example Complete Test Session

```bash
# Step 1: Dry run
python test_register_writability.py -i 192.168.0.110 --range 15000:15044 --dry-run

# Step 2: Test known read-only (should all fail to write)
python test_register_writability.py -i 192.168.0.110 --test 15011
python test_register_writability.py -i 192.168.0.110 --test 15036

# Step 3: Test unknown register
python test_register_writability.py -i 192.168.0.110 --test 15043

# Step 4: Full scan (excluding critical)
python test_register_writability.py -i 192.168.0.110 \
    --range 15000:15044 \
    --exclude 15016,15017,15020,15040

# Step 5: Verify system still healthy
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15507:3
```

---

## References

- [`modbus_sunspec2_reader.py`](file:///home/david/dev/modbus/modbus_sunspec2_reader.py) - Read utility
- [`modbus_sunspec2_readwrite.py`](file:///home/david/dev/modbus/modbus_sunspec2_readwrite.py) - Write utility
- [`TODO_MODBUS_ADDRESS_MISMATCH.md`](file:///home/david/dev/modbus/TODO_MODBUS_ADDRESS_MISMATCH.md) - Address documentation
- [`franklinwh_modbus_extensions.md`](file:///home/david/dev/modbus/franklinwh_modbus_extensions.md) - Source of truth (15500-15513)
