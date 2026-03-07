---
description: Project boundary enforcement — this project is /Users/davidhona/dev/modbus ONLY
priority: CRITICAL
---

# 🛡️ PROJECT BOUNDARY ENFORCEMENT

## THIS PROJECT

**Path**: `/Users/davidhona/dev/modbus/`
**Port**: `8080` (FastAPI via `src/main.py`)
**Process**: `python.*src.main` or `uvicorn`

## OUT OF BOUNDS — DO NOT TOUCH

| Path | What It Is | Why Forbidden |
|------|-----------|---------------|
| Other projects outside this directory | Separate projects | Separate repos |

## 🚨 MANDATORY CHECKS

**Before ANY file write:**
1. **Verify path starts with** `/Users/davidhona/dev/modbus/`
2. If it doesn't → **STOP and ALARM**: "⚠️ This path is outside the modbus project. Aborting."
3. **Never** auto-run file changes outside this project

**Before ANY process kill:**
1. **Identify by port or PID**, never by generic pattern like `pkill python`
2. This project: port **8080**, process matches `src.main` or `src/main`
3. **NEVER** kill processes on port 5000 (that's fhp_demo)
4. Safe pattern: `lsof -ti:8080 | xargs kill` or `pkill -f "src.main"`

## ❌ FORBIDDEN

- ❌ Editing files outside `/Users/davidhona/dev/modbus/`
- ❌ Running `pkill -f python` or `pkill -f app` (kills fhp_demo)
- ❌ Cross-project "consistency" changes
- ❌ Copying files between projects without explicit user approval

## 📝 LESSON LEARNED: Feb 18, 2026

**What happened**: Agent wrote Rule #14 to fhp_demo's SAFETY_CONTROLS.md while working on modbus project.
**Impact**: Modified 3 files in wrong project. Required git rollback.
**Prevention**: THIS RULE FILE + path verification before every write.
