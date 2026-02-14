"""
Async Modbus TCP client for FranklinWH battery with SunSpec2 support.
Handles models 701-706, 713-715 for battery and inverter control.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from enum import IntEnum
import struct

# Import data models
from src.models import (
    BatteryMode,
    InverterStatus,
    BatteryMetrics,
    InverterACMetrics,
    DERCapacity,
    DeviceInfo,
    SolarPVMetrics,
    HomeLoadMetrics,
)

# Try multiple SunSpec library variants
SUNSPEC_AVAILABLE = False
SUNSPEC_CLIENT = None

for import_path in [
    "sunspec2.modbus.client",
    "pysunspec2.modbus.client",
]:
    try:
        module = __import__(import_path, fromlist=["SunSpecModbusClientDeviceTCP"])
        SUNSPEC_CLIENT = module.SunSpecModbusClientDeviceTCP
        SUNSPEC_AVAILABLE = True
        logging.info(f"Using SunSpec library: {import_path}")
        break
    except ImportError:
        continue

if not SUNSPEC_AVAILABLE:
    raise ImportError(
        "\n" + "="*70 + "\n"
        "REQUIRED LIBRARY MISSING: sunspec2\n"
        "="*70 + "\n"
        "The FranklinWH Battery Manager requires the sunspec2 library\n"
        "to communicate with the battery via SunSpec Modbus protocol.\n"
        "\n"
        "To install:\n"
        "  source venv/bin/activate\n"
        "  pip install pysunspec2\n"
        "\n"
        "Then run:\n"
        "  ./run.sh\n"
        "\n"
        "Or for mock mode (no real device needed):\n"
        "  ./run-mock.sh\n"
        "="*70 + "\n"
    )

try:
    from pymodbus.client import ModbusTcpClient
    from pymodbus.exceptions import ModbusException
except ImportError:
    from pymodbus.client.tcp import ModbusTcpClient
    from pymodbus.exceptions import ModbusException


class BatteryMode(IntEnum):
    """Battery operating modes."""
    IDLE = 0
    CHARGING = 1
    DISCHARGING = 2


class InverterStatus(IntEnum):
    """Inverter status codes."""
    OFF = 1
    SLEEPING = 2
    STARTING = 3
    MPPT = 4
    THROTTLED = 5
    SHUTTING_DOWN = 6
    FAULT = 7
    STANDBY = 8


@dataclass
class BatteryMetrics:
    """Battery metrics from Model 713/714."""
    rated_energy_wh: Optional[float] = None
    available_energy_wh: Optional[float] = None
    state_of_charge_percent: Optional[float] = None
    state_of_health_percent: Optional[float] = None
    status: Optional[int] = None
    status_text: str = "Unknown"
    temperature_c: Optional[float] = None
    cycle_count: Optional[int] = None
    # Model 714 additions - DC power and energy
    dc_power_w: Optional[float] = None  # Model 714.DCW - instantaneous DC power (+ = discharge, - = charge)
    dc_energy_injected_wh: Optional[float] = None  # Total discharged from battery
    dc_energy_absorbed_wh: Optional[float] = None  # Total charged to battery


@dataclass
class SolarPVMetrics:
    """Solar PV metrics from Model 502."""
    output_power_w: Optional[float] = None        # Current PV power output
    output_energy_wh: Optional[float] = None      # Lifetime PV energy produced


@dataclass
class HomeLoadMetrics:
    """Home load metrics from FranklinWH extension registers (15500+)."""
    home_loads_w: Optional[float] = None          # 15506: Home Loads Active Power W
    pv_output_w: Optional[float] = None           # 15502: PV Output Power W
    pv_proximal_w: Optional[float] = None         # 15503: Proximal PV Output W
    remote1_pv_w: Optional[float] = None          # 15504: Remote1 PV W
    remote2_pv_w: Optional[float] = None          # 15505: Remote2 PV W
    pv_output_wh: Optional[float] = None          # 15510-15511: PV Output Energy Wh (int64)
    pv_proximal_wh: Optional[float] = None        # 15512-15513: Proximal PV Energy Wh (int64)


@dataclass
class InverterACMetrics:
    """AC inverter metrics from Model 701."""
    # Power measurements
    power_w: Optional[float] = None           # W - Active Power
    voltage_v: Optional[float] = None         # PhV/LNV/VL1 - Phase Voltage
    current_a: Optional[float] = None         # A - Total AC Current
    frequency_hz: Optional[float] = None      # Hz - Frequency
    apparent_power_va: Optional[float] = None # VA - Apparent Power
    reactive_power_var: Optional[float] = None # VAR - Reactive Power
    power_factor: Optional[float] = None      # PF - Power Factor
    
    # Status and wiring (from Model 701)
    ac_type: Optional[int] = None             # ACType - AC Wiring Type (enum16)
    ac_type_text: Optional[str] = None        # Human-readable AC type
    operating_state: Optional[int] = None     # St - Operating State (enum16)
    operating_state_text: Optional[str] = None
    inverter_state: Optional[int] = None      # InvSt - Inverter State (enum16)
    inverter_state_text: Optional[str] = None
    grid_connection_state: Optional[int] = None  # ConnSt - Grid Connection State (enum16)
    grid_connection_state_text: Optional[str] = None
    alarm: Optional[int] = None               # Alrm - Alarm Bitfield (bitfield32)
    alarm_text: Optional[str] = None          # Human-readable alarm summary
    der_mode: Optional[int] = None            # DERMode - DER Operational Characteristics (bitfield32)
    der_mode_text: Optional[str] = None       # Human-readable DER mode
    
    # Temperatures
    ambient_temperature_c: Optional[float] = None  # TmpAmb
    cabinet_temperature_c: Optional[float] = None  # TmpCab
    
    # Lifetime energy
    total_energy_injected_wh: Optional[float] = None  # TotWhInj
    total_energy_absorbed_wh: Optional[float] = None  # TotWhAbs


@dataclass
class DERCapacity:
    """DER capacity from Model 703."""
    max_charge_w: Optional[float] = None
    max_discharge_w: Optional[float] = None
    max_charge_va: Optional[float] = None
    max_discharge_va: Optional[float] = None


@dataclass
class DeviceInfo:
    """Device information from Model 1."""
    manufacturer: str = "Unknown"
    model: str = "Unknown"
    version: str = "Unknown"
    serial_number: str = "Unknown"
    device_address: Optional[int] = None


class FranklinWHModbusClient:
    """
    Async Modbus TCP client for FranklinWH battery system.
    Supports SunSpec2 models 502, 701-706, 713-715.
    """
    
    # Model definitions
    MODEL_COMMON = 1
    MODEL_SOLAR_PV = 502           # Solar PV module
    MODEL_DER_MEASURE_AC = 701
    MODEL_DER_MEASURE_DC = 702
    MODEL_DER_CAPACITY = 703
    MODEL_DER_ENTER_SERVICE = 704
    MODEL_DER_CTL_AC = 705
    MODEL_DER_VOLT_VAR_WATT = 706
    MODEL_DER_STORAGE_CAPACITY = 713
    MODEL_DER_STORAGE_STATUS = 714
    MODEL_DER_STORAGE_CTL = 715
    
    def __init__(
        self,
        host: str = "192.168.0.110",
        port: int = 502,
        unit_id: int = 2,
        base_address: int = 40000,
        timeout: float = 5.0,
    ):
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.base_address = base_address
        self.timeout = timeout
        
        self._client: Optional[ModbusTcpClient] = None
        self._sunspec_client: Optional[Any] = None
        self._lock = asyncio.Lock()
        self._connected = False
        self._model_cache: Dict[int, Any] = {}
        self._last_read: Dict[int, float] = {}
        self._cache_ttl = 5.0  # seconds
        
        self._logger = logging.getLogger(__name__)
        
        # Callbacks for data updates
        self._data_callbacks: List[Callable[[str, Any], None]] = []
    
    def add_data_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Add callback for data updates."""
        self._data_callbacks.append(callback)
    
    def remove_data_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Remove data callback."""
        if callback in self._data_callbacks:
            self._data_callbacks.remove(callback)
    
    async def _notify_callbacks(self, data_type: str, data: Any) -> None:
        """Notify all callbacks of new data."""
        for callback in self._data_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data_type, data)
                else:
                    callback(data_type, data)
            except Exception as e:
                self._logger.error(f"Callback error: {e}")
    
    async def _safe_operation(self, operation, operation_name: str, timeout: float = None):
        """Execute Modbus operation with timeout and error handling.
        
        Prevents infinite loops on WiFi drops by:
        - Adding timeout protection
        - Catching broken pipe and connection errors
        - Marking connection as failed for auto-recovery
        
        Args:
            operation: Async callable to execute
            operation_name: Name for logging
            timeout: Operation timeout (defaults to self.timeout)
        
        Returns:
            Operation result or None on timeout/error
        """
        if timeout is None:
            timeout = self.timeout
        
        try:
            return await asyncio.wait_for(operation(), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.error(f"{operation_name} timed out after {timeout}s")
            self._connected = False  # Mark as disconnected for reconnect task
            return None
        except (BrokenPipeError, ConnectionError, OSError) as e:
            self._logger.error(f"{operation_name} connection error: {e}")
            self._connected = False  # Mark as disconnected for reconnect task
            return None
        except Exception as e:
            # Check if it's a socket/connection error wrapped by pymodbus
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ['broken pipe', 'socket', 'connection', 'errno 32']):
                self._logger.error(f"{operation_name} connection error: {e}")
                self._connected = False  # Mark as disconnected for reconnect task
                return None
            else:
                self._logger.error(f"{operation_name} unexpected error: {e}")
                return None
    
    async def connect(self) -> bool:
        """Establish connection to Modbus device."""
        async with self._lock:
            try:
                # Try SunSpec2 first if available
                if SUNSPEC_AVAILABLE and SUNSPEC_CLIENT:
                    self._sunspec_client = SUNSPEC_CLIENT(
                        slave_id=self.unit_id,
                        ipaddr=self.host,
                        ipport=self.port,
                        timeout=self.timeout,
                    )
                    # Scan for models - try different API versions
                    try:
                        await asyncio.get_event_loop().run_in_executor(
                            None, lambda: self._sunspec_client.scan(base_addr=self.base_address)
                        )
                    except TypeError:
                        try:
                            await asyncio.get_event_loop().run_in_executor(
                                None, lambda: self._sunspec_client.scan(self.base_address)
                            )
                        except TypeError:
                            await asyncio.get_event_loop().run_in_executor(
                                None, self._sunspec_client.scan
                            )
                    self._connected = True
                    self._logger.info(f"Connected via SunSpec2 to {self.host}:{self.port}")
                    return True
                
                # Fallback to raw Modbus
                self._client = ModbusTcpClient(
                    host=self.host,
                    port=self.port,
                    timeout=self.timeout,
                )
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self._client.connect
                )
                self._connected = result
                if result:
                    self._logger.info(f"Connected via raw Modbus to {self.host}:{self.port}")
                return result
                
            except Exception as e:
                self._logger.error(f"Connection failed: {e}")
                self._connected = False
                return False
    
    async def disconnect(self) -> None:
        """Close connection and clear all cached state."""
        async with self._lock:
            self._connected = False
            
            # Clear model cache to force fresh reads after reconnect
            self._model_cache.clear()
            self._last_read.clear()
            
            if self._sunspec_client:
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._sunspec_client.close
                    )
                except Exception as e:
                    self._logger.debug(f"Error closing SunSpec client: {e}")
                finally:
                    self._sunspec_client = None
            
            if self._client:
                try:
                    # Force close the socket
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._client.close
                    )
                except Exception as e:
                    self._logger.debug(f"Error closing Modbus client: {e}")
                finally:
                    self._client = None
            
            self._logger.info("Disconnected and cleared connection state")
                    
    def close(self) -> None:
        """Sync wrapper to close connection."""
        if self._connected:
            asyncio.create_task(self.disconnect())
    
    async def _get_raw_client(self) -> Optional[ModbusTcpClient]:
        """Get or create raw client for extension reading."""
        if self._client:
            return self._client
            
        async with self._lock:
            # Check again under lock
            if self._client:
                return self._client
                
            # Create temporary raw client sharing connection params
            try:
                client = ModbusTcpClient(
                    host=self.host,
                    port=self.port,
                    timeout=self.timeout,
                )
                connected = await asyncio.get_event_loop().run_in_executor(
                    None, client.connect
                )
                if connected:
                    self._client = client
                    return client
            except Exception as e:
                self._logger.error(f"Failed to create fallback raw client: {e}")
                return None
        return None

    async def read_model(self, model_id: int, force: bool = False) -> Optional[Any]:
        """
        Read a SunSpec model with timeout protection.
        
        Args:
            model_id: SunSpec model ID
            force: Force re-read even if cache is valid
        
        Returns:
            Model data or None if not available
        """
        # Check cache
        now = asyncio.get_event_loop().time()
        if not force and model_id in self._last_read:
            if now - self._last_read[model_id] < self._cache_ttl:
                return self._model_cache.get(model_id)
        
        async with self._lock:
            if not self._connected:
                if not await self.connect():
                    return None
            
            # Define the read operation
            async def _do_read():
                if self._sunspec_client:
                    # SunSpec2 read
                    model = self._sunspec_client.models.get(model_id)
                    if model is None:
                        model = self._sunspec_client.models.get(str(model_id))
                    
                    if model is None:
                        self._logger.debug(f"Model {model_id} not found")
                        return None
                    
                    # Handle list of models
                    if isinstance(model, list):
                        if len(model) == 0:
                            return None
                        model = model[0]
                    
                    # Read model data
                    await asyncio.get_event_loop().run_in_executor(None, model.read)
                    return model
                else:
                    # Raw Modbus read - would need manual register mapping
                    self._logger.warning("Raw Modbus model reading not implemented")
                    return None
            
            # Use safe wrapper with 2x timeout for model reads
            model = await self._safe_operation(
                _do_read,
                f"read_model({model_id})",
                timeout=self.timeout * 2
            )
            
            if model is not None:
                self._model_cache[model_id] = model
                self._last_read[model_id] = now
            
            return model
    
    async def get_device_info(self) -> Optional[DeviceInfo]:
        """Read device information from Model 1."""
        model = await self.read_model(self.MODEL_COMMON)
        if model is None:
            return None
        
        try:
            info = DeviceInfo()
            
            # Extract fields with fallbacks
            if hasattr(model, 'Mn'):
                info.manufacturer = str(getattr(model.Mn, 'value', 'Unknown'))
            if hasattr(model, 'Md'):
                info.model = str(getattr(model.Md, 'value', 'Unknown'))
            if hasattr(model, 'Vr'):
                info.version = str(getattr(model.Vr, 'value', 'Unknown'))
            if hasattr(model, 'SN'):
                info.serial_number = str(getattr(model.SN, 'value', 'Unknown'))
            if hasattr(model, 'DA'):
                info.device_address = getattr(model.DA, 'value', None)
            
            await self._notify_callbacks("device_info", info)
            return info
            
        except Exception as e:
            self._logger.error(f"Error parsing device info: {e}")
            return None
    
    async def get_battery_metrics(self) -> Optional[BatteryMetrics]:
        """Read battery metrics from Models 713 and 714."""
        metrics = BatteryMetrics()
        
        # Model 713: Storage Capacity
        model713 = await self.read_model(self.MODEL_DER_STORAGE_CAPACITY)
        
        # Model 714: Storage Status (if available)
        model714 = await self.read_model(self.MODEL_DER_STORAGE_STATUS)
        
        # Initialize scale factors
        wh_sf = 0
        pct_sf = 0
        dcw_sf = 0
        dcwh_sf = 0
        tmp_sf = 0

        # Get scale factors from Model 713 first
        if model713:
            try:
                if hasattr(model713, 'WH_SF'):
                    wh_sf = getattr(model713.WH_SF, 'value', 0) or 0
                if hasattr(model713, 'Pct_SF'):
                    pct_sf = getattr(model713.Pct_SF, 'value', 0) or 0
            except Exception as e:
                self._logger.error(f"Error parsing scale factors from model 713: {e}")

        # Get scale factors from Model 714 (can override/supplement 713)
        if model714:
            try:
                if hasattr(model714, 'DCW_SF'):
                    dcw_sf = getattr(model714.DCW_SF, 'value', 0) or 0
                if hasattr(model714, 'DCWH_SF'):
                    dcwh_sf = getattr(model714.DCWH_SF, 'value', 0) or 0
                if hasattr(model714, 'Tmp_SF'):
                    tmp_sf = getattr(model714.Tmp_SF, 'value', 0) or 0
            except Exception as e:
                self._logger.error(f"Error parsing scale factors from model 714: {e}")

        if model713:
            try:
                # Read values with scaling from Model 713
                if hasattr(model713, 'WHRtg'):
                    val = getattr(model713.WHRtg, 'value', None)
                    if val is not None:
                        metrics.rated_energy_wh = val * (10 ** wh_sf)
                
                if hasattr(model713, 'WHAvail'):
                    val = getattr(model713.WHAvail, 'value', None)
                    if val is not None:
                        metrics.available_energy_wh = val * (10 ** wh_sf)
                
                if hasattr(model713, 'SoC'):
                    val = getattr(model713.SoC, 'value', None)
                    if val is not None:
                        metrics.state_of_charge_percent = val * (10 ** pct_sf)
                
                if hasattr(model713, 'SoH'):
                    val = getattr(model713.SoH, 'value', None)
                    if val is not None:
                        metrics.state_of_health_percent = val * (10 ** pct_sf)
                
                # Status from Model 713 (fallback if not in 714)
                if hasattr(model713, 'Sta') and metrics.status is None:
                    status = getattr(model713.Sta, 'value', None)
                    if status is not None:
                        metrics.status = status
                        # Map status to text
                        status_map = {0: "OK", 1: "Warning", 2: "Error"}
                        metrics.status_text = status_map.get(status, f"Unknown({status})")
                        
            except Exception as e:
                self._logger.error(f"Error parsing model 713: {e}")
        
        # Model 714: Storage Status (if available)
        model714 = await self.read_model(self.MODEL_DER_STORAGE_STATUS)
        if model714:
            try:
                # Get scale factors for DC values
                dcw_sf = 0
                dcwh_sf = 0
                tmp_sf = 0
                
                if hasattr(model714, 'DCW_SF'):
                    dcw_sf = getattr(model714.DCW_SF, 'value', 0) or 0
                if hasattr(model714, 'DCWH_SF'):
                    dcwh_sf = getattr(model714.DCWH_SF, 'value', 0) or 0
                if hasattr(model714, 'Tmp_SF'):
                    tmp_sf = getattr(model714.Tmp_SF, 'value', 0) or 0
                
                # Try different temperature field names (Tmp, TmpBat)
                temp_val = None
                if hasattr(model714, 'Tmp'):
                    temp_val = getattr(model714.Tmp, 'value', None)
                elif hasattr(model714, 'TmpBat'):
                    temp_val = getattr(model714.TmpBat, 'value', None)
                
                if temp_val is not None:
                    temp = temp_val * (10 ** tmp_sf)
                    # If temperature is unrealistically high (>150°C), assume it's in tenths of degrees
                    if temp > 150:
                        temp = temp_val / 10.0
                    metrics.temperature_c = temp
                
                # DC Power - instantaneous (Model 714.DCW)
                # Positive = discharging, Negative = charging
                if hasattr(model714, 'DCW'):
                    val = getattr(model714.DCW, 'value', None)
                    if val is not None:
                        metrics.dc_power_w = val * (10 ** dcw_sf)
                
                if hasattr(model714, 'CyC'):
                    metrics.cycle_count = getattr(model714.CyC, 'value', None)
                
                # DC Energy Lifetime (Model 714 additions)
                # DCWhInj = Energy injected (discharged from battery)
                # DCWhAbs = Energy absorbed (charged to battery)
                if hasattr(model714, 'DCWhInj'):
                    val = getattr(model714.DCWhInj, 'value', None)
                    if val is not None:
                        # uint64 - may need special handling
                        if isinstance(val, (list, tuple)) and len(val) == 2:
                            # Handle as two uint32 words
                            high, low = val
                            val = (high << 32) | low
                        metrics.dc_energy_injected_wh = val * (10 ** dcwh_sf)
                
                if hasattr(model714, 'DCWhAbs'):
                    val = getattr(model714.DCWhAbs, 'value', None)
                    if val is not None:
                        if isinstance(val, (list, tuple)) and len(val) == 2:
                            high, low = val
                            val = (high << 32) | low
                        metrics.dc_energy_absorbed_wh = val * (10 ** dcwh_sf)
                    
            except Exception as e:
                self._logger.error(f"Error parsing model 714: {e}")
        
        await self._notify_callbacks("battery_metrics", metrics)
        return metrics
    
    async def get_inverter_ac_metrics(self) -> Optional[InverterACMetrics]:
        """Read AC inverter metrics from Model 701."""
        model = await self.read_model(self.MODEL_DER_MEASURE_AC)
        if model is None:
            return None
        
        metrics = InverterACMetrics()
        
        try:
            # Get scale factors
            a_sf = v_sf = w_sf = va_sf = var_sf = pf_sf = hz_sf = 0
            
            if hasattr(model, 'A_SF'): a_sf = getattr(model.A_SF, 'value', 0) or 0
            if hasattr(model, 'V_SF'): v_sf = getattr(model.V_SF, 'value', 0) or 0
            if hasattr(model, 'W_SF'): w_sf = getattr(model.W_SF, 'value', 0) or 0
            if hasattr(model, 'VA_SF'): va_sf = getattr(model.VA_SF, 'value', 0) or 0
            if hasattr(model, 'VAR_SF'): var_sf = getattr(model.VAR_SF, 'value', 0) or 0
            if hasattr(model, 'PF_SF'): pf_sf = getattr(model.PF_SF, 'value', 0) or 0
            if hasattr(model, 'Hz_SF'): hz_sf = getattr(model.Hz_SF, 'value', 0) or 0
            
            # Read values
            if hasattr(model, 'W'):
                val = getattr(model.W, 'value', None)
                if val is not None:
                    metrics.power_w = val * (10 ** w_sf)
            
            # Try PhV (Phase Voltage Average) first, then LNV (Phase-Neutral Average), then VL1 (Phase A Voltage)
            if hasattr(model, 'PhV') and getattr(model.PhV, 'value', None) is not None:
                metrics.voltage_v = getattr(model.PhV, 'value') * (10 ** v_sf)
            elif hasattr(model, 'LNV') and getattr(model.LNV, 'value', None) is not None:
                metrics.voltage_v = getattr(model.LNV, 'value') * (10 ** v_sf)
            elif hasattr(model, 'VL1') and getattr(model.VL1, 'value', None) is not None:
                metrics.voltage_v = getattr(model.VL1, 'value') * (10 ** v_sf)
            
            if hasattr(model, 'A'):
                val = getattr(model.A, 'value', None)
                if val is not None:
                    metrics.current_a = val * (10 ** a_sf)
            
            if hasattr(model, 'Hz'):
                val = getattr(model.Hz, 'value', None)
                if val is not None:
                    metrics.frequency_hz = val * (10 ** hz_sf)
            
            if hasattr(model, 'VA'):
                val = getattr(model.VA, 'value', None)
                if val is not None:
                    metrics.apparent_power_va = val * (10 ** va_sf)
            
            # Note: SunSpec uses 'Var' not 'VAR'
            if hasattr(model, 'Var'):
                val = getattr(model.Var, 'value', None)
                if val is not None:
                    metrics.reactive_power_var = val * (10 ** var_sf)
            
            if hasattr(model, 'PF'):
                val = getattr(model.PF, 'value', None)
                if val is not None:
                    metrics.power_factor = val * (10 ** pf_sf)
            
            # Temperatures (Model 701) - check for Tmp_SF, fallback to /10 if values are suspiciously high
            tmp_sf = 0
            if hasattr(model, 'Tmp_SF'): 
                tmp_sf = getattr(model.Tmp_SF, 'value', 0) or 0
            
            if hasattr(model, 'TmpAmb'):
                val = getattr(model.TmpAmb, 'value', None)
                if val is not None:
                    temp = val * (10 ** tmp_sf)
                    # If temperature is unrealistically high (>150°C), assume it's in tenths of degrees
                    if temp > 150:
                        temp = val / 10.0
                    metrics.ambient_temperature_c = temp
            
            if hasattr(model, 'TmpCab'):
                val = getattr(model.TmpCab, 'value', None)
                if val is not None:
                    temp = val * (10 ** tmp_sf)
                    # If temperature is unrealistically high (>150°C), assume it's in tenths of degrees
                    if temp > 150:
                        temp = val / 10.0
                    metrics.cabinet_temperature_c = temp
            
            # AC Wiring Type (Model 701)
            # Default to Single Phase for residential systems when Unknown
            AC_TYPE_MAP = {
                0: "Single Phase",  # Default from "Unknown" for residential
                1: "Single Phase (1P)", 2: "Split Phase (1PN)", 
                3: "Three Phase (3P)", 4: "Three Phase with Neutral (3PN)",
                5: "Three Phase with Split Neutral (3PS)", 6: "Three Phase Corner Grounded (3PG)",
                7: "Two Phase (2P)", 8: "Two Phase with Neutral (2PN)",
                9: "Direct Current (DC)", 10: "Single Phase with Neutral (1PNS)"
            }
            if hasattr(model, 'ACType'):
                val = getattr(model.ACType, 'value', None)
                if val is not None:
                    metrics.ac_type = val
                    # Default 0 (Unknown) to Single Phase for residential
                    display_val = val if val in AC_TYPE_MAP else 0
                    metrics.ac_type_text = AC_TYPE_MAP.get(display_val, f"Unknown ({val})")
                else:
                    # No value present - assume single phase residential
                    metrics.ac_type = 1
                    metrics.ac_type_text = "Single Phase"
            else:
                # Field not present - assume single phase residential
                metrics.ac_type = 1
                metrics.ac_type_text = "Single Phase"
            
            # Operating State (Model 701)
            OP_STATE_MAP = {
                0: "Unknown", 1: "Off", 2: "Sleeping", 3: "Starting", 
                4: "Running/MPPT", 5: "Throttled", 6: "Shutting Down", 
                7: "Fault", 8: "Standby"
            }
            if hasattr(model, 'St'):
                val = getattr(model.St, 'value', None)
                if val is not None:
                    metrics.operating_state = val
                    metrics.operating_state_text = OP_STATE_MAP.get(val, f"Unknown ({val})")
            
            # Status enums (Model 701)
            INV_STATE_MAP = {
                1: "Off", 2: "Sleeping", 3: "Starting", 4: "MPPT", 5: "Throttled",
                6: "Shutting Down", 7: "Fault", 8: "Standby", 9: "Remote Shutdown"
            }
            if hasattr(model, 'InvSt'):
                val = getattr(model.InvSt, 'value', None)
                if val is not None:
                    metrics.inverter_state = val
                    metrics.inverter_state_text = INV_STATE_MAP.get(val, f"Unknown ({val})")
            
            CONN_STATE_MAP = {
                0: "Disconnected", 1: "Connected"
            }
            if hasattr(model, 'ConnSt'):
                val = getattr(model.ConnSt, 'value', None)
                if val is not None:
                    metrics.grid_connection_state = val
                    metrics.grid_connection_state_text = CONN_STATE_MAP.get(val, f"Unknown ({val})")
            
            # Alarm Bitfield (Model 701) - bitfield32
            # Bit meanings per SunSpec:
            # 0: Ground fault, 1: DC over voltage, 2: AC disconnect open, 3: DC disconnect open
            # 4: Grid disconnect, 5: Cabinet open, 6: Manual shutdown, 7: Over temperature
            # 8: Over frequency, 9: Under frequency, 10: AC over voltage, 11: AC under voltage
            # 12: Blown string fuse, 13: Under temperature, 14: Memory loss, 15: HW test failure
            if hasattr(model, 'Alrm'):
                val = getattr(model.Alrm, 'value', None)
                if val is not None:
                    metrics.alarm = val
                    # Decode active alarms
                    alarm_bits = []
                    if val & 0x0001: alarm_bits.append("Ground Fault")
                    if val & 0x0002: alarm_bits.append("DC Over Voltage")
                    if val & 0x0004: alarm_bits.append("AC Disconnect")
                    if val & 0x0008: alarm_bits.append("DC Disconnect")
                    if val & 0x0010: alarm_bits.append("Grid Disconnect")
                    if val & 0x0020: alarm_bits.append("Cabinet Open")
                    if val & 0x0040: alarm_bits.append("Manual Shutdown")
                    if val & 0x0080: alarm_bits.append("Over Temperature")
                    if val & 0x0100: alarm_bits.append("Over Frequency")
                    if val & 0x0200: alarm_bits.append("Under Frequency")
                    if val & 0x0400: alarm_bits.append("AC Over Voltage")
                    if val & 0x0800: alarm_bits.append("AC Under Voltage")
                    if val & 0x1000: alarm_bits.append("String Fuse")
                    if val & 0x2000: alarm_bits.append("Under Temperature")
                    if val & 0x4000: alarm_bits.append("Memory Loss")
                    if val & 0x8000: alarm_bits.append("HW Test Failure")
                    metrics.alarm_text = ", ".join(alarm_bits) if alarm_bits else "None"
            
            # DER Mode (Model 701) - bitfield32
            # Bit meanings per SunSpec:
            # 0: PV connected, 1: Energy storage connected, 2: Reserved
            # 3: ECP connected, 4: IT islanding, 5: Reserved
            # 6: Intentional islanding (ECS), 7: Unintentional islanding
            if hasattr(model, 'DERMode'):
                val = getattr(model.DERMode, 'value', None)
                if val is not None:
                    metrics.der_mode = val
                    mode_bits = []
                    if val & 0x0001: mode_bits.append("PV")
                    if val & 0x0002: mode_bits.append("Storage")
                    if val & 0x0008: mode_bits.append("ECP")
                    if val & 0x0010: mode_bits.append("IT Islanding")
                    if val & 0x0040: mode_bits.append("ECS Islanding")
                    if val & 0x0080: mode_bits.append("Unint. Islanding")
                    metrics.der_mode_text = ", ".join(mode_bits) if mode_bits else "None"
            
            # Lifetime energy (Model 701) - scale factor needed
            wh_sf = 0
            if hasattr(model, 'TotWh_SF'): 
                wh_sf = getattr(model.TotWh_SF, 'value', 0) or 0
            
            if hasattr(model, 'TotWhInj'):
                val = getattr(model.TotWhInj, 'value', None)
                if val is not None:
                    metrics.total_energy_injected_wh = val * (10 ** wh_sf)
            
            if hasattr(model, 'TotWhAbs'):
                val = getattr(model.TotWhAbs, 'value', None)
                if val is not None:
                    metrics.total_energy_absorbed_wh = val * (10 ** wh_sf)
            
            await self._notify_callbacks("inverter_ac", metrics)
            return metrics
            
        except Exception as e:
            self._logger.error(f"Error parsing AC metrics: {e}")
            return None
    
    async def get_der_capacity(self) -> Optional[DERCapacity]:
        """Read DER capacity from Model 703."""
        model = await self.read_model(self.MODEL_DER_CAPACITY)
        if model is None:
            return None
        
        capacity = DERCapacity()
        
        try:
            # Get scale factors
            w_sf = va_sf = 0
            
            if hasattr(model, 'WChaMax_SF'): 
                w_sf = getattr(model.WChaMax_SF, 'value', 0) or 0
            if hasattr(model, 'VAChaMax_SF'): 
                va_sf = getattr(model.VAChaMax_SF, 'value', 0) or 0
            
            # Max charge/discharge power
            if hasattr(model, 'WChaMax'):
                val = getattr(model.WChaMax, 'value', None)
                if val is not None:
                    capacity.max_charge_w = val * (10 ** w_sf)
            
            if hasattr(model, 'WDisChaMax'):
                val = getattr(model.WDisChaMax, 'value', None)
                if val is not None:
                    capacity.max_discharge_w = val * (10 ** w_sf)
            
            if hasattr(model, 'VAChaMax'):
                val = getattr(model.VAChaMax, 'value', None)
                if val is not None:
                    capacity.max_charge_va = val * (10 ** va_sf)
            
            if hasattr(model, 'VADisChaMax'):
                val = getattr(model.VADisChaMax, 'value', None)
                if val is not None:
                    capacity.max_discharge_va = val * (10 ** va_sf)
            
            await self._notify_callbacks("der_capacity", capacity)
            return capacity
            
        except Exception as e:
            self._logger.error(f"Error parsing DER capacity: {e}")
            return None
    
    async def get_solar_pv_metrics(self) -> Optional[SolarPVMetrics]:
        """Read Solar PV metrics from Model 502."""
        model = await self.read_model(self.MODEL_SOLAR_PV)
        if model is None:
            return None
        
        metrics = SolarPVMetrics()
        
        try:
            # Get scale factors
            wh_sf = 0
            w_sf = 0
            
            if hasattr(model, 'OutWh_SF'):
                wh_sf = getattr(model.OutWh_SF, 'value', 0) or 0
            if hasattr(model, 'OutPw_SF'):
                w_sf = getattr(model.OutPw_SF, 'value', 0) or 0
            
            # Output Energy (lifetime)
            if hasattr(model, 'OutWh'):
                val = getattr(model.OutWh, 'value', None)
                if val is not None:
                    # acc32 - may need special handling for large values
                    if isinstance(val, (list, tuple)) and len(val) == 2:
                        high, low = val
                        val = (high << 16) | low
                    metrics.output_energy_wh = val * (10 ** wh_sf)
            
            # Output Power (current)
            if hasattr(model, 'OutPw'):
                val = getattr(model.OutPw, 'value', None)
                if val is not None:
                    metrics.output_power_w = val * (10 ** w_sf)
            
            await self._notify_callbacks("solar_pv", metrics)
            return metrics
            
        except Exception as e:
            self._logger.error(f"Error parsing Solar PV metrics: {e}")
            return None
    
    async def get_home_load_metrics(self) -> Optional[HomeLoadMetrics]:
        """
        Read Home Load metrics from FranklinWH extension registers (15500+).
        These are raw Modbus registers, not SunSpec models.
        """
        metrics = HomeLoadMetrics()
        
        # Use raw Modbus client to read extension registers
        client = await self._get_raw_client()
        if not client:
            return metrics  # Return empty if no raw client
        
        try:
            # Read block from 15500 (14 registers covers 15500-15513)
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.read_holding_registers(
                    address=15500,
                    count=14,
                    device_id=self.unit_id
                )
            )
            
            if result.isError():
                self._logger.debug("Could not read home load extension registers")
                return metrics
            
            regs = result.registers
            
            # Parse registers according to FranklinWH extension map
            # 15500: PV Installed
            # 15501: apBox PV Installed  
            # 15502: PV Output Power W
            # 15503: Proximal PV Output W
            # 15504: Remote1 PV W
            # 15505: Remote2 PV W
            # 15506: Home Loads Active Power W
            # 15507: Operating Mode
            # 15508: Self-Consumption Reserve %
            # 15509: Time-of-Use Reserve %
            # 15510-15511: PV Output Wh (uint64)
            # 15512-15513: Proximal PV Output Wh (uint64)
            
            if len(regs) >= 7:
                metrics.pv_output_w = regs[2]
                metrics.pv_proximal_w = regs[3]
                metrics.remote1_pv_w = regs[4]
                metrics.remote2_pv_w = regs[5]
                metrics.home_loads_w = regs[6]
            
            if len(regs) >= 12:
                # Combine two uint16 into uint64 for energy
                # 15510 (high) + 15511 (low)
                pv_output_wh = (regs[10] << 16) | regs[11]
                metrics.pv_output_wh = pv_output_wh if pv_output_wh != 0 else None
            
            if len(regs) >= 14:
                # 15512 (high) + 15513 (low)
                pv_proximal_wh = (regs[12] << 16) | regs[13]
                metrics.pv_proximal_wh = pv_proximal_wh if pv_proximal_wh != 0 else None
            
            await self._notify_callbacks("home_loads", metrics)
            return metrics
            
        except Exception as e:
            self._logger.debug(f"Error reading home load registers: {e}")
            return metrics
    
    async def set_battery_mode(self, mode: BatteryMode) -> bool:
        """
        Set battery operating mode.
        
        Args:
            mode: Target battery mode
        
        Returns:
            True if successful
        """
        # Model 715: Storage Controls
        model = await self.read_model(self.MODEL_DER_STORAGE_CTL, force=True)
        if model is None:
            self._logger.error("Model 715 not available for control")
            return False
        
        try:
            # Map mode to control values
            # This depends on specific FranklinWH implementation
            # Typically involves setting WChaMax or WDisChaMax to 0
            
            if mode == BatteryMode.IDLE:
                # Set both charge and discharge to 0
                success = await self._write_point(model, 'WChaMax', 0)
                success = success and await self._write_point(model, 'WDisChaMax', 0)
                
            elif mode == BatteryMode.CHARGING:
                # Enable charging, disable discharging
                # Use max charge rate
                capacity = await self.get_der_capacity()
                max_charge = int(capacity.max_charge_w / 10) if capacity and capacity.max_charge_w else 10000
                success = await self._write_point(model, 'WChaMax', max_charge)
                success = success and await self._write_point(model, 'WDisChaMax', 0)
                
            elif mode == BatteryMode.DISCHARGING:
                # Enable discharging, disable charging
                capacity = await self.get_der_capacity()
                max_discharge = int(capacity.max_discharge_w / 10) if capacity and capacity.max_discharge_w else 10000
                success = await self._write_point(model, 'WChaMax', 0)
                success = success and await self._write_point(model, 'WDisChaMax', max_discharge)
            
            else:
                return False
            
            # Trigger write
            if hasattr(model, 'write'):
                await asyncio.get_event_loop().run_in_executor(None, model.write)
            
            self._logger.info(f"Set battery mode to {mode.name}")
            return success
            
        except Exception as e:
            self._logger.error(f"Error setting battery mode: {e}")
            return False
    
    async def set_discharge_power(self, power_w: float, unit: str = "w") -> bool:
        """
        Set discharge power limit.
        
        Args:
            power_w: Power value
            unit: "w" (watts), "kw" (kilowatts), "a" (amps), or "%" (percent)
        
        Returns:
            True if successful
        """
        # Convert to watts if needed
        if unit.lower() == "kw":
            power_w = power_w * 1000
        elif unit.lower() == "a":
            # Need voltage for conversion
            metrics = await self.get_inverter_ac_metrics()
            if metrics and metrics.voltage_v:
                power_w = power_w * metrics.voltage_v
            else:
                self._logger.error("Cannot convert amps to watts: no voltage reading")
                return False
        elif unit == "%":
            # Percent of max discharge
            capacity = await self.get_der_capacity()
            if capacity and capacity.max_discharge_w:
                power_w = (power_w / 100) * capacity.max_discharge_w
            else:
                self._logger.error("Cannot use percent: no capacity reading")
                return False
        
        model = await self.read_model(self.MODEL_DER_STORAGE_CTL, force=True)
        if model is None:
            return False
        
        try:
            # Get scale factor for writing
            w_sf = 0
            if hasattr(model, 'WDisChaMax_SF'):
                w_sf = getattr(model.WDisChaMax_SF, 'value', 0) or 0
            
            # Scale value for writing
            raw_value = int(power_w / (10 ** w_sf))
            
            success = await self._write_point(model, 'WDisChaMax', raw_value)
            
            if success:
                self._logger.info(f"Set discharge power to {power_w}W")
            
            return success
            
        except Exception as e:
            self._logger.error(f"Error setting discharge power: {e}")
            return False
    
    async def _write_point(self, model, point_name: str, value) -> bool:
        """Write a value to a model point."""
        try:
            point = getattr(model, point_name, None)
            if point is None:
                self._logger.error(f"Point {point_name} not found in model")
                return False
            
            # Set value
            if hasattr(point, 'value'):
                point.value = value
                return True
            
            return False
            
        except Exception as e:
            self._logger.error(f"Error writing point {point_name}: {e}")
            return False
    
    async def read_all(self, models: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Read all configured models.
        
        Args:
            models: List of model IDs to read, or None for all enabled
        
        Returns:
            Dictionary of all readings
        """
        if models is None:
            models = [
                self.MODEL_COMMON,
                self.MODEL_SOLAR_PV,
                self.MODEL_DER_MEASURE_AC,
                self.MODEL_DER_CAPACITY,
                self.MODEL_DER_STORAGE_CAPACITY,
                self.MODEL_DER_STORAGE_STATUS,
            ]
        
        results = {
            "timestamp": asyncio.get_event_loop().time(),
            "device_info": None,
            "battery": None,
            "inverter_ac": None,
            "capacity": None,
            "solar_pv": None,
            "home_loads": None,
        }
        
        # Read device info
        if self.MODEL_COMMON in models:
            results["device_info"] = await self.get_device_info()
        
        # Read battery metrics
        if self.MODEL_DER_STORAGE_CAPACITY in models or self.MODEL_DER_STORAGE_STATUS in models:
            results["battery"] = await self.get_battery_metrics()
        
        # Read inverter metrics
        if self.MODEL_DER_MEASURE_AC in models:
            results["inverter_ac"] = await self.get_inverter_ac_metrics()
        
        # Read capacity
        if self.MODEL_DER_CAPACITY in models:
            results["capacity"] = await self.get_der_capacity()
        
        # Read Solar PV (optional - may not be present on all systems)
        if self.MODEL_SOLAR_PV in models:
            results["solar_pv"] = await self.get_solar_pv_metrics()
        
        # Read Home Loads (extension registers - always try)
        results["home_loads"] = await self.get_home_load_metrics()
        
        return results
    
    async def read_sunspec_model_detailed(self, model_id: int) -> Optional[Dict]:
        """
        Read a SunSpec model and return detailed point information.
        
        Args:
            model_id: SunSpec model ID (e.g., 701)
        
        Returns:
            Dictionary with model info and list of points with names, values, units, etc.
        """
        model = await self.read_model(model_id)
        if model is None:
            return None
        
        points = []
        try:
            # Get model address
            base_addr = getattr(model, 'addr', 0)
            
            # Iterate through model points (OrderedDict)
            for point_name, point in model.points.items():
                try:
                    point_addr = getattr(point, 'addr', None)
                    
                    # Get value
                    raw_val = getattr(point, 'value', None)
                    
                    # Get scale factor if present
                    sf_val = None
                    sf_name = getattr(point, 'sf', None)
                    if sf_name and sf_name in model.points:
                        sf_point = model.points[sf_name]
                        sf_val = getattr(sf_point, 'value', None)
                    
                    # Get units
                    units = getattr(point, 'units', '') or ''
                    
                    # Get data type from pdef
                    type_str = 'unknown'
                    pdef = getattr(point, 'pdef', {})
                    if isinstance(pdef, dict):
                        type_str = pdef.get('type', 'unknown')
                    
                    # Get access mode (RW) - check if point is writable
                    access_str = 'R'
                    if isinstance(pdef, dict):
                        # Check if type indicates writability or if there's an access field
                        access = pdef.get('access', 'R')
                        access_str = 'RW' if 'W' in str(access) else 'R'
                    
                    # Calculate scaled value
                    scaled_val = raw_val
                    if raw_val is not None and sf_val is not None:
                        try:
                            scaled_val = raw_val * (10 ** sf_val)
                        except:
                            scaled_val = raw_val
                    
                    # Get label/description from pdef
                    label = point_name
                    if isinstance(pdef, dict):
                        label = pdef.get('label', pdef.get('desc', point_name))
                    
                    points.append({
                        'addr': point_addr,
                        'name': point_name,
                        'label': label,
                        'value': scaled_val,
                        'raw_value': raw_val,
                        'units': units,
                        'scale_factor': sf_val,
                        'access': access_str,
                        'type': type_str
                    })
                except Exception as e:
                    self._logger.debug(f"Error parsing point {point_name}: {e}")
                    continue
            
            # Get model name safely
            model_name = f'Model {model_id}'
            if hasattr(model, 'model'):
                try:
                    model_val = model.model
                    if isinstance(model_val, str):
                        model_name = model_val
                    elif hasattr(model_val, 'value'):
                        model_name = str(model_val.value)
                except:
                    pass
            
            return {
                'model_id': model_id,
                'model_name': model_name,
                'base_addr': base_addr,
                'length': getattr(model, 'len', 0),
                'points': points
            }
            
        except Exception as e:
            self._logger.error(f"Error reading model {model_id} details: {e}")
            return None
