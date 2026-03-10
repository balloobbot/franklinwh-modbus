---
description: Verify implementation is working (mandatory before declaring complete)
---

# Verify Implementation Workflow

> **MANDATORY**: This workflow MUST be executed before any implementation is declared complete.
> Test results MUST be captured in `tests/results/` with a timestamped filename.

## Steps

1. Run the full test suite:
// turbo
```bash
cd /Users/davidhona/dev/modbus && source venv/bin/activate && PYTHONPATH=src:. python3 -m pytest tests/ --tb=short -v 2>&1
```

2. Run live verification against the aGate (if device is reachable):
// turbo
```bash
cd /Users/davidhona/dev/modbus && source venv/bin/activate && python3 -c "
from franklinwh_modbus import FranklinWHController
ctrl = FranklinWHController('192.168.0.110')
ctrl.connect()
print('Battery:', ctrl.read_battery_status())
print('Grid:', ctrl.read_grid_status())
print('Solar:', ctrl.read_solar_status())
print('Nameplate:', ctrl.read_nameplate())
print('Control:', ctrl.read_control_status())
print('NativeMode:', ctrl.read_native_mode())
h = ctrl.healthcheck()
print(f'Health: {h.healthy} - {h.message}')
ctrl.disconnect()
"
```

3. **MANDATORY**: Save test results to `tests/results/YYYY-MM-DD_<description>.md` with:
   - Date, commit hash, device info
   - pytest output (pass/fail/skip counts)
   - Live verification output for each method tested
   - A table of changes tested and their results
   - Any known limitations discovered

4. If any tests were **bypassed or skipped**, document the reason:
   - Why the test was skipped (e.g., no hardware access, test not applicable)
   - Whether it should be run later
   - Any risk of the untested change

5. Commit the test results file along with the code changes.

## Test Results Format

Use this template for `tests/results/YYYY-MM-DD_<description>.md`:

```markdown
# Test Results — YYYY-MM-DD (<description>)

**Commit:** `<hash>` (branch)
**Date:** YYYY-MM-DD HH:MM TZ
**Device:** FranklinWH aGate X @ <IP> (or "N/A — no hardware")

## 1. Unit/Integration Tests (pytest)
<paste pytest -v output summary>

## 2. Live Verification
<paste live verification output per method>

## 3. Changes Tested
| Change | Test Type | Result |
|--------|-----------|--------|

## 4. Tests Bypassed (if any)
| Test | Reason Bypassed | Risk | Follow-up Required |
|------|----------------|------|-------------------|

## 5. Known Limitations
<any issues found>
```
