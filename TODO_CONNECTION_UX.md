# TODO: Connection Status UX Issues

## Issues

### 1. "Lost connection" Flash on Page Load
**Problem:** Red banner briefly shows "Lost connection to backend server • Retrying..." every time page loads/refreshes.

**Likely Cause:** Connection check threshold too tight - initial SSE connection hasn't established yet when check runs.

**Fix:** Add delay before first connection check or adjust threshold logic.

---

### 2. WiFi Warning Persistence
**Problem:** WiFi warning modal reappears after being dismissed.

**Expected:** Once dismissed, should stay hidden until app restart.

**Fix:** Store dismissal state in localStorage with session tracking.

---

## Priority

🟡 **MEDIUM** - Annoying but not blocking functionality

**When:** Week 2 polish work (after critical data bugs fixed)

## Estimated Effort

⏱️ 1-2 hours
