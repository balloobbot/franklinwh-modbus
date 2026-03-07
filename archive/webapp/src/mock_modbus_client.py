"""
Mock Modbus client for testing without a real FranklinWH device.
Generates realistic simulated data for the web UI and MQTT.
"""

import asyncio
import logging
import random
import math
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import IntEnum

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

logger = logging.getLogger(__name__)


class MockFranklinWHModbusClient:
    """
    Mock Modbus client that simulates a FranklinWH battery system.
    Useful for testing the web UI and MQTT integration without hardware.
    """
    
    MODEL_COMMON = 1
    MODEL_SOLAR_PV = 502
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
        host: str = "mock://localhost",
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
        
        self._connected = False
        self._lock = asyncio.Lock()
        self._data_callbacks: List[Callable[[str, Any], None]] = []
        
        # Simulated device state
        self._soc = 75.0  # State of charge %
        self._soh = 96.5  # State of health %
        self._temperature = 28.5  # Temperature °C
        self._cycles = 342  # Cycle count
        self._operating_mode = 2  # 0=Standby, 1=Normal, 2=Backup Reserve, etc.
        self._reserve_soc = 20  # Self-Consumption Reserve (15508)
        self._reserve_soc_2 = 20  # TOU Reserve (15509) - using positive value
        
        # Simulated power values
        self._power_w = -1250  # Negative = discharging, positive = charging
        self._voltage_v = 240.5
        self._current_a = -5.2
        self._frequency_hz = 60.0
        self._power_factor = 0.98
        
        # Capacity
        self._rated_energy_wh = 13600  # 13.6 kWh
        self._available_energy_wh = 12500
        self._max_charge_w = 5000
        self._max_discharge_w = 5000
        
        # Battery Lifetime Energy (Model 714)
        self._dc_energy_injected_wh = 5317760  # Total discharged
        self._dc_energy_absorbed_wh = 5435940  # Total charged
        
        # Solar PV (Model 502)
        self._solar_output_power_w = 3200  # Current PV power
        self._solar_output_energy_wh = 11299612  # Lifetime PV energy
        
        # Home Loads (Extension registers 15500+)
        self._home_loads_w = 400  # Home consumption
        self._pv_output_w = 3200    # PV output
        self._pv_proximal_w = 3000  # Proximal PV
        
        # Device info - matching real aGate SunSpec Model 1
        self._device_info = DeviceInfo(
            manufacturer="FranklinWH Technologies Co., Ltd",
            model="aGate X",
            version="V10R01B04D00",
            serial_number="FWH123456789",
            device_address=unit_id,
        )
        
        # Background simulation task
        self._simulation_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("Mock Modbus client initialized")
    
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
                logger.error(f"Callback error: {e}")
    
    async def connect(self) -> bool:
        """Simulate connection to device."""
        async with self._lock:
            # Simulate connection delay
            await asyncio.sleep(0.5)
            self._connected = True
            self._running = True
            
            # Start simulation task
            self._simulation_task = asyncio.create_task(self._simulation_loop())
            
            logger.info(f"[MOCK] Connected to simulated FranklinWH device at {self.host}")
            logger.info(f"[MOCK] Device: {self._device_info.manufacturer} {self._device_info.model}")
            return True
    
    async def disconnect(self) -> None:
        """Simulate disconnection."""
        async with self._lock:
            self._running = False
            self._connected = False
            
            if self._simulation_task:
                self._simulation_task.cancel()
                try:
                    await self._simulation_task
                except asyncio.CancelledError:
                    pass
                self._simulation_task = None
            
            logger.info("[MOCK] Disconnected from simulated device")
    
    def close(self) -> None:
        """Close the mock client."""
        self._connected = False
        self._running = False
    
    async def _simulation_loop(self) -> None:
        """
        Background loop to simulate realistic battery behavior.
        Gradually changes values to simulate real device behavior.
        """
        while self._running:
            try:
                # Simulate SOC changes based on power flow
                if self._power_w > 0:  # Charging
                    charge_rate = self._power_w / self._rated_energy_wh / 3600  # % per second
                    self._soc = min(100, self._soc + charge_rate * 5)  # Update every 5s
                elif self._power_w < 0:  # Discharging
                    discharge_rate = abs(self._power_w) / self._rated_energy_wh / 3600
                    self._soc = max(0, self._soc - discharge_rate * 5)
                
                # Add small random variations to power
                power_variation = random.gauss(0, 50)  # 50W std dev
                self._power_w = max(-self._max_discharge_w, 
                                   min(self._max_charge_w, 
                                       self._power_w + power_variation))
                
                # Recalculate current based on power and voltage
                if self._voltage_v > 0:
                    self._current_a = self._power_w / self._voltage_v
                
                # Small voltage fluctuations
                self._voltage_v = 240.0 + random.gauss(0, 0.5)
                
                # Temperature slowly drifts
                self._temperature += random.gauss(0, 0.01)
                self._temperature = max(15, min(45, self._temperature))
                
                # Simulate occasional mode changes (rarely)
                if random.random() < 0.001:  # 0.1% chance per 5s
                    self._operating_mode = random.randint(0, 4)
                    logger.info(f"[MOCK] Operating mode changed to {self._operating_mode}")
                
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MOCK] Simulation error: {e}")
                await asyncio.sleep(5)
    
    async def read_model(self, model_id: int, force: bool = False) -> Optional[Any]:
        """Return mock model data."""
        # Return a mock object that mimics SunSpec model structure
        return MockModel(model_id)
    
    async def get_device_info(self) -> Optional[DeviceInfo]:
        """Return mock device info."""
        await self._notify_callbacks("device_info", self._device_info)
        return self._device_info
    
    async def get_battery_metrics(self) -> Optional[BatteryMetrics]:
        """Return simulated battery metrics."""
        metrics = BatteryMetrics(
            rated_energy_wh=self._rated_energy_wh,
            available_energy_wh=self._available_energy_wh,
            state_of_charge_percent=round(self._soc, 1),
            state_of_health_percent=self._soh,
            status=0,  # OK
            status_text="OK",
            temperature_c=round(self._temperature, 1),
            cycle_count=self._cycles,
            dc_energy_injected_wh=self._dc_energy_injected_wh,
            dc_energy_absorbed_wh=self._dc_energy_absorbed_wh,
        )
        await self._notify_callbacks("battery_metrics", metrics)
        return metrics
    
    async def get_inverter_ac_metrics(self) -> Optional[InverterACMetrics]:
        """Return simulated inverter metrics."""
        metrics = InverterACMetrics(
            power_w=round(self._power_w, 1),
            voltage_v=round(self._voltage_v, 1),
            current_a=round(self._current_a, 2),
            frequency_hz=round(self._frequency_hz + random.gauss(0, 0.01), 2),
            apparent_power_va=round(abs(self._power_w) / self._power_factor, 1),
            reactive_power_var=round(random.gauss(0, 50), 1),
            power_factor=round(self._power_factor + random.gauss(0, 0.01), 2),
            # New Model 701 fields
            ambient_temperature_c=round(25 + random.gauss(0, 2), 1),
            cabinet_temperature_c=round(35 + random.gauss(0, 3), 1),
            inverter_state=4,  # MPPT
            inverter_state_text="MPPT",
            grid_connection_state=1,  # Connected
            grid_connection_state_text="Connected",
            total_energy_injected_wh=12500000 + random.randint(0, 1000),
            total_energy_absorbed_wh=9800000 + random.randint(0, 1000),
        )
        await self._notify_callbacks("inverter_ac", metrics)
        return metrics
    
    async def get_der_capacity(self) -> Optional[DERCapacity]:
        """Return simulated capacity."""
        capacity = DERCapacity(
            max_charge_w=self._max_charge_w,
            max_discharge_w=self._max_discharge_w,
            max_charge_va=self._max_charge_w * 1.1,
            max_discharge_va=self._max_discharge_w * 1.1,
        )
        await self._notify_callbacks("der_capacity", capacity)
        return capacity
    
    async def set_battery_mode(self, mode: BatteryMode) -> bool:
        """Simulate setting battery mode."""
        mode_map = {
            BatteryMode.IDLE: 0,
            BatteryMode.CHARGING: 1,
            BatteryMode.DISCHARGING: 2,
        }
        self._operating_mode = mode_map.get(mode, 1)
        
        # Adjust power based on mode
        if mode == BatteryMode.IDLE:
            self._power_w = 0
        elif mode == BatteryMode.CHARGING:
            self._power_w = random.uniform(2000, 4000)
        elif mode == BatteryMode.DISCHARGING:
            self._power_w = random.uniform(-4000, -2000)
        
        logger.info(f"[MOCK] Battery mode set to {mode.name}")
        return True
    
    async def get_solar_pv_metrics(self) -> Optional[SolarPVMetrics]:
        """Return simulated Solar PV metrics."""
        # Simulate solar variation based on time of day
        hour = asyncio.get_event_loop().time() % 86400 / 3600  # 0-24
        # Peak at noon (12:00)
        solar_factor = max(0, math.sin((hour - 6) * math.pi / 12)) if 6 <= hour <= 18 else 0
        
        # Vary solar output
        base_output = self._solar_output_power_w * solar_factor
        current_output = base_output * random.uniform(0.9, 1.1)
        
        metrics = SolarPVMetrics(
            output_power_w=round(current_output, 0) if current_output > 0 else 0,
            output_energy_wh=self._solar_output_energy_wh,
        )
        await self._notify_callbacks("solar_pv", metrics)
        return metrics
    
    async def get_home_load_metrics(self) -> Optional[HomeLoadMetrics]:
        """Return simulated Home Load metrics."""
        # Home load varies based on solar (more consumption when solar available)
        base_load = self._home_loads_w
        current_load = base_load * random.uniform(0.8, 1.5)
        
        metrics = HomeLoadMetrics(
            home_loads_w=round(current_load, 0),
            pv_output_w=self._pv_output_w if self._pv_output_w > 0 else 0,
            pv_proximal_w=self._pv_proximal_w if self._pv_proximal_w > 0 else None,
            pv_output_wh=self._solar_output_energy_wh,
        )
        await self._notify_callbacks("home_loads", metrics)
        return metrics
    
    async def set_discharge_power(self, power_w: float, unit: str = "w") -> bool:
        """Simulate setting discharge power limit."""
        # Convert to watts
        if unit.lower() == "kw":
            power_w = power_w * 1000
        
        self._max_discharge_w = power_w
        logger.info(f"[MOCK] Max discharge power set to {power_w}W")
        return True
    
    async def read_all(self, models: Optional[List[int]] = None) -> Dict[str, Any]:
        """Read all simulated data."""
        return {
            "timestamp": asyncio.get_event_loop().time(),
            "device_info": await self.get_device_info(),
            "battery": await self.get_battery_metrics(),
            "inverter_ac": await self.get_inverter_ac_metrics(),
            "capacity": await self.get_der_capacity(),
            "solar_pv": await self.get_solar_pv_metrics(),
            "home_loads": await self.get_home_load_metrics(),
        }


class MockModel:
    """Mock SunSpec model for testing."""
    
    def __init__(self, model_id: int):
        self.model_id = model_id
        
        # Add some mock attributes based on model ID
        if model_id == 1:  # Common
            self.Mn = MockPoint("FranklinWH")
            self.Md = MockPoint("aPower")
            self.Vr = MockPoint("2.1.4")
            self.SN = MockPoint("FWH123456789")


class MockPoint:
    """Mock SunSpec point attribute."""
    
    def __init__(self, value):
        self.value = value
