# AI Agent Development Guide — FranklinWH Modbus Battery Manager

> **Project**: `/home/david/dev/modbus/`
> **Port**: 8080 (FastAPI)
> **Created**: 2026-02-18

> **🛡️ See**: [SAFETY_CONTROLS.md](./SAFETY_CONTROLS.md) for all safety rules (10 rules)

> **🔒 CRITICAL**: ALL agents MUST follow the approved plan in order (Rule #8), maintain `in_flight_work.md`, pass zero-error gates, and persist test evidence. See also: `.agent/workflows/`

**Strict adherence to these rules is required for all agents and developers:**

### 1. Structural Changes Protocol
Do NOT restructure, reorganize, rename, delete, move, or merge files and directories without EXPLICIT user approval.

### 2. Single-Purpose Commits
Each git commit should do one thing. Don't bundle unrelated changes.

### 3. Project Boundary
This project is `/home/david/dev/modbus/` ONLY.
- ❌ Never touch `/home/david/dev/ha/docker/fhp_demo/`
- ❌ Never kill processes on port 5000
- ✅ Only modify files under `/home/david/dev/modbus/`
- ✅ Only kill/restart processes on port 8080

### 4. Git-First Development
No file changes without git tracking. Verify clean state before starting, commit working features.

### 5. Process Safety
This web app runs on port **8080**. fhp_demo runs on port **5000**.
```bash
# ✅ Safe restart (this project only):
lsof -ti:8080 | xargs kill 2>/dev/null; sleep 2; ./run.sh -q &

# ❌ NEVER use:
pkill python
pkill -f app
```

### 6. In-Flight Work
`in_flight_work.md` is the source of truth for current work state. Read it at session start, update it after each completed item.
