# Quick test with raw Modbus
from pymodbus.client import ModbusTcpClient
import time

client = ModbusTcpClient('192.168.0.110', port=502, timeout=10)
client.connect()

# Read current 704 state
r = client.read_holding_registers(40318, 10, slave=2)
print(f"Before: {r.registers}")

# Write with explicit revert configuration
# WSetEna=1, WSetMod=2, WSet=3000 (high=0, low=3000), WSetRvrt=65535, WSetRvrtTms=60
client.write_register(40318, 1)      # WSetEna
client.write_register(40319, 2)      # WSetMod
client.write_registers(40320, [0, 3000])  # WSet (int32: high, low)
client.write_registers(40322, [0xFFFF, 0xFFFF])  # WSetRvrt = -1 (no revert power)
client.write_registers(40327, [0, 60])  # WSetRvrtTms = 60 seconds

time.sleep(0.5)
r = client.read_holding_registers(40318, 10, slave=2)
print(f"After: {r.registers}")

client.close()
