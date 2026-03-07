# ⚡ CRITICAL: VPP Mode is AUTOMATIC

**Date:** 2026-02-15  
**CONFIRMED:** VPP Mode auto-switches when Modbus commands succeed

---

## 🎯 THE KEY DISCOVERY

### VPP Mode is NOT Something We Set

**VPP Mode is FranklinWH's AUTOMATIC RESPONSE to receiving Model 704 battery control commands.**

When you successfully write Model 704 registers (WSetEna, WSetMod, WSet), the FranklinWH system:
1. **Detects the battery control command**
2. **Automatically switches to VPP Mode** (Operating Mode = 4)
3. **Executes the command**

---

## ✅ PROOF from Yesterday (2026-02-14 20:30)

### What Happened

**Command sent via API:**
```bash
curl -X POST http://localhost:8080/api/battery/force_power \
  -H "Content-Type: application/json" \
  -d '{"power_watts": 0}'
```

**Modbus writes (Model 704):**
- WSetEna = 0 (disable)
- WSetMod = 0 (Absolute W)
- WSet = 0 (idle)

**FranklinWH Response:**
- ✅ Registers accepted
- ✅ **VPP Mode activated AUTOMATICALLY**
- ✅ Battery went to Standby
- ✅ User saw mode change in FranklinWH app

### User Quote (Line 11832)

> "I saw the battery mode change and the 'Run Status' changed to 'VPP Mode' - which means a remote app issued it a command :)"

---

## 🔍 What This Means

### We DO NOT need to:
- ❌ Manually set operating mode to VPP
- ❌ Write to register 15507
- ❌ Call any special "enable VPP" function
- ❌ Set Model 802 SetInvState

### We ONLY need to:
- ✅ Write Model 704 registers correctly
- ✅ FranklinWH detects this and switches to VPP automatically

---

## ⚠️ Why Current Tests Fail

**Today's tests (2026-02-15 01:40):**
- Registers write successfully ✅
- Values verify correctly ✅  
- **VPP Mode does NOT activate** ❌
- Battery doesn't respond ❌

**Hypothesis:**
Something is BLOCKING the automatic VPP mode switch. Possible causes:
1. Different system state prevents mode change
2. Missing prerequisite (Model 702 settings?)
3. Time-of-day restriction
4. Safety lock preventing mode change

---

## 📋 Complete Successful Sequence (2026-02-14)

### Commands from Conversation Logs

**Test 1: Discharge -3000W** (Line 11910)
```bash
curl -X POST http://localhost:8080/api/battery/force_power \
  -d '{"power_watts": -3000}'
```
Result: Registers wrote, WSet = -3000W

**Test 2: Charge +3000W** (Line 11922)
```bash  
curl -X POST http://localhost:8080/api/battery/force_power \
  -d '{"power_watts": 3000}'
```
Result: Registers wrote, WSet = 3000W, **VPP Mode activated**

**Test 3: Idle 0W** (Line 11979)
```bash
curl -X POST http://localhost:8080/api/battery/force_power \
  -d '{"power_watts": 0}'
```  
Result: Battery to Standby, **VPP Mode still active**

### Modbus Implementation (from API)

The API calls `modbus_client.py` which writes:
1. WSetEna = 0 (disable first)
2. WSetMod = 0 (Absolute W mode)
3. WSetRvrtTms = 0 (no auto-revert)
4. WSet = [high, low] (power value as int32)
5. WSetEna = 1 (enable if power ≠ 0)

**FranklinWH sees these writes and AUTO-SWITCHES to VPP Mode**

---

## 🎯 THE ANSWER

**Question:** How do we get FranklinWH into VPP Mode?

**Answer:** **You don't.** FranklinWH automatically switches to VPP Mode when it detects valid battery control commands via Model 704.

**The real question:** Why aren't today's commands triggering the auto-switch?

---

## 📝 Documentation Status

✅ **THIS DOCUMENT** - Primary VPP auto-switch documentation  
⚠️ All other documents need updating to reflect this

**User has stated this 3+ times - THIS IS THE KEY FINDING**
