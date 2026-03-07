# Modbus SunSpec2 Reader Utility

**File:** `modbus_sunspec2_reader.py` (root) / `src/modbus_sunspec2_reader.py` (module)  
**Purpose:** Multi-purpose Modbus diagnostic and exploration tool for SunSpec2 devices

---

## Overview

This utility provides comprehensive Modbus register inspection capabilities for FranklinWH aGates and other SunSpec2-compliant devices. It can:

1. Query SunSpec2 models and info-points
2. Read raw register addresses (including undocumented extensions)
3. Cross-reference values against known SunSpec2 definitions
4. Export data for analysis

---

## Key Features

### ✅ SunSpec2 Model Discovery
- Auto-discovers all implemented SunSpec2 models
- Displays model info-points with scaled values
- Shows data types, units, and access modes

### ✅ Raw Register Reading
- Read arbitrary address ranges outside SunSpec2 models
- Useful for reverse-engineering undocumented registers
- Multiple display formats (hex, uint16, int16, binary)

### ✅ Value Cross-Matching
- `--match` option compares raw values against SunSpec2 database
- **⚠️ WARNING:** Produces false positives - use cautiously

---

## Usage

### Basic SunSpec2 Query
```bash
# Read all SunSpec2 models
python modbus_sunspec2_reader.py -i 192.168.0.110 -t 5

# Read specific model (e.g., Battery Model 713)
python modbus_sunspec2_reader.py -i 192.168.0.110 -m 713
```

### Raw Register Reading
```bash
# Read FranklinWH extensions (15500-15513)
python modbus_sunspec2_reader.py -i 192.168.0.110 -t 5 --raw 15500:14

# Read undocumented range (15000-15040)
python modbus_sunspec2_reader.py -i 192.168.0.110 -t 5 --raw 15000:41

# Large scan with cross-matching (SLOW)
python modbus_sunspec2_reader.py -i 192.168.0.110 -t 5 --raw 15000:514 --match
```

### Write Operations
```bash
# Write to register (DANGEROUS - use with caution)
python modbus_sunspec2_readwrite.py -i 192.168.0.110 --write 15507:3

# Example: Set operating mode to TOU (mode 3)
python modbus_sunspec2_readwrite.py -i 192.168.0.110 --write 15507:3
```

---

## Command-Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `-i HOST` | aGate IP address | `-i 192.168.0.110` |
| `-p PORT` | Modbus TCP port (default: 502) | `-p 502` |
| `-t TIMEOUT` | Connection timeout in seconds | `-t 5` |
| `-u UNIT` | Modbus unit ID (default: 1) | `-u 1` |
| `-m MODEL` | Read specific SunSpec2 model | `-m 713` |
| `--raw START:COUNT` | Read raw registers | `--raw 15500:14` |
| `--match` | Cross-check values vs SunSpec2 | `--match` |
| `--write ADDR:VAL` | Write register (readwrite script) | `--write 15507:3` |

---

## Use Cases

### 1. Verify FranklinWH Extension Addresses
```bash
# Confirm documented 15500-15513 range
python modbus_sunspec2_reader.py -i 192.168.0.110 -t 5 --raw 15500:14
```

**Output:**
```
15500    0000   0        PVUse (NotUsed)
15501    0000   0        apBoxPVUse (NotUsed)
15502    0578   1400     PVOutputP W
15503    0578   1400     proximalPVOutputP W
15504    0000   0        Remote1PV W
15505    0000   0        Remote2PV W
15506    01F4   500      LoadActiveP W
15507    0003   3        OnGridMode (TOU)        ← RW
15508    0014   20       SelfReserve %           ← RW
15509    0014   20       TouReserve %            ← RW
15510    00AE   174      PVOutputWh (High Word)
15511    BD70   48496    -> Low Word
15512    00AE   174      proximalOutputWh (High)
15513    BD70   48496    -> Low Word
```

### 2. Investigate Undocumented Registers
```bash
# Scan 15000-15040 for active registers
python modbus_sunspec2_reader.py -i 192.168.0.110 -t 5 --raw 15000:41
```

**Purpose:** Discover legacy or hidden registers (e.g., 15016/15017 aliases)

### 3. Debug Control Commands
```bash
# Before writing, verify current value
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15507:1

# Write new operating mode
python modbus_sunspec2_readwrite.py -i 192.168.0.110 --write 15507:2

# Verify write succeeded
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15507:1
```

---

## ⚠️ Important Warnings

### 1. `--match` Option is Unreliable
The `--match` flag performs simple value equality checks against the SunSpec2 database. This produces **many false positives**:

```
15507    0003   3    OnGridMode (TOU) [Matches: 701.InvSt (raw), 701.TotVarh_SF (raw)...]
                                        ^^^^^ FALSE POSITIVE
```

