# FranklinWH Hardware Test Guide

> **Purpose**: Safe, recorded testing of battery control commands against live aGate hardware  
> **Location**: `tests/hardware/test_live_battery_control.py`  
> **Runner**: `run_hardware_tests.py`  
> **Last Updated**: 2026-02-28

---

## ⚠️ CRITICAL: Always Release Control After Testing

**The aGate MUST be returned to Cloud API control after testing.**

If tests are interrupted or fail, the aGate may be left in Modbus control mode (WSetEna=1), which:
- Prevents the FranklinWH app from working
- Blocks Cloud API/TOU schedules
- May cause unexpected behavior

### Quick Release Commands

```bash
# Method 1: Using CLI --stop flag (RECOMMENDED)
python franklinwh_cli.py -i YOUR_AGATE_IP --stop

# Method 2: Using release test
python run_hardware_tests.py --release

# Method 3: Direct reset via Python
python -c "
import sys; sys.path.insert(0, 'src')
from franklinwh_modbus import FranklinWHController
ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()
ctrl.reset_control_state()
print('✓ Control released - WSetEna=0')
ctrl.disconnect()
"
```

### Post-Test Verification Checklist

After ANY testing, verify the aGate is in a safe state:

```bash
# Check 1: Verify released state
python franklinwh_cli.py -i YOUR_AGATE_IP --status | grep "Control Source"
# Expected: "Control Source: Cloud API (aGate native mode)" OR "Idle (no active control)"

# Check 2: Verify no zombie state
python franklinwh_cli.py -i YOUR_AGATE_IP --healthcheck | grep "zombie_state"
# Expected: "✓ zombie_state: OK (not in zombie state)"

# Check 3: Verify alarms clear
python franklinwh_cli.py -i YOUR_AGATE_IP --status | grep -A5 "ALARMS"
# Expected: "✓ No alarms active"
```

**If Control Source shows "Modbus Control: ACTIVE" - run `--stop` immediately.**

---

## 📁 Test Results Location

All test results are automatically saved to:

```
data/test_results_YYYYMMDD_HHMMSS.json
```

### Result File Structure

```json
{
  "test_session": {
    "start_time": "2026-02-28T23:30:00",
    "end_time": "2026-02-28T23:35:00",
    "total_tests": 5,
    "passed": 4,
    "failed": 0,
    "skipped": 1
  },
  "results": [
    {
      "test_name": "test_charge_low_power",
      "timestamp": "2026-02-28T23:30:15",
      "status": "passed",
      "duration_seconds": 12.5,
      
      "pre_soc": 70.0,
      "pre_battery_power": 500,
      "pre_grid_power": -36,
      "pre_control_mode": "Self-Consumption",
      "pre_wset_ena": 0,
      
      "command_power": -500,
      "command_mode": "manual",
      
      "post_soc": 70.1,
      "post_battery_power": -450,
      "post_grid_power": 520,
      "post_wset_ena": 1,
      
      "expected_behavior": "Battery charging at ~500W (negative power)",
      "actual_behavior": "Battery power: -450W, WSetEna: 1",
      "validation_passed": true,
      
      "error_message": null,
      "traceback": null
    }
  ]
}
```

### Viewing Recent Results

```bash
# List all result files
ls -lt data/test_results_*.json | head -5

# View latest results
latest=$(ls -t data/test_results_*.json | head -1)
cat "$latest" | python -m json.tool

# Get summary only
cat "$latest" | python -c "import json,sys; d=json.load(sys.stdin); print(f\"Passed: {d['test_session']['passed']}/{d['test_session']['total_tests']}\")"
```

---

## 🚀 Running Tests

### Option 1: Using the Test Runner (Recommended)

The test runner provides a guided interface with safety checks:

```bash
# 1. List available tests
python run_hardware_tests.py --list

# 2. Run read-only tests (safest - no writes to battery)
python run_hardware_tests.py --read-only

# 3. Run low-power write tests (500W for ~10 seconds each)
python run_hardware_tests.py --low-power

# 4. Run with auto-confirmation (for automation)
python run_hardware_tests.py --low-power --yes

# 5. Custom results file
python run_hardware_tests.py --low-power --results-file my_test.json
```

### Option 2: Using Pytest Directly

For more control or CI integration:

```bash
# Source the virtual environment
source venv/bin/activate

# Read-only tests
pytest tests/hardware/test_live_battery_control.py -v -m hardware --collect-only
pytest tests/hardware/test_live_battery_control.py -v -m "hardware and not destructive"

# Destructive tests (writes to battery)
pytest tests/hardware/test_live_battery_control.py -v -m "hardware and destructive" --destructive-enabled

# Specific test
pytest tests/hardware/test_live_battery_control.py::test_charge_low_power -v --destructive-enabled
```

