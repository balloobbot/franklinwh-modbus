# FranklinWH Modbus Controller - Phases & Roadmap

**Last Updated:** 2026-03-01  
**Current Phase:** Phase 2 - Core Library Stabilization  
**Next Milestone:** Virtual Mode Testing Complete

---

## Phase Overview

| Phase | Focus | Status | Key Deliverables |
|-------|-------|--------|------------------|
| **Phase 0** | Discovery & Research | ✅ Complete | Protocol docs, register maps |
| **Phase 1** | Basic Control | ✅ Complete | Manual mode, CLI, core library |
| **Phase 2** | Core Library Stabilization | 🟡 **IN PROGRESS** | Virtual modes, SoC validation |
| **Phase 3** | Enhanced Conflict Detection | 🟢 QUEUED | Intent-based detection |
| **Phase 4** | Ecosystem & Tools | 🟢 FUTURE | Web UI, automation, integrations |

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

**Key Documents:**
- [SUNSPEC_MODBUS_TEST_REPORT.md](./SUNSPEC_MODBUS_TEST_REPORT.md)
- [VPP_MODE_DISCOVERY.md](./VPP_MODE_DISCOVERY.md)
- [Sunspec2_battery_control_reference.md](./Sunspec2_battery_control_reference.md)

---

### Phase 1: Basic Control ✅

**Timeline:** Completed  
**Status:** Production-ready for manual control

**Deliverables:**
- ✅ Core library (`src/franklinwh/`)
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

**Documents:**
- [SOC_VALIDATION_IMPLEMENTATION.md](./SOC_VALIDATION_IMPLEMENTATION.md)
- [REQUIREMENTS_SOC_VALIDATION.md](./REQUIREMENTS_SOC_VALIDATION.md)
- [TRACEABILITY_SOC_VALIDATION.md](./TRACEABILITY_SOC_VALIDATION.md)

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
- [CONFLICT_DETECTION_ANALYSIS.md](./CONFLICT_DETECTION_ANALYSIS.md)

#### 2.4 TUI Monitor 🟡 PARKED
- ✅ Implemented with Rich library
- ✅ 5 themes, keyboard controls
- ✅ Auto-quiet mode
- ⚠️ **PARKED** - Waiting for user validation

**Document:** [TODO_TUI_TERMINAL_MONITOR.md](./TODO_TUI_TERMINAL_MONITOR.md)

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
- [CONFLICT_DETECTION_ANALYSIS.md](./CONFLICT_DETECTION_ANALYSIS.md) - Full analysis
- [TODO_INTENT_BASED_CONFLICT_DETECTION.md](./TODO_INTENT_BASED_CONFLICT_DETECTION.md) - Implementation plan

**Key Deliverables:**
- Energy flow context display
- Intent-aware conflict detection
- Reduced false positives
- Better conflict messages

---

### Phase 4: Ecosystem & Tools 🟢

**Timeline:** Future  
**Status:** IDEAS / PLANNING

**Potential Features:**
- Web dashboard ( historical data)
- Home Assistant integration
- Cloud API bridge
- Multi-device support
- Advanced scheduling
- Pricing API integration

**Documents:**
- [TODO_DATA_RETENTION.md](./TODO_DATA_RETENTION.md)
- [TODO_MULTI_AGATE.md](./TODO_MULTI_AGATE.md)
- [TODO_PRICING_APIS.md](./TODO_PRICING_APIS.md)
- [TODO_SCHEDULE_LIBRARY.md](./TODO_SCHEDULE_LIBRARY.md)

---

## Decision Log

| Date | Decision | Context | Status |
|------|----------|---------|--------|
| 2026-03-01 | **Select Option 2** for conflict detection | Intent-based most accurate; requires virtual mode testing first | QUEUED for Phase 3 |
| 2026-03-01 | **Park TUI Monitor** | Implemented but needs user validation; focus on core features | PARKED |
| 2026-03-01 | **Complete SoC Validation** | GAP-1, GAP-2 implemented and tested | ✅ COMPLETE |
| 2026-02-28 | **Implement SoC Safety** | Critical safety feature for reserve handling | ✅ COMPLETE |

---

## Current Work Queue

### This Week (Priority)
1. **Virtual Mode Testing** - Self-Consumption mode hardware test
2. **Documentation** - Update mode behavior docs based on testing

### Next (After Virtual Mode Testing)
1. **Intent-Based Conflict Detection** - Phase 3 implementation
2. **Energy Context Display** - Solar/load/grid in status output

### Future
1. **TUI Monitor** - Unpark and validate
2. **Phase 4 Features** - Web UI, integrations

---

## File Index

### Core Implementation
- `src/franklinwh/controller.py` - Main controller with Modbus interface
- `src/franklinwh/modes.py` - Virtual mode implementations
- `src/franklinwh/types.py` - Data types and enums
- `src/franklinwh/monitor.py` - TUI dashboard (PARKED)
- `franklinwh_cli.py` - Command-line interface

### Documentation by Phase

**Phase 0-1 (Complete):**
- [SUNSPEC_MODBUS_TEST_REPORT.md](./SUNSPEC_MODBUS_TEST_REPORT.md)
- [VPP_MODE_DISCOVERY.md](./VPP_MODE_DISCOVERY.md)
- [BATTERY_CONTROL_SAFETY.md](./BATTERY_CONTROL_SAFETY.md)

**Phase 2 (Current):**
- [SOC_VALIDATION_IMPLEMENTATION.md](./SOC_VALIDATION_IMPLEMENTATION.md)
- [REQUIREMENTS_SOC_VALIDATION.md](./REQUIREMENTS_SOC_VALIDATION.md)
- [TRACEABILITY_SOC_VALIDATION.md](./TRACEABILITY_SOC_VALIDATION.md)
- [TODO_TUI_TERMINAL_MONITOR.md](./TODO_TUI_TERMINAL_MONITOR.md)

**Phase 3 (Queued):**
- [CONFLICT_DETECTION_ANALYSIS.md](./CONFLICT_DETECTION_ANALYSIS.md)
- [TODO_INTENT_BASED_CONFLICT_DETECTION.md](./TODO_INTENT_BASED_CONFLICT_DETECTION.md)

**Phase 4 (Future):**
- [TODO_DATA_RETENTION.md](./TODO_DATA_RETENTION.md)
- [TODO_MULTI_AGATE.md](./TODO_MULTI_AGATE.md)
- [TODO_SCHEDULE_LIBRARY.md](./TODO_SCHEDULE_LIBRARY.md)

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
