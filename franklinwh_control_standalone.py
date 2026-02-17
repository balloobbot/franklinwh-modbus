#!/usr/bin/env python3
"""
FranklinWH aGate Battery Control Script
Uses sunspec2 library with model-based addressing

Includes:
- Direct hardware control via Model 704
- Virtual mode controller with 6 automated modes
- Time-of-use scheduling
- Continuous tick-based execution
- Graceful shutdown with idle-on-exit
- Health check with zombie state detection
- SPAN extension detection (conditional read/write)
- Cloud API placeholder for future integration

Usage:
    # Direct control
    python franklinwh_control.py -i 192.168.0.110 --power 3000
    python franklinwh_control.py -i 192.168.0.110 --status
    
    # Virtual modes
    python franklinwh_control.py -i 192.168.0.110 --mode self_consumption
    python franklinwh_control.py -i 192.168.0.110 --mode emergency_backup --target-soc 90
    
    # Health check
    python franklinwh_control.py -i 192.168.0.110 --healthcheck
    
    # With reset (recommended if zombie state detected)
    python franklinwh_control.py -i 192.168.0.110 --reset-on-start --mode manual --power 1500
"""

import argparse
import sys
import time
import signal
import atexit
import logging
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time
from enum import Enum, IntEnum
from typing import Optional, Callable, Dict, Any, Tuple, List, Union

try:
    from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP
    from sunspec2.modbus.client import SunSpecModbusClientException
except ImportError as e:
    print(f"Error: sunspec2 not installed. Run: pip install pysunspec2")
    sys.exit(1)

# Future cloud integration (v2.0+)
# try:
#     from franklinwh_cloud import FranklinWHCloudClient
#     CLOUD_API_AVAILABLE = True
# except ImportError:
#     CLOUD_API_AVAILABLE = False
CLOUD_API_AVAILABLE = False  # PLANNED for v2.0


# Module exports for library use
__all__ = [
    'ControlMode',
    'BatteryCommand',
    'VirtualMode',
    'TOUSchedule',
    'FranklinWHController',
    'VirtualModeController',
    'HealthStatus',
]


# Setup logging (module level for backward compatibility)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ControlMode(IntEnum):
    """DERCtlAC WSetMod values per SunSpec 802/704."""
    LIMIT_ABS = 0      # Limit active power to WSet (absolute watts)
    LIMIT_PCT = 1      # Limit to percentage of max
    SET_ABS = 2        # Set active power to WSet (signed, charge/discharge)
    SET_PCT = 3        # Set to percentage of max (signed)


class VirtualMode(Enum):
    """Software-implemented battery modes."""
    SELF_CONSUMPTION = "self_consumption"    # Maximize solar self-use
    EMERGENCY_BACKUP = "emergency_backup"    # Keep full for outages
    TIME_OF_USE = "time_of_use"              # Grid price arbitrage
    GRID_ZERO = "grid_zero"                  # Minimize grid import/export
    PEAK_SHAVE = "peak_shave"                # Discharge during peak demand
    MANUAL = "manual"                        # Direct power setting


@dataclass
class BatteryCommand:
    """Battery control command."""
    power_watts: float  # Positive=charge, negative=discharge, 0=idle
    mode: ControlMode = ControlMode.LIMIT_ABS


@dataclass
class TOUSchedule:
    """Time-of-use rate periods for arbitrage."""
    peak_hours: Tuple[int, int] = (16, 21)      # 4 PM - 9 PM
    shoulder_hours: Tuple[int, int] = (7, 16)    # 7 AM - 4 PM
    off_peak_hours: Tuple[int, int] = (21, 7)   # 9 PM - 7 AM
    
    peak_price: float = 0.50          # $/kWh
    shoulder_price: float = 0.25
    off_peak_price: float = 0.10
    
    def get_current_period(self) -> str:
        """Determine current TOU period."""
        hour = datetime.now().hour
        p_start, p_end = self.peak_hours
        
        if p_start <= hour < p_end:
            return "peak"
        elif self.shoulder_hours[0] <= hour < self.shoulder_hours[1]:
            return "shoulder"
        else:
            return "off_peak"
    
    def get_current_price(self) -> float:
        """Get current electricity price."""
        period = self.get_current_period()
        return getattr(self, f"{period}_price")


@dataclass
class HealthStatus:
    """Health check results."""
    healthy: bool
    message: str
    details: Dict[str, Any]
    recommendations: List[str]


