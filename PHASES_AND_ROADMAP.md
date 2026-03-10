# franklinwh-modbus — Phases & Roadmap

**Last Updated:** 2026-03-07  
**Current Phase:** Phase 2 — Core Library Stabilization  
**Next Milestone:** Virtual mode hardware testing → PyPi publication

> [!IMPORTANT]
> **Strategic Decision (2026-03-07):** Web app is **archived** (`archive/webapp/`).
> Priority is the core `franklinwh-modbus` library as a standalone, PyPi-publishable
> package. Distribution name: `franklinwh-modbus`, import: `from franklinwh_modbus import ...`

---

## Phase Overview

| Phase | Focus | Status | Key Deliverables |
|-------|-------|--------|------------------|
| **Phase 0** | Discovery & Research | ✅ Complete | Protocol docs, register maps |
| **Phase 1** | Basic Control | ✅ Complete | Manual mode, CLI, core library |
| **Phase 2** | Core Library Stabilization | 🟡 **IN PROGRESS** | API fixes, v0.9.0, virtual mode testing |
| **Phase 3** | Enhanced Conflict Detection | 🟢 QUEUED | Intent-based detection |
| **Phase 4** | PyPi Publication & Ecosystem | ⏳ FUTURE | PyPi, LICENSE, CI/CD |

---

## Phase Details

### Phase 0: Discovery & Research ✅

**Timeline:** Completed  
**Status:** All core documentation complete

**Deliverables:**
- ✅ SunSpec Modbus protocol understanding
- ✅ FranklinWH extension registers documented (15500+)
- ✅ Register writability tested
- ✅ Safety requirements identified
- ✅ Alarm handling documented

**Key Documents:** (in `archive/docs/`)
- SUNSPEC_MODBUS_TEST_REPORT.md
- VPP_MODE_DISCOVERY.md
- Sunspec2_battery_control_reference.md

---

### Phase 1: Basic Control ✅

**Timeline:** Completed  
**Status:** Production-ready for manual control

**Deliverables:**
- ✅ Core library (`src/franklinwh_modbus/`)
- ✅ CLI tool (`franklinwh_cli.py`)
- ✅ Manual mode (charge/discharge/idle)
- ✅ Basic conflict detection
- ✅ Health check & diagnostics
- ✅ Safety limits & alarms

**Key Features:**
- Direct power control via Modbus
- SoC monitoring
- Auto-revert timer
- Dry-run mode
- Status display

**Known Limitations (By Design for Phase 1):**
- Virtual modes implemented but not fully tested
- Conflict detection has false positives
- No automatic schedule following

---

### Phase 2: Core Library Stabilization 🟡

**Timeline:** Current  
**Status:** IN PROGRESS - Virtual mode testing

**Deliverables:**

#### 2.1 SoC Validation ✅ COMPLETE
- ✅ Reserve SoC conflict detection (GAP-1)
- ✅ Safety margin enforcement (GAP-2)
- ✅ Target vs current validation
- ✅ Extension register integration (15507-15509)

**Documents:** (in `archive/docs/` — work complete)
- SOC_VALIDATION_IMPLEMENTATION.md
- REQUIREMENTS_SOC_VALIDATION.md
- TRACEABILITY_SOC_VALIDATION.md

#### 2.2 Virtual Mode Testing ⚠️ IN PROGRESS
**Status:** Manual mode ✅ | Other modes need testing

| Mode | Code | Tests | Hardware Validation | Status |
|------|------|-------|---------------------|--------|
| Manual | ✅ | ✅ | ✅ | **COMPLETE** |
| Self-Consumption | ✅ | ⚠️ | ❌ | Needs Testing |
| Emergency Backup | ✅ | ⚠️ | ❌ | Needs Testing |
| Time-of-Use | ✅ | ⚠️ | ❌ | Needs Testing |
| Peak Shave | ✅ | ⚠️ | ❌ | Needs Testing |

**Testing Requirements:**
- Self-Consumption: Full day cycle, reserve handling
- Emergency Backup: Outage simulation, target charging
- Time-of-Use: Multi-period transitions, rate boundaries
- Peak Shave: Threshold events, discharge limiting

**Exit Criteria:**
- [ ] Each mode tested for 24+ hours
- [ ] Edge cases documented
- [ ] Bug fixes applied
- [ ] Mode behavior validated against design