---

## 🧪 Available Tests

### Read-Only Tests (Always Safe)

| Test | Description | Duration |
|------|-------------|----------|
| `test_read_all_models` | Reads all SunSpec models (1, 501, 502, 701, 702, 703, 704, 713, 714, 715) | ~2s |
| `test_battery_status_consistency` | Reads battery 5 times over 5 seconds, validates stability | ~5s |
| `test_alarms_clear` | Verifies no critical alarms are active | ~1s |

### Low-Power Write Tests (500W)

| Test | Description | Duration | Safety |
|------|-------------|----------|--------|
| `test_charge_low_power` | Commands 500W charge, validates negative power | ~15s | Auto-rollback |
| `test_discharge_low_power` | Commands 500W discharge, validates positive power | ~15s | Auto-rollback |
| `test_standby` | Commands 0W standby | ~10s | Auto-rollback |
| `test_release_control` | Takes control then releases (WSetEna→0) | ~10s | Validates release |

### Advanced Tests (Conditional)

| Test | Description | Condition |
|------|-------------|-----------|
| `test_soc_ramping_near_limit` | Validates power ramping near SoC limits | Only runs if SoC > 85% |

---

## 🛡️ Safety Mechanisms

### 1. Pre-Test Safety Checks

Every destructive test validates:
- ✅ SoC between 10-95% (prevents overcharge/deep discharge)
- ✅ Grid connected (off-grid operation blocked by default)
- ✅ Voltage 200-270V (safe operating range)
- ✅ No critical alarms (safety faults block operation)

**If any check fails, test is skipped with explanation.**

### 2. Automatic Rollback

Every test automatically:
1. Captures pre-test state
2. Executes test
3. Waits for power stabilization (up to 30s)
4. Validates results
5. **Calls `reset_control_state()` to release control**
6. Records results to JSON

### 3. Power Stabilization Detection

After each command, the test waits for:
- 5 consecutive readings within 100W variance
- Or 30-second timeout (whichever comes first)

This ensures validation occurs after the battery has responded.

### 4. Test Result Recording

Every test records:
- Pre/post SoC, power, grid state
- Command parameters
- Expected vs actual behavior
- Pass/fail validation
- Error messages on failure

---

## 📋 Post-Test Procedure (MANDATORY)

After completing tests, ALWAYS execute this sequence:

### Step 1: Release Control

```bash
python franklinwh_cli.py -i YOUR_AGATE_IP --stop
```

Expected output:
```
INFO - Resetting control state to idle...
INFO - Before reset: WSetEna=1, WSetPct=XX, WSet=XXX
INFO - ✓ Reset successful: WSetEna=0, WSetPct=0
INFO - Control released
```

### Step 2: Verify Status

```bash
python franklinwh_cli.py -i YOUR_AGATE_IP --status
```

Verify these lines:
```
🔋 BATTERY POWER (DC)
    ...
    Control Source:   Cloud API (aGate native mode)   ← MUST say this

🎛️  AGATE MODE
    OnGridMode:       Self-Consumption   ← Or your preferred mode
```

**If it says "Modbus Control: ACTIVE", repeat Step 1.**

### Step 3: Health Check

```bash
python franklinwh_cli.py -i YOUR_AGATE_IP --healthcheck
```

Verify:
```
============================================================
  HEALTH CHECK: HEALTHY
============================================================

  Checks:
    ✓ connection: OK
    ✓ model_704: OK
    ✓ zombie_state: OK (not in zombie state)   ← CRITICAL
    ✓ can_operate: OK
```

**If zombie_state is not OK, run:**
```bash
python franklinwh_cli.py -i YOUR_AGATE_IP --stop
```

### Step 4: Review Test Results

```bash
# Find latest results
latest=$(ls -t data/test_results_*.json | head -1)
echo "Results: $latest"

# View summary
python -c "
import json
with open('$latest') as f:
    d = json.load(f)
    s = d['test_session']
    print(f\"Tests: {s['passed']}/{s['total_tests']} passed\")
    for r in d['results']:
        status = '✅' if r['status'] == 'passed' else '❌'
        print(f\"  {status} {r['test_name']}: {r['status']}\")
"
```

---

## 🚨 Emergency Procedures

### If Tests Are Interrupted (Ctrl+C, crash, etc.)

1. **Check control state:**
   ```bash
   python franklinwh_cli.py -i YOUR_AGATE_IP --status | grep "Control Source"
   ```

2. **If Modbus Control is ACTIVE:**
   ```bash
   # Release immediately
   python franklinwh_cli.py -i YOUR_AGATE_IP --stop
   
   # Verify release
   python franklinwh_cli.py -i YOUR_AGATE_IP --healthcheck | grep zombie_state
   ```

