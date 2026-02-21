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

### 2026-02-21 23:25 AEDT — Fixed: Use Actual M702 Nameplate Ratings
- User question: Does script read nameplate ratings for charge/discharge limits?
- **Found bug**: VirtualModeController using hardcoded 5000W instead of actual ratings
- Fixed all virtual mode calculations:
  - _calc_self_consumption: Uses RATED_MAX_CHARGE_W / RATED_MAX_DISCHARGE_W
  - _calc_emergency_backup: Uses actual ratings
  - _calc_time_of_use: Uses actual ratings
  - _calc_grid_zero: Uses actual ratings
  - _calc_peak_shave: Uses actual ratings
- Added new solar_priority strategy:
  - Charges battery from solar first, even if home needs grid
  - Matches Cloud API mode for pre-peak charging
  - Useful for storing solar before expensive peak period
- Script now reads Model 702 registers:
  - WMaxRtg (40227): Max active power
  - WChaRteMaxRtg (40235): Max charge rate
  - WDisChaRteMaxRtg (40236): Max discharge rate
- Handles asymmetric ratings (e.g., 3500W charge / 5000W discharge)
- Updated CLI_OPTIONS.md with new strategy and ratings documentation
- Commits: `8f3e563`, `8837242`

### 2026-02-21 23:10 AEDT — Cloud API Coordination & Conflict Detection
- User request: Show OnGridMode, reserve SOC, detect Cloud API conflicts
- Implemented telemetry enhancements:
  - Show OnGridMode register (15507) value and mode name
  - Show active reserve (Self or TOU based on OnGridMode)
  - Show both actual battery DC power AND Modbus command power
  - Show WSetEna status
  - Detect ⚠️  CLOUD ACTIVE when OnGridMode != Manual AND battery active
- Added startup coordination logging:
  - Read and log OnGridMode at startup
  - Log active reserve for current mode
  - Detect WSetEna=1 in non-Manual modes (potential Cloud conflict)
  - Log warnings with recommendations
- Added documentation:
  - Cloud API Coordination section in CLI_OPTIONS.md
  - OnGridMode value reference table
  - Conflict detection explanation
  - Best practices for hybrid operation
  - Note: OnGridMode is read-only via Modbus (requires SPAN unlock)
  - VPP mode detection notes
- Key insight: Cannot write OnGridMode via Modbus, but can detect conflicts
- Recommendation: Use FranklinWH app to switch to Self-Consumption before local control
- Commit: `ef96eb0` - "feat: add Cloud API coordination visibility and conflict detection"

### 2026-02-21 22:45 AEDT — SoC Limits with Ramping Implemented
- Implemented comprehensive SoC limit system as requested:
  - --max-charge-soc: Maximum SoC for charging (default 100%)
  - --min-discharge-soc: Minimum SoC for discharging (auto-reads aGate reserve)
  - --soc-ramp-window: Ramping zone before hard limit (default 10%)
  - --force: Emergency override (logged warning)
- Features implemented:
  - Auto-reads aGate reserve SOC from native mode registers (15508/15509)
  - Validates min-discharge >= aGate reserve (enforced floor)
  - Linear ramping: 100% power -> reduced -> 0% over ramp window
  - Hard stop at limit with 🔒 indicator in telemetry
  - Ramping status shows percentage in telemetry
  - All events logged (ramping, hard stops, overrides)
- Updated telemetry display to show limit status and ramping info
- Created CLI_OPTIONS.md - comprehensive documentation of all CLI options
- Comprehensive logging: startup, runtime events, shutdown
- Commit: `0e8332e` - "feat: add SoC limits with ramping and comprehensive logging"

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
