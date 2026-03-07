#!/usr/bin/env python3
"""
FranklinWH Battery Control - Simple CLI Tool
Uses correct register addresses for FranklinWH aGate (not generic SunSpec offsets)

Based on WORKING_BATTERY_CONTROL_SEQUENCE.md
"""

import argparse
import sys
from pymodbus.client import ModbusTcpClient

# CORRECT FranklinWH Model 704 addresses (0-indexed PDU)
# From WORKING_BATTERY_CONTROL_SEQUENCE.md and FRANKLINWH_NATIVE_ADDRESSING.md
# Model 704 register map (Modbus 40001-based → PDU 0-indexed):
#   40318 → 317: WSetEna (enable/disable)
#   40319 → 318: WSetMod (mode: 0=W, 1=%, 2=VA)
#   40320 → 319: WSet (power setpoint, int32)
#   40327 → 326: WSetRvrtTms (reversion time, uint32)
WSET_ENA = 317       # Enable/disable
WSET_MOD = 318       # Mode
WSET = 319           # Power setpoint (int32, 2 registers)
WSET_RVRT_TMS = 326  # Reversion time (uint32, 2 registers)

# Mode values
MODE_ABSOLUTE_W = 0
MODE_PERCENT_WMAX = 1
MODE_VA = 2

# Operating modes (from register 15507)
# Source: franklinwh_modbus_extensions.md
OPERATING_MODES = {
    1: "Emergency Backup",
    2: "Self-Consumption",
    3: "Time-of-Use (TOU)",
    4: "Remote Control/VPP"
}


def check_operating_mode(client):
    """Check and display FranklinWH operating mode"""
    try:
        r = client.read_holding_registers(15507, count=1, device_id=1)
        if r.isError():
            return None, "Unknown (read failed)"
        
        mode_id = r.registers[0]
        mode_name = OPERATING_MODES.get(mode_id, f"Unknown ({mode_id})")
        
        print(f"\n⚙️  Operating Mode: {mode_name}")
        print(f"   ℹ️  System auto-switches to VPP mode when battery control commands are sent")
        
        return mode_id, mode_name
    except Exception as e:
        print(f"\n⚠️  Could not read operating mode: {e}")
        return None, "Unknown"



def read_current_state(client, device_id=2):
    """Read and display current battery control state"""
    print("📊 Reading current state...")
    
    # Read WSetEna
    r = client.read_holding_registers(WSET_ENA, count=1, device_id=device_id)
    if r.isError():
        return None, None, None
    ena = r.registers[0]
    
    # Read WSetMod  
    r = client.read_holding_registers(WSET_MOD, count=1, device_id=device_id)
    if r.isError():
        return None, None, None
    mod = r.registers[0]
    
    # Read WSet (int32)
    r = client.read_holding_registers(WSET, count=2, device_id=device_id)
    if r.isError():
        return None, None, None
    
    # Convert to signed int32
    wset_val = (r.registers[0] << 16) | r.registers[1]
    if wset_val >= 0x80000000:
        wset_val -= 0x100000000
    
    return ena, mod, wset_val


def display_state(ena, mod, wset_val):
    """Display battery control state in human-readable format"""
    # FranklinWH returns 0=disabled, 1 or 65535 (0xFFFF)=enabled
    status = "ENABLED" if ena != 0 else "DISABLED"
    mode_names = {0: "Absolute W", 1: "% WMax", 2: "VA", None: "Unknown"}
    mode = mode_names.get(mod, f"Unknown ({mod})")
    
    if wset_val == 0:
        direction = "IDLE"
    elif wset_val < 0:
        direction = f"CHARGING at {abs(wset_val)}W"
    else:
        direction = f"DISCHARGING at {wset_val}W"
    
    print(f"   Enable: {status}")
    print(f"   Mode:   {mode}")
    print(f"   Power:  {direction}")
    return direction


