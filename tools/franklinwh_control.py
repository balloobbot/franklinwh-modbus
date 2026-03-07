#!/usr/bin/env python3
"""
FranklinWH aGate Battery Control Script
Uses sunspec2 library with model-based addressing
"""

import argparse
import sys
import time
import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, List, Tuple, Any

try:
    from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP
    from sunspec2.modbus.client import SunSpecModbusClientException
except ImportError as e:
    print(f"Error: sunspec2 not installed. Run: pip install pysunspec2")
    sys.exit(1)


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ControlMode(IntEnum):
    """DERCtlAC WSetMod values."""
    LIMIT_ABS = 0      # Limit active power to WSet (absolute watts)
    LIMIT_PCT = 1      # Limit to percentage of max
    SET_ABS = 2        # Set active power to WSet (signed, charge/discharge)
    SET_PCT = 3        # Set to percentage of max (signed)


@dataclass
class BatteryCommand:
    """Battery control command."""
    power_watts: float  # Positive=charge, negative=discharge, 0=idle
    mode: ControlMode = ControlMode.SET_ABS


class FranklinWHController:
    """FranklinWH aGate controller using sunspec2 model-based access."""
    
    def __init__(
        self,
        ip_address: str,
        port: int = 502,
        unit_id: int = 2,  # FranklinWH default
        timeout: float = 5.0,
        base_address: int = 0,  # sunspec2 uses 0 for auto/scan
    ):
        self.ip_address = ip_address
        self.port = port
        self.unit_id = unit_id
        self.timeout = timeout
        self.base_address = base_address
        self.dev: Optional[SunSpecModbusClientDeviceTCP] = None
        self.models: dict = {}
        
    def connect(self) -> bool:
        """Connect and scan for models."""
        try:
            logger.info(f"Connecting to {self.ip_address}:{self.port} (unit {self.unit_id})")
            self.dev = SunSpecModbusClientDeviceTCP(
                slave_id=self.unit_id,
                ipaddr=self.ip_address,
                ipport=self.port,
                timeout=self.timeout,
            )
            
            logger.info("Scanning for SunSpec models...")
            self.dev.scan()
            
            self.models = {
                int(k) if str(k).isdigit() else k: v 
                for k, v in self.dev.models.items()
            }
            
            numeric_models = [k for k in self.models.keys() if isinstance(k, int)]
            logger.info(f"Found models: {sorted(numeric_models)}")
            
            # Verify critical models exist
            required = [704, 713, 701]  # Control, Battery, Grid
            missing = [m for m in required if m not in self.models]
            if missing:
                logger.warning(f"Missing recommended models: {missing}")
            
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close connection."""
        if self.dev:
            self.dev.close()
            self.dev = None
            logger.info("Disconnected")
    
    def get_model(self, model_id: int):
        """Get model instance, handling list wrapper."""
        model = self.models.get(model_id)
        if model is None:
            return None
        if isinstance(model, list):
            return model[0] if model else None
        return model
    
    def read_battery_status(self) -> dict:
        """Read current battery status from Model 713."""
        m713 = self.get_model(713)
        if not m713:
            return {}
        
        m713.read()
        
        # Scale factors
        sf_wh = self._get_scale_factor(m713, 'WH_SF')
        sf_pct = self._get_scale_factor(m713, 'Pct_SF')
        
        return {
            'soc': m713.SoC.value * (10 ** sf_pct),
            'soh': m713.SoH.value * (10 ** sf_pct),
            'wh_rating': m713.WHRtg.value * (10 ** sf_wh),
            'wh_available': m713.WHAvail.value * (10 ** sf_wh),
            'status': m713.Sta.value,
        }
    
    def read_grid_status(self) -> dict:
        """Read grid status from Model 701."""
        m701 = self.get_model(701)
        if not m701:
            return {}
        
        m701.read()
        
        sf_w = self._get_scale_factor(m701, 'W_SF')
        
        return {
            'grid_power_w': m701.W.value * (10 ** sf_w),  # Negative = exporting
            'grid_va': m701.VA.value * (10 ** sf_w),
            'grid_var': m701.Var.value * (10 ** sf_w),
            'voltage_v': m701.LNV.value * (10 ** self._get_scale_factor(m701, 'V_SF')),
            'frequency_hz': m701.Hz.value * (10 ** self._get_scale_factor(m701, 'Hz_SF')),
        }
    
    def read_solar_status(self) -> dict:
        """Read solar status from Model 714."""
        m714 = self.get_model(714)
        if not m714:
            return {}
        
        m714.read()
        
        sf_w = self._get_scale_factor(m714, 'DCW_SF')
        sf_a = self._get_scale_factor(m714, 'DCA_SF')
        
        return {
            'dc_power_w': m714.DCW.value * (10 ** sf_w),
            'dc_current_a': m714.DCA.value * (10 ** sf_a) if hasattr(m714, 'DCA') else None,
            'dc_energy_injected_wh': m714.DCWhInj.value,
            'dc_energy_absorbed_wh': m714.DCWhAbs.value,
        }
    
    def read_control_status(self) -> dict:
        """Read current control settings from Model 704."""
        m704 = self.get_model(704)
        if not m704:
            return {}
        
        m704.read()
        
        sf_w = self._get_scale_factor(m704, 'WSet_SF')
        
        return {
            'wset_enabled': m704.WSetEna.value,
            'wset_mode': m704.WSetMod.value,
            'wset_watts': m704.WSet.value * (10 ** sf_w),
            'wset_revert_watts': m704.WSetRvrt.value * (10 ** sf_w) if m704.WSetRvrt.value != -0x80000000 else None,
            'wset_revert_time_s': m704.WSetRvrtTms.value,
            'wset_revert_remain_s': m704.WSetRvrtRem.value,
        }
    
    def _get_scale_factor(self, model, sf_name: str) -> int:
        """Get scale factor value, default to 0."""
        sf_point = getattr(model, sf_name, None)
        if sf_point and hasattr(sf_point, 'value'):
            return sf_point.value
        return 0
    
    def send_command(
        self,
        command: BatteryCommand,
        revert_time_s: int = 0,
        dry_run: bool = False
    ) -> Tuple[bool, str]:
        """
        Send battery control command.
        
        Args:
            command: BatteryCommand with power and mode
            revert_time_s: Auto-revert time (0 = no reversion)
            dry_run: Validate only, don't write
            
        Returns:
            (success, message)
        """
        m704 = self.get_model(704)
        if not m704:
            return False, "Model 704 not available"
        
        # Safety checks
        if not dry_run:
            status = self.read_battery_status()
            if status.get('soc', 0) > 95 and command.power_watts > 0:
                return False, f"SoC too high for charging: {status['soc']:.1f}%"
            if status.get('soc', 100) < 10 and command.power_watts < 0:
                return False, f"SoC too low for discharging: {status['soc']:.1f}%"
        
        # Read current state
        m704.read()
        
        old_wset = m704.WSet.value
        old_ena = m704.WSetEna.value
        
        logger.info(f"Current: WSetEna={old_ena}, WSet={old_wset}")
        logger.info(f"Command: power={command.power_watts}W, mode={command.mode.name}, revert={revert_time_s}s")
        
        if dry_run:
            return True, f"Dry run: Would set WSet={command.power_watts}, WSetEna=1"
        
        # Set values
        m704.WSet.value = int(command.power_watts)
        m704.WSetMod.value = command.mode.value
        m704.WSetEna.value = 1  # Enable power setpoint control
        
        if revert_time_s > 0:
            m704.WSetRvrtTms.value = revert_time_s
        
        try:
            m704.write()
            logger.info("Write successful")
            
            # Verify
            time.sleep(0.2)
            m704.read()
            new_wset = m704.WSet.value
            new_ena = m704.WSetEna.value
            
            if new_ena != 1:
                return False, f"WSetEna not enabled after write: {new_ena}"
            
            return True, f"WSet changed: {old_wset} -> {new_wset}"
            
        except Exception as e:
            return False, f"Write failed: {e}"


def main():
    parser = argparse.ArgumentParser(description='FranklinWH aGate Battery Control')
    parser.add_argument('-i', '--ip', required=True, help='aGate IP address')
    parser.add_argument('-p', '--port', type=int, default=502)
    parser.add_argument('-u', '--unit', type=int, default=2, help='Modbus unit ID')
    parser.add_argument('--power', type=float, help='Power in watts (+charge, -discharge)')
    parser.add_argument('--idle', action='store_true', help='Set to idle (0W)')
    parser.add_argument('--revert', type=int, default=0, help='Auto-revert time in seconds')
    parser.add_argument('--status', action='store_true', help='Read status only')
    parser.add_argument('--dry-run', action='store_true', help='Validate without writing')
    parser.add_argument('-v', '--verbose', action='store_true')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    ctrl = FranklinWHController(
        ip_address=args.ip,
        port=args.port,
        unit_id=args.unit
    )
    
    if not ctrl.connect():
        sys.exit(1)
    
    try:
        if args.status or not (args.power is not None or args.idle):
            # Print comprehensive status
            print("\n=== Battery Status (Model 713) ===")
            bat = ctrl.read_battery_status()
            for k, v in bat.items():
                print(f"  {k}: {v}")
            
            print("\n=== Grid Status (Model 701) ===")
            grid = ctrl.read_grid_status()
            for k, v in grid.items():
                print(f"  {k}: {v}")
            
            print("\n=== Solar Status (Model 714) ===")
            solar = ctrl.read_solar_status()
            for k, v in solar.items():
                print(f"  {k}: {v}")
            
            print("\n=== Control Status (Model 704) ===")
            ctl = ctrl.read_control_status()
            for k, v in ctl.items():
                print(f"  {k}: {v}")
            
            return
        
        # Send command
        power = 0.0 if args.idle else args.power
        cmd = BatteryCommand(power_watts=power)
        
        success, msg = ctrl.send_command(cmd, args.revert, args.dry_run)
        print(f"\nResult: {'SUCCESS' if success else 'FAILED'} - {msg}")
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        ctrl.disconnect()


if __name__ == '__main__':
    main()
