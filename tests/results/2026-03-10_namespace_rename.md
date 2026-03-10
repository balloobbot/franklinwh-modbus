# Namespace Rename Test Results — 2026-03-10

## Change
Renamed Python package namespace: `franklinwh` → `franklinwh_modbus`  
Resolves PyPI collision with `franklinwh-python` (Cloud API package).

## Pre-Refactor Baseline
```
32 passed, 7 skipped, 2 warnings in 14.37s
```

## Post-Refactor Results
```
32 passed, 7 skipped, 2 warnings in 13.79s
```

## Delta
**Zero regressions.** Identical pass/skip/warn counts.

## Issues Found During Refactor
1. `patch('franklinwh.schedule.datetime')` in `test_tou_schedule.py` — needed update to `franklinwh_modbus.schedule.datetime`
2. `mod.startswith('franklinwh')` in `test_package_import.py` — updated to `franklinwh_modbus`

## Files Modified
| Category | Files |
|----------|-------|
| Package dir | `src/franklinwh/` → `src/franklinwh_modbus/` |
| Package init | `src/franklinwh_modbus/__init__.py` |
| CLI (2) | `franklinwh_cli.py`, `tools/franklinwh_cli.py` |
| Tests (5) | `test_smoke_proof_of_life.py`, `test_package_import.py`, `test_tou_schedule.py`, `test_virtual_mode_controller.py`, `test_live_battery_control.py` |
| Runner | `run_hardware_tests.py` |
| Setup | `setup.py` |
| Docs (6) | `FRANKLINWH_MODBUS_GUIDE.md`, `HARDWARE_TEST_GUIDE.md`, `TEST_QUICK_REFERENCE.md`, `DER_CONTROL_REFERENCE.md`, `ORCHESTRATION_AND_CONTROL.md`, `VERIFICATION_BASELINE.md` |
| Agent rules (2) | `library_first_strategy.md`, `library_cli_architecture.md` |
