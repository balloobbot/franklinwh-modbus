# In-Flight Work

**Last Updated:** 2026-03-12  
**Current Phase:** Phase 2 — Core Library Stabilization  
**Branch:** `develop`  
**Package:** `franklinwh-modbus` v0.9.0  
**Sister project:** `/Users/davidhona/dev/franklinwh-python/` (Cloud API, `pip install franklinwh`)  
**Consumer:** `/Users/davidhona/dev/franklinwh-energy-manager/` (Flask web app → MQTT → Home Assistant)

---

## Current State

- ✅ macOS migration complete (from Ubuntu)
- ✅ All tests passing: 32 passed, 0 failed, 7 skipped
- ✅ Proof-of-life smoke test: 47 pass, 0 fail, 3 skip
- ✅ `pip install -e ".[dev]"` → `franklinwh-modbus-0.9.0`
- ✅ aGate reachable at `192.168.0.110` from macOS
- ✅ DCW sign convention validated on live hardware (2026-03-12)
- ✅ Working tree clean, all committed and pushed to `develop`

## Completed (2026-03-12)

### Live Tier 2 Validation
1. **DCW sign convention** — charge/discharge at 500W on live aGate:
   - Charge: M714.DCW positive = CHARGING ✅
   - Discharge: M714.DCW negative = DISCHARGING ✅
   - Results: `tests/results/2026-03-12_dcw_sign_convention_validation.md`

### Documentation (New)
2. **Virtual Mode Specifications** — `docs/VIRTUAL_MODE_SPECIFICATIONS.md`
   - 6 virtual modes defined with algorithms and validation targets
   - Modbus TCP constraints as primary framing
   - Power sources, curtailment, load priority per mode
   - 9 hardware validation targets (2 completed, 7 remaining)

3. **FranklinWH Official Docs Reference** — `docs/FRANKLINWH_OFFICIAL_DOCS_REFERENCE.md`
   - Feature capability matrix (App vs Modbus TCP, 18 features)
   - Operating modes (Self-Consumption, Emergency Backup, TOU) from official docs
   - Grid Import/Export, Go Off-Grid, Smart Circuits, Generator, V2L
   - SPAN Panel integration (commissioning, ETH2, firmware ≥R06)
   - SPAN API gap analysis (fills 4 gaps: per-circuit control, EV visibility)
   - SunSpec Alliance membership and model table
   - `franklinwh-energy-manager` architecture and HA integration
   - 19 official URLs indexed

4. **Testing mandate** — updated to require Tier 2 live validation for power-related changes

## Completed (2026-03-08 — 2026-03-10)

### Modbus Library & CLI
1. **DER control testing** — M704 WSetEna/WSet confirmed working for charge/discharge
2. **Off-grid detection** — `ConnSt=0` now shows OFF-GRID in `--status`
3. **DERMode fix** — correct bit positions (bit 0=Grid Following, bit 1=Grid Forming)
4. **Register annotations** — `--status` shows `(M701.W)`, `(M713.SoC)` etc.
5. **`--check-span`** — local network scan (replaced Cloud API, no auth needed)
6. **Extension register probe** — confirmed READ-ONLY without SPAN Modbus unlock
7. **Namespace rename** — `franklinwh` → `franklinwh_modbus` (no conflicts with Cloud API)
8. **Test results** archived in `tests/results/`

### franklinwh-python (Cloud API)
1. **`pyproject.toml`** added — `pip install -e .` works
2. **`tou_predefined_builtin`** — fixed missing export from `const/__init__.py`

## Next Priorities

1. **Virtual mode hardware testing** — 7 remaining Tier 2 tests from `docs/VIRTUAL_MODE_SPECIFICATIONS.md`
2. **Phase 3: Intent-based conflict detection** — see [TODO doc](./docs/TODO_INTENT_BASED_CONFLICT_DETECTION.md)
3. **PyPi publication prep** — LICENSE, pyproject.toml, CI/CD
4. **TUI Monitor validation** — after library stable
5. **SPAN panel beta testing** — find tester with SPAN+aGate

## Blockers

- Extension registers (15507-15509) confirmed READ-ONLY — need SPAN Modbus unlock
- Need beta tester with SPAN panel connected to aGate

## Key Docs for Next Agent

> **READ THESE FIRST:**
> 1. `agent.md` — project overview, protocols, constraints
> 2. This file (`in_flight_work.md`) — current state + next priorities
> 3. `docs/VIRTUAL_MODE_SPECIFICATIONS.md` — mode definitions and validation targets
> 4. `docs/FRANKLINWH_OFFICIAL_DOCS_REFERENCE.md` — official feature/capability reference
> 5. `docs/FRANKLINWH_SUNSPEC_QUIRKS.md` — hardware quirks

## Related Docs

- [PHASES_AND_ROADMAP.md](./PHASES_AND_ROADMAP.md) — strategic multi-phase plan
- [docs/TODO_INTENT_BASED_CONFLICT_DETECTION.md](./docs/TODO_INTENT_BASED_CONFLICT_DETECTION.md) — Phase 3 design
- [docs/CONFLICT_DETECTION_ANALYSIS.md](./docs/CONFLICT_DETECTION_ANALYSIS.md) — Phase 3 analysis
- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) — library architecture overview

---

**Branch history:** `develop` — active development branch

