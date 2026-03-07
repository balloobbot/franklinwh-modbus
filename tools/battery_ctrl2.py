#!/usr/bin/env python3
"""
SunSpec Model 704 Battery Control Script with Write Verification and Reversion Timers

Controls battery charging/discharging using SunSpec Modbus TCP with
verified writes, retry logic, configurable output levels, and automatic
reversion timer support (WSetRvrtTms, VarSetRvrtTms, VaSetRvrtTms).
"""

import argparse
import sys
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, List, Tuple, Union

try:
    from pysunspec2.modbus.client import TCPClientDevice
    from pysunspec2 import SunSpecError
except ImportError:
    print("Error: pysunspec2 not installed. Run: pip install pysunspec2")
    sys.exit(1)


class BatteryState(IntEnum):
    """SunSpec 704 battery state values."""
    OFF = 1
    STANDBY = 2
    CHARGING = 3
    DISCHARGING = 4
    FAULT = 5


class ControlMode(IntEnum):
    """SunSpec 704 control mode values."""
    MAX_CHARGE = 1
    MAX_DISCHARGE = 2
    SET_W = 3
    SET_VA = 4
    SET_VAR = 5


@dataclass
class BatteryCommand:
    """Represents a battery control command."""
    mode: ControlMode
    power: float
    is_va: bool = False


@dataclass
class WriteResult:
    """Result of a verified write operation."""
    success: bool
    address: int
    values_written: List[int]
    values_read: Optional[List[int]]
    attempts: int
    used_infopoint: bool
    error_message: Optional[str] = None


@dataclass
class ReversionConfig:
    """Configuration for automatic reversion timers."""
    wset_rvrt_tms: int = 0      # W setpoint reversion time (seconds)
    varset_rvrt_tms: int = 0    # VAR setpoint reversion time (seconds)
    vaset_rvrt_tms: int = 0     # VA setpoint reversion time (seconds)


