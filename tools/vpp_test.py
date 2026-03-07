#!/usr/bin/env python3
"""
FranklinWH Extension Write Test in VPP Mode
Activates SunSpec control first, then tests extension writes
"""

import sys
import time
from pymodbus.client import ModbusTcpClient
from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP

IP = '192.168.0.110'
PORT = 502
UNIT = 2

# Model 704 register addresses (from your scan)
WSET_ENA = 40318
WSET_MOD = 40319
WSET = 40320


def read_ext(pymodbus, addr, count=1):
    """Read FranklinWH extension."""
    try:
        result = pymodbus.read_holding_registers(address=addr, count=count, device_id=UNIT)
        return result.registers if not result.isError() else None
    except Exception as e:
        return None


def write_ext(pymodbus, addr, value):
    """Write FranklinWH extension."""
    try:
        result = pymodbus.write_register(address=addr, value=value, device_id=UNIT)
        return not result.isError()
    except Exception as e:
        return False


def activate_vpp_mode():
    """
    Activate VPP mode by enabling SunSpec Model 704 WSet control.
    This should trigger the aGate to enter 'VPP Mode'.
    """
    print("Activating VPP mode via SunSpec Model 704...")
    
    dev = SunSpecModbusClientDeviceTCP(
        slave_id=UNIT, ipaddr=IP, ipport=PORT, timeout=5
    )
    dev.connect()
    dev.scan()
    
    m704 = dev.models[704][0]
    m704.read()
    
    print(f"  Pre-VPP: WSetEna={m704.WSetEna.value}, WSet={m704.WSet.value}")
    
    # Enable power setpoint control (this triggers VPP mode)
    m704.WSetEna.value = 1
    m704.WSetMod.value = 2  # SET_ABS
    m704.WSet.value = 0     # 0W = standby/active but not charging/discharging
    
    try:
        m704.write()
        time.sleep(0.5)
        m704.read()
        
        vpp_active = (m704.WSetEna.value == 1)
        print(f"  Post-VPP: WSetEna={m704.WSetEna.value}, WSet={m704.WSet.value}")
        print(f"  VPP Mode: {'ACTIVE' if vpp_active else 'FAILED'}")
        
        dev.close()
        return vpp_active
        
    except Exception as e:
        print(f"  VPP activation failed: {e}")
        dev.close()
        return False


def deactivate_vpp_mode():
    """Disable VPP mode."""
    print("\nDeactivating VPP mode...")
    
    dev = SunSpecModbusClientDeviceTCP(
        slave_id=UNIT, ipaddr=IP, ipport=PORT, timeout=5
    )
    dev.connect()
    dev.scan()
    
    m704 = dev.models[704][0]
    m704.read()
    
    m704.WSetEna.value = 0  # Disable SunSpec control
    
    try:
        m704.write()
        print("  VPP mode deactivated")
    except Exception as e:
        print(f"  Error: {e}")
    
    dev.close()


def test_extension_in_context(pymodbus, context_name, vpp_active=False):
    """
    Test extension writes in specific context.
    """
    print(f"\n{'='*60}")
    print(f"TESTING EXTENSIONS: {context_name}")
    print(f"{'='*60}")
    
    # Read baseline
    mode = read_ext(pymodbus, 15507, 1)
    reserve = read_ext(pymodbus, 15508, 1)
    print(f"\nBaseline: OnGridMode={mode[0] if mode else 'ERR'}, SelfReserve={reserve[0] if reserve else 'ERR'}%")
    
    results = {}
    
    # Test 1: OnGridMode change
    print(f"\n--- Test: OnGridMode (15507) ---")
    current_mode = mode[0] if mode else 2
    test_val = 1 if current_mode == 2 else 2  # Toggle
    
    print(f"Writing OnGridMode = {test_val}...")
    write_ext(pymodbus, 15507, test_val)
    time.sleep(0.5)
    
    new_mode = read_ext(pymodbus, 15507, 1)
    changed = (new_mode and new_mode[0] == test_val)
    results['OnGridMode'] = changed
    
    status = "✓ CHANGED" if changed else "✗ UNCHANGED"
    print(f"Result: {status} (now {new_mode[0] if new_mode else 'ERR'})")
    
    # Restore if changed
    if changed:
        write_ext(pymodbus, 15507, current_mode)
        time.sleep(0.3)
    
    # Test 2: SelfReserve change
    print(f"\n--- Test: SelfReserve (15508) ---")
    current_reserve = reserve[0] if reserve else 10
    test_val = 25 if current_reserve != 25 else 30
    
    print(f"Writing SelfReserve = {test_val}%...")
    write_ext(pymodbus, 15508, test_val)
    time.sleep(0.5)
    
    new_reserve = read_ext(pymodbus, 15508, 1)
    changed = (new_reserve and new_reserve[0] == test_val)
    results['SelfReserve'] = changed
    
    status = "✓ CHANGED" if changed else "✗ UNCHANGED"
    print(f"Result: {status} (now {new_reserve[0] if new_reserve else 'ERR'})")
    
    # Restore if changed
    if changed:
        write_ext(pymodbus, 15508, current_reserve)
        time.sleep(0.3)
    
    # Summary
    print(f"\n--- {context_name} Summary ---")
    for reg, worked in results.items():
        print(f"  {reg}: {'WRITEABLE' if worked else 'PROTECTED'}")
    
    return any(results.values())


def main():
    print(f"FranklinWH VPP Mode Extension Write Test")
    print(f"Device: {IP}:{PORT}")
    print(f"{'='*60}")
    
    # Connect with pymodbus for extension access
    pymodbus = ModbusTcpClient(IP, port=PORT, timeout=5)
    if not pymodbus.connect():
        print("CONNECTION FAILED")
        sys.exit(1)
    
    # Phase 1: Test WITHOUT VPP mode (baseline)
    normal_worked = test_extension_in_context(pymodbus, "NORMAL MODE (no VPP)", vpp_active=False)
    
    # Phase 2: Activate VPP mode
    vpp_ok = activate_vpp_mode()
    
    if vpp_ok:
        # Phase 3: Test WITH VPP mode
        vpp_worked = test_extension_in_context(pymodbus, "VPP MODE ACTIVE", vpp_active=True)
        
        # Deactivate VPP
        deactivate_vpp_mode()
        
        # Final comparison
        print(f"\n{'='*60}")
        print("COMPARISON")
        print(f"{'='*60}")
        print(f"Normal mode:  {'WRITEABLE' if normal_worked else 'PROTECTED'}")
        print(f"VPP mode:     {'WRITEABLE' if vpp_worked else 'PROTECTED'}")
        
        if vpp_worked and not normal_worked:
            print(f"\n✓✓✓ BREAKTHROUGH: Extensions only writeable in VPP mode!")
        elif not vpp_worked:
            print(f"\n✗ Extensions remain protected even in VPP mode")
            print("  Possible reasons:")
            print("  - Requires specific WSet value (non-zero?)")
            print("  - Requires additional VPP enable register")
            print("  - Firmware permanently locks extensions")
    else:
        print("\nCould not activate VPP mode - aborting comparison")
    
    pymodbus.close()
    print(f"\n{'='*60}")
    print("Disconnected")


if __name__ == '__main__':
    main()
