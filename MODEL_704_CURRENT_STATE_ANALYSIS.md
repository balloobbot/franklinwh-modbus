# Model 704 Current Register State Analysis

**Date:** 2026-02-15 02:19  
**Source:** Direct Modbus read from 192.168.0.110 unit 2  
**Method:** Read PDU addresses 299-333 (Model 704 registers)

---

## 🔍 ACTUAL EVIDENCE - Current Register Values

### Critical Control Registers (WSet Control Block)

| PDU Addr | Protocol | Value | Hex | Register | Status |
|----------|----------|-------|-----|----------|--------|
| 321 | 40322 | 0 | 0x0000 | **WSetEna** | ❌ DISABLED |
| 322 | 40323 | 0 | 0x0000 | **WSetMod** | Absolute W mode |
| 323 | 40324 | 0 | 0x0000 | **WSet (high)** | 0W |
| 324 | 40325 | 0 | 0x0000 | **WSet (low)** | 0W |
| 330 | 40331 | 0 | 0x0000 | **WSetRvrtTms (high)** | No reversion |
| 331 | 40332 | 0 | 0x0000 | **WSetRvrtTms (low)** | No reversion |

**Combined WSet value:** 0W (idle)  
**Combined WSetRvrtTms:** 0 seconds (no auto-revert)

---

## ❓ CRITICAL UNKNOWN: Model 702 Control Registers

### What We DON'T Know

The reader shows Model 704 but **Model 702** is the DERCapacity model that contains:
- `WChaRteMax` (offset 4-5) - Max charge rate limit
- `WDisChaRteMax` (offset 6-7) - Max discharge rate limit  
- **State** register (offset 2)
- **CtlMode** register (offset 3) ⚡

**These registers could be blocking battery control if set to restrictive values!**

---

## 🚨 USER'S CRITICAL QUESTION

> "Are all Model 704 and 704 RW registers back to the default SunSpec values? How do we know. THIS IS A LIKELY ROOT CAUSE? If we do not know what they all do? And what influence they have on setting or not setting subsequent modes."

### Answer: WE DON'T KNOW!

**Evidence we HAVE:**
- ✅ Model 704 WSet control registers are at IDLE/DEFAULT state
- ✅ WSetEna = 0 (disabled)
- ✅ WSet = 0W
- ✅ WSetRvrtTms = 0

**Evidence we DON'T HAVE:**
- ❌ Model 702 CtlMode value
- ❌ Model 702 WChaRteMax value
- ❌ Model 702 WDisChaRteMax value
- ❌ Model 702 State value
- ❌ Other Model 704 registers (PF, VarSet, VaSet, etc.)
- ❌ Whether these are at SunSpec defaults or custom values

---

## 🎯 SPECULATION vs EVIDENCE

### What I Claimed WITHOUT Evidence ❌

In previous documentation, I stated:
- "CtlMode = 3 is the key finding" - **NO TEST EVIDENCE**
- "This triggers VPP mode" - **NO VERIFICATION**
- "System working with Kimi's approach" - **ASSUMED from user's output**

### What I Actually Know ✅

1. **From VPP extraction:** User saw VPP Mode activate on 2026-02-14
2. **From conversation logs:** Kimi's script uses atomic write with CtlMode
3. **From current read:** Model 704 WSet registers are at defaults
4. **From user:** Battery was CHARGING with "Control Mode: SET_W (3)"

**But I don't know:**
- Which script produced that charging state (Kimi's or battery_ctl.py?)
- What ALL register values were during successful VPP activation
- Whether Model 702 registers are blocking current attempts

---

## 🔬 WHAT WE NEED TO DO

### 1. Read Model 702 Registers

```python
# Read Model 702 to see CtlMode and rate limits
r = client.read_holding_registers(0, count=20, device_id=2)
# Check offsets 3 (CtlMode), 4-5 (WChaRteMax), 6-7 (WDisChaRteMax)
```

### 2. Compare Against SunSpec Defaults

**SunSpec 704 Defaults (from spec):**
- WSetEna = 0 (disabled)
- WSetMod = 0 (Absolute W)
- WSet = 0
- WSetRvrtTms = 0

**SunSpec 702 Defaults:**
- Unknown - need to check spec or test device

### 3. Test the Theory

**Hypothesis:** Model 702 CtlMode or rate limits are blocking battery control

**Test:**
1. Read Model 702 current values
2. Document what they are
3. Try Kimi's atomic write approach
4. Read back both Model 702 AND 704
5. Document what changed

---

## 📊 REGISTER MAP - What Influences What?

**Unknown relationships:**
- Does Model 702 CtlMode override Model 704 WSetEna?
- Do Model 702 rate limits restrict Model 704 WSet commands?
- Are there dependency chains we don't understand?

**This is the user's point - we're operating blind on register interactions!**

---

## ✅ CORRECTED APPROACH

1. **Stop claiming CtlMode=3 works** - no evidence I tested it
2. **Read Model 702 registers** - see what CtlMode/rates are set to
3. **Document ONLY observed values** - no speculation
4. **Test systematically** - vary one thing at a time
5. **Compare before/after** - both models, all registers

**User is correct: Unknown register states could absolutely be blocking VPP mode activation.**
