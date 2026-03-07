#!/home/david/dev/modbus/venv/bin/python3
"""
SunSpec Model 704 Battery Control with FranklinWH aGate Support

Enhanced for devices using direct addressing (base 0 or 1) without
40000/50000 offsets, specifically FranklinWH aGate.
"""

import argparse
import sys
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, List, Tuple, Union

try:
    from sunspec2.modbus.client import TCPClientDevice
    from sunspec2 import SunSpecError
except ImportError:
    print("Error: sunspec2 not installed. Run: pip install pysunspec2")
    sys.exit(1)


class BatteryState(IntEnum):
    OFF = 1
    STANDBY = 2
    CHARGING = 3
    DISCHARGING = 4
    FAULT = 5


class ControlMode(IntEnum):
    MAX_CHARGE = 1
    MAX_DISCHARGE = 2
    SET_W = 3
    SET_VA = 4
    SET_VAR = 5


@dataclass
class BatteryCommand:
    mode: ControlMode
    power: float
    is_va: bool = False


@dataclass
class ReversionConfig:
    wset_rvrt_tms: int = 0
    varset_rvrt_tms: int = 0
    vaset_rvrt_tms: int = 0


class SunSpecBatteryController:
    """SunSpec Model 704 controller with flexible addressing."""
    
    # SunSpec 704 register offsets (standard model definition)
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
    REG_WSET_RVRT_REM = 18
    
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
        quiet: bool = False,
        # FranklinWH specific
        franklinwh_mode: bool = False,
        address_zero_based: bool = False
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
        self.franklinwh_mode = franklinwh_mode
        self.address_zero_based = address_zero_based
        self.device: Optional[TCPClientDevice] = None
        
        # FranklinWH: typically base 1, direct addressing
        if franklinwh_mode:
            self.base_address = 1 if not address_zero_based else 0
            if not quiet:
                print(f"FranklinWH mode: using base address {self.base_address}")
        
    def _log(self, message: str, force: bool = False):
        if not self.quiet or force:
            print(message)
    
    def _get_effective_address(self, offset: int) -> int:
        """Calculate effective Modbus address."""
        # Standard: base + offset (e.g., 40000 + 3 = 40003)
        # FranklinWH: base + offset (e.g., 1 + 3 = 4)
        return self.base_address + offset
    
    def connect(self) -> bool:
        try:
            self.device = TCPClientDevice(
                slave_id=self.unit_id,
                ipaddr=self.ip_address,
                ipport=self.port,
                timeout=self.timeout
            )
            self.device.connect()
            self._log(f"Connected to {self.ip_address}:{self.port} (unit {self.unit_id})")
            self._log(f"Base address: {self.base_address} "
                     f"({'FranklinWH/direct' if self.franklinwh_mode else 'standard'})")
            return True
        except Exception as e:
            self._log(f"Connection failed: {e}", force=True)
            return False
    
    def disconnect(self):
        if self.device:
            self.device.disconnect()
            self.device = None
            self._log("Disconnected")
    
    def _read_registers_direct(self, offset: int, count: int) -> List[int]:
        if not self.device:
            raise RuntimeError("Not connected")
        
        addr = self._get_effective_address(offset)
        self._log(f"  [Debug] Read addr {addr} (offset {offset}, count {count})")
        return self.device.client.read_holding_registers(addr, count)
    
    def _write_registers_direct(self, offset: int, values: List[int]):
        if not self.device:
            raise RuntimeError("Not connected")
        
        addr = self._get_effective_address(offset)
        self._log(f"  [Debug] Write addr {addr} (offset {offset}): {values}")
        self.device.client.write_multiple_registers(addr, values)
    
    def _split_int32(self, value: int) -> Tuple[int, int]:
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
        if high == self.NOT_IMPL_HIGH and low == self.NOT_IMPL_LOW:
            return -0x80000000
        
        value = (high << 16) | low
        if value & 0x80000000:
            value = value - 0x100000000
        return value
    
    def _values_equal(self, written: List[int], read: List[int], tolerance: int = 0) -> bool:
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
    ) -> dict:
        addr = self._get_effective_address(offset)
        used_infopoint = False
        last_error = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                if attempt == 1:
                    self._log(f"  Writing to effective address {addr} (offset {offset}): {values}")
                    if description:
                        self._log(f"    Description: {description}")
                
                try:
                    self._write_registers_direct(offset, values)
                    write_method = "direct"
                except Exception as direct_error:
                    # Try infopoint fallback
                    if register_name and hasattr(self.device, 'models'):
                        try:
                            if '704' in self.device.models:
                                model = self.device.models['704']
                                if hasattr(model, register_name):
                                    point = getattr(model, register_name)
                                    if len(values) == 1:
                                        point.value = values[0]
                                    else:
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
                    return {
                        'success': True,
                        'address': addr,
                        'values_written': values,
                        'values_read': None,
                        'attempts': attempt,
                        'used_infopoint': used_infopoint,
                        'error_message': None
                    }
                
                time.sleep(self.verify_delay)
                values_read = self._read_registers_direct(offset, len(values))
                
                if self._values_equal(values, values_read):
                    self._log(f"    ✓ Verified (attempt {attempt}, {write_method})")
                    return {
                        'success': True,
                        'address': addr,
                        'values_written': values,
                        'values_read': list(values_read),
                        'attempts': attempt,
                        'used_infopoint': used_infopoint,
                        'error_message': None
                    }
                
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
        
        return {
            'success': False,
            'address': addr,
            'values_written': values,
            'values_read': None,
            'attempts': self.max_retries,
            'used_infopoint': used_infopoint,
            'error_message': last_error
        }
    
    def verify_model(self) -> bool:
        try:
            self._log("Reading model information...")
            data = self._read_registers_direct(self.REG_MODEL_ID, 2)
            model_id = data[0]
            model_len = data[1]
            
            self._log(f"  Raw registers at offset {self.REG_MODEL_ID}: {data}")
            
            if model_id != self.MODEL_ID_704:
                # FranklinWH might use different model numbering or offset
                self._log(f"Warning: Expected model 704, found model {model_id}", force=True)
                self._log(f"  This may be normal for FranklinWH - continuing...", force=True)
                # Don't fail immediately for FranklinWH - let user decide
                if not self.franklinwh_mode:
                    return False
            
            self._log(f"Found SunSpec Model {model_id} (length: {model_len} registers)")
            return True
            
        except Exception as e:
            self._log(f"Model verification failed: {e}", force=True)
            # FranklinWH troubleshooting hint
            if self.franklinwh_mode:
                self._log("  Try --franklinwh-zero-based if base 1 doesn't work", force=True)
            else:
                self._log("  Try --franklinwh mode for direct addressing devices", force=True)
            return False
    
    def scan_for_model(self, start_addr: int = 0, end_addr: int = 200, step: int = 1) -> Optional[Tuple[int, int]]:
        """Scan for SunSpec model 704 (useful for FranklinWH discovery)."""
        if self.quiet:
            return None  # Skip scan in quiet mode
            
        self._log(f"Scanning for Model 704 from address {start_addr} to {end_addr}...")
        
        for test_base in range(start_addr, end_addr + 1, step):
            try:
                # Quick read of potential model ID register
                addr = self.base_address + test_base
                data = self.device.client.read_holding_registers(addr, 2)
                model_id = data[0]
                
                if model_id == self.MODEL_ID_704:
                    self._log(f"  Found Model 704 at offset {test_base} (effective address {addr})")
                    return (test_base, data[1])  # (offset, length)
                    
            except Exception:
                continue
        
        self._log("  Model 704 not found in scan range")
        return None
    
    def get_battery_status(self) -> dict:
        try:
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
                'wset_rvrt_tms': data[13],
                'varset_rvrt_tms': data[14],
                'vaset_rvrt_tms': data[15],
                'wset_rvrt_rem': self._combine_int32(data[16], data[17]),
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
        
        output.append("\n--- Reversion Timers ---")
        wset_rvrt = status['wset_rvrt_tms']
        varset_rvrt = status['varset_rvrt_tms']
        vaset_rvrt = status['vaset_rvrt_tms']
        wset_rem = status['wset_rvrt_rem']
        
        output.append(f"WSetRvrtTms:        {wset_rvrt} s {'(no reversion)' if wset_rvrt == 0 else ''}")
        output.append(f"VarSetRvrtTms:      {varset_rvrt} s {'(no reversion)' if varset_rvrt == 0 else ''}")
        output.append(f"VaSetRvrtTms:       {vaset_rvrt} s {'(no reversion)' if vaset_rvrt == 0 else ''}")
        
        if wset_rvrt > 0 and wset_rem != -0x80000000:
            output.append(f"WSetRvrtRem:        {wset_rem} s remaining")
        
        output.append("-" * 30)
        
        self._log("\n".join(output))
    
    def send_command(
        self,
        command: BatteryCommand,
        ctl_timeout: int = 60,
        rvrt_config: Optional[ReversionConfig] = None
    ) -> Tuple[bool, List[dict]]:
        if rvrt_config is None:
            rvrt_config = ReversionConfig()
        
        results = []
        
        power = int(command.power)
        power_high, power_low = self._split_int32(power)
        max_high, max_low = 0x7FFF, 0xFFFF
        
        w_set_high, w_set_low = self.NOT_IMPL_HIGH, self.NOT_IMPL_LOW
        va_set_high, va_set_low = self.NOT_IMPL_HIGH, self.NOT_IMPL_LOW
        var_set_high, var_set_low = self.NOT_IMPL_HIGH, self.NOT_IMPL_LOW
        
        if command.mode == ControlMode.SET_W:
            w_set_high, w_set_low = power_high, power_low
        elif command.mode == ControlMode.SET_VA:
            va_set_high, va_set_low = power_high, power_low
        elif command.mode == ControlMode.SET_VAR:
            var_set_high, var_set_low = power_high, power_low
        
        register_block = [
            command.mode.value,
            max_high, max_low,
            max_high, max_low,
            w_set_high, w_set_low,
            var_set_high, var_set_low,
            va_set_high, va_set_low,
            ctl_timeout,
            rvrt_config.wset_rvrt_tms,
            rvrt_config.varset_rvrt_tms,
            rvrt_config.vaset_rvrt_tms,
        ]
        
        self._log(f"\n--- Sending Command ---")
        self._log(f"Mode: {command.mode.name}, Power: {command.power}")
        self._log(f"Command Timeout: {ctl_timeout}s")
        
        self._log(f"\nReversion Configuration:")
        self._log(f"  WSetRvrtTms:    {rvrt_config.wset_rvrt_tms}s "
                  f"{'(no reversion)' if rvrt_config.wset_rvrt_tms == 0 else ''}")
        self._log(f"  VarSetRvrtTms:  {rvrt_config.varset_rvrt_tms}s "
                  f"{'(no reversion)' if rvrt_config.varset_rvrt_tms == 0 else ''}")
        self._log(f"  VaSetRvrtTms:   {rvrt_config.vaset_rvrt_tms}s "
                  f"{'(no reversion)' if rvrt_config.vaset_rvrt_tms == 0 else ''}")
        
        result = self.verified_write(
            offset=self.REG_CTRL_MODE,
            values=register_block,
            register_name="CtlMode",
            description=f"Control: mode={command.mode.name}, power={command.power}"
        )
        results.append(result)
        
        self._log(f"\n--- Write Summary ---")
        for i, r in enumerate(results, 1):
            status = "✓ SUCCESS" if r['success'] else "✗ FAILED"
            method = "infopoint" if r['used_infopoint'] else "direct"
            self._log(f"Write {i}: {status}")
            self._log(f"  Address:  {r['address']}")
            self._log(f"  Values:   {r['values_written']}")
            if r['values_read']:
                self._log(f"  Readback: {r['values_read']}")
            self._log(f"  Method:   {method}")
            self._log(f"  Attempts: {r['attempts']}")
            if r['error_message']:
                self._log(f"  Error:    {r['error_message']}")
        
        all_success = all(r['success'] for r in results)
        return all_success, results