#### 2.3 Band-Aid Conflict Detection ✅ COMPLETE
**Status:** ✅ **IMPLEMENTED** 2026-03-01  
**Note:** Context-aware detection that reduces false positives by considering solar/load/grid. Full intent-based detection in Phase 3.

**Documents:**
- [CONFLICT_DETECTION_ANALYSIS.md](./docs/CONFLICT_DETECTION_ANALYSIS.md)

#### 2.5 Library API Stabilization ✅ COMPLETE (2026-03-07)
- ✅ Decoupled signal handling from `run_continuous()` — uses `stop_event`
- ✅ New `run_with_signal_handling()` wrapper for CLI
- ✅ Replaced `print()` with `logger.warning()` in library code
- ✅ Removed duplicate mode enums from `constants.py`
- ✅ Added `pymodbus` to `install_requires`
- ✅ Added `rich` as optional `[monitor]` extra
- ✅ Distribution renamed: `franklinwh` → `franklinwh-modbus`
- ✅ Version set to `0.9.0` (pre-release)
- ✅ Proof-of-life smoke test: 47/47 pass
- ✅ Safety docs: prerequisites, VPP Mode reference, network requirements

#### 2.4 TUI Monitor 🟡 PARKED
- ✅ Implemented with Rich library
- ✅ 5 themes, keyboard controls
- ✅ Auto-quiet mode
- ⚠️ **PARKED** - Waiting for user validation

---

### Phase 3: Enhanced Conflict Detection 🟢

**Timeline:** After Phase 2.2 Complete  
**Status:** QUEUED - Design Complete, Awaiting Prerequisites

**Overview:**
Implement intent-based conflict detection to eliminate false positives.

**Prerequisites:**
- ✅ Manual mode stable
- ⚠️ All virtual modes tested (Phase 2.2)
- ✅ SoC validation complete

**Selected Option:** Option 2 - Intent-Based Detection

**Implementation:**
- Pass user intent to conflict detector
- Compare intent vs aGate behavior
- Distinguish natural activity from conflicts

**Documents:**
- [CONFLICT_DETECTION_ANALYSIS.md](./docs/CONFLICT_DETECTION_ANALYSIS.md) - Full analysis
- [TODO_INTENT_BASED_CONFLICT_DETECTION.md](./docs/TODO_INTENT_BASED_CONFLICT_DETECTION.md) - Implementation plan

**Key Deliverables:**
- Energy flow context display
- Intent-aware conflict detection
- Reduced false positives
- Better conflict messages

---

### Phase 4: PyPi Publication & Ecosystem ⏳

**Timeline:** After library stable and tested  
**Status:** FUTURE — Library must be stable and hardware-tested first

**Deliverables:**
- PyPi publication (`pip install franklinwh-modbus`)
- LICENSE file (MIT)
- pyproject.toml migration from setup.py
- CI/CD (GitHub Actions: lint, test, publish)
- FranklinWH Energy Manager integration

**Future Features (separate projects):**
- Web dashboard (rebuilt on `franklinwh-modbus`)
- Home Assistant integration
- Cloud API bridge
- Multi-device support

**Web app design preserved:** `archive/webapp/README.md`

### Future Library Consumers

Projects that will consume `franklinwh-modbus` as a dependency:

| Project | Repo | Purpose | Status |
|---------|------|---------|--------|
| **FranklinWH Energy Manager** | `~/dev/franklinwh-energy-manager` | Dashboard, static data, Cloud API integration | WIP — porting to macOS |
| **FranklinWH Local VPP** | `~/dev/modbus2` (planned) | Multi-site/multi-aGate orchestration, dynamic tariff optimization | Concept — AI-generated code, not functional |

**Local VPP vision:** Define site topology (single/multi-site) with single or multi-aGate Modbus TCP devices connected to single or multiple utility services. Orchestrate aGates to optimize solar production, battery balancing across units, and TOU / dynamic tariff arbitrage. See `~/dev/franklinwh-energy-manager/multi-site-architecture.md` for initial static data architecture.

---

## Decision Log

