# RULE: Staged Execution Mandatory

**Priority:** CRITICAL  
**Applies to:** All work sessions  
**Enforced by:** Agent self-check

---

## The Rule

> **NO work shall commence without user-approved plan and staged execution.**

---

## Hard Requirements

### 1. Planning Gate (CANNOT BYPASS)

```python
# PSEUDOCODE - Mental Check
if not has_explicit_user_approval():
    propose_work_plan()
    wait_for_approval()
    # DO NOT PROCEED until "yes", "go", "approved", "proceed"
```

**Explicit approval keywords:**
- "go"
- "yes"
- "approved"
- "proceed"
- "do it"

**NOT approval:**
- "ok" (ambiguous - confirm)
- "sure" (ambiguous - confirm)
- Silence (ask again)
- "what were you doing" (status request, not approval)

### 2. Staged Execution

All work MUST be broken into stages:
- Maximum 30 minutes per stage
- Each stage has defined test/verification
- Each stage has git commit
- Each stage tracked in in_flight_work.md

### 3. Git Commits (REQUIRED)

```bash
# After EACH stage completes
git commit -m "stage[N]: [what was done]"
```

### 4. Documentation (REQUIRED)

Update `in_flight_work.md`:
- Before: Mark stage "in_progress"
- After: Mark stage "done" with timestamp

---

## Pre-Work Checklist

Before typing any code:

- [ ] Read in_flight_work.md
- [ ] Understand current context
- [ ] Write proposed plan
- [ ] Get explicit user approval
- [ ] Identify first stage

---

## During Work Checklist

Per stage:

- [ ] Mark stage "in_progress" in in_flight_work.md
- [ ] Execute work
- [ ] Run tests/verification
- [ ] Git commit with stage message
- [ ] Mark stage "done" in in_flight_work.md
- [ ] Report to user

---

## Violation Examples

### ❌ WRONG:
```
User: "Can you fix the bug?"
Agent: [immediately starts editing files]
```

### ✅ CORRECT:
```
User: "Can you fix the bug?"
Agent: "I'll propose a plan:

## Proposed Work: Fix Connection Bug

**Stages:**
| Stage | Description | Test |
|-------|-------------|------|
| 1 | Diagnose root cause | Reproduce bug |
| 2 | Implement fix | Test passes |
| 3 | Add regression test | New test passes |

Please confirm to proceed."

User: "go"
Agent: [begins Stage 1]
```

---

## Emergency Override

Only for critical production issues:

1. State: "Emergency override - proceeding without full plan"
2. Keep stages tiny (single file changes)
3. Commit after each change
4. Post-hoc document

---

## Enforcement

This rule is self-enforced. The agent MUST:
1. Reference this rule before starting work
2. Follow the staged-execution.md workflow
3. Not allow user urgency to bypass planning

---

*Rule created: 2026-02-22*  
*Violations: Report to user immediately*
