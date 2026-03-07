# Battery Control Safety Guidelines

**Last Updated:** 2026-02-14

---

## ⚠️ CRITICAL SAFETY WARNINGS

### Model 703.ES - Grid Relay Control

**DANGER: Grid Disconnect Risk**

| Point | Values | Effect |
|-------|--------|--------|
| `ES` (Enter Service) | 1 = Disconnected<br>3 = Connected | **Controls PHYSICAL GRID RELAY CONTACTOR** |

**Scenario:**
```python
model_703.ES = 1  # Set to DISCONNECTED
model_703.write()

# Result: aGate DISCONNECTS from grid
# - Grid power to home is CUT
# - Switches to battery/backup mode
# - Computer loses power if no UPS
# - WiFi router loses power if no UPS
# - MODBUS connection is LOST
# - Cannot reverse the command!
```

**Why This Is Dangerous:**

1. **Power Interruption**
   - Computer running control software loses power
   - Network equipment (WiFi/router) loses power
   - Modbus connection drops mid-command

2. **Loss of Control**
   - Cannot send `ES = 3` (RECONNECT) if connection is lost
   - Requires manual intervention at aGate

3. **Delayed Battery Switchover**
   - Grid disconnect → battery switchover has transition delay
   - Devices without UPS will reboot/crash during transition

### 🛡️ Protection Requirements

**MANDATORY for Model 703.ES Testing:**

| Protection | Purpose | Status |
|------------|---------|--------|
| **UPS on Control Computer** | Maintain control during grid disconnect | ✅ User confirmed |
| **UPS on Network Equipment** | Maintain Modbus connection | ⚠️  Verify |
| **Ethernet (not WiFi)** | More reliable during power transitions | 🟡 Optional |
| **Physical Access to aGate** | Manual recovery if needed | ✅ Required |

---

## Safe Testing Order

### Phase 1: Read-Only (SAFE)

✅ **No writes - just data collection**

- Read all Model 702/703/704 points
- Document current values
- Understand baseline state

### Phase 2: Model 702 Limits (LOW RISK)

🟡 **Writes that limit power - non-disruptive**

```python
# Safe: Limiting charge/discharge power
model_702.WChaRteMax = 2500    # 2.5 kW charge limit
model_702.WDisChaRteMax = 3000  # 3.0 kW discharge limit
model_702.write()

# Effect: Battery operates within limits
# Risk: LOW - does not disconnect anything
```

### Phase 3: Model 704 Percentage Limits (LOW RISK)

🟡 **Percentage-based power limiting**

```python
# Safe: Enable % limiting
model_704.WMaxLimPctEna = 1  # Enable
model_704.WMaxLimPct = 5000  # 50% (scale factor -2)
model_704.write()

# Effect: Limits power to 50% of rated max
# Risk: LOW - does not disconnect anything
```

### Phase 4: Model 704 Power Setpoint (MEDIUM RISK)

🟠 **Active power setpoint - uncertain behavior**

```python
# Uncertain: Power setpoint
model_704.WSetEna = 1     # Enable setpoint
model_704.WSetMod = 1     # Watts mode
model_704.WSet = 3000     # 3 kW target
model_704.write()

# Effect: UNKNOWN - may force power to setpoint
# Risk: MEDIUM - behavior unclear
```

### Phase 5: Model 703.ES (HIGH RISK - DO NOT TEST WITHOUT UPS)

🔴 **GRID DISCONNECT - ONLY WITH FULL UPS PROTECTION**

```python
# DANGER: Grid relay control
model_703.ES = 1  # DISCONNECT GRID
model_703.write()

# Effect: ⚠️  DISCONNECTS GRID POWER TO HOME
# Risk: HIGH - power interruption, connection loss
```

**DO NOT TEST without:**
- ✅ UPS on control computer
- ✅ UPS on network equipment
- ✅ Physical access to aGate
- ✅ Understanding of recovery procedure

---

## Rollback Strategy

### Automatic Rollback

**Test script implements automatic rollback on:**
- User interrupt (Ctrl+C)
- Exception during test
- Unexpected values after write

```python
try:
    # Test writes
    await test_model_702_limits()
except Exception as e:
    # Auto-rollback
    await rollback_to_original()
finally:
    # Always disconnect cleanly
    await client.disconnect()
```

### Manual Rollback

**If script fails or connection lost:**

```bash
# Reconnect and restore
python modbus_sunspec2_readwrite.py -i 192.168.0.110 \
    --write 702.WChaRteMax=5000 \
    --write 702.WDisChaRteMax=5000 \
    --write 704.WMaxLimPctEna=0
```

---

## Recovery Procedures

### If Grid Disconnects (Model 703.ES = 1)

**Symptoms:**
- Home power switches to battery
- Control connection may drop
- Cannot send reconnect command

**Recovery:**

1. **Physical Access Method:**
   - Go to aGate
   - Use aGate screen/app to reconnect grid
   - OR power cycle aGate (grid will auto-reconnect on boot)

2. **If Connection Maintained (UPS):**
   ```python
   model_703.ES = 3  # CONNECTED
   model_703.write()
   # Wait 30-60 seconds for grid relay to close
   ```

### If Limits Are Stuck

**Symptoms:**
- Battery won't charge/discharge above limit
- Rollback script failed

**Recovery:**

```python
# Method 1: Set to rated maximums
model_702.WChaRteMax = 5000     # Rated max
model_702.WDisChaRteMax = 5000   # Rated max
model_702.write()

# Method 2: Disable percentage limiting
model_704.WMaxLimPctEna = 0  # Disable
model_704.write()

# Method 3: Power cycle aGate (resets to defaults)
```

---

## Testing Checklist

**Before ANY write operation:**

-  Read and document current values
-  Validate new values are within hardware ratings
-  Confirm user has UPS protection
-  Verify network connection is stable
-  Have rollback plan ready
-  Test on non-production system first (if available)

**During test:**

-  Monitor power flow (Model 714.W)
-  Check for unexpected behavior
-  Log all writes and responses
-  Be ready to rollback immediately

**After test:**

-  Verify values were applied correctly
-  Monitor system for 5-10 minutes
-  Rollback to original values
-  Document results

---

## Risk Matrix

| Operation | Risk Level | UPS Required | Rollback Available |
|-----------|-----------|--------------|-------------------|
| Read baseline | 🟢 NONE | No | N/A |
| Model 702 limits | 🟡 LOW | No | ✅ Yes |
| Model 704 % limits | 🟡 LOW | No | ✅ Yes |
| Model 704 setpoint | 🟠 MEDIUM | Recommended | ✅ Yes |
| Model 703.ES write | 🔴 HIGH | **MANDATORY** | ⚠️  Only if connected |

---

## Summary

**SAFE to test (Phase 1-3):**
- ✅ Model 702: WChaRteMax, WDisChaRteMax
- ✅ Model 704: WMaxLimPctEna, WMaxLimPct

**TEST WITH CAUTION (Phase 4):**
- 🟡 Model 704: WSetEna, WSetMod, WSet

**DO NOT TEST without full UPS protection (Phase 5):**
- 🔴 Model 703: ES (grid relay control)

**Protection Confirmed:**
- ✅ User has UPS on control computer
- ⚠️  Verify UPS on network equipment

**Ready to proceed with Phase 1-3 testing.**
