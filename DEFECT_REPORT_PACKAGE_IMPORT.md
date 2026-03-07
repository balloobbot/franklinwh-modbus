# Defect Report: `franklinwh` Package Import Failure

**Date**: 2026-03-01  
**Reported by**: David (via energy-manager integration test)  
**Severity**: **BLOCKER** — prevents ALL imports from the `franklinwh` package  
**Status**: Reverted energy-manager to `franklinwh_control_standalone` until fixed

---

## Summary

`from franklinwh import FranklinWHController` fails with `NameError: name 'Layout' is not defined`.  
The entire package is unusable as a library dependency.

## Root Cause

`src/franklinwh/__init__.py` line 37 unconditionally imports `CLIMonitor`:

```python
from .monitor import CLIMonitor, MonitorConfig  # __init__.py:37
```

`monitor.py` line 689 uses `Layout` as a return type annotation at **class body level**:

```python
def create_layout(self) -> Layout:  # monitor.py:689
```

`Layout` is imported from `rich.layout` at line 43, but this import is inside a try/except block. When `rich` is not installed (or the conditional import fails), `Layout` is undefined at class parse time → `NameError`.

## Reproduction

```bash
$ python3 -c "import sys; sys.path.insert(0, 'src'); from franklinwh import FranklinWHController"

Traceback:
  File "src/franklinwh/__init__.py", line 37, in <module>
    from .monitor import CLIMonitor, MonitorConfig
  File "src/franklinwh/monitor.py", line 303, in <module>
    class CLIMonitor:
  File "src/franklinwh/monitor.py", line 689, in CLIMonitor
    def create_layout(self) -> Layout:
NameError: name 'Layout' is not defined
```

## Impact

- **Energy Manager**: Cannot use `franklinwh` package for Modbus provider → reverted to old `franklinwh_control_standalone.py`
- **Any consumer**: Anyone importing `from franklinwh import ...` gets this error unless `rich` is installed
- **MQTT publisher**: `from franklinwh.const.modes import RUN_STATUS` also fails (same root cause)

## Fix Applied

### Fix: `from __future__ import annotations` (2026-03-01)

Added to `src/franklinwh/monitor.py` line 2:

```python
from __future__ import annotations  # Postpone type hint evaluation
```

This makes all type annotations be stored as strings and evaluated lazily,
preventing the `NameError: name 'Layout' is not defined` at import time.

### How it works:

- Before fix: Python tried to resolve `Layout` at class definition time → NameError
- After fix: Python stores `"Layout"` as a string → resolved only when needed

### Additional safeguard in `__init__.py`:

The `__init__.py` already had a try/except around the monitor import:

```python
try:
    from .monitor import CLIMonitor, MonitorConfig
    HAS_MONITOR = True
except ImportError:
    HAS_MONITOR = False
    CLIMonitor = None
    MonitorConfig = None
```

This ensures graceful degradation when `rich` is not installed.

## Test Added

Created `tests/test_package_import.py` to verify:
1. Core imports work with and without rich
2. No NameError when importing monitor module
3. Type annotations are properly postponed
4. Clean subprocess import works

Run: `python tests/test_package_import.py`

## Status: ✅ FIXED

The package can now be imported without `rich` installed:

```python
# This works even without rich installed
from franklinwh import FranklinWHController, VirtualModeController

# CLIMonitor is None when rich not available
from franklinwh import CLIMonitor, HAS_MONITOR
assert CLIMonitor is None  # When rich not installed
assert HAS_MONITOR is False
```

## Additional Note: sys.path

The package lives at `~/dev/modbus/src/franklinwh/` but the energy-manager's `MODBUS_LIB_PATH` was pointing to `~/dev/modbus/` (not `~/dev/modbus/src/`). When switching to the package import path, both `~/dev/modbus/src/` AND `~/dev/modbus/` need to be on sys.path, or the package needs to be pip-installed.

---

*Filed from energy-manager session — Kimi please prioritise Fix 1.*
