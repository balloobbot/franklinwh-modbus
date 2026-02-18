#!/bin/bash
# Test Sequence: MAX_CHARGE Unlock + STANDBY Grid Force
# Date: 2026-02-15 02:30
# Hypothesis: MAX_CHARGE unlocks control, STANDBY forces grid usage

IP="192.168.0.110"
UNIT=2

echo "=== Battery Control Unlock Test Sequence ==="
echo "Starting: $(date)"
echo ""

# STEP 1: Baseline - Read current state
echo "STEP 1: Reading baseline register state..."
python3 << 'EOF'
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('192.168.0.110', port=502, timeout=10)
client.connect()

print("\n--- Model 704 WSet Control Registers (Baseline) ---")
r = client.read_holding_registers(321, count=15, device_id=2)
if not r.isError():
    print(f"WSetEna (321): {r.registers[0]} - {'ENABLED' if r.registers[0] != 0 else 'DISABLED'}")
    print(f"WSetMod (322): {r.registers[1]}")
    wset = (r.registers[3] << 16) | r.registers[4]
    if wset >= 0x80000000: wset -= 0x100000000
    print(f"WSet (323-324): {wset}W")
    
print("\n--- Check FranklinWH App NOW ---")
print("Current operating mode: ?")
print("VPP Mode status: ?")

client.close()
EOF

read -p "Press Enter after checking app state..."

# STEP 2: Send MAX_CHARGE command (the unlock?)
echo ""
echo "STEP 2: Sending MAX_CHARGE command..."
/home/david/dev/modbus/venv/bin/python3 /home/david/dev/modbus/fhp_battery_ctrl.py -i $IP --franklinwh --unit-id $UNIT --max-charge --wset-rvrt 5m -v

echo ""
echo "Waiting 10 seconds for system to respond..."
sleep 10

# STEP 3: Check if VPP mode activated
echo ""
echo "STEP 3: Check FranklinWH app - did VPP mode activate?"
read -p "VPP Mode active? (y/n): " vpp_after_maxcharge

# STEP 4: Send STANDBY command (force grid?)
echo ""
echo "STEP 4: Sending STANDBY (0W) command..."
/home/david/dev/modbus/venv/bin/python3 /home/david/dev/modbus/fhp_battery_ctrl.py -i $IP --franklinwh --unit-id $UNIT --idle --wset-rvrt 5m -v

echo ""
echo "Waiting 10 seconds..."
sleep 10

echo ""
echo "STEP 5: Check if home loads switched to grid"
read -p "Are home loads being supplied from grid? (y/n): " grid_active

# STEP 6: Now try actual charge command
echo ""
echo "STEP 6: Sending CHARGE command (after unlock sequence)..."
/home/david/dev/modbus/venv/bin/python3 /home/david/dev/modbus/fhp_battery_ctrl.py -i $IP --franklinwh --unit-id $UNIT -p -2000W --wset-rvrt 5m -v

echo ""
echo "Waiting 15 seconds for battery to respond..."
sleep 15

# STEP 7: Final status check
echo ""
echo "STEP 7: Final status check..."
/home/david/dev/modbus/venv/bin/python3 /home/david/dev/modbus/fhp_battery_ctrl.py -i $IP --franklinwh --unit-id $UNIT --status

echo ""
echo "STEP 8: Check battery physical response"
echo "Check FranklinWH app:"
echo "  - Battery DCW value?"
echo "  - Battery state (charging/discharging/standby)?"
echo "  - VPP Mode still active?"

echo ""
echo "=== Test Complete ==="
echo "Please document results in test log"
