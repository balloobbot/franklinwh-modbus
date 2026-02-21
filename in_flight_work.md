# In-Flight Work — Updated 2026-02-18 14:12

## Current Plan Reference

**Project**: FranklinWH Modbus Battery Manager (`/home/david/dev/modbus/`)
**Plan Status**: GOVERNANCE COMPLETE — Implementation plan not yet written
**Priority**: Stabilise `franklinwh_control_standalone.py` as an importable library (see `ARCHITECTURE.md` Phase 2)

## Status: SETTING UP PROJECT GOVERNANCE

---

## Completed Items

- [x] Full modbus web app inventory — 2026-02-18
  - 77 API endpoints, 16 backend modules, 7 templates, 13 dashboard cards
  - All 20 TODO files confirmed as legitimate for this project
- [x] fhp_demo accidental changes identified and rolled back — 2026-02-18
- [x] Project governance created from scratch — 2026-02-18
  - `SAFETY_CONTROLS.md` (10 rules inherited/adapted from fhp_demo)
  - `agent.md` (development guide)
  - `.agent/rules/project_boundaries.md` (boundary enforcement)
  - `.agent/workflows/verify-implementation.md` (3-check verification)
  - `.agent/workflows/restart-server.md` (port-safe restart)
  - `.agent/workflows/execution-discipline.md` (plan adherence)

## Awaiting

- [ ] User review/approval of governance documents
- [ ] Scoped implementation plan (modbus project only — no fhp_demo)
- [ ] TODO prioritisation for this project

## Blocked

_No blockers._

## Test Evidence

| Item | Logs Clean | Console Clean | Functional Test | Recording |
|------|-----------|--------------|-----------------|-----------|
| fhp_demo rollback | ✅ git checkout clean | N/A | N/A | N/A |

---

## Error Baseline

**Last checked**: 2026-02-18
**Reference**: See `AGENT_ERROR_TRACKING.md` for full error history

---

## Session Log

### 2026-02-21 22:25 AEDT — TOU Schedule File Support Added
- Implemented TOU schedule file support per user request
- Added TOUSchedule.from_file() for JSON schedule loading
- Added CLI args: --schedule-file, --show-schedule, --validate-schedule
- Updated _calc_time_of_use() to use schedule strategies (charge/discharge/etc)
- Created schedules/ directory with examples:
  - simple_day_night.json - 2-period basic schedule
  - ausgrid_tou.json - Australian Ausgrid TOU
  - README.md - Usage documentation
- Created TOU_SCHEDULE_DESIGN.md - Architecture and future integration plans
- Telemetry display now shows schedule info in TOU mode
- Ready for future Service Engine scheduler integration
- Commit: `8a428e5` - "feat: add TOU schedule file support"

### 2026-02-21 21:50 AEDT — Current State Audit & DEFECT-002 Fix
- User confirmed: proceed with audit approach first
- Created comprehensive audit documentation:
  - `audits/01_working_features.md` - Verified working vs untested
  - `audits/02_known_defects.md` - 8 defects catalogued (2 HIGH, 3 MEDIUM, 3 LOW)
  - `audits/03_code_analysis.md` - TODOs, placeholders, code smells
  - `audits/04_hardware_required.md` - Test environment requirements
  - `audits/README.md` - Executive summary
- Fixed DEFECT-002: Insufficient CLI output for operational verification
  - Added `_print_telemetry()` method with formatted console output
  - Added `_format_duration()` for HH:MM:SS display
  - Added `_get_target_soc_display()` for mode-specific target info
  - Shows: elapsed time, remaining time, home load, solar PV, target SoC, battery state, grid state
  - Updates every 5 seconds to console, every 60 seconds to log file
- Created `TEST_SUITE_PLAN.md` - Comprehensive testing strategy for library split
- Created `TELEMETRY_DEMO.md` - Visual demonstration of new output
- Commit: `1ddeb97` - "feat: add comprehensive telemetry output to CLI (DEFECT-002)"

### 2026-02-18 13:40 AEDT — Governance Established
- Reviewed all fhp_demo policies (13 rules, 4 workflows, production protection)
- Identified modbus project had zero governance
- Created 10-rule SAFETY_CONTROLS.md
- Created agent.md, 3 workflows, 1 rule file
- Rolled back accidental fhp_demo changes (git checkout + rm)