class FranklinWHController:
    """FranklinWH aGate controller using sunspec2 model-based access."""
    
    # FranklinWH SPAN extension registers (15500+)
    # NOTE: Write access requires installer-enabled "SPAN Modbus" option
    EXT_BASE = 15500
    EXT_PV_TOTAL = 15502
    EXT_HOME_LOAD = 15506
    EXT_ONGRID_MODE = 15507      # 0=Backup, 1=Self, 2=TOU, 3=Manual
    EXT_SELF_RESERVE = 15508     # Percentage
    EXT_TOU_RESERVE = 15509      # Percentage
    
    def __init__(
        self,
        ip_address: str,
        port: int = 502,
        unit_id: int = 2,  # FranklinWH default
        timeout: float = 10.0,  # Increased from 5.0 for reliability
        base_address: int = 0,  # sunspec2 uses 0 for auto/scan
    ):
        self.ip_address = ip_address
        self.port = port
        self.unit_id = unit_id
        self.timeout = timeout
        self.base_address = base_address
        self.dev: Optional[SunSpecModbusClientDeviceTCP] = None
        self.models: dict = {}
        self._span_writable: Optional[bool] = None  # Detected at runtime
        
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
        
        return {
            'dc_power_w': m714.DCW.value * (10 ** sf_w),
            'dc_current_a': m714.DCA.value * (10 ** self._get_scale_factor(m714, 'DCA_SF')) if hasattr(m714, 'DCA') else None,
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
    
    def healthcheck(self) -> HealthStatus:
        """
        Comprehensive system health check.
        
        Detects:
        - Connection status
        - Model availability
        - Zombie state (WSetEna=1 with expired revert timer)
        - Battery safety bounds
        - SPAN extension availability
        - OnGridMode (safety for remote control)
        
        Returns:
            HealthStatus with recommendations
        """
        checks = {}
        recommendations = []
        
        # 1. Connection
        checks['connection'] = self.dev is not None
        if not checks['connection']:
            return HealthStatus(
                healthy=False,
                message="CONNECTION FAILED",
                details=checks,
                recommendations=["Check IP address and network connectivity"]
            )
        
        # 2. Critical models
        checks['model_704'] = 704 in self.models
        checks['model_713'] = 713 in self.models
        checks['model_701'] = 701 in self.models
        
        if not checks['model_704']:
            return HealthStatus(
                healthy=False,
                message="CRITICAL: Model 704 (Control) not available",
                details=checks,
                recommendations=["Verify aGate firmware supports SunSpec Model 704"]
            )
        
        # 3. Control state analysis
        m704 = self.get_model(704)
        m704.read()
        
        checks['wset_ena'] = m704.WSetEna.value
        checks['wset_mode'] = m704.WSetMod.value
        checks['wset'] = m704.WSet.value
        checks['revert_rem'] = m704.WSetRvrtRem.value
        checks['revert_tms'] = m704.WSetRvrtTms.value
        
        # Zombie state: enabled but timer expired
        checks['zombie_state'] = (
            m704.WSetEna.value == 1 and
            m704.WSetRvrtRem.value == 0 and
            m704.WSetRvrtTms.value > 0
        )
        
        if checks['zombie_state']:
            recommendations.append(
                "ZOMBIE STATE DETECTED: Use --reset-on-start to clear "
                "(WSetEna=1 with expired revert timer)"
            )
        
        # 4. Battery safety
        bat = self.read_battery_status()
        checks['soc'] = bat.get('soc', 0)
        checks['soc_safe'] = 5 < checks['soc'] < 99
        
        if not checks['soc_safe']:
            recommendations.append(
                f"WARNING: SoC {checks['soc']}% outside safe range (5-99%)"
            )
        
        # 5. Grid safety
        grid = self.read_grid_status()
        checks['grid_voltage'] = grid.get('voltage_v', 0)
        checks['grid_frequency'] = grid.get('frequency_hz', 0)
        checks['grid_safe'] = (
            220 < checks['grid_voltage'] < 260 and
            47 < checks['grid_frequency'] < 53
        )
        
        if not checks['grid_safe']:
            recommendations.append(
                f"WARNING: Grid {checks['grid_voltage']:.1f}V / "
                f"{checks['grid_frequency']:.2f}Hz outside nominal"
            )
        
        # 6. SPAN extension detection
        span_status = self._detect_span_capability()
        checks['span'] = span_status
        
        if span_status['readable']:
            # Check OnGridMode for safety
            ongrid_mode = span_status.get('ongrid_mode', -1)
            mode_names = {0: 'Backup', 1: 'Self', 2: 'TOU', 3: 'Manual'}
            checks['ongrid_mode'] = ongrid_mode
            checks['ongrid_mode_name'] = mode_names.get(ongrid_mode, 'Unknown')
            
            # Safety: remote control only safe in Self-Consumption (2)
            checks['remote_control_safe'] = (ongrid_mode == 2)
            
            if not checks['remote_control_safe'] and ongrid_mode >= 0:
                recommendations.append(
                    f"SAFETY: OnGridMode={ongrid_mode} ({checks['ongrid_mode_name']}). "
                    f"Remote control recommended only in Self-Consumption (2) mode"
                )
        
        # 7. Cloud API status (placeholder)
        checks['cloud_api'] = {
            'available': CLOUD_API_AVAILABLE,
            'status': 'Not implemented in current release',
            'span_enabled': None,  # Would come from cloud
        }
        
        # Determine overall health
        critical_issues = [
            not checks['connection'],
            not checks['model_704'],
            not checks['soc_safe'],
        ]
        
        warnings = [
            checks.get('zombie_state', False),
            not checks.get('remote_control_safe', True),
        ]
        
        if any(critical_issues):
            healthy = False
            message = "CRITICAL ISSUES DETECTED"
        elif any(warnings):
            healthy = False  # Degraded, not fully healthy
            message = "DEGRADED (warnings present)"
        else:
            healthy = True
            message = "HEALTHY"
        
        return HealthStatus(
            healthy=healthy,
            message=message,
            details=checks,
            recommendations=recommendations if recommendations else ["No action required"]
        )
    
    def _detect_span_capability(self) -> dict:
        """
        Detect SPAN extension availability.
        Attempts read, then test write to determine capability.
        """
        result = {
            'readable': False,
            'writable': False,
            'ongrid_mode': -1,
            'self_reserve': -1,
            'tou_reserve': -1,
        }
        
        # Try to read extensions using sunspec2 raw access if possible
        # Fallback: assume not available for safety
        try:
            # Note: sunspec2 doesn't expose raw register access easily
            # This is a placeholder for future pymodbus integration
            # For now, report as unavailable but detectable
            
            # If we had pymodbus raw client:
            # raw = ModbusTcpClient(self.ip_address, port=self.port, timeout=5)
            # r = raw.read_holding_registers(self.EXT_ONGRID_MODE, 1, slave=self.unit_id)
            
            result['readable'] = False  # Placeholder: requires raw Modbus
            result['note'] = 'SPAN detection requires raw Modbus (pymodbus) - see SPAN_INTEGRATION.md'
            
        except Exception as e:
            result['error'] = str(e)
        
        # Cache write capability (detect once)
        self._span_writable = result['writable']
        
        return result
    
    def reset_control_state(self) -> bool:
        """
        Reset aGate to known clean state.
        
        Clears:
        - WSetEna (disable control)
        - WSet (zero setpoint)
        - WSetRvrtTms (clear revert timer)
        
        Returns:
            True if successfully reset
        """
        logger.info("Resetting control state to idle...")
        
        m704 = self.get_model(704)
        if not m704:
            logger.error("Model 704 not available for reset")
            return False
        
        try:
            # Read current state
            m704.read()
            logger.info(f"Before reset: WSetEna={m704.WSetEna.value}, WSet={m704.WSet.value}")
            
            # Disable control
            m704.WSetEna.value = 0
            m704.OpCtl.value = 0
            m704.WSet.value = 0
            m704.WSetRvrtTms.value = 0  # Clear revert timer

            m715 = self.get_model(715)
            if m715:
                m715.read()
                m715.OpCtl.value = 0  # Disable external control, return to auto
                m715.write()
                logger.debug("OpCtl set to 0 (auto mode)")
            
            m704.write()
            time.sleep(0.5)
            
            # Verify
            m704.read()
            success = (m704.WSetEna.value == 0 and m704.WSet.value == 0)
            
            if success:
                logger.info(f"✓ Reset successful: WSetEna={m704.WSetEna.value}, WSet={m704.WSet.value}")
            else:
                logger.warning(f"Reset verification failed: WSetEna={m704.WSetEna.value}, WSet={m704.WSet.value}")
            
            return success
            
        except Exception as e:
            logger.error(f"Reset failed: {e}")
            return False
    
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

        m715 = self.get_model(715)
        if m715:
            m715.read()
            m715.OpCtl.value = 1  # Enable external control
            m715.write()
            logger.debug("OpCtl set to 1 (external control enabled)")
        
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


# ============================================================
# VIRTUAL MODE CONTROLLER
# ============================================================

class VirtualModeController:
    """
    Software-based battery mode controller for FranklinWH aGate.
    
    Since hardware modes (15507-15509) are Modbus read-only without SPAN unlock,
    we implement equivalent logic using direct WSet control via Model 704.
    
    Usage:
        hw = FranklinWHController(ip='192.168.0.110', timeout=10.0)
        hw.connect()
        
        modes = VirtualModeController(hw)
        modes.set_mode(VirtualMode.TIME_OF_USE)
        modes.run_continuous()
    """
    
    def __init__(self, franklinwh_controller: FranklinWHController):
        self.ctrl = franklinwh_controller
        self.mode = VirtualMode.SELF_CONSUMPTION
        self.tou = TOUSchedule()
        
        # Mode-specific parameters
        self.self_reserve_pct = 20        # Keep 20% for self-consumption
        self.backup_target_soc = 95       # Charge to 95% for backup
        self.grid_zero_buffer = 100       # Watts tolerance for grid zero
        self.peak_shave_threshold = 2000  # Discharge if home load > 2kW
        
        # Manual mode setting
        self.manual_power_w = 0
        
        # State for tick() method
        self.last_tick = 0
        self.tick_interval = 5  # seconds
        
        # Shutdown flag
        self._shutdown_requested = False
        
        # Register cleanup handler
        atexit.register(self._emergency_idle)
    
    def _emergency_idle(self):
        """Ensure battery goes idle on unexpected exit."""
        if hasattr(self.ctrl, 'send_command'):
            try:
                logger.warning("Emergency idle on shutdown")
                cmd = BatteryCommand(power_watts=0)
                self.ctrl.send_command(cmd)
            except Exception as e:
                logger.error(f"Emergency idle failed: {e}")
    
    def set_mode(self, mode: VirtualMode, **kwargs):
        """
        Change operating mode with optional parameters.
        
        Examples:
            controller.set_mode(VirtualMode.SELF_CONSUMPTION, self_reserve_pct=15)
            controller.set_mode(VirtualMode.EMERGENCY_BACKUP, backup_target_soc=90)
            controller.set_mode(VirtualMode.MANUAL, manual_power_w=3000)
        """
        self.mode = mode
        
        # Update parameters if provided
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"Set {key} = {value}")
        
        logger.info(f"Mode changed to: {mode.value}")
        
        # Immediate action
        self.execute_once()
    
    def get_current_period(self) -> str:
        """Determine current TOU period."""
        hour = datetime.now().hour
        start, end = self.tou.peak_hours
        
        if start <= hour < end:
            return "peak"
        elif self.tou.shoulder_hours[0] <= hour < self.tou.shoulder_hours[1]:
            return "shoulder"
        else:
            return "off_peak"
    
    def read_status(self) -> Dict[str, Any]:
        """Get current system status from hardware."""
        status = {
            'battery': self.ctrl.read_battery_status(),
            'grid': self.ctrl.read_grid_status(),
            'solar': self.ctrl.read_solar_status(),
            'control': self.ctrl.read_control_status(),
        }
        
        # Add derived values
        solar = status['solar'].get('dc_power_w', 0)
        home = 0  # Estimated or from proprietary registers if available
        grid = status['grid'].get('grid_power_w', 0)
        
        # Estimate home load: solar + grid_import - battery_activity
        battery_w = status['control'].get('wset_watts', 0)
        home_est = solar + grid - battery_w  # Simplified
        
        status['derived'] = {
            'home_load_w': home_est,
            'excess_solar_w': max(solar - home_est, 0),
            'grid_import_w': max(grid, 0),
            'grid_export_w': max(-grid, 0),
        }
        
        return status
    
    def calculate_power(self) -> float:
        """
        Calculate desired battery power based on current mode.
        Returns: watts (positive=charge, negative=discharge, 0=idle)
        """
        # Read current status
        status = self.read_status()
        
        solar = status['solar'].get('dc_power_w', 0)
        home = status['derived'].get('home_load_w', 0)
        grid = status['grid'].get('grid_power_w', 0)
        soc = status['battery'].get('soc', 50)
        
        # Calculate based on mode
        calculator = self._get_calculator()
        power = calculator(solar, home, grid, soc)
        
        # Safety limits
        power = self._apply_safety_limits(power, soc)
        
        return power
    
    def _get_calculator(self) -> Callable:
        """Get the power calculation function for current mode."""
        calculators = {
            VirtualMode.SELF_CONSUMPTION: self._calc_self_consumption,
            VirtualMode.EMERGENCY_BACKUP: self._calc_emergency_backup,
            VirtualMode.TIME_OF_USE: self._calc_time_of_use,
            VirtualMode.GRID_ZERO: self._calc_grid_zero,
            VirtualMode.PEAK_SHAVE: self._calc_peak_shave,
            VirtualMode.MANUAL: self._calc_manual,
        }
        return calculators.get(self.mode, self._calc_self_consumption)
    
    def _calc_self_consumption(self, solar: float, home: float, 
                                grid: float, soc: float) -> float:
        """
        Maximize self-consumption of solar generation.
        
        Strategy:
        - Charge battery with excess solar
        - Discharge to cover home load when solar insufficient
        - Maintain reserve for nighttime
        """
        excess_solar = solar - home
        
        # High SOC - prioritize using battery
        if soc > (100 - self.self_reserve_pct):
            if excess_solar > 0:
                # Still charging but gently
                return min(excess_solar * 0.5, 1000)
            else:
                # Discharge to cover deficit
                return max(home - solar, -5000)
        
        # Low SOC - aggressive charging if excess solar
        if excess_solar > 0:
            return min(excess_solar, 5000)  # Charge up to 5kW
        
        # No excess solar, discharge if needed
        if home > solar and soc > 10:
            return max(solar - home, -5000)
        
        return 0
    
    def _calc_emergency_backup(self, solar: float, home: float,
                                grid: float, soc: float) -> float:
        """
        Keep battery as full as possible for outage protection.
        
        Strategy:
        - Charge from any available source (solar + grid)
        - Only discharge if absolutely necessary
        - Target 95% SOC
        """
        if soc >= self.backup_target_soc:
            # Full enough, minimal activity
            if home > solar:
                # Small discharge to help
                return max(solar - home, -500)
            return 0
        
        # Need to charge
        charge_needed = (self.backup_target_soc - soc) / 100 * 13600  # Wh to full
        hours_to_charge = 2  # Target 2 hours to full
        target_watts = min(charge_needed / hours_to_charge, 5000)
        
        # Use solar first, then grid if needed
        if solar > home:
            # Excess solar available
            return min(solar - home, target_watts)
        else:
            # Charge from grid + solar
            return min(target_watts, 5000)
    
    def _calc_time_of_use(self, solar: float, home: float,
                          grid: float, soc: float) -> float:
        """
        Arbitrage grid prices: charge cheap, discharge expensive.
        
        Strategy:
        - Off-peak: Charge from grid if battery low
        - Shoulder: Normal self-consumption
        - Peak: Discharge to avoid grid import
        """
        period = self.get_current_period()
        
        if period == "off_peak":
            # Cheap power - charge if not full
            if soc < 90:
                return 5000  # Max charge
            return 0
            
        elif period == "peak":
            # Expensive power - discharge to cover load
            if soc > 20:
                # Cover home load, export excess if profitable
                return max(min(home - solar, 5000), -5000)
            return 0
            
        else:  # shoulder
            # Normal self-consumption
            return self._calc_self_consumption(solar, home, grid, soc)
    
    def _calc_grid_zero(self, solar: float, home: float,
                        grid: float, soc: float) -> float:
        """
        Minimize grid interaction (island mode simulation).
        
        Strategy:
        - Target zero grid import/export
        - Battery buffers all imbalances
        """
        target_grid = 0
        current_grid = grid  # Positive = importing
        
        # Calculate battery power to achieve zero grid
        # If importing 500W, discharge 500W
        # If exporting 500W, charge 500W
        power = -current_grid
        
        # Add buffer for stability
        if abs(power) < self.grid_zero_buffer:
            power = 0
            
        # Limit to battery capabilities
        return max(min(power, 5000), -5000)
    
    def _calc_peak_shave(self, solar: float, home: float,
                         grid: float, soc: float) -> float:
        """
        Discharge during high home demand to reduce peak grid draw.
        
        Strategy:
        - Monitor home load
        - Discharge if load exceeds threshold
        - Charge during low demand
        """
        if home > self.peak_shave_threshold and soc > 30:
            # High demand - discharge to help
            discharge = min(home - solar, 5000)
            return -discharge
        
        elif home < 500 and soc < 80:
            # Low demand - charge if solar available
            if solar > home:
                return min(solar - home, 3000)
        
        return 0
    
    def _calc_manual(self, solar: float, home: float,
                     grid: float, soc: float) -> float:
        """Direct manual control."""
        return self.manual_power_w
    
    def _apply_safety_limits(self, power: float, soc: float) -> float:
        """Apply safety limits based on SOC."""
        # Don't charge if full
        if soc >= 99 and power > 0:
            logger.warning(f"SoC {soc:.1f}% - blocking charge")
            return 0
        
        # Don't discharge if empty
        if soc <= 5 and power < 0:
            logger.warning(f"SoC {soc:.1f}% - blocking discharge")
            return 0
        
        # Limit charge rate at high SOC
        if soc > 95 and power > 1000:
            logger.info(f"High SoC {soc:.1f}% - limiting charge to 1000W")
            return 1000
        
        # Limit discharge rate at low SOC
        if soc < 15 and power < -1000:
            logger.info(f"Low SoC {soc:.1f}% - limiting discharge to 1000W")
            return -1000
        
        return power
    
    def execute_once(self) -> float:
        """
        Calculate and send single command.
        Returns actual power sent.
        """
        power = self.calculate_power()
        
        # Send via hardware controller
        cmd = BatteryCommand(power_watts=power, mode=ControlMode.LIMIT_ABS)
        success, msg = self.ctrl.send_command(cmd)
        
        if success:
            logger.info(f"{self.mode.value}: {power:.0f}W")
        else:
            logger.error(f"Failed: {msg}")
        
        return power if success else 0
    
    def tick(self) -> bool:
        """
        Call periodically to maintain control.
        Returns True if action taken, False if skipped.
        """
        now = time.time()
        if now - self.last_tick >= self.tick_interval:
            self.execute_once()
            self.last_tick = now
            return True
        return False
    
    def run_continuous(self, duration_seconds: Optional[float] = None):
        """
        Run controller continuously with graceful shutdown.
        
        Args:
            duration_seconds: Run for N seconds, or None for indefinite
        """
        logger.info(f"Starting continuous control: {self.mode.value}")
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self._shutdown_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler) # systemd stop
        
        start = time.time()
        last_status_log = 0
        
        try:
            while not self._shutdown_requested:
                # Execute control tick
                self.tick()
                
                # Periodic status logging (every 60 seconds)
                now = time.time()
                if now - last_status_log >= 60:
                    status = self.ctrl.read_battery_status()
                    grid = self.ctrl.read_grid_status()
                    logger.info(f"Status: SOC={status.get('soc', 0):.1f}%, "
                               f"Grid={grid.get('grid_power_w', 0):.0f}W")
                    last_status_log = now
                
                # Small sleep to prevent busy-wait
                time.sleep(0.1)
                
                # Check duration limit
                if duration_seconds and (now - start) > duration_seconds:
                    logger.info("Duration expired, stopping")
                    break
                    
        except Exception as e:
            logger.error(f"Runtime error: {e}")
        finally:
            # Safe shutdown - set to idle
            logger.info("Setting idle before exit")
            try:
                cmd = BatteryCommand(power_watts=0)
                self.ctrl.send_command(cmd)
            except Exception as e:
                logger.error(f"Idle command failed: {e}")


