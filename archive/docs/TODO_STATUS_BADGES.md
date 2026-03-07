# TODO: Status Badges for aGate & MQTT on Top Status Bar

## Objective
Add clear status badges for aGate and MQTT connection state to the fixed top status bar, and review/consolidate the multiple connection state indicators currently scattered across the dashboard.

## Current State Analysis

### Existing Connection Status Indicators

#### 1. **Device Status Bar** (Top, Fixed - Does Not Scroll)
Location: [templates/base.html](file:///home/david/dev/modbus/templates/base.html#L265-L331)

Current indicators:
- ✅ Device Serial (from aGate)
- ✅ Control Mode (LOCAL/REMOTE with warning)
- ✅ Grid Connection (Connected/Disconnected)
- ✅ Charging Status (Charging/Discharging/Standby)
- ✅ Backend Connection (Connected/Disconnected)
- ✅ MQTT Stats (message count, last publish time)

**Missing**:
- ❌ **aGate Connection Status Badge** (clear visual indicator)
- ❌ **MQTT Connection Status Badge** (enabled/connected/disconnected/error)

#### 2. **Sidebar Footer** (Bottom-Left, Scrollable)
Location: [templates/base.html](file:///home/david/dev/modbus/templates/base.html#L174-L193)

Shows:
- Green/Red dot (connected/disconnected)
- "Connected" / "Disconnected" text
- Last update timestamp
- Version number

#### 3. **Header Connection Banner** (Top-Right)
Location: [templates/base.html](file:///home/david/dev/modbus/templates/base.html#L212-L225)

Shows:
- "CONNECTING..." badge (amber) when not connected
- "MOCK MODE" badge (purple) when in mock mode

### Problem
- **3 different connection state displays** showing overlapping information
- **No dedicated badge for aGate status** (is Modbus connection healthy?)
- **No dedicated badge for MQTT status** (is MQTT broker connected and publishing?)
- MQTT stats show message count but not connection health
- Confusion between "Backend API connection" vs "Modbus/aGate connection"

## Proposed Solution

### Add Status Badges to Device Status Bar

Update the fixed top status bar to include:

```
┌────────────────────────────────────────────────────────────┐
│ [aGate: 2A17FA21]  │  [🔓 No Ctrl]  │  [⚡ Grid: ✓]  │     │
│                    │                 │                      │
│ [🟢 aGate: OK]  │  [🟢 MQTT: Connected]  │  [⚙️ 1.2k msgs] │
└────────────────────────────────────────────────────────────┘
```

### Badge Designs

#### aGate Status Badge
```html
<div class="flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium"
     :class="{
         'bg-emerald-100 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400': connected && backendConnected,
         'bg-amber-100 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400': !connected && backendConnected,
         'bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-400': !backendConnected
     }">
    <i class="fas fa-server text-[10px]"></i>
    <span>aGate:</span>
    <span x-text="connected && backendConnected ? 'OK' : (!backendConnected ? 'Offline' : 'Connecting')"></span>
</div>
```

**States**:
- 🟢 **Connected** (green): Modbus + Backend both OK
- 🟡 **Connecting** (amber): Backend OK, Modbus connecting
- 🔴 **Offline** (red): Backend down

#### MQTT Status Badge
```html
<div class="flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium"
     x-show="config.mqtt.enabled"
     :class="{
         'bg-emerald-100 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400': mqttConnected,
         'bg-amber-100 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400': !mqttConnected && config.mqtt.enabled,
         'bg-gray-100 dark:bg-gray-800 text-gray-500': !config.mqtt.enabled
     }">
    <i class="fas fa-broadcast-tower text-[10px]"></i>
    <span>MQTT:</span>
    <span x-text="!config.mqtt.enabled ? 'Disabled' : (mqttConnected ? 'OK' : 'Error')"></span>
</div>
```

**States**:
- 🟢 **Connected** (green): MQTT broker connected and publishing
- 🟡 **Error** (amber): MQTT enabled but can't connect
- ⚫ **Disabled** (gray): MQTT not configured

### Data Requirements

#### New Alpine.js State
```javascript
mqttConnected: false,  // Track MQTT broker connection
mqttLastError: null,   // Last MQTT error message
```

#### API Enhancement
```python
@app.get("/api/mqtt/status")
async def get_mqtt_status():
    return {
        "enabled": mqtt_config.enabled,
        "connected": mqtt_client.is_connected() if mqtt_client else False,
        "last_error": mqtt_client.last_error if mqtt_client else None,
        "stats": {
            "messages_published": mqtt_client.messages_sent,
            "last_publish_seconds_ago": mqtt_client.seconds_since_last_publish
        }
    }
```

## Implementation Plan

### Phase 1: Add MQTT Connection State
- [ ] Update `/api/mqtt/status` endpoint to include `connected` boolean
- [ ] Add `mqttConnected` to Alpine.js state
- [ ] Poll MQTT status every 5 seconds (same as MQTT stats polling)
- [ ] Update Alpine.js `fetchMQTTStats()` to set `mqttConnected`

### Phase 2: Add Status Badges
- [ ] Create aGate status badge in Device Status Bar
- [ ] Create MQTT status badge in Device Status Bar
- [ ] Add hover tooltips with more details
- [ ] Test different states (connected, disconnected, error)

### Phase 3: Consolidate Connection Indicators
- [ ] **Keep**: Device Status Bar (top fixed) - **PRIMARY status display**
- [ ] **Keep**: Sidebar footer - Shows last update timestamp (useful)
- [ ] **Review**: Header connection banner - May be redundant now
- [ ] Consider removing "CONNECTING..." banner if status bar is clear enough

### Phase 4: Enhanced Status Bar Layout
- [ ] Reorganize status bar for better visual hierarchy
- [ ] Group related items (Device | Connectivity | Activity)
- [ ] Make badges clickable for more details
- [ ] Add tooltips explaining each status

## Proposed Status Bar Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  DEVICE INFO          │  CONNECTIVITY        │  ACTIVITY               │
│  ─────────────────────────────────────────────────────────────────────  │
│  🖥️ 2A17FA21           │  🟢 aGate: OK         │  ⚡ Discharging        │
│  🔓 No Ctrl            │  🟢 MQTT: OK          │  ⚙️ 1.2k msgs (5s)    │
│  ⚡ Grid: Connected    │                      │                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Alternative Compact Layout
```
[🖥️ aGate X]  [🔓 No Ctrl]  [⚡ Grid ✓]  [⚡ Discharging]  │  [🟢 aGate]  [🟢 MQTT]  [⚙️ 1.2k msgs]
```

## Badge Click Actions

### aGate Badge Click
```javascript
@click="showAGateDetails()"
```
- Open modal/popover with:
  - Last successful poll time
  - Modbus connection details (host, port, unit ID)
  - Recent errors
  - Connection quality stats
  - "Test Connection" button

### MQTT Badge Click
```javascript
@click="showMQTTDetails()"
```
- Open modal/popover with:
  - Broker connection status
  - Last publish time
  - Messages published count
  - Recent errors
  - "Reconnect" button
  - Link to MQTT Admin page

## Backend Changes

### Enhanced MQTT Client State Tracking
```python
class MQTTClient:
    def __init__(self):
        self.is_connected_flag = False
        self.last_error = None
        self.last_error_time = None
        self.connection_attempts = 0
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected_flag = True
            self.last_error = None
        else:
            self.is_connected_flag = False
            self.last_error = f"Connection failed: {rc}"
            
    def on_disconnect(self, client, userdata, rc):
        self.is_connected_flag = False
        if rc != 0:
            self.last_error = "Unexpected disconnect"
```

### Add to `/api/mqtt/status` Response
```json
{
    "enabled": true,
    "connected": true,
    "last_error": null,
    "connection_attempts": 5,
    "uptime_seconds": 3600,
    "stats": {
        "messages_published": 1240,
        "last_publish_seconds_ago": 5
    }
}
```

## Visual States Reference

### aGate Badge States

| State | Color | Icon | Text | Tooltip |
|-------|-------|------|------|---------|
| Connected | Green | 🟢 | aGate: OK | Modbus connected to 192.168.0.110:502 |
| Connecting | Amber | 🟡 | aGate: Connecting | Attempting to connect... |
| Offline | Red | 🔴 | aGate: Offline | Backend server unreachable |
| Mock Mode | Purple | 🧪 | aGate: Mock | Using simulated data |

### MQTT Badge States

| State | Color | Icon | Text | Tooltip |
|-------|-------|------|------|---------|
| Connected | Green | 🟢 | MQTT: OK | Publishing to broker at 192.168.0.109 |
| Error | Amber | 🟡 | MQTT: Error | Can't connect to broker |
| Disconnected | Red | 🔴 | MQTT: Down | Connection lost |
| Disabled | Gray | ⚫ | MQTT: Off | MQTT not configured |

## Mobile Responsiveness

### Desktop View (>1024px)
- Show full status bar with all badges
- All text labels visible

### Tablet View (768px - 1024px)
- Compress text labels ("aGate: OK" → "aGate ✓")
- Keep all badges

### Mobile View (<768px)
- Show only icon badges (no text)
- Tap to show tooltip/popover
- Consider collapsing into dropdown menu

## Testing Checklist

- [ ] Test aGate status badge in all states
- [ ] Test MQTT status badge in all states
- [ ] Test with MQTT disabled
- [ ] Test with backend disconnected
- [ ] Test in Mock Mode
- [ ] Test responsive behavior on mobile
- [ ] Test badge click actions
- [ ] Test tooltips
- [ ] Verify no layout shift when badges change state

## Alternative: Status Dropdown Menu

Consider adding a "System Status" dropdown button:

```html
<button @click="statusMenuOpen = true" class="px-3 py-1 rounded-lg hover:bg-gray-100">
    <i class="fas fa-info-circle"></i>
    <span class="ml-1">Status</span>
    <!-- Badge indicators -->
    <span class="w-2 h-2 rounded-full" :class="allSystemsOK ? 'bg-green-500' : 'bg-amber-500'"></span>
</button>
```

Dropdown shows:
- ✅ aGate Connection: OK
- ✅ MQTT Broker: OK
- ✅ Backend API: OK
- ⚠️ WiFi Quality: Degraded
- Links to diagnostics and admin pages

## Priority
Medium - Improves visibility of critical system states, helps users quickly diagnose issues

## Related TODOs
- `TODO_WIFI_WARNING.md` - Network quality should also get a badge
- `TODO_ADMIN_SETTINGS_PAGE.md` - Badge clicks could link to connection settings

## Notes
- Consider showing WiFi quality as a third badge if network monitoring is enabled
- Badge states should be intuitive (green = good, amber = warning, red = error)
- Keep badges small and unobtrusive but visible
- Consider animation/pulse for state transitions
- Don't overwhelm the status bar - keep it clean and scannable
