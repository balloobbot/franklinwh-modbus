
import inspect
try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    from pymodbus.client.tcp import ModbusTcpClient

print(f"Inspecting ModbusTcpClient.read_holding_registers:")
sig = inspect.signature(ModbusTcpClient.read_holding_registers)
print(sig)

try:
    from pymodbus.client.mixin import ModbusClientMixin
    print(f"\nInspecting ModbusClientMixin.read_holding_registers:")
    sig = inspect.signature(ModbusClientMixin.read_holding_registers)
    print(sig)
except ImportError:
    pass

import pymodbus
print(f"\nPymodbus version: {pymodbus.__version__}")
