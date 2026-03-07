# AI Agent Development Guide — FranklinWH Modbus Battery Manager

> **Project**: `/Users/davidhona/dev/modbus/`
> **Port**: 8080 (FastAPI)
> **Created**: 2026-02-18

> **🛡️ See**: [SAFETY_CONTROLS.md](./docs/SAFETY_CONTROLS.md) for all safety rules (10 rules)  
> **📋 CRITICAL**: See [.agent/workflows/staged-execution.md](./.agent/workflows/staged-execution.md) for MANDATORY staged work process  
> **🧪 MANDATORY**: See [HARDWARE_TEST_GUIDE.md](./docs/HARDWARE_TEST_GUIDE.md) for REQUIRED hardware testing process

> **🔒 CRITICAL**: ALL agents MUST follow the approved plan in order (Rule #8), maintain `in_flight_work.md`, pass zero-error gates, persist test evidence, and **USE THE HARDWARE TEST TOOL for any battery control modifications**.

---

## ⚠️ MANDATORY: Hardware Test Tool Usage

### When MUST Use the Hardware Test Tool

**ANY agent modifying the following MUST run hardware tests:**

- `src/franklinwh/` package (controller, modes, types)
- `franklinwh_cli.py` (CLI tool)
- Any Modbus register write sequences
- Power calculation logic
- Safety limit validation code

### Testing Process (MANDATORY)

```bash
# STEP 1: Read current state
python franklinwh_cli.py -i 192.168.0.110 --status
python franklinwh_cli.py -i 192.168.0.110 --healthcheck

# STEP 2: Run read-only tests (always safe)
python run_hardware_tests.py --read-only

# STEP 3: Get user approval for write tests
# DO NOT proceed without explicit "go" from user

# STEP 4: Run low-power write tests (if approved)
python run_hardware_tests.py --low-power

# STEP 5: MANDATORY - Release control
python franklinwh_cli.py -i 192.168.0.110 --stop

# STEP 6: MANDATORY - Verify release
python franklinwh_cli.py -i 192.168.0.110 --status | grep "Control Source"
python franklinwh_cli.py -i 192.168.0.110 --healthcheck | grep zombie_state

# STEP 7: Record results in in_flight_work.md
ls -lt data/test_results_*.json | head -1
```

### Test Results Recording

**EVERY test run MUST be recorded in `in_flight_work.md`:**

```markdown
## Test Results - YYYY-MM-DD HH:MM

| Test | Status | Results File |
|------|--------|--------------|
| Read-Only | ✅ Passed | data/test_results_YYYYMMDD_HHMMSS.json |
| Charge 500W | ✅ Passed | Same file |
| Release | ✅ Verified | WSetEna=0, zombie_state=OK |

**Pre-Test State:**
- SoC: 70%
- Control: Cloud API

**Post-Test State:**
- SoC: 70.1%
- Control: Cloud API (released)
- Zombie State: OK
```

### What Constitutes "Testing"

**NOT ACCEPTABLE:**
- ❌ "Code looks correct"
- ❌ "Should work based on logic"
- ❌ "Matches documentation"
- ❌ Unit tests only (without hardware validation)
- ❌ "Ran script, no errors"

**REQUIRED:**
- ✅ Actual commands sent to aGate
- ✅ Pre/post state comparison
- ✅ Validation of expected behavior
- ✅ Results recorded in JSON
- ✅ Control released and verified
- ✅ Documentation in `in_flight_work.md`

### Safety Checklist (Before ANY Write Test)

- [ ] SoC between 10-95%
- [ ] Grid connected
- [ ] Voltage 200-270V
- [ ] No critical alarms
- [ ] User explicitly approved
- [ ] Rollback plan ready

### Post-Test Checklist (After ANY Test)

- [ ] Control released (`--stop` executed)
- [ ] Status shows "Cloud API" or "Idle"
- [ ] Health check shows "zombie_state: OK"
- [ ] No alarms triggered
- [ ] Results saved to JSON
- [ ] `in_flight_work.md` updated

### Emergency Release Commands

**If tests are interrupted or fail:**

```bash
# Quick release
python run_hardware_tests.py --release

# Or via CLI
python franklinwh_cli.py -i 192.168.0.110 --stop

# Verify
python franklinwh_cli.py -i 192.168.0.110 --status | grep "Control Source"
```

**Reference:** [HARDWARE_TEST_GUIDE.md](./docs/HARDWARE_TEST_GUIDE.md), [TEST_QUICK_REFERENCE.md](./docs/TEST_QUICK_REFERENCE.md)

---

## ⚠️ MANDATORY: Staged Execution Process

**NO work shall commence without:**
1. **Written proposed plan** with stages
2. **Explicit user approval** ("go", "yes", "approved", "proceed")
3. **Per-stage git commits**
4. **in_flight_work.md updates**

**Reference:** `.agent/workflows/staged-execution.md` and `.agent/rules/staged_execution_rule.md`

---

**Strict adherence to these rules is required for all agents and developers:**

### 1. Structural Changes Protocol
Do NOT restructure, reorganize, rename, delete, move, or merge files and directories without EXPLICIT user approval.

### 2. Single-Purpose Commits
Each git commit should do one thing. Don't bundle unrelated changes.

### 3. Project Boundary
This project is `/Users/davidhona/dev/modbus/` ONLY.
- ❌ Never touch other projects outside this directory
- ❌ Never kill processes on port 5000
- ✅ Only modify files under `/Users/davidhona/dev/modbus/`
- ✅ Only kill/restart processes on port 8080

### 4. Git-First Development
No file changes without git tracking. Verify clean state before starting, commit working features.

### 5. Process Safety
This web app runs on port **8080**. fhp_demo runs on port **5000**.
```bash
# ✅ Safe restart (this project only):
lsof -ti:8080 | xargs kill 2>/dev/null; sleep 2; tools/run.sh -q &

# ❌ NEVER use:
pkill python
pkill -f app
```

### 6. In-Flight Work
`in_flight_work.md` is the source of truth for current work state. Read it at session start, update it after each completed item.

---

*Last Updated: 2026-03-07 — Fixed paths for macOS migration, removed deprecated file references*
