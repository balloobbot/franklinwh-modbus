#!/usr/bin/env python3
"""
Complete FranklinWH Virtual Mode Controller
Includes both hardware interface and mode logic in one file
"""

import sys
import time
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    print("pip install pymodbus")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================
# HARDWARE INTERFACE (your existing logic, integrated)
# ============================================================

class FranklinWHHardware:
    """Direct Modbus interface to FranklinWH aGate."""
    
    # SunSpec Model 704 addresses (from your scan)
    WSET_ENA = 40318
    WSET_MOD = 40319
    WSET = 40320
    WSET_RVRT_TMS = 40327
    
    # FranklinWH extensions
    EXT_BASE = 15500
    EXT_PV_TOTAL = 15502
    EXT_HOME_LOAD = 15506
    
    def __init__(self, ip: str, port: int = 502, unit: int = 2):
        self.ip = ip
        self.port = port
        self.unit = unit
        self.client = None
        
    def connect(self) -> bool:
        self.client = ModbusTcpClient(self.ip, port=self.port, timeout=5)
        return self.client.connect()
    
    def disconnect(self):
        if self.client:
            self.client.close()
    
    def read_extensions(self) -> dict:
        """Read FranklinWH proprietary registers."""
        r = self.client.read_holding_registers(
            address=self.EXT_BASE, count=14, device_id=self.unit
        )
        if r.isError():
            return {}
        
        regs = r.registers
        return {
            'pv_total_w': regs[2],
            'pv_proximal_w': regs[3],
            'pv_remote1_w': regs[4],
            'pv_remote2_w': regs[5],
            'home_load_w': regs[6],
            'ongrid_mode': regs[7],
            'self_reserve_pct': regs[8],
        }
    
    def send_command(self, power_w: float) -> bool:
        """
        Send battery power command via Model 704.
        Matches your working battery_ctl.py logic.
        """
        try:
            # Split 32-bit power value
            power_int = int(power_w)
            high = (power_int >> 16) & 0xFFFF
            low = power_int & 0xFFFF
            
            # Write WSet (two registers for int32)
            self.client.write_registers(
                address=self.WSET, values=[high, low], device_id=self.unit
            )
            
            # Set mode to absolute watts (2)
            self.client.write_register(
                address=self.WSET_MOD, value=2, device_id=self.unit
            )
            
            # Enable control
            self.client.write_register(
                address=self.WSET_ENA, value=1, device_id=self.unit
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return False


# ============================================================
# VIRTUAL MODE CONTROLLER
# ============================================================

class VirtualMode(Enum):
    SELF_CONSUMPTION = "self_consumption"
    EMERGENCY_BACKUP = "emergency_backup"
    TIME_OF_USE = "time_of_use"
    MANUAL = "manual"


class VirtualModeController:
    """Software battery modes."""
    
    def __init__(self, hardware: FranklinWHHardware):
        self.hw = hardware
        self.mode = VirtualMode.SELF_CONSUMPTION
        
        # Tunable parameters
        self.self_reserve_pct = 20
        self.backup_target_soc = 95
        self.manual_power_w = 0
        
        self.tick_interval = 5
        self.last_tick = 0
        
    def set_mode(self, mode: VirtualMode, **kwargs):
        self.mode = mode
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
        logger.info(f"Mode set to: {mode.value}")
        self.execute_once()
    
    def read_status(self) -> dict:
        """Get current system status."""
        ext = self.hw.read_extensions()
        
        # Estimate SOC from your existing method or placeholder
        # In real use, read from Model 713
        
        return {
            'solar_w': ext.get('pv_total_w', 0),
            'home_w': ext.get('home_load_w', 0),
            'soc': 50,  # Replace with actual Model 713 read
        }
    
    def calculate(self) -> float:
        """Calculate desired battery power."""
        s = self.read_status()
        solar, home, soc = s['solar_w'], s['home_w'], s['soc']
        
        if self.mode == VirtualMode.SELF_CONSUMPTION:
            return self._self_consumption(solar, home, soc)
        elif self.mode == VirtualMode.EMERGENCY_BACKUP:
            return self._emergency_backup(solar, home, soc)
        elif self.mode == VirtualMode.MANUAL:
            return self.manual_power_w
        return 0
    
    def _self_consumption(self, solar, home, soc):
        excess = solar - home
        
        if soc > (100 - self.self_reserve_pct):
            if home > solar:
                return max(solar - home, -5000)
            return min(excess * 0.5, 1000) if excess > 0 else 0
        
        if excess > 0:
            return min(excess, 5000)
        
        if home > solar and soc > 10:
            return max(solar - home, -5000)
        
        return 0
    
    def _emergency_backup(self, solar, home, soc):
        if soc >= self.backup_target_soc:
            return 0
        return 5000  # Max charge
    
    def execute_once(self):
        power = self.calculate()
        success = self.hw.send_command(power)
        if success:
            logger.info(f"{self.mode.value}: {power:.0f}W")
        return power
    
    def tick(self):
        now = time.time()
        if now - self.last_tick >= self.tick_interval:
            self.execute_once()
            self.last_tick = now
    
    def run(self):
        logger.info(f"Running {self.mode.value}")
        try:
            while True:
                self.tick()
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("Stopping")
            self.hw.send_command(0)  # Idle


# ============================================================
# MAIN
# ============================================================

def main():
    print("FranklinWH Virtual Mode Controller")
    print("=" * 50)
    
    ip = input("Enter aGate IP [192.168.0.110]: ").strip() or "192.168.0.110"
    
    hw = FranklinWHHardware(ip)
    if not hw.connect():
        print("Connection failed")
        sys.exit(1)
    
    print(f"Connected to {ip}")
    
    ctrl = VirtualModeController(hw)
    
    print("\nModes:")
    print("1. Self-consumption (maximize solar use)")
    print("2. Emergency backup (charge to 95%)")
    print("3. Manual (set specific power)")
    print("4. Read status only")
    
    choice = input("\nSelect: ").strip()
    
    if choice == '1':
        reserve = int(input("SOC reserve % [20]: ") or "20")
        ctrl.set_mode(VirtualMode.SELF_CONSUMPTION, self_reserve_pct=reserve)
        ctrl.run()
        
    elif choice == '2':
        target = int(input("Target SOC % [95]: ") or "95")
        ctrl.set_mode(VirtualMode.EMERGENCY_BACKUP, backup_target_soc=target)
        ctrl.run()
        
    elif choice == '3':
        power = float(input("Power in watts (+charge, -discharge): "))
        duration = int(input("Duration minutes [60]: ") or "60")
        ctrl.set_mode(VirtualMode.MANUAL, manual_power_w=power)
        time.sleep(duration * 60)
        hw.send_command(0)
        
    elif choice == '4':
        status = ctrl.read_status()
        print(f"\nStatus: {status}")
    
    hw.disconnect()
    print("Disconnected")


if __name__ == '__main__':
    main()
