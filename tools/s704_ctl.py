#!/usr/bin/env python3
"""
SunSpec-2 Model 704 (DERCtlAC) battery charge / discharge / idle utility.
Requires: pymodbus >= 3.x

Source: Kimi K2.5
"""

import argparse
import struct
import sys
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

# SunSpec 704 register offsets relative to model base
REG_W_SF = 70  # int16
REG_W_SET = 52  # int32 => two 16-bit registers
REG_W_SET_ENA = 50  # enum16
REG_W_SET_MOD = 51  # enum16   0=absolute W, 1=% WMax, 2=VA

# DERCtlAC enumeration values
ENA_DISABLED = 0
ENA_ENABLED = 1
MODE_ABSOLUTE_W = 0
MODE_PERCENT_WMAX = 1
MODE_VA = 2


class S704Client:
    def __init__(self, host, port, unit, base_addr, timeout):
        self.unit = unit
        self.base = base_addr - 40001  # convert to 0-based PDU
        self.client = ModbusTcpClient(host, port=port, timeout=timeout)

    def open(self):
        if not self.client.connect():
            raise RuntimeError("Modbus connection failed")

    def close(self):
        self.client.close()

    def read_reg(self, offset):
        """Read a single 16-bit register."""
        rr = self.client.read_holding_registers(self.base + offset, count=1, device_id=self.unit)
        if rr.isError():
            raise ModbusException(rr)
        return rr.registers[0]

    def read_s32(self, offset):
        """Read two 16-bit registers as signed 32-bit."""
        rr = self.client.read_holding_registers(self.base + offset, count=2, device_id=self.unit)
        if rr.isError():
            raise ModbusException(rr)
        lo, hi = rr.registers
        return struct.unpack(">i", struct.pack(">HH", hi, lo))[0]

    def write_reg(self, offset, value):
        """Write a single 16-bit register."""
        rq = self.client.write_register(self.base + offset, int(value), device_id=self.unit)
        if rq.isError():
            raise ModbusException(rq)

    def write_s32(self, offset, value):
        """Write signed 32-bit to two consecutive 16-bit registers."""
        hi = (int(value) >> 16) & 0xFFFF
        lo = int(value) & 0xFFFF
        rq = self.client.write_registers(self.base + offset, [hi, lo], device_id=self.unit)
        if rq.isError():
            raise ModbusException(rq)

    def scale_factor(self):
        """Return W_SF (scale factor for W/VA registers)."""
        raw = self.read_reg(REG_W_SF)
        # SunSpec SF is int16; convert to signed
        return struct.unpack(">h", struct.pack(">H", raw))[0]

    def set_power(self, direction, value, unit):
        """
        direction: 'charge', 'discharge', 'idle'
        value: numeric power (W or VA)
        unit: 'W' or 'VA'
        """
        sf = self.scale_factor()
        scale = 10 ** sf

        # Convert input to raw integer
        raw = int(round(value / scale))

        # Determine mode and sign
        if direction == "idle":
            mode = MODE_ABSOLUTE_W
            raw = 0
            ena = ENA_DISABLED
        else:
            ena = ENA_ENABLED
            mode = MODE_VA if unit == "VA" else MODE_ABSOLUTE_W
            if direction == "charge":
                raw = -abs(raw)  # negative = importing
            else:  # discharge
                raw = abs(raw)

        # Write sequence: disable, set mode, setpoint, enable
        self.write_reg(REG_W_SET_ENA, ENA_DISABLED)
        self.write_reg(REG_W_SET_MOD, mode)
        self.write_s32(REG_W_SET, raw)
        self.write_reg(REG_W_SET_ENA, ena)

    def get_power(self):
        """Return (direction, value, unit) currently active."""
        ena = self.read_reg(REG_W_SET_ENA)
        if ena == ENA_DISABLED:
            return "idle", 0, "W"
        mode = self.read_reg(REG_W_SET_MOD)
        unit = "VA" if mode == MODE_VA else "W"
        sf = self.scale_factor()
        scale = 10 ** sf
        raw = self.read_s32(REG_W_SET)
        value = abs(raw) * scale
        direction = "charge" if raw < 0 else "discharge"
        return direction, value, unit


def parse_args():
    p = argparse.ArgumentParser(description="SunSpec-2 Model 704 battery control")
    p.add_argument("host", help="IP address")
    p.add_argument("action", choices=["charge", "discharge", "idle"])
    p.add_argument("power", nargs="?", type=float, help="Power in W or VA (ignored for idle)")
    p.add_argument("-p", "--port", type=int, default=502, help="Modbus-TCP port (default 502)")
    p.add_argument("-u", "--unit", type=int, default=1, help="Unit ID (default 1)")
    p.add_argument("-b", "--base", type=int, default=40300, help="SunSpec model base address (default 40300)")
    p.add_argument("-t", "--timeout", type=int, default=5, help="TCP timeout (default 5 s)")
    p.add_argument("--unit-type", choices=["W", "VA"], default="W", help="Unit for power (default W)")
    return p.parse_args()


def main():
    args = parse_args()
    if args.action != "idle" and args.power is None:
        print("Power value required for charge/discharge", file=sys.stderr)
        sys.exit(2)

    c = S704Client(args.host, args.port, args.unit, args.base, args.timeout)
    try:
        c.open()
        if args.action == "idle":
            c.set_power("idle", 0, "W")
        else:
            c.set_power(args.action, args.power, args.unit_type)
        # show result
        direction, value, unit = c.get_power()
        print(f"Device now: {direction}  {value:g} {unit}")
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        sys.exit(1)
    finally:
        c.close()


if __name__ == "__main__":
    main()
