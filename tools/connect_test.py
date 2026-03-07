#!/usr/bin/env python3
"""
Minimal FranklinWH Test - Using BOTH raw Modbus AND SunSpec
"""

import time
import sys
from pymodbus.client import ModbusTcpClient
from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP

IP = '192.168.0.110'
PORT = 502
UNIT = 2


def test_extensions_raw():
    """Test FranklinWH extensions via raw Modbus."""
    print("=" * 60)
    print("TEST 1: Raw Modbus Extensions (15500-15513)")
    print("=" * 60)
    
    client = ModbusTcpClient(IP, port=PORT, timeout=5)
    try:
        if not client.connect():
            print("✗ Connection failed")
            return False
        
        result = client.read_holding_registers(address=15500, count=14, device_id=UNIT)
        if result.isError():
            print(f"✗ Read failed: {result}")
            return False
        
        regs = result.registers
        print(f"✓ Read successful")
        print(f"  PV Total Power: {regs[2]} W")
        print(f"  Home Load: {regs[6]} W")
        print(f"  OnGridMode: {regs[7]}")
        print(f"  SelfReserve: {regs[8]}%")
        return True
        
    finally:
        client.close()


def test_sunspec_scan():
    """Test SunSpec model discovery."""
    print("\n" + "=" * 60)
    print("TEST 2: SunSpec Model Scan")
    print("=" * 60)
    
    try:
        dev = SunSpecModbusClientDeviceTCP(
            slave_id=UNIT, ipaddr=IP, ipport=PORT, timeout=5
        )
        dev.connect()
        
        print("Scanning...")
        dev.scan()
        
        models = [k for k in dev.models.keys() if isinstance(k, int)]
        print(f"✓ Found models: {sorted(models)}")
        
        # Check for 704
        if 704 in dev.models:
            print("✓ Model 704 (DERCtlAC) found")
            m704 = dev.models[704][0]  # Get first instance
            m704.read()
            print(f"  WSetEna: {m704.WSetEna.value}")
            print(f"  WSetMod: {m704.WSetMod.value}")
            print(f"  WSet: {m704.WSet.value} W")
            dev.close()
            return True
        else:
            print("✗ Model 704 not found")
            dev.close()
            return False
            
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False


def test_sunspec_write():
    """Test writing via SunSpec."""
    print("\n" + "=" * 60)
    print("TEST 3: SunSpec Model 704 Write")
    print("=" * 60)
    
    try:
        dev = SunSpecModbusClientDeviceTCP(
            slave_id=UNIT, ipaddr=IP, ipport=PORT, timeout=5
        )
        dev.connect()
        dev.scan()
        
        if 704 not in dev.models:
            print("✗ Model 704 not available")
            return False
        
        m704 = dev.models[704][0]
        m704.read()
        
        print(f"Before: WSetEna={m704.WSetEna.value}, WSet={m704.WSet.value}")
        
        # Write enable
        print("\nWriting WSetEna=1, WSet=500...")
        m704.WSetEna.value = 1
        m704.WSetMod.value = 2  # SET_ABS
        m704.WSet.value = 500
        
        m704.write()
        time.sleep(0.3)
        
        m704.read()
        print(f"After: WSetEna={m704.WSetEna.value}, WSet={m704.WSet.value}")
        
        success = (m704.WSetEna.value == 1 and m704.WSet.value == 500)
        print(f"Result: {'✓ SUCCESS' if success else '✗ FAILED'}")
        
        # Cleanup
        if success:
            print("\nCleaning up (idle)...")
            m704.WSetEna.value = 0
            m704.WSet.value = 0
            m704.write()
            time.sleep(0.2)
        
        dev.close()
        return success
        
    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_combined():
    """Test using both interfaces together."""
    print("\n" + "=" * 60)
    print("TEST 4: Combined Raw + SunSpec")
    print("=" * 60)
    
    # Keep SunSpec connection open for control
    # Use raw Modbus for monitoring
    
    try:
        # SunSpec for control
        sunspec = SunSpecModbusClientDeviceTCP(
            slave_id=UNIT, ipaddr=IP, ipport=PORT, timeout=5
        )
        sunspec.connect()
        sunspec.scan()
        
        if 704 not in sunspec.models:
            print("✗ Model 704 not found")
            return False
        
        m704 = sunspec.models[704][0]
        
        # Raw Modbus for monitoring (separate connection)
        raw = ModbusTcpClient(IP, port=PORT, timeout=5)
        raw.connect()
        
        # Read baseline
        r = raw.read_holding_registers(address=15506, count=1, device_id=UNIT)
        home_before = r.registers[0] if not r.isError() else None
        print(f"Home load before: {home_before} W")
        
        # Command battery via SunSpec
        print("\nCommanding 1000W charge via SunSpec...")
        m704.read()
        m704.WSetEna.value = 1
        m704.WSetMod.value = 2
        m704.WSet.value = 1000
        m704.write()
        
        # Monitor via raw
        time.sleep(2)
        r = raw.read_holding_registers(address=15506, count=1, device_id=UNIT)
        home_after = r.registers[0] if not r.isError() else None
        print(f"Home load after: {home_after} W")
        
        # Check if home load changed (indicating battery active)
        if home_after and home_before:
            change = home_after - home_before
            print(f"Change: {change:+.0f} W")
            if abs(change) > 100:
                print("✓ Battery likely active (home load shifted)")
        
        # Cleanup
        m704.read()
        m704.WSetEna.value = 0
        m704.WSet.value = 0
        m704.write()
        
        raw.close()
        sunspec.close()
        return True
        
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False


def main():
    print("FranklinWH Corrected Test Suite")
    print(f"Target: {IP}:{PORT} (unit {UNIT})")
    print()
    
    results = []
    results.append(("Raw Extensions", test_extensions_raw()))
    results.append(("SunSpec Scan", test_sunspec_scan()))
    results.append(("SunSpec Write", test_sunspec_write()))
    results.append(("Combined", test_combined()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
    
    if all(r[1] for r in results):
        print("\n✓ All tests passed!")
        print("\nArchitecture for full controller:")
        print("  - SunSpec (sunspec2): For Model 704 control (WSet)")
        print("  - Raw Modbus (pymodbus): For extensions 15500+ monitoring")
    else:
        print("\n✗ Some tests failed")


if __name__ == '__main__':
    main()