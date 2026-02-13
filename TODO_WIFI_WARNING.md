# Quick WiFi Detection -  Implementation TODO

## Status

✅ **Phase 1: Backend Complete**
- Created `src/network_health.py` with ping-based detection
- Integrated into `src/main.py` (runs startup ping check)
- Enhanced `/api/health` endpoint with network statistics
- Server detects "degraded" quality from WiFi latency/jitter

## Remaining Work (TODO)

### 1. Dashboard Warning Banner (IN PROGRESS)
**Location**: Add to `templates/dashboard.html` after line 43

**Pattern**: Similar to existing danger modals but less extreme

**TODO**: 
```html
<!-- WiFi Warning Banner (show if network quality is CRITICAL or DEGRADED) -->
<div x-show="healthData?.network?.quality === 'critical' || healthData?.network?.quality === 'degraded'"
     class="mb-4 bg-amber-50 dark:bg-amber-900/20 border-2 border-amber-500 rounded-xl p-4">
    <!-- Warning content here -->
</div>
```

### 2. Fetch Health Data
**Location**: Alpine.js init in `templates/dashboard.html`

**TODO**: Add health data fetch to existing data polling
```javascript
// In your existing data fetch interval, also fetch health
const health = await fetch('/api/health').then(r => r.json());
this.healthData = health;
```

### 3. Optional: Periodic Ping Checks
**Location**: ` src/main.py` - add to background tasks

**TODO**: Run ping check every 5 minutes (currently only runs on startup)
```python
async def _network_health_loop(self):
    """Periodic network health checks."""
    while self.running:
        await asyncio.sleep(300)  # 5 minutes
        await self.network_monitor.ping_check(count=5)
```

### 4. Optional: WiFi Override Modal
**Location**: Create new modal in `templates/dashboard.html`

**Pattern**: Like "EXTREME DANGER" modal at line 1512-1578

**TODO**:
- Add acknowledgment checkbox
- Maybe countdown timer (5-10 seconds)
- Override code could be "WIFI" or current date
- Only allow proceeding if user truly understands

## Testing Checklist

- [ ] Verify `/api/health` returns network data
- [ ] Check dashboard shows warning when quality is CRITICAL/DEGRADED
- [ ] Test warning dismissal (if implemented)
- [ ] Verify warning persists across page refreshes
- [ ] Test on actual Ethernet connection (should show "healthy")

## Notes

Network quality thresholds (from `network_health.py`):
- **HEALTHY**: <1% loss, <10ms latency (Ethernet-like)
- **DEGRADED**: 1-10% loss, 10-50ms latency  
- **CRITICAL**: >10% loss OR >50ms latency (WiFi/unstable)

Current user's WiFi: 0% loss, 20ms avg, 63ms max → **DEGRADED**

User mentioned they saw 75% packet loss earlier → **CRITICAL**