class SunSpecBatteryController:
    """SunSpec Model 704 battery controller with verified writes and reversion support."""
    
    # Register offsets
    REG_MODEL_ID = 0
    REG_MODEL_LEN = 1
    REG_STATE = 2
    REG_CTRL_MODE = 3
    REG_W_CHA_MAX = 4
    REG_W_DIS_CHA_MAX = 6
    REG_W_SET = 8
    REG_VAR_SET = 10
    REG_VA_SET = 12
    REG_TIMEOUT = 14
    REG_WSET_RVRT_TMS = 15
    REG_VARSET_RVRT_TMS = 16
    REG_VASET_RVRT_TMS = 17
    REG_WSET_RVRT_REM = 18      # 2 registers: remaining reversion time
    
    MODEL_ID_704 = 704
    NOT_IMPL_HIGH = 0x8000
    NOT_IMPL_LOW = 0x0000
    
    def __init__(
        self,
        ip_address: str,
        port: int = 502,
        base_address: int = 40000,
        timeout: float = 5.0,
        unit_id: int = 1,
        verify_writes: bool = True,
        max_retries: int = 3,
        retry_interval: float = 0.5,
        verify_delay: float = 0.1,
        quiet: bool = False
    ):
        self.ip_address = ip_address
        self.port = port
        self.base_address = base_address
        self.timeout = timeout
        self.unit_id = unit_id
        self.verify_writes = verify_writes
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        self.verify_delay = verify_delay
        self.quiet = quiet
        self.device: Optional[TCPClientDevice] = None
        
    def _log(self, message: str, force: bool = False):
        """Print message unless in quiet mode."""
        if not self.quiet or force:
            print(message)
    
    def connect(self) -> bool:
        """Establish connection to the Modbus device."""
        try:
            self.device = TCPClientDevice(
                slave_id=self.unit_id,
                ipaddr=self.ip_address,
                ipport=self.port,
                timeout=self.timeout
            )
            self.device.connect()
            self._log(f"Connected to {self.ip_address}:{self.port} (unit {self.unit_id})")
            return True
        except Exception as e:
            self._log(f"Connection failed: {e}", force=True)
            return False
    
    def disconnect(self):
        """Close the Modbus connection."""
        if self.device:
            self.device.disconnect()
            self.device = None
            self._log("Disconnected")
    
    def _read_registers_direct(self, offset: int, count: int) -> List[int]:
        """Read registers using direct Modbus access."""
        if not self.device:
            raise RuntimeError("Not connected")
        
        addr = self.base_address + offset
        return self.device.client.read_holding_registers(addr, count)
    
    def _write_registers_direct(self, offset: int, values: List[int]):
        """Write registers using direct Modbus access."""
        if not self.device:
            raise RuntimeError("Not connected")
        
        addr = self.base_address + offset
        self.device.client.write_multiple_registers(addr, values)
    
    def _split_int32(self, value: int) -> Tuple[int, int]:
        """Split 32-bit signed int into two 16-bit registers."""
        if value == -0x80000000:
            return self.NOT_IMPL_HIGH, self.NOT_IMPL_LOW
        
        if value > 0x7FFFFFFF:
            value = 0x7FFFFFFF
        elif value < -0x80000000:
            value = -0x80000000
        
        if value < 0:
            value = value & 0xFFFFFFFF
        
        high = (value >> 16) & 0xFFFF
        low = value & 0xFFFF
        return high, low
    
    def _combine_int32(self, high: int, low: int) -> int:
        """Combine two 16-bit registers into signed 32-bit int."""
        if high == self.NOT_IMPL_HIGH and low == self.NOT_IMPL_LOW:
            return -0x80000000
        
        value = (high << 16) | low
        if value & 0x80000000:
            value = value - 0x100000000
        return value
    
    def _values_equal(self, written: List[int], read: List[int], tolerance: int = 0) -> bool:
        """Compare written and read values with optional tolerance."""
        if len(written) != len(read):
            return False
        
        for w, r in zip(written, read):
            if abs(w - r) > tolerance:
                return False
        return True
    
    def verified_write(
        self,
        offset: int,
        values: List[int],
        register_name: str = "",
        description: str = ""
    ) -> WriteResult:
        """
        Perform a verified write with retry logic.
        """
        addr = self.base_address + offset
        used_infopoint = False
        last_error = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                if attempt == 1:
                    self._log(f"  Writing to address {addr} (offset {offset}): {values}")
                    if description:
                        self._log(f"    Description: {description}")
                
                # Try direct write first
                try:
                    self._write_registers_direct(offset, values)
                    write_method = "direct"
                except Exception as direct_error:
                    # Fall back to infopoint if available
                    if register_name:
                        try:
                            if (hasattr(self.device, 'models') and 
                                '704' in self.device.models):
                                model = self.device.models['704']
                                if hasattr(model, register_name):
                                    point = getattr(model, register_name)
                                    if len(values) == 1:
                                        point.value = values[0]
                                    else:
                                        # For multi-register writes, try first value
                                        point.value = values[0]
                                    used_infopoint = True
                                    write_method = "infopoint"
                                else:
                                    raise direct_error
                            else:
                                raise direct_error
                        except Exception:
                            raise direct_error
                    else:
                        raise direct_error
                
                if not self.verify_writes:
                    return WriteResult(
                        success=True,
                        address=addr,
                        values_written=values,
                        values_read=None,
                        attempts=attempt,
                        used_infopoint=used_infopoint,
                        error_message=None
                    )
                
                # Wait before verification read
                time.sleep(self.verify_delay)
                
                # Read back for verification
                values_read = self._read_registers_direct(offset, len(values))
                
                # Check if values match
                if self._values_equal(values, values_read):
                    self._log(f"    ✓ Verified (attempt {attempt}, {write_method})")
                    return WriteResult(
                        success=True,
                        address=addr,
                        values_written=values,
                        values_read=list(values_read),
                        attempts=attempt,
                        used_infopoint=used_infopoint,
                        error_message=None
                    )
                
                # Mismatch - will retry
                self._log(f"    ✗ Mismatch on attempt {attempt}: wrote {values}, read {list(values_read)}")
                last_error = f"Verification failed: wrote {values}, read {list(values_read)}"
                
                if attempt < self.max_retries:
                    self._log(f"    Retrying in {self.retry_interval}s...")
                    time.sleep(self.retry_interval)
                    
            except Exception as e:
                last_error = str(e)
                self._log(f"    ✗ Error on attempt {attempt}: {last_error}")
                if attempt < self.max_retries:
                    self._log(f"    Retrying in {self.retry_interval}s...")
                    time.sleep(self.retry_interval)
        
        # All retries exhausted
        return WriteResult(
            success=False,
            address=addr,
            values_written=values,
            values_read=None,
            attempts=self.max_retries,
            used_infopoint=used_infopoint,
            error_message=last_error
        )
    
    def verify_model(self) -> bool:
        """Verify that Model 704 exists at the base address."""
        try:
            data = self._read_registers_direct(self.REG_MODEL_ID, 2)
            model_id = data[0]
            model_len = data[1]
            
            if model_id != self.MODEL_ID_704:
                self._log(f"Warning: Expected model 704, found model {model_id}", force=True)
                return False
            
            self._log(f"Found SunSpec Model {model_id} (length: {model_len} registers)")
            return True
            
        except Exception as e:
            self._log(f"Model verification failed: {e}", force=True)
            return False
    
    def get_battery_status(self) -> dict:
        """Read current battery status including reversion timers."""
        try:
            # Read extended range including reversion registers
            data = self._read_registers_direct(self.REG_STATE, 20)
            
            status = {
                'state': data[self.REG_STATE - self.REG_STATE],
                'control_mode': data[self.REG_CTRL_MODE - self.REG_STATE],
                'w_cha_max': self._combine_int32(data[2], data[3]),
                'w_dis_cha_max': self._combine_int32(data[4], data[5]),
                'w_set': self._combine_int32(data[6], data[7]),
                'var_set': self._combine_int32(data[8], data[9]),
                'va_set': self._combine_int32(data[10], data[11]),
                'timeout': data[12],
                'wset_rvrt_tms': data[13],      # NEW
                'varset_rvrt_tms': data[14],    # NEW
                'vaset_rvrt_tms': data[15],     # NEW
                'wset_rvrt_rem': self._combine_int32(data[16], data[17]),  # NEW
            }
            
            state_names = {
                1: 'OFF', 2: 'STANDBY', 3: 'CHARGING',
                4: 'DISCHARGING', 5: 'FAULT'
            }
            status['state_name'] = state_names.get(status['state'], f"UNKNOWN({status['state']})")
            
            mode_names = {
                1: 'MAX_CHARGE', 2: 'MAX_DISCHARGE', 3: 'SET_W',
                4: 'SET_VA', 5: 'SET_VAR'
            }
            status['control_mode_name'] = mode_names.get(
                status['control_mode'], f"UNKNOWN({status['control_mode']})"
            )
            
            return status
            
        except Exception as e:
            self._log(f"Failed to read status: {e}", force=True)
            return {}
    
    def print_status(self):
        """Print current battery status with reversion information."""
        status = self.get_battery_status()
        if not status:
            return
        
        output = []
        output.append("\n--- Current Battery Status ---")
        output.append(f"State:              {status['state_name']} ({status['state']})")
        output.append(f"Control Mode:       {status['control_mode_name']} ({status['control_mode']})")
        output.append(f"Max Charge:         {status['w_cha_max']} W")
        output.append(f"Max Discharge:      {status['w_dis_cha_max']} W")
        output.append(f"W Setpoint:         {status['w_set']} W")
        output.append(f"VAR Setpoint:       {status['var_set']} VAR")
        output.append(f"VA Setpoint:        {status['va_set']} VA")
        output.append(f"Command Timeout:    {status['timeout']} s")
        
        # Reversion timers
        output.append("\n--- Reversion Timers ---")
        wset_rvrt = status['wset_rvrt_tms']
        varset_rvrt = status['varset_rvrt_tms']
        vaset_rvrt = status['vaset_rvrt_tms']
        wset_rem = status['wset_rvrt_rem']
        
        output.append(f"WSetRvrtTms:        {wset_rvrt} s {'(no reversion)' if wset_rvrt == 0 else ''}")
        output.append(f"VarSetRvrtTms:      {varset_rvrt} s {'(no reversion)' if varset_rvrt == 0 else ''}")
        output.append(f"VaSetRvrtTms:       {vaset_rvrt} s {'(no reversion)' if vaset_rvrt == 0 else ''}")
        
        if wset_rvrt > 0:
            output.append(f"WSetRvrtRem:        {wset_rem} s remaining")
        
        output.append("-" * 30)
        
        self._log("\n".join(output))
    
    def send_command(
        self,
        command: BatteryCommand,
        ctl_timeout: int = 60,
        rvrt_config: Optional[ReversionConfig] = None
    ) -> Tuple[bool, List[WriteResult]]:
        """
        Send control command with full verification and reversion support.
        """
        if rvrt_config is None:
            rvrt_config = ReversionConfig()  # All zeros = no reversion
        
        results = []
        
        # Build register values
        power = int(command.power)
        power_high, power_low = self._split_int32(power)
        max_high, max_low = 0x7FFF, 0xFFFF
        
        # Determine which power register to set
        w_set_high, w_set_low = self.NOT_IMPL_HIGH, self.NOT_IMPL_LOW
        va_set_high, va_set_low = self.NOT_IMPL_HIGH, self.NOT_IMPL_LOW
        var_set_high, var_set_low = self.NOT_IMPL_HIGH, self.NOT_IMPL_LOW
        
        if command.mode == ControlMode.SET_W:
            w_set_high, w_set_low = power_high, power_low
        elif command.mode == ControlMode.SET_VA:
            va_set_high, va_set_low = power_high, power_low
        elif command.mode == ControlMode.SET_VAR:
            var_set_high, var_set_low = power_high, power_low
        
        # Build complete register block including reversion timers
        # 16 registers total: 0-15 (indices 0-15)
        register_block = [
            command.mode.value,         # 0: Control mode
            max_high, max_low,          # 1-2: WChaMax
            max_high, max_low,          # 3-4: WDisChaMax
            w_set_high, w_set_low,      # 5-6: WSet
            var_set_high, var_set_low,  # 7-8: VarSet
            va_set_high, va_set_low,    # 9-10: VaSet
            ctl_timeout,                # 11: Timeout
            rvrt_config.wset_rvrt_tms,      # 12: WSetRvrtTms
            rvrt_config.varset_rvrt_tms,    # 13: VarSetRvrtTms
            rvrt_config.vaset_rvrt_tms,     # 14: VaSetRvrtTms
        ]
        
        self._log(f"\n--- Sending Command ---")
        self._log(f"Mode: {command.mode.name}, Power: {command.power}")
        self._log(f"Command Timeout: {ctl_timeout}s")
        
        # Reversion info
        self._log(f"\nReversion Configuration:")
        self._log(f"  WSetRvrtTms:    {rvrt_config.wset_rvrt_tms}s "
                  f"{'(no reversion)' if rvrt_config.wset_rvrt_tms == 0 else ''}")
        self._log(f"  VarSetRvrtTms:  {rvrt_config.varset_rvrt_tms}s "
                  f"{'(no reversion)' if rvrt_config.varset_rvrt_tms == 0 else ''}")
        self._log(f"  VaSetRvrtTms:   {rvrt_config.vaset_rvrt_tms}s "
                  f"{'(no reversion)' if rvrt_config.vaset_rvrt_tms == 0 else ''}")
        
        # Perform verified write of entire block
        result = self.verified_write(
            offset=self.REG_CTRL_MODE,
            values=register_block,
            register_name="CtlMode",
            description=f"Full control block with reversion: mode={command.mode.name}, "
                       f"power={command.power}, wset_rvrt={rvrt_config.wset_rvrt_tms}s"
        )
        results.append(result)
        
        # Print summary
        self._log(f"\n--- Write Summary ---")
        for i, r in enumerate(results, 1):
            status = "✓ SUCCESS" if r.success else "✗ FAILED"
            method = "infopoint" if r.used_infopoint else "direct"
            self._log(f"Write {i}: {status}")
            self._log(f"  Address:  {r.address}")
            self._log(f"  Values:   {r.values_written}")
            if r.values_read:
                self._log(f"  Readback: {r.values_read}")
            self._log(f"  Method:   {method}")
            self._log(f"  Attempts: {r.attempts}")
            if r.error_message:
                self._log(f"  Error:    {r.error_message}")
        
        all_success = all(r.success for r in results)
        return all_success, results


