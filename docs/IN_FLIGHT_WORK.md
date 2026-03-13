# In-Flight Work

**Status:** 🟡 PICS improvements — 13/21 complete  
**Date:** 2026-03-14  
**Last Commits:** `0c44cc7` (library safety), `d862c16` (docs)

---

## Completed This Session

### PICS Conformance Document — FINALIZED ✅
- 6 violations filed, 186s reversion observation, 160+ permutations
- External review applied (dual hypothesis, systemic safety, clearance conditions)
- Commit chain: `a7325d4` → `c51e0cf` (11 commits)
- **Ready for vendor submission**

### Library Safety Improvements — DONE ✅
- `_check_orphaned_vpp()` — detects WSetEna=1 on connect
- `auto_release_orphan=True` constructor flag
- `BatteryCommand.__post_init__()` — clamps ±10000W
- `ALARM_BITS`, `PICS_STATUS`, `DEFAULT_MAX_POWER_W` in types.py
- Enhanced docstrings (PICS Issues 4+5)

### Documentation — DONE ✅
- QUIRKS.md: reversion cosmetic, no validation, reactive exhausted
- SAFETY_CONTROLS.md: hardware safety section + clearance conditions
- VPP_MODE_REFERENCE.md: capability summary

---

## Remaining (8 items)

| # | Item | File | Priority |
|---|------|------|:--------:|
| 6 | `read_alarm_snapshot()` method | controller.py | 🟡 |
| 7 | `read_reversion_status()` method | controller.py | 🟡 |
| 9 | TUI timer + alarm display | monitor.py | 🟡 |
| 11 | `--alarm` CLI flag | franklinwh_cli.py | 🟡 |
| 12 | `--reversion-status` CLI flag | franklinwh_cli.py | 🟡 |
| 13 | `--safety-check` CLI flag | franklinwh_cli.py | 🟠 |
| 14 | Startup orphan warning for `--start` | franklinwh_cli.py | 🟢 |
| 21 | `safety_audit.py` standalone | tools/ | 🟢 |

**Full plan:** See artifact `implementation_plan.md` in conversation `13992edd`

---

*Last updated: 2026-03-14 01:03 AEDT*
