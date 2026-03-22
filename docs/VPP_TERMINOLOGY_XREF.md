# VPP → Remote Control Terminology Cross-Reference

> **LOCAL REFERENCE ONLY — do NOT commit to GitHub.**
> Created: 2026-03-22 for terminology review purposes.

## Terminology Decision

| Term | Usage |
|------|-------|
| **Remote Control** | SunSpec-correct term for `WSetEna=1` (DER under external control via Modbus) |
| **"VPP Mode"** | FranklinWH mobile app label for Remote Control. Use only as quoted UI string |
| **VPP** | Acceptable in code identifiers (e.g. `_check_orphaned_vpp()`) — too disruptive to rename |

## Docs Already Updated ✅

| File | Replacements | Notes |
|------|:---:|-------|
| `FRANKLINWH_SUNSPEC_QUIRKS.md` | 15 | VPP Mode → Remote Control throughout |
| `PICS_CONFORMANCE_CROSS_REFERENCE.md` | 22 | App/MQTT quoted strings preserved |

## Source Code — VPP References (NO CHANGES — review only)

### `controller.py` — Function names & comments

| Line | Content | Verdict |
|:----:|---------|:-------:|
| 50 | `auto_release_orphan: bool = False,  # Release orphaned VPP on connect` | ⚠️ Comment could say "Remote Control" but param name is API |
| 111 | `# Check for orphaned VPP state from previous session` | ⚠️ Comment — safe to update later |
| 112 | `self._check_orphaned_vpp()` | ❌ Private method — rename would break nothing but touches many lines |
| 120 | `def _check_orphaned_vpp(self) -> None:` | ❌ Function name — defer to major version |
| 121 | `"""Check if VPP control is active...` | ⚠️ Docstring — safe to update later |
| 123 | `Reads WSetEna (318) and logs if VPP is active` | ⚠️ Docstring |
| 137 | `f"Active VPP state detected: WSetEna=1..."` | ⚠️ Log message — user-visible in debug |
| 141 | `"auto_release_orphan=True — releasing VPP state"` | ⚠️ Log message |
| 1103 | `mechanism. Set this for ALL unattended VPP operations.` | ⚠️ Docstring |

### `constants.py` — Mode enum

| Line | Content | Verdict |
|:----:|---------|:-------:|
| 20 | `9: "VPP mode"` | ✅ **KEEP** — this is the aGate's actual mode name as reported by the device |

### `types.py` — PICS status

| Line | Content | Verdict |
|:----:|---------|:-------:|
| 204 | `'WSetEna': 'functional',  # M704.318 — VPP enable` | ⚠️ Comment — could say "Remote Control enable" |

## Other Docs — VPP References (NOT yet updated)

| File | VPP refs | Priority |
|------|:---:|:---:|
| `readme.md` | 2 | HIGH — public-facing. Line 29 (WiFi warning), Line 47 (VPP Mode indicator) |
| `USAGE_GUIDE.md` | 7 | HIGH — user-facing. Has "VPP Mode Indicator" section header |
| `PHASES_AND_ROADMAP.md` | 4 | LOW — internal roadmap, "Local VPP" is a product concept name |
| `IN_FLIGHT_WORK.md` | 2 | LOW — internal tracking |
| `TODO_INTENT_BASED_CONFLICT_DETECTION.md` | 5 | MEDIUM — design doc |
| `tests/results/*.md` | 8 | LOW — historical test evidence, should not be rewritten |

## Recommended Next Steps

1. **readme.md + USAGE_GUIDE.md** — Update for public release. Keep "VPP Mode" as quoted app label, use "Remote Control" for the concept.
2. **Source code** — Defer code identifier renames to a major version. Comments/docstrings can be updated opportunistically.
3. **Test results** — Do NOT modify. These are historical records of what was observed.
