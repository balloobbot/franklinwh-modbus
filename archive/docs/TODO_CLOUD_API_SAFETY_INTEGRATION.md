# TODO: Cloud API Integration for Safe Battery Control

**Status:** READY TO IMPLEMENT (Interim Solution)  
**Priority:** HIGH  
**Created:** 2026-02-14

---

## Background

**Problem:**
- FranklinWH Extension registers (15507-15509) are READ-ONLY via Modbus
- Cannot programmatically check/set operating mode via Modbus
- Cannot verify VPP enrollment via Modbus
- Battery controls (Model 702/704) should ONLY be used in Self-Consumption mode

**Solution:**
Use existing `franklinwh.client.py` Cloud API as interim solution!

---

## Cloud API Capabilities

The existing Cloud API (`franklinwh.client.py`) provides:

| Feature | Cloud API | Modbus Status |
|---------|-----------|---------------|
| Get Operating Mode | ✅ Available | ✅ Read-only (15507) |
| Set Operating Mode | ✅ Available | ❌ Write-pending |
| Check VPP Enrollment | ✅ Available | ❌ Not available |
| Get Reserve Settings | ✅ Available | ✅ Read-only (15508/15509) |
| Set Reserve Settings | ✅ Available | ❌ Write-pending |

**This gives us everything we need for safe battery control!**

---

## Implementation Approach

### Phase 1: Pre-Flight Safety Check (Cloud API)

**Before allowing Model 702/704 battery control writes:**

```python
# src/battery_control_safety.py

from franklinwh.client import FranklinWHCloudClient

async def check_battery_control_safety(cloud_client: FranklinWHCloudClient):
    """
    Verify system is safe for battery control using Cloud API
    
    Returns:
        dict: {
            "safe": bool,
            "current_mode": str,
            "vpp_enrolled": bool,
            "warnings": list[str]
        }
    """
    
    # Get current operating mode via Cloud API
    mode_info = await cloud_client.get_operating_mode()
    current_mode = mode_info.get("mode")  # "backup", "self-consumption", "tou"
    
    # Check VPP enrollment
    vpp_info = await cloud_client.get_vpp_status()
    vpp_enrolled = vpp_info.get("enrolled", False)
    
    warnings = []
    safe = True
    
    # Check operating mode
    if current_mode != "self-consumption":
        warnings.append(f"Operating mode is '{current_mode}' (should be 'self-consumption')")
        safe = False
    
    # Check VPP enrollment
    if vpp_enrolled:
        warnings.append("System is enrolled in VPP - battery control may conflict with VPP provider")
        safe = False
    
    return {
        "safe": safe,
        "current_mode": current_mode,
        "vpp_enrolled": vpp_enrolled,
        "warnings": warnings
    }
```

### Phase 2: Automatic Mode Switching (Optional)

**If user consents, auto-switch to Self-Consumption:**

```python
async def enable_safe_battery_control_mode(cloud_client: FranklinWHCloudClient):
    """
    Switch to Self-Consumption mode via Cloud API
    
    Returns:
        str: Previous mode (for restoration)
    """
    
    # Get current mode
    mode_info = await cloud_client.get_operating_mode()
    previous_mode = mode_info.get("mode")
    
    # Switch to self-consumption if needed
    if previous_mode != "self-consumption":
        await cloud_client.set_operating_mode("self-consumption")
        logger.info(f"Switched from '{previous_mode}' to 'self-consumption' for battery control")
    
    return previous_mode

async def restore_operating_mode(cloud_client: FranklinWHCloudClient, mode: str):
    """Restore previous operating mode"""
    await cloud_client.set_operating_mode(mode)
    logger.info(f"Restored operating mode to '{mode}'")
```

### Phase 3: Integrated Control Flow

