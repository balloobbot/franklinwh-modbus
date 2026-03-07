---
description: Safe restart of the modbus web server (port 8080 only)
---

# Restart Modbus Web Server

**CRITICAL**: Only restart THIS project on port 8080. Never kill processes on port 5000 (fhp_demo).

## Step 1: Stop Current Server

// turbo
```bash
lsof -ti:8080 | xargs kill 2>/dev/null && echo "Server stopped" || echo "No server running on 8080"
```

## Step 2: Wait for Shutdown

// turbo
```bash
sleep 2
```

## Step 3: Start Server

```bash
cd /Users/davidhona/dev/modbus && tools/run.sh -q &
```

## Step 4: Verify Startup

// turbo
```bash
sleep 5 && tail -20 data/logs/franklinwh.log
```

Expected: Server started successfully, no errors.

## Step 5: Verify Port

// turbo
```bash
lsof -i:8080 | head -5
```

Expected: Python process listening on 8080.

## ❌ FORBIDDEN

```bash
# NEVER use these — they kill fhp_demo too:
pkill python
pkill -f app
killall python3
```
