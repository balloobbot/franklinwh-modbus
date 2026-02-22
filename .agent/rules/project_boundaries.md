---
description: Project boundary enforcement — this project is /home/david/dev/modbus ONLY
priority: CRITICAL
---

# 🛡️ PROJECT BOUNDARY ENFORCEMENT

## THIS PROJECT

**Path**: `/home/david/dev/modbus/`
**Port**: `8080` (FastAPI via `src/main.py`)
**Process**: `python.*src.main` or `uvicorn`

## OUT OF BOUNDS — DO NOT TOUCH

| Path | What It Is | Why Forbidden |
|------|-----------|---------------|
| `/home/david/dev/ha/docker/fhp_demo/` | Cloud API web dashboard (Flask, port 5000) | Separate project, production |
| `/home/david/franklinwh-clean/` | Library PR for upstream | Separate repo |
| `/home/david/franklin-energy-dashboard/` | Public web app project | Separate repo |

## 🚨 MANDATORY CHECKS

**Before ANY file write:**
1. **Verify path starts with** `/home/david/dev/modbus/`
2. If it doesn't → **STOP and ALARM**: "⚠️ This path is outside the modbus project. Aborting."
3. **Never** auto-run file changes outside this project

**Before ANY process kill:**
1. **Identify by port or PID**, never by generic pattern like `pkill python`
2. This project: port **8080**, process matches `src.main` or `src/main`
3. **NEVER** kill processes on port 5000 (that's fhp_demo)
4. Safe pattern: `lsof -ti:8080 | xargs kill` or `pkill -f "src.main"`

## ❌ FORBIDDEN

- ❌ Editing files in `/home/david/dev/ha/`
- ❌ Running `pkill -f python` or `pkill -f app` (kills fhp_demo)
- ❌ Cross-project "consistency" changes
- ❌ Copying files between projects without explicit user approval

## 📝 LESSON LEARNED: Feb 18, 2026

**What happened**: Agent wrote Rule #14 to fhp_demo's SAFETY_CONTROLS.md while working on modbus project.
**Impact**: Modified 3 files in wrong project. Required git rollback.
**Prevention**: THIS RULE FILE + path verification before every write.
