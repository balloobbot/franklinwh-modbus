#!/bin/bash
# Working Test - Using Direct PyModbus (No Broken Scripts)

IP="192.168.0.110"
UNIT=2

echo "=== Battery Control Test (Direct PyModbus) ==="
echo ""

# STEP 1: Baseline
echo "STEP 1: Baseline check..."
python3 << 'EOF'
from pymodbus.client import ModbusTcpClient
client = ModbusTcpClient('192.168.0.110', port=502, timeout=10)
client.connect()
r = client.read_holding_registers(321, count=5, device_id=2)
print(f"WSetEna: {r.registers[0]} (should be 0)")
print(f"WSet: {(r.registers[3] << 16) | r.registers[4]}W (should be 0)")
client.close()
EOF

echo ""
read -p "Check FranklinWH app - VPP Mode OFF? Press Enter..."

# STEP 2: Send CHARGE command directly
echo ""
echo "STEP 2: Sending -2000W CHARGE command..."
python3 << 'EOF'
from pymodbus.client import ModbusTcpClient
client = ModbusTcpClient('192.168.0.110', port=502, timeout=10)
client.connect()

power = -2000
# Convert to unsigned 32-bit
if power < 0:
    value_u32 = (1 << 32) + power
else:
    value_u32 = power

high = (value_u32 >> 16) & 0xFFFF
low = value_u32 & 0xFFFF

print(f"Writing WSet = {power}W (high={high}, low={low})")

# Atomic-ish write sequence
client.write_register(321, 0, device_id=2)  # WSetEna = 0 (disable first)
client.write_register(322, 0, device_id=2)  # WSetMod = 0 (absolute W)
client.write_registers(323, [high, low], device_id=2)  # WSet = -2000W
client.write_register(321, 1, device_id=2)  # WSetEna = 1 (enable)

print("✅ Command sent!")
client.close()
EOF

echo ""
echo "Waiting 15 seconds for battery response..."
sleep 15

# STEP 3: Check result
echo ""
echo "STEP 3: Checking battery state..."
python3 << 'EOF'
from pymodbus.client import ModbusTcpClient
client = ModbusTcpClient('192.168.0.110', port=502, timeout=10)
client.connect()

# Read state and WSet
r = client.read_holding_registers(301, count=25, device_id=2)

state = r.registers[0]
wsetena = r.registers[20]
wset_high = r.registers[22]
wset_low = r.registers[23]
wset = (wset_high << 16) | wset_low
if wset >= 0x80000000:
    wset -= 0x100000000

state_map = {1: "OFF", 2: "STANDBY", 3: "CHARGING", 4: "DISCHARGING", 5: "FAULT"}

print(f"Battery State: {state_map.get(state, 'UNKNOWN')}")
print(f"WSetEna: {wsetena}")
print(f"WSet: {wset}W")

client.close()
EOF

echo ""
echo "=== CHECK FRANKLINWH APP NOW ==="
echo "1. Battery DCW = -2000W? (charging)"
echo "2. VPP Mode active?"
echo "3. Battery state = CHARGING?"
echo ""
read -p "Document results and press Enter when done..."

echo ""
echo "Test complete!"
