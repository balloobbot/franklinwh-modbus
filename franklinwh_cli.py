#!/usr/bin/env python3
"""
FranklinWH Modbus Battery Manager - CLI

Command-line interface for controlling FranklinWH aGate battery systems.
Uses the franklinwh library package.

Examples:
    # Show system status
    python franklinwh_cli.py -i 192.168.1.100 --status
    
    # Self-consumption mode
    python franklinwh_cli.py -i 192.168.1.100 --mode self_consumption --target-soc 90
    
    # Emergency backup mode
    python franklinwh_cli.py -i 192.168.1.100 --mode emergency_backup --target-soc 95
    
    # Manual control
    python franklinwh_cli.py -i 192.168.1.100 --mode manual --power -3000
"""

import argparse
import logging
import signal
import sys
import os

# Add src to path for development (not needed if package is installed)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from franklinwh import (
    FranklinWHController,
    VirtualModeController,
    VirtualMode,
    TOUSchedule,
    BatteryCommand,
    ControlMode,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_parser():
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description='FranklinWH aGate Battery Controller',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -i 192.168.1.100 --status
  %(prog)s -i 192.168.1.100 --mode self_consumption --target-soc 90
  
  # Explicit action flags (RECOMMENDED)
  %(prog)s -i 192.168.1.100 --charge 3000 --duration 3600
  %(prog)s -i 192.168.1.100 --discharge 3000 --duration 3600
  %(prog)s -i 192.168.1.100 --standby
  
  # Legacy --power with sign
  %(prog)s -i 192.168.1.100 --mode manual --power 3000 --duration 3600   # Charge
  %(prog)s -i 192.168.1.100 --mode manual --power -3000 --duration 3600  # Discharge
        """
    )
    
    # Connection
    parser.add_argument('-i', '--ip', required=True, help='aGate IP address')
    parser.add_argument('-p', '--port', type=int, default=502, help='Modbus port (default: 502)')
    parser.add_argument('-u', '--unit', type=int, default=2, help='Modbus unit ID (default: 2)')
    parser.add_argument('-t', '--timeout', type=float, default=10.0, help='Connection timeout')
    
    # Control modes
    parser.add_argument('--mode', choices=[m.value for m in VirtualMode],
                       help='Virtual control mode')
    
    # Power control (mutually exclusive)
    power_group = parser.add_mutually_exclusive_group()
    power_group.add_argument('--power', type=float, 
                            help='Manual power in watts (+charge, -discharge). Legacy, use --charge/--discharge.')
    power_group.add_argument('--charge', type=float, metavar='WATTS',
                            help='Charge battery at specified watts (import from grid)')
    power_group.add_argument('--discharge', type=float, metavar='WATTS',
                            help='Discharge battery at specified watts (export to grid)')
    power_group.add_argument('--standby', action='store_true',
                            help='Set battery to standby (0W)')
    
    parser.add_argument('--target-soc', type=float, default=100, help='Target SoC (default: 100)')
    parser.add_argument('--reserve', type=int, default=20, help='Reserve percentage (default: 20)')
    parser.add_argument('--threshold', type=int, default=2000, help='Peak shave threshold (default: 2000)')
    parser.add_argument('--schedule-file', help='TOU schedule JSON file')
    
    # SoC limits
    parser.add_argument('--max-charge-soc', type=int, default=100, 
                       help='Max charge SoC - will EXIT when reached during charging')
    parser.add_argument('--min-discharge-soc', type=int, 
                       help='Min discharge SoC - will EXIT when reached during discharging (auto-read if not set)')
    parser.add_argument('--soc-ramp-window', type=int, default=10, help='SoC ramping window')
    parser.add_argument('--force', action='store_true', help='Force override SoC limits')
    parser.add_argument('--off-grid-permitted', action='store_true', help='Allow operation when grid is disconnected')
    
    # Operation
    parser.add_argument('--duration', type=int, help='Run duration in seconds')
    parser.add_argument('--reset-on-start', action='store_true', help='Reset control state on start')
    parser.add_argument('--dry-run', action='store_true', help='Simulate without sending commands')
    
    # Info
    parser.add_argument('--status', action='store_true', help='Show system status')
    parser.add_argument('--healthcheck', action='store_true', help='Run health check')
    parser.add_argument('--stop', action='store_true', help='Stop control and exit')
    parser.add_argument('--clear-alarms', action='store_true', help='Clear/reset alarms (write to AlarmReset)')
    parser.add_argument('--test-extension-write', action='store_true', help='Test extension register writability (15507-15509)')
    
    # Schedule validation
    parser.add_argument('--show-schedule', metavar='FILE', help='Display schedule file')
    parser.add_argument('--validate-schedule', metavar='FILE', help='Validate schedule file')
    
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose logging')
    
    return parser


def print_status(ctrl: FranklinWHController):
    """Print system status with dashboard-style layout."""
    print("\n" + "=" * 60)
    print("  FRANKLINWH SYSTEM STATUS")
    print("=" * 60)
    
    # Read all data first
    nameplate = ctrl.read_nameplate()
    bat = ctrl.read_battery_status()
    grid = ctrl.read_grid_status()
    solar = ctrl.read_solar_status()
    ctl = ctrl.read_control_status()
    native = ctrl.read_native_mode()
    alarms = ctrl.read_alarms()
    
    soc = bat.get('soc', 0)
    soh = bat.get('soh', 0)
    
    # Power values
    grid_power = grid.get('grid_power_w', 0)
    
    # Solar power - try multiple sources (Model 502 AC, extension total, fallback)
    # Priority: 1) Model 502 AC power, 2) Extension total_solar, 3) 0
    solar_ac = solar.get('ac_power_w', 0)  # Model 502 - actual solar AC output
    solar_ext = solar.get('extension', {})
    solar_total = solar_ext.get('total_solar', 0) if solar_ext else 0
    # Use best available solar value
    solar_power = solar_ac if solar_ac > 0 else solar_total
    
    # Battery DC power from Model 714
    battery_dc = solar.get('battery_dc_power_w', solar.get('dc_power_w', 0))
    
    # Calculate home load (estimate)
    # home = solar + grid - battery_dc
    home_load = solar_power + grid_power - battery_dc
    
    # ═══════════════════════════════════════════════════════
    # POWER FLOW SUMMARY (like dashboard)
    # ═══════════════════════════════════════════════════════
    print(f"\n  ⚡ POWER FLOW SUMMARY")
    print("  " + "─" * 54)
    
    # Show arrows based on direction
    # Home always consumes (just show magnitude), other sources show direction
    solar_arrow = "→" if solar_power > 50 else " "
    battery_arrow = "↓" if battery_dc < -50 else ("↑" if battery_dc > 50 else " ")
    grid_arrow = "←" if grid_power > 50 else ("→" if grid_power < -50 else " ")
    
    # Home load status (always consuming if magnitude > 50W)
    home_active = abs(home_load) > 50
    
    print(f"      Solar: {solar_arrow} {abs(solar_power):>5.0f}W  {'Producing' if solar_power > 50 else 'Idle'}")
    print(f"       Home: ← {abs(home_load):>5.0f}W  {'Consuming' if home_active else 'Idle'}")
    
    if battery_dc < 0:
        print(f"     Battery: {battery_arrow} {abs(battery_dc):>5.0f}W  CHARGING")
    elif battery_dc > 0:
        print(f"     Battery: {battery_arrow} {abs(battery_dc):>5.0f}W  DISCHARGING")
    else:
        print(f"     Battery:     {abs(battery_dc):>5.0f}W  IDLE")
    
    if grid_power > 0:
        print(f"       Grid: {grid_arrow} {abs(grid_power):>5.0f}W  IMPORTING")
    elif grid_power < 0:
        print(f"       Grid: {grid_arrow} {abs(grid_power):>5.0f}W  EXPORTING")
    else:
        print(f"       Grid:     {abs(grid_power):>5.0f}W  BALANCED")
    
    # ═══════════════════════════════════════════════════════
    # BATTERY POWER (DC side)
    # ═══════════════════════════════════════════════════════
    print(f"\n  🔋 BATTERY POWER (DC)")
    print("  " + "─" * 54)
    print(f"    State of Charge:  {soc:.1f}%")
    print(f"    State of Health:  {soh:.1f}%")
    print(f"    DC Power:         {abs(battery_dc):.0f}W  {'CHARGING' if battery_dc < 0 else ('DISCHARGING' if battery_dc > 0 else 'IDLE')}")
    print(f"    Available:        {bat.get('wh_available', 0)/1000:.1f} / {bat.get('wh_rating', 0)/1000:.1f} kWh")
    
    # Show control source
    wset_ena = ctl.get('wset_enabled', 0)
    if wset_ena == 1:
        wset = ctl.get('wset_watts', 0)
        print(f"    Modbus Control:   ACTIVE (WSet={wset:.0f}W)")
    elif battery_dc != 0:
        print(f"    Control Source:   Cloud API (aGate native mode)")
    else:
        print(f"    Control Source:   Idle (no active control)")
    
    # ═══════════════════════════════════════════════════════
    # AC POWER (like dashboard card)
    # ═══════════════════════════════════════════════════════
    print(f"\n  ⚡ AC POWER")
    print("  " + "─" * 54)
    print(f"    Architecture:     AC-Coupled (aGate X)")
    print(f"    Solar Inputs:     2x 63A AC circuits (+ remote via aPbox/aHub)")
    print(f"    AC Type:          {grid.get('ac_type', 'Unknown')}")
    print(f"    Voltage:          {grid.get('voltage_v', 0):.1f}V")
    print(f"    Frequency:        {grid.get('frequency_hz', 0):.2f}Hz")
    
    # Calculate current from power and voltage (I = P/V)
    voltage = grid.get('voltage_v', 240)
    if voltage > 0:
        current = abs(grid_power) / voltage
        print(f"    Current:          {current:.1f}A")
    
    # Power factor if available
    pf = grid.get('power_factor', 0)
    if pf:
        print(f"    Power Factor:     {pf:.2f}")
    
    # Apparent power (VA)
    va = grid.get('grid_va', 0)
    if va:
        print(f"    Apparent Power:   {va:.0f}VA")
    
    # Reactive power (VAR)
    var = grid.get('grid_var', 0)
    if var:
        print(f"    Reactive Power:   {var:.0f}VAR")
    
    print(f"    Grid Power:       {grid_power:.0f}W  ({'Importing' if grid_power > 0 else ('Exporting' if grid_power < 0 else 'Balanced')})")
    print(f"    Connection:       {grid.get('connection_state', 'Unknown')}")
    print(f"    Grid Mode:        {grid.get('grid_mode', 'Unknown')}")
    print(f"    Inverter State:   {grid.get('inverter_state', 'Unknown')}")
    
    # ═══════════════════════════════════════════════════════
    # DEVICE INFO
    # ═══════════════════════════════════════════════════════
    if nameplate:
        print(f"\n  📟 DEVICE")
        print("  " + "─" * 54)
        
        def clean_value(val):
            if not val:
                return None
            val = str(val).strip()
            for prefix in ['Mn:', 'Md:', 'SN:', 'Vr:', 'Opt:']:
                if val.startswith(prefix):
                    val = val[len(prefix):].strip()
            return val
        
        mfg = clean_value(nameplate.get('manufacturer'))
        model = clean_value(nameplate.get('model'))
        serial = clean_value(nameplate.get('serial'))
        version = clean_value(nameplate.get('version'))
        
        if mfg:
            print(f"    Manufacturer:     {mfg}")
        if model:
            print(f"    Model:            {model}")
        if serial:
            print(f"    Serial:           {serial}")
        if version:
            print(f"    Firmware:         {version}")
    
    # ═══════════════════════════════════════════════════════
    # AGATE MODE
    # ═══════════════════════════════════════════════════════
    if native:
        print(f"\n  🎛️  AGATE MODE")
        print("  " + "─" * 54)
        print(f"    OnGridMode:       {native.get('mode_name', 'Unknown')}")
        print(f"    Self Reserve:     {native.get('self_reserve_pct', 0)}%")
        print(f"    TOU Reserve:      {native.get('tou_reserve_pct', 0)}%")
    
    # ═══════════════════════════════════════════════════════
    # ALARMS
    # ═══════════════════════════════════════════════════════
    print(f"\n  🚨 ALARMS")
    print("  " + "─" * 54)
    has_alarms = False
    if alarms.get('system_alrm', 0):
        print(f"    ⚠️  System Alarm:  0x{alarms['system_alrm']:08X}")
        has_alarms = True
    if alarms.get('dc_port_alrm', 0):
        print(f"    ⚠️  DC Port Alarm:  0x{alarms['dc_port_alrm']:08X}")
        has_alarms = True
    if alarms.get('battery_sta', 0) == 6:
        print(f"    ⚠️  Battery Status: FAULT")
        has_alarms = True
    if not has_alarms:
        print(f"    ✓ No alarms active")
    
    # ═══════════════════════════════════════════════════════
    # EXTENSION REGISTERS (Write Test)
    # ═══════════════════════════════════════════════════════
    ext_write = ctrl.get_extension_write_status()
    if ext_write.get('tested'):
        print(f"\n  📝 EXTENSION REGISTERS (15500+)")
        print("  " + "─" * 54)
        
        # OnGridMode
        ongrid = ext_write.get('ongrid_mode', {})
        if ongrid.get('writable'):
            print(f"    ✓ OnGridMode (15507):  WRITABLE")
        else:
            err = ongrid.get('error', 'unknown')
            print(f"    ✗ OnGridMode (15507):  READ-ONLY ({err})")
        
        # Self Reserve
        self_res = ext_write.get('self_reserve', {})
        if self_res.get('writable'):
            print(f"    ✓ SelfReserve (15508): WRITABLE")
        else:
            err = self_res.get('error', 'unknown')
            print(f"    ✗ SelfReserve (15508): READ-ONLY ({err})")
        
        # TOU Reserve
        tou_res = ext_write.get('tou_reserve', {})
        if tou_res.get('writable'):
            print(f"    ✓ TOUReserve (15509):  WRITABLE")
        else:
            err = tou_res.get('error', 'unknown')
            print(f"    ✗ TOUReserve (15509):  READ-ONLY ({err})")
        
        # Summary note
        writable_count = sum(1 for k in ['ongrid_mode', 'self_reserve', 'tou_reserve']
                            if ext_write.get(k, {}).get('writable'))
        if writable_count == 0:
            print(f"    ─" * 27)
            print(f"    Note: Write access requires 'SPAN Modbus' unlock")
            print(f"          in installer settings (FranklinWH app)")
    
    print("\n" + "=" * 60)


def print_health(health):
    """Print health check results."""
    print("\n" + "=" * 60)
    print(f"  HEALTH CHECK: {health.message}")
    print("=" * 60)
    
    # Nameplate info if available
    details = health.details
    nameplate = details.get('nameplate', {})
    if nameplate:
        print("\n  DEVICE:")
        # Clean up values - strip register prefixes
        def clean_value(val):
            if not val:
                return None
            val = str(val).strip()
            for prefix in ['Mn:', 'Md:', 'SN:', 'Vr:', 'Opt:']:
                if val.startswith(prefix):
                    val = val[len(prefix):].strip()
            return val
        
        mfg = clean_value(nameplate.get('manufacturer'))
        model = clean_value(nameplate.get('model'))
        serial = clean_value(nameplate.get('serial'))
        version = clean_value(nameplate.get('version'))
        
        if mfg:
            print(f"    Manufacturer: {mfg}")
        if model:
            print(f"    Model:        {model}")
        if serial:
            print(f"    Serial:       {serial}")
        if version:
            print(f"    Firmware:     {version}")
    
    print("\n  Checks:")
    for key, value in details.items():
        if key == 'nameplate':  # Skip nameplate, already shown
            continue
        # Special handling for zombie_state - False is actually GOOD
        if key == 'zombie_state':
            if value:
                print(f"    🚨 {key}: ZOMBIE STATE DETECTED")
            else:
                print(f"    ✓ {key}: OK (not in zombie state)")
        # Skip extension_write_results dict - handled separately
        elif key == 'extension_write_test':
            continue
        elif key == 'extension_writable':
            if value:
                print(f"    ✓ {key}: {', '.join(value)}")
            else:
                print(f"    ℹ {key}: None")
        elif key == 'extension_readonly':
            if value:
                print(f"    ℹ {key}: {', '.join(value)}")
        elif isinstance(value, bool):
            status = "✓" if value else "✗"
            print(f"    {status} {key}: {'OK' if value else 'FAIL'}")
        else:
            print(f"    {key}: {value}")
    
    # Blocking alarms
    blocking = details.get('blocking_alarms', [])
    if blocking:
        print(f"\n  ⚠️  BLOCKING ALARMS:")
        for alarm in blocking:
            print(f"    • {alarm}")
    
    print("\n  Recommendations:")
    for rec in health.recommendations:
        print(f"    • {rec}")
    
    print("\n" + "=" * 60)


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Normalize explicit action flags to power value
    # Priority: --charge, --discharge, --standby, then --power
    if args.charge is not None:
        args.power = abs(args.charge)  # Positive = charge
        logger.debug(f"--charge {args.charge}W → power={args.power}W")
    elif args.discharge is not None:
        args.power = -abs(args.discharge)  # Negative = discharge
        logger.debug(f"--discharge {args.discharge}W → power={args.power}W")
    elif args.standby:
        args.power = 0
        logger.debug("--standby → power=0W")
    
    # Schedule file operations (no hardware needed)
    if args.show_schedule:
        try:
            schedule = TOUSchedule.from_file(args.show_schedule)
            print(f"\nSchedule: {schedule.get_schedule_name()}")
            print("=" * 60)
            import json
            print(json.dumps(schedule.to_dict(), indent=2))
            print(f"\nCurrent: {schedule.get_current_period()}")
            print(f"Strategy: {schedule.get_strategy()}")
            sys.exit(0)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    if args.validate_schedule:
        try:
            schedule = TOUSchedule.from_file(args.validate_schedule)
            print(f"✓ Valid: {schedule.get_schedule_name()}")
            sys.exit(0)
        except Exception as e:
            print(f"✗ Invalid: {e}")
            sys.exit(1)
    
    # Connect to hardware
    ctrl = FranklinWHController(
        ip_address=args.ip,
        port=args.port,
        unit_id=args.unit,
        timeout=args.timeout,
    )
    
    if not ctrl.connect():
        sys.exit(1)
    
    try:
        # Health check
        if args.healthcheck:
            health = ctrl.healthcheck()
            print_health(health)
            sys.exit(0 if health.healthy else 1)
        
        # Stop control
        if args.stop:
            if ctrl.reset_control_state():
                print("✓ Control released")
                sys.exit(0)
            else:
                print("✗ Failed to release control")
                sys.exit(1)
        
        # Clear alarms
        if args.clear_alarms:
            success, msg = ctrl.clear_alarms()
            if success:
                print(f"✓ {msg}")
                sys.exit(0)
            else:
                print(f"✗ Failed: {msg}")
                sys.exit(1)
        
        # Show status
        if args.status:
            print_status(ctrl)
            sys.exit(0)
        
        # Test extension register writability
        if args.test_extension_write:
            print("\n  Testing Extension Register Writability...")
            print("  " + "─" * 54)
            
            # Force re-test by resetting results and running again
            ctrl._extension_write_results = {
                'tested': False,
                'timestamp': None,
                'ongrid_mode': {'writable': False, 'error': None},
                'self_reserve': {'writable': False, 'error': None},
                'tou_reserve': {'writable': False, 'error': None},
            }
            results = ctrl._test_extension_writability()
            
            print(f"\n  Results:")
            for reg_name in ['ongrid_mode', 'self_reserve', 'tou_reserve']:
                reg_result = results.get(reg_name, {})
                addr = {'ongrid_mode': 15507, 'self_reserve': 15508, 'tou_reserve': 15509}[reg_name]
                if reg_result.get('writable'):
                    print(f"    ✓ {reg_name.replace('_', ' ').title():12} ({addr}): WRITABLE")
                else:
                    err = reg_result.get('error', 'unknown')
                    print(f"    ✗ {reg_name.replace('_', ' ').title():12} ({addr}): READ-ONLY ({err})")
            
            writable_count = sum(1 for k in ['ongrid_mode', 'self_reserve', 'tou_reserve']
                                if results.get(k, {}).get('writable'))
            
            print(f"\n  Summary: {writable_count}/3 registers writable")
            if writable_count == 0:
                print("  Note: Write access requires 'SPAN Modbus' unlock in installer settings")
            elif writable_count < 3:
                print("  Note: Partial write access - some features may be limited")
            else:
                print("  Full write access - all extension features available")
            
            print("")
            sys.exit(0)
        
        # Virtual modes
        if args.mode:
            # Check for aGate native mode conflicts FIRST (before any control)
            state = ctrl.check_state()
            native_mode = state.get('ongrid_mode', 'Unknown')
            conflicts = state.get('conflicts', [])
            battery_activity = state.get('battery_activity', 'Unknown')
            
            # Check if aGate is actively controlling via Cloud API
            if conflicts:
                print("\n🚨 CONFLICTS DETECTED - aGate is actively controlling:")
                for conflict in conflicts:
                    print(f"   • {conflict}")
                
                if not args.reset_on_start:
                    print("\n⚠️  Use --reset-on-start to force takeover")
                    print("⚠️  Or change aGate mode in vendor app first")
                    print("⚠️  Exiting to avoid fighting with aGate control!")
                    sys.exit(1)
                else:
                    print("\n⚠️  --reset-on-start specified, forcing takeover...")
            
            # Check for off-grid condition
            grid_connected = state.get('grid_connected', False)
            connection_state = state.get('connection_state', 'Unknown')
            if not grid_connected and not args.off_grid_permitted:
                print(f"\n🚨 OFF-GRID DETECTED - Grid connection state: {connection_state}")
                print("   Operating without grid connection can be unsafe.")
                print("   Use --off-grid-permitted to explicitly allow off-grid operation.")
                sys.exit(1)
            elif not grid_connected and args.off_grid_permitted:
                print(f"\n⚠️  WARNING: Operating OFF-GRID (connection: {connection_state})")
                print("   --off-grid-permitted specified, continuing...")
            
            # Validate SoC limits before operation
            current_soc = state.get('soc', 0)
            requested_power = args.power or 0
            is_charge_request = requested_power > 0 or args.mode in ['self_consumption', 'emergency_backup', 'time_of_use']
            is_discharge_request = requested_power > 0 or args.mode == 'peak_shave'
            
            # Check 1: target_soc for charge modes
            if is_charge_request and args.target_soc and current_soc >= args.target_soc:
                print(f"\n🛑 SoC VALIDATION FAILED:")
                print(f"   Current SoC: {current_soc:.1f}%")
                print(f"   Target SoC:  {args.target_soc:.1f}%")
                print(f"   Cannot charge - already at or above target.")
                print(f"   Use --force to override (not recommended).")
                sys.exit(1)
            
            # Check 2: max_charge_soc for charge modes
            if is_charge_request and current_soc >= args.max_charge_soc:
                print(f"\n🛑 SoC VALIDATION FAILED:")
                print(f"   Current SoC: {current_soc:.1f}%")
                print(f"   Max Charge SoC: {args.max_charge_soc}%")
                print(f"   Cannot charge - at maximum charge limit.")
                print(f"   Use --force to override (not recommended).")
                sys.exit(1)
            
            # Check 3: min_discharge_soc for discharge modes
            min_discharge = args.min_discharge_soc or state.get('reserve_soc', 20)
            if is_discharge_request and current_soc <= min_discharge:
                print(f"\n🛑 SoC VALIDATION FAILED:")
                print(f"   Current SoC: {current_soc:.1f}%")
                print(f"   Min Discharge SoC: {min_discharge}%")
                print(f"   Cannot discharge - at minimum discharge limit.")
                print(f"   Use --force to override (not recommended).")
                sys.exit(1)
            
            if args.reset_on_start:
                ctrl.reset_control_state()
            
            # Create virtual mode controller
            vmc = VirtualModeController(
                ctrl,
                max_charge_soc=args.max_charge_soc,
                min_discharge_soc=args.min_discharge_soc,
                soc_ramp_window=args.soc_ramp_window,
                force_soc_limits=args.force,
            )
            
            # Load schedule if provided
            if args.schedule_file:
                try:
                    schedule = TOUSchedule.from_file(args.schedule_file)
                    vmc.tou = schedule
                    print(f"Loaded schedule: {schedule}")
                except Exception as e:
                    print(f"Error loading schedule: {e}")
                    sys.exit(1)
            
            # Map args to mode parameters
            mode_kwargs = {'target_soc': args.target_soc}
            
            if args.mode == 'self_consumption':
                mode_kwargs['self_reserve_pct'] = args.reserve
            elif args.mode == 'emergency_backup':
                mode_kwargs['backup_target_soc'] = args.target_soc
            elif args.mode == 'peak_shave':
                mode_kwargs['peak_shave_threshold'] = args.threshold
            elif args.mode == 'manual':
                mode_kwargs['manual_power_w'] = args.power or 0
            elif args.mode == 'time_of_use' and vmc.tou.is_file_based():
                mode_kwargs['tou_schedule'] = vmc.tou
            
            # Set mode and run
            try:
                vmc.set_mode(VirtualMode(args.mode), **mode_kwargs)
            except ValueError as e:
                print(f"\n❌ CONFIGURATION ERROR: {e}")
                print("\nOptions:")
                print(f"  1. Lower --target-soc below current SoC")
                print(f"  2. Wait for battery to discharge naturally")
                print(f"  3. Use discharge mode to reduce SoC first")
                sys.exit(1)
            
            print(f"\n{'='*60}")
            print(f"  STARTING: {args.mode} mode")
            if args.duration:
                print(f"  DURATION: {args.duration}s")
            print(f"  Press Ctrl+C to stop")
            print(f"{'='*60}")
            
            vmc.run_continuous(duration_seconds=args.duration, enable_safety_checks=False)
            sys.exit(0)
        
        # Direct power control (no mode)
        if args.power is not None:
            # Check if we should run continuous mode
            # Continuous if: duration specified OR SoC limits specified
            has_duration = args.duration is not None
            has_soc_limits = (args.max_charge_soc != 100 or args.min_discharge_soc is not None)
            is_controlling = args.power != 0
            
            if (has_duration or has_soc_limits) and is_controlling:
                # Run continuous control with SoC limits
                from franklinwh import VirtualModeController, VirtualMode
                vmc = VirtualModeController(
                    ctrl,
                    max_charge_soc=args.max_charge_soc,
                    min_discharge_soc=args.min_discharge_soc or 20,
                    soc_ramp_window=args.soc_ramp_window
                )
                vmc.set_mode(VirtualMode.MANUAL, manual_power_w=args.power)
                
                if has_duration:
                    print(f"Running manual mode: {args.power}W for {args.duration}s")
                else:
                    print(f"Running manual mode: {args.power}W until SoC limit reached")
                print(f"  Max charge SoC: {args.max_charge_soc}%")
                print(f"  Min discharge SoC: {vmc.min_discharge_soc}%")
                print("Press Ctrl+C to stop")
                vmc.run_continuous(duration_seconds=args.duration, enable_safety_checks=False)
                sys.exit(0)
            else:
                # One-shot command
                cmd = BatteryCommand(power_watts=args.power, mode=ControlMode.LIMIT_ABS)
                success, msg = ctrl.send_command(cmd, dry_run=args.dry_run)
                print(f"Result: {'SUCCESS' if success else 'FAILED'} - {msg}")
                sys.exit(0 if success else 1)
        
        # No action specified
        parser.print_help()
        
    except KeyboardInterrupt:
        print("\nInterrupted")
    except Exception as e:
        logger.error(f"Runtime error: {e}")
        raise
    finally:
        try:
            ctrl.reset_control_state()
            logger.info("Control released")
        except:
            pass
        ctrl.disconnect()


if __name__ == '__main__':
    main()
