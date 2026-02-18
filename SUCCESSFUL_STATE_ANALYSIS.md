# Successful Battery Control State - 2026-02-14 20:30

**When:** 2026-02-14 approximately 20:30 (8:30pm)  
**Result:** Battery control command accepted, system switched to VPP Mode/Standby

## Screenshot Analysis

### FranklinWH App Display

**Power Flow:**
- Solar: 0.0 kW
- Consuming: 0.6 kW  
- Import: 0.6 kW
- aPower (battery): **0.0 kW**

**Battery Status:**
- State: **Standby** ✅
- Operating Mode: **VPP Mode** ✅
- SOC: **86%**

## Critical Observations

### 1. VPP Mode Active
The system **DID switch to VPP Mode** when the command was sent. This confirms:
- Battery control commands trigger automatic mode change
- VPP Mode is the correct mode for remote control

### 2. Standby State
Battery went to **Standby** (0.0 kW), which means:
- Command was accepted
- Battery stopped charging/discharging
- System responded to Model 704 control

### 3. System Configuration at Success Time

| Parameter | Value | Notes |
|-----------|-------|-------|
| Operating Mode | VPP Mode (4) | Auto-switched from previous mode |
| Battery State | Standby | Idle/not active |
| SOC | 86% | Well within safe operating range |
| Solar | 0.0 kW | Nighttime (8:30pm) |
| Home Load | 0.6 kW | Importing from grid |
| Battery Power | 0.0 kW | Idle as commanded |

## What Command Was Sent?

Based on the Standby state and conversation logs, likely commands:
1. **Set to idle (0W)** - Battery standby mode
2. **Set WSetEna = 0** - Disabled battery control
3. **Atomic write** with ControlMode=3, WSet=0

## Differences from Current Failed Tests

### Successful State (Yesterday 20:30)
- ✅ Operating Mode changed to VPP
- ✅ Battery went to Standby
- ✅ System responded to command

### Failed Tests (Today 01:40)
- ❌ Operating Mode stayed Self-Consumption
- ❌ Battery DCW = 0W (not responding)
- ❌ WSet writes but no physical effect

## Key Questions

1. **Was command sent FROM the FranklinWH app or via Modbus?**
   - If from app: We need to understand what the app does differently
   - If via Modbus: What registers/sequence did it use?

2. **What was operating mode BEFORE the command?**
   - Self-Consumption → VPP (mode change)
   - Already in VPP → stayed VPP

3. **Time of day factor?**
   - 20:30 = nighttime, no solar
   - Grid import active
   - Does this matter for battery control?

4. **Model 702 rate limits?**
   - Were WChaRteMax / WDisChaRteMax set?
   - Check if rate limits were configured

## Next Steps to Replicate

1. Check conversation logs around 20:30 yesterday for exact command
2. Try setting operating mode to VPP FIRST before battery command
3. Test at similar time (nighttime, no solar)
4. Check Model 702 rate limit configuration

## Hypothesis

**Battery control only works when:**
1. System is in VPP Mode (4), OR
2. Command automatically triggers VPP mode switch, AND
3. No conflicting settings block the mode change

**Current problem:**
- Operating mode not switching to VPP automatically
- Self-Consumption mode may override battery commands
- Missing prerequisite that allows mode switch
