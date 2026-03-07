
import sys
import os
import logging
from pymodbus.client import ModbusTcpClient

# Setup
HOST = "192.168.0.110"
PORT = 502
UNIT = 1 

def check_raw_registers():
    print(f"\n=== Checking Raw Registers ===")
    client = ModbusTcpClient(HOST, port=PORT)
    if not client.connect():
        print("Failed to connect")
        return

    # User requested 15500:14
    print(f"\n--- Range 15500:14 ---")
    rr = client.read_holding_registers(15500, 14, slave=UNIT)
    if not rr.isError():
        for i, val in enumerate(rr.registers):
            print(f"  {15500+i}: {val} (0x{val:04X})")
    else:
        print(f"  Error: {rr}")

    # Franklin Extensions 15000:50
    print(f"\n--- Range 15000:50 (Franklin Extensions) ---")
    rr = client.read_holding_registers(15000, 50, slave=UNIT)
    if not rr.isError():
        known_regs = {
            15011: "SOC",
            15016: "Op Mode",
            15017: "Reserve",
            15020: "Rated Energy",
            15022: "Power",
            15024: "Current",
            15025: "Voltage",
            15036: "SOH",
            15040: "Reserve 2",
        }
        for i, val in enumerate(rr.registers):
            addr = 15000+i
            name = known_regs.get(addr, "")
            val_s16 = val if val < 32768 else val - 65536
            extra = f"- Name: {name}" if name else ""
            print(f"  {addr}: {val:<5} (0x{val:04X}) / S16: {val_s16:<6} {extra}")
    else:
        print(f"  Error: {rr}")

    client.close()

if __name__ == "__main__":
    check_raw_registers()
