#!/usr/bin/env python3
"""
FranklinWH Modbus Battery Library

Single-file library for controlling FranklinWH aGate battery systems via Modbus.
Forked from franklinwh_control_standalone.py

This is the LIBRARY version - no CLI functionality. Use franklinwh_cli.py for command-line interface.

Usage:
    from franklinwh_modbus_library import (
        FranklinWHController, VirtualModeController, VirtualMode,
        BatteryCommand, TOUSchedule, HealthStatus
    )
    
    # Connect and control
    ctrl = FranklinWHController('192.168.0.110')
    ctrl.connect()
    
    # Direct control
    cmd = BatteryCommand(power_watts=3000)  # Charge at 3000W
    ctrl.send_command(cmd)
    
    # Or use virtual modes
    vmc = VirtualModeController(ctrl)
    vmc.set_mode(VirtualMode.SELF_CONSUMPTION)
    vmc.run_continuous()
"""

import logging
import time
import struct
import json
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time
from enum import Enum, IntEnum
from typing import Optional, Dict, Any, Tuple, List, Union

try:
    from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP
    SUNSPEC_AVAILABLE = True
except ImportError:
    SunSpecModbusClientDeviceTCP = None
    SUNSPEC_AVAILABLE = False

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
    TIME_OF_USE = "time_of_use"              # Price arbitrage
    GRID_ZERO = "grid_zero"                  # Minimize grid import/export
    PEAK_SHAVE = "peak_shave"                # Discharge during high demand
    MANUAL = "manual"                        # Direct power control


@dataclass
class BatteryCommand:
    """Battery control command."""
    power_watts: float  # Positive=charge, negative=discharge, 0=idle
    mode: ControlMode = ControlMode.LIMIT_ABS


@dataclass
class HealthStatus:
    """System health check result."""
    healthy: bool
    message: str
    recommendations: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    zombie_state: bool = False


ONGRID_MODES = {0: 'Emergency Backup', 1: 'Time of Use', 
                2: 'Self-Consumption', 3: 'Manual'}


class TOUSchedule:
    """Time-of-Use schedule with periods and strategies."""
    
    DEFAULT_SCHEDULE = {
        'name': 'Default Single Rate',
        'description': 'Simple single rate schedule',
        'timezone': 'Australia/Sydney',
        'periods': [
            {'name': 'always', 'start': '00:00', 'end': '23:59', 
             'price': 0.30, 'strategy': 'self_consumption'}
        ]
    }
    
    def __init__(self, schedule_data: Optional[Dict] = None):
        self._data = schedule_data or self.DEFAULT_SCHEDULE.copy()
        self._file_path = None
        
    @classmethod
    def from_file(cls, filepath: str) -> 'TOUSchedule':
        """Load schedule from JSON file."""
        with open(filepath) as f:
            data = json.load(f)
        instance = cls(data)
        instance._file_path = filepath
        return instance
    
    def get_schedule_name(self) -> str:
        return self._data.get('name', 'Unnamed Schedule')
    
    def get_current_period(self) -> Dict[str, Any]:
        """Get current period based on time."""
        now = datetime.now()
        current_time = now.strftime('%H:%M')
        
        for period in self._data.get('periods', []):
            if period['start'] <= current_time <= period['end']:
                return period
        return self._data['periods'][0] if self._data.get('periods') else {}
    
    def get_current_price(self) -> float:
        return self.get_current_period().get('price', 0.30)
    
    def get_strategy(self) -> str:
        return self.get_current_period().get('strategy', 'self_consumption')
    
    def get_min_soc(self) -> int:
        return self.get_current_period().get('min_soc', 20)
    
    def get_max_soc(self) -> int:
        return self.get_current_period().get('max_soc', 100)
    
    def to_dict(self) -> Dict:
        return self._data.copy()
    
    def is_file_based(self) -> bool:
        return self._file_path is not None


