# Known Issues and Gotchas

## 🔴 CRITICAL: Log Spam Issues

### 1. ConfigManager AttributeError (ACTIVE - NEEDS FIX)
**Error:** `'ConfigManager' object has no attribute 'get_config'. Did you mean: '_config'?`

**Affected Endpoints:**
- `/api/power_limits` 
- `/api/battery/safety-status`

**Location:** `src/web_server.py` line 924

**Impact:** Logs spam (47+ errors per session), endpoints return 500

**Fix Required:** Replace `config_manager.get_config()` with correct API

---

## ⚠️ Pymodbus API Confusion

### Unit ID vs Slave ID Parameter Names

**Problem:** pymodbus has changed parameter names across versions, causing confusion

**Correct API for pymodbus 3.x:**
- ✅ **USE:** `unit=` parameter
- ❌ **DON'T USE:** `slave=`, `device_id=` (in direct client calls)

**Examples:**
```python
# ✅ CORRECT (pymodbus 3.x)
client.write_register(address, value, unit=2)
client.read_holding_registers(address, count, unit=2)

# ❌ WRONG (will error)
client.write_register(address, value, slave=2)  # TypeError
client.write_register(address, value, device_id=2)  # TypeError
```

**In FranklinWHModbusClient class:**
- Uses `self.unit_id` instance variable
- Must pass to underlying pymodbus client as `unit=self.unit_id`

---

## 🎯 FranklinWH Addressing Rules

### Native Base Address = 1
- FranklinWH uses base address `1` in SunSpec certification
- This **directly maps** to pymodbus 0-indexed PDU addresses
- **NO 40001 SUBTRACTION NEEDED** for Model 704 control registers

**Example:**
```
SunSpec Register 40318 (WSetEna)
→ FranklinWH native: 318 (base 1)
→ pymodbus address: 317 (0-indexed PDU)
→ Calculation: 40318 - 40001 = 317 ✅
```

See: [FRANKLINWH_NATIVE_ADDRESSING.md](file:///home/david/.gemini/antigravity/brain/a17c20ae-bda9-47cd-b5ca-89f4d9f6b5bc/FRANKLINWH_NATIVE_ADDRESSING.md)

---

## 📋 Testing Requirements

### Before ANY code changes:
1. ✅ Check for existing errors: `grep -c "ERROR" data/logs/franklinwh.log`
2. ✅ Fix ALL log spam before testing new features
3. ✅ Verify syntax: `python3 -c "import src.module_name"`
4. ✅ Test in isolation before integration

### Battery Control Testing Checklist:
- [ ] Direct pymodbus test passes (isolates API issues)
- [ ] Web server endpoint returns 2xx (not 500)
- [ ] Logs show 🔋 emoji and step messages
- [ ] Registers verify: `modbus_sunspec2_reader.py -m 704`
- [ ] FranklinWH app reflects mode change

---

## 🔧 Recurring Issues

### Issue: "Modbus connection failed" 
**Cause:** iptables blocking writes, concurrent client limit, aGate busy
**Check:** `nc -zv 192.168.0.110 502`
**Fix:** Reuse existing connection, check firewall rules

### Issue: Writes appear to succeed but don't persist
**Cause:** Disable-first sequence not followed, wrong addresses
**Fix:** Use verified 4-step sequence from [WORKING_BATTERY_CONTROL_SEQUENCE.md](file:///home/david/.gemini/antigravity/brain/a17c20ae-bda9-47cd-b5ca-89f4d9f6b5bc/WORKING_BATTERY_CONTROL_SEQUENCE.md)

---

**Last Updated:** 2026-02-14  
**Priority:** FIX ConfigManager errors IMMEDIATELY before further testing