| Date | Decision | Context | Status |
|------|----------|---------|--------|
| 2026-03-07 | **Rename to franklinwh-modbus** | Avoid conflict with Cloud API `franklinwh` package | ✅ DONE |
| 2026-03-07 | **Library v0.9.0 stabilized** | Signal handling, print→logger, setup.py deps, smoke test | ✅ DONE |
| 2026-03-07 | **Web app archived** | Moved to `archive/webapp/`, design elements preserved | ✅ DONE |
| 2026-03-07 | **Library-first for PyPi** | `franklinwh-modbus` as standalone package | IN PROGRESS |
| 2026-03-01 | **Select Option 2** for conflict detection | Intent-based most accurate; requires virtual mode testing first | QUEUED for Phase 3 |
| 2026-03-01 | **Park TUI Monitor** | Implemented but needs user validation; focus on core features | PARKED |
| 2026-03-01 | **Complete SoC Validation** | GAP-1, GAP-2 implemented and tested | ✅ COMPLETE |
| 2026-02-28 | **Implement SoC Safety** | Critical safety feature for reserve handling | ✅ COMPLETE |

---

## Current Work Queue

### Immediate (Blocked)
1. **Virtual Mode Hardware Testing** — Self-Consumption, Emergency Backup, TOU, Peak Shave
   - Requires aGate network access from macOS host

### Next (Not Blocked)
1. **FEM Integration Test** — verify `franklinwh-modbus` works from `franklinwh-energy-manager`
2. **PyPi Publication Prep** — LICENSE, pyproject.toml, CI/CD

### Future
1. **Phase 3: Intent-Based Conflict Detection** — after hardware testing
2. **TUI Monitor** — unpark and validate on macOS
3. **Phase 4: PyPi publication + ecosystem**

---

## File Index

### Core Implementation
- `src/franklinwh_modbus/controller.py` - Main controller with Modbus interface
- `src/franklinwh_modbus/modes.py` - Virtual mode implementations
- `src/franklinwh_modbus/types.py` - Data types and enums
- `src/franklinwh_modbus/monitor.py` - TUI dashboard (PARKED)
- `franklinwh_cli.py` - Command-line interface

### Documentation by Phase

**Phase 0-1 (Complete, in `archive/docs/`):**
- SUNSPEC_MODBUS_TEST_REPORT.md
- VPP_MODE_DISCOVERY.md
- BATTERY_CONTROL_SAFETY.md

**Phase 2 (Current):**
- SoC validation docs (archived — work complete)
- [TODO_TUI_TERMINAL_MONITOR.md](./archive/docs/TODO_TUI_TERMINAL_MONITOR.md)

**Phase 3 (Queued):**
- [CONFLICT_DETECTION_ANALYSIS.md](./docs/CONFLICT_DETECTION_ANALYSIS.md)
- [TODO_INTENT_BASED_CONFLICT_DETECTION.md](./docs/TODO_INTENT_BASED_CONFLICT_DETECTION.md)

**Phase 4 (Future, in `archive/docs/`):**
- TODO_DATA_RETENTION.md, TODO_MULTI_AGATE.md, TODO_SCHEDULE_LIBRARY.md

---

## Quick Reference for Next Agent

### If User Says "Test Virtual Modes"
→ See [TODO_INTENT_BASED_CONFLICT_DETECTION.md](./TODO_INTENT_BASED_CONFLICT_DETECTION.md) Phase 1

### If User Says "Fix Conflict Detection"
→ See [CONFLICT_DETECTION_ANALYSIS.md](./CONFLICT_DETECTION_ANALYSIS.md)  
→ Remind: Blocked until virtual modes tested

### If User Says "Resume TUI Monitor"
→ See [TODO_TUI_TERMINAL_MONITOR.md](./TODO_TUI_TERMINAL_MONITOR.md)  
→ Status: PARKED but ready

### If User Says "What's Next?"
→ See **Current Work Queue** above  
→ Priority: Virtual Mode Testing

---

## Success Criteria by Phase

### Phase 2 Success
- [x] SoC validation prevents unsafe operations
- [ ] All virtual modes tested and documented
- [ ] No known critical bugs in core library
- [ ] CLI stable for daily use

### Phase 3 Success
- [ ] Conflict detection has <10% false positive rate
- [ ] Intent parameter works across all modes
- [ ] Energy flow context in all status displays
- [ ] Users can trust conflict warnings

### Phase 4 Success
- [ ] Web dashboard operational
- [ ] Home Assistant integration available
- [ ] Multi-device support working
- [ ] Community adoption