# ============================================================
# COMMAND LINE INTERFACE
# ============================================================

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with all options."""
    parser = argparse.ArgumentParser(
        description='FranklinWH aGate Battery Control with Virtual Modes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Health check (recommended first step)
  %(prog)s -i 192.168.0.110 --healthcheck
  
  # Direct control (original functionality)
  %(prog)s -i 192.168.0.110 --power 3000
  %(prog)s -i 192.168.0.110 --power -2000 --revert 3600
  %(prog)s -i 192.168.0.110 --status
  
  # Virtual modes with reset (recommended)
  %(prog)s -i 192.168.0.110 --reset-on-start --mode self_consumption
  %(prog)s -i 192.168.0.110 --reset-on-start --mode emergency_backup --target-soc 90
  %(prog)s -i 192.168.0.110 --reset-on-start --mode time_of_use
  %(prog)s -i 192.168.0.110 --reset-on-start --mode manual --power 1500 --duration 7200
  
  # With custom timeout
  %(prog)s -i 192.168.0.110 -t 15.0 --status
        """
    )
    
    # Connection parameters
    parser.add_argument('-i', '--ip', required=True,
                       help='aGate IP address')
    parser.add_argument('-p', '--port', type=int, default=502,
                       help='Modbus TCP port (default: 502)')
    parser.add_argument('-u', '--unit', type=int, default=2,
                       help='Modbus unit ID (default: 2)')
    parser.add_argument('-t', '--timeout', type=float, default=10.0,
                       help='Connection timeout in seconds (default: 10.0)')
    
    # Startup behavior
    parser.add_argument('--reset-on-start', action='store_true',
                       help='Reset control state to idle before operation '
                            '(recommended if zombie state detected)')
    parser.add_argument('--assume-clean-state', action='store_true',
                       help='Skip health check warnings (use with caution)')
    
    # Direct control (original)
    parser.add_argument('--power', type=float,
                       help='Power in watts (+charge, -discharge)')
    parser.add_argument('--idle', action='store_true',
                       help='Set to idle (0W)')
    parser.add_argument('--revert', type=int, default=0,
                       help='Auto-revert time in seconds')
    
    # Virtual modes (new)
    parser.add_argument('--mode', type=str, choices=[m.value for m in VirtualMode],
                       help='Virtual operating mode')
    parser.add_argument('--reserve', type=int, default=20,
                       help='Self-consumption reserve %% (default: 20)')
    parser.add_argument('--target-soc', type=int, default=95,
                       help='Emergency backup target SOC (default: 95)')
    parser.add_argument('--threshold', type=int, default=2000,
                       help='Peak shave threshold in watts (default: 2000)')
    parser.add_argument('--duration', type=int,
                       help='Mode duration in seconds (default: indefinite)')
    
    # Information
    parser.add_argument('--status', action='store_true',
                       help='Read status only')
    parser.add_argument('--healthcheck', action='store_true',
                       help='Run health check and exit')
    parser.add_argument('--dry-run', action='store_true',
                       help='Validate without writing')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable debug logging')
    
    return parser


