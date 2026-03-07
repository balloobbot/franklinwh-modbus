# ⚠️ CRITICAL: Battery Control Operating Mode Requirement

**Last Updated:** 2026-02-14

---

## 🚨 SAFETY REQUIREMENT

**Battery controls (Model 702/704) should ONLY be used when Operating Mode = Self-Consumption.**

---

## Why This Matters

FranklinWH has sophisticated built-in orchestration strategies that manage battery charging and discharging based on the selected operating mode:

### Built-In Orchestration Strategies

| Operating Mode | Internal Strategy | Conflicts with External Control? |
|----------------|-------------------|----------------------------------|
| **Self-Consumption** | Manual user control | ✅ NO - Safe to use |
| **Time-of-Use (TOU)** | Charge during off-peak, discharge during peak | ❌ YES - Dangerous conflict |
| **Backup Reserve** | Maintain reserve percentage, backup priority | ❌ YES - Dangerous conflict |

### The Conflict

```
Example Scenario:
┌──────────────────────────────────────────┐
│ FranklinWH Internal State:              │
│ - Operating Mode: Time-of-Use           │
│ - Strategy: Charge 0-6am (off-peak)     │
│ - Current Time: 2:00 AM                 │
│ - Action: Charging at max rate (5kW)   │
└──────────────────────────────────────────┘
                    ↓
         External Modbus Control:
         Set WChaRteMax = 1000W (1kW limit)
                    ↓
┌──────────────────────────────────────────┐
│ CONFLICT!                                │
│ - TOU strategy wants max charging        │
│ - External limit restricts to 1kW        │
│ - Unpredictable behavior                 │
│ - May fail to charge enough for peak     │
│ - Violates user's TOU optimization       │
└──────────────────────────────────────────┘
```

---

## Additional Conflict Scenarios

### 1. VPP (Virtual Power Plant) Enrollment

**If user is enrolled in a VPP service:**
- VPP provider sends control commands
- External Modbus control conflicts with VPP
- May violate VPP contract terms
- Could result in penalties or service termination

### 2. FranklinWH App Schedules

**If user has active schedules in FranklinWH App:**
- App-based TOU schedules conflict with Modbus limits
- User confusion: "Why isn't my schedule working?"
- App display may show incorrect state

### 3. Backup Reserve Management

**If in Backup Reserve mode:**
- System maintains minimum reserve percentage
- External discharge limits may prevent reserve maintenance
- Critical backup power may not be available during outage

---

## Current Technical Limitation

### FranklinWH Extension Registers (15507-15509)

| Register | Function | Current Status |
|----------|----------|----------------|
| 15507 | Operating Mode | ✅ READ / ❌ WRITE |
| 15508 | Self-Consumption Reserve | ✅ READ / ❌ WRITE |
| 15509 | TOU Reserve | ✅ READ / ❌ WRITE |

**Problem:**
- Cannot programmatically SET operating mode to Self-Consumption
- Cannot verify mode before applying battery controls
- Reliance on user manual configuration

**Status:**
- Write access requested from FranklinWH support
- Pending response

---

## Implementation Requirements

### 1. UI Warning Banner (MANDATORY)

**When user accesses battery control features, display:**

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️  OPERATING MODE CHECK REQUIRED                       │
│                                                          │
│ Battery controls should ONLY be used in                 │
│ Self-Consumption mode.                                  │
│                                                          │
│ Current Mode: Time-of-Use  ❌                           │
│                                                          │
│ Please change to Self-Consumption mode in the          │
│ FranklinWH App before using these controls.            │
│                                                          │
│ [×] I understand and have set Self-Consumption mode    │
│                                                          │
│ Why? External controls conflict with built-in TOU/     │
│ Backup strategies and may cause unpredictable behavior │
└─────────────────────────────────────────────────────────┘
```

### 2. Read Current Operating Mode

```python
# Before allowing battery control writes
current_mode = await read_extension_register(15507)

mode_map = {
    1: "Backup Reserve",
    2: "Self-Consumption", 
    3: "Time-of-Use"
}

if current_mode != 2:  # Not Self-Consumption
    return {
        "error": "Operating mode must be Self-Consumption",
        "current_mode": mode_map.get(current_mode),
        "action_required": "Change mode in FranklinWH App"
    }
```

### 3. Dashboard Status Indicator

```
┌─ Power Control Status ─────────────────┐
│ Operating Mode:  Self-Consumption  ✅  │
│ Controls:        SAFE TO USE           │
└─────────────────────────────────────────┘

┌─ Power Control Status ─────────────────┐
│ Operating Mode:  Time-of-Use  ⚠️       │
│ Controls:        NOT RECOMMENDED        │
│                  (Conflicts with TOU)  │
└─────────────────────────────────────────┘
```

---

## Safe Usage Checklist

**Before using battery control features:**

- [ ] Check current operating mode (Dashboard → Control → Operating Mode)
- [ ] Verify mode is "Self-Consumption"
- [ ] Confirm NOT enrolled in VPP service
- [ ] Verify no active TOU schedules in FranklinWH App
- [ ] Understand you are taking manual control
- [ ] Monitor system behavior after applying controls

---

## Migration Path (When Write Access Granted)

**Once FranklinWH enables write access to extension registers:**

```python
async def enable_safe_battery_control():
    """Automatically switch to Self-Consumption mode"""
    
    # Read current mode
    current_mode = await read_extension_register(15507)
    
    # Store original mode for rollback
    original_mode = current_mode
    
    # Switch to Self-Consumption (mode 2)
    if current_mode != 2:
        await write_extension_register(15507, 2)
        logger.info("Switched to Self-Consumption mode for battery control")
    
    return original_mode

async def restore_original_mode(original_mode: int):
    """Restore previous operating mode"""
    await write_extension_register(15507, original_mode)
    logger.info(f"Restored operating mode to {original_mode}")
```

**This enables:**
- ✅ Automatic mode switching before control
- ✅ Automatic restoration after control session
- ✅ Safer user experience

---

## Documentation Requirements

### User-Facing Documentation

**Must clearly state:**
1. Battery controls only work safely in Self-Consumption mode
2. Do not use if enrolled in VPP
3. Do not use with active TOU schedules
4. How to check and change operating mode

### API Documentation

**Endpoints must:**
1. Check operating mode before accepting control commands
2. Return clear error messages if mode is incompatible
3. Recommend user action to resolve

---

## Summary

**Critical Rule:** 🚨 **Self-Consumption Mode ONLY**

- ✅ Safe in Self-Consumption mode
- ❌ Dangerous in TOU or Backup modes
- ⏳ Waiting for write access to automate mode checking/switching

**Until write access is granted:**
- Rely on manual user configuration
- Display prominent warnings
- Read-only verification where possible

This is not just a recommendation - it's a **safety requirement** to prevent system conflicts and user confusion.
