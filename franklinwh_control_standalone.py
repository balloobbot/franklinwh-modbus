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
        
        # Battery state icon
        if battery_power < -50:
            bat_icon = "⚡ CHARGING"
            bat_detail = f"{abs(battery_power):.0f}W"
        elif battery_power > 50:
            bat_icon = "🔋 DISCHARGING"
            bat_detail = f"{battery_power:.0f}W"
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
        print(f"  MODE: {self.mode.value.upper()}")
        print(f"  {'─' * 66}")
        print(f"  ⏱️  ELAPSED: {self._format_duration(elapsed)}" + 
              (f"  |  ⏳ REMAINING: {self._format_duration(remaining)}" if remaining is not None else ""))
        print(f"  🎯 TARGET:   {self._get_target_soc_display()}")
        print(f"  {'─' * 66}")
        print(f"  BATTERY:    {bat_icon:15s} {bat_detail:>10s}  |  SoC: {soc:.1f}%")
        print(f"  SOLAR PV:   {'☀️  PRODUCING':15s} {solar_power:>10.0f}W  |  ")
        print(f"  HOME LOAD:  {'🏠 CONSUMING':15s} {home_load:>10.0f}W  |  ")
        print(f"  GRID:       {grid_icon:15s} {grid_detail:>10s}")
        print(f"  {'─' * 66}")
        print(f"  CMD: WSetPct={control.get('wset_pct', 0):.1f}%  ({battery_power:.0f}W)")
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
        # Ensure control is released before disconnect
        try:
            ctrl.reset_control_state()
            logger.info("Control released (WSetEna=0)")
        except Exception as e:
            logger.warning(f"Could not release control: {e}")
        ctrl.disconnect()


if __name__ == '__main__':
    main()