```python
# API endpoint: /api/battery/control/limits

@app.post("/api/battery/control/limits")
async def set_battery_limits(
    charge_kw: float,
    discharge_kw: float,
    auto_switch_mode: bool = False
):
    """
    Set battery charge/discharge limits with safety checks
    
    Args:
        charge_kw: Charge limit in kW
        discharge_kw: Discharge limit in kW
        auto_switch_mode: If True, auto-switch to Self-Consumption
    """
    
    # Step 1: Safety check via Cloud API
    safety_check = await check_battery_control_safety(cloud_client)
    
    if not safety_check["safe"]:
        if not auto_switch_mode:
            # Return error with instructions
            return {
                "error": "Unsafe operating mode",
                "current_mode": safety_check["current_mode"],
                "vpp_enrolled": safety_check["vpp_enrolled"],
                "warnings": safety_check["warnings"],
                "action_required": "Set auto_switch_mode=true or manually change mode in FranklinWH App"
            }
        else:
            # Auto-switch to Self-Consumption
            previous_mode = await enable_safe_battery_control_mode(cloud_client)
            # Store for potential restoration
            session["previous_mode"] = previous_mode
    
    # Step 2: Apply limits via SunSpec2 Modbus
    await modbus_client.write_point("702.WChaRteMax", int(charge_kw * 1000))
    await modbus_client.write_point("702.WDisChaRteMax", int(discharge_kw * 1000))
    
    return {
        "status": "success",
        "charge_limit_w": int(charge_kw * 1000),
        "discharge_limit_w": int(discharge_kw * 1000),
        "mode_switched": auto_switch_mode and not safety_check["safe"]
    }
```

---

## UI Integration

### Warning Banner (if mode is unsafe)

```html
<div class="alert alert-warning" v-if="!safetyCheck.safe">
  <h4>⚠️ Operating Mode Check Required</h4>
  <p>Current Mode: <strong>{{ safetyCheck.current_mode }}</strong></p>
  <p v-if="safetyCheck.vpp_enrolled">⚠️ VPP Enrollment Detected</p>
  
  <ul>
    <li v-for="warning in safetyCheck.warnings">{{ warning }}</li>
  </ul>
  
  <button @click="autoSwitchMode">
    Switch to Self-Consumption Mode Automatically
  </button>
  
  <p class="text-muted">
    Or manually change mode in the FranklinWH App
  </p>
</div>
```

### Status Indicator

```html
<div class="control-status">
  <span class="badge badge-success" v-if="safetyCheck.safe">
    ✅ Safe for Battery Control
  </span>
  <span class="badge badge-danger" v-else>
    ⚠️ Unsafe Mode ({{ safetyCheck.current_mode }})
  </span>
</div>
```

---

## Configuration

```json
// config/battery_control.json
{
  "safety_checks": {
    "require_self_consumption_mode": true,
    "allow_auto_mode_switch": true,
    "block_if_vpp_enrolled": true
  },
  "cloud_api": {
    "enabled": true,
    "use_for_mode_verification": true,
    "use_for_mode_switching": true
  }
}
```

---

## Benefits of This Approach

| Benefit | Description |
|---------|-------------|
| **Immediate Solution** | No waiting for FranklinWH to enable Modbus writes |
| **Complete Safety** | Can verify VPP enrollment (not available via Modbus) |
| **Auto-Recovery** | Can auto-switch to safe mode with user consent |
| **User-Friendly** | Clear warnings and one-click mode switching |
| **Fallback Option** | When Modbus writes are enabled, can switch to pure Modbus |

---

## Migration Path

**Now (Interim):**
- ✅ Use Cloud API for mode checking and switching
- ✅ Use SunSpec2 Modbus for battery control

**Future (When Modbus Writes Enabled):**
- 🔲 Optionally switch to pure Modbus approach
- 🔲 Keep Cloud API for VPP verification (not available via Modbus)
- 🔲 Add config flag: `prefer_modbus_over_cloud_api: true/false`

---

## Implementation Checklist

- [ ] Review `franklinwh.client.py` Cloud API methods
- [ ] Identify exact API calls for:
  - [ ] `get_operating_mode()`
  - [ ] `set_operating_mode(mode)`
  - [ ] `get_vpp_status()`
- [ ] Implement `battery_control_safety.py` module
- [ ] Add safety check to battery control API endpoints
- [ ] Update dashboard UI with warning banner
- [ ] Add "Auto-Switch Mode" button
- [ ] Test full flow:
  - [ ] Start in TOU mode
  - [ ] Attempt battery control (should warn)
  - [ ] Auto-switch to Self-Consumption
  - [ ] Apply battery control (should succeed)
  - [ ] Restore previous mode
- [ ] Documentation updates

---

## References

- Cloud API client: `franklinwh.client.py`
- Battery control safety: `BATTERY_CONTROL_WARNING.md`
- SunSpec2 control points: `sunspec2_control_points_analysis.md`
- Test results: `walkthrough.md`

---

**This is the best interim solution while waiting for FranklinWH support response!**
