# In-Flight Work

**Last Updated:** 2026-03-07  
**Current Phase:** Phase 2 — Core Library Stabilization  
**Branch:** `fix/modbus-stability`  
**Package:** `franklinwh-modbus` v0.9.0  
**Strategic Priority:** Library-first for PyPi — web app archived

---

## Current State

- ✅ macOS migration complete (from Ubuntu)
- ✅ All tests passing: 32 passed, 0 failed, 7 skipped
- ✅ Proof-of-life smoke test: 47 pass, 0 fail, 3 skip
- ✅ Project cleanup done: root 190→11 files
- ✅ Web app archived to `archive/webapp/`
- ✅ `pip install -e ".[dev]"` → `franklinwh-modbus-0.9.0`
- ✅ Git + GitHub SSH configured
- ✅ Library API fixes: `stop_event`, `run_with_signal_handling`, no `sys.exit`
- ✅ Docs updated: README, USAGE_GUIDE, VPP_MODE_REFERENCE, safety warnings

## Completed This Session (2026-03-07)

1. Web app archived (39 files → `archive/webapp/`)
2. Library v0.9.0: signal handling decoupled, print→logger, duplicate types removed
3. `setup.py`: `pymodbus` added, `[monitor]` extra, author/URL
4. Distribution renamed: `franklinwh` → `franklinwh-modbus`
5. USAGE_GUIDE rewritten for library-first
6. Safety docs: extension register provisioning, VPP Mode, network requirements
7. Proof-of-life smoke test: 47/47 pass across 9 capability areas
8. Documentation health audit

## Next Priorities

1. **Virtual mode hardware testing** — Self-Consumption, Emergency Backup, TOU, Peak Shave
   - **Blocked:** Need aGate network access from macOS
2. **FEM integration test** — verify `franklinwh-modbus` works from `franklinwh-energy-manager`
   - Not blocked — can test locally
3. **PyPi publication prep** — LICENSE, pyproject.toml, CI/CD
4. **Phase 3: Intent-based conflict detection** — after hardware testing
5. **TUI Monitor validation** — after library stable

## Blockers

- aGate hardware (`192.168.0.110`) not reachable from macOS host
- Virtual mode testing requires network access to aGate

## On Hold

- **TUI Monitor** — implemented but parked until library usage validated
- **Web app** — archived in `archive/webapp/`, design elements preserved

---

**Branch history:** `fix/modbus-stability` — 15+ commits this session