3. **If release fails (zombie state):**
   ```bash
   # Force reset by taking control then releasing
   python franklinwh_cli.py -i YOUR_AGATE_IP --mode manual --power 0 --duration 1
   sleep 2
   python franklinwh_cli.py -i YOUR_AGATE_IP --stop
   ```

### If Battery Won't Respond to Cloud/App

1. Check if Modbus control is still active:
   ```bash
   python franklinwh_cli.py -i YOUR_AGATE_IP --status | grep -A2 "Control Source"
   ```

2. If WSetEna=1, release it:
   ```bash
   python -c "
import sys; sys.path.insert(0, 'src')
from franklinwh_modbus import FranklinWHController
ctrl = FranklinWHController('YOUR_AGATE_IP')
if ctrl.connect():
    ctrl.reset_control_state()
    print('Released')
    ctrl.disconnect()
"
   ```

3. Verify in FranklinWH app that control is restored

---

## 🔧 Troubleshooting

### Test Skipped: "Safety check failed"

Check specific issue:
```bash
python franklinwh_cli.py -i YOUR_AGATE_IP --status
```

Common causes:
- SoC < 10% or > 95% → Wait for natural charge/discharge
- Grid disconnected → Check AC connection
- Critical alarms → Resolve faults first

### Test Failed: "Command failed"

1. Check connection:
   ```bash
   python franklinwh_cli.py -i YOUR_AGATE_IP --healthcheck | grep connection
   ```

2. Check for conflicts:
   ```bash
   python franklinwh_cli.py -i YOUR_AGATE_IP --status | grep -A2 "AGATE MODE"
   ```

3. May need `--reset-on-start` if another controller is active

### Results File Not Created

Check data directory exists:
```bash
mkdir -p data
ls -la data/
```

Verify permissions:
```bash
touch data/test_write && rm data/test_write || echo "Permission issue"
```

---

## 📝 Example Test Session

```bash
# 1. Check current state
$ python franklinwh_cli.py -i YOUR_AGATE_IP --status | head -20
State of Charge:  70.0%
Control Source:   Cloud API (aGate native mode)   ← Good, not in test mode

# 2. Run read-only tests
$ python run_hardware_tests.py --read-only
✅ All safety checks passed
Tests: 3/3 passed
  ✅ test_read_all_models: passed
  ✅ test_battery_status_consistency: passed
  ✅ test_alarms_clear: passed

# 3. Run low-power write tests
$ python run_hardware_tests.py --low-power
Do you want to proceed? Type 'yes' to continue: yes
✅ TEST PASSED: test_charge_low_power
✅ TEST PASSED: test_discharge_low_power
✅ TEST PASSED: test_standby
✅ TEST PASSED: test_release_control
Tests: 4/4 passed

# 4. MANDATORY: Release control
$ python franklinwh_cli.py -i YOUR_AGATE_IP --stop
INFO - ✓ Reset successful: WSetEna=0

# 5. Verify release
$ python franklinwh_cli.py -i YOUR_AGATE_IP --status | grep "Control Source"
Control Source:   Cloud API (aGate native mode)   ← Confirmed released

# 6. Health check
$ python franklinwh_cli.py -i YOUR_AGATE_IP --healthcheck | grep zombie_state
✓ zombie_state: OK (not in zombie state)   ← Confirmed clean

# 7. Review results
$ ls -lt data/test_results_*.json | head -1
-rw-r--r-- 1 user user 2.3K Feb 28 23:45 data/test_results_20260228_234515.json

$ cat data/test_results_20260228_234515.json | python -m json.tool
```

---

## 📊 Interpreting Results

### Passed Test Indicators
- `status`: "passed"
- `validation_passed`: true
- `post_wset_ena`: 0 (after rollback)
- `post_soc` within ±1% of `pre_soc` (short tests don't significantly change SoC)

### Failed Test Indicators
- `status`: "failed"
- `error_message`: Description of failure
- `traceback`: Full stack trace
- Common failures: connection timeout, safety check failure, validation mismatch

### Skipped Test Indicators
- `status`: "skipped"
- Reason in test output (e.g., "SoC 96% not in ramping zone")

---

## 🎯 Best Practices

1. **Always start with `--read-only`** to verify system health
2. **Run `--low-power` tests first** before any high-power testing
3. **Never leave tests running unattended** - monitor for failures
4. **Always run `--stop` after testing** even if tests passed
5. **Verify `--healthcheck` shows zombie_state OK** before considering complete
6. **Keep result files** for regression analysis
7. **Test during stable grid conditions** (avoid stormy weather, peak demand)

---

**Remember: The aGate controls your home's energy. Treat it with respect, verify the release, and keep the Cloud API in control for normal operation.**