def parse_power_string(power_str: str) -> Tuple[float, bool]:
    """Parse power string like '5000W', '-3000W', '5000VA', '0', 'idle'."""
    power_str = power_str.strip().upper()
    
    if power_str in ('IDLE', '0', '0W', '0VA'):
        return 0.0, False
    
    is_va = 'VA' in power_str
    
    num_str = power_str.replace('VA', '').replace('W', '').strip()
    
    try:
        power = float(num_str)
    except ValueError:
        raise ValueError(f"Cannot parse power value: {power_str}")
    
    return power, is_va


def parse_time_string(time_str: str) -> int:
    """Parse time string like '5m', '1h', '300s', or plain seconds."""
    time_str = time_str.strip().lower()
    
    # Plain number = seconds
    if time_str.isdigit():
        return int(time_str)
    
    # Check for suffix
    if time_str.endswith('s'):
        return int(time_str[:-1])
    elif time_str.endswith('m'):
        return int(time_str[:-1]) * 60
    elif time_str.endswith('h'):
        return int(time_str[:-1]) * 3600
    
    raise ValueError(f"Cannot parse time value: {time_str}")


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description='SunSpec Model 704 Battery Control with Reversion Timers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic charge (no reversion)
  %(prog)s -i 192.168.1.100 -p 5000W
  
  # Charge for 5 minutes, then revert
  %(prog)s -i 192.168.1.100 -p 5000W --wset-rvrt 5m
  
  # Discharge with 1 hour reversion
  %(prog)s -i 192.168.1.100 -p -3000W --wset-rvrt 1h
  
  # Complex: different reversion for each power type
  %(prog)s -i 192.168.1.100 -p 4000VA --vaset-rvrt 10m
  
  # Read status to check remaining reversion time
  %(prog)s -i 192.168.1.100 --status

