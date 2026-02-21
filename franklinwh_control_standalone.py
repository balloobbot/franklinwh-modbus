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
    power_watts: float  # Positive=discharge, negative=charge, 0=idle
    mode: ControlMode = ControlMode.LIMIT_ABS


@dataclass
class TOUSchedule:
    """Time-of-use rate periods for arbitrage.
    
    Supports both legacy hardcoded schedules and file-based configuration.
    File-based schedules provide more flexibility with custom periods,
    strategies, and constraint rules.
    """
    # Legacy fields (for backward compatibility)
    peak_hours: Tuple[int, int] = (16, 21)      # 4 PM - 9 PM
    shoulder_hours: Tuple[int, int] = (7, 16)    # 7 AM - 4 PM
    off_peak_hours: Tuple[int, int] = (21, 7)   # 9 PM - 7 AM
    
    peak_price: float = 0.50          # $/kWh
    shoulder_price: float = 0.25
    off_peak_price: float = 0.10
    
    # File-based schedule support
    _schedule_data: Optional[Dict] = field(default=None, repr=False)
    _source_file: Optional[str] = field(default=None, repr=False)
    
    @classmethod
    def from_file(cls, filepath: str) -> "TOUSchedule":
        """Load TOU schedule from JSON file.
        
        Args:
            filepath: Path to JSON schedule file
            
        Returns:
            TOUSchedule instance with loaded configuration
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file contains invalid JSON or schema
        """
        import json
        from pathlib import Path
        
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Schedule file not found: {filepath}")
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Validate basic schema
        cls._validate_schedule(data)
        
        # Create instance with schedule data
        instance = cls(_schedule_data=data, _source_file=str(path))
        
        # Try to populate legacy fields for compatibility
        instance._populate_legacy_fields(data)
        
        logger.info(f"Loaded TOU schedule from {filepath}: {data.get('name', 'unnamed')}")
        return instance
    
    @staticmethod
    def _validate_schedule(data: Dict) -> None:
        """Validate schedule file schema."""
        if not isinstance(data, dict):
            raise ValueError("Schedule must be a JSON object")
        
        if 'version' not in data:
            raise ValueError("Schedule must have 'version' field")
        
        if 'periods' not in data or not isinstance(data['periods'], list):
            raise ValueError("Schedule must have 'periods' array")
        
        if len(data['periods']) == 0:
            raise ValueError("Schedule must have at least one period")
        
        for i, period in enumerate(data['periods']):
            if 'id' not in period:
                raise ValueError(f"Period {i} missing 'id' field")
            if 'hours' not in period or not isinstance(period['hours'], list):
                raise ValueError(f"Period '{period.get('id', i)}' missing 'hours' array")
            if 'strategy' not in period:
                raise ValueError(f"Period '{period.get('id', i)}' missing 'strategy' field")
    
    def _populate_legacy_fields(self, data: Dict) -> None:
        """Try to populate legacy fields from schedule for backward compat."""
        # Look for known period types
        for period in data.get('periods', []):
            pid = period.get('id', '').lower()
            hours = period.get('hours', [])
            
            if 'peak' in pid and hours:
                self.peak_hours = (min(hours), max(hours) + 1)
                self.peak_price = period.get('price', self.peak_price)
            elif 'shoulder' in pid and hours:
                self.shoulder_hours = (min(hours), max(hours) + 1)
                self.shoulder_price = period.get('price', self.shoulder_price)
            elif 'off' in pid or 'valley' in pid and hours:
                self.off_peak_hours = (min(hours), max(hours) + 1)
                self.off_peak_price = period.get('price', self.off_peak_price)
    
    def is_file_based(self) -> bool:
        """Check if using file-based schedule."""
        return self._schedule_data is not None
    
    def get_schedule_name(self) -> str:
        """Get schedule name or 'Legacy' if using defaults."""
        if self._schedule_data:
            return self._schedule_data.get('name', 'Unnamed')
        return 'Legacy (hardcoded)'
    
    def get_current_period(self) -> str:
        """Determine current TOU period.
        
        Uses file-based schedule if loaded, otherwise legacy logic.
        """
        if self._schedule_data:
            hour = datetime.now().hour
            for period in self._schedule_data['periods']:
                if hour in period.get('hours', []):
                    return period['id']
            return "unknown"
        
        # Legacy logic
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
        if self._schedule_data:
            period_id = self.get_current_period()
            for period in self._schedule_data['periods']:
                if period['id'] == period_id:
                    return period.get('price', 0.25)
            return 0.25
        
        # Legacy logic
        period = self.get_current_period()
        return getattr(self, f"{period}_price", 0.25)
    
    def get_strategy(self) -> str:
        """Get battery strategy for current period.
        
        Returns:
            Strategy name: 'charge', 'discharge', 'self_consumption', 
                          'grid_zero', or 'standby'
        """
        if self._schedule_data:
            period_id = self.get_current_period()
            for period in self._schedule_data['periods']:
                if period['id'] == period_id:
                    return period.get('strategy', 'self_consumption')
        
        # Default strategy based on legacy period
        period = self.get_current_period()
        if period == 'peak':
            return 'discharge'
        elif period == 'off_peak':
            return 'charge'
        else:
            return 'self_consumption'
    
    def get_rules(self) -> Dict[str, Any]:
        """Get constraint rules from schedule."""
        if self._schedule_data:
            return self._schedule_data.get('rules', {})
        return {}
    
    def get_min_soc(self) -> int:
        """Get minimum SoC constraint."""
        return self.get_rules().get('min_soc', 10)
    
    def get_max_soc(self) -> int:
        """Get maximum SoC constraint."""
        return self.get_rules().get('max_soc', 95)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export schedule as dictionary."""
        if self._schedule_data:
            return self._schedule_data
        
        # Legacy format
        return {
            'version': '1.0 (legacy)',
            'name': 'Legacy Hardcoded',
            'periods': [
                {
                    'id': 'peak',
                    'name': 'Peak',
                    'hours': list(range(self.peak_hours[0], self.peak_hours[1])),
                    'price': self.peak_price,
                    'strategy': 'discharge'
                },
                {
                    'id': 'shoulder',
                    'name': 'Shoulder',
                    'hours': list(range(self.shoulder_hours[0], self.shoulder_hours[1])),
                    'price': self.shoulder_price,
                    'strategy': 'self_consumption'
                },
                {
                    'id': 'off_peak',
                    'name': 'Off-Peak',
                    'hours': list(range(self.off_peak_hours[0], 24)) + list(range(0, self.off_peak_hours[1])),
                    'price': self.off_peak_price,
                    'strategy': 'charge'
                }
            ]
        }
    
    def __str__(self) -> str:
        """String representation of schedule."""
        name = self.get_schedule_name()
        period = self.get_current_period()
        price = self.get_current_price()
        strategy = self.get_strategy()
        return f"{name} | Current: {period} (${price:.2f}/kWh) | Strategy: {strategy}"


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
    EXT_ONGRID_MODE = 15507      # 0=Backup, 1=TOU, 2=Self-Consumption, 3=Manual
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
            
            self.discover_ratings()  # Read actual device capabilities
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
        
        # 5. Grid safety — use Model 703 enter-service limits when available
        grid = self.read_grid_status()
        checks['grid_voltage'] = grid.get('voltage_v', 0)
        checks['grid_frequency'] = grid.get('frequency_hz', 0)

        # Read Model 703 (DER Enter Service) for configured grid limits
        m703 = self.get_model(703)
        if m703:
            try:
                m703.read()
                sf_v = self._get_scale_factor(m703, 'V_SF')
                sf_hz = self._get_scale_factor(m703, 'Hz_SF')
                # Voltage limits are in % of nominal (e.g. 253% → 253V on 230V grid)
                # but register holds the actual threshold voltage
                v_hi = m703.ESVHi.value * (10 ** sf_v) if m703.ESVHi.value is not None else 260
                v_lo = m703.ESVLo.value * (10 ** sf_v) if m703.ESVLo.value is not None else 220
                hz_hi = m703.ESHzHi.value * (10 ** sf_hz) if m703.ESHzHi.value is not None else 53
                hz_lo = m703.ESHzLo.value * (10 ** sf_hz) if m703.ESHzLo.value is not None else 47
                checks['enter_service'] = {
                    'available': True,
                    'permit': m703.ES.value if m703.ES.value is not None else None,
                    'v_hi': v_hi, 'v_lo': v_lo,
                    'hz_hi': hz_hi, 'hz_lo': hz_lo,
                }
            except Exception as e:
                logger.warning(f"Failed to read Model 703: {e}")
                v_hi, v_lo, hz_hi, hz_lo = 260, 220, 53, 47
                checks['enter_service'] = {'available': False}
        else:
            # Fallback: hardcoded defaults for systems without M703
            v_hi, v_lo, hz_hi, hz_lo = 260, 220, 53, 47
            checks['enter_service'] = {'available': False}

        checks['grid_safe'] = (
            v_lo < checks['grid_voltage'] < v_hi and
            hz_lo < checks['grid_frequency'] < hz_hi
        )
        
        if not checks['grid_safe']:
            recommendations.append(
                f"WARNING: Grid {checks['grid_voltage']:.1f}V / "
                f"{checks['grid_frequency']:.2f}Hz outside limits "
                f"(V: {v_lo}-{v_hi}, Hz: {hz_lo}-{hz_hi})"
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
            # Now handled by read_native_mode() using raw Modbus TCP
            result['readable'] = False
            result['note'] = 'Use read_native_mode() for native register access'
            
        except Exception as e:
            result['error'] = str(e)
        
        # Cache write capability (detect once)
        self._span_writable = result['writable']
        
        return result

    def read_native_mode(self) -> dict:
        """Read FranklinWH native operating mode via raw Modbus TCP.
        
        Registers 15507-15509 are outside the SunSpec address space and
        require a raw Modbus read (the sunspec2 API doesn't expose them).
        
        Returns dict with mode, reserves, or empty dict on failure.
        """
        FRANKLIN_MODES = {0: 'Emergency Backup', 1: 'Time of Use',
                          2: 'Self-Consumption', 3: 'Manual'}
        try:
            import struct
            client = self.dev.client
            # sunspec2 disconnects between operations — reconnect for raw access
            client.connect()
            sock = client.socket
            if not sock:
                return {}
            # Raw Modbus TCP: transaction=0, protocol=0, length=6,
            # unit_id, function=3 (read holding), start=15507, count=3
            req = struct.pack('>HHHBBHH', 0, 0, 6, self.unit_id, 3, 15507, 3)
            sock.sendall(req)
            resp = sock.recv(256)
            if len(resp) >= 15:
                vals = struct.unpack('>HHH', resp[9:15])
                return {
                    'mode_raw': vals[0],
                    'mode_name': FRANKLIN_MODES.get(vals[0], f'Unknown({vals[0]})'),
                    'self_reserve_pct': vals[1],
                    'tou_reserve_pct': vals[2],
                }
        except Exception as e:
            logger.debug(f"Native mode read failed: {e}")
        return {}
    
    def reset_control_state(self) -> bool:
        """
        Reset aGate to known clean state.
        
        Clears:
        - WSetEna (disable control)
        - WSetPct (zero percentage setpoint — the real control)
        - WSet (zero watt setpoint)
        
        NOTE: M715 registers (OpCtl, ControllerHb) reject writes on current firmware.
        NOTE: WSetRvrtTms is unimplemented per PICS SM-000028.
        
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
            logger.info(f"Before reset: WSetEna={m704.WSetEna.value}, WSetPct={m704.WSetPct.value}, WSet={m704.WSet.value}")
            
            # Disable control — only M704 registers are writable
            m704.WSetEna.value = 0
            m704.WSetPct.value = 0   # Primary control register
            m704.WSet.value = 0
            
            m704.write()
            time.sleep(0.5)
            
            # Verify
            m704.read()
            success = (m704.WSetEna.value == 0 and m704.WSetPct.value == 0)
            
            if success:
                logger.info(f"✓ Reset successful: WSetEna={m704.WSetEna.value}, WSetPct={m704.WSetPct.value}")
            else:
                logger.warning(f"Reset verification failed: WSetEna={m704.WSetEna.value}, WSetPct={m704.WSetPct.value}")
            
            return success
            
        except Exception as e:
            logger.error(f"Reset failed: {e}")
            return False
    
    # Default fallback — overridden by discover_ratings() on connect
    RATED_MAX_W = 5000
    RATED_MAX_CHARGE_W = 5000
    RATED_MAX_DISCHARGE_W = 5000

    def discover_ratings(self):
        """Read M702 nameplate ratings to replace hardcoded limits.

        Reads READ-ONLY rating registers (not RW settings which return None):
        - WMaxRtg (40227): Active Power Max Rating
        - WChaRteMaxRtg (40235): Charge Rate Max Rating
        - WDisChaRteMaxRtg (40236): Discharge Rate Max Rating

        Different FranklinWH models may have asymmetric charge/discharge ratings.
        """
        m702 = self.get_model(702)
        if not m702:
            logger.warning("Model 702 not found; using default 5000W ratings")
            return
        try:
            m702.read()
            sf = self._get_scale_factor(m702, 'W_SF')

            def read_rating(attr, default):
                pt = getattr(m702, attr, None)
                if pt is None or pt.value is None or pt.value == 0:
                    return default
                return int(pt.value * (10 ** sf))

            w_max = read_rating('WMaxRtg', 5000)
            w_cha = read_rating('WChaRteMaxRtg', w_max)
            w_dis = read_rating('WDisChaRteMaxRtg', w_max)

            self.RATED_MAX_W = w_max
            self.RATED_MAX_CHARGE_W = w_cha
            self.RATED_MAX_DISCHARGE_W = w_dis

            logger.info(f"Device ratings: Max={w_max}W, Charge={w_cha}W, Discharge={w_dis}W")
        except Exception as e:
            logger.warning(f"Failed to read M702 ratings: {e}; using defaults")

    def _validate_power(self, power_watts: float) -> float:
        """Safety clamp: ensure requested power doesn't exceed device ratings."""
        is_charge = power_watts < 0
        limit = self.RATED_MAX_CHARGE_W if is_charge else self.RATED_MAX_DISCHARGE_W
        if abs(power_watts) > limit:
            clamped = limit if power_watts > 0 else -limit
            logger.warning(f"SAFETY CLAMP: {power_watts}W exceeds {'charge' if is_charge else 'discharge'} "
                          f"limit {limit}W — clamped to {clamped}W")
            return clamped
        return power_watts

    def send_command(
        self,
        command: BatteryCommand,
        revert_time_s: int = 0,
        heartbeat_interval: float = 5.0,
        dry_run: bool = False
    ) -> Tuple[bool, str]:
        """
        Send battery control command.

        FranklinWH Systematic Test Results (2026-02-18):
        - WSetPct is the ONLY working control register (WSet accepted but ignored)
        - Positive WSetPct = discharge, Negative = charge
        - Scale factor WSetPct_SF = -1, so raw 300 = 30.0% of 5kW = 1500W
        - M715 registers (ControllerHb, OpCtl) reject all writes (LocRemCtl=LOCAL)
        - M702 rate limits (WChaRteMax etc.) unimplemented (return None)
        - WSetRvrtTms unimplemented per PICS SM-000028 — no auto-timeout
        - WMaxLimPctEna/WMaxLimPct PICS says supported, firmware rejects writes
        """
        m704 = self.get_model(704)
        m715 = self.get_model(715)
        if not m704:
            return False, "Model 704 not available"

        # Safety clamp against device ratings
        safe_watts = self._validate_power(command.power_watts)

        # Calculate WSetPct: percentage of rated max
        pct_sf = self._get_scale_factor(m704, 'WSetPct_SF')
        pct_raw = int((safe_watts / self.RATED_MAX_W) * 100 / (10 ** pct_sf))

        if dry_run:
            return True, f"Dry Run: WSetPct={pct_raw} ({command.power_watts}W)"

        # 1. STOP & CLEAR (Pre-flight reset)
        m704.read()
        m704.WSetEna.value = 0
        m704.write()
        time.sleep(0.3)

        # 2. CONFIGURE — WSetPct is the primary control for FranklinWH
        m704.read()
        m704.WSetMod.value = 0  # Absolute W mode
        m704.WSetPct.value = pct_raw
        # Also set WSet for readback/logging (aGate ignores it for power control)
        wset_sf = self._get_scale_factor(m704, 'WSet_SF')
        m704.WSet.value = int(command.power_watts / (10 ** wset_sf))
        # NOTE: WSetRvrtTms is unimplemented per PICS SM-000028.
        # Commands persist until explicitly disabled with WSetEna=0.
        m704.write()
        time.sleep(0.3)

        # 3. ENABLE
        m704.read()
        m704.WSetEna.value = 1
        m704.write()
        time.sleep(0.5)

        # 4. VERIFY
        m704.read()
        actual_pct = m704.WSetPct.value * (10 ** pct_sf) if m704.WSetPct.value else 0
        logger.info(f"Command sent: WSetPct={actual_pct}% (raw={m704.WSetPct.value}), "
                   f"WSet={m704.WSet.value}, WSetEna={m704.WSetEna.value}")
        return True, f"Command Sent: {command.power_watts}W ({actual_pct}% of {self.RATED_MAX_W}W)"


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
    
    def __init__(self, franklinwh_controller: FranklinWHController,
                 max_charge_soc: int = 100,
                 min_discharge_soc: Optional[int] = None,
                 soc_ramp_window: int = 10,
                 force_soc_limits: bool = False):
        """
        Initialize virtual mode controller.
        
        Args:
            franklinwh_controller: Connected FranklinWHController instance
            max_charge_soc: Maximum SoC for charging (with ramping)
            min_discharge_soc: Minimum SoC for discharging (with ramping).
                             If None, reads from aGate native mode.
            soc_ramp_window: SoC percentage for ramping before hard limit
            force_soc_limits: If True, allows override of SoC limits (logged warning)
        """
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
        
        # SoC limit parameters
        self.max_charge_soc = max_charge_soc
        self.soc_ramp_window = soc_ramp_window
        self.force_soc_limits = force_soc_limits
        
        # Read min discharge from aGate if not specified
        if min_discharge_soc is None:
            self.min_discharge_soc = self._read_agate_reserve_soc()
        else:
            # Validate against aGate reserve (cannot go below)
            agate_reserve = self._read_agate_reserve_soc()
            if min_discharge_soc < agate_reserve:
                logger.warning(f"Requested min-discharge-soc {min_discharge_soc}% is below "
                              f"aGate reserve {agate_reserve}%. Using {agate_reserve}%.")
                self.min_discharge_soc = agate_reserve
            else:
                self.min_discharge_soc = min_discharge_soc
        
        logger.info(f"SoC limits configured: min_discharge={self.min_discharge_soc}%, "
                   f"max_charge={self.max_charge_soc}%, ramp_window={self.soc_ramp_window}%")
        if self.force_soc_limits:
            logger.warning("FORCE MODE ENABLED: SoC limits can be overridden (use with caution)")
        
        # State for tick() method
        self.last_tick = 0
        self.tick_interval = 5  # seconds
        
        # Shutdown flag
        self._shutdown_requested = False
        
        # Register cleanup handler
        atexit.register(self._emergency_idle)
    
    def _read_agate_reserve_soc(self) -> int:
        """Read reserve SOC from aGate native mode registers.
        
        Returns:
            Reserve SOC percentage (defaults to 10 if cannot read)
        """
        try:
            native = self.ctrl.read_native_mode()
            if native:
                # TOU reserve (15509) or Self reserve (15508)
                # Use the higher of the two for safety
                tou_reserve = native.get('tou_reserve_pct', 10)
                self_reserve = native.get('self_reserve_pct', 10)
                reserve = max(tou_reserve, self_reserve)
                logger.info(f"Read aGate reserve SOC: {reserve}% (TOU={tou_reserve}%, Self={self_reserve}%)")
                return reserve
        except Exception as e:
            logger.warning(f"Could not read aGate reserve SOC: {e}, using default 10%")
        return 10  # Safe default
    
    def _emergency_idle(self):
        """Ensure battery control is fully released on unexpected exit.
        
        CRITICAL: Must set WSetEna=0 (not just WSetPct=0) so the aGate
        resumes its configured operating mode (e.g. Self-Consumption).
        WSetEna=1 + WSetPct=0 = 'actively commanding standby' = VPP mode.
        """
        if hasattr(self.ctrl, 'reset_control_state'):
            try:
                logger.warning("Emergency shutdown: releasing Modbus control (WSetEna=0)")
                self.ctrl.reset_control_state()
            except Exception as e:
                logger.error(f"Emergency reset failed: {e}")
    
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
        
        Uses actual device ratings from M702 nameplate.
        """
        # Get actual device ratings (not hardcoded)
        max_charge = self.ctrl.RATED_MAX_CHARGE_W
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W
        
        excess_solar = solar - home
        
        # High SOC - prioritize using battery
        if soc > (100 - self.self_reserve_pct):
            if excess_solar > 0:
                # Still charging but gently
                return min(excess_solar * 0.5, max_charge * 0.2)  # 20% of max
            else:
                # Discharge to cover deficit
                return max(home - solar, -max_discharge)
        
        # Low SOC - aggressive charging if excess solar
        if excess_solar > 0:
            return min(excess_solar, max_charge)  # Up to rated max
        
        # No excess solar, discharge if needed
        if home > solar and soc > 10:
            return max(solar - home, -max_discharge)
        
        return 0
    
    def _calc_emergency_backup(self, solar: float, home: float,
                                grid: float, soc: float) -> float:
        """
        Keep battery as full as possible for outage protection.
        
        Strategy:
        - Charge from any available source (solar + grid)
        - Only discharge if absolutely necessary
        - Target 95% SOC
        
        Uses actual device ratings from M702 nameplate.
        """
        max_charge = self.ctrl.RATED_MAX_CHARGE_W
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W
        
        if soc >= self.backup_target_soc:
            # Full enough, minimal activity
            if home > solar:
                # Small discharge to help (10% of max)
                return max(solar - home, -max_discharge * 0.1)
            return 0
        
        # Need to charge
        # Estimate energy needed (rough calc using rated capacity)
        rated_wh = self.ctrl.RATED_MAX_W * 2.72  # ~13.6kWh for 5kW rated
        charge_needed = (self.backup_target_soc - soc) / 100 * rated_wh
        hours_to_charge = 2  # Target 2 hours to full
        target_watts = min(charge_needed / hours_to_charge, max_charge)
        
        # Use solar first, then grid if needed
        if solar > home:
            # Excess solar available
            return min(solar - home, target_watts)
        else:
            # Charge from grid + solar
            return min(target_watts, max_charge)
    
    def _calc_time_of_use(self, solar: float, home: float,
                          grid: float, soc: float) -> float:
        """
        Arbitrage grid prices: charge cheap, discharge expensive.
        
        Uses TOU schedule strategy if file-based schedule loaded,
        otherwise falls back to hardcoded logic.
        
        Strategies:
        - charge: Maximize charging (off-peak)
        - discharge: Maximize discharging (peak)
        - self_consumption: Normal solar self-use (shoulder)
        - grid_zero: Minimize grid import/export
        - standby: Let aGate manage itself
        
        Uses actual device ratings from M702 nameplate.
        """
        # Get actual device ratings
        max_charge = self.ctrl.RATED_MAX_CHARGE_W
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W
        
        # Get strategy from schedule (file-based or legacy)
        strategy = self.tou.get_strategy()
        min_soc = self.tou.get_min_soc()
        max_soc = self.tou.get_max_soc()
        
        if strategy == "charge":
            # Cheap power - charge if not full
            if soc < max_soc - 5:  # 5% buffer
                # Use excess solar first, then grid
                if solar > home:
                    # Charge excess solar + some from grid (60% of max)
                    return min(solar - home + max_charge * 0.6, max_charge)
                else:
                    return max_charge  # Max charge from grid
            return 0
            
        elif strategy == "discharge":
            # Expensive power - discharge to cover load
            if soc > min_soc + 5:  # 5% buffer
                # Cover home load from battery
                return max(min(home - solar, max_discharge), -max_discharge)
            return 0
            
        elif strategy == "grid_zero":
            # Minimize grid interaction
            return self._calc_grid_zero(solar, home, grid, soc)
            
        elif strategy == "solar_priority":
            # Priority: Charge battery from solar first, home loads from grid
            # This is useful when you want to maximize battery storage
            # for later use (e.g., before peak pricing period)
            if soc < max_soc - 5:  # If not near full
                if solar > 0:
                    # Use all solar for charging, home takes from grid
                    return min(solar, max_charge)
            # Otherwise normal self-consumption
            return self._calc_self_consumption(solar, home, grid, soc)
            
        elif strategy == "standby":
            # Let aGate manage itself
            return 0
            
        else:  # self_consumption or unknown
            # Normal self-consumption
            return self._calc_self_consumption(solar, home, grid, soc)
    
    def _calc_grid_zero(self, solar: float, home: float,
                        grid: float, soc: float) -> float:
        """
        Minimize grid interaction (island mode simulation).
        
        Strategy:
        - Target zero grid import/export
        - Battery buffers all imbalances
        
        Uses actual device ratings from M702 nameplate.
        """
        max_charge = self.ctrl.RATED_MAX_CHARGE_W
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W
        
        target_grid = 0
        current_grid = grid  # Positive = importing
        
        # Calculate battery power to achieve zero grid
        # If importing 500W, discharge 500W
        # If exporting 500W, charge 500W
        power = -current_grid
        
        # Add buffer for stability
        if abs(power) < self.grid_zero_buffer:
            power = 0
            
        # Limit to actual battery capabilities
        return max(min(power, max_charge), -max_discharge)
    
    def _calc_peak_shave(self, solar: float, home: float,
                         grid: float, soc: float) -> float:
        """
        Discharge during high home demand to reduce peak grid draw.
        
        Strategy:
        - Monitor home load
        - Discharge if load exceeds threshold
        - Charge during low demand
        
        Uses actual device ratings from M702 nameplate.
        """
        max_charge = self.ctrl.RATED_MAX_CHARGE_W
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W
        
        if home > self.peak_shave_threshold and soc > 30:
            # High demand - discharge to help
            discharge = min(home - solar, max_discharge)
            return -discharge
        
        elif home < 500 and soc < 80:
            # Low demand - charge if solar available (60% of max)
            if solar > home:
                return min(solar - home, max_charge * 0.6)
        
        return 0
    
    def _calc_manual(self, solar: float, home: float,
                     grid: float, soc: float) -> float:
        """Direct manual control."""
        return self.manual_power_w
    
    def _apply_safety_limits(self, power: float, soc: float) -> float:
        """Apply safety limits based on SOC.
        
        Implements soft limits with ramping:
        - Hard limits at absolute boundaries (0%, 100%)
        - Configurable limits with ramping window
        - Emergency override available (--force)
        """
        # Absolute hard limits (never override)
        if soc >= 99.5 and power > 0:
            logger.warning(f"SoC {soc:.1f}% at absolute maximum - blocking all charge")
            return 0
        
        if soc <= 0.5 and power < 0:
            logger.warning(f"SoC {soc:.1f}% at absolute minimum - blocking all discharge")
            return 0
        
        # Get limit parameters
        max_charge_soc = getattr(self, 'max_charge_soc', 100)
        min_discharge_soc = getattr(self, 'min_discharge_soc', 5)
        ramp_window = getattr(self, 'soc_ramp_window', 10)
        force_override = getattr(self, 'force_soc_limits', False)
        
        # Apply max charge limit with ramping
        if power > 0 and soc >= (max_charge_soc - ramp_window):
            if soc >= max_charge_soc:
                # Hard stop at limit
                if not force_override:
                    logger.info(f"SoC {soc:.1f}% at max charge limit ({max_charge_soc}%) - blocking charge")
                    return 0
                else:
                    logger.warning(f"FORCE OVERRIDE: SoC {soc:.1f}% exceeds max ({max_charge_soc}%) but charging anyway")
            else:
                # Ramping zone
                ramp_progress = (soc - (max_charge_soc - ramp_window)) / ramp_window
                ramp_factor = 1.0 - ramp_progress  # 1.0 at start, 0.0 at limit
                ramped_power = power * max(ramp_factor, 0.05)  # Minimum 5% power
                
                if ramp_factor < 0.9:  # Log when significantly ramped
                    logger.info(f"SoC {soc:.1f}% approaching max ({max_charge_soc}%) - "
                               f"ramping charge: {power:.0f}W → {ramped_power:.0f}W "
                               f"({ramp_factor*100:.0f}%)")
                power = ramped_power
        
        # Apply min discharge limit with ramping
        if power < 0 and soc <= (min_discharge_soc + ramp_window):
            if soc <= min_discharge_soc:
                # Hard stop at limit
                if not force_override:
                    logger.info(f"SoC {soc:.1f}% at min discharge limit ({min_discharge_soc}%) - blocking discharge")
                    return 0
                else:
                    logger.warning(f"FORCE OVERRIDE: SoC {soc:.1f}% below min ({min_discharge_soc}%) but discharging anyway")
            else:
                # Ramping zone
                ramp_progress = ((min_discharge_soc + ramp_window) - soc) / ramp_window
                ramp_factor = 1.0 - ramp_progress  # 1.0 at start, 0.0 at limit
                ramped_power = power * max(ramp_factor, 0.05)  # Minimum 5% power (negative)
                
                if ramp_factor < 0.9:  # Log when significantly ramped
                    logger.info(f"SoC {soc:.1f}% approaching min ({min_discharge_soc}%) - "
                               f"ramping discharge: {power:.0f}W → {ramped_power:.0f}W "
                               f"({ramp_factor*100:.0f}%)")
                power = ramped_power
        
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
    
    def _format_duration(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _get_target_soc_display(self) -> str:
        """Get target SoC display based on current mode."""
        if self.mode == VirtualMode.EMERGENCY_BACKUP:
            return f"{self.backup_target_soc}%"
        elif self.mode == VirtualMode.SELF_CONSUMPTION:
            return f"{self.self_reserve_pct}% reserve"
        elif self.mode == VirtualMode.TIME_OF_USE:
            # Show schedule info
            if self.tou.is_file_based():
                period = self.tou.get_current_period()
                strategy = self.tou.get_strategy()
                price = self.tou.get_current_price()
                return f"{period} (${price:.2f}) → {strategy}"
            else:
                return "Legacy schedule"
        else:
            return "N/A"
    
    def _print_telemetry(self, status: Dict, start_time: float, duration_seconds: Optional[float] = None):
        """Print formatted telemetry to console."""
        now = time.time()
        elapsed = now - start_time
        remaining = duration_seconds - elapsed if duration_seconds else None
        
        battery = status.get('battery', {})
        grid = status.get('grid', {})
        solar = status.get('solar', {})
        derived = status.get('derived', {})
        control = status.get('control', {})
        
        soc = battery.get('soc', 0)
        battery_power = control.get('wset_watts', 0)
        solar_power = solar.get('dc_power_w', 0)
        grid_power = grid.get('grid_power_w', 0)
        home_load = derived.get('home_load_w', 0)
        
        # Read aGate native mode (OnGridMode and reserves)
        native_mode = self.ctrl.read_native_mode() or {}
        ongrid_mode = native_mode.get('mode_raw', -1)
        ongrid_name = native_mode.get('mode_name', 'Unknown')
        self_reserve = native_mode.get('self_reserve_pct', -1)
        tou_reserve = native_mode.get('tou_reserve_pct', -1)
        
        # Determine which reserve is active based on OnGridMode
        # 0=Backup (no reserve shown), 1=Self, 2=TOU, 3=Manual
        active_reserve = "N/A"
        if ongrid_mode == 1:
            active_reserve = f"{self_reserve}% (Self)"
        elif ongrid_mode == 2:
            active_reserve = f"{tou_reserve}% (TOU)"
        
        # Detect potential Cloud API activity
        # If OnGridMode is not Manual and battery is active, Cloud might be controlling
        wset_ena = control.get('wset_ena', 0)
        dc_power = battery.get('dc_power_w', 0)  # Actual battery DC power
        cloud_active_warning = ""
        
        # Check for activity not from our Modbus control
        if ongrid_mode != 3:  # Not in Manual mode
            if abs(dc_power) > 100:  # Battery is actively charging/discharging
                cloud_active_warning = f" ⚠️  CLOUD ACTIVE (OnGridMode={ongrid_name})"
        
        # Battery state icon (use actual DC power for truth)
        if dc_power < -50:
            bat_icon = "⚡ CHARGING"
            bat_detail = f"{abs(dc_power):.0f}W"
        elif dc_power > 50:
            bat_icon = "🔋 DISCHARGING"
            bat_detail = f"{dc_power:.0f}W"
        else:
            bat_icon = "💤 IDLE"
            bat_detail = "0W"
        
        # Grid state
        if grid_power > 50:
            grid_icon = "↓ IMPORTING"
            grid_detail = f"{grid_power:.0f}W"
        elif grid_power < -50:
            grid_icon = "↑ EXPORTING"
            grid_detail = f"{abs(grid_power):.0f}W"
        else:
            grid_icon = "─ BALANCED"
            grid_detail = f"{grid_power:.0f}W"
        
        # Clear screen (optional, for cleaner output)
        # print("\033[2J\033[H", end="")  # Uncomment for terminal clear
        
        print("\n" + "=" * 70)
        print(f"  MODE: {self.mode.value.upper()}{cloud_active_warning}")
        print(f"  {'─' * 66}")
        print(f"  ⏱️  ELAPSED: {self._format_duration(elapsed)}" + 
              (f"  |  ⏳ REMAINING: {self._format_duration(remaining)}" if remaining is not None else ""))
        print(f"  🎯 TARGET:   {self._get_target_soc_display()}")
        print(f"  aGATE:      OnGridMode={ongrid_name} ({ongrid_mode}) | Reserve: {active_reserve}")
        print(f"  {'─' * 66}")
        print(f"  BATTERY:    {bat_icon:15s} {bat_detail:>10s}  |  SoC: {soc:.1f}%")
        print(f"  MODBUS:     WSetEna={wset_ena} | Command: {battery_power:.0f}W")
        print(f"  SOLAR PV:   {'☀️  PRODUCING':15s} {solar_power:>10.0f}W  |  ")
        print(f"  HOME LOAD:  {'🏠 CONSUMING':15s} {home_load:>10.0f}W  |  ")
        print(f"  GRID:       {grid_icon:15s} {grid_detail:>10s}")
        print(f"  {'─' * 66}")
        # SoC limit status
        limit_status = ""
        ramp_pct = 100.0
        if battery_power > 0 and soc >= (self.max_charge_soc - self.soc_ramp_window):
            if soc >= self.max_charge_soc:
                limit_status = " 🔒 MAX LIMIT"
            else:
                ramp_pct = (self.max_charge_soc - soc) / self.soc_ramp_window * 100
                limit_status = f" ↓ RAMPING ({ramp_pct:.0f}%)"
        elif battery_power < 0 and soc <= (self.min_discharge_soc + self.soc_ramp_window):
            if soc <= self.min_discharge_soc:
                limit_status = " 🔒 MIN LIMIT"
            else:
                ramp_pct = (soc - self.min_discharge_soc) / self.soc_ramp_window * 100
                limit_status = f" ↓ RAMPING ({ramp_pct:.0f}%)"
        
        if self.force_soc_limits and (soc >= self.max_charge_soc or soc <= self.min_discharge_soc):
            limit_status += " [FORCE]"
        
        print(f"  CMD: WSetPct={control.get('wset_pct', 0):.1f}%  ({battery_power:.0f}W){limit_status}")
        print(f"  LIMITS: Discharge≥{self.min_discharge_soc}% Charge≤{self.max_charge_soc}% (window:{self.soc_ramp_window}%)")
        print("=" * 70)

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
        last_console_output = 0
        
        # Print initial header
        print("\n" + "=" * 70)
        print(f"  STARTING: {self.mode.value} mode")
        if duration_seconds:
            print(f"  DURATION: {self._format_duration(duration_seconds)}")
        print(f"  Press Ctrl+C to stop")
        print("=" * 70)
        
        try:
            while not self._shutdown_requested:
                # Execute control tick
                self.tick()
                
                now = time.time()
                
                # Console telemetry output (every 5 seconds for visibility)
                if now - last_console_output >= 5:
                    status = self.read_status()
                    self._print_telemetry(status, start, duration_seconds)
                    last_console_output = now
                
                # Periodic status logging (every 60 seconds to file)
                if now - last_status_log >= 60:
                    status = self.read_status()
                    battery = status.get('battery', {})
                    grid = status.get('grid', {})
                    logger.info(f"Status: SOC={battery.get('soc', 0):.1f}%, "
                               f"Grid={grid.get('grid_power_w', 0):.0f}W, "
                               f"Mode={self.mode.value}")
                    last_status_log = now
                
                # Small sleep to prevent busy-wait
                time.sleep(0.1)
                
                # Check duration limit
                if duration_seconds and (now - start) > duration_seconds:
                    print("\n✓ Duration expired, stopping...")
                    break
                    
        except Exception as e:
            logger.error(f"Runtime error: {e}")
        finally:
            # Safe shutdown — MUST set WSetEna=0 to release Modbus control.
            # Without this, aGate stays in VPP standby instead of resuming
            # its configured mode (e.g. Self-Consumption).
            print("\n" + "=" * 70)
            print("  SHUTTING DOWN: Releasing Modbus control (WSetEna=0)")
            print("=" * 70)
            try:
                self.ctrl.reset_control_state()
                print("✓ Control released - aGate will resume configured mode")
            except Exception as e:
                logger.error(f"Shutdown reset failed: {e}")
                print(f"✗ Error releasing control: {e}")

    def read_all_alarms(client):
        """Read all alarm sources from FranklinWH aGate"""
        alarms = {
            'system': client.read_holding_registers(40076, 2),      # Model 701 Alrm
            'solar': client.read_holding_registers(41104, 2),       # Model 502 Evt
            'dc_port': client.read_holding_registers(41044, 2),     # Model 714 PrtAlrms
            'battery_status': client.read_holding_registers(41039, 1),  # Model 713 Sta
            'vendor_info': client.read_string(40193, 16),           # Model 701 MnAlrmInfo
        }
        return alarms

    def check_critical_alarms(alarms):
        """Determine if safe to operate"""
        system_alrm = (alarms['system'][1] << 16) | alarms['system'][0]
        dc_alrm = (alarms['dc_port'][1] << 16) | alarms['dc_port'][0]
        battery_sta = alarms['battery_status'][0]
        
        # Critical faults that block operation
        CRITICAL_BITS = (1 << 0) | (1 << 6) | (1 << 7) | (1 << 13) | (1 << 14)  # GROUND, CABINET_OPEN, MANUAL_SHUTDOWN, STRING_FAULT, ARC_FAULT
        
        if system_alrm & CRITICAL_BITS:
            return False, f"Critical system alarm: 0x{system_alrm:08X}"
        
        if dc_alrm & 0x3F:  # Any DC port electrical fault
            return False, f"DC port alarm: 0x{dc_alrm:08X}"
        
        if battery_sta == 6:  # FAULT
            return False, "Battery status: FAULT"
        
        return True, "System healthy"

    def reset_alarms_if_cleared(client):
        """Write to Model 715 AlarmReset after fault conditions resolved"""
        # First verify no active alarms
        alarms = read_all_alarms(client)
        safe, msg = check_critical_alarms(alarms)
        
        if safe:
            client.write_register(41094, 1)  # Write 1 to AlarmReset
            time.sleep(0.5)
            client.write_register(41094, 0)  # Clear reset bit
            return True
        else:
            return False, f"Cannot reset: {msg}"

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
  
  # Quick stop — release Modbus control, resume Self-Consumption
  %(prog)s -i 192.168.0.110 --stop
  
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
    parser.add_argument('-i', '--ip', 
                       help='aGate IP address (required for most operations)')
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
    parser.add_argument('--stop', action='store_true',
                       help='Release Modbus control (WSetEna=0) and exit. '
                            'Use this to resume normal aGate operation (e.g. Self-Consumption)')
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
    
    # SoC Limits (with ramping)
    parser.add_argument('--max-charge-soc', type=int, default=100,
                       help='Maximum SoC for charging with ramping (default: 100)')
    parser.add_argument('--min-discharge-soc', type=int, default=None,
                       help='Minimum SoC for discharging with ramping '
                            '(default: read from aGate reserve)')
    parser.add_argument('--soc-ramp-window', type=int, default=10,
                       help='SoC ramping window in percent (default: 10)')
    parser.add_argument('--force', action='store_true',
                       help='Force operation even if SoC limits would prevent it '
                            '(logged warning, use with caution)')
    
    # TOU Schedule file support
    parser.add_argument('--schedule-file', type=str, metavar='FILE',
                       help='TOU schedule JSON file (for time_of_use mode). '
                            'See schedules/ directory for examples.')
    parser.add_argument('--show-schedule', type=str, metavar='FILE',
                       help='Display schedule file contents and exit')
    parser.add_argument('--validate-schedule', type=str, metavar='FILE',
                       help='Validate schedule file and exit')
    
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


def print_system_status(ctrl):
    """Print comprehensive system status with clear operational state."""

    # SunSpec enum lookups
    OPERATING_STATE = {0: 'Off', 1: 'Operating', 2: 'Standby', 3: 'Fault',
                       4: 'Shutting Down', 5: 'Starting', 6: 'Maintenance'}
    INVERTER_STATE = {0: 'Off', 1: 'Sleeping', 2: 'Starting', 3: 'Running',
                      4: 'Throttled', 5: 'Shutting Down', 6: 'Fault',
                      7: 'Standby', 8: 'Test', 9: 'Manufacturing'}
    CONN_STATE = {0: 'Disconnected', 1: 'Connected'}
    DER_SOURCE = {0: 'PV', 1: 'Battery', 2: 'Hybrid', 3: 'Charger',
                  4: 'STATCOM', 5: 'Load', 6: 'Generator'}
    LOC_REM = {0: 'Remote', 1: 'Local'}

    print("\n" + "=" * 60)
    print("  FranklinWH aGate System Status")
    print("=" * 60)

    # --- Read all models ---
    m701 = ctrl.get_model(701)
    m703 = ctrl.get_model(703)
    m704 = ctrl.get_model(704)
    m713 = ctrl.get_model(713)
    m714 = ctrl.get_model(714)
    m715 = ctrl.get_model(715)

    if m701: m701.read()
    if m703: m703.read()
    if m704: m704.read()
    if m713: m713.read()
    if m714: m714.read()
    if m715: m715.read()

    # --- FranklinWH Operating Mode (native registers) ---
    native = ctrl.read_native_mode()
    if native:
        print(f"\n  FranklinWH Operating Mode")
        print(f"  {'─' * 40}")
        print(f"  Mode:              {native['mode_name']}")
        print(f"  Self Reserve:      {native['self_reserve_pct']}%")
        print(f"  TOU Reserve:       {native['tou_reserve_pct']}%")

    # --- Inverter & Grid ---
    if m701:
        sf_w = ctrl._get_scale_factor(m701, 'W_SF')
        sf_v = ctrl._get_scale_factor(m701, 'V_SF')
        sf_hz = ctrl._get_scale_factor(m701, 'Hz_SF')
        sf_tmp = ctrl._get_scale_factor(m701, 'Tmp_SF')

        st = m701.St.value if m701.St.value is not None else -1
        inv_st = m701.InvSt.value if m701.InvSt.value is not None else -1
        conn_st = m701.ConnSt.value if m701.ConnSt.value is not None else -1
        der_mode_raw = m701.DERMode.value if m701.DERMode.value is not None else 0
        ac_power_w = m701.W.value * (10 ** sf_w) if m701.W.value is not None else 0
        voltage = m701.LNV.value * (10 ** sf_v) if m701.LNV.value is not None else 0
        freq = m701.Hz.value * (10 ** sf_hz) if m701.Hz.value is not None else 0
        alrm = m701.Alrm.value if m701.Alrm.value is not None else 0
        tmp_cab = m701.TmpCab.value * (10 ** sf_tmp) if m701.TmpCab.value is not None else None
        tmp_amb = m701.TmpAmb.value * (10 ** sf_tmp) if m701.TmpAmb.value is not None else None

        # Decode DERMode bitfield (NOT a simple enum!)
        # Lower bits (0-6): Source type flags
        # Upper bits (16+): Grid mode flags (FranklinWH may not populate these)
        der_sources = [name for bit, name in DER_SOURCE.items() if der_mode_raw & (1 << bit)]

        # FranklinWH product line:
        #   aGate X (AU/US): AC-coupled — PV via AC solar inputs (2x 63A)
        #   aPower S (US):   DC-coupled — PV via 4x MPPT (built-in hybrid inverter)
        # Firmware only reports bit 0 (PV) in DERMode, missing bit 1 (Battery).
        # We correct this to reflect the actual hybrid PV+Battery hardware.
        if der_sources == ['PV']:
            der_source_str = 'PV+Battery (Hybrid Inverter)'
        elif der_sources:
            der_source_str = '+'.join(der_sources)
        else:
            der_source_str = 'Unknown'

        # Grid mode from upper bits (16-17) — FranklinWH firmware does not
        # populate these bits, so we interpret absence as grid-following
        # (the default operating mode for residential battery inverters)
        if der_mode_raw & (1 << 17):
            grid_mode_str = 'Grid Forming'
        elif der_mode_raw & (1 << 16):
            grid_mode_str = 'Grid Following'
        else:
            grid_mode_str = 'Grid Following (default)'

        print(f"\n  Inverter & Grid")
        print(f"  {'─' * 40}")
        print(f"  Operating State:   {OPERATING_STATE.get(st, f'Unknown({st})')}")
        print(f"  Inverter State:    {INVERTER_STATE.get(inv_st, f'Unknown({inv_st})')}")
        print(f"  Grid Connection:   {CONN_STATE.get(conn_st, f'Unknown({conn_st})')}")
        print(f"  DER Type:          {der_source_str}")
        print(f"  DER Grid Mode:     {grid_mode_str}")
        print(f"  DERMode Raw:       0x{der_mode_raw:08X} ({der_mode_raw})")

        print(f"  Grid Voltage:      {voltage:.1f} V")
        print(f"  Grid Frequency:    {freq:.2f} Hz")
        if tmp_cab:
            print(f"  Cabinet Temp:      {tmp_cab:.1f} °C")
        if tmp_amb:
            print(f"  Ambient Temp:      {tmp_amb:.1f} °C")
        if alrm:
            # Decode alarm bitfield
            ALARM_BITS = {
                0: 'GROUND_FAULT', 2: 'DC_OVER_VOLTAGE', 3: 'AC_DISCONNECT',
                5: 'GRID_DISCONNECT', 7: 'MANUAL_SHUTDOWN', 8: 'OVER_TEMP',
                9: 'VOLT_OUT_OF_RANGE', 10: 'FREQ_OUT_OF_RANGE',
                12: 'HW_FAILURE', 13: 'MANUFACTURER_ALARM'
            }
            active = [name for bit, name in ALARM_BITS.items() if alrm & (1 << bit)]
            print(f"  ⚠ Alarms:          0x{alrm:08X}")
            for a in active:
                print(f"                     → {a}")
        else:
            print(f"  Alarms:            None ✓")

    # --- Battery ---
    if m713:
        sf_pct = ctrl._get_scale_factor(m713, 'Pct_SF')
        sf_wh = ctrl._get_scale_factor(m713, 'WH_SF')
        soc = m713.SoC.value * (10 ** sf_pct) if m713.SoC.value is not None else 0
        soh = m713.SoH.value * (10 ** sf_pct) if m713.SoH.value is not None else 0
        wh_rtg = m713.WHRtg.value * (10 ** sf_wh) if m713.WHRtg.value is not None else 0
        wh_avail = m713.WHAvail.value * (10 ** sf_wh) if m713.WHAvail.value is not None else 0

        # Derive actual state from DC power (M713.Sta always reports IDLE)
        dc_w = 0
        if m714 and m714.DCW.value is not None:
            sf_dcw = ctrl._get_scale_factor(m714, 'DCW_SF')
            dc_w = m714.DCW.value * (10 ** sf_dcw)

        if dc_w < -50:
            bat_state = f"⚡ Charging ({abs(dc_w):.0f}W)"
            bat_icon = "↓"
        elif dc_w > 50:
            bat_state = f"🔋 Discharging ({dc_w:.0f}W)"
            bat_icon = "↑"
        else:
            bat_state = "💤 Idle"
            bat_icon = "─"

        # SOC bar
        bar_len = 20
        filled = int(soc / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        print(f"\n  Battery")
        print(f"  {'─' * 40}")
        print(f"  State:             {bat_state}")
        print(f"  SoC:               {soc:.1f}%  [{bar}]")
        print(f"  SoH:               {soh:.1f}%")
        print(f"  Energy Available:  {wh_avail/1000:.1f} / {wh_rtg/1000:.1f} kWh")
        print(f"  DC Power:          {dc_w:.0f} W  {bat_icon}")
        print(f"  Note:              M713.Sta always reports IDLE (firmware bug)")

    # --- Power Flow ---
    if m701 and m714:
        grid_w = m701.W.value * (10 ** sf_w) if m701.W.value is not None else 0

        print(f"\n  Power Flow")
        print(f"  {'─' * 40}")
        print(f"  AC Power (total):  {ac_power_w:.0f} W")
        if grid_w > 50:
            print(f"  Grid:              ↓ Importing {grid_w:.0f} W")
        elif grid_w < -50:
            print(f"  Grid:              ↑ Exporting {abs(grid_w):.0f} W")
        else:
            print(f"  Grid:              ─ Balanced ({grid_w:.0f} W)")
        print(f"  Battery (DC):      {dc_w:.0f} W {'(charging)' if dc_w < 0 else '(discharging)' if dc_w > 0 else '(idle)'}")

    # --- Control State ---
    if m704:
        wset_ena = m704.WSetEna.value if m704.WSetEna.value is not None else 0
        wset_pct = m704.WSetPct.value if m704.WSetPct.value is not None else 0
        sf_pct704 = ctrl._get_scale_factor(m704, 'WSetPct_SF')
        pct_real = wset_pct * (10 ** sf_pct704) if wset_pct else 0

        print(f"\n  Modbus Control (M704)")
        print(f"  {'─' * 40}")
        if wset_ena == 0:
            print(f"  Status:            ✅ Released (aGate in self-control)")
        elif wset_pct == 0:
            print(f"  Status:            ⚠️  Active at 0% (VPP Standby!)")
        else:
            direction = "Discharge" if pct_real > 0 else "Charge"
            pct_w = abs(pct_real / 100 * ctrl.RATED_MAX_W)
            print(f"  Status:            🔌 Active: {direction} {abs(pct_real):.1f}% ({pct_w:.0f}W)")
        print(f"  WSetEna:           {wset_ena}")
        print(f"  WSetPct:           {pct_real:.1f}% (raw={wset_pct})")

    # --- DER Control (M715) ---
    if m715:
        loc_rem = m715.LocRemCtl.value if m715.LocRemCtl.value is not None else -1
        print(f"\n  DER Control (M715)")
        print(f"  {'─' * 40}")
        print(f"  Control Mode:      {LOC_REM.get(loc_rem, f'Unknown({loc_rem})')}")
        if loc_rem == 1:
            print(f"  Note:              Local mode — advanced registers locked")

    # --- Enter Service (M703) ---
    if m703:
        ES_STATUS = {0: 'Disabled', 1: 'Enabled'}
        sf_v703 = ctrl._get_scale_factor(m703, 'V_SF')
        sf_hz703 = ctrl._get_scale_factor(m703, 'Hz_SF')
        es_permit = m703.ES.value if m703.ES.value is not None else -1
        v_hi = m703.ESVHi.value * (10 ** sf_v703) if m703.ESVHi.value is not None else None
        v_lo = m703.ESVLo.value * (10 ** sf_v703) if m703.ESVLo.value is not None else None
        hz_hi = m703.ESHzHi.value * (10 ** sf_hz703) if m703.ESHzHi.value is not None else None
        hz_lo = m703.ESHzLo.value * (10 ** sf_hz703) if m703.ESHzLo.value is not None else None
        dly_tms = m703.ESDlyTms.value if hasattr(m703, 'ESDlyTms') and m703.ESDlyTms.value is not None else None
        rmp_tms = m703.ESRmpTms.value if hasattr(m703, 'ESRmpTms') and m703.ESRmpTms.value is not None else None

        print(f"\n  Enter Service (M703)")
        print(f"  {'─' * 40}")
        print(f"  Permit:            {ES_STATUS.get(es_permit, f'Unknown({es_permit})')}")
        if v_lo is not None and v_hi is not None:
            print(f"  Voltage Range:     {v_lo:.1f} – {v_hi:.1f} %Vnom")
        if hz_lo is not None and hz_hi is not None:
            print(f"  Frequency Range:   {hz_lo:.2f} – {hz_hi:.2f} Hz")
        if dly_tms is not None:
            print(f"  Connect Delay:     {dly_tms} s")
        if rmp_tms is not None:
            print(f"  Ramp Time:         {rmp_tms} s")

    # --- Device Ratings ---
    print(f"\n  Device Ratings (M702)")
    print(f"  {'─' * 40}")
    print(f"  Max Power:         {ctrl.RATED_MAX_W} W")
    print(f"  Max Charge:        {ctrl.RATED_MAX_CHARGE_W} W")
    print(f"  Max Discharge:     {ctrl.RATED_MAX_DISCHARGE_W} W")

    print("\n" + "=" * 60)


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Handle schedule file display/validation (no hardware needed)
    if args.show_schedule:
        try:
            schedule = TOUSchedule.from_file(args.show_schedule)
            print(f"\nSchedule: {schedule.get_schedule_name()}")
            print("=" * 60)
            import json
            print(json.dumps(schedule.to_dict(), indent=2))
            print("=" * 60)
            print(f"Current period: {schedule.get_current_period()}")
            print(f"Current price: ${schedule.get_current_price():.2f}/kWh")
            print(f"Current strategy: {schedule.get_strategy()}")
            print(f"Rules: {schedule.get_rules()}")
            sys.exit(0)
        except Exception as e:
            print(f"Error loading schedule: {e}")
            sys.exit(1)
    
    if args.validate_schedule:
        try:
            schedule = TOUSchedule.from_file(args.validate_schedule)
            print(f"✓ Schedule '{schedule.get_schedule_name()}' is valid")
            print(f"  Periods: {len(schedule._schedule_data.get('periods', []))}")
            print(f"  Current period: {schedule.get_current_period()}")
            print(f"  Current strategy: {schedule.get_strategy()}")
            sys.exit(0)
        except Exception as e:
            print(f"✗ Schedule validation failed: {e}")
            sys.exit(1)
    
    # Check required IP for hardware operations
    if not args.ip:
        print("Error: -i/--ip is required (except for --show-schedule and --validate-schedule)")
        sys.exit(1)
    
    # Create hardware controller
    ctrl = FranklinWHController(
        ip_address=args.ip,
        port=args.port,
        unit_id=args.unit,
        timeout=args.timeout,
    )
    
    if not ctrl.connect():
        sys.exit(1)
    
    # Log startup information
    logger.info("=" * 60)
    logger.info("FranklinWH Control Starting")
    logger.info(f"  Target: {args.ip}:{args.port} (unit {args.unit})")
    logger.info(f"  Mode: {args.mode or 'direct control'}")
    logger.info(f"  SoC Limits: min_discharge={args.min_discharge_soc or 'auto'}, "
                f"max_charge={args.max_charge_soc}, ramp_window={args.soc_ramp_window}%")
    
    # Check aGate native mode for Cloud API coordination
    native = ctrl.read_native_mode()
    if native:
        ongrid_mode = native.get('mode_raw', -1)
        ongrid_name = native.get('mode_name', 'Unknown')
        self_reserve = native.get('self_reserve_pct', -1)
        tou_reserve = native.get('tou_reserve_pct', -1)
        
        logger.info(f"  aGate OnGridMode: {ongrid_name} ({ongrid_mode})")
        
        if ongrid_mode == 0:
            logger.info(f"  aGate Reserve: Emergency Backup mode (no reserve)")
        elif ongrid_mode == 1:
            logger.info(f"  aGate Reserve: Self-Consumption {self_reserve}%")
        elif ongrid_mode == 2:
            logger.info(f"  aGate Reserve: TOU {tou_reserve}%")
        elif ongrid_mode == 3:
            logger.info(f"  aGate Reserve: Manual mode")
        
        # Check for potential Cloud API activity
        if ongrid_mode != 3:  # Not in Manual mode
            # Read current battery activity
            bat_status = ctrl.read_battery_status()
            soc = bat_status.get('soc', 0)
            logger.info(f"  aGate SoC: {soc:.1f}%")
            
            # Check if Cloud API might be actively controlling
            control_status = ctrl.read_control_status()
            wset_ena = control_status.get('wset_enabled', 0)
            
            if wset_ena == 1:
                logger.warning(f"  ⚠️  WARNING: WSetEna=1 detected in {ongrid_name} mode!")
                logger.warning(f"      Cloud API or another controller may be active.")
                logger.warning(f"      Using --reset-on-start will take control via Modbus.")
            else:
                logger.info(f"  Note: OnGridMode={ongrid_name}, but WSetEna=0 (no active control)")
                if ongrid_mode == 2:
                    logger.info(f"        TOU schedule may activate soon.")
    
    logger.info("=" * 60)
    
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
        
        # Quick stop mode — release control and exit
        if args.stop:
            print("Releasing Modbus control (WSetEna=0)...")
            if ctrl.reset_control_state():
                print("✓ Control released — aGate will resume configured mode")
                sys.exit(0)
            else:
                print("✗ Failed to release control")
                sys.exit(1)
        
        # Status-only mode
        if args.status:
            print_system_status(ctrl)
            return
        
        # Virtual mode operation
        if args.mode:
            # Safety: require reset-on-start for virtual modes
            if not args.reset_on_start and not args.assume_clean_state:
                health = ctrl.healthcheck()
                if health.details.get('wset_ena') == 1:
                    print("\n⚠ Control already active. Use --reset-on-start for clean state.")
                    sys.exit(1)
            
            # Create virtual mode controller with SoC limits
            vmc = VirtualModeController(
                ctrl,
                max_charge_soc=args.max_charge_soc,
                min_discharge_soc=args.min_discharge_soc,
                soc_ramp_window=args.soc_ramp_window,
                force_soc_limits=args.force
            )
            
            # Load schedule file if provided (for time_of_use mode)
            if args.schedule_file:
                try:
                    schedule = TOUSchedule.from_file(args.schedule_file)
                    vmc.tou = schedule
                    print(f"Loaded TOU schedule: {schedule}")
                except Exception as e:
                    print(f"Error loading schedule file: {e}")
                    sys.exit(1)
            
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
            elif args.mode == 'time_of_use':
                # Schedule file is optional - will use default if not provided
                if vmc.tou.is_file_based():
                    mode_kwargs['tou_schedule'] = vmc.tou
            
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
        # Ensure control is released before disconnect
        try:
            ctrl.reset_control_state()
            logger.info("Control released (WSetEna=0)")
        except Exception as e:
            logger.warning(f"Could not release control: {e}")
        ctrl.disconnect()


if __name__ == '__main__':
    main()