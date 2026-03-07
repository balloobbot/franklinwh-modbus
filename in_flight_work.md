# In-Flight Work

**Last Updated:** 2026-03-07  
**Current Phase:** Phase 2 — Core Library Stabilization  
**Branch:** `fix/modbus-stability`

---

## Current State

- ✅ macOS migration complete (from Ubuntu)
- ✅ All tests passing: 32 passed, 0 failed, 6 skipped
- ✅ Project cleanup done: root 190→11 files
- ✅ `pip install -e ".[dev]"` working
- ✅ Git + GitHub SSH configured

## Active Work

### Phase 2.2: Virtual Mode Testing
- Manual mode ✅ tested
- Self-Consumption, Emergency Backup, TOU, Peak Shave — need hardware testing
- **Blocked:** No aGate hardware access from macOS host

### Phase 2.4: TUI Monitor
- Implemented but PARKED — needs user validation on macOS
- Not yet verified running on macOS

## Next Priorities

1. Verify CLI/TUI/web server startup on macOS (non-hardware checks)
2. Merge `fix/modbus-stability` → `develop`
3. Virtual Mode hardware testing (requires aGate network access)
4. Phase 3: Intent-based conflict detection

## Blockers

- aGate hardware (`192.168.0.110`) not reachable from macOS host
- No hardware testing possible until network configured

---

**Previous session logs:** `archive/in_flight_work_2026-02-18_to_2026-03-01.md`
