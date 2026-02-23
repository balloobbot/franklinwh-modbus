# RULE: Library/CLI Architecture Compliance

**Priority:** CRITICAL  
**Applies to:** All work on battery control functionality  
**Created:** 2026-02-23

---

## Architecture Overview

This project uses a **THREE-COMPONENT** architecture:

```
franklinwh_modbus_library.py      ← LIBRARY (single file)
├── FranklinWHController          ← Main hardware interface
├── VirtualModeController         ← Virtual mode logic  
├── TOUSchedule                   ← Time-of-use scheduling
└── Types: BatteryCommand, HealthStatus, ControlMode, VirtualMode

franklinwh_cli.py                  ← CLI (separate file)
└── Imports from franklinwh_modbus_library.py

franklinwh_control_standalone.py   ← DEPRECATED (frozen)
└── Do not modify without explicit user approval
```

---

## Component Responsibilities

### 1. franklinwh_modbus_library.py (LIBRARY)
- **Purpose**: Single-file library for battery control
- **Contains**: Classes and functions only (NO CLI code)
- **Usage**: `from franklinwh_modbus_library import FranklinWHController`
- **Status**: Active development target

### 2. franklinwh_cli.py (CLI)
- **Purpose**: Command-line interface
- **Contains**: Argument parsing, main(), user interaction
- **Uses**: franklinwh_modbus_library.py (or src/franklinwh/ package)
- **Status**: Active development target

### 3. franklinwh_control_standalone.py (DEPRECATED)
- **Purpose**: Legacy standalone script
- **Status**: FROZEN - do not modify
- **Has**: Deprecation warning directing users to CLI or library
- **Exception**: Only critical safety fixes with user approval

---

## Hard Rules

### ❌ FORBIDDEN (without explicit user approval):

1. **Modifying franklinwh_control_standalone.py**
   - Exception: Critical bug fixes only
   - Must ask user: "Standalone is deprecated - should I also update it?"

2. **Adding CLI code to franklinwh_modbus_library.py**
   - The library must remain library-only
   - No argparse, no main(), no print statements

3. **Duplicating logic between components**
   - Library = single source of truth
   - CLI imports from library
   - No copy-paste between files

### ✅ REQUIRED:

1. **Update BOTH library and CLI for new features**
   - If adding feature to library, ensure CLI can use it
   - If adding CLI option, ensure library supports it

2. **Maintain deprecation warning in standalone**
   - Never remove the deprecation notice
   - Never make standalone "work better" than CLI (encourages migration)

---

## Checklist Before Changes

When modifying battery control code:

- [ ] Identify which component(s) need changes
- [ ] If standalone affected → Ask user for approval
- [ ] If library changed → Verify CLI still works
- [ ] If CLI changed → Verify library supports it
- [ ] Test both import and CLI usage

---

## Common Mistakes to Avoid

### ❌ WRONG:
```python
# Adding argparse to library
# In franklinwh_modbus_library.py:
if __name__ == "__main__":
    parser = argparse.ArgumentParser()  # NO! CLI is separate
```

### ✅ CORRECT:
```python
# Library stays clean
# In franklinwh_modbus_library.py:
class FranklinWHController:
    def send_command(self, cmd: BatteryCommand):
        ...

# CLI handles arguments
# In franklinwh_cli.py:
parser.add_argument('--charge', type=float)
args = parser.parse_args()
ctrl = FranklinWHController(args.ip)
```

---

## Migration Path for Users

**Old way (deprecated):**
```bash
python franklinwh_control_standalone.py -i 192.168.0.110 --power 3000
```

**New way (recommended):**
```bash
# CLI
python franklinwh_cli.py -i 192.168.0.110 --charge 3000

# Or library
python -c "from franklinwh_modbus_library import FranklinWHController; ..."
```

---

## Enforcement

This rule is **self-enforced**. Before any battery control work:

1. Read this rule file
2. Verify which component(s) you're modifying
3. If standalone → Get explicit user approval
4. Document changes in in_flight_work.md

---

*Rule created: 2026-02-23*  
*Reason: User requested single-file library + CLI separation, but agents kept modifying both standalone and CLI*
