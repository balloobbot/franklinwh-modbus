# AI Agent Development Guide — franklinwh-modbus

> **Project**: `/Users/davidhona/dev/modbus/`
> **Package**: `franklinwh-modbus` v0.9.0 (import as `from franklinwh_modbus import ...`)
> **Sister project**: `/Users/davidhona/dev/franklinwh-python/` (Cloud API client, `pip install franklinwh`)
> **Created**: 2026-02-18

---

## 📖 Essential Reading Order (START HERE)

**New agents MUST read these files in order before starting work:**

| Priority | File | Why |
|----------|------|-----|
| 1 | [`in_flight_work.md`](./in_flight_work.md) | Current state, active work, blockers |
| 2 | [`agent.md`](./agent.md) | This file — rules, safety, testing |
| 3 | [`docs/FRANKLINWH_MODBUS_GUIDE.md`](./docs/FRANKLINWH_MODBUS_GUIDE.md) | Definitive implementation guide |
| 4 | [`docs/FRANKLINWH_SUNSPEC_QUIRKS.md`](./docs/FRANKLINWH_SUNSPEC_QUIRKS.md) | Hardware quirks (critical gotchas) |
| 5 | [`docs/DER_CONTROL_REFERENCE.md`](./docs/DER_CONTROL_REFERENCE.md) | M704/M715 register map |
| 6 | [`docs/SAFETY_CONTROLS.md`](./docs/SAFETY_CONTROLS.md) | 10 safety rules |
| 7 | [`readme.md`](./readme.md) | Project overview, SunSpec model table |
| 8 | [`USAGE_GUIDE.md`](./USAGE_GUIDE.md) | Library & CLI usage |

**Read-on-demand** (when working on specific areas):

| File | When |
|------|------|
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | AC/DC coupling questions |
| [`docs/ORCHESTRATION_AND_CONTROL.md`](./docs/ORCHESTRATION_AND_CONTROL.md) | Control logic changes |
| [`docs/VPP_MODE_REFERENCE.md`](./docs/VPP_MODE_REFERENCE.md) | VPP/mobile app behavior |
| [`docs/HARDWARE_TEST_GUIDE.md`](./docs/HARDWARE_TEST_GUIDE.md) | Before any hardware testing |
| [`docs/VERIFICATION_BASELINE.md`](./docs/VERIFICATION_BASELINE.md) | Register verification |
| [`tools/README.md`](./tools/README.md) | Network scanner, SPAN detection |
| [`.agent/workflows/`](./.agent/workflows/) | Staged execution, verification workflows |
| [`.agent/rules/`](./.agent/rules/) | Project rules (boundaries, architecture) |

---

> **🛡️ See**: [SAFETY_CONTROLS.md](./docs/SAFETY_CONTROLS.md) for all safety rules (10 rules)  
> **📋 CRITICAL**: See [.agent/workflows/staged-execution.md](./.agent/workflows/staged-execution.md) for MANDATORY staged work process  
> **🧪 MANDATORY**: See [HARDWARE_TEST_GUIDE.md](./docs/HARDWARE_TEST_GUIDE.md) for REQUIRED hardware testing process

## ⚠️ Package Naming

- **Distribution name:** `franklinwh-modbus` (`pip install franklinwh-modbus`)
- **Python import:** `from franklinwh_modbus import ...` (import name is `franklinwh_modbus`)
- **NOT** `franklinwh` — that name is taken by the Cloud API package
- Always refer to this library as `franklinwh-modbus` in docs and conversations

---

## ⚠️ MANDATORY: Hardware Test Tool Usage

### When MUST Use the Hardware Test Tool

**ANY agent modifying the following MUST run hardware tests:**

- `src/franklinwh_modbus/` package (controller, modes, types)
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
PYTHONPATH=src:. python -m pytest tests/ --tb=short

# STEP 3: Run proof-of-life smoke test
python3 tests/test_smoke_proof_of_life.py

# STEP 4: Get user approval for write tests
# DO NOT proceed without explicit "go" from user

# STEP 5: Run low-power write tests (if approved)
python franklinwh_cli.py -i 192.168.0.110 --mode manual --power 500

# STEP 6: MANDATORY - Release control
python franklinwh_cli.py -i 192.168.0.110 --stop

# STEP 7: MANDATORY - Verify release
python franklinwh_cli.py -i 192.168.0.110 --status | grep "Control Source"
python franklinwh_cli.py -i 192.168.0.110 --healthcheck | grep zombie_state

# STEP 8: Record results in in_flight_work.md
```

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
- [ ] `in_flight_work.md` updated

### Emergency Release Commands

**If tests are interrupted or fail:**

```bash
# Quick release via CLI
python franklinwh_cli.py -i 192.168.0.110 --stop

# Or via library
python -c "from franklinwh_modbus import FranklinWHController; c=FranklinWHController('192.168.0.110'); c.connect(); c.reset_control_state(); c.disconnect()"
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
- ✅ Only modify files under `/Users/davidhona/dev/modbus/`

### 4. Git-First Development
No file changes without git tracking. Verify clean state before starting, commit working features.

### 5. In-Flight Work
`in_flight_work.md` is the source of truth for current work state. Read it at session start, update it after each completed item.

---

*Last Updated: 2026-03-10 — Added Essential Reading Order for agent onboarding*
