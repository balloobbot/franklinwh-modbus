# TODO: FranklinWH aGate WiFi Drop Infinite Loop

## Status
**Priority:** 🔴 **CRITICAL** - Causes complete application hang, requires restart  
**Discovered:** 2026-02-14  
**User Reported:** Yes (Defect #2)

---

## Problem

When the FranklinWH aGate drops off WiFi, the application enters an **infinite loop** that completely hangs the web server. The application becomes unresponsive and **requires a server restart** to recover.

### Symptoms
- ❌ Web server stops responding to requests
- ❌ Dashboard becomes inaccessible
- ❌ No automatic recovery
- ❌ Must manually restart application

### User Impact
**SEVERE** - Complete application outage requiring manual intervention

---

## Root Cause

The application does **not** have proper network health detection or timeout handling when the aGate becomes unreachable. When Modbus connection attempts fail, they likely retry indefinitely without:
- Connection timeout
- Exponential backoff
- Circuit breaker pattern
- Health check to detect network unavailability

This causes the event loop to block or enter an infinite retry state.

---

## Related Work

### Existing Network Health Infrastructure
From [`TODO_WIFI_WARNING.md`](file:///home/david/dev/modbus/TODO_WIFI_WARNING.md):

**✅ Phase 1 COMPLETE:**
- `src/network_health.py` - Ping-based network quality monitoring
- `/api/health` endpoint with network statistics
- Detects "degraded" quality from WiFi latency/jitter

**❌ Phase 2 MISSING:**
- Dashboard warning banner (frontend)
- Health data polling in Alpine.js
- **Critically: No integration with Modbus client for circuit breaking**

### The Issue
The network health monitoring exists but is **not integrated** with the Modbus connection layer to:
1. Detect when aGate is unreachable
2. Stop retry attempts after reasonable timeout
3. Gracefully degrade functionality
4. Allow server to continue operating

---

## Solution Options

### Option 1: Connection Timeout + Circuit Breaker (Recommended)

**Implementation:**

#### 1.1. Add Connection Timeout to Modbus Client

**File:** `src/modbus_client.py` or `src/modbus_client_franklinwh.py`

```python
class ModbusClient:
    def __init__(self, host, port=502, timeout=10, max_retries=3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay_base = 2  # Exponential backoff base
        self.circuit_open = False
        self.circuit_open_until = None
        
    async def _with_circuit_breaker(self, operation):
        """Execute operation with circuit breaker pattern."""
        # Check if circuit is open
        if self.circuit_open:
            if time.time() < self.circuit_open_until:
                raise CircuitOpenError("Circuit breaker is open")
            else:
                # Try to close circuit
                self.circuit_open = False
        
        # Try operation with retries
        for attempt in range(self.max_retries):
            try:
                # Set asyncio timeout
                async with asyncio.timeout(self.timeout):
                    return await operation()
            except asyncio.TimeoutError:
                if attempt == self.max_retries - 1:
                    # Open circuit breaker
                    self.circuit_open = True
                    self.circuit_open_until = time.time() + 60  # 60s cooldown
                    raise ConnectionError("aGate unreachable, circuit opened")
                # Exponential backoff
                await asyncio.sleep(self.retry_delay_base ** attempt)
```

#### 1.2. Integrate with Network Health Monitor

**File:** `src/network_health.py` enhancement

```python
class NetworkHealthMonitor:
    async def check_agate_reachable(self, host: str) -> bool:
        """Quick ping check to see if aGate is on network."""
        try:
            result = await asyncio.create_subprocess_exec(
                'ping', '-c', '1', '-W', '2', host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            return result.returncode == 0
        except Exception:
            return False
    
    async def health_check_loop(self, modbus_client):
        """Periodic health check that controls circuit breaker."""
        while True:
            await asyncio.sleep(30)  # Every 30 seconds
            
            is_reachable = await self.check_agate_reachable(modbus_client.host)
            
            if not is_reachable:
                logger.warning("aGate unreachable via ping, opening circuit")
                modbus_client.circuit_open = True
                modbus_client.circuit_open_until = time.time() + 60
            else:
                # aGate is back, allow circuit to close
                if modbus_client.circuit_open:
                    logger.info("aGate is reachable again, circuit can close")
```

**Effort:** 2-3 hours  
**Risk:** Low - adds safety without changing existing behavior

---

### Option 2: Async Task Timeout Wrapper (Simpler)

**Implementation:**

```python
async def safe_modbus_operation(operation, timeout=10):
    """Wrap any modbus operation with timeout."""
    try:
        return await asyncio.wait_for(operation(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error("Modbus operation timed out")
        return None  # Or raise graceful error
```

**Usage in data collection:**

```python
# In main polling loop
try:
    data = await safe_modbus_operation(
        lambda: client.read_battery_data(),
        timeout=10
    )
    if data is None:
        # Fall back to last known good data or display error
        consecutive_failures += 1
        if consecutive_failures > 5:
            logger.critical("aGate unreachable, entering degraded mode")
            # Set flag so UI shows "Connection Lost"
except Exception as e:
    logger.error(f"Modbus error: {e}")
```

**Effort:** 1-2 hours  
**Risk:** Very low - minimal changes to existing code

---

### Option 3: Watchdog Thread (Nuclear Option)

**Implementation:**

```python
import threading
import time

class WatchdogTimer:
    def __init__(self, timeout=30):
        self.timeout = timeout
        self.last_ping = time.time()
        self.running = True
        self.thread = threading.Thread(target=self._watchdog, daemon=True)
        self.thread.start()
    
    def ping(self):
        """Call this from main loop to reset watchdog."""
        self.last_ping = time.time()
    
    def _watchdog(self):
        while self.running:
            time.sleep(5)
            if (time.time() - self.last_ping) > self.timeout:
                logger.critical("Watchdog timeout! Main loop is frozen!")
                # Force restart or set degraded mode flag
                # Could even forcibly restart the server
                os._exit(1)  # Nuclear option - force exit
```

**Effort:** 2 hours  
**Risk:** High - may cause data loss, requires careful tuning

---

## Recommended Approach

**Hybrid: Options 1 + 2**

### Phase A: Immediate Fix (Option 2)
- Add `asyncio.wait_for()` timeout wrappers to all Modbus operations
- Set reasonable timeout (10 seconds)
- Gracefully handle timeout by using cached data
- Display "Connection Lost" banner on frontend
- **Prevents infinite loop**

**Effort:** 1-2 hours  
**Outcome:** Application stays responsive even when aGate is offline

### Phase B: Robust Solution (Option 1)
- Implement circuit breaker pattern
- Integrate with existing `network_health.py`
- Add self-healing (auto-close circuit when ping succeeds)
- Exponential backoff on retries
- **Prevents excessive network traffic during outages**

**Effort:** 2-3 hours  
**Outcome:** Production-grade resilience

---

## Implementation Files

### Files to Modify

1. **`src/modbus_client_franklinwh.py`**
   - Add timeout parameter to async operations
   - Implement circuit breaker
   - Add connection state tracking

2. **`src/network_health.py`**
   - Add `check_agate_reachable()` method
   - Integration with Modbus client
   - Periodic health check loop

3. **`src/web_server.py`**
   - Catch connection errors gracefully
   - Return degraded status to frontend
   - Don't let exceptions propagate to event loop

4. **`static/js/app.js`**
   - Handle "Connection Lost" state
   - Show warning banner
   - Display last known good data with timestamp

---

## Testing Plan

### Test Scenario 1: aGate Unreachable at Startup
```bash
# Block aGate IP at firewall
sudo iptables -A OUTPUT -d 192.168.0.110 -j DROP

# Start application
./run.sh

# Expected: App starts, shows "Connection Lost" banner, stays responsive
# NOT Expected: Infinite loop, frozen server
```

### Test Scenario 2: aGate Drops During Operation
```bash
# Start app normally
./run.sh

# Wait for connection
# Block aGate IP
sudo iptables -A OUTPUT -d 192.168.0.110 -j DROP

# Expected: Within 30s, shows "Connection Lost", data freezes at last known
# NOT Expected: Server hangs, must restart
```

### Test Scenario 3: aGate Returns
```bash
# Unblock aGate IP
sudo iptables -D OUTPUT -d 192.168.0.110 -j DROP

# Expected: Within 60s, connection resumes, "Connection Lost" clears
```

---

## Configuration

### Proposed Settings (`config.json`)

```json
{
  "modbus": {
    "timeout": 10,
    "max_retries": 3,
    "retry_backoff_base": 2,
    "circuit_breaker": {
      "enabled": true,
      "failure_threshold": 3,
      "recovery_timeout": 60,
      "half_open_timeout": 30
    }
  },
  "network_health": {
    "enabled": true,
    "check_interval": 30,
    "ping_count": 1,
    "ping_timeout": 2
  }
}
```

---

## Error Handling

### Graceful Degradation Strategy

When aGate becomes unreachable:

1. **First 10 seconds:** Retry with exponential backoff
2. **After 3 failures:** Open circuit breaker
3. **UI shows:** "Connection Lost - Last update: 10:15 AM"
4. **Data display:** Freeze at last known good values
5. **Background:** Health check pings every 30s
6. **Recovery:** When ping succeeds, close circuit, resume polling

### User Experience

```
┌─────────────────────────────────────────────────┐
│ ⚠️ Connection Lost to aGate                     │
│ Last update: 10:15:43 AM (2 minutes ago)        │
│ Showing last known data. Retrying...            │
│ [Retry Now] [Diagnostics]                       │
└─────────────────────────────────────────────────┘
```

---

## Priority Justification

**🔴 CRITICAL** because:
- ✅ Complete application outage
- ✅ Requires manual restart (no auto-recovery)
- ✅ Affects production availability
- ✅ User cannot access dashboard during WiFi issues
- ✅ Australian WiFi networks are notoriously unstable

**Timeline:** This should be fixed **before** any feature work

---

## Related TODOs

- **`TODO_WIFI_WARNING.md`** - Network health monitoring (Phase 1 complete)
- **`TODO_CONNECTION_UX.md`** - Connection banner UX improvements
- **`TODO_DIAGNOSTICS_UI.md`** - Could add connection diagnostics panel

---

## Technical Notes

### Why This Happens

1. **Synchronous blocking:** Modbus library may have synchronous calls that block event loop
2. **No timeout:** `pymodbus` client created without proper timeout
3. **Infinite retries:** No retry limit on connection attempts
4. **No circuit breaker:** Continues trying even when clearly unreachable

### Why It Requires Restart

- Event loop is blocked/frozen
- HTTP server can't process new requests
- No watchdog to detect and recover
- Python GIL may be held by blocking Modbus call

---

## User's Specific Feedback

> "When the FranklinWH aGate drops off wifi - the application goes into an infinite loop. it should do a health check - like usage ping to determine it has dropped off. This error is not recoverable and the web.app servers needs to be restate."

**Key Requirements:**
- ✅ Health check using ping (already exists in `network_health.py`)
- ✅ Detect when aGate drops off network
- ✅ Make error **recoverable** (don't require restart)
- ✅ Provide multiple solution options

**Options provided:** 3 approaches (timeout wrapper, circuit breaker, watchdog)  
**Recommended:** Hybrid approach (timeout + circuit breaker)

---

## Next Steps

1. ✅ Choose implementation approach (recommend Option 2 immediate + Option 1 follow-up)
2. ✅ Implement timeout wrappers on all Modbus operations
3. ✅ Test with simulated network outage
4. ✅ Add circuit breaker with health check integration
5. ✅ Update frontend to show connection state
6. ✅ Deploy and monitor in production

**Estimated Total Effort:** 3-5 hours (both phases)
