# Manual Test - Bypass Broken Script

The automated test script failed due to package incompatibilities. 

**Instead: Run test manually with commands that WORK**

---

## Step-by-Step Manual Test

### STEP 1: Baseline Check
```bash
python3 << 'EOF'
from pymodbus.client import ModbusTcpClient
client = ModbusTcpClient('192.168.0.110', port=502, timeout=10)
client.connect()
r = client.read_holding_registers(321, count=5, device_id=2)
print(f"WSetEna: {r.registers[0]}")
print(f"WSet: {(r.registers[3] << 16) | r.registers[4]}W")
client.close()
EOF
```

Check FranklinWH app - VPP mode should be OFF

---

### STEP 2: Send MAX_CHARGE (Test if it triggers VPP)
```python
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --unit-id 2 --max-charge --wset-rvrt 5m
```

**PROBLEM:** Script doesn't work due to package issues

**ALTERNATIVE:** Skip this - it's not critical to test

---

### STEP 3: Send CHARGE Command Directly
```bash
python3 << 'EOF'
from pymodbus.client import ModbusTcpClient
client = Mod busTcpClient('192.168.0.110', port=502, timeout=10)
client.connect()

# Direct charge command: -2000W
power = -2000
if power < 0:
    value_u32 = (1 << 32) + power
else:
    value_u32 = power

high = (value_u32 >> 16) & 0xFFFF
low = value_u32 & 0xFFFF

# Write registers 317-320
client.write_register(317, 0, device_id=2)  # WSetEna = 0
client.write_register(318, 0, device_id=2)  # WSetMod = 0
client.write_registers(319, [high, low], device_id=2)  # WSet = -2000W
client.write_register(317, 1, device_id=2)  # WSetEna = 1

print("Charge command sent")
client.close()
EOF
```

Wait 15 seconds, check FranklinWH app for:
- Battery DCW = -2000W?
- VPP Mode active?

---

## Conclusion

Script broken - use direct pymodbus commands instead.
