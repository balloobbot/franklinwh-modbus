---
description: Mandatory execution discipline checks — plan adherence and in-flight tracking
---

# Execution Discipline Workflow

**MANDATORY**: Follow for ALL implementation work.
**Reference**: SAFETY_CONTROLS.md Rule #8

---

## At Session Start

// turbo
1. Read in-flight work state:
```bash
cat in_flight_work.md 2>/dev/null || echo "No in_flight_work.md found"
```

2. Identify the approved plan and current position.
3. Resume from where the previous session left off — do NOT restart.

---

## Before Starting Each Task Item

1. Confirm item is the NEXT in the approved plan order.
2. Mark it `[/]` (in progress) in `in_flight_work.md`.

---

## After Completing Each Task Item

### Step 1: Zero-Error Gate

// turbo
```bash
tail -100 data/logs/franklinwh.log | grep -iE "error|exception|traceback"
```

Must be empty (or only pre-existing documented errors).

### Step 2: Browser Console Check

Open `http://localhost:8080` → F12 → Console → must show zero red errors.
Use `browser_subagent` to capture recording as evidence.

### Step 3: Functional Test

Actually USE the feature. Click, navigate, test edge cases.

### Step 4: Update In-Flight Work

Update `in_flight_work.md` with:
- Mark item `[x]` with date
- Add evidence to the tracking table

---

## Before Ending Session

// turbo
```bash
head -30 in_flight_work.md
```

Ensure all evidence persisted. Document any blockers.

---

## If Asked to Diverge From Plan

1. **STOP** — do not proceed
2. **FLAG** — "This diverges from step N. Proceed anyway?"
3. **WAIT** — for user approval
4. **DOCUMENT** — update `in_flight_work.md`