class FranklinWHController:
    """FranklinWH aGate controller using sunspec2 model-based access."""
    
    EXT_BASE = 15500
    EXT_PV_TOTAL = 15502
    EXT_HOME_LOAD = 15506
    EXT_ONGRID_MODE = 15507
    EXT_SELF_RESERVE = 15508
    EXT_TOU_RESERVE = 15509
    
    def __init__(
        self,
        ip_address: str,
        port: int = 502,
        unit_id: int = 2,
        timeout: float = 10.0,
    ):
        if not SUNSPEC_AVAILABLE:
            raise ImportError("sunspec2 package required: pip install sunspec2")
        
        self.ip_address = ip_address
        self.port = port
        self.unit_id = unit_id
        self.timeout = timeout
        self.dev = None
        self.models = {}
        
        self.RATED_MAX_W = 5000
        self.RATED_MAX_CHARGE_W = 5000
        self.RATED_MAX_DISCHARGE_W = 5000
        
    def connect(self) -> bool:
        """Connect and scan for models."""
        try:
            logger.info(f"Connecting to {self.ip_address}:{self.port}")
            self.dev = SunSpecModbusClientDeviceTCP(
                slave_id=self.unit_id,
                ipaddr=self.ip_address,
                ipport=self.port,
                timeout=self.timeout,
            )
            self.dev.scan()
            self.models = {int(k) if str(k).isdigit() else k: v 
                          for k, v in self.dev.models.items()}
            self.discover_ratings()
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from device."""
        if self.dev:
            try:
                self.dev.disconnect()
            except:
                pass
            self.dev = None
    
    def get_model(self, model_id: int):
        """Get a sunspec model by ID."""
        return self.models.get(model_id)
    
    def discover_ratings(self):
        """Read nameplate ratings from M702."""
        try:
            m702 = self.get_model(702)
            if m702:
                m702.read()
                w_sf = self._get_scale_factor(m702, 'WRtg_SF')
                self.RATED_MAX_W = getattr(m702, 'WRtg', 5000) * (10 ** w_sf)
                self.RATED_MAX_CHARGE_W = getattr(m702, 'WChaRteMaxRtg', 5000) * (10 ** w_sf)
                self.RATED_MAX_DISCHARGE_W = getattr(m702, 'WDisChaRteMaxRtg', 5000) * (10 ** w_sf)
                logger.info(f"Ratings: Max={self.RATED_MAX_W}W, "
                          f"Charge={self.RATED_MAX_CHARGE_W}W, "
                          f"Discharge={self.RATED_MAX_DISCHARGE_W}W")
        except Exception as e:
            logger.warning(f"Could not read ratings: {e}")
    
    def _get_scale_factor(self, model, sf_field: str) -> int:
        """Get scale factor from model."""
        try:
            sf = getattr(model, sf_field, None)
            return sf.value if sf else 0
        except:
            return 0
    
    def _validate_power(self, power_watts: float) -> float:
        """Safety clamp to device ratings."""
        is_charge = power_watts > 0
        limit = self.RATED_MAX_CHARGE_W if is_charge else self.RATED_MAX_DISCHARGE_W
        if abs(power_watts) > limit:
            clamped = -limit if power_watts > 0 else limit
            logger.warning(f"SAFETY CLAMP: {power_watts}W → {clamped}W")
            return clamped
        return power_watts
    
    def send_command(self, command: BatteryCommand, 
                     revert_time_s: int = 0,
                     dry_run: bool = False) -> Tuple[bool, str]:
        """Send battery command."""
        try:
            m704 = self.get_model(704)
            if not m704:
                return False, "Model 704 not found"
            
            m704.read()
            
            safe_watts = self._validate_power(command.power_watts)
            pct = int((safe_watts / self.RATED_MAX_W) * 100)
            pct_raw = int((safe_watts / self.RATED_MAX_W) * 1000)
            
            if dry_run:
                return True, f"Dry Run: WSetPct={pct_raw} ({safe_watts}W)"
            
            sf_pct = self._get_scale_factor(m704, 'WSetPct_SF')
            sf_w = self._get_scale_factor(m704, 'WSet_SF')
            
            m704.WSetEna.value = 1
            m704.WSetMod.value = command.mode
            m704.WSetPct.value = int(pct_raw / (10 ** sf_pct))
            m704.WSet.value = int(safe_watts / (10 ** sf_w))
            
            m704.write()
            
            return True, f"Command sent: {safe_watts}W ({pct}% of {self.RATED_MAX_W}W)"
            
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return False, str(e)
    
    def reset_control_state(self) -> bool:
        """Reset control state to idle."""
        try:
            m704 = self.get_model(704)
            if not m704:
                return False
            
            m704.read()
            m704.WSetEna.value = 0
            m704.WSetPct.value = 0
            m704.WSet.value = 0
            m704.write()
            
            time.sleep(0.5)
            m704.read()
            return m704.WSetEna.value == 0 and m704.WSetPct.value == 0
            
        except Exception as e:
            logger.error(f"Reset failed: {e}")
            return False
    
    def read_battery_status(self) -> Dict[str, Any]:
        """Read battery status from Model 713."""
        try:
            m713 = self.get_model(713)
            if not m713:
                return {}
            m713.read()
            
            sf = self._get_scale_factor(m713, 'WH_SF')
            return {
                'soc': getattr(m713, 'SOC', 0) / 10.0,
                'soh': getattr(m713, 'SOH', 0) / 10.0,
                'capacity_wh': getattr(m713, 'WHRtg', 0) * (10 ** sf),
            }
        except Exception as e:
            logger.error(f"Battery read failed: {e}")
            return {}
    
    def healthcheck(self) -> HealthStatus:
        """Run system health check."""
        issues = []
        recommendations = []
        zombie = False
        
        try:
            status = self.read_battery_status()
            soc = status.get('soc', 0)
            
            if soc < 10:
                issues.append(f"Low battery: {soc}%")
                recommendations.append("Consider charging")
            
            return HealthStatus(
                healthy=len(issues) == 0,
                message="; ".join(issues) if issues else "System healthy",
                recommendations=recommendations,
                zombie_state=zombie
            )
        except Exception as e:
            return HealthStatus(
                healthy=False,
                message=f"Health check failed: {e}",
                recommendations=["Check connection"],
                zombie_state=True
            )


class VirtualModeController:
    """Software-implemented battery modes using direct control."""
    
    def __init__(self, controller: FranklinWHController,
                 max_charge_soc: int = 100,
                 min_discharge_soc: Optional[int] = None,
                 soc_ramp_window: int = 10):
        self.ctrl = controller
        self.mode = VirtualMode.MANUAL
        self.max_charge_soc = max_charge_soc
        self.min_discharge_soc = min_discharge_soc or 20
        self.soc_ramp_window = soc_ramp_window
        self.target_soc = 95
        self.manual_power_w = 0
        self.running = False
        
    def set_mode(self, mode: VirtualMode, **kwargs):
        """Set operating mode with parameters."""
        self.mode = mode
        if 'target_soc' in kwargs:
            self.target_soc = kwargs['target_soc']
        if 'manual_power_w' in kwargs:
            self.manual_power_w = kwargs['manual_power_w']
        logger.info(f"Mode set to: {mode.value}")
    
    def calculate_power(self) -> float:
        """Calculate optimal power for current mode."""
        status = self.ctrl.read_battery_status()
        soc = status.get('soc', 50)
        
        if self.mode == VirtualMode.MANUAL:
            return self.manual_power_w
        
        elif self.mode == VirtualMode.SELF_CONSUMPTION:
            if soc < self.target_soc:
                return self.ctrl.RATED_MAX_CHARGE_W
            return 0
        
        elif self.mode == VirtualMode.EMERGENCY_BACKUP:
            if soc < self.target_soc:
                return self.ctrl.RATED_MAX_CHARGE_W
            return 0
        
        elif self.mode == VirtualMode.GRID_ZERO:
            return 0
        
        elif self.mode == VirtualMode.PEAK_SHAVE:
            return -self.ctrl.RATED_MAX_DISCHARGE_W
        
        return 0
    
    def execute_once(self) -> bool:
        """Execute single control cycle."""
        try:
            power = self.calculate_power()
            cmd = BatteryCommand(power_watts=power)
            success, msg = self.ctrl.send_command(cmd)
            return success
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return False
    
    def run_continuous(self, duration_seconds: Optional[int] = None,
                       interval: float = 5.0):
        """Run continuous control loop."""
        self.running = True
        start = time.time()
        
        try:
            while self.running:
                if not self.execute_once():
                    logger.warning("Control cycle failed")
                
                if duration_seconds and (time.time() - start) >= duration_seconds:
                    logger.info("Duration reached")
                    break
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Graceful shutdown - reset to idle."""
        self.running = False
        logger.info("Shutting down - releasing control")
        self.ctrl.reset_control_state()


# Module exports
__all__ = [
    'ControlMode',
    'VirtualMode',
    'BatteryCommand',
    'TOUSchedule',
    'FranklinWHController',
    'VirtualModeController',
    'HealthStatus',
]
