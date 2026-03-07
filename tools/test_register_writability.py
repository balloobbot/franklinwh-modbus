#!/usr/bin/env python3
"""
Safe Register Writability Tester for FranklinWH Undocumented Extensions

PURPOSE:
  Discovers which registers in the 15000-15044 range are writable (RW)
  by reading the current value and attempting to write it back unchanged.

SAFETY:
  - Only writes the EXACT value that was read (no modifications)
  - Verifies value after write to detect unexpected changes
  - Logs all operations for audit trail
  - Allows testing individual registers or ranges
  - Provides dry-run mode for verification

USAGE:
  # Test single register
  python test_register_writability.py -i 192.168.0.110 --test 15016

  # Test range (excluding known dangerous ones)
  python test_register_writability.py -i 192.168.0.110 --range 15000:15044 --exclude 15016,15017

  # Dry run (no actual writes)
  python test_register_writability.py -i 192.168.0.110 --range 15000:15044 --dry-run

WARNING:
  Even writing the same value back can trigger unintended behavior.
  Always test on non-production systems first!
"""

import argparse
import time
import sys
from typing import List, Tuple, Optional

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    from pymodbus.client.tcp import ModbusTcpClient


class SafeRegisterTester:
    """Safe register writability tester."""
    
    def __init__(self, host: str, port: int = 502, timeout: int = 5, unit_id: int = 1):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.unit_id = unit_id
        self.client = None
        self.results = []
        
    def connect(self) -> bool:
        """Connect to Modbus device."""
        self.client = ModbusTcpClient(
            host=self.host,
            port=self.port,
            timeout=self.timeout
        )
        
        if not self.client.connect():
            print(f"❌ Failed to connect to {self.host}:{self.port}")
            return False
        
        print(f"✅ Connected to {self.host}:{self.port}")
        return True
    
    def disconnect(self):
        """Disconnect from device."""
        if self.client:
            self.client.close()
            print("✅ Disconnected")
    
    def read_register(self, address: int) -> Optional[int]:
        """Read a single register."""
        try:
            result = self.client.read_holding_registers(
                address=address,
                count=1,
                slave=self.unit_id
            )
            
            if result.isError():
                return None
            
            return result.registers[0]
        except Exception as e:
            print(f"   ⚠️  Read error: {e}")
            return None
    
    def write_register(self, address: int, value: int) -> bool:
        """Write a single register."""
        try:
            result = self.client.write_register(
                address=address,
                value=value,
                slave=self.unit_id
            )
            
            return not result.isError()
        except Exception as e:
            print(f"   ⚠️  Write error: {e}")
            return False
    
    def test_register_writability(
        self, 
        address: int, 
        dry_run: bool = False,
        wait_after_write: float = 0.5
    ) -> Tuple[str, Optional[int], Optional[int]]:
        """
        Test if a register is writable by reading and writing back same value.
        
        Returns:
            (status, original_value, final_value)
            status: 'WRITABLE', 'READ_ONLY', 'READ_ERROR', 'WRITE_ERROR', 'CHANGED'
        """
        # Step 1: Read original value
        original = self.read_register(address)
        
        if original is None:
            return ('READ_ERROR', None, None)
        
        print(f"   📖 Read: {original} (0x{original:04X})")
        
        if dry_run:
            return ('DRY_RUN', original, original)
        
        # Step 2: Write same value back
        print(f"   ✍️  Writing back: {original}...")
        write_ok = self.write_register(address, original)
        
        if not write_ok:
            return ('READ_ONLY', original, None)  # Likely read-only
        
        # Step 3: Wait for write to settle
        time.sleep(wait_after_write)
        
        # Step 4: Verify value
        final = self.read_register(address)
        
        if final is None:
            return ('WRITE_ERROR', original, None)
        
        print(f"   ✔️  Verify: {final} (0x{final:04X})")
        
        if final != original:
            print(f"   ⚠️  VALUE CHANGED: {original} → {final}")
            return ('CHANGED', original, final)
        
        return ('WRITABLE', original, final)
    
    def test_range(
        self, 
        start: int, 
        end: int, 
        exclude: List[int] = None,
        dry_run: bool = False
    ):
        """Test a range of registers."""
        exclude = exclude or []
        
        print(f"\n{'='*70}")
        print(f"Testing Registers: {start} to {end}")
        if exclude:
            print(f"Excluding: {exclude}")
        print(f"Mode: {'DRY RUN' if dry_run else 'LIVE TEST'}")
        print(f"{'='*70}\n")
        
        writable_count = 0
        readonly_count = 0
        error_count = 0
        
        for addr in range(start, end + 1):
            if addr in exclude:
                print(f"⏭️  {addr}: SKIPPED (excluded)")
                continue
            
            print(f"\n🔍 Testing {addr}:")
            status, orig, final = self.test_register_writability(addr, dry_run)
            
            # Record result
            self.results.append({
                'address': addr,
                'status': status,
                'original': orig,
                'final': final
            })
            
            # Categorize
            if status == 'WRITABLE':
                print(f"   ✅ WRITABLE")
                writable_count += 1
            elif status == 'READ_ONLY':
                print(f"   🔒 READ-ONLY")
                readonly_count += 1
            elif status == 'DRY_RUN':
                print(f"   💤 Dry run (would test)")
            else:
                print(f"   ❌ {status}")
                error_count += 1
            
            # Small delay between tests
            time.sleep(0.2)
        
        # Summary
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        print(f"Writable:   {writable_count}")
        print(f"Read-Only:  {readonly_count}")
        print(f"Errors:     {error_count}")
        print(f"{'='*70}\n")
    
    def print_writable_list(self):
        """Print list of discovered writable registers."""
        writable = [r for r in self.results if r['status'] == 'WRITABLE']
        
        if not writable:
            print("No writable registers found.")
            return
        
        print("\n📝 WRITABLE REGISTERS:")
        print("=" * 50)
        for r in writable:
            print(f"  {r['address']} = {r['original']} (0x{r['original']:04X})")
        print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Safe register writability tester for FranklinWH extensions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test single register (safe - just writes same value back)
  %(prog)s -i 192.168.0.110 --test 15016
  
  # Test range, excluding critical registers
  %(prog)s -i 192.168.0.110 --range 15000:15044 --exclude 15016,15017
  
  # Dry run (no actual writes)
  %(prog)s -i 192.168.0.110 --range 15000:15044 --dry-run
        """
    )
    
    parser.add_argument('-i', '--host', required=True, help='aGate IP address')
    parser.add_argument('-p', '--port', type=int, default=502, help='Modbus port (default: 502)')
    parser.add_argument('-t', '--timeout', type=int, default=5, help='Timeout in seconds')
    parser.add_argument('-u', '--unit', type=int, default=1, help='Unit ID (default: 1)')
    
    parser.add_argument('--test', type=int, help='Test single register')
    parser.add_argument('--range', help='Test range (format: START:END, e.g., 15000:15044)')
    parser.add_argument('--exclude', help='Comma-separated list of registers to skip')
    parser.add_argument('--dry-run', action='store_true', help='Dry run - read only, no writes')
    
    args = parser.parse_args()
    
    if not args.test and not args.range:
        parser.error("Must specify either --test or --range")
    
    # Parse exclusions
    exclude = []
    if args.exclude:
        exclude = [int(x.strip()) for x in args.exclude.split(',')]
    
    # Create tester
    tester = SafeRegisterTester(
        host=args.host,
        port=args.port,
        timeout=args.timeout,
        unit_id=args.unit
    )
    
    # Connect
    if not tester.connect():
        return 1
    
    try:
        if args.test:
            # Test single register
            print(f"\n🔍 Testing register {args.test}:")
            status, orig, final = tester.test_register_writability(args.test, args.dry_run)
            print(f"\nResult: {status}")
            if status == 'WRITABLE':
                print(f"✅ Register {args.test} is WRITABLE")
            elif status == 'READ_ONLY':
                print(f"🔒 Register {args.test} is READ-ONLY")
        
        elif args.range:
            # Parse range
            start, end = map(int, args.range.split(':'))
            tester.test_range(start, end, exclude, args.dry_run)
            tester.print_writable_list()
    
    finally:
        tester.disconnect()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