def print_health_report(health: HealthStatus):
    """Pretty print health check results."""
    print("\n" + "=" * 70)
    print("HEALTH CHECK REPORT")
    print("=" * 70)
    print(f"Overall Status: {health.message}")
    print(f"Healthy: {'✓ YES' if health.healthy else '✗ NO'}")
    print("-" * 70)
    
    details = health.details
    
    # Connection
    print(f"\nConnection:")
    print(f"  Modbus TCP: {'✓ Connected' if details.get('connection') else '✗ Failed'}")
    
    # Models
    print(f"\nSunSpec Models:")
    print(f"  Model 704 (Control):  {'✓ Present' if details.get('model_704') else '✗ Missing'}")
    print(f"  Model 713 (Battery):  {'✓ Present' if details.get('model_713') else '✗ Missing'}")
    print(f"  Model 701 (Grid):     {'✓ Present' if details.get('model_701') else '✗ Missing'}")
    
    # Control state
    print(f"\nControl State (Model 704):")
    print(f"  WSetEna:              {details.get('wset_ena', 'N/A')}")
    print(f"  WSetMod:              {details.get('wset_mode', 'N/A')}")
    print(f"  WSet:                 {details.get('wset', 'N/A')} W")
    print(f"  Revert Timer:         {details.get('revert_tms', 'N/A')} s")
    print(f"  Revert Remaining:     {details.get('revert_rem', 'N/A')} s")
    
    if details.get('zombie_state'):
        print(f"  ⚠ ZOMBIE STATE:       Control enabled with expired timer!")
    
    # Battery
    print(f"\nBattery (Model 713):")
    soc = details.get('soc', 0)
    soc_safe = details.get('soc_safe', False)
    print(f"  SoC:                  {soc:.1f}% {'✓' if soc_safe else '⚠'}")
    
    # Grid
    print(f"\nGrid (Model 701):")
    v = details.get('grid_voltage', 0)
    f = details.get('grid_frequency', 0)
    grid_safe = details.get('grid_safe', False)
    print(f"  Voltage:              {v:.1f} V {'✓' if grid_safe else '⚠'}")
    print(f"  Frequency:            {f:.2f} Hz {'✓' if grid_safe else '⚠'}")
    
    # SPAN / OnGridMode
    print(f"\nSPAN Extensions:")
    span = details.get('span', {})
    if span.get('readable'):
        ongrid = details.get('ongrid_mode', -1)
        ongrid_name = details.get('ongrid_mode_name', 'Unknown')
        remote_safe = details.get('remote_control_safe', False)
        print(f"  Status:               ✓ Detected")
        print(f"  OnGridMode:           {ongrid} ({ongrid_name})")
        print(f"  Remote Control:       {'✓ Safe' if remote_safe else '⚠ Caution'}")
    else:
        print(f"  Status:               Not detected (SunSpec mode only)")
        print(f"  Note:                 SPAN extensions require installer unlock")
    
    # Cloud API
    print(f"\nCloud API:")
    cloud = details.get('cloud_api', {})
    print(f"  Status:               {'✓ Available' if cloud.get('available') else '✗ Not implemented'}")
    if not cloud.get('available'):
        print(f"  Note:                 Planned for v2.0 release")
    
    # Recommendations
    print("\n" + "-" * 70)
    print("RECOMMENDATIONS:")
    for rec in health.recommendations:
        print(f"  • {rec}")
    
    print("=" * 70)


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create hardware controller
    ctrl = FranklinWHController(
        ip_address=args.ip,
        port=args.port,
        unit_id=args.unit,
        timeout=args.timeout,
    )
    
    if not ctrl.connect():
        sys.exit(1)
    
    # Register signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Signal {signum} received, shutting down...")
        raise SystemExit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Health check mode
        if args.healthcheck:
            health = ctrl.healthcheck()
            print_health_report(health)
            sys.exit(0 if health.healthy else 1)
        
        # Always run health check unless suppressed
        if not args.assume_clean_state:
            health = ctrl.healthcheck()
            if not health.healthy:
                print_health_report(health)
                if health.details.get('zombie_state'):
                    print("\n⚠ ZOMBIE STATE DETECTED!")
                    print("   Use --reset-on-start to clear, or --assume-clean-state to ignore")
                    if not args.reset_on_start:
                        sys.exit(1)
        
        # Reset if requested or required
        if args.reset_on_start:
            if not ctrl.reset_control_state():
                logger.error("Failed to reset control state")
                sys.exit(1)
        
        # Status-only mode
        if args.status:
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
        
        # Virtual mode operation
        if args.mode:
            # Safety: require reset-on-start for virtual modes
            if not args.reset_on_start and not args.assume_clean_state:
                health = ctrl.healthcheck()
                if health.details.get('wset_ena') == 1:
                    print("\n⚠ Control already active. Use --reset-on-start for clean state.")
                    sys.exit(1)
            
            vmc = VirtualModeController(ctrl)
            
            # Map CLI args to mode parameters
            mode_kwargs = {}
            if args.mode == 'self_consumption':
                mode_kwargs['self_reserve_pct'] = args.reserve
            elif args.mode == 'emergency_backup':
                mode_kwargs['backup_target_soc'] = args.target_soc
            elif args.mode == 'peak_shave':
                mode_kwargs['peak_shave_threshold'] = args.threshold
            elif args.mode == 'manual':
                mode_kwargs['manual_power_w'] = args.power or 0
            
            # Set mode and run
            vmc.set_mode(VirtualMode(args.mode), **mode_kwargs)
            
            if args.duration:
                vmc.run_continuous(duration_seconds=args.duration)
            else:
                vmc.run_continuous()
            
            return
        
        # Direct control (original functionality)
        if args.power is not None or args.idle:
            power = 0.0 if args.idle else args.power
            cmd = BatteryCommand(power_watts=power, mode=ControlMode.LIMIT_ABS)
            
            success, msg = ctrl.send_command(cmd, args.revert, args.dry_run)
            print(f"\nResult: {'SUCCESS' if success else 'FAILED'} - {msg}")
            # If revert timer set, stay connected and wait
            if args.revert > 0 and success:
                print(f"Waiting {args.revert} seconds for revert timer...")
                try:
                    time.sleep(args.revert)
                except KeyboardInterrupt:
                    print("\nInterrupted, setting idle...")
                # After wait, idle will be sent by finally block

        sys.exit(0 if success else 1)
        
        # No action specified
        parser.print_help()
        
    except SystemExit:
        # Graceful shutdown handled
        pass
    except Exception as e:
        logger.error(f"Runtime error: {e}")
        raise
    finally:
        # Ensure idle before disconnect
        try:
            m704 = ctrl.get_model(704)
            if m704:
                m704.read()
                m704.WSetEna.value = 0  # Disable external control
                m704.WSet.value = 0
                m704.write()
                logger.info("Control disabled (WSetEna=0)")
        except Exception as e:
            logger.warning(f"Could not disable control: {e}")
        ctrl.disconnect()


if __name__ == '__main__':
    main()