Time Formats for Reversion:
  300, 300s    = 300 seconds
  5m           = 5 minutes (300 seconds)
  1h           = 1 hour (3600 seconds)
  0            = no automatic reversion (default)

Reversion Behavior:
  When WSetRvrtTms > 0, the battery automatically reverts to its
  previous operating state after the specified time. Use --status
  to check WSetRvrtRem for remaining time.
        """
    )
    
    # Connection parameters
    conn_group = parser.add_argument_group('Connection Settings')
    conn_group.add_argument('-i', '--ip', required=True, help='IP address')
    conn_group.add_argument('--port', type=int, default=502, help='TCP port (default: 502)')
    conn_group.add_argument('--unit-id', type=int, default=1, help='Modbus unit ID (default: 1)')
    conn_group.add_argument('--base-addr', type=int, default=40000, 
                           help='Base address (default: 40000)')
    conn_group.add_argument('-t', '--timeout', type=float, default=5.0,
                           help='Connection timeout (default: 5.0)')
    
    # Control commands
    cmd_group = parser.add_mutually_exclusive_group(required=True)
    cmd_group.add_argument('-p', '--power',
                          help='Power setpoint (e.g., 5000W, -3000W, 4000VA, idle)')
    cmd_group.add_argument('--max-charge', action='store_true', help='Maximize charging')
    cmd_group.add_argument('--max-discharge', action='store_true', help='Maximize discharging')
    cmd_group.add_argument('--idle', action='store_true', help='Set to idle/standby')
    cmd_group.add_argument('--status', action='store_true', help='Read status only')
    
    # Reversion timer options
    rvrt_group = parser.add_argument_group('Reversion Timers (Auto-revert after time)')
    rvrt_group.add_argument('--wset-rvrt', metavar='TIME',
                           help='W setpoint reversion time (e.g., 300s, 5m, 1h, 0)')
    rvrt_group.add_argument('--varset-rvrt', metavar='TIME',
                           help='VAR setpoint reversion time')
    rvrt_group.add_argument('--vaset-rvrt', metavar='TIME',
                           help='VA setpoint reversion time')
    rvrt_group.add_argument('--rvrt-all', metavar='TIME',
                           help='Set all reversion timers to same value')
    
    # Command timeout
    parser.add_argument('--ctl-timeout', type=int, default=60,
                       help='Command validity timeout in seconds (default: 60)')
    
    # Write verification options
    verify_group = parser.add_argument_group('Write Verification')
    verify_group.add_argument('--verify', dest='verify_writes', action='store_true',
                             default=True, help='Enable write verification (default)')
    verify_group.add_argument('--no-verify', dest='verify_writes', action='store_false',
                             help='Disable write verification')
    verify_group.add_argument('--retry', type=int, default=3, metavar='N',
                             help='Max retry attempts (default: 3)')
    verify_group.add_argument('--retry-interval', type=float, default=0.5, metavar='S',
                             help='Delay between retries (default: 0.5)')
    verify_group.add_argument('--verify-delay', type=float, default=0.1, metavar='S',
                             help='Delay before verify read (default: 0.1)')
    
    # Output control
    output_group = parser.add_argument_group('Output Control')
    output_group.add_argument('-q', '--quiet', action='store_true',
                             help='Suppress non-error output')
    output_group.add_argument('-v', '--verbose', action='store_true',
                             help='Verbose output (overrides quiet)')
    
    return parser


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Quiet mode: verbose overrides quiet
    quiet = args.quiet and not args.verbose
    
    # Build reversion configuration
    rvrt_config = ReversionConfig()
    
    if args.rvrt_all:
        try:
            rvrt_seconds = parse_time_string(args.rvrt_all)
            rvrt_config.wset_rvrt_tms = rvrt_seconds
            rvrt_config.varset_rvrt_tms = rvrt_seconds
            rvrt_config.vaset_rvrt_tms = rvrt_seconds
        except ValueError as e:
            if not quiet:
                print(f"Error parsing --rvrt-all: {e}", file=sys.stderr)
            sys.exit(1)
    
    if args.wset_rvrt:
        try:
            rvrt_config.wset_rvrt_tms = parse_time_string(args.wset_rvrt)
        except ValueError as e:
            if not quiet:
                print(f"Error parsing --wset-rvrt: {e}", file=sys.stderr)
            sys.exit(1)
    
    if args.varset_rvrt:
        try:
            rvrt_config.varset_rvrt_tms = parse_time_string(args.varset_rvrt)
        except ValueError as e:
            if not quiet:
                print(f"Error parsing --varset-rvrt: {e}", file=sys.stderr)
            sys.exit(1)
    
    if args.vaset_rvrt:
        try:
            rvrt_config.vaset_rvrt_tms = parse_time_string(args.vaset_rvrt)
        except ValueError as e:
            if not quiet:
                print(f"Error parsing --vaset-rvrt: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Create controller
    controller = SunSpecBatteryController(
        ip_address=args.ip,
        port=args.port,
        base_address=args.base_addr,
        timeout=args.timeout,
        unit_id=args.unit_id,
        verify_writes=args.verify_writes,
        max_retries=args.retry,
        retry_interval=args.retry_interval,
        verify_delay=args.verify_delay,
        quiet=quiet
    )
    
    if not controller.connect():
        sys.exit(1)
    
    try:
        if not controller.verify_model():
            if not quiet:
                print("Model verification failed. Use --no-verify to skip.", file=sys.stderr)
            sys.exit(1)
        
        if args.status:
            controller.print_status()
            return
        
        # Build command
        command = None
        
        if args.idle or args.power in ('idle', '0', '0W', '0VA'):
            command = BatteryCommand(ControlMode.SET_W, 0.0, False)
        elif args.max_charge:
            command = BatteryCommand(ControlMode.MAX_CHARGE, 0.0, False)
        elif args.max_discharge:
            command = BatteryCommand(ControlMode.MAX_DISCHARGE, 0.0, False)
        elif args.power:
            power, is_va = parse_power_string(args.power)
            mode = ControlMode.SET_VA if is_va else ControlMode.SET_W
            command = BatteryCommand(mode=mode, power=power, is_va=is_va)
        
        if command is None:
            if not quiet:
                print("No valid command specified", file=sys.stderr)
            sys.exit(1)
        
        # Send command with reversion
        success, results = controller.send_command(
            command, 
            args.ctl_timeout,
            rvrt_config
        )
        
        # Final status
        if not quiet:
            time.sleep(0.3)
            print("\n--- Final Status ---")
            controller.print_status()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        if not quiet:
            print("\nInterrupted - attempting to set idle...", file=sys.stderr)
        try:
            controller.send_command(
                BatteryCommand(ControlMode.SET_W, 0.0), 
                5,
                ReversionConfig()  # No reversion on emergency idle
            )
        except Exception:
            pass
        sys.exit(130)
    finally:
        controller.disconnect()


if __name__ == '__main__':
    main()
