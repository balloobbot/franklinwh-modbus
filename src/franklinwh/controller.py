"""
FranklinWH Modbus Battery Manager - Hardware Controller

This module provides the FranklinWHController class for direct Modbus
communication with FranklinWH aGate battery systems.
"""

import logging
import time
import struct
import threading
from typing import Dict, Any, Optional, Tuple, List

from .types import BatteryCommand, HealthStatus, ONGRID_MODES

logger = logging.getLogger(__name__)

# Try to import sunspec2, fallback to None if not available
try:
    from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP
    SUNSPEC_AVAILABLE = True
except ImportError:
    SunSpecModbusClientDeviceTCP = None
    SUNSPEC_AVAILABLE = False

# Cloud API availability flag
CLOUD_API_AVAILABLE = False


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
        timeout: float = 10.0,
        base_address: int = 0,  # sunspec2 uses 0 for auto/scan
    ):
        if not SUNSPEC_AVAILABLE:
            raise ImportError("sunspec2 package is required. Install with: pip install sunspec2")
        
        self.ip_address = ip_address
        self.port = port
        self.unit_id = unit_id
        self.timeout = timeout
        self.base_address = base_address
        self.dev: Optional[SunSpecModbusClientDeviceTCP] = None
        self.models: dict = {}
        self._span_writable: Optional[bool] = None
        
        # Software command timeout (hardware WSetRvrtTms doesn't work)
        self._command_timer: Optional[threading.Timer] = None
        self._command_timer_lock = threading.Lock()
        
        # Extension register write test results
        self._extension_write_results: Dict[str, Any] = {
            'tested': False,
            'timestamp': None,
            'ongrid_mode': {'writable': False, 'error': None},
            'self_reserve': {'writable': False, 'error': None},
            'tou_reserve': {'writable': False, 'error': None},
        }
        
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
            
            self.discover_ratings()
            
            # Run extension write test (non-blocking, informational)
            self._test_extension_writability()
            
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def _test_extension_writability(self) -> Dict[str, Any]:
        """
        Test writability of FranklinWH extension registers.
        
        Tests OnGridMode (15507), SelfReserve (15508), and TOUReserve (15509).
        This is informational only - non-blocking, never raises.
        
        Returns dict with test results stored in self._extension_write_results.
        """
        import time
        import struct
        self._extension_write_results['timestamp'] = time.time()
        
        if not self.dev or not self.dev.client:
            self._extension_write_results['ongrid_mode']['error'] = 'No connection'
            self._extension_write_results['self_reserve']['error'] = 'No connection'
            self._extension_write_results['tou_reserve']['error'] = 'No connection'
            return self._extension_write_results
        
        client = self.dev.client
        
        # Helper to read registers using raw socket (sunspec2 client doesn't have read_holding_registers)
        def read_regs(addr: int, count: int) -> Optional[list]:
            try:
                client.connect()
                sock = client.socket
                if not sock:
                    return None
                # Modbus TCP request: transaction_id(2), protocol(2), length(2), unit(1), function(1), addr(2), count(2)
                req = struct.pack('>HHHBBHH', 0, 0, 6, self.unit_id, 3, addr, count)
                sock.sendall(req)
                resp = sock.recv(256)
                # Response: transaction_id(2), protocol(2), length(2), unit(1), function(1), byte_count(1), data...
                if len(resp) >= 9 + count * 2:
                    return list(struct.unpack(f'>{count}H', resp[9:9+count*2]))
            except Exception:
                pass
            return None
        
        # Helper to write a single register
        def write_reg(addr: int, value: int) -> bool:
            try:
                client.connect()
                sock = client.socket
                if not sock:
                    return False
                # Modbus TCP write request
                req = struct.pack('>HHHBBHHH', 0, 0, 6, self.unit_id, 6, addr, value)
                sock.sendall(req)
                resp = sock.recv(256)
                return len(resp) >= 12
            except Exception:
                return False
        
        # Test 1: OnGridMode (15507)
        # Test: read -> write Self-Consumption (2) -> verify -> restore original
        try:
            regs = read_regs(self.EXT_ONGRID_MODE, 1)
            original = regs[0] if regs else None
            if original is None:
                self._extension_write_results['ongrid_mode']['error'] = 'Read failed'
            elif original not in (0, 1, 2, 3):
                self._extension_write_results['ongrid_mode']['error'] = f'Invalid value: {original}'
            else:
                # Try to write Self-Consumption mode (2)
                test_value = 2 if original != 2 else 1  # Use 2 or alternate with 1
                if write_reg(self.EXT_ONGRID_MODE, test_value):
                    # Verify write
                    time.sleep(0.1)
                    verified_regs = read_regs(self.EXT_ONGRID_MODE, 1)
                    verified = verified_regs[0] if verified_regs else None
                    if verified == test_value:
                        self._extension_write_results['ongrid_mode']['writable'] = True
                        # Restore original
                        write_reg(self.EXT_ONGRID_MODE, original)
                    else:
                        self._extension_write_results['ongrid_mode']['error'] = 'Verify failed (read-only?)'
                else:
                    self._extension_write_results['ongrid_mode']['error'] = 'Write rejected (needs unlock?)'
        except Exception as e:
            self._extension_write_results['ongrid_mode']['error'] = str(e)[:50]
        
        # Test 2: SelfReserve (15508)
        # Test: read -> write +1 -> verify -> restore
        try:
            regs = read_regs(self.EXT_SELF_RESERVE, 1)
            original = regs[0] if regs else None
            if original is None:
                self._extension_write_results['self_reserve']['error'] = 'Read failed'
            elif not (0 <= original <= 100):
                self._extension_write_results['self_reserve']['error'] = f'Invalid value: {original}'
            else:
                # Try to write +1 (wrap at 100)
                test_value = (original + 1) % 101
                if write_reg(self.EXT_SELF_RESERVE, test_value):
                    time.sleep(0.1)
                    verified_regs = read_regs(self.EXT_SELF_RESERVE, 1)
                    verified = verified_regs[0] if verified_regs else None
                    if verified == test_value:
                        self._extension_write_results['self_reserve']['writable'] = True
                        write_reg(self.EXT_SELF_RESERVE, original)
                    else:
                        self._extension_write_results['self_reserve']['error'] = 'Verify failed (read-only?)'
                else:
                    self._extension_write_results['self_reserve']['error'] = 'Write rejected (needs unlock?)'
        except Exception as e:
            self._extension_write_results['self_reserve']['error'] = str(e)[:50]
        
        # Test 3: TOUReserve (15509)
        # Test: read -> write +1 -> verify -> restore
        try:
            regs = read_regs(self.EXT_TOU_RESERVE, 1)
            original = regs[0] if regs else None
            if original is None:
                self._extension_write_results['tou_reserve']['error'] = 'Read failed'
            elif not (0 <= original <= 100):
                self._extension_write_results['tou_reserve']['error'] = f'Invalid value: {original}'
            else:
                test_value = (original + 1) % 101
                if write_reg(self.EXT_TOU_RESERVE, test_value):
                    time.sleep(0.1)
                    verified_regs = read_regs(self.EXT_TOU_RESERVE, 1)
                    verified = verified_regs[0] if verified_regs else None
                    if verified == test_value:
                        self._extension_write_results['tou_reserve']['writable'] = True
                        write_reg(self.EXT_TOU_RESERVE, original)
                    else:
                        self._extension_write_results['tou_reserve']['error'] = 'Verify failed (read-only?)'
                else:
                    self._extension_write_results['tou_reserve']['error'] = 'Write rejected (needs unlock?)'
        except Exception as e:
            self._extension_write_results['tou_reserve']['error'] = str(e)[:50]
        
        self._extension_write_results['tested'] = True
        
        # Log summary
        writable_count = sum(1 for k in ['ongrid_mode', 'self_reserve', 'tou_reserve'] 
                            if self._extension_write_results[k]['writable'])
        if writable_count == 3:
            logger.info("Extension registers: FULL WRITE ACCESS (OnGridMode + Reserves)")
        elif writable_count > 0:
            writable_regs = [k for k in ['ongrid_mode', 'self_reserve', 'tou_reserve'] 
                           if self._extension_write_results[k]['writable']]
            logger.info(f"Extension registers: PARTIAL WRITE ACCESS ({', '.join(writable_regs)})")
        else:
            logger.info("Extension registers: READ-ONLY (requires installer unlock for SPAN Modbus)")
        
        return self._extension_write_results
    
    def get_extension_write_status(self) -> Dict[str, Any]:
        """Get the results of the extension write test."""
        return self._extension_write_results.copy()
    
    def disconnect(self):
        """Close connection."""
        if self.dev:
            try:
                self.dev.close()
            except Exception:
                pass
            self.dev = None
            logger.info("Disconnected")
    
    def is_connected(self) -> bool:
        """Check if connection is alive."""
        if self.dev is None:
            return False
        try:
            # Try a simple read to check connection
            self.dev.read(40071, 1)
            return True
        except Exception:
            return False
    
    def reconnect(self) -> bool:
        """Reconnect to the aGate."""
        logger.info("Attempting to reconnect...")
        self.disconnect()
        time.sleep(1.0)  # Longer pause for aGate to reset
        
        # Completely recreate the client (not just reconnect)
        # This clears any corrupted internal state
        try:
            self.dev = SunSpecModbusClientDeviceTCP(
                slave_id=self.unit_id,
                ipaddr=self.ip_address,
                ipport=self.port,
                timeout=self.timeout,
            )
            self.dev.scan()
            
            # Rebuild models dict
            self.models = {
                int(k) if str(k).isdigit() else k: v 
                for k, v in self.dev.models.items()
            }
            
            logger.info("Reconnected successfully")
            return True
            
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            self.dev = None
            return False
    
    def _with_retry(self, operation, max_retries: int = 2):
        """Execute operation with automatic reconnect on failure."""
        for attempt in range(max_retries):
            try:
                return operation()
            except Exception as e:
                # Check if it's a connection-related error
                err_str = str(e).lower()
                is_connection_error = (
                    isinstance(e, (ConnectionError, BrokenPipeError, OSError)) or
                    'broken pipe' in err_str or
                    'socket' in err_str or
                    'timeout' in err_str or
                    'connection' in err_str or
                    'modbus' in err_str
                )
                
                if is_connection_error and attempt < max_retries - 1:
                    logger.warning(f"Connection issue ({e}), attempt {attempt + 1}/{max_retries}, reconnecting...")
                    if self.reconnect():
                        logger.info("Reconnected, retrying operation...")
                        continue
                    else:
                        logger.error("Reconnection failed")
                raise
        return operation()
    
    def get_model(self, model_id: int):
        """Get model instance, handling list wrapper."""
        model = self.models.get(model_id)
        if model is None:
            return None
        if isinstance(model, list):
            return model[0] if model else None
        return model
    
    def _get_scale_factor(self, model, sf_name: str) -> int:
        """Get scale factor value, default to 0.

        SunSpec scale factors are always in range [-10, 10].
        Values outside this range (e.g. -32768 / 0x8000) indicate
        corrupt register data and are clamped to 0 to prevent
        OverflowError in 10**sf arithmetic.
        """
        sf_point = getattr(model, sf_name, None)
        if sf_point and hasattr(sf_point, 'value'):
            val = sf_point.value
            if val is not None and -10 <= val <= 10:
                return val
            if val is not None:
                logger.warning(f"Corrupt scale factor {sf_name}={val}, using 0")
        return 0
    
    def read_battery_status(self) -> dict:
        """Read current battery status from Model 713 and 714.
        
        Returns dict with:
            soc, soh, wh_rating, wh_available (from M713)
            status_raw: M713.Sta raw value (always 0 on FranklinWH — do not use)
            battery_state: Derived from M714 DCW power direction (CHARGING/DISCHARGING/IDLE)
            battery_power_w, battery_current_a, battery_temp_c (from M714)
        """
        def _do_read():
            m713 = self.get_model(713)
            if not m713:
                raise ConnectionError("Model 713 not available")
            
            m713.read()
            
            sf_wh = self._get_scale_factor(m713, 'WH_SF')
            sf_pct = self._get_scale_factor(m713, 'Pct_SF')
            
            result = {
                'soc': round(m713.SoC.value * (10 ** sf_pct), 1),
                'soh': round(m713.SoH.value * (10 ** sf_pct), 1),
                'wh_rating': m713.WHRtg.value * (10 ** sf_wh),
                'wh_available': m713.WHAvail.value * (10 ** sf_wh),
                'status_raw': m713.Sta.value,  # Always 0 on FranklinWH (quirk)
            }
            
            # Model 714 - Battery DC power (DCW: negative=charging, positive=discharging)
            m714 = self.get_model(714)
            if m714:
                try:
                    m714.read()
                    sf_w = self._get_scale_factor(m714, 'DCW_SF')
                    sf_a = self._get_scale_factor(m714, 'DCA_SF')
                    sf_v = self._get_scale_factor(m714, 'DCV_SF')
                    
                    dc_power = m714.DCW.value * (10 ** sf_w) if m714.DCW.value is not None else 0
                    result['battery_power_w'] = dc_power
                    
                    # Derive battery state from DC power direction (±50W deadband)
                    # FranklinWH M713.Sta is always 0 (OFF) — cannot rely on it
                    if dc_power < -50:
                        result['battery_state'] = 'CHARGING'
                    elif dc_power > 50:
                        result['battery_state'] = 'DISCHARGING'
                    else:
                        result['battery_state'] = 'IDLE'
                    
                    # DC current (read or calculate from P/V)
                    dc_current = 0
                    if hasattr(m714, 'DCA') and m714.DCA.value is not None and m714.DCA.value != 0:
                        dc_current = m714.DCA.value * (10 ** sf_a)
                    elif hasattr(m714, 'DCV') and m714.DCV.value is not None and m714.DCV.value != 0:
                        dc_voltage = m714.DCV.value * (10 ** sf_v)
                        if dc_voltage > 0:
                            dc_current = round(dc_power / dc_voltage, 2)
                    result['battery_current_a'] = dc_current
                    
                    # Battery temperature from M714
                    sf_tmp = self._get_scale_factor(m714, 'Tmp_SF')
                    if hasattr(m714, 'Tmp') and m714.Tmp.value is not None:
                        result['battery_temp_c'] = round(m714.Tmp.value * (10 ** sf_tmp), 1)
                    else:
                        result['battery_temp_c'] = 0
                except Exception as e:
                    logger.debug(f"Could not read Model 714: {e}")
            
            return result
        
        try:
            return self._with_retry(_do_read, max_retries=2)
        except Exception as e:
            logger.debug(f"Failed to read battery status: {e}")
            return {}
    
    def read_grid_status(self) -> dict:
        """Read grid status from Model 701.
        
        Returns dict with:
            grid_power_w, grid_va, grid_var, voltage_v, frequency_hz,
            connection_state, inverter_state, grid_mode, ac_type,
            current_a, power_factor, ambient_temp_c, cabinet_temp_c
        """
        def _do_read():
            m701 = self.get_model(701)
            if not m701:
                raise ConnectionError("Model 701 not available")
            
            m701.read()
            
            sf_w = self._get_scale_factor(m701, 'W_SF')
            sf_v = self._get_scale_factor(m701, 'V_SF')
            sf_hz = self._get_scale_factor(m701, 'Hz_SF')
            sf_a = self._get_scale_factor(m701, 'A_SF')
            sf_pf = self._get_scale_factor(m701, 'PF_SF')
            sf_tmp = self._get_scale_factor(m701, 'Tmp_SF')
            
            voltage = round(m701.LNV.value * (10 ** sf_v), 1) if m701.LNV.value is not None else 0
            freq = round(m701.Hz.value * (10 ** sf_hz), 2) if m701.Hz.value is not None else 0
            
            # Connection state
            conn_st = m701.ConnSt.value if hasattr(m701, 'ConnSt') and m701.ConnSt.value is not None else -1
            CONN_STATES = {0: 'Disconnected', 1: 'Connected', 2: 'Fault'}
            
            # Inverter state
            inv_st = m701.InvSt.value if hasattr(m701, 'InvSt') and m701.InvSt.value is not None else -1
            INVERTER_STATES = {0: 'Off', 1: 'Sleeping', 2: 'Starting', 3: 'Running',
                              4: 'Throttled', 5: 'Shutting Down', 6: 'Fault',
                              7: 'Standby', 8: 'Test', 9: 'Manufacturing'}
            
            # Grid mode from DERMode upper bits
            der_mode_raw = m701.DERMode.value if hasattr(m701, 'DERMode') and m701.DERMode.value is not None else 0
            if der_mode_raw & (1 << 17):
                grid_mode = 'Grid Forming'
            elif der_mode_raw & (1 << 16):
                grid_mode = 'Grid Following'
            else:
                grid_mode = 'Grid Following (default)'
            
            # Determine AC type based on voltage
            if 200 <= voltage <= 260:
                ac_type = 'Single-Phase (230V Nominal)'
            elif 100 <= voltage < 200:
                ac_type = 'Single-Phase (120V Nominal)'
            elif 380 <= voltage <= 420:
                ac_type = 'Three-Phase (400V Line-Line)'
            else:
                ac_type = 'Unknown'
            
            # Current (A field or AphA fallback)
            current = 0
            if hasattr(m701, 'A') and m701.A.value is not None:
                current = round(m701.A.value * (10 ** sf_a), 1)
            elif hasattr(m701, 'AphA') and m701.AphA.value is not None:
                current = round(m701.AphA.value * (10 ** sf_a), 1)
            
            # Power factor
            pf = 0
            if hasattr(m701, 'PF') and m701.PF.value is not None:
                pf = round(m701.PF.value * (10 ** sf_pf), 3)
            
            # Temperatures (FranklinWH implements TmpAmb and TmpCab)
            ambient_temp = 0
            if hasattr(m701, 'TmpAmb') and m701.TmpAmb.value is not None:
                ambient_temp = round(m701.TmpAmb.value * (10 ** sf_tmp), 1)
            
            cabinet_temp = 0
            if hasattr(m701, 'TmpCab') and m701.TmpCab.value is not None:
                cabinet_temp = round(m701.TmpCab.value * (10 ** sf_tmp), 1)
            
            return {
                'grid_power_w': m701.W.value * (10 ** sf_w) if m701.W.value is not None else 0,
                'grid_va': m701.VA.value * (10 ** sf_w) if m701.VA.value is not None else 0,
                'grid_var': m701.Var.value * (10 ** sf_w) if m701.Var.value is not None else 0,
                'voltage_v': voltage,
                'frequency_hz': freq,
                'current_a': current,
                'power_factor': pf,
                'ambient_temp_c': ambient_temp,
                'cabinet_temp_c': cabinet_temp,
                'connection_state': CONN_STATES.get(conn_st, f'Unknown({conn_st})'),
                'inverter_state': INVERTER_STATES.get(inv_st, f'Unknown({inv_st})'),
                'grid_mode': grid_mode,
                'ac_type': ac_type,
            }
        
        try:
            return self._with_retry(_do_read, max_retries=2)
        except Exception as e:
            logger.debug(f"Failed to read grid status: {e}")
            return {}
    
    def read_solar_status(self) -> dict:
        """Read solar status from Model 502 (AC output), Model 714 (battery DC), and extensions."""
        def _do_read():
            # Model 502 - Solar AC Output (for AC-coupled systems like aGate X)
            m502 = self.get_model(502)
            solar_ac_power = 0
            if m502:
                try:
                    m502.read()
                    sf_w = self._get_scale_factor(m502, 'W_SF')
                    # Model 502 uses OutPw (Output Power), not W
                    if hasattr(m502, 'OutPw') and m502.OutPw.value is not None:
                        solar_ac_power = m502.OutPw.value * (10 ** sf_w)
                except Exception as e:
                    logger.debug(f"Could not read Model 502: {e}")
            
            # Model 714 - Battery DC Power (not solar!)
            m714 = self.get_model(714)
            battery_dc_power = 0
            if m714:
                try:
                    m714.read()
                    sf_w = self._get_scale_factor(m714, 'DCW_SF')
                    battery_dc_power = m714.DCW.value * (10 ** sf_w)
                except Exception as e:
                    logger.debug(f"Could not read Model 714: {e}")
            
            solar_status = {
                # Model 502 - Actual solar AC output
                'ac_power_w': solar_ac_power,
                # Model 714 - Battery DC (for backward compat, but this is BATTERY not solar!)
                'dc_power_w': battery_dc_power,
                'battery_dc_power_w': battery_dc_power,
            }
            
            # FranklinWH extensions (15500+) - may have total solar including remote
            try:
                ext_solar = self._read_extension_solar()
                if ext_solar:
                    solar_status['extension'] = ext_solar
                    # If extension has total solar, use it
                    if ext_solar.get('total_solar', 0) > 0:
                        solar_status['total_solar_w'] = ext_solar['total_solar']
                        # Also update ac_power_w if Model 502 was 0
                        if solar_ac_power == 0:
                            solar_status['ac_power_w'] = ext_solar['total_solar']
            except Exception as e:
                logger.debug(f"Could not read extension solar: {e}")
            
            return solar_status
        
        try:
            return self._with_retry(_do_read, max_retries=2)
        except Exception as e:
            logger.debug(f"Failed to read solar status: {e}")
            return {}
    
    def _read_extension_solar(self) -> Optional[dict]:
        """Read FranklinWH extension registers for solar (15500-15513).
        
        Uses raw Modbus TCP socket because SunSpec2 client remaps addresses
        and fails on FranklinWH proprietary extension registers.
        """
        try:
            client = self.dev.client
            client.connect()
            sock = client.socket
            if not sock:
                return None
            
            # Raw Modbus TCP: read 14 registers starting at 15500
            req = struct.pack('>HHHBBHH', 0, 0, 6, self.unit_id, 3, 15500, 14)
            sock.settimeout(self.timeout)
            sock.sendall(req)
            resp = sock.recv(256)
            
            if len(resp) < 37:  # 9 header + 14*2 bytes
                return None
            
            regs = list(struct.unpack('>14H', resp[9:37]))
            
            pv_total = regs[2] if len(regs) > 2 else 0
            pv_proximal = regs[3] if len(regs) > 3 else 0
            pv_remote1 = regs[4] if len(regs) > 4 else 0
            pv_remote2 = regs[5] if len(regs) > 5 else 0
            home_load = regs[6] if len(regs) > 6 else 0
            ongrid_mode = regs[7] if len(regs) > 7 else -1
            self_reserve = regs[8] if len(regs) > 8 else 0
            tou_reserve = regs[9] if len(regs) > 9 else 0
            
            individual_sum = pv_proximal + pv_remote1 + pv_remote2
            if pv_total > 0 and abs(pv_total - individual_sum) < 100:
                total_solar = pv_total
            elif individual_sum > 0:
                total_solar = individual_sum
            else:
                total_solar = pv_total
            
            return {
                'pv_total': pv_total,
                'pv_proximal': pv_proximal,
                'pv_remote1': pv_remote1,
                'pv_remote2': pv_remote2,
                'total_solar': total_solar,
                'home_load_ext': home_load,
                'ongrid_mode': ongrid_mode,
                'self_reserve': self_reserve,
                'tou_reserve': tou_reserve,
            }
        except Exception as e:
            logger.debug(f"Extension solar read failed: {e}")
            return None
    
    def read_nameplate(self) -> dict:
        """Read device nameplate information from Model 1 (Common).
        
        Returns:
            Dict with manufacturer, model, serial, version as strings.
        """
        m1 = self.get_model(1)
        if not m1:
            return {}
        
        def _get_point_str(model, point_name):
            """Resolve a SunSpec point to a clean string value."""
            pt = getattr(model, point_name, None)
            if pt is None:
                return ''
            if hasattr(pt, 'value'):
                val = pt.value
                if isinstance(val, bytes):
                    return val.decode('utf-8', errors='ignore').strip('\x00').strip()
                return str(val).strip() if val else ''
            return str(pt).strip() if pt else ''
        
        try:
            m1.read()
            return {
                'manufacturer': _get_point_str(m1, 'Mn'),
                'model': _get_point_str(m1, 'Md'),
                'serial': _get_point_str(m1, 'SN'),
                'version': _get_point_str(m1, 'Vr'),
                'options': _get_point_str(m1, 'Opt'),
            }
        except Exception as e:
            logger.debug(f"Could not read Model 1 nameplate: {e}")
            return {}
    
    def read_control_status(self) -> dict:
        """Read current control settings from Model 704."""
        def _do_read():
            m704 = self.get_model(704)
            if not m704:
                raise ConnectionError("Model 704 not available")
            
            m704.read()
            
            sf_w = self._get_scale_factor(m704, 'WSet_SF')
            sf_pct = self._get_scale_factor(m704, 'WSetPct_SF')
            
            return {
                'wset_enabled': m704.WSetEna.value,
                'wset_mode': m704.WSetMod.value,
                'wset_watts': m704.WSet.value * (10 ** sf_w),
                'wset_pct': m704.WSetPct.value * (10 ** sf_pct),
                'wset_pct_raw': m704.WSetPct.value,
                'wset_revert_watts': m704.WSetRvrt.value * (10 ** sf_w) if m704.WSetRvrt.value != -0x80000000 else None,
                'wset_revert_time_s': m704.WSetRvrtTms.value,
                'wset_revert_remain_s': m704.WSetRvrtRem.value,
            }
        
        try:
            return self._with_retry(_do_read, max_retries=2)
        except Exception as e:
            logger.debug(f"Failed to read control status: {e}")
            return {}
    
    def read_native_mode(self) -> dict:
        """Read FranklinWH native operating mode via raw Modbus TCP."""
        FRANKLIN_MODES = {0: 'Emergency Backup', 1: 'Time of Use',
                          2: 'Self-Consumption', 3: 'Manual'}
        try:
            client = self.dev.client
            client.connect()
            sock = client.socket
            if not sock:
                return {}
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
    
    # =========================================================================
    # RESERVE SOC VALIDATION (GAP-1, GAP-2 SAFETY FEATURES)
    # =========================================================================
    
    SAFETY_MARGIN_PCT = 5  # Minimum 5% buffer above reserve level
    ABSOLUTE_MIN_SOC = 5   # Absolute minimum SoC for any operation
    ABSOLUTE_MAX_SOC = 99  # Absolute maximum SoC for any operation
    
    def get_effective_reserve_level(self) -> Tuple[Optional[int], str]:
        """Get the effective reserve level based on current aGate mode.
        
        Returns:
            Tuple of (reserve_pct, source) where source describes which
            reserve setting is active ('self', 'tou', 'none', 'unknown').
        """
        native = self.read_native_mode()
        if not native:
            return None, 'unknown'
        
        mode_raw = native.get('mode_raw', -1)
        
        # Mode mapping: 0=Backup, 1=TOU, 2=Self-Consumption, 3=Manual
        if mode_raw == 2:  # Self-Consumption
            reserve = native.get('self_reserve_pct', 20)
            return reserve, 'self'
        elif mode_raw == 1:  # Time of Use
            reserve = native.get('tou_reserve_pct', 20)
            return reserve, 'tou'
        elif mode_raw == 0:  # Emergency Backup
            # Emergency backup typically uses self_reserve
            reserve = native.get('self_reserve_pct', 20)
            return reserve, 'self'
        elif mode_raw == 3:  # Manual
            # Manual mode may not enforce reserve, but we still check
            return None, 'none'
        else:
            return None, 'unknown'
    
    def validate_target_soc(
        self,
        target_soc: float,
        operation: str  # 'charge' or 'discharge'
    ) -> Tuple[bool, str, dict]:
        """Validate target SoC against reserve levels and safety margins.
        
        Implements GAP-1 (reserve conflict detection) and GAP-2 (safety margin).
        
        Args:
            target_soc: Target SoC percentage (0-100)
            operation: 'charge' or 'discharge'
            
        Returns:
            Tuple of (is_valid, message, details) where details contains:
            - target_soc: The requested target
            - effective_reserve: Current reserve level (if applicable)
            - min_allowed: Minimum allowed SoC for this operation
            - max_allowed: Maximum allowed SoC for this operation
            - safety_margin: Applied safety margin
        """
        details = {
            'target_soc': target_soc,
            'operation': operation,
            'effective_reserve': None,
            'reserve_source': 'unknown',
            'min_allowed': self.ABSOLUTE_MIN_SOC,
            'max_allowed': self.ABSOLUTE_MAX_SOC,
            'safety_margin': self.SAFETY_MARGIN_PCT,
        }
        
        # Basic range check
        if not (self.ABSOLUTE_MIN_SOC <= target_soc <= self.ABSOLUTE_MAX_SOC):
            return (
                False,
                f"E001: Target SoC {target_soc:.1f}% outside absolute safe range "
                f"({self.ABSOLUTE_MIN_SOC}-{self.ABSOLUTE_MAX_SOC}%)",
                details
            )
        
        # Get effective reserve level
        reserve, source = self.get_effective_reserve_level()
        details['effective_reserve'] = reserve
        details['reserve_source'] = source
        
        if reserve is not None:
            # GAP-2: Apply safety margin above reserve
            min_with_margin = reserve + self.SAFETY_MARGIN_PCT
            details['min_allowed'] = max(min_with_margin, self.ABSOLUTE_MIN_SOC)
            
            # GAP-1: Check for reserve conflicts
            if operation == 'discharge':
                # Discharging: target must not go below reserve + margin
                if target_soc < min_with_margin:
                    return (
                        False,
                        f"E002: Target SoC {target_soc:.1f}% conflicts with reserve "
                        f"({reserve}% from {source}) + safety margin ({self.SAFETY_MARGIN_PCT}%). "
                        f"Minimum allowed: {min_with_margin:.1f}%",
                        details
                    )
            elif operation == 'charge':
                # Charging: target should not be below reserve (warn, don't block)
                if target_soc < reserve:
                    details['warning'] = (
                        f"W001: Target SoC {target_soc:.1f}% below configured reserve "
                        f"({reserve}% from {source}). Battery may not charge as expected."
                    )
        
        # Operation-specific validation
        if operation == 'discharge':
            # For discharge, target must be below current SoC (checked elsewhere)
            pass
        elif operation == 'charge':
            # For charge, target must be above current SoC (checked elsewhere)
            pass
        
        return True, "Target SoC validated successfully", details
    
    def validate_soc_safety(
        self,
        target_soc: float,
        current_soc: float,
        operation: str
    ) -> Tuple[bool, str, dict]:
        """Comprehensive SoC safety validation before operation.
        
        Combines reserve validation with current SoC sanity checks.
        
        Args:
            target_soc: Target SoC to reach
            current_soc: Current battery SoC
            operation: 'charge' or 'discharge'
            
        Returns:
            Tuple of (is_safe, message, details)
        """
        # First, validate target against reserves
        is_valid, msg, details = self.validate_target_soc(target_soc, operation)
        
        if not is_valid:
            return is_valid, msg, details
        
        # Add current SoC to details
        details['current_soc'] = current_soc
        
        # Validate target vs current based on operation
        if operation == 'discharge':
            # Target must be below current for discharge
            if target_soc >= current_soc:
                return (
                    False,
                    f"E003: Discharge target {target_soc:.1f}% must be below "
                    f"current SoC {current_soc:.1f}%",
                    details
                )
            # Check if we're already at or below target
            if current_soc <= target_soc + 1.0:  # 1% tolerance
                return (
                    False,
                    f"E004: Already at or below target SoC (current: {current_soc:.1f}%, "
                    f"target: {target_soc:.1f}%)",
                    details
                )
                
        elif operation == 'charge':
            # Target must be above current for charge
            if target_soc <= current_soc:
                return (
                    False,
                    f"E005: Charge target {target_soc:.1f}% must be above "
                    f"current SoC {current_soc:.1f}%",
                    details
                )
            # Check if we're already at or above target
            if current_soc >= target_soc - 1.0:  # 1% tolerance
                return (
                    False,
                    f"E006: Already at or above target SoC (current: {current_soc:.1f}%, "
                    f"target: {target_soc:.1f}%)",
                    details
                )
        
        # Check reserve boundary proximity (warning only for discharge)
        reserve, source = self.get_effective_reserve_level()
        if reserve is not None and operation == 'discharge':
            reserve_distance = current_soc - reserve
            if reserve_distance <= self.SAFETY_MARGIN_PCT + 2:
                details['proximity_warning'] = (
                    f"W002: Current SoC {current_soc:.1f}% is only {reserve_distance:.1f}% "
                    f"above reserve ({reserve}% from {source}). "
                    f"Discharge will stop with minimal margin."
                )
        
        return True, "SoC safety validation passed", details
    
    # Default fallback ratings
    RATED_MAX_W = 5000
    RATED_MAX_CHARGE_W = 5000
    RATED_MAX_DISCHARGE_W = 5000
    
    def discover_ratings(self):
        """Read M702 nameplate ratings to replace hardcoded limits."""
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
        is_charge = power_watts > 0
        limit = self.RATED_MAX_CHARGE_W if is_charge else self.RATED_MAX_DISCHARGE_W
        if abs(power_watts) > limit:
            clamped = -limit if power_watts > 0 else limit
            logger.warning(f"SAFETY CLAMP: {power_watts}W exceeds {'charge' if is_charge else 'discharge'} "
                          f"limit {limit}W — clamped to {clamped}W")
            return clamped
        return power_watts
    
    def cancel_command_timer(self) -> None:
        """Cancel any active software command timeout."""
        with self._command_timer_lock:
            if self._command_timer and self._command_timer.is_alive():
                self._command_timer.cancel()
                logger.info("Command timer cancelled")
            self._command_timer = None
    
    def get_command_timer_status(self) -> dict:
        """Return status of software command timeout timer.
        
        Returns dict with:
            active: bool - whether a timer is currently running
            remaining_s: float - approximate seconds remaining (0 if no timer)
        """
        with self._command_timer_lock:
            if self._command_timer and self._command_timer.is_alive():
                # Timer.interval is the full duration, but we don't track start time
                # Just indicate it's active
                return {'active': True, 'interval_s': self._command_timer.interval}
            return {'active': False, 'interval_s': 0}

    def send_command(
        self,
        command: BatteryCommand,
        duration_s: Optional[int] = None,
        dry_run: bool = False
    ) -> Tuple[bool, str]:
        """Send battery control command via Model 704.
        
        Args:
            command: BatteryCommand with power_watts and direction
            duration_s: Optional software timeout in seconds. After this
                duration, reset_control_state() is called automatically.
                Hardware reversion (WSetRvrtTms) does NOT work on FranklinWH.
            dry_run: If True, report what would happen without writing
        """
        def _do_send():
            m704 = self.get_model(704)
            if not m704:
                raise ConnectionError("Model 704 not available")
            
            safe_watts = self._validate_power(command.power_watts)
            
            pct_sf = self._get_scale_factor(m704, 'WSetPct_SF')
            pct_raw = int((safe_watts / self.RATED_MAX_W) * 100 / (10 ** pct_sf))
            
            if dry_run:
                return True, f"Dry Run: WSetPct={pct_raw} ({command.power_watts}W)"
            
            # Cancel any existing timer before sending new command
            self.cancel_command_timer()
            
            # 1. STOP & CLEAR
            m704.read()
            m704.WSetEna.value = 0
            m704.write()
            time.sleep(0.3)
            
            # 2. CONFIGURE - WSetPct ONLY, do not set WSet (causes mode flickering)
            # NOTE: Invert sign - hardware WSetPct: positive=discharge, negative=charge
            m704.read()
            m704.WSetMod.value = 0
            m704.WSetPct.value = -pct_raw  # INVERTED for hardware convention
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
            
            # 5. START SOFTWARE TIMEOUT if requested
            if duration_s and duration_s > 0:
                def _on_timeout():
                    logger.warning(f"Software timeout ({duration_s}s) expired — resetting control")
                    try:
                        self.reset_control_state()
                    except Exception as e:
                        logger.error(f"Failed to reset on timeout: {e}")
                
                with self._command_timer_lock:
                    self._command_timer = threading.Timer(duration_s, _on_timeout)
                    self._command_timer.daemon = True  # Don't block exit
                    self._command_timer.start()
                logger.info(f"Software timeout set: {duration_s}s")
                return True, f"Command Sent: {command.power_watts}W ({actual_pct}% of {self.RATED_MAX_W}W) [timeout: {duration_s}s]"
            
            return True, f"Command Sent: {command.power_watts}W ({actual_pct}% of {self.RATED_MAX_W}W)"
        
        try:
            return self._with_retry(_do_send, max_retries=2)
        except Exception as e:
            return False, str(e)
    
    def reset_control_state(self) -> bool:
        """Reset aGate to known clean state (idle)."""
        def _do_reset():
            logger.info("Resetting control state to idle...")
            
            m704 = self.get_model(704)
            if not m704:
                raise ConnectionError("Model 704 not available for reset")
            
            m704.read()
            logger.info(f"Before reset: WSetEna={m704.WSetEna.value}, WSetPct={m704.WSetPct.value}, WSet={m704.WSet.value}")
            
            m704.WSetEna.value = 0
            m704.WSetPct.value = 0
            m704.WSet.value = 0
            
            m704.write()
            time.sleep(0.5)
            
            m704.read()
            success = (m704.WSetEna.value == 0 and m704.WSetPct.value == 0)
            
            if success:
                logger.info(f"✓ Reset successful: WSetEna={m704.WSetEna.value}, WSetPct={m704.WSetPct.value}")
            else:
                logger.warning(f"Reset verification failed: WSetEna={m704.WSetEna.value}, WSetPct={m704.WSetPct.value}")
            
            return success
        
        try:
            return self._with_retry(_do_reset, max_retries=2)
        except Exception as e:
            logger.error(f"Reset failed: {e}")
            return False
    
    def read_alarms(self) -> Dict[str, Any]:
        """
        Read all alarm registers from the aGate.
        
        Returns dict with alarm bitfields and decoded descriptions.
        """
        alarms = {
            'system_alrm': 0,
            'dc_port_alrm': 0,
            'battery_sta': 0,
            'decoded': {},
        }
        
        try:
            m701 = self.get_model(701)
            if m701 and hasattr(m701, 'Alrm'):
                alarms['system_alrm'] = m701.Alrm.value if m701.Alrm.value else 0
            
            m714 = self.get_model(714)
            if m714 and hasattr(m714, 'PrtAlrms'):
                alarms['dc_port_alrm'] = m714.PrtAlrms.value if m714.PrtAlrms.value else 0
            
            m713 = self.get_model(713)
            if m713 and hasattr(m713, 'Sta'):
                alarms['battery_sta'] = m713.Sta.value if m713.Sta.value else 0
                
        except Exception as e:
            logger.debug(f"Could not read alarms: {e}")
        
        return alarms
    
    def check_blocking_alarms(self) -> Tuple[bool, List[str]]:
        """
        Check if any alarms are blocking operation.
        
        Returns (can_operate, blocking_reasons).
        """
        alarms = self.read_alarms()
        blocking = []
        
        # Critical system alarm bits
        CRITICAL_BITS = (1 << 0) | (1 << 6) | (1 << 7) | (1 << 13) | (1 << 14)
        if alarms['system_alrm'] & CRITICAL_BITS:
            blocking.append(f"System alarm: 0x{alarms['system_alrm']:08X}")
        
        # DC port electrical faults
        if alarms['dc_port_alrm'] & 0x3F:
            blocking.append(f"DC port alarm: 0x{alarms['dc_port_alrm']:08X}")
        
        # Battery fault status
        if alarms['battery_sta'] == 6:  # FAULT
            blocking.append('BATTERY_FAULT')
        
        return len(blocking) == 0, blocking
    
    def clear_alarms(self) -> Tuple[bool, str]:
        """
        Clear alarms by writing to AlarmReset register.
        
        Writes 1 then 0 to register 41094 (Model 715).
        
        Returns (success, message).
        """
        try:
            # Check if it's safe to clear (no active critical alarms)
            can_operate, blocking = self.check_blocking_alarms()
            
            # Even if blocking alarms exist, try to clear (user may have fixed issue)
            self.dev.write_register(41094, 1)  # Write 1 to AlarmReset
            time.sleep(0.5)
            self.dev.write_register(41094, 0)  # Clear reset bit
            
            logger.info("Alarm reset command sent (wrote 1 then 0 to 41094)")
            return True, "Alarm reset command sent"
            
        except Exception as e:
            logger.error(f"Failed to clear alarms: {e}")
            return False, str(e)
    
    def check_state(self) -> Dict[str, Any]:
        """
        Check current system state and return summary.
        
        Returns dict with:
            - soc: Current state of charge
            - grid_connected: Whether grid is connected and stable
            - grid_power: Current grid power (negative = exporting)
            - grid_voltage: Grid voltage
            - battery_activity: Charging/Discharging/Idle description
            - actual_power: Current battery power from WSetPct
            - wset_ena: Control enabled state
            - ongrid_mode: Current aGate mode
            - conflicts: List of potential conflicts
            - alarms: Active alarm summary
        """
        result = {
            'soc': 0,
            'grid_connected': False,
            'grid_power': 0,
            'grid_voltage': 0,
            'battery_activity': 'Unknown',
            'actual_power': 0,
            'wset_ena': 0,
            'ongrid_mode': 'Unknown',
            'conflicts': []
        }
        
        try:
            # Battery status
            bat = self.read_battery_status()
            result['soc'] = bat.get('soc', 0)
            
            # Grid status
            grid = self.read_grid_status()
            result['grid_power'] = grid.get('grid_power_w', 0)
            result['grid_voltage'] = grid.get('voltage_v', 0)
            result['connection_state'] = grid.get('connection_state', 'Unknown')
            # Grid is connected if ConnSt=1 AND voltage in valid range
            voltage_ok = 180 < result['grid_voltage'] < 270
            conn_st_ok = result['connection_state'] == 'Connected'
            result['grid_connected'] = voltage_ok and conn_st_ok
            
            # Control status
            ctl = self.read_control_status()
            wset_ena = ctl.get('wset_enabled', 0)
            wset_pct = ctl.get('wset_pct', 0)
            result['wset_ena'] = wset_ena
            
            # Calculate actual power from WSetPct
            actual_power = (wset_pct / 100.0 * self.RATED_MAX_W) if wset_ena == 1 else 0
            result['actual_power'] = actual_power
            
            # Determine battery activity
            dc_power = bat.get('dc_power', 0) or 0
            if wset_ena == 1:
                if actual_power < -50:
                    result['battery_activity'] = f'CHARGING ({abs(actual_power):.0f}W)'
                elif actual_power > 50:
                    result['battery_activity'] = f'DISCHARGING ({actual_power:.0f}W)'
                else:
                    result['battery_activity'] = 'IDLE'
            else:
                # No Modbus control — show actual DC power from native mode
                if dc_power < -50:
                    result['battery_activity'] = f'CHARGING ({abs(dc_power):.0f}W, aGate native)'
                elif dc_power > 50:
                    result['battery_activity'] = f'DISCHARGING ({dc_power:.0f}W, aGate native)'
                else:
                    result['battery_activity'] = 'IDLE (no Modbus control)'
            
            # Native mode and reserve levels
            native = self.read_native_mode()
            if native:
                result['ongrid_mode'] = native.get('mode_name', 'Unknown')
                result['ongrid_mode_raw'] = native.get('mode_raw', -1)
                result['self_reserve_pct'] = native.get('self_reserve_pct', 20)
                result['tou_reserve_pct'] = native.get('tou_reserve_pct', 20)
                
                # Add effective reserve info
                reserve, source = self.get_effective_reserve_level()
                if reserve is not None:
                    result['effective_reserve'] = {
                        'level': reserve,
                        'source': source,
                        'min_operational': reserve + self.SAFETY_MARGIN_PCT,
                    }
            
            # Check alarms
            can_operate, blocking = self.check_blocking_alarms()
            result['alarms'] = {
                'can_operate': can_operate,
                'blocking': blocking,
                'system_alrm': self.read_alarms().get('system_alrm', 0),
            }
            
            # Check for control conflicts
            # Check BOTH wset_ena AND native mode activity (Cloud API doesn't use WSetEna)
            native_mode = result.get('ongrid_mode', 'Unknown')
            
            # Detect if aGate is actively controlling via Cloud API (WSetEna=0 but battery active)
            # Read actual battery DC power from Model 714
            m714 = self.get_model(714)
            battery_dc_power = 0
            if m714:
                try:
                    m714.read()
                    sf_w = self._get_scale_factor(m714, 'DCW_SF')
                    battery_dc_power = m714.DCW.value * (10 ** sf_w) if m714.DCW.value else 0
                except Exception:
                    pass
            
            # Conflict: aGate native mode is actively controlling
            is_active_charging = battery_dc_power < -500 or actual_power < -100
            is_active_discharging = battery_dc_power > 500 or actual_power > 100
            
            # =========================================================================
            # BAND-AID FIX: Context-aware conflict detection (Phase 3 pre-work)
            # Reduces false positives by considering solar/load/grid context
            # Full intent-based detection (Option 2) will replace this in Phase 3
            # =========================================================================
            
            # Read energy context for smarter conflict detection
            ext = self._read_extension_solar()
            solar_power = ext.get('total_solar', 0) if ext else 0
            home_load = ext.get('home_load_ext', 0) if ext else 0
            grid_power = result.get('grid_power', 0)
            
            # Add energy context to result for display
            result['energy_context'] = {
                'solar_w': solar_power,
                'home_load_w': home_load,
                'battery_dc_w': battery_dc_power,
                'grid_w': grid_power,
            }
            
            if wset_ena == 1 or is_active_charging or is_active_discharging:
                if native_mode == 'Self-Consumption':
                    if is_active_charging:
                        # Charging: Check if importing from grid (conflict) or excess solar (natural)
                        is_importing = grid_power > 500
                        is_night = solar_power < 100
                        
                        if is_importing and is_night:
                            # DEFINITE CONFLICT: Importing grid power at night to charge
                            result['conflicts'].append(
                                f"aGate importing {grid_power:.0f}W from grid to charge battery at night "
                                f"({abs(battery_dc_power or actual_power):.0f}W charge, SoC {result['soc']:.1f}%)"
                            )
                        elif is_importing:
                            # CONFLICT: Importing from grid when we might want to discharge
                            result['conflicts'].append(
                                f"aGate importing {grid_power:.0f}W to charge battery "
                                f"({abs(battery_dc_power or actual_power):.0f}W charge, solar {solar_power}W, load {home_load}W)"
                            )
                        else:
                            # Natural: Charging from excess solar - still report as info
                            result['conflicts'].append(
                                f"INFO: aGate charging {abs(battery_dc_power or actual_power):.0f}W from excess solar "
                                f"(solar {solar_power}W > load {home_load}W) - This is NORMAL Self-Consumption behavior"
                            )
                            
                    elif is_active_discharging:
                        # Discharging: Check if serving load (natural) or wasting energy (conflict)
                        if solar_power > home_load + 500:
                            # CONFLICT: Discharging despite excess solar (should be charging)
                            result['conflicts'].append(
                                f"aGate discharging {battery_dc_power or actual_power:.0f}W despite excess solar "
                                f"(solar {solar_power}W > load {home_load}W)"
                            )
                        elif home_load > solar_power + 500:
                            # Natural: Serving excess load - report as info, not conflict
                            result['conflicts'].append(
                                f"INFO: aGate discharging {battery_dc_power or actual_power:.0f}W to serve home load "
                                f"(load {home_load}W > solar {solar_power}W) - This is NORMAL Self-Consumption behavior"
                            )
                        else:
                            # Ambiguous: Balanced conditions - mild warning
                            result['conflicts'].append(
                                f"aGate Self-Consumption discharging {battery_dc_power or actual_power:.0f}W "
                                f"(solar {solar_power}W, load {home_load}W)"
                            )
                            
                elif native_mode == 'Emergency Backup' and is_active_charging:
                    result['conflicts'].append(
                        f"aGate Emergency Backup actively charging at {abs(battery_dc_power or actual_power):.0f}W"
                    )
                elif native_mode == 'Time of Use' and (is_active_charging or is_active_discharging):
                    result['conflicts'].append(
                        f"aGate TOU mode active and battery is moving ({battery_dc_power or actual_power:.0f}W)"
                    )
            
        except Exception as e:
            result['conflicts'].append(f"Could not read state: {e}")
        
        return result
    
    def healthcheck(self) -> HealthStatus:
        """Comprehensive system health check."""
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
        
        # 3. Control state
        m704 = self.get_model(704)
        m704.read()
        
        checks['wset_ena'] = m704.WSetEna.value
        checks['wset_mode'] = m704.WSetMod.value
        checks['wset'] = m704.WSet.value
        
        # Zombie state: enabled but timer expired
        checks['zombie_state'] = (
            m704.WSetEna.value == 1 and
            m704.WSetRvrtRem.value == 0 and
            m704.WSetRvrtTms.value > 0
        )
        
        if checks['zombie_state']:
            recommendations.append(
                "ZOMBIE STATE DETECTED: Use --reset-on-start to clear"
            )
        
        # 4. Battery safety
        bat = self.read_battery_status()
        checks['soc'] = bat.get('soc', 0)
        checks['soc_safe'] = 5 < checks['soc'] < 99
        
        if not checks['soc_safe']:
            recommendations.append(
                f"WARNING: SoC {checks['soc']}% outside safe range (5-99%)"
            )
        
        # 5. Grid safety and AC info
        grid = self.read_grid_status()
        checks['grid_voltage'] = grid.get('voltage_v', 0)
        checks['grid_frequency'] = grid.get('frequency_hz', 0)
        checks['ac_type'] = grid.get('ac_type', 'Unknown')
        checks['grid_connection'] = grid.get('connection_state', 'Unknown')
        checks['grid_mode'] = grid.get('grid_mode', 'Unknown')
        checks['inverter_state'] = grid.get('inverter_state', 'Unknown')
        
        # 6. Native mode and reserve levels
        native = self.read_native_mode()
        if native:
            checks['ongrid_mode'] = native.get('mode_raw', -1)
            checks['ongrid_mode_name'] = native.get('mode_name', 'Unknown')
            checks['self_reserve_pct'] = native.get('self_reserve_pct', 20)
            checks['tou_reserve_pct'] = native.get('tou_reserve_pct', 20)
            
            # Add effective reserve with safety margin info
            reserve, source = self.get_effective_reserve_level()
            if reserve is not None:
                checks['effective_reserve'] = reserve
                checks['reserve_source'] = source
                checks['min_operational_soc'] = reserve + self.SAFETY_MARGIN_PCT
                
                # Warn if current SoC is close to reserve
                soc = checks.get('soc', 0)
                reserve_distance = soc - reserve
                if reserve_distance <= self.SAFETY_MARGIN_PCT:
                    recommendations.append(
                        f"⚠️  RESERVE WARNING: Current SoC {soc}% is only {reserve_distance:.1f}% "
                        f"above {source} reserve ({reserve}%). Discharge operations limited."
                    )
        
        # 7. Nameplate info (Model 1)
        nameplate = self.read_nameplate()
        if nameplate:
            checks['nameplate'] = nameplate
        
        # 8. Alarm check
        can_operate, blocking = self.check_blocking_alarms()
        checks['blocking_alarms'] = blocking if blocking else []
        checks['can_operate'] = can_operate
        
        if not can_operate:
            healthy = False
            message = f"BLOCKING ALARMS: {', '.join(blocking)}"
            recommendations.append("Clear alarms before operating battery")
        
        # 9. Control conflict check
        if checks['wset_ena'] == 1:
            ongrid_mode = checks.get('ongrid_mode_name', 'Unknown')
            wset_val = checks.get('wset', 0)
            
            if ongrid_mode == 'Self-Consumption' and wset_val < -100:
                recommendations.append(
                    f"⚠️  CONFLICT: aGate Self-Consumption charging at {abs(wset_val)}W. "
                    f"Use --reset-on-start or set reserve lower than current SoC."
                )
            elif ongrid_mode == 'Emergency Backup' and wset_val < -100:
                recommendations.append(
                    f"⚠️  CONFLICT: aGate Emergency Backup charging at {abs(wset_val)}W. "
                    f"Use --reset-on-start or switch mode."
                )
            elif ongrid_mode == 'Time of Use':
                recommendations.append(
                    f"⚠️  CONFLICT: aGate TOU mode active. "
                    f"Use --reset-on-start to take control."
                )
        
        # 10. Extension register write test results
        ext_write = self._extension_write_results
        checks['extension_write_test'] = ext_write.get('tested', False)
        
        if ext_write.get('tested'):
            writable_regs = []
            read_only_regs = []
            
            for reg_name in ['ongrid_mode', 'self_reserve', 'tou_reserve']:
                reg_result = ext_write.get(reg_name, {})
                if reg_result.get('writable'):
                    writable_regs.append(reg_name.replace('_', ' ').title())
                else:
                    read_only_regs.append(reg_name.replace('_', ' ').title())
            
            checks['extension_writable'] = writable_regs
            checks['extension_readonly'] = read_only_regs
            
            if writable_regs:
                writable_str = ', '.join(writable_regs)
                recommendations.append(f"✓ Extension registers writable: {writable_str}")
            if read_only_regs:
                readonly_str = ', '.join(read_only_regs)
                recommendations.append(f"ℹ Extension registers read-only: {readonly_str} (requires installer unlock)")
        else:
            recommendations.append("ℹ Extension write test not completed (run --status to test)")
        
        # Determine overall health
        if any([not checks['connection'], not checks['model_704'], not checks['soc_safe']]):
            healthy = False
            message = "CRITICAL ISSUES DETECTED"
        elif checks.get('zombie_state', False):
            healthy = False
            message = "DEGRADED (zombie state)"
        else:
            healthy = True
            message = "HEALTHY"
        
        return HealthStatus(
            healthy=healthy,
            message=message,
            details=checks,
            recommendations=recommendations if recommendations else ["No action required"]
        )