**Why it happens:**
- Simple integer value `3` appears in many unrelated SunSpec2 registers
- No semantic validation - just raw value matching
- Scale factors are ignored

**Recommendation:** Use `--match` only for initial exploration, NOT for definitive identification.

### 2. Write Operations are Dangerous
The `modbus_sunspec2_readwrite.py` script can **directly modify battery behavior**:

- Setting wrong operating mode can disable solar charging
- Incorrect reserve SOC can prevent backup power
- No validation or safety checks

**Always:**
- Verify current value before writing
- Understand what you're changing
- Test on non-production systems first

### 3. Large Scans Can Timeout
Reading 500+ registers (`--raw 15000:514`) can take 30+ seconds and may timeout on busy/slow networks.

---

## Output Format

### Raw Register Display

```
Addr     Hex    UInt16   Int16    Value           Acc Bits (Binary)      Guess/Notes
--------------------------------------------------------------------------------------------------------------
15507    0003   3        3        3               RW  0000000000000011   OnGridMode (TOU)
```

**Columns:**
- **Addr:** Register address
- **Hex:** Hexadecimal value
- **UInt16:** Unsigned 16-bit interpretation
- **Int16:** Signed 16-bit interpretation (if different)
- **Value:** Final interpreted value (may be 32-bit for acc32 types)
- **Acc:** Access mode (R=read, RW=read-write)
- **Bits:** Binary representation
- **Guess/Notes:** Register name and description (if known)

---

## Technical Details

### SunSpec2 Model Database
The utility includes hardcoded definitions for:
- Model 1 (Common)
- Model 701 (Inverter - Single Phase)
- Model 702 (Inverter - Three Phase)
- Model 713 (Battery Base Model)
- Model 714 (Battery String Model)
- Plus ~12 more models

### Register Address Mapping
```python
EXTENSIONS = {
    15500: ("PVUse", "enum:0=NotUsed,1=Used", "R"),
    15501: ("apBoxPVUse", "enum:0=NotUsed,1=Used", "R"),
    15502: ("PVOutputP", "W", "R"),
    # ... etc
    15507: ("OnGridMode", "enum:1=Back,2=Self,3=TOU", "RW"),
    15508: ("SelfReserve", "%", "RW"),
    15509: ("TouReserve", "%", "RW"),
}
```

---

## Files

- **`modbus_sunspec2_reader.py`** (root) - Standalone utility
- **`src/modbus_sunspec2_reader.py`** (module) - Library version (identical)
- **`modbus_sunspec2_readwrite.py`** (root) - Write-capable version
- **`src/modbus_sunspec2_readwrite.py`** (module) - Library version (identical)

**Note:** Root and `src/` versions are duplicates - either can be used.

---

## Example Workflows

### Workflow 1: Verify Address Mapping
```bash
# Step 1: Read FranklinWH extensions
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15500:14

# Step 2: Check for legacy aliases
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15016:2

# Step 3: Compare values - should match 15507/15508
```

### Workflow 2: Change Battery Mode
```bash
# Step 1: Check current mode
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15507:1
# Output: 15507    0002   2   OnGridMode (Self)

# Step 2: Change to TOU mode (3)
python modbus_sunspec2_readwrite.py -i 192.168.0.110 --write 15507:3

# Step 3: Verify change
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15507:1
# Output: 15507    0003   3   OnGridMode (TOU)
```

### Workflow 3: Investigate Unknown Register
```bash
# Step 1: Read register
python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15040:1
# Output: 15040    05C5   1477

# Step 2: Monitor over time
watch -n 5 'python modbus_sunspec2_reader.py -i 192.168.0.110 --raw 15040:1'

# Step 3: Correlate with known values (manual analysis)
```

---

## Limitations

1. **No automatic discovery** of non-SunSpec2 registers
2. **--match option unreliable** due to false positives
3. **No write safety checks** - user must validate
4. **Hardcoded model definitions** - new models require code updates
5. **Synchronous operations** - large scans are slow

---

## Related Documentation

- [`franklinwh_modbus_extensions.md`](file:///home/david/dev/modbus/franklinwh_modbus_extensions.md) - Source of truth for FranklinWH extensions
- [`TODO_MODBUS_ADDRESS_MISMATCH.md`](file:///home/david/dev/modbus/TODO_MODBUS_ADDRESS_MISMATCH.md) - Defect report on address confusion
- [`SUNSPEC_TRACEABILITY.md`](file:///home/david/dev/modbus/SUNSPEC_TRACEABILITY.md) - SunSpec protocol traceability

---

## Maintenance

**Last Updated:** 2026-02-14  
**Status:** Production utility, actively used for diagnostics  
**Known Issues:**
- Duplicate files in root and src/ (cosmetic only)
- --match produces false positives (by design limitation)
