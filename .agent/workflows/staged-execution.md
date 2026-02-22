# Staged Execution Workflow

**MANDATORY** for all non-trivial work. No exceptions.

---

## Overview

This workflow ensures all work is:
- **Planned** before execution
- **Tracked** through completion
- **Tested** at each stage
- **Committed** to git locally
- **Documented** in in_flight_work.md

---

## Phase 1: PLANNING (REQUIRED - Cannot Skip)

### Before ANY Work Begins:

1. **STOP** - Do not write any code yet
2. **Read** `in_flight_work.md` for context
3. **Propose** work plan to user
4. **Await** explicit user approval ("go", "yes", "approved", "proceed")

### Work Plan Template:

```markdown
## Proposed Work: [Brief Title]

**Objective:** [One sentence goal]

**Stages:**
| Stage | Description | Test Criteria | Est. Time |
|-------|-------------|---------------|-----------|
| 1 | [What will be done] | [How we verify] | [X min] |
| 2 | [What will be done] | [How we verify] | [X min] |
| 3 | [What will be done] | [How we verify] | [X min] |

**Risk Level:** [Low/Medium/High]
**Files to Modify:** [List files]
**Rollback Plan:** [How to undo if needed]
```

### Approval Required:
- User must explicitly approve the plan
- Ambiguous responses ("ok", "sure", "do it") require confirmation
- Silence is NOT approval - ask again

---

## Phase 2: STAGED EXECUTION

### For Each Stage:

```
┌─────────────────────────────────────────────────────────────┐
│  STAGE N: [Description]                                     │
├─────────────────────────────────────────────────────────────┤
│  1. Update in_flight_work.md - mark stage "in_progress"     │
│  2. Execute the work                                        │
│  3. Run tests/verification                                  │
│  4. If tests fail → fix or rollback, do NOT proceed         │
│  5. Git commit with stage description                       │
│  6. Update in_flight_work.md - mark stage "done"            │
│  7. Report completion to user                               │
└─────────────────────────────────────────────────────────────┘
```

### Stage Commit Message Format:

```
stage[N]: [Brief description]

- What was done
- Test results: [PASS/FAIL/SKIPPED]
- Files changed: [list]
```

Example:
```
stage[1]: Add alarm monitoring read methods

- Added read_system_alarms() to controller
- Added read_dc_port_alarms() to controller
- Test results: PASS (read registers successfully)
- Files changed: src/franklinwh/controller.py
```

---

## Phase 3: DOCUMENTATION

### Update in_flight_work.md:

```markdown
## In-Flight Work — Updated [TIMESTAMP]

### Current
- [x] Stage 1: [Description] — [TIMESTAMP] — DONE
- [x] Stage 2: [Description] — [TIMESTAMP] — DONE
- [>] Stage 3: [Description] — IN PROGRESS

### Next
- [ ] Stage 4: [Description]

### Blocked
- None / [Description if any]
```

---

## Git Commit Rules

### REQUIRED at Each Stage:
```bash
# After stage completes and tests pass
git add [files]
git commit -m "stage[N]: [description]"
```

### NEVER:
- ❌ Commit multiple stages in one commit
- ❌ Commit untested code
- ❌ Amend previous stage commits
- ❌ Push to remote (local commits only)

### ALLOWED:
- ✅ Multiple commits within a stage if needed
- ✅ Fixup commits (mark as "stage[N]-fixup: description")
- ✅ WIP commits during stage (squash before stage complete)

---

## Test Requirements by Stage Type

| Stage Type | Minimum Verification |
|------------|---------------------|
| Add feature | Unit test passes |
| Fix bug | Reproduction case → fix verified |
| Refactor | Existing tests still pass |
| Documentation | Visual inspection |
| Config change | Application starts without error |
| UI change | Screenshot/verification |

---

## Emergency Override

**ONLY** for critical production fixes:

1. Document why planning is skipped
2. Keep stages small (1-2 commits max)
3. Post-hoc document in in_flight_work.md
4. User must approve the emergency

---

## Workflow Diagram

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   PROPOSE    │────▶│   AWAIT      │────▶│   STAGE 1    │
│    PLAN      │     │   APPROVAL   │     │  EXECUTION   │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
                       ┌──────────────────────────┘
                       ▼
              ┌────────────────┐
              │   TEST PASS?   │──NO──▶ FIX/ROLLBACK
              └───────┬────────┘
                      │ YES
                      ▼
              ┌────────────────┐
              │  GIT COMMIT    │
              └───────┬────────┘
                      ▼
              ┌────────────────┐     ┌──────────────┐
              │  MORE STAGES?  │──YES─▶│   STAGE N+1  │
              └───────┬────────┘     └──────────────┘
                      │ NO
                      ▼
              ┌────────────────┐
              │  FINALIZE      │
              │  DOCUMENTATION │
              └────────────────┘
```

---

## Checklist Before Proceeding to Next Stage

- [ ] Current stage tests pass
- [ ] Code committed with stage message
- [ ] in_flight_work.md updated
- [ ] User notified (if significant)
- [ ] No uncommitted changes from this stage

---

*Created: 2026-02-22*  
*Applies to: All non-trivial work (> 15 minutes or > 1 file)*
