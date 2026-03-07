# TODO:DEFECT — Web App Inverter State Mapping Issue

**Status:** Documented, Deferred  
**Created:** 2026-02-24  
**Priority:** Low (web app not critical path)  

## Issue Summary

The custom web dashboard (left panel in screenshots) displays incorrect inverter state mappings:

| Raw Value | Correct Mapping | Web App Shows |
|-----------|-----------------|---------------|
| 3 | `Running` | `Fault` ❌ |
| 1 | `Standby` | `Off` ❌ |

## Evidence

From `modbus_sunspec2_reader.py` raw output:
- Model 701, Addr 40073 (`St`): Value = **1** (should be "Standby")
- Model 701, Addr 40074 (`InvSt`): Value = **3** (should be "Running")

Correct enum mapping (from `src/franklinwh/controller.py`):
```python
INVERTER_STATES = {
    0: 'Off',
    1: 'Sleeping', 
    2: 'Starting',
    3: 'Running',      # ← Value 3 = Running, not Fault
    4: 'Throttled',
    5: 'Shutting Down', 
    6: 'Fault',        # ← Value 6 = Fault
    7: 'Standby',
    8: 'Test',
    9: 'Manufacturing'
}
```

## Decision

- **Web app:** Defer fix — may abandon/re-engineer using new `franklinwh_modbus_library.py`
- **Terminal monitor:** Add correct mapping + raw values for reliable debugging

## Action Items

- [ ] Fix web app enum mappings (deferred)
- [ ] Consider migrating web app to use `franklinwh_modbus_library.py` instead of current implementation
- [ ] Add raw value display to terminal monitor for verification