def parse_power_string(power_str: str) -> Tuple[float, bool]:
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
    time_str = time_str.strip().lower()
    
    if time_str.isdigit():
        return int(time_str)
    
    if time_str.endswith('s'):
        return int(time_str[:-1])
    elif time_str.endswith('m'):
        return int(time_str[:-1]) * 60
    elif time_str.endswith('h'):
        return int(time_str[:-1]) * 3600
    
    raise ValueError(f"Cannot parse time value: {time_str}")


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='SunSpec Model 704 Battery Control (FranklinWH aGate compatible)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
FranklinWH aGate Specific Options:
  --franklinwh          Enable FranklinWH mode (base address 1)
  --franklinwh-zero-based  Use base address 0 instead of 1
  --scan-models         Scan for Model 704 location

Standard vs FranklinWH Addressing:
  Standard SunSpec:    base 40000 + offset 3 = address 40003
  FranklinWH aGate:    base 1 + offset 3 = address 4

Examples:
  # FranklinWH aGate - simple mode
  %(prog)s -i 192.168.1.50 --franklinwh -p 5000W
  
  # FranklinWH with reversion
  %(prog)s -i 192.168.1.50 --franklinwh -p 3000W --wset-rvrt 10m
  
  # Scan for model location (troubleshooting)
  %(prog)s -i 192.168.1.50 --franklinwh --scan-models
  
  # Standard SunSpec device
  %(prog)s -i 192.168.1.100 --base-addr 40000 -p 5000W
        """
    )
    
    # Connection
    conn_group = parser.add_argument_group('Connection')
    conn_group.add_argument('-i', '--ip', required=True, help='IP address')
    conn_group.add_argument('--port', type=int, default=502)
    conn_group.add_argument('--unit-id', type=int, default=1)
    conn_group.add_argument('-t', '--timeout', type=float, default=5.0)
    
    # Addressing - mutually exclusive approaches
    addr_group = parser.add_mutually_exclusive_group()
    addr_group.add_argument('--base-addr', type=int, default=40000,
                           help='Custom base address (default: 40000)')
    addr_group.add_argument('--franklinwh', action='store_true',
                           help='FranklinWH mode: use base address 1')
    addr_group.add_argument('--franklinwh-zero-based', action='store_true',
                           help='FranklinWH mode: use base address 0')
    
    # Commands
    cmd_group = parser.add_mutually_exclusive_group(required=True)
    cmd_group.add_argument('-p', '--power', help='Power setpoint')
    cmd_group.add_argument('--max-charge', action='store_true')
    cmd_group.add_argument('--max-discharge', action='store_true')
    cmd_group.add_argument('--idle', action='store_true')
    cmd_group.add_argument('--status', action='store_true')
    
    # Reversion timers
    rvrt_group = parser.add_argument_group('Reversion Timers')
    rvrt_group.add_argument('--wset-rvrt', metavar='TIME')
    rvrt_group.add_argument('--varset-rvrt', metavar='TIME')
    rvrt_group.add_argument('--vaset-rvrt', metavar='TIME')
    rvrt_group.add_argument('--rvrt-all', metavar='TIME')
    
    # Other options
    parser.add_argument('--ctl-timeout', type=int, default=60)
    parser.add_argument('--verify', dest='verify_writes', action='store_true', default=True)
    parser.add_argument('--no-verify', dest='verify_writes', action='store_false')
    parser.add_argument('--retry', type=int, default=3)
    parser.add_argument('--retry-interval', type=float, default=0.5)
    parser.add_argument('--verify-delay', type=float, default=0.1)
    parser.add_argument('-q', '--quiet', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--scan-models', action='store_true',
                       help='Scan for Model 704 and exit')
    
    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()
    
    quiet = args.quiet and not args.verbose
    
    # Determine addressing mode
    franklinwh_mode = args.franklinwh or args.franklinwh_zero_based
    address_zero_based = args.franklinwh_zero_based
    
    # Override base_addr if FranklinWH mode specified
    base_addr = args.base_addr
    if franklinwh_mode:
        base_addr = 0 if address_zero_based else 1
    
    # Build reversion config
    rvrt_config = type('obj', (object,), {
        'wset_rvrt_tms': 0,
        'varset_rvrt_tms': 0,
        'vaset_rvrt_tms': 0
    })()
    
    if args.rvrt_all:
        try:
            rvrt_seconds = parse_time_string(args.rvrt_all)
            rvrt_config.wset_rvrt_tms = rvrt_seconds
            rvrt_config.varset_rvrt_tms = rvrt_seconds
            rvrt_config.vaset_rvrt_tms = rvrt_seconds
        except ValueError as e:
            if not quiet:
                print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    for opt, attr in [(args.wset_rvrt, 'wset_rvrt_tms'),
                      (args.varset_rvrt, 'varset_rvrt_tms'),
                      (args.vaset_rvrt, 'vaset_rvrt_tms')]:
        if opt:
            try:
                setattr(rvrt_config, attr, parse_time_string(opt))
            except ValueError as e:
                if not quiet:
                    print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
    
    # Create controller
    controller = SunSpecBatteryController(
        ip_address=args.ip,
        port=args.port,
        base_address=base_addr,
        timeout=args.timeout,
        unit_id=args.unit_id,
        verify_writes=args.verify_writes,
        max_retries=args.retry,
        retry_interval=args.retry_interval,
        verify_delay=args.verify_delay,
        quiet=quiet,
        franklinwh_mode=franklinwh_mode,
        address_zero_based=address_zero_based
    )
    
    if not controller.connect():
        sys.exit(1)
    
    try:
        # Scan mode
        if args.scan_models:
            result = controller.scan_for_model()
            if result:
                offset, length = result
                print(f"Found Model 704 at offset {offset}, length {length}")
                print(f"Effective base address would be: {controller.base_address}")
                print(f"Try: --base-addr {controller.base_address + offset - 0} "
                      f"(if model starts at offset 0)")
            else:
                print("Model 704 not found")
            sys.exit(0 if result else 1)
        
        # Verify model (with FranklinWH flexibility)
        if not controller.verify_model():
            # Try scan as fallback for FranklinWH
            if franklinwh_mode and not quiet:
                print("Attempting auto-scan...", file=sys.stderr)
                result = controller.scan_for_model()
                if result:
                    offset, _ = result
                    print(f"Found at offset {offset} - "
                          f"you may need to adjust base address", file=sys.stderr)
            sys.exit(1)
        
        if args.status:
            controller.print_status()
            return
        
        # Build command
        command = None
        
        if args.idle:
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
                print("No valid command", file=sys.stderr)
            sys.exit(1)
        
        # Cast rvrt_config to proper dataclass
        proper_rvrt = ReversionConfig(
            wset_rvrt_tms=rvrt_config.wset_rvrt_tms,
            varset_rvrt_tms=rvrt_config.varset_rvrt_tms,
            vaset_rvrt_tms=rvrt_config.vaset_rvrt_tms
        )
        
        success, results = controller.send_command(
            command,
            args.ctl_timeout,
            proper_rvrt
        )
        
        if not quiet:
            time.sleep(0.3)
            print("\n--- Final Status ---")
            controller.print_status()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        if not quiet:
            print("\nInterrupted - setting idle...", file=sys.stderr)
        try:
            controller.send_command(
                BatteryCommand(ControlMode.SET_W, 0.0),
                5,
                ReversionConfig()
            )
        except Exception:
            pass
        sys.exit(130)
    finally:
        controller.disconnect()


if __name__ == '__main__':
    main()
