# Battery Control Safety - Usage Examples

## Mode 1: Modbus-Only (Default - No Cloud Credentials)

**Privacy-first, offline-capable, zero cloud dependency**

```python
from src.battery_control_safety import create_safety_manager

# Create safety manager WITHOUT Cloud credentials
safety = await create_safety_manager(
    modbus_client=modbus_client
    # No cloud_username, cloud_password, or agate_serial needed!
)

# Check safety
result = await safety.check_battery_control_safety()

# Result will show:
# ✅ safe: True/False (based on operating mode from Modbus register 15507)
# ⚠️  warnings: [
#       "⚠️ VPP enrollment check: NOT AVAILABLE (Cloud credentials not configured)",
#       "ℹ️  To enable VPP checking, add FranklinWH Cloud credentials in Settings"
#     ]
# ✅ vpp_check_available: False
# ✅ auto_switch_available: False
# ✅ cloud_api_enabled: False
```

**UI Display:**
```
┌─ Battery Control Safety Check ───────────────────┐
│ Mode: Self-Consumption ✅                        │
│                                                   │
│ ⚠️  VPP Check: NOT AVAILABLE                     │
│     (Add Cloud credentials to enable)             │
│                                                   │
│ ⚠️  Auto-Switch: NOT AVAILABLE                   │
│     (Manual mode change required)                 │
│                                                   │
│ [Proceed Anyway] [Cancel]                        │
└───────────────────────────────────────────────────┘
```

---

## Mode 2: Cloud-Enhanced (Optional - With Credentials)

**Full feature set: VPP checking + auto-mode switching**

```python
from src.battery_control_safety import create_safety_manager

# Create safety manager WITH Cloud credentials
safety = await create_safety_manager(
    modbus_client=modbus_client,
    cloud_username="user@example.com",  # Optional
    cloud_password="password",          # Optional
    agate_serial="10060006A02F24170091" # Optional (can read from Modbus)
)

# Check safety
result = await safety.check_battery_control_safety()

# Result will show:
# ✅ safe: True/False (checked via Modbus first, Cloud API fallback)
# ✅ vpp_enrolled: True/False (checked via Cloud API)
# ✅ vpp_programme_name: "Example VPP Provider" or None
# ✅ vpp_check_available: True
# ✅ auto_switch_available: True
# ✅ cloud_api_enabled: True

# If not safe, can auto-switch!
if not result.safe and result.auto_switch_available:
    previous_mode = await safety.enable_safe_battery_control_mode()
    # ... perform battery control ...
    await safety.restore_operating_mode(previous_mode)
```

**UI Display:**
```
┌─ Battery Control Safety Check ───────────────────┐
│ Mode: Time-of-Use ⚠️                             │
│                                                   │
│ ✅ VPP Check: NOT ENROLLED                       │
│                                                   │
│ ⚠️  Mode conflict detected!                      │
│     External control may interfere with TOU       │
│                                                   │
│ [Auto-Switch to Self-Consumption] [Cancel]       │
└───────────────────────────────────────────────────┘
```

---

## API Endpoint Example

```python
@app.post("/api/battery/limits/kw")
async def set_battery_limits_kw(
    charge_kw: float,
    discharge_kw: float,
    auto_switch_mode: bool = False
):
    """Set battery limits in kW"""
    
    # Get Modbus client
    modbus = await app.state.connection_manager.get_client()
    if not modbus:
        raise HTTPException(503, "Modbus not available")
    
    # Get Cloud credentials from config (if user provided them)
    config = config_manager.get_config()
    cloud_user = config.get("cloud_api", {}).get("username")
    cloud_pass = config.get("cloud_api", {}).get("password")
    
    # Create safety manager (works with OR without Cloud credentials!)
    safety = await create_safety_manager(
        modbus_client=modbus,
        cloud_username=cloud_user,  # May be None - that's OK!
        cloud_password=cloud_pass   # May be None - that's OK!
    )
    
    # Safety check
    result = await safety.check_battery_control_safety()
    
    if not result.safe:
        if auto_switch_mode and result.auto_switch_available:
            # Auto-switch enabled AND Cloud API available
            await safety.enable_safe_battery_control_mode(result.current_mode_id)
        else:
            # Return error with guidance
            return {
                "error": "Unsafe operating mode",
                "current_mode": result.current_mode,
                "warnings": result.warnings,
                "vpp_check_available": result.vpp_check_available,
                "auto_switch_available": result.auto_switch_available,
                "action_required": (
                    "Change mode to Self-Consumption manually in FranklinWH App"
                    if not result.auto_switch_available
                    else "Enable auto_switch_mode or change manually"
                )
            }
    
    # Safe to proceed - write to Model 702
    await modbus.write_sunspec2_point("702.WChaRteMax", int(charge_kw * 1000))
    await modbus.write_sunspec2_point("702.WDisChaRteMax", int(discharge_kw * 1000))
    
    return {
        "success": True,
        "charge_limit_w": int(charge_kw * 1000),
        "discharge_limit_w": int(discharge_kw * 1000),
        "mode_switched": auto_switch_mode and not result.safe
    }
```

---

## Configuration Schema

```json
{
  "cloud_api": {
    "username": "",  // OPTIONAL - leave blank for Modbus-only mode
    "password": "",  // OPTIONAL - leave blank for Modbus-only mode
    "enabled": false // OPTIONAL - enable enhanced features
  },
  "battery_control": {
    "allow_auto_mode_switch": true,
    "warn_on_vpp_enrollment": true,
    "require_self_consumption_mode": true
  }
}
```

---

## Feature Matrix

| Feature | Modbus-Only | Cloud-Enhanced |
|---------|-------------|----------------|
| **Operating Mode Check** | ✅ Via register 15507 | ✅ Via Modbus (Cloud fallback) |
| **VPP Enrollment Check** | ⚠️ NOT AVAILABLE | ✅ Available |
| **Auto-Mode Switching** | ⚠️ NOT AVAILABLE | ✅ Available |
| **Battery Control (702/704)** | ✅ Available | ✅ Available |
| **Privacy** | ✅ Perfect (local-only) | ⚠️ Cloud connection |
| **Offline Operation** | ✅ Yes | ⚠️ Requires internet |
| **Zero Configuration** | ✅ Works immediately | ❌ Requires credentials |

---

## Key Design Principles

1. **Privacy First**: Modbus-only by default, no forced cloud dependency
2. **Graceful Degradation**: Features marked "NOT AVAILABLE" instead of blocking
3. **User Choice**: Cloud enhancement is OPTIONAL, not REQUIRED
4. **Clear Communication**: Warnings explain what's unavailable and why
5. **Fallback Strategy**: Modbus primary, Cloud API secondary

---

## User Experience

**Without Cloud Credentials:**
- ✅ Battery control works perfectly
- ⚠️ Some features show "NOT AVAILABLE"
- 💡 Prompt to add credentials if user wants enhanced features
- 🔒 Perfect privacy - never contacts cloud

**With Cloud Credentials:**
- ✅ All features available
- ✅ Enhanced safety (VPP check)
- ✅ Convenience (auto-mode switch)
- 🌐 Cloud API used for enhancements

**This is the best of both worlds!**