def set_battery_power(client, power_watts, device_id=2, verbose=False):
    """
    Set battery charge/discharge power
    
    Args:
        power_watts: Positive = discharge, Negative = charge, 0 = idle
        verbose: If True, read and display registers after each write step
    """
    print(f"\n🔋 Setting battery power: {power_watts}W")
    
    if power_watts == 0:
        print("   Mode: IDLE (disabled)")
    elif power_watts < 0:
        print(f"   Mode: CHARGE at {abs(power_watts)}W")
    else:
        print(f"   Mode: DISCHARGE at {power_watts}W")
    
    # STEP 1: Disable
    print("   1. Disabling WSetEna...")
    client.write_register(WSET_ENA, 0, device_id=device_id)
    if verbose:
        r = client.read_holding_registers(WSET_ENA, count=1, device_id=device_id)
        print(f"      → WSetEna = {r.registers[0]} (0x{r.registers[0]:04X})")
    
    # STEP 2: Set Mode (Absolute W)
    print("   2. Setting WSetMod=0 (Absolute W)...")
    client.write_register(WSET_MOD, MODE_ABSOLUTE_W, device_id=device_id)
    if verbose:
        r = client.read_holding_registers(WSET_MOD, count=1, device_id=device_id)
        print(f"      → WSetMod = {r.registers[0]}")
    
    # STEP 2b: Disable automatic reversion (CRITICAL!)
    print("   2b. Setting WSetRvrtTms=0 (disable auto-revert)...")
    client.write_registers(WSET_RVRT_TMS, [0, 0], device_id=device_id)  # uint32 = 0
    if verbose:
        r = client.read_holding_registers(WSET_RVRT_TMS, count=2, device_id=device_id)
        rvrt_time = (r.registers[0] << 16) | r.registers[1]
        print(f"      → WSetRvrtTms = {rvrt_time} seconds")
    
    # STEP 3: Write Power Value
    print(f"   3. Writing WSet={power_watts}W...")
    # Convert signed int32 to two uint16 registers
    if power_watts < 0:
        value_u32 = (1 << 32) + power_watts
    else:
        value_u32 = power_watts
    high = (value_u32 >> 16) & 0xFFFF
    low = value_u32 & 0xFFFF
    client.write_registers(WSET, [high, low], device_id=device_id)
    if verbose:
        r = client.read_holding_registers(WSET, count=2, device_id=device_id)
        wset_val = (r.registers[0] << 16) | r.registers[1]
        if wset_val >= 0x80000000:
            wset_val -= 0x100000000
        print(f"      → WSet = {wset_val}W (raw: [{r.registers[0]}, {r.registers[1]}])")
    
    # STEP 4: Enable (if not idle)
    if power_watts != 0:
        print("   4. Enabling WSetEna...")
        client.write_register(WSET_ENA, 1, device_id=device_id)
        if verbose:
            r = client.read_holding_registers(WSET_ENA, count=1, device_id=device_id)
            print(f"      → WSetEna = {r.registers[0]} (0x{r.registers[0]:04X})")
    else:
        print("   4. Keeping disabled (idle mode - WSetEna stays 0)")
        # Note: Already disabled in step 1, but read back to confirm
        if verbose:
            r = client.read_holding_registers(WSET_ENA, count=1, device_id=device_id)
            print(f"      → WSetEna = {r.registers[0]} (should be 0, actual: {'✅' if r.registers[0] == 0 else '⚠️'})")
    
    print("   ✅ Write sequence complete")



def main():
    parser = argparse.ArgumentParser(
        description="FranklinWH Battery Control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Charge at 2000W (imports from grid to battery)
  %(prog)s 192.168.0.110 -2000
  
  # Discharge at 3000W (exports from battery to loads)
  %(prog)s 192.168.0.110 3000
  
  # Set idle (disable control)
  %(prog)s 192.168.0.110 0
  
  # Just view current state without changing
  %(prog)s 192.168.0.110 --status
  
Power values:
  Positive = Discharge (battery → loads/grid)
  Negative = Charge (grid → battery)
  Zero = Idle (disable control)
        """
    )
    
    parser.add_argument("host", help="FranklinWH aGate IP address")
    parser.add_argument("power", nargs="?", type=int, help="Power in watts (+ discharge, - charge, 0 idle)")
    parser.add_argument("--status", action="store_true", help="Only show current status, don't change")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show register values after each write step")
    parser.add_argument("-u", "--unit", type=int, default=2, help="Unit ID (default: 2 for aGate)")
    parser.add_argument("-p", "--port", type=int, default=502, help="Modbus port (default: 502)")
    parser.add_argument("-t", "--timeout", type=int, default=10, help="Timeout in seconds (default: 10)")
    
    args = parser.parse_args()
    
    # Validate input
    if not args.status and args.power is None:
        parser.error("power value required (or use --status to just view current state)")
    
    # Connect
    print(f"🔌 Connecting to {args.host}:{args.port}...")
    client = ModbusTcpClient(args.host, port=args.port, timeout=args.timeout)
    
    if not client.connect():
        print("❌ Connection failed!", file=sys.stderr)
        return 1
    
    print("✅ Connected!")
    
    try:
        # Check operating mode first
        mode_id, mode_name = check_operating_mode(client)
        
        # Read current state
        ena, mod, wset_val = read_current_state(client, args.unit)
        if ena is None:
            print("❌ Failed to read current state", file=sys.stderr)
            return 1
        
        print("\n📊 CURRENT STATE:")
        current = display_state(ena, mod, wset_val)
        
        # If status-only, exit here
        if args.status:
            return 0
        
        # Set new power value
        set_battery_power(client, args.power, args.unit, args.verbose)
        
        # Verify by reading back
        print("\n🔍 VERIFYING...")
        import time
        time.sleep(0.5)  # Brief delay for write to settle
        
        ena, mod, wset_val = read_current_state(client, args.unit)
        if ena is None:
            print("❌ Failed to verify", file=sys.stderr)
            return 1
        
        print("\n✅ NEW STATE:")
        new = display_state(ena, mod, wset_val)
        
        # Validate
        # Note: FranklinWH keeps WSetEna enabled even for idle mode
        # The actual power value (WSet) is what matters
        if args.power == 0:
            # For idle, power should be 0 (enable state doesn't matter)
            success = (wset_val == 0)
        else:
            # For charge/discharge, power should match target
            success = (wset_val == args.power)
        
        if success:
            print("\n🎉 SUCCESS! Battery control updated.")
        else:
            print(f"\n⚠️  Warning: Readback value ({wset_val}W) doesn't match target ({args.power}W)")
            return 1
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1
    finally:
        client.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
