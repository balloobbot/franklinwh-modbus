# In-Flight Work

**Last Updated:** 2026-03-10  
**Current Phase:** Phase 2 — Core Library Stabilization  
**Branch:** `develop`  
**Package:** `franklinwh-modbus` v0.9.0  
**Sister project:** `/Users/davidhona/dev/franklinwh-python/` (Cloud API, `pip install franklinwh`)

---

## Current State

- ✅ macOS migration complete (from Ubuntu)
- ✅ All tests passing: 32 passed, 0 failed, 7 skipped
- ✅ Proof-of-life smoke test: 47 pass, 0 fail, 3 skip
- ✅ `pip install -e ".[dev]"` → `franklinwh-modbus-0.9.0`
- ✅ `pip install -e .` → `franklinwh-python` (pyproject.toml added)
- ✅ Git + GitHub SSH configured (both repos)
- ✅ aGate reachable at `192.168.0.110` from macOS

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

1. **SPAN panel beta testing** — find beta tester with SPAN+aGate to test extension register writability
2. **Virtual mode hardware testing** — Self-Consumption, Emergency Backup, TOU, Peak Shave
3. **Phase 3: Intent-based conflict detection** — see [TODO doc](./docs/TODO_INTENT_BASED_CONFLICT_DETECTION.md)
4. **PyPi publication prep** — LICENSE, pyproject.toml, CI/CD
5. **TUI Monitor validation** — after library stable

## Blockers

- Extension registers (15507-15509) confirmed READ-ONLY — need SPAN Modbus unlock from FranklinWH
- Need beta tester with SPAN panel connected to aGate

## Related Docs

- [PHASES_AND_ROADMAP.md](./PHASES_AND_ROADMAP.md) — strategic multi-phase plan
- [docs/TODO_INTENT_BASED_CONFLICT_DETECTION.md](./docs/TODO_INTENT_BASED_CONFLICT_DETECTION.md) — Phase 3 design
- [docs/CONFLICT_DETECTION_ANALYSIS.md](./docs/CONFLICT_DETECTION_ANALYSIS.md) — Phase 3 analysis

---

**Branch history:** `develop` — active development branch
